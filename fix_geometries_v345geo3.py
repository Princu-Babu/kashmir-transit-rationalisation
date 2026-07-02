#!/usr/bin/env python
"""
v3.4.5-geo step 3 — resolve the 7 review routes with researched pins + the
deep-dive ledger's verified km BANDS as the acceptance test (fairer than the
midpoint: the v3.4.4 corrections stored Route_KM as a point inside a cited band).

Research (web, 2026-07-03):
  - JVC = SKIMS Bemina (ex-Jhelum Valley College), Main Chowk Bemina on the
    NH1A bypass, 34.083867/74.761369 (mappls), "4-5 km from the city centre"
    == the ledger band for FDR-269.
  - Iskanderpora = village near Beerwah (Beerwah post office, lower Khag),
    Budgam — NOT Baramulla. Badran = hamlet near Beerwah/Magam, Khag tehsil.
    Beerwah is 27 km from Srinagar (ledger bands 24-28 km consistent).
Village pins below resolved via Nominatim (bounded to the valley) at runtime.

Acceptance: new line km within [band_lo*0.90, band_hi*1.15] (one-way systems
and stand approaches legitimately add a little over the cited band).
Prefer observed GPS runs between accepted pins where >=2 exist (same as step 2).

Run:  & "D:\\plotting\\ana\\python.exe" fix_geometries_v345geo3.py
"""
import sys, os, json, math, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import pandas as pd
import requests
from shapely.geometry import LineString

OUT = "outputs_v3.4.5"
GJ = f"{OUT}/Rationalised_Routes_Kashmir_v3.geojson"
TRACE_RUNS = r"E:\bus-sathi-trace\data\runs_matched.pkl.gz"
OSRM = "http://localhost:5000"
LAT0 = 34.0
KX = math.cos(math.radians(LAT0)) * 111320.0
KY = 111320.0
CELL_M = 150.0
END_M = 800.0

# route -> (band_lo, band_hi, [candidate pin pairs to try])
JVC = (34.083867, 74.761369)
TARGETS = {
    "FDR-269": dict(band=(4, 5),   a=[("Jehangir Chowk", (34.0755, 74.8043))],
                    b=[("JVC SKIMS Bemina", JVC)]),
    "FDR-467": dict(band=(10, 13), a=[("Jehangir Chowk", (34.0755, 74.8043))],
                    b=[("Budgam town", (34.0180, 74.7140)), ("Budgam bus stand", (34.0225, 74.7185))]),
    "FDR-108": dict(band=(7, 8),   a=[("Saidakadal", (34.1063, 74.8258))],
                    b=[("HMT bypass junction", (34.1290, 74.7520)), ("Bemina bypass chowk", (34.0980, 74.7480)),
                       ("Parimpora bypass", (34.1310, 74.7690))]),
    "FDR-080": dict(band=(3, 4),   a=[("Batamaloo stand", (34.0770, 74.7942)), ("Batamaloo stand 2", (34.0795, 74.7975))],
                    b=[("Dalgate", (34.0731, 74.8322)), ("Dalgate bridge", (34.0745, 74.8305))]),
    "FDR-406": dict(band=(2, 3),   a=[("Qamarwari chowk", (34.0997, 74.7828)), ("Qamarwari 2", (34.1030, 74.7860))],
                    b=[("Parimpora stand", (34.1264, 74.7823))]),
    "FDR-466": dict(band=(25, 28), a=[("Srinagar Lal Chowk", (34.0745, 74.8110)), ("Batamaloo stand", (34.0770, 74.7942))],
                    b=[("NOMINATIM:Iskanderpora, Budgam", None), ("Beerwah town", (33.9902, 74.5836))]),
    "FDR-464": dict(band=(24, 26), a=[("Srinagar Lal Chowk", (34.0745, 74.8110)), ("Batamaloo stand", (34.0770, 74.7942))],
                    b=[("NOMINATIM:Badran, Budgam", None), ("Magam town", (34.0920, 74.5920)), ("Beerwah town", (33.9902, 74.5836))]),
}


def nominatim(q):
    try:
        r = requests.get("https://nominatim.openstreetmap.org/search",
                         params={"q": q + ", Jammu and Kashmir, India", "format": "json", "limit": 3},
                         headers={"User-Agent": "kashmir-transit-geofix/1.0"}, timeout=20).json()
        time.sleep(1.1)
        for hit in r:
            la, lo = float(hit["lat"]), float(hit["lon"])
            if 33.3 < la < 34.6 and 74.0 < lo < 75.6:
                return (la, lo)
    except Exception:
        pass
    return None


def line_km(latlon):
    return LineString([(lo * KX, la * KY) for la, lo in latlon]).length / 1000.0


def osrm_route(a, b):
    try:
        u = f"{OSRM}/route/v1/driving/{a[1]},{a[0]};{b[1]},{b[0]}?overview=full&geometries=geojson"
        j = requests.get(u, timeout=15).json()
        if j.get("code") != "Ok": return None
        return [(la, lo) for lo, la in j["routes"][0]["geometry"]["coordinates"]]
    except Exception:
        return None


def hav_m(a1, o1, a2, o2):
    from math import radians, sin, cos, asin, sqrt
    a1, o1, a2, o2 = map(radians, (a1, o1, a2, o2))
    return 2 * 6371000 * asin(sqrt(sin((a2 - a1) / 2) ** 2 + cos(a1) * cos(a2) * sin((o2 - o1) / 2) ** 2))


def cellset(latlon):
    return {(round(lo * KX / CELL_M), round(la * KY / CELL_M)) for la, lo in latlon}


def jac(a, b):
    i = len(a & b)
    return i / len(a | b) if i else 0.0


def main():
    gj = json.load(open(GJ, encoding="utf-8"))
    runs = pd.read_pickle(TRACE_RUNS, compression="gzip")
    runs = runs[(runs.matched == True) & (runs.clean == True)].reset_index(drop=True)

    results = []
    for f in gj["features"]:
        p = f["properties"]
        rid = p.get("New_Route_ID")
        if rid not in TARGETS or p.get("geometry_source"): continue
        t = TARGETS[rid]
        lo_b, hi_b = t["band"][0] * 0.90, t["band"][1] * 1.15

        def resolve(cands):
            out = []
            for name, pin in cands:
                if pin is None and name.startswith("NOMINATIM:"):
                    pin = nominatim(name.split(":", 1)[1])
                    name = name.split(":", 1)[1] + " (nominatim)"
                if pin: out.append((name, pin))
            return out

        best = None
        for na, a in resolve(t["a"]):
            for nb, b in resolve(t["b"]):
                line = osrm_route(a, b)
                if not line: continue
                lk = line_km(line)
                ok = lo_b <= lk <= hi_b
                score = 0 if ok else min(abs(lk - lo_b), abs(lk - hi_b))
                if best is None or (ok and not best["ok"]) or (ok == best["ok"] and score < best["score"]):
                    best = dict(ok=ok, score=score, line=line, lk=lk, a=a, b=b, na=na, nb=nb)
        if not best:
            results.append(dict(route_id=rid, route=p.get("Route_Name"), status="REVIEW", note="no OSRM route")); continue
        if not best["ok"]:
            results.append(dict(route_id=rid, route=p.get("Route_Name"), status="REVIEW",
                                note=f"best {best['lk']:.1f} km via {best['na']}/{best['nb']} outside band {t['band']} (+15% grace)"))
            continue

        # prefer observed runs between accepted pins
        a, b = best["a"], best["b"]
        km_t = best["lk"]
        cands = []
        for _, r in runs.iterrows():
            g = r["geom"]
            d_fwd = max(hav_m(*g[0], *a), hav_m(*g[-1], *b))
            d_rev = max(hav_m(*g[0], *b), hav_m(*g[-1], *a))
            if min(d_fwd, d_rev) <= END_M and lo_b <= float(r.matched_km) <= hi_b:
                cands.append(g if d_fwd <= d_rev else g[::-1])
        chosen, source, support = best["line"], f"osrm_reanchored({best['na']} -> {best['nb']})", 0
        if len(cands) >= 2:
            sigs = [cellset(g) for g in cands]
            bi = max(range(len(cands)), key=lambda i: sum(jac(sigs[i], sigs[j]) for j in range(len(cands))))
            grp = [j for j in range(len(cands)) if jac(sigs[bi], sigs[j]) >= 0.55]
            if len(grp) >= 2:
                chosen, source, support = cands[bi], "observed_gps", len(grp)

        f["geometry"]["coordinates"] = [[round(lo, 5), round(la, 5)] for la, lo in chosen]
        p["geometry_source"] = source
        results.append(dict(route_id=rid, route=p.get("Route_Name"), status="FIXED",
                            new_km=round(line_km(chosen), 1), band=str(t["band"]),
                            source=source, obs_runs=support))

    json.dump(gj, open(GJ, "w"), ensure_ascii=False)
    df = pd.DataFrame(results)
    print(df.to_string(index=False))
    # append to the log
    old = pd.read_csv("geometry_fixes_v345geo.csv")
    old = old[~old.route_id.isin(df.route_id)]
    pd.concat([old, df], ignore_index=True).to_csv("geometry_fixes_v345geo.csv", index=False)
    print("\nUpdated", GJ, "+ geometry_fixes_v345geo.csv")


if __name__ == "__main__":
    main()
