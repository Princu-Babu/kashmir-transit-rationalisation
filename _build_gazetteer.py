"""
_build_gazetteer.py — assemble kashmir_gazetteer.csv from the recovery results +
district-centre fallbacks, so EVERY real place name has an (at least approximate)
coordinate. Quality control: low-confidence single-geocoder hits are overridden
with the district centre if they land >35 km from the expected district (a wrong
hit); residual unresolved names get the district centre. Genuine non-places
(SCRAPED/SCRAPPED) are skipped (noted).
"""
import math
import pandas as pd

# District HQ / centre coordinates (lat, lon) — used as the approximate fallback.
DISTRICT_CENTRE = {
    "Srinagar":  (34.0830, 74.7970), "Budgam":    (34.0140, 74.7190),
    "Ganderbal": (34.2270, 74.7750), "Anantnag":  (33.7300, 75.1480),
    "Kulgam":    (33.6450, 75.0190), "Shopian":   (33.7170, 74.8310),
    "Pulwama":   (33.8740, 74.8990), "Baramulla": (34.1980, 74.3640),
    "Bandipora": (34.4180, 74.6430), "Kupwara":   (34.5260, 74.2550),
}
# Known Srinagar localities/features among the "junk" residuals → Srinagar coords.
SRINAGAR_PINS = {
    "GBS": (34.0686, 74.8100),                 # General Bus Stand
    "BONE JOINT HOSPITAL BARZALLA": (34.0585, 74.7905),  # Barzulla
    "90FEET": (34.0470, 74.8000), "EXB CROSSING": (34.0470, 74.8000),
    "EXCROSSING": (34.0470, 74.8000), "BY PASS": (34.0300, 74.8200),
    "BOHRIKADAL": (34.0928, 74.8126), "SAKIDAFAR": (34.1100, 74.8050),
    "CHUNTWALIWAR": (34.0950, 74.8000),
}
SKIP = {"SCRAPED", "SCRAPPED"}     # void permit markers, not places

def km(a, b): return math.hypot((a[0]-b[0])*111, (a[1]-b[1])*92)

rec = pd.read_csv("gazetteer_recovery.csv")
dd  = pd.read_csv("dest_district_map.csv")
dist_of = {str(r["dest"]).strip().upper(): str(r["district"]).strip() for _, r in dd.iterrows()}

rows, stats = [], {"keep":0, "override":0, "fallback":0, "srinagar_pin":0, "skip":0}
for _, r in rec.iterrows():
    nm = str(r["name"]).strip().upper()
    if nm in SKIP:
        stats["skip"] += 1; continue
    district = dist_of.get(nm, "Srinagar")     # JKRTC dest → its depot district; else Srinagar
    centre = DISTRICT_CENTRE.get(district, DISTRICT_CENTRE["Srinagar"])
    has = pd.notna(r["lat"]) and str(r["lat"]) != ""
    if has:
        coord = (float(r["lat"]), float(r["lon"])); conf = str(r["conf"]); src = str(r["source"])
        # trust high/med; sanity-check low against district
        if conf in ("high", "med") or km(coord, centre) <= 35:
            rows.append({"name": nm, "lat": round(coord[0],5), "lon": round(coord[1],5),
                         "source": src, "district": district}); stats["keep"] += 1
        else:
            rows.append({"name": nm, "lat": centre[0], "lon": centre[1],
                         "source": f"district_centre({district})", "district": district}); stats["override"] += 1
    else:
        if nm in SRINAGAR_PINS:
            c = SRINAGAR_PINS[nm]
            rows.append({"name": nm, "lat": c[0], "lon": c[1], "source": "srinagar_pin",
                         "district": "Srinagar"}); stats["srinagar_pin"] += 1
        else:
            rows.append({"name": nm, "lat": centre[0], "lon": centre[1],
                         "source": f"district_centre({district})", "district": district}); stats["fallback"] += 1

out = pd.DataFrame(rows)
out.to_csv("kashmir_gazetteer.csv", index=False)
print(f"kashmir_gazetteer.csv written: {len(out)} entries")
print("breakdown:", stats)
print("by district:", out["district"].value_counts().to_dict())
print("skipped (void, not places):", sorted(SKIP))
