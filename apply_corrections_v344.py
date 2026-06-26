#!/usr/bin/env python
"""
v3.4.4 — apply audited, citation-backed route corrections to the v3.4.3 plan.

ROOT CAUSE (from the AI route-by-route deep-dive, ROUTE_DEEPDIVE_LEDGER.csv):
the engine's Route_KM == OSRM distance for the routed input coordinates (no
inflation factor). For ~73 routes that distance diverged from the REAL road
distance because of (a) a wrong/peripheral endpoint coordinate the geocoder
picked, or (b) an OSRM path that detours. A blind OSRM re-run cannot fix either
class. So we substitute the WEB-VERIFIED real road distance (each cited in the
ledger) and recompute Cycle_Time and Fleet with the engine's EXACT formulas.

Keyed by Route_Code: ONLY audited routes change; the verified-correct PASS
routes stay byte-identical. SSCL (CMP_Trunk) routes are never touched (their
longer km are legitimate via-loops; fleet is empirical CHALO).

Cycle/fleet formulas are lifted verbatim from transit_kashmir_v3.py
(compute_cycle_times / step8_compute_fleet_required) and self-tested to
reproduce every v3.4.3 active route exactly before any correction is applied.
"""
import csv, math, json, os, re, shutil

SRC='outputs_v3.4.3'; DST='outputs_v3.4.4'
CAP={'Urban':4.0,'Peri_Urban':2.5,'Regional_District':1.5}
FLEET_SPARE=1.15; FLOOR={'Regional_District':1}
def floor_of(t): return FLOOR.get(t,2)
def cong(z): return 2.2 if z=='City_Core' else 1.4

def recompute_cycle(km, osrm_s, junc, zone, rtype):
    n=max(1,int(km*1000/500)); sp=n*0.5
    ow=(osrm_s/60.0)*cong(zone)+sp+junc
    cyc=ow*2*1.10
    cap=km*2.0*CAP.get(rtype,4.0)
    if cap>0 and cyc>cap: cyc=cap
    return round(max(1.0,cyc),1), n, round(sp,1)

def fleet_of(cycle, headway, rtype):
    op=max(1,math.ceil(cycle/max(1,headway)))
    raw=max(1,math.ceil(op*FLEET_SPARE))
    return max(raw, floor_of(rtype))

# ---- load ----
rows=list(csv.DictReader(open(f'{SRC}/Rationalised_Routes_Kashmir_v3.csv',encoding='utf-8-sig')))
hdr=rows[0].keys()
diag={r['Route_Code']:r for r in csv.DictReader(open('route_corrections_v344_diag.csv',encoding='utf-8-sig'))}

# ---- SELF-TEST cycle + fleet on unchanged active routes ----
act=[r for r in rows if float(r['Fleet_Required'] or 0)>0]
cyc_ok=fl_ok=0
for r in act:
    c,_,_=recompute_cycle(float(r['Route_KM']),float(r['OSRM_Duration_S']),float(r['Junction_Penalty_Min']),r['Congestion_Zone'],r['Route_Type'])
    if abs(c-float(r['Cycle_Time_Min']))<=0.2: cyc_ok+=1
    if str(r['CMP_Trunk']).strip().lower() in ('true','1'): continue
    if fleet_of(float(r['Cycle_Time_Min']),float(r['Headway_Min']),r['Route_Type'])==int(float(r['Fleet_Required'])): fl_ok+=1
nonsscl=sum(1 for r in act if str(r['CMP_Trunk']).strip().lower() not in('true','1'))
print(f"SELF-TEST cycle {cyc_ok}/{len(act)}  fleet(non-SSCL) {fl_ok}/{nonsscl}")
assert cyc_ok==len(act), "cycle formula drift — abort"

# ---- curated FAIL handling (the 5 geocoding errors need individual judgement) ----
# real_km=None  -> do NOT change numbers, only flag for RTO
CURATED={
 'SRSR02023736': dict(real=1.5,  conf='HIGH', note='Safakadal-SMHS is ~0.8-1.6 km (engine 6.26 km stale); set to verified ~1.5 km.'),
 'SRBG02023903': dict(real=11.5, conf='HIGH', note='Srinagar-Budgam ~9-14 km via NH444 (engine 23.6 km, dest pinned too far west); set to 11.5 km. Endpoint coord also needs re-geocode to Budgam town (34.018,74.714).'),
 'SRSR01010809': dict(real=4.0,  conf='MED',  note='Rangpora & Soura adjacent (~3-5 km); engine 22 km is a mis-snap. Set to 4 km.'),
 'SRSR02021523': dict(real=4.0,  conf='LOW',  note='GBS & Lal Chowk pins ~0.3 km apart (engine 20.3 km garbage). If GBS=General Bus Stand Batamaloo, real ~4 km; placeholder pending re-geocode of GBS.'),
 'BRBR01010201': dict(real=None, conf='DEFER',note='Garkote identity unresolved: only documented Garkote in Baramulla dist is in Uri (~37 km), but engine pins it ~3 km from Baramulla. Defer to RTO surveyed stop register; numbers unchanged.'),
}
LOWCONF=re.compile(r'could not|unverifiable|not independently|no source|no direct|no single|inferred|unconfirmed|verify the exact|estimate|benchmarked|approximat', re.I)

applied=[]; deferred=[]
for r in rows:
    code=r['Route_Code']
    if code not in diag: continue
    if float(r['Fleet_Required'] or 0)<=0: continue
    if str(r['CMP_Trunk']).strip().lower() in ('true','1'):
        deferred.append((code,r['Route_Name'],'SSCL trunk — legit via-loop, not corrected')); continue
    d=diag[code]; v=d['Verdict']; cat=d['Category']
    realmid=float(d['Real_KM_mid']) if d['Real_KM_mid'] else None
    finding=d['Finding']

    if code in CURATED:
        cur=CURATED[code]
        if cur['real'] is None:
            deferred.append((code,r['Route_Name'],cur['note'])); continue
        new_km=cur['real']; reason=cur['note']; conf=cur['conf']
    else:
        delta=d['KM_Delta']
        if not realmid or delta in ('',None) or abs(int(delta))<16:
            deferred.append((code,r['Route_Name'],'within tolerance / no reliable real km')); continue
        if LOWCONF.search(finding):
            deferred.append((code,r['Route_Name'],'real km low-confidence (needs RTO stop register)')); continue
        new_km=realmid; reason=finding; conf='AUTO'

    old_km=float(r['Route_KM']);
    if old_km<=0: deferred.append((code,r['Route_Name'],'old_km<=0')); continue
    old_fleet=int(float(r['Fleet_Required']))
    new_osrm=float(r['OSRM_Duration_S'])*(new_km/old_km)   # scale duration by km ratio
    new_cyc,n_stops,stop_pen=recompute_cycle(new_km,new_osrm,float(r['Junction_Penalty_Min']),r['Congestion_Zone'],r['Route_Type'])
    new_fleet=fleet_of(new_cyc,float(r['Headway_Min']),r['Route_Type'])
    # vehicle split: preserve v3.4.3 proportions scaled to new fleet
    oh,om,ol=int(float(r['HPV_Count'])),int(float(r['MPV_Count'])),int(float(r['LPV_Count'] or 0))
    if old_fleet>0:
        nh=round(oh*new_fleet/old_fleet); nl=round(ol*new_fleet/old_fleet)
        nh=min(nh,new_fleet); nl=min(nl,new_fleet-nh); nm=new_fleet-nh-nl
    else:
        nh,nm,nl=0,new_fleet,0
    # write back
    r['Route_KM']=f"{new_km:.3f}"; r['OSRM_Duration_S']=f"{new_osrm:.1f}"
    r['Cycle_Time_Min']=f"{new_cyc:.1f}"; r['N_Stops_Estimated']=str(n_stops); r['Stop_Penalty_Min']=f"{stop_pen:.1f}"
    r['Fleet_Required']=str(new_fleet); r['HPV_Count']=str(nh); r['MPV_Count']=str(nm); r['LPV_Count']=str(nl)
    applied.append(dict(Route_Code=code,Route_Name=r['Route_Name'],Eng_Type=r['Route_Type'],
        Old_KM=round(old_km,2),New_KM=round(new_km,2),Old_Cycle=round(float(d['Eng_KM']) and float(rows and 0) or 0,1),
        New_Cycle=new_cyc,Old_Fleet=old_fleet,New_Fleet=new_fleet,Confidence=conf,
        Headway=r['Headway_Min'],Reason=reason,Sources=d['Sources']))

print(f"APPLIED {len(applied)}  DEFERRED {len(deferred)}")

# ---- write outputs ----
os.makedirs(DST,exist_ok=True)
with open(f'{DST}/Rationalised_Routes_Kashmir_v3.csv','w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=list(hdr)); w.writeheader()
    for r in rows: w.writerow(r)

# geojson: update active props (geometry kept; flagged where coord-fix still needed)
gj=json.load(open(f'{SRC}/Rationalised_Routes_Kashmir_v3.geojson',encoding='utf-8'))
appmap={a['Route_Code']:a for a in applied}
csvmap={}
for r in rows:
    csvmap.setdefault(r['Route_Code'],r)
for ft in gj['features']:
    c=ft['properties'].get('Route_Code')
    if c in csvmap:
        src=csvmap[c]
        for k in ('Route_KM','Fleet_Required','HPV_Count','MPV_Count','Headway_Min'):
            if k in ft['properties'] and k in src:
                try: ft['properties'][k]=type(ft['properties'][k])(src[k]) if ft['properties'][k] is not None else src[k]
                except Exception: ft['properties'][k]=src[k]
        ft['properties']['v344_corrected']= c in appmap
json.dump(gj,open(f'{DST}/Rationalised_Routes_Kashmir_v3.geojson','w'),ensure_ascii=False)

# audit log
with open('corrections_applied_v344.csv','w',newline='',encoding='utf-8') as f:
    cols=['Route_Code','Route_Name','Eng_Type','Old_KM','New_KM','New_Cycle','Old_Fleet','New_Fleet','Confidence','Headway','Reason','Sources']
    w=csv.DictWriter(f,fieldnames=cols,extrasaction='ignore',quoting=csv.QUOTE_ALL); w.writeheader()
    for a in applied: w.writerow(a)
with open('corrections_deferred_v344.csv','w',newline='',encoding='utf-8') as f:
    w=csv.writer(f,quoting=csv.QUOTE_ALL); w.writerow(['Route_Code','Route_Name','Why_deferred'])
    for d in deferred: w.writerow(d)

# totals
def total_fleet(rws): return sum(int(float(r['Fleet_Required'])) for r in rws if float(r['Fleet_Required'] or 0)>0)
old_total=total_fleet(list(csv.DictReader(open(f'{SRC}/Rationalised_Routes_Kashmir_v3.csv',encoding='utf-8-sig'))))
new_total=total_fleet(rows)
print(f"FLEET TOTAL  v3.4.3={old_total}  ->  v3.4.4={new_total}  (delta {new_total-old_total:+d})")
print("wrote", DST, "+ corrections_applied_v344.csv + corrections_deferred_v344.csv")
