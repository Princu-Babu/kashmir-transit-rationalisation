#!/usr/bin/env python
"""
v3.4.5-geo — redraw the 18 stale route geometries with REAL observed alignments.

BACKGROUND: apply_corrections_v344.py substituted web-verified road km on 48
routes but did NOT redraw their map lines — 18 active routes still carry a drawn
LineString >25% (and >1 km) longer than their corrected Route_KM. The map shows
a path nobody certified.

FIX, evidence-first (numbers do NOT change — km/cycle/fleet were already
corrected; this is geometry-only):
  1. OBSERVED alignment: among the 2,426 clean map-matched app-GPS runs, find
     runs whose endpoints sit within END_M of the route's endpoints (either
     orientation). Cluster by path shape; take the best-supported cluster's
     medoid line. Accept only if its length is within TOL of the corrected
     Route_KM (closed loop: real GPS confirming web-verified km).
  2. OSRM fallback: else re-route the corrected endpoints on local OSRM and
     accept under the same length tolerance.
  3. Else leave untouched + flag for review.

Patches Rationalised_Routes_Kashmir_v3.geojson IN PLACE in outputs_v3.4.5
(features gain geometry_source: observed_gps | osrm_reroute). CSV untouched.
Log: geometry_fixes_v345geo.csv.

Run:  & "D:\\plotting\\ana\\python.exe" fix_geometries_v345geo.py
"""
import sys, os, json, math
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import pandas as pd
import requests
from shapely.geometry import LineString

OUT = "outputs_v3.4.5"
GJ = f"{OUT}/Rationalised_Routes_Kashmir_v3.geojson"
TRACE_RUNS = r"E:\bus-sathi-trace\data\runs_matched.pkl.gz"
OSRM = "http://localhost:5000"

MISMATCH_FRAC, MISMATCH_KM = 0.25, 1.0
END_M = 700.0
TOL = 0.22                      # accepted |line-km|/km
CELL_M = 150.0
LAT0 = 34.0
KX = math.cos(math.radians(LAT0)) * 111320.0
KY = 111320.0


def hav_m(a1, o1, a2, o2):
    from math import radians, sin, cos, asin, sqrt
    a1, o1, a2, o2 = map(radians, (a1, o1, a2, o2))
    return 2 * 6371000 * asin(sqrt(sin((a2 - a1) / 2) ** 2 + cos(a1) * cos(a2) * sin((o2 - o1) / 2) ** 2))


def line_km(latlon):
    return LineString([(lo * KX, la * KY) for la, lo in latlon]).length / 1000.0


def cellset(latlon):
    return {(round(lo * KX / CELL_M), round(la * KY / CELL_M)) for la, lo in latlon}


def jac(a, b):
    i = len(a & b)
    return i / len(a | b) if i else 0.0


def main():
    gj = json.load(open(GJ, encoding="utf-8"))
    runs = pd.read_pickle(TRACE_RUNS, compression="gzip")
    runs = runs[(runs.matched == True) & (runs.clean == True)].reset_index(drop=True)
    print(f"clean runs: {len(runs)}")

    fixes, review = [], []
    for f in gj["features"]:
        p = f["properties"]
        coords = [(la, lo) for lo, la in f["geometry"]["coordinates"]]
        if len(coords) < 2: continue
        km = float(p.get("Route_KM") or 0)
        drawn = line_km(coords)
        if km <= 0 or not (abs(drawn - km) / km > MISMATCH_FRAC and abs(drawn - km) > MISMATCH_KM):
            continue
        ra, rb = coords[0], coords[-1]

        # 1. observed candidates
        cands = []
        for _, r in runs.iterrows():
            g = r["geom"]
            d_fwd = max(hav_m(*g[0], *ra), hav_m(*g[-1], *rb))
            d_rev = max(hav_m(*g[0], *rb), hav_m(*g[-1], *ra))
            if min(d_fwd, d_rev) <= END_M:
                gl = float(r.matched_km)
                if abs(gl - km) / km <= TOL:
                    cands.append((g if d_fwd <= d_rev else g[::-1], gl, r.driver))
        chosen = None; source = None; support = 0; drivers = 0
        if cands:
            sigs = [cellset(g) for g, _, _ in cands]
            # medoid by summed similarity
            best_i = max(range(len(cands)),
                         key=lambda i: sum(jac(sigs[i], sigs[j]) for j in range(len(cands))))
            grp = [j for j in range(len(cands)) if jac(sigs[best_i], sigs[j]) >= 0.55]
            if len(grp) >= 2:
                chosen = cands[best_i][0]; source = "observed_gps"
                support = len(grp); drivers = len({cands[j][2] for j in grp})

        # 2. OSRM fallback
        if chosen is None:
            try:
                u = (f"{OSRM}/route/v1/driving/{ra[1]},{ra[0]};{rb[1]},{rb[0]}"
                     "?overview=full&geometries=geojson")
                j = requests.get(u, timeout=15).json()
                geom = j["routes"][0]["geometry"]["coordinates"]
                cand = [(la, lo) for lo, la in geom]
                gl = line_km(cand)
                if abs(gl - km) / km <= TOL:
                    chosen = cand; source = "osrm_reroute"
            except Exception:
                pass

        if chosen is None:
            review.append(dict(route_id=p.get("New_Route_ID"), route=p.get("Route_Name"),
                               stated_km=round(km, 1), drawn_km=round(drawn, 1),
                               note="no observed same-OD line within tolerance; OSRM reroute also out of tolerance — needs manual/via-waypoint review"))
            continue

        new_km = line_km(chosen)
        f["geometry"]["coordinates"] = [[round(lo, 5), round(la, 5)] for la, lo in chosen]
        p["geometry_source"] = source
        fixes.append(dict(route_id=p.get("New_Route_ID"), route=p.get("Route_Name"),
                          stated_km=round(km, 1), old_drawn_km=round(drawn, 1),
                          new_drawn_km=round(new_km, 1), source=source,
                          support_runs=support, support_drivers=drivers))

    json.dump(gj, open(GJ, "w"), ensure_ascii=False)
    pd.DataFrame(fixes + review).to_csv("geometry_fixes_v345geo.csv", index=False)
    print(f"\nFIXED {len(fixes)} geometries:")
    print(pd.DataFrame(fixes).to_string(index=False) if fixes else "  none")
    print(f"\nREVIEW (untouched): {len(review)}")
    if review:
        print(pd.DataFrame(review)[["route_id", "route", "stated_km", "drawn_km"]].to_string(index=False))
    print("\nPatched", GJ, "+ log geometry_fixes_v345geo.csv")


if __name__ == "__main__":
    main()
