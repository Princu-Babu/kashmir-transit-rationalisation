"""
_recover_villages.py — recover coordinates for unresolved Kashmir place names.

Cascade per name:
  1. Nominatim (OSM) with spelling variants, non-bounded, valley-box accept.
  2. Photon + ArcGIS REST as cross-validators (both must agree, and the result
     must NOT be a detected fallback/collapse point).
Detects fallback points (a coord returned for many distinct names) and rejects
them. Writes gazetteer_recovery.csv (name,lat,lon,source,conf). Resumable: reuses
any rows already present in gazetteer_recovery.csv.
"""
import time, math, os
import pandas as pd, requests

UA = {"User-Agent": "kashmir-transit/3.3.8 village-recovery (RTO plan; imassolutionss@gmail.com)"}
# whole Kashmir valley + margin
LAT0, LAT1, LON0, LON1 = 33.2, 34.8, 73.8, 75.6
SRI = (34.08565, 74.80555)
OUT = "gazetteer_recovery.csv"


def inbox(la, lo):
    return LAT0 <= la <= LAT1 and LON0 <= lo <= LON1


def _variants(name):
    n = name.strip()
    vs = [n]
    if n.upper().endswith("H") and len(n) > 4:
        vs.append(n[:-1])               # ANANTNAGH -> ANANTNAG
    vs.append(n.replace("OO", "U").replace("PORA", "pora"))
    # de-dup, keep order
    seen, out = set(), []
    for v in vs:
        k = v.upper()
        if k not in seen:
            seen.add(k); out.append(v)
    return out


def nominatim(q):
    try:
        r = requests.get("https://nominatim.openstreetmap.org/search",
                         params={"q": q, "format": "json", "limit": 1},
                         headers=UA, timeout=20).json()
        time.sleep(1.1)
        if r:
            return float(r[0]["lat"]), float(r[0]["lon"])
    except Exception:
        time.sleep(1.1)
    return None


def photon(q):
    try:
        r = requests.get("https://photon.komoot.io/api/", params={"q": q, "limit": 1},
                         headers=UA, timeout=20).json()
        time.sleep(0.4)
        f = r.get("features")
        if f:
            c = f[0]["geometry"]["coordinates"]
            return c[1], c[0]
    except Exception:
        pass
    return None


def arcgis(q):
    try:
        r = requests.get("https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/findAddressCandidates",
                         params={"SingleLine": q, "f": "json", "maxLocations": 1, "countryCode": "IND"},
                         headers=UA, timeout=20).json()
        time.sleep(0.4)
        c = r.get("candidates")
        if c:
            return c[0]["location"]["y"], c[0]["location"]["x"]
    except Exception:
        pass
    return None


def km(a, b):
    return math.hypot((a[0] - b[0]) * 111, (a[1] - b[1]) * 92)


def main():
    names = pd.read_csv("gazetteer_worklist.csv")["name"].astype(str).str.strip().str.upper().tolist()
    done = {}
    if os.path.exists(OUT):
        prev = pd.read_csv(OUT)
        for _, r in prev.iterrows():
            done[str(r["name"]).upper()] = r
    rows = []
    # PASS 1: collect candidates from all 3 geocoders
    raw = {}
    for i, nm in enumerate(names):
        if nm in done and pd.notna(done[nm].get("lat")):
            rows.append(done[nm].to_dict()); continue
        nres = None
        for v in _variants(nm):
            nres = nominatim(f"{v}, Kashmir, Jammu and Kashmir, India")
            if nres and inbox(*nres):
                break
            nres = None
        pres = photon(f"{nm}, Jammu and Kashmir, India")
        ares = arcgis(f"{nm}, Jammu and Kashmir, India")
        raw[nm] = (nres, pres, ares)
        print(f"  [{i+1}/{len(names)}] {nm:24s} N={_f(nres)} P={_f(pres)} A={_f(ares)}", flush=True)
    # detect fallback points: any coord returned (rounded 2dp) for >=3 distinct names
    from collections import Counter
    cnt = Counter()
    for nm, (n, p, a) in raw.items():
        for r in (p, a):  # Photon/ArcGIS are the ones that collapse
            if r:
                cnt[(round(r[0], 2), round(r[1], 2))] += 1
    fallbacks = {k for k, c in cnt.items() if c >= 3}
    print("detected fallback/collapse points:", fallbacks)

    def is_fb(r):
        return r is not None and (round(r[0], 2), round(r[1], 2)) in fallbacks
    # PASS 2: decide
    for nm, (n, p, a) in raw.items():
        coord, src, conf = None, "", ""
        if n and inbox(*n) and km(n, SRI) > 0.3:
            coord, src, conf = n, "nominatim", "high"
        elif p and a and inbox(*p) and inbox(*a) and not is_fb(p) and not is_fb(a) and km(p, a) <= 3.0:
            coord, src, conf = ((p[0]+a[0])/2, (p[1]+a[1])/2), "photon+arcgis", "med"
        elif p and inbox(*p) and not is_fb(p):
            coord, src, conf = p, "photon", "low"
        elif a and inbox(*a) and not is_fb(a):
            coord, src, conf = a, "arcgis", "low"
        if coord:
            rows.append({"name": nm, "lat": round(coord[0], 5), "lon": round(coord[1], 5),
                         "source": src, "conf": conf})
        else:
            rows.append({"name": nm, "lat": "", "lon": "", "source": "UNRESOLVED", "conf": ""})
    out = pd.DataFrame(rows).drop_duplicates("name")
    out.to_csv(OUT, index=False)
    res = out[out["source"] != "UNRESOLVED"]
    print(f"\nRESOLVED {len(res)}/{len(out)}  (high={sum(out['conf']=='high')} med={sum(out['conf']=='med')} low={sum(out['conf']=='low')})")
    print(f"UNRESOLVED {len(out)-len(res)} -> need district fallback (R3)")


def _f(r):
    return f"({r[0]:.3f},{r[1]:.3f})" if r else "."


if __name__ == "__main__":
    main()
