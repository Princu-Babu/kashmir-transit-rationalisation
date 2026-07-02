#!/usr/bin/env python
"""
v3.4.5 — measured-cycle corrections for the 5 GPS-verified Srinagar corridors.

SOURCE: bus-sathi-trace-intelligence REALITY_CHECK.md — 5 plan routes were
confidently matched to observed app-GPS corridors (40-211 runs each). On all
five, the engine's planned one-way (Cycle_Time/2) ran at ~0.5x the MEASURED
one-way; 4 of the 5 were bound by the per-km cycle CAP, which was masking it.

METHOD (measurement beats model, but only where measured):
  - drive time  = Route_KM / corridor MEASURED MOVING speed (dwell excluded by
    construction — this is bus physics on that corridor, incl. real congestion,
    so it REPLACES the OSRM-car-time x congestion-multiplier estimate);
  - keep the engine's own stop + junction penalties (scheduled dwell model);
  - cycle = one-way x 2 x 1.10 as ever, but the per-km CAP does not clamp a
    directly-measured corridor (the cap is a heuristic for unmeasured routes);
  - fleet  = ceil(ceil(cycle/headway) x 1.15), unchanged formula.
  OSRM_Duration_S is back-scaled so the engine's exact cycle formula reproduces
  the new cycle (same self-consistency trick as apply_corrections_v344.py).

Keyed by Route_Code; ONLY the 5 measured routes change. Everything else is
byte-identical to v3.4.4. SSCL untouched (none of the 5 is SSCL).
"""
import csv, math, json, os, shutil, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SRC = "outputs_v3.4.4"; DST = "outputs_v3.4.5"
FLEET_SPARE = 1.15
CAP = {"Urban": 4.0, "Peri_Urban": 2.5, "Regional_District": 1.5}
FLOOR = {"Regional_District": 1}

# corridor -> (permit, measured moving km/h, support) from
# bus-sathi-trace data/corridor_profiles.csv + analyst verdicts (post-audit)
MEASURED = {
    "FDR-050": dict(c="C1", mv=18.2, runs=211, drv=32, obs_oneway=75.9),
    "FDR-262": dict(c="C4", mv=18.1, runs=93,  drv=12, obs_oneway=85.2),
    "FDR-370": dict(c="C6", mv=20.6, runs=79,  drv=9,  obs_oneway=78.7),
    "FDR-270": dict(c="C7", mv=18.5, runs=47,  drv=11, obs_oneway=64.3),
    "FDR-575": dict(c="C8", mv=17.5, runs=40,  drv=5,  obs_oneway=26.6),
}

def cong(z): return 2.2 if z == "City_Core" else 1.4

def cycle_formula(km, osrm_s, junc, zone, rtype, capped=True):
    n = max(1, int(km * 1000 / 500)); sp = n * 0.5
    ow = (osrm_s / 60.0) * cong(zone) + sp + junc
    cyc = ow * 2 * 1.10
    cap = km * 2.0 * CAP.get(rtype, 4.0)
    if capped and cap > 0 and cyc > cap: cyc = cap
    return round(max(1.0, cyc), 1), n, round(sp, 1)

def fleet_of(cycle, headway, rtype):
    op = max(1, math.ceil(cycle / max(1, headway)))
    return max(max(1, math.ceil(op * FLEET_SPARE)), FLOOR.get(rtype, 2))

rows = list(csv.DictReader(open(f"{SRC}/Rationalised_Routes_Kashmir_v3.csv", encoding="utf-8-sig")))
hdr = rows[0].keys()

# SELF-TEST: formula reproduces every active route
act = [r for r in rows if float(r["Fleet_Required"] or 0) > 0]
ok = sum(1 for r in act if abs(cycle_formula(float(r["Route_KM"]), float(r["OSRM_Duration_S"]),
        float(r["Junction_Penalty_Min"]), r["Congestion_Zone"], r["Route_Type"])[0]
        - float(r["Cycle_Time_Min"])) <= 0.2)
print(f"SELF-TEST cycle {ok}/{len(act)}"); assert ok == len(act), "formula drift — abort"

applied = []
for r in rows:
    pid = r["New_Route_ID"]
    if pid not in MEASURED or r["Action_Taken"] == "MERGED_INTO_TRUNK":
        continue
    m = MEASURED[pid]
    km = float(r["Route_KM"]); junc = float(r["Junction_Penalty_Min"])
    zone = r["Congestion_Zone"]; rtype = r["Route_Type"]; hw = float(r["Headway_Min"])
    old_cyc = float(r["Cycle_Time_Min"]); old_fleet = int(float(r["Fleet_Required"]))

    drive_min = km / m["mv"] * 60.0                      # measured bus moving pace
    new_osrm = drive_min * 60.0 / cong(zone)             # back-scale so formula reproduces
    new_cyc, n, sp = cycle_formula(km, new_osrm, junc, zone, rtype, capped=False)
    new_fleet = fleet_of(new_cyc, hw, rtype)
    if new_fleet == old_fleet and abs(new_cyc - old_cyc) < 1:
        applied.append(dict(Route_Code=r["Route_Code"], Route_Name=r["Route_Name"], Corridor=m["c"],
                            Old_Cycle=old_cyc, New_Cycle=old_cyc, Old_Fleet=old_fleet, New_Fleet=old_fleet,
                            Note="measured cycle ~= planned; no change needed"))
        continue

    oh, om, ol = int(float(r["HPV_Count"])), int(float(r["MPV_Count"])), int(float(r["LPV_Count"] or 0))
    nh = min(round(oh * new_fleet / old_fleet), new_fleet) if old_fleet else 0
    nl = min(round(ol * new_fleet / old_fleet), new_fleet - nh) if old_fleet else 0
    nm = new_fleet - nh - nl
    r["OSRM_Duration_S"] = f"{new_osrm:.1f}"
    r["Cycle_Time_Min"] = f"{new_cyc:.1f}"
    r["Fleet_Required"] = str(new_fleet)
    r["HPV_Count"] = str(nh); r["MPV_Count"] = str(nm); r["LPV_Count"] = str(nl)
    applied.append(dict(Route_Code=r["Route_Code"], Route_Name=r["Route_Name"], Corridor=m["c"],
                        Old_Cycle=old_cyc, New_Cycle=new_cyc, Old_Fleet=old_fleet, New_Fleet=new_fleet,
                        Note=f"measured moving {m['mv']} km/h over {m['runs']} runs/{m['drv']} drivers "
                             f"(observed one-way {m['obs_oneway']} min); cap lifted (directly measured)"))

# copy dir then overwrite CSV + geojson
os.makedirs(DST, exist_ok=True)
for fn in os.listdir(SRC):
    s = os.path.join(SRC, fn)
    d = os.path.join(DST, fn.replace("v3.4.4", "v3.4.5"))
    if os.path.isdir(s):
        if not os.path.exists(d): shutil.copytree(s, d)
    elif not os.path.exists(d):
        shutil.copy2(s, d)

with open(f"{DST}/Rationalised_Routes_Kashmir_v3.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(hdr)); w.writeheader()
    for r in rows: w.writerow(r)

gj = json.load(open(f"{SRC}/Rationalised_Routes_Kashmir_v3.geojson", encoding="utf-8"))
csvmap = {}
for r in rows: csvmap.setdefault(r["Route_Code"], r)
appset = {a["Route_Code"] for a in applied if a["New_Fleet"] != a["Old_Fleet"]}
for ft in gj["features"]:
    c = ft["properties"].get("Route_Code")
    if c in csvmap:
        src = csvmap[c]
        for k in ("Fleet_Required", "HPV_Count", "MPV_Count", "Headway_Min"):
            if k in ft["properties"]:
                try: ft["properties"][k] = int(float(src[k]))
                except Exception: ft["properties"][k] = src[k]
        ft["properties"]["v345_measured"] = c in appset
json.dump(gj, open(f"{DST}/Rationalised_Routes_Kashmir_v3.geojson", "w"), ensure_ascii=False)

with open("corrections_applied_v345.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(applied[0].keys()), quoting=csv.QUOTE_ALL)
    w.writeheader()
    for a in applied: w.writerow(a)

tot = sum(int(float(r["Fleet_Required"])) for r in rows if float(r["Fleet_Required"] or 0) > 0)
h = sum(int(float(r["HPV_Count"])) for r in rows if float(r["Fleet_Required"] or 0) > 0)
mv = sum(int(float(r["MPV_Count"])) for r in rows if float(r["Fleet_Required"] or 0) > 0)
lp = sum(int(float(r["LPV_Count"] or 0)) for r in rows if float(r["Fleet_Required"] or 0) > 0)
for a in applied:
    print(f"  {a['Corridor']} {a['Route_Name'][:32]:34s} cycle {a['Old_Cycle']:6.1f}->{a['New_Cycle']:6.1f}  fleet {a['Old_Fleet']}->{a['New_Fleet']}")
print(f"FLEET TOTAL v3.4.4=1004 -> v3.4.5={tot}  (HPV {h}/MPV {mv}/LPV {lp})")
print("wrote", DST, "+ corrections_applied_v345.csv")
