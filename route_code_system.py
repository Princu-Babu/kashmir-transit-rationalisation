"""
route_code_system.py — Kashmir Valley deterministic Route-Code engine (v4, "geo-canonical").

================================================================================
WHY THIS EXISTS  (the structural rebuild)
================================================================================
The earlier route-code logic matched route-terminal *names* against a hand-built
stops master (`Kashmir_Stops_Sectored_V2.csv`). That master had three fatal
defects for government use:
  • unreliable coordinates (AIRPORT recorded ~80 km from the real airport,
    PARIMPORA ~18 km off);
  • undeduplicated spelling variants (R S PURA / RS PURA / RSPURA each a "stop");
  • wrong district tags (LALCHOWK -> Anantnag, AMRITSAR/LEH -> Shopian).
Name-matching against it produced wrong-district codes, A/B collisions for
distinct places, and was impossible to audit.

This module discards that master entirely and rebuilds the route-code system
from two TRUSTWORTHY foundations:

  1. COORDINATES — the engine's own geocoded route endpoints (district-aware
     Nominatim + curated gazetteer, already validated). One source of truth; the
     stops registry is built FROM the route endpoints, so route→stop linkage is
     EXACT (no fuzzy name matching).

  2. ADMINISTRATIVE GEOGRAPHY — authoritative OpenStreetMap boundaries:
       District  = admin_level 5  (kashmir_districts_osm.geojson, 10 districts)
       Tehsil    = admin_level 6  (kashmir_tehsils_osm.geojson, 39 tehsils)
     Every stop's District and Tehsil come from point-in-polygon against these
     real boundaries — not reverse-geocoding, not nearest-centroid, not a
     hand-typed column. (Verified: Hazratbal/Lal Chowk/Batamaloo -> Srinagar;
     Airport -> Budgam; Kangan/Manigam -> Ganderbal; Pampore -> Pulwama.)

================================================================================
THE CODE  (format preserved from the documented J&K convention)
================================================================================
A Route Code is 12 characters:  <Do><Dd><So><Sd><No><Nd>
  • <Do><Dd> : 2-letter ORIGIN district + 2-letter DEST district   (4 letters)
  • <So><Sd> : 2-digit  ORIGIN sector   + 2-digit  DEST sector     (4 digits)
  • <No><Nd> : 2-digit  ORIGIN stop-no  + 2-digit  DEST stop-no    (4 digits)
Readable display form (hyphenated):  SRGB-0102-0305
  = Srinagar->Ganderbal, sector 01->02, stop 03->05.

Where:
  • DISTRICT  — the 2-letter code of the OSM district the endpoint falls in.
  • SECTOR    — the endpoint's TEHSIL, numbered 1..N within its district
                (tehsils sorted alphabetically over ALL of the district's
                tehsils, so a sector number is STABLE even if stop coverage
                changes). Sector = a real revenue tehsil, not an arbitrary grid.
  • STOP-NO   — the canonical stop, numbered 1..M within its (district, tehsil),
                stops sorted alphabetically by name.

Two routes receive the same 12-char code ONLY if they share the SAME canonical
origin stop AND the SAME canonical destination stop — i.e. they are genuinely the
same terminal pair. Such a true collision gets a trailing letter (A/B/C, the
standard "5A/5B" bus convention). Distinct places never collide, because each
canonical stop has a distinct (district, tehsil, stop-no).

================================================================================
DETERMINISM  (required for government uniformity)
================================================================================
Every step is a pure function of the inputs. No randomness, no run-to-run drift:
  • endpoints sorted before clustering;
  • greedy proximity clustering with a fixed radius (DEDUP_RADIUS_M);
  • sectors numbered from the fixed OSM tehsil list;
  • stops numbered alphabetically;
  • letter suffixes assigned by sorted route name.
Re-running on the same inputs yields byte-identical codes.

District 2-letter codes (OSM district name -> code):
"""
from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from typing import Dict, List, Optional, Tuple

import pandas as pd

try:
    import json as _json
    from shapely.geometry import Point, shape
except Exception as _e:  # pragma: no cover
    Point = shape = None  # type: ignore

# ── District name (OSM) -> official 2-letter code ────────────────────────────
DISTRICT_2L: Dict[str, str] = {
    "Srinagar": "SR", "Ganderbal": "GB", "Bandipore": "BP", "Baramulla": "BR",
    "Kupwara": "KW", "Budgam": "BG", "Pulwama": "PW", "Shopian": "SP",
    "Anantnag": "AN", "Kulgam": "KG",
}

DEDUP_RADIUS_M = 150.0      # co-located distinct names within this = one stop
_DEG = 111_000.0           # metres per degree latitude (lon scaled by cos lat)

# Tokens that are route-name decoration, not part of a place identity. Stripped
# only for the readable representative name (clustering uses coordinates).
_NOISE = re.compile(
    r"\b(BUS\s+STAND|BUS\s+STATION|RAILWAY\s+STATION|BUS\s+STOP|CROSSING|"
    r"CHOWK|CHOK|STAND|STOP)\b", re.I)


# ─────────────────────────────────────────────────────────────────────────────
# Name handling
# ─────────────────────────────────────────────────────────────────────────────
def _clean_display(name: str) -> str:
    """Readable, title-cased representative stop name."""
    s = re.sub(r"\s+", " ", str(name).replace("↔", " to ")).strip(" -,;")
    if not s or s.lower() in ("nan", "none"):
        return ""
    # Title-case but keep short all-caps acronyms (LD, TRC, GBS, HMT, SMHS…)
    out = []
    for tok in s.split():
        bare = re.sub(r"[^A-Za-z0-9]", "", tok)
        if bare.isupper() and 2 <= len(bare) <= 4 and bare.isalpha():
            out.append(tok.upper())
        else:
            out.append(tok[:1].upper() + tok[1:].lower())
    return " ".join(out)


def _norm_key(name: str) -> str:
    """Normalised comparison key (used only to pick a cluster's representative)."""
    s = _NOISE.sub("", str(name).upper())
    return re.sub(r"[^A-Z0-9]", "", s)


def extract_origin_dest(route_name: str) -> Tuple[str, str]:
    """'A to B via C' -> ('A','B'). Mirrors the engine's route-name grammar."""
    s = str(route_name).replace(" ↔ ", " to ").strip()
    low = s.lower()
    if " to " in low:
        i = low.index(" to ")
        origin = s[:i].strip()
        rest = s[i + 4:]
        dest = re.split(r"\s+via\s+", rest, flags=re.I)[0].strip()
        return origin, dest
    return s.strip(), ""


# ─────────────────────────────────────────────────────────────────────────────
# Administrative geography (OSM point-in-polygon)
# ─────────────────────────────────────────────────────────────────────────────
class AdminIndex:
    """District + tehsil polygons with a stable sector (tehsil) numbering."""

    def __init__(self, districts_geojson: str, tehsils_geojson: str):
        dj = _json.load(open(districts_geojson, encoding="utf-8"))
        tj = _json.load(open(tehsils_geojson, encoding="utf-8"))
        self.districts = [(f["properties"]["district"], shape(f["geometry"]))
                          for f in dj["features"]]
        self.tehsils = [(f["properties"]["tehsil"], f["properties"]["district"],
                         shape(f["geometry"])) for f in tj["features"]]
        # Stable sector numbering: tehsils sorted alphabetically WITHIN each
        # district -> 1..N. Covers ALL tehsils (not just populated ones) so a
        # sector number never shifts when stop coverage changes.
        by_dist: Dict[str, List[str]] = defaultdict(list)
        for tname, dname, _ in self.tehsils:
            by_dist[dname].append(tname)
        self.sector_no: Dict[Tuple[str, str], int] = {}
        for dname, tlist in by_dist.items():
            for i, tname in enumerate(sorted(set(tlist)), start=1):
                self.sector_no[(dname, tname)] = i

    def locate(self, lat: float, lon: float) -> Tuple[str, str, int]:
        """Return (district_name, tehsil_name, sector_no) for a coordinate.
        Uses point-in-polygon; falls back to the nearest polygon for points just
        outside a boundary (slightly-off geocodes, lakeshores, etc.)."""
        p = Point(lon, lat)
        dname = None
        for n, poly in self.districts:
            if poly.contains(p):
                dname = n
                break
        if dname is None:  # nearest district
            dname = min(self.districts, key=lambda x: x[1].distance(p))[0]
        cand = [(n, poly) for n, dd, poly in self.tehsils if dd == dname]
        tname = None
        for n, poly in cand:
            if poly.contains(p):
                tname = n
                break
        if tname is None and cand:
            tname = min(cand, key=lambda x: x[1].distance(p))[0]
        sec = self.sector_no.get((dname, tname), 0)
        return dname, tname, sec


# ─────────────────────────────────────────────────────────────────────────────
# Canonical stop registry (proximity dedup)
# ─────────────────────────────────────────────────────────────────────────────
def _haversine_m(a_lat, a_lon, b_lat, b_lon) -> float:
    dlat = (b_lat - a_lat) * _DEG
    dlon = (b_lon - a_lon) * _DEG * math.cos(math.radians((a_lat + b_lat) / 2))
    return math.hypot(dlat, dlon)


def build_canonical_stops(endpoints: List[Tuple[str, float, float]],
                          radius_m: float = DEDUP_RADIUS_M):
    """Deterministic FIXED-ANCHOR proximity clustering of (name, lat, lon) points.

    Returns (clusters, point_to_cluster) where clusters[i] = dict(lat, lon, name,
    names Counter, n) and point_to_cluster maps each input endpoint index to its
    cluster id.

    Each cluster is anchored by its FIRST point (in a fixed sort order); a later
    point joins the cluster whose ANCHOR is nearest AND within ``radius_m``,
    otherwise it opens a new cluster. The anchor never moves — this is the key
    property: it prevents the "chaining" that a running-mean centroid suffers
    (where A–B–C each 300 m apart would drift into one 600 m-wide blob, e.g.
    LD and TRC, 2 km apart, wrongly merging). Cluster diameter is therefore
    bounded by 2·radius. The display coordinate is the mean of the members.
    Input is sorted first, so the result is independent of route order.
    """
    order = sorted(range(len(endpoints)),
                   key=lambda i: (round(endpoints[i][1], 6),
                                  round(endpoints[i][2], 6),
                                  _norm_key(endpoints[i][0])))
    clusters: List[dict] = []
    point_to_cluster: Dict[int, int] = {}
    for idx in order:
        nm, la, lo = endpoints[idx]
        best, best_d = -1, radius_m
        for ci, c in enumerate(clusters):
            d = _haversine_m(la, lo, c["alat"], c["alon"])   # vs fixed ANCHOR
            if d <= best_d:
                best, best_d = ci, d
        if best < 0:
            clusters.append({"alat": la, "alon": lo, "slat": la, "slon": lo,
                             "n": 1, "names": Counter([_clean_display(nm)] if nm else [])})
            point_to_cluster[idx] = len(clusters) - 1
        else:
            c = clusters[best]
            c["slat"] += la; c["slon"] += lo; c["n"] += 1     # accumulate for mean
            if nm:
                c["names"][_clean_display(nm)] += 1
            point_to_cluster[idx] = best
    for c in clusters:
        c["lat"] = c["slat"] / c["n"]            # display centroid = mean
        c["lon"] = c["slon"] / c["n"]
        if c["names"]:
            c["name"] = sorted(c["names"].items(),
                               key=lambda kv: (-kv[1], len(kv[0]), kv[0]))[0][0]
        else:
            c["name"] = f"STOP_{c['lat']:.4f}_{c['lon']:.4f}"
    return clusters, point_to_cluster


# ─────────────────────────────────────────────────────────────────────────────
# Main entry — build master + assign route codes
# ─────────────────────────────────────────────────────────────────────────────
def assign(routes: List[dict], admin: AdminIndex,
           radius_m: float = DEDUP_RADIUS_M):
    """Assign deterministic route codes + build the canonical stop master.

    routes: list of dicts, each with:
        route_name, o_lat, o_lon, d_lat, d_lon, active (bool)
    Returns (codes, master_df, stats) where codes is a list aligned to ``routes``.
    """
    # 1. Endpoints (origin + dest of every route). Record each route's origin and
    #    destination NORMALISED name so the route links to a stop by identity.
    raw_eps: List[Tuple[str, str, float, float]] = []   # (norm, display, lat, lon)
    o_key, d_key = [], []
    for r in routes:
        o_name, d_name = extract_origin_dest(r["route_name"])
        ok, dk = _norm_key(o_name), _norm_key(d_name)
        o_key.append(ok); d_key.append(dk)
        raw_eps.append((ok, o_name, r["o_lat"], r["o_lon"]))
        raw_eps.append((dk, d_name, r["d_lat"], r["d_lon"]))

    # 2. Aggregate by NORMALISED NAME -> one representative coordinate per name.
    #    This guarantees the same place name always resolves to one stop (the
    #    geocoder occasionally returned 2 slightly different coords for one name —
    #    e.g. "TRC" — which must not split into two stops).
    by_name: Dict[str, List[Tuple[str, float, float]]] = defaultdict(list)
    for ok, disp, la, lo in raw_eps:
        if ok:
            by_name[ok].append((disp, la, lo))
    name_pts: List[Tuple[str, float, float]] = []   # (display, lat, lon) per name
    name_order: List[str] = []
    for ok in sorted(by_name):
        recs = by_name[ok]
        # representative coord = most common rounded coord (tie -> first sorted)
        cc = Counter((round(la, 5), round(lo, 5)) for _, la, lo in recs)
        (rla, rlo), _ = sorted(cc.items(), key=lambda kv: (-kv[1], kv[0]))[0]
        disp = sorted((d for d, _, _ in recs), key=lambda s: (len(s), s))[0]
        name_order.append(ok)
        name_pts.append((disp, rla, rlo))

    # 3. Canonical stops = proximity-merge of co-located distinct names.
    clusters, name_to_cluster_idx = build_canonical_stops(name_pts, radius_m)
    norm_to_cluster: Dict[str, int] = {
        name_order[i]: name_to_cluster_idx[i] for i in range(len(name_order))}

    def _cluster_of(norm: str, lat: float, lon: float) -> int:
        ci = norm_to_cluster.get(norm)
        if ci is not None:
            return ci
        # fallback: nearest cluster by coordinate (empty/odd names)
        return min(range(len(clusters)),
                   key=lambda j: _haversine_m(lat, lon, clusters[j]["lat"], clusters[j]["lon"]))

    p2c = {}  # kept for parity (unused downstream)

    # 3. District + tehsil(sector) for every canonical stop (point-in-polygon).
    for c in clusters:
        dname, tname, sec = admin.locate(c["lat"], c["lon"])
        c["district"] = dname
        c["tehsil"] = tname
        c["dist2"] = DISTRICT_2L.get(dname, dname[:2].upper())
        c["sector"] = sec

    # 4. Stop numbers: within each (district, sector), alphabetical by name.
    groups: Dict[Tuple[str, int], List[int]] = defaultdict(list)
    for ci, c in enumerate(clusters):
        groups[(c["dist2"], c["sector"])].append(ci)
    for (_, _), cis in groups.items():
        for n, ci in enumerate(sorted(cis, key=lambda j: (clusters[j]["name"],
                                                          round(clusters[j]["lat"], 5))),
                               start=1):
            clusters[ci]["stop_no"] = n

    def _code_of(ci: int) -> Tuple[str, str, str]:
        c = clusters[ci]
        return c["dist2"], f"{c['sector']:02d}", f"{c['stop_no']:02d}"

    # 5. Route codes = origin stop + dest stop (linked by NAME -> canonical stop).
    raw_codes: List[str] = []
    for i, r in enumerate(routes):
        od, os_, on = _code_of(_cluster_of(o_key[i], r["o_lat"], r["o_lon"]))
        dd, ds, dn = _code_of(_cluster_of(d_key[i], r["d_lat"], r["d_lon"]))
        raw_codes.append(f"{od}{dd}{os_}{ds}{on}{dn}")

    # 6. Letter suffix only for genuine same-stop-pair collisions among ACTIVE routes.
    active = [bool(r.get("active", True)) for r in routes]
    names = [str(r["route_name"]) for r in routes]
    counts = Counter(c for c, a in zip(raw_codes, active) if a)
    coll = defaultdict(list)
    for i, (c, a) in enumerate(zip(raw_codes, active)):
        if a and counts[c] > 1:
            coll[c].append(i)
    suffix: Dict[int, str] = {}
    for c, idxs in coll.items():
        for rank, i in enumerate(sorted(idxs, key=lambda j: names[j])):
            suffix[i] = chr(ord("A") + rank) if rank < 26 else f"Z{rank}"
    codes = [(c + suffix[i]) if i in suffix else c for i, c in enumerate(raw_codes)]

    # 7. Canonical master table.
    rows = []
    for c in clusters:
        rows.append({
            "Master_Stop_Code": f"{c['dist2']}-{c['sector']:02d}-{c['stop_no']:02d}",
            "Stop_Name": c["name"], "District": c["district"], "Tehsil": c["tehsil"],
            "Tehsil_Code": c["dist2"], "Sector_ID": c["sector"], "Stop_No": c["stop_no"],
            "Latitude": round(c["lat"], 6), "Longitude": round(c["lon"], 6),
            "N_Endpoints": c["n"],
        })
    master = pd.DataFrame(rows).sort_values(
        ["Tehsil_Code", "Sector_ID", "Stop_No"]).reset_index(drop=True)

    stats = {
        "endpoints": len(raw_eps), "unique_names": len(name_pts),
        "canonical_stops": len(clusters),
        "active_routes": sum(active), "letter_suffixed": len(suffix),
        "districts_used": master["District"].nunique(),
        "sectors_used": master[["Tehsil_Code", "Sector_ID"]].drop_duplicates().shape[0],
    }
    return codes, master, stats


def _resolve(fname: str) -> str:
    """Find a data file in the cwd, then alongside this module."""
    import os
    for p in (fname, os.path.join(os.path.dirname(os.path.abspath(__file__)), fname)):
        if os.path.exists(p):
            return p
    return fname


def load_admin(districts_path: str = "kashmir_districts_osm.geojson",
               tehsils_path: str = "kashmir_tehsils_osm.geojson") -> AdminIndex:
    return AdminIndex(_resolve(districts_path), _resolve(tehsils_path))
