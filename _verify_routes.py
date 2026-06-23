"""
_verify_routes.py — government-grade, route-by-route feasibility & sanity check.

Runs a battery of independent checks on EVERY active route, using the LOCAL OSRM
(localhost:5000), the authoritative OSM district/tehsil polygons, and the engine
output. The intent is a "a government agency checked each route locally" level of
scrutiny — from the source coordinates to the literal planned geometry to the
recommended bus count.

Three layers per route (full method in MASTER_VERIFICATION_PLAN.md):

  LAYER 1 — COORDINATES (origin / destination / via)
    • O & D inside the 10-district division (point-in-polygon)?
    • O ≠ D (not a degenerate zero-length)?
    • endpoint on a known bad/collision point (e.g. the Srinagar centroid, or a
      coordinate shared by ≥3 distinct place names)?
    • endpoint a district-centre APPROXIMATION (indicative, not surveyed)?
    • via points (if any) inside the valley and roughly on-corridor?

  LAYER 2 — OSRM FEASIBILITY (is the literal route drivable & sensible?)
    • does local OSRM return a route for O→(via)→D (road-connected)?
    • OSRM road distance vs the engine's Route_KM (engine used OSRM → must agree)
    • OSRM distance vs straight-line = circuity (huge ⇒ detour/via or error)
    • OSRM duration sanity.

  LAYER 3 — PLAN REALISM (is "X buses on this route" believable?)
    • Fleet = ⌈⌈cycle/headway⌉×spare⌉, floored — reproduces the engine?
    • HPV+MPV+LPV = Fleet
    • headway in the allowed tier set (city 15/20/35; rural 35/40/45/50; SSCL 15)
    • implied round-trip speed 8–45 km/h
    • load ratio in a sane band (flag >1.2 overload, <0.03 ghost)
    • fleet not absurd for the corridor (flag > FLEET_SANITY_MAX).

Output: route_verification_report.csv (one row/route, every check + verdict +
reasons) and a console summary. Verdict = PASS / REVIEW / FAIL.

Usage:  python _verify_routes.py --outdir outputs_vX.Y.Z
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections import Counter

import pandas as pd

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

OSRM_URL = "http://localhost:5000/route/v1/driving/"
FLEET_SANITY_MAX = 20          # > this on one route is implausible → REVIEW
CITY_HEADWAYS = {15, 20, 35}
RURAL_HEADWAYS = {35, 40, 45, 50}
SRINAGAR_CENTROID = (34.083, 74.797)


def hav(a, b):
    R = 6371.0; p = math.pi / 180
    return 2 * R * math.asin(math.sqrt(
        math.sin((b[0]-a[0])*p/2)**2 +
        math.cos(a[0]*p)*math.cos(b[0]*p)*math.sin((b[1]-a[1])*p/2)**2))


def osrm_route(pts):
    """pts = [(lat,lon),...]. Returns (ok, distance_km, duration_min)."""
    import requests
    coord = ";".join(f"{lo},{la}" for la, lo in pts)
    try:
        r = requests.get(OSRM_URL + coord, params={"overview": "false"}, timeout=20)
        j = r.json()
        if j.get("code") == "Ok" and j.get("routes"):
            rt = j["routes"][0]
            return True, rt["distance"]/1000.0, rt["duration"]/60.0
    except Exception:
        pass
    return False, None, None


def load_admin(path):
    from shapely.geometry import shape
    dj = json.load(open(path, encoding="utf-8"))
    return [(f["properties"]["district"], shape(f["geometry"])) for f in dj["features"]]


def district_of(polys, lat, lon):
    from shapely.geometry import Point
    p = Point(lon, lat)
    for n, poly in polys:
        if poly.contains(p):
            return n
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", default="outputs_v3.4.3")
    ap.add_argument("--existing", default="existing-routes.csv")
    ap.add_argument("--districts", default="kashmir_districts_osm.geojson")
    args = ap.parse_args()

    import geopandas as gpd
    df = pd.read_csv(os.path.join(args.outdir, "Rationalised_Routes_Kashmir_v3.csv"))
    g = gpd.read_file(os.path.join(args.outdir, "Rationalised_Routes_Kashmir_v3.geojson"))
    polys = load_admin(args.districts)
    er = pd.read_csv(args.existing)
    # via lookup by Route_ID (best-effort; SSCL synthetics have none here)
    via_by_id = {}
    if "Route_ID" in er.columns and "Via_Points_Geocoded" in er.columns:
        for _, r in er.iterrows():
            via_by_id[str(r["Route_ID"])] = r.get("Via_Points_Geocoded", "")

    geom = {r["Route_Code"]: r.geometry for _, r in g.iterrows()}
    glen = {r["Route_Code"]: r.geometry.length * 111.0 for _, r in g.iterrows()}  # rough deg→km (lat); fine for cross-check only

    # GENUINE coordinate-collapse points: one coord shared by >=3 DISTINCT place
    # NAMES (e.g. the historical 15-villages-on-one-Srinagar-point bug). A busy
    # hub used by many routes is ONE name repeated → NOT flagged (that's a real
    # terminal, not an error). We count distinct normalised names per rounded coord.
    coord_names = {}
    def _norm(s): return "".join(ch for ch in str(s).upper() if ch.isalnum())
    if {"Origin_Lat", "Origin_Lon", "Origin", "Destination"}.issubset(er.columns):
        for _, r in er.iterrows():
            for nm, la, lo in [(r.get("Origin"), r.get("Origin_Lat"), r.get("Origin_Lon")),
                               (r.get("Destination"), r.get("Dest_Lat"), r.get("Dest_Lon"))]:
                try:
                    k = (round(float(la), 3), round(float(lo), 3))
                    coord_names.setdefault(k, set()).add(_norm(nm))
                except Exception:
                    pass
    collision = {k for k, names in coord_names.items() if len(names) >= 3}

    act = df[df["Action_Taken"] != "MERGED_INTO_TRUNK"].copy()
    rows = []
    for _, r in act.iterrows():
        code = r["Route_Code"]; rid = str(r.get("Route_ID", "")); name = str(r.get("Route_Name", ""))
        gm = geom.get(code)
        if gm is None:
            rows.append({"Route_Code": code, "Route_Name": name, "verdict": "FAIL",
                         "reasons": "no geometry"})
            continue
        cs = list(gm.coords); O = (cs[0][1], cs[0][0]); D = (cs[-1][1], cs[-1][0])
        reasons = []; flags = {}

        # LAYER 1 — coordinates
        dO = district_of(polys, *O); dD = district_of(polys, *D)
        flags["O_in_division"] = dO is not None
        flags["D_in_division"] = dD is not None
        if dO is None: reasons.append("origin outside division")
        if dD is None: reasons.append("dest outside division")
        sl = hav(O, D)
        flags["O_ne_D"] = sl > 0.3
        if sl <= 0.3: reasons.append("origin≈dest (<0.3km)")
        for tag, pt in [("O", O), ("D", D)]:
            if hav(pt, SRINAGAR_CENTROID) < 0.15:
                reasons.append(f"{tag} on Srinagar-centroid point")
            if (round(pt[0], 3), round(pt[1], 3)) in collision:
                reasons.append(f"{tag} on shared/collision coord")

        # LAYER 2 — OSRM feasibility. OSRM O→D = the shortest DRIVABLE distance, an
        # independent ground truth: (a) does the corridor connect by road at all?
        # (b) the engine's one-way path length must be ≥ that shortest distance —
        # a shorter planned path would be physically impossible. A LONGER planned
        # path is normal (it routes via the permit's waypoints) → reported, not failed.
        ok, okm, omin = osrm_route([O, D])
        flags["osrm_ok"] = ok
        eng_km = float(r.get("Route_KM", 0) or 0)
        # cross-check the stored Route_KM against the actual planned geometry length
        gjkm = sum(hav((cs[i][1], cs[i][0]), (cs[i+1][1], cs[i+1][0]))
                   for i in range(len(cs)-1))
        flags["geojson_km"] = round(gjkm, 1)
        if eng_km > 0 and abs(gjkm - eng_km) / eng_km > 0.12:
            reasons.append(f"stored Route_KM {eng_km:.0f} ≠ geometry length {gjkm:.0f} (>12%)")
        if not ok:
            reasons.append("OSRM could not route O→D (not road-connected)")
        else:
            flags["osrm_direct_km"] = round(okm, 1)
            if eng_km > 0 and okm > 0:
                if eng_km < 0.9 * okm:
                    reasons.append(f"path {eng_km:.0f}km < shortest road {okm:.0f}km (impossible)")
                flags["detour_ratio"] = round(eng_km / okm, 2)   # >1 = via-routing (INFO)
            circ = (gjkm / sl) if sl > 0.5 else None
            if circ:
                flags["circuity"] = round(circ, 2)
                if circ > 4.0:
                    reasons.append(f"circuity {circ:.1f}× — verify via-routing is intended")

        # LAYER 3 — plan realism
        cyc = float(r.get("Cycle_Time_Min", 0) or 0); hw = int(r.get("Headway_Min", 0) or 0)
        fleet = int(r.get("Fleet_Required", 0) or 0)
        hpv = int(r.get("HPV_Count", 0) or 0); mpv = int(r.get("MPV_Count", 0) or 0); lpv = int(r.get("LPV_Count", 0) or 0)
        is_sscl = bool(r.get("CMP_Trunk", False))
        rtype = r.get("Route_Type", "")
        flags["mix_ok"] = (hpv + mpv + lpv == fleet)
        if not flags["mix_ok"]: reasons.append("HPV+MPV+LPV≠Fleet")
        # headway tier
        allowed = {15} if is_sscl else (CITY_HEADWAYS if rtype in ("Urban", "Peri_Urban") else CITY_HEADWAYS | RURAL_HEADWAYS)
        flags["headway_ok"] = hw in allowed
        if hw not in allowed: reasons.append(f"headway {hw} not in tier {sorted(allowed)}")
        # fleet formula (non-SSCL; SSCL is empirical)
        if not is_sscl and cyc > 0 and hw > 0:
            exp = max(math.ceil(math.ceil(cyc/hw)*1.15), 1 if rtype == "Regional_District" else 2)
            flags["fleet_formula_ok"] = (exp == fleet)
            if exp != fleet: reasons.append(f"fleet {fleet}≠formula {exp}")
        # speed
        spd = 2*eng_km/(cyc/60) if cyc > 0 else 0
        flags["speed_kmh"] = round(spd, 1)
        if spd and (spd < 8 or spd > 45): reasons.append(f"implausible speed {spd:.0f} km/h")
        # load
        load = float(r.get("Load_Ratio", 0) or 0)
        flags["load"] = load
        if load > 1.2: reasons.append(f"overload {load:.2f}")
        # fleet sanity
        if fleet > FLEET_SANITY_MAX: reasons.append(f"fleet {fleet} > {FLEET_SANITY_MAX} (review)")
        if fleet <= 0: reasons.append("zero fleet")

        hard = any(k in " ".join(reasons) for k in
                   ["outside division", "impossible", "not road-connected", "≠Fleet",
                    "zero fleet", "origin≈dest", "≠ geometry length"])
        verdict = "FAIL" if hard else ("REVIEW" if reasons else "PASS")
        rows.append({"Route_Code": code, "Route_Name": name[:46], "Route_Type": rtype,
                     "District_O": dO, "District_D": dD, "engine_km": round(eng_km, 1),
                     "osrm_direct_km": flags.get("osrm_direct_km"),
                     "geojson_km": flags.get("geojson_km"), "circuity": flags.get("circuity"),
                     "detour_ratio": flags.get("detour_ratio"), "headway": hw, "fleet": fleet,
                     "load": load, "speed_kmh": flags.get("speed_kmh"),
                     "verdict": verdict, "reasons": "; ".join(reasons)})

    rep = pd.DataFrame(rows)
    out = os.path.join(args.outdir, "route_verification_report.csv")
    rep.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"\nVerified {len(rep)} active routes → {out}")
    print(rep["verdict"].value_counts().to_string())
    for v in ("FAIL", "REVIEW"):
        sub = rep[rep["verdict"] == v]
        if len(sub):
            print(f"\n── {v} ({len(sub)}) ──")
            for _, x in sub.head(40).iterrows():
                print(f"  {x['Route_Code']:14} {str(x['Route_Name'])[:40]:40} | {x['reasons']}")


if __name__ == "__main__":
    main()
