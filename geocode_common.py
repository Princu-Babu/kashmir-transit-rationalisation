"""
geocode_common.py — shared, hardened geocoding for latlon.py and
geocode_other_routes.py.
======================================================================================
Fixes audit Findings 1, 2 and 5 (Recommendation 1) at the root.

ROOT CAUSE the audit found
--------------------------
Both geocoders queried ArcGIS with the over-narrow context
``"{place}, Srinagar, Kashmir, India"``. For any valley town ArcGIS could not
resolve, it fell back to matching the next token — **"Srinagar"** — and returned
the city centroid (34.085650, 74.805550). 118 distinct valley place names
(Anantnag, Pampore, Budgam, Pulwama, Sopore, Kulgam, Shopian, …) collapsed onto
that single point, so 290 routes became zero-length and were silently dropped at
the engine's sub-1 km filter. The plan then "rationalised" a network missing
most of JKRTC's actual inter-district operation.

WHAT THIS MODULE CHANGES
------------------------
1. **District-aware query.** Known valley towns carry their district into the
   query: ``"Anantnag, Anantnag, Jammu and Kashmir, India"`` instead of
   ``"Anantnag, Srinagar, …"`` — so the geocoder is not pulled toward Srinagar.
2. **Valley study extent.** Results are constrained to the Kashmir-valley
   bounding box (passed to ArcGIS as ``search_extent`` when available).
3. **Centroid-collision rejection.** Any result within
   ``CENTROID_REJECT_M`` of the Srinagar centroid is REJECTED (returns None)
   unless the input name is itself Srinagar — a snap to the exact LD-Hospital
   centroid means the geocoder fell back, not that it found the place. The row
   is then recorded as a failure to be resolved manually, never silently
   collapsed onto Srinagar.
4. **Auditable failures.** ``write_failures()`` emits ``geocode_failures.csv``
   so every name that could not be placed is recorded with a reason.

This module has NO hard dependency on arcgis: callers pass a ``geocode_fn`` that
returns a list of result dicts (the arcgis.geocoding.geocode signature) OR None.
That keeps it testable and lets a future Nominatim/Photon backend drop in.
"""
from __future__ import annotations

import csv
import math
import re
import time as _time
from typing import Callable, Dict, List, Optional, Tuple

# ── Srinagar centroid the broken context collapsed everything onto ──
SRINAGAR_CENTROID = (34.085650, 74.805550)   # (lat, lon) — LD Hospital area
CENTROID_REJECT_M = 300.0                     # reject snaps within this radius

# ── Kashmir-valley study extent (generous; the engine still bbox-clips) ──
#   covers Anantnag/Kulgam/Shopian in the south up to Bandipora/Handwara north.
VALLEY_EXTENT = {  # xmin/ymin/xmax/ymax in lon/lat (ArcGIS search_extent order)
    "xmin": 74.10, "ymin": 33.45, "xmax": 75.45, "ymax": 34.75,
    "spatialReference": {"wkid": 4326},
}

# ── District hints for the known out-of-Srinagar valley towns ──
# token (UPPERCASE) -> district. Only high-confidence town->district pairs; any
# name not listed falls back to a valley-wide context, and the extent + centroid
# rejection remain the safety net regardless.
DISTRICT_HINTS: Dict[str, str] = {
    # Anantnag
    "ANANTNAG": "Anantnag", "ANANTNAGH": "Anantnag", "BIJBEHARA": "Anantnag",
    "MATTAN": "Anantnag", "PAHALGAM": "Anantnag", "PHALGAM": "Anantnag",
    "DOORU": "Anantnag", "KOKERNAG": "Anantnag", "ACHABAL": "Anantnag",
    "SHANGUS": "Anantnag", "LARNOO": "Anantnag", "VERINAG": "Anantnag",
    "QAZIGUND": "Anantnag", "SALIA": "Anantnag", "LAMMER": "Anantnag",
    "KHERUM": "Anantnag", "MATIGAWRAN": "Anantnag",
    # Pulwama
    "PULWAMA": "Pulwama", "PAMPORE": "Pulwama", "TRAL": "Pulwama",
    "AWANTIPORA": "Pulwama", "AWANTIPURA": "Pulwama", "KAKAPORA": "Pulwama",
    "RAJPORA": "Pulwama", "PINGLENA": "Pulwama", "GALANDAR": "Pulwama",
    "NEWA": "Pulwama", "KHREW": "Pulwama", "RATNIPORA": "Pulwama",
    "RATINPORA": "Pulwama", "LELHAR": "Pulwama",
    # Shopian
    "SHOPIAN": "Shopian", "KELLER": "Shopian", "ZAINAPORA": "Shopian",
    # Kulgam
    "KULGAM": "Kulgam", "QAIMOH": "Kulgam", "FRISAL": "Kulgam",
    "DEVSAR": "Kulgam", "DAMHAL": "Kulgam", "YARIPORA": "Kulgam",
    # Budgam
    "BUDGAM": "Budgam", "CHADOORA": "Budgam", "CHADURA": "Budgam",
    "BEERWAH": "Budgam", "KHANSAHIB": "Budgam", "MAGAM": "Budgam",
    "CHRAR": "Budgam", "CHARARI SHARIEF": "Budgam", "KHANSHAIB": "Budgam",
    # Baramulla
    "BARAMULLA": "Baramulla", "BARAMULA": "Baramulla", "SOPORE": "Baramulla",
    "PATTAN": "Baramulla", "URI": "Baramulla", "TANGMARG": "Baramulla",
    "KUNZER": "Baramulla", "BONIYAR": "Baramulla", "WAGOORA": "Baramulla",
    "RAFIABAD": "Baramulla", "SANGRAMA": "Baramulla",
    # Bandipora
    "BANDIPORA": "Bandipora", "SUMBAL": "Bandipora", "HAJIN": "Bandipora",
    "GUREZ": "Bandipora", "ALOOSA": "Bandipora", "ARIN": "Bandipora",
    # Ganderbal
    "GANDERBAL": "Ganderbal", "KANGAN": "Ganderbal", "LAR": "Ganderbal",
    "SONAMARG": "Ganderbal", "GUND": "Ganderbal", "WAYIL": "Ganderbal",
    # Kupwara
    "KUPWARA": "Kupwara", "HANDWARA": "Kupwara", "CHOWKIBAL": "Kupwara",
    "CHOWKBAL": "Kupwara", "KARNAH": "Kupwara", "TANGDAR": "Kupwara",
    "TANGDHAR": "Kupwara", "SOGAM": "Kupwara", "TREHGAM": "Kupwara",
    "KRALPORA": "Kupwara", "LANGATE": "Kupwara",
}


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def is_srinagar_centroid(lat: float, lon: float,
                         tol_m: float = CENTROID_REJECT_M) -> bool:
    """True if (lat, lon) is within tol_m of the Srinagar collapse point."""
    return _haversine_m(lat, lon, *SRINAGAR_CENTROID) <= tol_m


# Spelling normalisation: the permit data records Srinagar localities with
# concatenated / non-standard spellings the geocoder can't match (BATAMAALO,
# PANTHACHOWK, LALCHOWK …). Map the cleaned token to a canonical, OSM-resolvable
# name — coordinates still come from the geocoder, we only fix the query string.
NAME_ALIASES: Dict[str, str] = {
    "BATAMAALO": "Batamaloo", "BATAMALLO": "Batamaloo", "BATAMALOO": "Batamaloo",
    "LALCHOWK": "Lal Chowk", "LAL CHOWK": "Lal Chowk",
    "PANTHACHOWK": "Pantha Chowk", "PANTHACHOK": "Pantha Chowk",
    "PATHACHOWK": "Pantha Chowk", "PANTHA CHOK": "Pantha Chowk",
    "NOWHATA": "Nowhatta", "SONAWAR": "Sonwar", "SONWAR": "Sonwar",
    "RAINAWARA": "Rainawari", "KARANANGAR": "Karan Nagar",
    "ZONIMAR": "Zoonimar", "BOHRIKADAL": "Bohri Kadal",
    "RAJIAKADAL": "Raja Kadal", "RAZIAKADAL": "Raja Kadal",
    "ILLAHIBAGH": "Ilahibagh", "JAWAHIRNAGAR": "Jawahar Nagar",
    "JAWAHAIRNAGAR": "Jawahar Nagar", "RANGRATH": "Rangreth",
    "SORA": "Soura", "CHADORA": "Chadoora", "JEHANGIR CHOWK": "Jehangir Chowk",
    "BAGHI MEHTAB": "Bagh-i-Mehtab", "ILLAHI BAGH": "Ilahibagh",
}


# Authoritative coordinate pins for hubs the public geocoder places poorly
# (F-V3). Checked BEFORE the API in geocode_one(). Parimpora & LD use the same
# coords as the SSCL synthetic routes so permit-derived and SSCL services share
# the terminal; Airport/TRC verified against OSM. Keys are cleaned (UPPER) names
# in the forms the two cleaners emit.
GAZETTEER: Dict[str, Tuple[float, float]] = {
    "PARIMPORA": (34.1112, 74.7475),          # actual bus-stand/mandi (OSM gives a bypass rd 4.6 km off)
    "LD": (34.0822, 74.8059),
    "LD HOSPITAL": (34.0822, 74.8059),
    "LAL DED HOSPITAL SRINAGAR": (34.0822, 74.8059),
    "AIRPORT": (33.9934, 74.7752),            # Sheikh ul-Alam Int'l Airport
    "SRINAGAR AIRPORT": (33.9934, 74.7752),
    "TRC": (34.0747, 74.8247),
    "TRC SRINAGAR": (34.0747, 74.8247),
}


def _load_gazetteer_csv() -> int:
    """Merge curated village coordinates from kashmir_gazetteer.csv into GAZETTEER
    (recovered village/town centres + district-centre approximations, so no route
    is dropped for lack of coordinates). Hardcoded pins above take precedence."""
    import csv as _csv
    import os as _os
    n = 0
    for p in ("kashmir_gazetteer.csv",
              _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "kashmir_gazetteer.csv")):
        if _os.path.exists(p):
            try:
                with open(p, encoding="utf-8") as f:
                    for row in _csv.DictReader(f):
                        nm = str(row.get("name", "")).strip().upper()
                        la, lo = row.get("lat", ""), row.get("lon", "")
                        if nm and str(la) and str(lo) and nm not in GAZETTEER:
                            GAZETTEER[nm] = (float(la), float(lo))
                            n += 1
            except Exception:
                pass
            break
    return n


_GAZETTEER_CSV_LOADED = _load_gazetteer_csv()


def _first_token(name: str) -> str:
    return re.split(r"[\s\-]+", name.strip().upper(), maxsplit=1)[0] if name else ""


def _canonical(location_name: str) -> str:
    return NAME_ALIASES.get(location_name.strip().upper(), location_name)


def build_query(location_name: str) -> str:
    """District-aware query string. Applies a spelling alias, then a known
    town→district hint; falls back to a valley-wide context."""
    up = location_name.strip().upper()
    canon = _canonical(location_name)
    district = (DISTRICT_HINTS.get(up) or DISTRICT_HINTS.get(_first_token(up))
                or DISTRICT_HINTS.get(canon.strip().upper()))
    if district:
        return f"{canon}, {district}, Jammu and Kashmir, India"
    # Srinagar localities and everything else: keep the city/valley context but
    # NOT as the sole disambiguator — the extent + centroid rejection guard it.
    return f"{canon}, Srinagar, Jammu and Kashmir, India"


def geocode_one(location_name: str,
                geocode_fn: Callable[..., Optional[list]],
                failures: Optional[List[Dict]] = None
                ) -> Tuple[Optional[float], Optional[float]]:
    """Geocode a single name with all guards applied.

    geocode_fn(query, search_extent=...) -> list of {'location': {'x','y'}} | None
    Returns (lat, lon) or (None, None). On failure, appends a reason row to
    ``failures`` if provided.
    """
    # Authoritative pin first (F-V3) — overrides the public geocoder for hubs it
    # places poorly (e.g. Parimpora, the busiest origin).
    pin = GAZETTEER.get(location_name.strip().upper())
    if pin is not None:
        return pin

    name_is_srinagar = "SRINAGAR" in location_name.upper()
    query = build_query(location_name)
    try:
        try:
            results = geocode_fn(query, search_extent=VALLEY_EXTENT)
        except TypeError:
            # geocode_fn without search_extent support (older signature / tests)
            results = geocode_fn(query)
    except Exception as exc:  # noqa: BLE001 — record, don't crash the batch
        if failures is not None:
            failures.append({"name": location_name, "query": query,
                             "reason": f"api_error: {exc}"})
        return None, None

    if not results:
        if failures is not None:
            failures.append({"name": location_name, "query": query,
                             "reason": "no_result"})
        return None, None

    loc = results[0]["location"]
    lat, lon = float(loc["y"]), float(loc["x"])

    # Reject a fallback snap to the Srinagar centroid for non-Srinagar names.
    if not name_is_srinagar and is_srinagar_centroid(lat, lon):
        if failures is not None:
            failures.append({"name": location_name, "query": query,
                             "reason": "rejected_srinagar_centroid_collision"})
        return None, None

    # Reject anything well outside the valley extent.
    if not (VALLEY_EXTENT["ymin"] <= lat <= VALLEY_EXTENT["ymax"] and
            VALLEY_EXTENT["xmin"] <= lon <= VALLEY_EXTENT["xmax"]):
        if failures is not None:
            failures.append({"name": location_name, "query": query,
                             "reason": f"outside_valley_extent ({lat:.4f},{lon:.4f})"})
        return None, None

    return lat, lon


# ── requests-based Nominatim backend (no arcgis dependency) ───────────────────
# The audit (Recommendation 1) suggests Nominatim with a district viewbox as a
# second geocoder. It is also a drop-in replacement when the heavy `arcgis`
# package is not installed, so the re-geocode can run anywhere `requests` is.
_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_NOMINATIM_UA  = ("kashmir-transit-rationalisation/3.3.8 "
                  "(RTO audit remediation; contact: imassolutionss@gmail.com)")
_LAST_NOMINATIM_CALL = [0.0]   # mutable holder for simple 1 req/sec throttling


def nominatim_geocode(query: str, search_extent: Optional[dict] = None):
    """Geocoder with the ArcGIS result shape, backed by OSM Nominatim via
    `requests`. Returns ``[{'location': {'x': lon, 'y': lat}}]`` or ``[]``
    (None on transport error). Honours Nominatim's 1 req/sec usage policy.
    """
    import requests

    def _call(bounded: bool):
        dt = _time.time() - _LAST_NOMINATIM_CALL[0]
        if dt < 1.1:
            _time.sleep(1.1 - dt)
        params = {"q": query, "format": "json", "limit": 1}
        if search_extent:
            # viewbox order is xmin,ymax,xmax,ymin (lon/lat)
            params["viewbox"] = (f"{search_extent['xmin']},{search_extent['ymax']},"
                                 f"{search_extent['xmax']},{search_extent['ymin']}")
            if bounded:
                params["bounded"] = 1
        try:
            r = requests.get(_NOMINATIM_URL, params=params,
                             headers={"User-Agent": _NOMINATIM_UA}, timeout=20)
            _LAST_NOMINATIM_CALL[0] = _time.time()
            r.raise_for_status()
            return r.json()
        except Exception:
            return None

    # Pass 1: bounded to the valley (strict). Pass 2: soft viewbox bias only, so
    # spelling/POI variants OSM only knows globally still resolve — the caller's
    # valley-extent + Srinagar-centroid checks remain the safety net either way.
    j = _call(bounded=True)
    if not j:
        j = _call(bounded=False)
    if not j:
        return [] if j == [] else None
    return [{"location": {"x": float(j[0]["lon"]), "y": float(j[0]["lat"])}}]


def get_default_geocoder() -> Tuple[Callable, str]:
    """Return (geocode_fn, backend_name): the arcgis package if importable and
    a GIS session can be created, else the requests-based Nominatim backend."""
    try:
        from arcgis.gis import GIS              # noqa: F401
        from arcgis.geocoding import geocode as _arcgis_geocode
        GIS()                                   # anonymous session
        return _arcgis_geocode, "arcgis"
    except Exception:
        return nominatim_geocode, "nominatim (OSM)"


def write_failures(failures: List[Dict], path: str = "geocode_failures.csv") -> None:
    """Emit an auditable reject file so no drop is ever silent (Finding 2)."""
    if not failures:
        print(f"[OK] No geocode failures to report ({path} not written).")
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["name", "query", "reason"])
        w.writeheader()
        w.writerows(failures)
    print(f"[AUDIT] {len(failures)} geocode failures written to {path} "
          f"(resolve these manually — they are NOT in existing-routes.csv).")
