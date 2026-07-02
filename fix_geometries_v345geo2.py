#!/usr/bin/env python
"""
v3.4.5-geo step 2 — RE-ANCHOR endpoints, then redraw the 18 stale geometries.

Step-1 finding: for all 18 mismatch routes, the drawn line IS the OSRM shortest
path from the CURRENT pins — no path between those pins matches the web-verified
km. So the endpoint coordinates are the defect (the v3.4.4 leftover: km fixed,
endpoints never re-geocoded).

Method per route (the verified Route_KM is the arbiter throughout):
  1. Parse termini names from Route_Name ("A to B").
  2. Build candidate pins per terminus: current pin · Kashmir_Stops_Master_v4
     name match · observed coded stops (real GPS clusters) place match ·
     manually-researched pins for known Srinagar termini (RESEARCHED below,
     each cross-checkable on OSM).
  3. Try pin combinations on local OSRM; keep the combo whose route length is
     CLOSEST to the verified km; accept only within TOL.
  4. Prefer an OBSERVED app-GPS run between the accepted pins (>=2 similar
     runs) over the OSRM line where one exists.

Writes geometry (+ endpoints) into outputs_v3.4.5 geojson; CSV numbers untouched.
Log: geometry_fixes_v345geo.csv (overwritten with final status).

Run:  & "D:\\plotting\\ana\\python.exe" fix_geometries_v345geo2.py
"""
import sys, os, json, math, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import pandas as pd
import requests
from shapely.geometry import LineString

OUT = "outputs_v3.4.5"
GJ = f"{OUT}/Rationalised_Routes_Kashmir_v3.geojson"
MASTER = f"{OUT}/Kashmir_Stops_Master_v4.csv"
OBS_STOPS = r"E:\bus-sathi-trace\data\observed_stops_coded.csv"
TRACE_RUNS = r"E:\bus-sathi-trace\data\runs_matched.pkl.gz"
OSRM = "http://localhost:5000"

MISMATCH_FRAC, MISMATCH_KM = 0.25, 1.0
TOL = 0.22
END_M = 800.0
CELL_M = 150.0
LAT0 = 34.0
KX = math.cos(math.radians(LAT0)) * 111320.0
KY = 111320.0

# Manually-researched terminus pins (well-known Srinagar/valley places; each
# verifiable on OpenStreetMap). Used only as CANDIDATES — the verified-km
# tolerance test decides acceptance.
RESEARCHED = {
    "dalgate": (34.0731, 74.8322),
    "batmaloo": (34.0770, 74.7942), "batamaloo": (34.0770, 74.7942),
    "parimpora": (34.1264, 74.7823),
    "hazratbal": (34.1268, 74.8442),
    "jehangir chowk": (34.0755, 74.8043),
    "jvc": (34.0350, 74.8280),                     # JVC hospital, Bemina->Nowgam side
    "budgam": (34.0180, 74.7140),
    "qamarwari": (34.0997, 74.7828),
    "saidakadal": (34.1063, 74.8258),
    "bypass": (34.0570, 74.7770),                  # Srinagar bypass (Nowgam crossing)
    "panzinara": (34.1440, 74.7570),
    "batwara": (34.0620, 74.8560),
    "ld": (34.0805, 74.8180),                      # LD hospital
    "beeru": (33.9930, 74.5880),                   # Beerwah (Budgam)
    "koil": (33.9210, 74.9210),                    # Koil, Pulwama
    "sedow": (33.6470, 74.7760),                   # Sedow, Shopian
    "badrun": (34.2160, 74.5730),                  # Badran, Baramulla side
    "isganderpora": (34.2000, 74.5580),
    "chadora": (33.9720, 74.7920),                 # Chadoora
    "srinagar": (34.0745, 74.8110),                # Lal Chowk anchor
    "hazratbal to ld": None,
}


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


def osrm_route(a, b):
    try:
        u = f"{OSRM}/route/v1/driving/{a[1]},{a[0]};{b[1]},{b[0]}?overview=full&geometries=geojson"
        j = requests.get(u, timeout=15).json()
        if j.get("code") != "Ok": return None
        return [(la, lo) for lo, la in j["routes"][0]["geometry"]["coordinates"]]
    except Exception:
        return None


def main():
    gj = json.load(open(GJ, encoding="utf-8"))
    master = pd.read_csv(MASTER)
    obs_stops = pd.read_csv(OBS_STOPS)
    runs = pd.read_pickle(TRACE_RUNS, compression="gzip")
    runs = runs[(runs.matched == True) & (runs.clean == True)].reset_index(drop=True)

    def candidates(name, current):
        name_l = name.strip().lower()
        out = [("current", current)]
        m = master[master.Stop_Name.str.lower().str.strip() == name_l]
        for _, r in m.iterrows():
            out.append(("master", (float(r.Latitude), float(r.Longitude))))
        o = obs_stops[obs_stops.place.astype(str).str.lower().str.strip() == name_l]
        for _, r in o.head(2).iterrows():
            out.append(("observed_stop", (float(r.lat), float(r.lon))))
        if name_l in RESEARCHED and RESEARCHED[name_l]:
            out.append(("researched", RESEARCHED[name_l]))
        # dedupe within 150 m
        ded = []
        for tag, c in out:
            if not any(hav_m(*c, *c2) < 150 for _, c2 in ded):
                ded.append((tag, c))
        return ded

    fixes, review = [], []
    for f in gj["features"]:
        p = f["properties"]
        coords = [(la, lo) for lo, la in f["geometry"]["coordinates"]]
        if len(coords) < 2 or p.get("geometry_source"): continue
        km = float(p.get("Route_KM") or 0)
        drawn = line_km(coords)
        if km <= 0 or not (abs(drawn - km) / km > MISMATCH_FRAC and abs(drawn - km) > MISMATCH_KM):
            continue
        name = str(p.get("Route_Name", ""))
        if " to " not in name.lower():
            review.append(dict(route_id=p.get("New_Route_ID"), route=name, stated_km=km,
                               drawn_km=round(drawn, 1), status="REVIEW", note="unparseable name")); continue
        left, right = [s.strip() for s in name.split(" to ", 1)]
        ca = candidates(left, coords[0]); cb = candidates(right, coords[-1])

        best = None
        for ta, a in ca:
            for tb, b in cb:
                line = osrm_route(a, b)
                if not line: continue
                lk = line_km(line)
                err = abs(lk - km) / km
                if best is None or err < best["err"]:
                    best = dict(err=err, line=line, lk=lk, a=a, b=b, ta=ta, tb=tb)
        if not best or best["err"] > TOL:
            review.append(dict(route_id=p.get("New_Route_ID"), route=name, stated_km=km,
                               drawn_km=round(drawn, 1), status="REVIEW",
                               note=f"best OSRM candidate {best['lk']:.1f} km (err {best['err']:.0%}) via {best['ta']}/{best['tb']}" if best else "no OSRM route"))
            continue

        # prefer an observed run between the accepted pins
        a, b = best["a"], best["b"]
        cands = []
        for _, r in runs.iterrows():
            g = r["geom"]
            d_fwd = max(hav_m(*g[0], *a), hav_m(*g[-1], *b))
            d_rev = max(hav_m(*g[0], *b), hav_m(*g[-1], *a))
            if min(d_fwd, d_rev) <= END_M and abs(float(r.matched_km) - km) / km <= TOL:
                cands.append(g if d_fwd <= d_rev else g[::-1])
        chosen, source, support = best["line"], f"osrm_reanchored({best['ta']}/{best['tb']})", 0
        if len(cands) >= 2:
            sigs = [cellset(g) for g in cands]
            bi = max(range(len(cands)), key=lambda i: sum(jac(sigs[i], sigs[j]) for j in range(len(cands))))
            grp = [j for j in range(len(cands)) if jac(sigs[bi], sigs[j]) >= 0.55]
            if len(grp) >= 2:
                chosen, source, support = cands[bi], "observed_gps", len(grp)

        new_km = line_km(chosen)
        f["geometry"]["coordinates"] = [[round(lo, 5), round(la, 5)] for la, lo in chosen]
        p["geometry_source"] = source
        fixes.append(dict(route_id=p.get("New_Route_ID"), route=name, stated_km=km,
                          old_drawn_km=round(drawn, 1), new_drawn_km=round(new_km, 1),
                          status="FIXED", source=source, obs_runs=support))

    json.dump(gj, open(GJ, "w"), ensure_ascii=False)
    log = pd.DataFrame(fixes + review)
    log.to_csv("geometry_fixes_v345geo.csv", index=False)
    print(f"FIXED {len(fixes)} / REVIEW {len(review)}")
    print(log.to_string(index=False))


if __name__ == "__main__":
    main()
