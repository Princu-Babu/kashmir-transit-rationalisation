# CLAUDE.md — Kashmir Valley Transit Rationalisation Engine

Working notes for any Claude session picking up this project. Read this first.

---

## 0. TL;DR — how to run anything here

**Python is the conda env at `D:\plotting\ana` — NOT system Python.**
On Windows the bare `python` / conda activate does not put it on PATH cleanly.
Always prepend PATH in PowerShell before invoking:

```powershell
$env:PATH = "D:\plotting\ana;D:\plotting\ana\Library\bin;D:\plotting\ana\Scripts;" + $env:PATH
& "D:\plotting\ana\python.exe" <script>.py
```

- `D:\plotting\ana\python.exe` is Python 3.13. Has pandas, numpy, rasterio,
  geopandas, folium, jenkspy, rasterstats, shapely, requests, openpyxl,
  python-pptx, reportlab.
- GDAL_DATA warnings on import are harmless.
- The engine needs **OSRM running in Docker on localhost:5000**. If it's down,
  the engine falls back to circuity-based cycle times which invalidates any
  cross-version comparison — always confirm OSRM is up before a real run:
  ```powershell
  try { Invoke-WebRequest "http://localhost:5000/route/v1/driving/74.8,34.1;74.85,34.05" -TimeoutSec 5 -UseBasicParsing | Out-Null; "OSRM OK" } catch { "OSRM DOWN" }
  ```
- The engine needs the WorldPop raster. `RASTER_PATH` resolves:
  `--raster` CLI flag → `$KASHMIR_WORLDPOP` env → `./kashmir_worldpop.tif` →
  legacy `E:/kash/kashmir_worldpop.tif`. If missing it raises RuntimeError
  **unless** `KASHMIR_ALLOW_DUMMY_POP=1` (dev-only, writes flat 1000/route,
  prints "DO NOT SHIP" — never commit outputs from a dummy run).

---

## 1. Two repos

| Repo | Remote | Local path |
|---|---|---|
| Engine | `github.com/Princu-Babu/kashmir-transit-rationalisation` | `E:\kash` |
| Dashboard | `github.com/GrostesqueChip/bus-sathi-dashboard` (Next.js) | `E:\dash\bus-sathi-dashboard` |

Commit/push to both when an engine change ships. End commit messages with the
Co-Authored-By Claude line per the harness rules.

---

## 2. The per-build workflow (run after ANY engine change)

```powershell
$env:PATH = "D:\plotting\ana;D:\plotting\ana\Library\bin;D:\plotting\ana\Scripts;" + $env:PATH
Set-Location E:\kash

# 1. Bump version constant in transit_kashmir_v3.py header + comments
# 2. Fresh output dir (keep prior versions for diffing)
mkdir outputs_vX.Y.Z; copy existing-routes.csv,pois.csv outputs_vX.Y.Z\

# 3. Run engine (cwd = the output dir so artefacts land there)
Set-Location E:\kash\outputs_vX.Y.Z
& "D:\plotting\ana\python.exe" ..\transit_kashmir_v3.py 2>&1 | Tee-Object ..\engine_run_vX.Y.Z.log
Set-Location E:\kash

# 4. Cross-validate against CHALO
& "D:\plotting\ana\python.exe" cross_evaluate.py --engine-out outputs_vX.Y.Z\Rationalised_Routes_Kashmir_v3.csv

# 5. Generate route codes from the stops master
& "D:\plotting\ana\python.exe" generate_route_codes.py   # defaults to outputs_vX.Y.Z

# 6. Regenerate decks
& "D:\plotting\ana\python.exe" generate_presentations.py --outdir outputs_vX.Y.Z --engine-csv outputs_vX.Y.Z\Rationalised_Routes_Kashmir_v3.csv
& "D:\plotting\ana\python.exe" generate_kashmir_pitch.py --outdir outputs_vX.Y.Z --engine-csv outputs_vX.Y.Z\Rationalised_Routes_Kashmir_v3.csv

# 7. Beautified RTO workbook (4-sheet cut-down)
& "D:\plotting\ana\python.exe" _beautify_rto_master.py   # edit ENGINE_OUT path inside first

# 8. Sync dashboard (copies assets + rebuilds JSON with fresh route codes)
& "D:\plotting\ana\python.exe" _sync_dashboard.py        # edit ENGINE_OUT path inside first

# 9. Commit + push BOTH repos
```

`_sync_dashboard.py` and `_beautify_rto_master.py` have the output-version path
hardcoded near the top (`ENGINE_OUT` / `SRC` / `SRC_CSV`). Update those when the
version bumps. (These are `_`-prefixed helper scripts, committed to the engine repo.)

---

## 3. Route_Code system — v4 "geo-canonical" (`route_code_system.py`)

**Full methodology: `ROUTE_CODE_METHODOLOGY.md`. This replaced the old
name-match-against-a-hand-built-master approach entirely (v3.4.0).**

- **Why rebuilt:** the old logic fuzzy-matched terminal NAMES against
  `Kashmir_Stops_Sectored_V2.csv`, which had unreliable coords (AIRPORT ~80 km
  off, PARIMPORA ~18 km off), undeduped spelling variants, and wrong district
  tags (LALCHOWK→Anantnag). That produced wrong-district codes and spurious A/B.
- **New foundations:** (1) COORDINATES from the engine's own geocoded route
  endpoints — the stop registry is built FROM them, so route→stop linkage is
  EXACT (no fuzzy matching). (2) ADMIN GEOGRAPHY from authoritative OSM
  boundaries: District = `kashmir_districts_osm.geojson` (admin_level 5, 10
  districts); Tehsil = `kashmir_tehsils_osm.geojson` (admin_level 6, 39 tehsils).
  Every stop's District + Tehsil(=Sector) come from POINT-IN-POLYGON. Both
  geojsons are committed (fetched once from OSM Overpass + osm2geojson).
- **Code (unchanged 12-char format):** `<Do><Dd><So><Sd><No><Nd>` — 2-letter
  origin+dest District, 2-digit origin+dest Sector, 2-digit origin+dest Stop.
  Display `SRGB-0102-0305`. District codes: SR BG GB BR BP PW SP AN KG KW.
- **Pipeline (deterministic):** endpoints → one coord per normalised name →
  150 m FIXED-ANCHOR proximity merge (no chaining — running-centroid had merged
  LD+TRC 2 km apart) → district+tehsil by point-in-polygon → sectors numbered
  1..N over the district's full alphabetical tehsil list (STABLE) → stops
  alphabetical within (district,sector). Re-runs are byte-identical.
- **Letter suffix (A/B):** only when 2+ active routes share the SAME canonical
  origin AND dest stop (true "5A/5B"). v3.4.0 result: **4 letter-suffixed, all
  legit** (Khull Ahmadabad/Kulgam — a village approximated to its district town;
  "By Pass"/"Bypass" — a spelling-duplicate corridor). NO dashes.
- **Outputs:** `Kashmir_Stops_Master_v4.csv` (126 canonical stops: Master_Stop_Code,
  Stop_Name, District, Tehsil, Tehsil_Code, Sector_ID, Stop_No, Lat/Lon, N_Endpoints)
  + Route_Code on every route. Verified: 172/172 valid `^4L+8D(+letter)$`, 0
  dashes/dups/UNMATCHED, identical across CSV/GeoJSON/dashboard/pretty workbook,
  and EVERY master stop's district == independent point-in-polygon (0 mismatches).
- **To refresh boundaries** (rare): re-fetch admin_level 5 & 6 within `IN-JK` from
  OSM Overpass, assemble with `osm2geojson`, overwrite the two `*_osm.geojson`.
- `generate_route_codes.py` and `Kashmir_Stops_Sectored_V2.csv` are now RETIRED
  for code generation (kept only for reference / diffing).

---

## 4. Version history (what changed and why)

| Version | Theme | Key changes |
|---|---|---|
| v3.1 | Initial Kashmir fork | Replaced Jammu's 13 RITES CMP routes with 30 SSCL CHALO e-bus routes |
| v3.2 | Audit r1 | RASTER_PATH bug; SSCL headway 45→15; Jhelum bridge bottleneck +8 min; congestion ×2.2 downtown; Tier-3 POI split |
| v3.3 | Phase-1 audit r1 | Typology flags; spare ratio 1.15; Phase-4 KPIs; SSCL_CDI_Conflict flag |
| v3.3.1 | Phase-1 audit r2 | Per-km cycle cap; typology mode-share; subsidy 0.5→0.6; social prune 17→11 |
| v3.3.2 | Demand calibration | Phase-4 Daily_Demand rewrite (corridor-share + CAPTURE_SCALE 0.18); portable RASTER_PATH; cross_evaluate operator-absorption aware |
| v3.3.3 | Teammate review | Tourist tagging 4→69 routes (geometry-proximity + endpoint tests); catchment ×1.3 tourist boost; Daily_Capacity formula fix (cycle-time based) |
| v3.3.4 | Honest fleet sizing | SSCL empirical fleet = FLOOR not override (eliminated 12 false Red_Overload); LPV restored to dashboard breakdown; cross_evaluate headway-scaled objective |
| v3.3.5 | Conservative phase-1 | Non-SSCL HP headway 15→20, MP 30→35; fleet 1,113→988 |
| v3.3.6 | RTO Kashmir asks r1 | SSCL_HPV_SHARE_CAP=0.60 (more MPV on HPV-dominated trunks); LP headway 60→35 min; route-code generator integrated |
| v3.3.7 | RTO Kashmir asks r2 | 35-min headway CEILING (HEADWAY_MAX_MIN=35 — regional 60/90, MPS 45, "regular" 60 all eliminated → headways now only 15/20/35); SSCL_HPV_SHARE_CAP 0.60→0.50 + long-haul bracket 0.60→0.50 (neither class a trunk majority); dashboard download cleanup; _sync_dashboard auto-copies RTO+Pretty workbooks and purges stale ones |
| v3.3.8 | Independent audit remediation | Re-geocoded district-aware via Nominatim (`geocode_common.py`; `arcgis` now optional) — eliminated the 118-name Srinagar-centroid collapse (0 centroid endpoints, was 391/416). `parse_via` format fix; duplicate-permit consolidation (Finding 8); apportionment normalised to the dedup union (Finding 9); input-QA gate + per-route disposition trail; new QC checks (geocode/dup-corridor/load/route-code uniqueness); LPV_Count in CSV; route-code uniqueness suffix. Outcome: fleet 1,009→855, coverage 69.8%→94.7%, median route 8.7→16.5 km. See `AUDIT_FIX_LOG.md`. |
| v3.3.9 | Government-screening source re-audit | Re-checked the plan against the original Kashmir source files. (1) SSCL FALSE-TRUNK BUG: `_terminal_matches_cmp` matched on a 0.45 char-ratio + raw substring, so 11 conventional JKRTC permits (Anantnag→Srinagar, Tangmarg, Haftnar→Anantnag…) were mis-labelled SSCL e-bus trunks — fake `CMP_Route_ID`, 15-min headway, ~115 inflated buses. Rewrote the matcher (strong fuzzy ≥0.80 OR shared meaningful non-generic token) + length-sanity guard; synthetic backbone force-self-matches. Result: CMP trunks 41→30 (exactly the SSCL backbone), 0 false trunks. (2) GEOCODE DISTRICT COLLAPSE: `_build_gazetteer` defaulted unknown districts to Srinagar → 15 villages from 6 districts on one Srinagar point; fixed via depot→district map (`_fix_gazetteer_districts.py`) + real pins (Pahalgam etc.). Outcome: fleet 1,053→1,005 (165/751/89), SSCL fleet 398→283, coverage 37.81% unchanged. 24/24 QA pass. See `AUDIT_2026-06-21_SOURCE_RECHECK.md`. |
| v3.4.0 | Route-code system rebuilt — "geo-canonical" | Completely reimagined route codes. The old name-match-against-`Kashmir_Stops_Sectored_V2.csv` is REPLACED by `route_code_system.py`, which builds the stop registry FROM the engine's own geocoded route endpoints (EXACT route→stop linkage, no fuzzy matching) and resolves District + Tehsil(=Sector) by POINT-IN-POLYGON against OSM admin boundaries (`kashmir_districts_osm.geojson` admin_level 5; `kashmir_tehsils_osm.geojson` admin_level 6). New registry `Kashmir_Stops_Master_v4.csv`. 172/172 codes valid, 0 dashes/dups/UNMATCHED, 4 legit letter-suffixed, every stop's district == point-in-polygon. Full method in `ROUTE_CODE_METHODOLOGY.md`. |
| v3.4.1 | Once-and-for-all system audit — bbox + double-count crackdown | Root-caused why bugs kept recurring (output-focused audits never reconciled the INPUT funnel). (1) STUDY-BBOX was clipped to lat[33.50,34.50] lon[74.40,75.20] + raster pre-cropped → dropped ~29 routes (Kupwara/Baramulla/SE-Anantnag) and shrank the denominator to 5.1M. Extended bbox to the 10-district extent; `study_area_population` clips by the 10-district UNION → 6.58M. (2) REVERSE-DIRECTION DOUBLE-COUNTING (round-trip cycle ⇒ A→B+B→A double-counted ~10 corridors) → `consolidate_duplicate_permits` key made UNDIRECTED. Full funnel reconciliation + 10-class crackdown. Result: 186 active, 1,144 fleet, 10 districts, 2.32M/35.2% of 6.58M. See `SYSTEM_AUDIT_2026-06-22.md`. |
| v3.4.2 | Route-level audit — Hybrid demand-responsive rural sizing | **Per-route audit (`ROUTE_LEVEL_AUDIT_2026-06-22.md`): directions/geometry sound for all 186 (high-circuity = legit via-hub permits); but the flat 35-min ceiling (an urban RTO ask) over-provisioned the 71 rural Regional lifelines (481 buses at 0.11 median load — every lifeline got a uniform ~55 trips/day; a 121-km Tangdar route = 13 buses for ~270 riders) AND under-served 6 busy inter-district corridors. User decision: HYBRID — keep 15/20/35 for Urban+Peri-Urban; size Regional_District lifelines by DEMAND (`apply_regional_demand_headway`: headway = current × target_load/load, bucketed 35/60/90/120, ≥2-hourly lifeline floor), then re-run fleet→split→phase4. SSCL backbone untouched (15-min). Tourist/seasonal modelling deliberately NOT changed (plan gives year-round recommended sizes; RTO reduces at execution). Result: Regional fleet 481→261, TOTAL 1,144→**924** (139 HPV/703 MPV/82 LPV), +91%→**+54%** over ~600; Tangdar 13→5, Kupwara 11→4, Handwara 9→3; headways now city 15/20/35 + rural 35/60/90/120. 186 active / 30 SSCL / 35.2% coverage unchanged. QA green. |
| v3.4.3 | Rural wait cap 50 min + route-by-route OSRM verification | User ask: rural waits must not exceed ~50 min. REGIONAL_HEADWAY_BUCKETS 35/60/90/120 → 35/40/45/50 (hard 50-min max). Fleet 924→1,044 (185/776/83, +74%); Tangdar 5→10 buses. Also built `_verify_routes.py` — internal-consistency route check (coords vs OSM polygons; local-OSRM drivability; fleet/headway/load realism) → 168 PASS / 18 REVIEW / 0 FAIL. |
| v3.4.4 | AI real-world route deep-dive + audited distance corrections | **User rejected `_verify_routes.py` (a script re-checking our own numbers) and asked for an AI ANALYST to deep-dive every route against the REAL world via web research. All 186 active routes verified (Opus for 71 rural / Sonnet for 115 city; one-at-a-time after parallel hit session limits) → `ROUTE_DEEPDIVE_LEDGER.csv` (real km/time/service/sources per route), `_FINDINGS.md`, `_METHODOLOGY.md`. Result 93 PASS / 88 REVIEW / 5 FAIL. ROOT CAUSE: engine `Route_KM == OSRM km` (no inflation; line ~1399) → divergences are wrong endpoint coords or OSRM detours, which a blind re-run CANNOT fix. So `apply_corrections_v344.py` SUBSTITUTES the web-verified real road km (cited per route) and recomputes cycle+fleet with the engine's EXACT formulas (self-tested: cycle 186/186, fleet non-SSCL 156/156), keyed by Route_Code so only audited routes change; SSCL untouched. 48 corrected (42 shrank/6 grew), 45 deferred (12 SSCL via-loop / 19 name-unverifiable→RTO stop register / 14 within tolerance). Fleet 1,044→1,004 (HPV 187/MPV 748/LPV 69); 186 active / 30 SSCL / 10 districts unchanged; HPV+MPV+LPV==Fleet all rows. Closed-loop: 46/48 within ±15% of real; 4/5 FAILs fixed (Garkote deferred). Final artifact: `ROUTE_VERIFICATION_RTO_APPENDIX.md` + `outputs_v3.4.4/Kashmir_Route_Verification_Appendix_v3.4.4_RTO.xlsx`. Resumable deep-dive: `deepdive_parts/check_progress.py`. NOT yet: dashboard/deck regen, git commit both repos, endpoint re-geocode for the 2 coord-fix map lines.** |
| **v3.4.5** | **Measured-cycle corrections from real app GPS (CURRENT)** | **The bus-sathi-trace-intelligence project (E:\bus-sathi-trace) matched 5 plan routes to observed app-GPS corridors (40–211 runs each; REALITY_CHECK.md) and found planned one-way ≈ 0.51× MEASURED — 4 of 5 were bound by the per-km cycle CAP, which masked it. `apply_reality_v345.py` (self-tested 186/186) re-anchors those 5 cycles to the corridor's MEASURED MOVING speed (replaces OSRM-car×congestion; keeps engine stop/junction penalties; cap lifted only where directly measured): FDR-050 76→101 (5→7 buses), FDR-262 94→187 (4→7), FDR-270 74→107 (4→5), FDR-370 81→111 (4→5), FDR-575 25→33 (3→3). Fleet 1,004→**1,011** (HPV 187/MPV 754/LPV 70). 9-sheet master patched via `_patch_rto_master_v345.py` (route rows+totals+cover, verified resum 1,011); Pretty + decks regenerated; dashboard synced (v3.4.5 hero download + service-plan constants + chatbot). Only the 5 measured routes changed — everything else byte-identical to v3.4.4. SSCL untouched. Log: `corrections_applied_v345.csv`.** |

---

## 5. Current key constants (v3.3.7)

```
HEADWAY_HP_MIN              = 20        # non-SSCL trunks
HEADWAY_MP_MIN             = 35        # feeders
HEADWAY_LP_MIN              = 35        # lifelines (was 60 — RTO ask r1)
HEADWAY_REGIONAL_HP_MIN    = 35        # rural lifeline (was 60 — RTO ask r2)
HEADWAY_REGIONAL_MP_MIN    = 35        # rural lifeline (was 90 — RTO ask r2)
HEADWAY_MAX_MIN            = 35        # v3.3.7 HARD CEILING — clamp applied at
                                       #   end of step6; the "mps" 45 floor and
                                       #   "regular" 60 bucket also dropped to 35.
                                       #   Verified: 0 routes >35; values are 15/20/35.
SSCL_TRUNK_HEADWAY_MIN     = 15        # SSCL backbone (their design target; below ceiling)
SSCL_HPV_SHARE_CAP         = 0.50      # v3.3.7: was 0.60 — neither class a trunk majority
FLEET_SPARE_RATIO          = 1.15      # maintenance/breakdown buffer
PHASE4_CORRIDOR_CAPTURE_SCALE = 0.18   # empirical CHALO demand anchor
CONGESTION_CITY_CORE       = 2.2       # downtown peak multiplier
JHELUM_BRIDGE_BOTTLENECK_MIN = 8.0
TOURIST_POPULATION_MULTIPLIER = 1.3    # tourist-corridor catchment boost
_route_km_hpv_share long-haul bracket (≥22 km) = 0.50 (was 0.60 in v3.3.6)
0.50 cap binding → verified 0 trunk routes with HPV majority (>50%, fleet≥4)
```

---

## 6. Current numbers (v3.4.3, the live plan — rural wait capped at 50 min)

- 613 permits → re-geocoded + village recovery → **644 engine routes**; **186 active**
  (Trunk 32 / Feeder 154 / Merged 458). Engine in=out (644=186+458), 0 routes lost.
- **Total fleet 1,044 (v3.4.3)** = HPV 185 / MPV 776 / LPV 83 (+74% over current ~600).
  Rural Regional lifelines demand-sized but capped at a 50-min max wait (v3.4.3 user
  ask): Tangdar = 10 buses (was 13 at flat-35, 5 at the old 120-min cap). Urban+Peri
  -Urban + SSCL fleet unchanged. (Fleet path: 1,144 flat-35 → 924 at 120-cap → 1,044 at 50-cap.)
- **v3.4.1 bbox extension:** study area was clipped to lat[33.50,34.50] lon[74.40,
  75.20] (raster pre-cropped to it) → silently dropped ~29 routes + understated the
  denominator. Extended to the 10-district extent; coverage denominator now the
  **10-district UNION = 6,584,762** (point-in-polygon). Active routes now span all
  **10 districts** (Kupwara recovered).
- **v3.4.1 reverse-direction de-dup:** corridor consolidation made UNDIRECTED
  (round-trip cycle ⇒ "A→B"+"B→A" was double-counting ~10 corridors); 0 true
  reverse-pairs remain.
- 30 CHALO SSCL routes → **exactly 30 SSCL trunks** (all active); SSCL fleet **283**
- **v3.3.9 geocode fix:** `_build_gazetteer` had defaulted unknown-district names to
  Srinagar → 15 villages from 6 districts collapsed onto one Srinagar point. Now
  reassigned to the **correct depot district centre** (`_fix_gazetteer_districts.py`)
  + 6 real town pins (Pahalgam, Tangdhar, Kamalkote, Kupwara×2, D.H. Pora). Only the
  2 genuine Srinagar features (By-Pass, Ex-Crossing) remain on the Srinagar point.
- **Village recovery (GAZETTEER_RECOVERY.md):** ~110 rural names OSM couldn't place
  earlier are now in kashmir_gazetteer.csv (real geocoder coords + correct-district
  approximations + Srinagar pins). existing-routes.csv 401→614. Only 2 void
  "SCRAPED/SCRAPPED" markers excluded.
- **Corridor consolidation now spans trunks AND feeders** (v3.3.8 r2): identical
  (rounded O→D) duplicate permits collapse to one service per corridor regardless
  of class; a real SSCL backbone route is never merged away. Removed e.g. 6
  identical Batamaloo→Pantha Chowk permit-trunks (~48 buses → one 7-bus service,
  load 0.12). Route codes: 0 duplicates, 0 duplicate names among active.
- **Headways: city (Urban/Peri-Urban/SSCL) 15 / 20 / 35 min; rural Regional lifelines
  demand-responsive 35 / 40 / 45 / 50 min — HARD 50-min max wait (v3.4.3 user ask).**
- Median route 22.8 km (longest Srinagar→Tangdar 121 km — full-division reach)  (older: Urban/Peri/Regional split
  — genuinely valley-wide; 55 long regional/rural routes recovered)
- **Network reaches 2,317,958 residents within 400m = 35.2% of the 6.58M Kashmir-
  Division population** (F-V9 fix: coverage is vs the WorldPop study-area total ~5,105,699,
  NOT the 1.66M Srinagar-UA figure (old "95.7%") nor the old clipped 5.1M bbox total).
- **~0.45 buses / 1000 residents SERVED** (1,044 / 2.318M)
- v3.3.8 R-V/round-2 re-verification fixes: Parimpora hub pinned, TRC→Airport link
  kept, depot "A-B" pairs split, active Population_Served reconciled to the cover
  (Finding 9 closed), demand re-anchored to CHALO (capture scale 0.18→0.33), coverage
  denominator corrected. See `VERIFICATION_v3.3.8.md`.
- **QC 8/8 passing** + QC-Geocode clean (0 centroid endpoints), route codes unique
- Calibration vs CHALO Apr 2026: per-route SSCL fleet **+24.9%** vs headway-scaled
  CHALO (within ±25% band; rose from +9.7% because corrected geometry routes SSCL
  trunks through their real via-waypoints → longer cycles → more honest fleet)
- Audit reject worklist (manual resolution): `geocode_failures*.csv`,
  `existing_routes_dropped.csv`; per-route disposition `Route_Disposition_Kashmir_v3.csv`

### Two service-level plans on the table
- **v3.3.7 (recommended phase-1)**: ~1,009 buses, +68% over current ~600,
  35-min headway ceiling, balanced 50/50 trunk fleet. Deployable Year-1 plan.
- **v3.3.4 (aspirational)**: 1,113 buses, +85%, 15-min everywhere. Year-3 ambition.

---

## 7. Calibration anchor (cite this when defending numbers)

CHALO ridership data, **May 2025 – Apr 2026, 11.6M trips across 30 SSCL e-bus
routes**. Engine blocks export if any of 8 QC checks fail. The cross_evaluate
objective compares engine fleet/route against a *headway-scaled* CHALO
equivalent (98 buses × 34/15 ≈ 220 = 7.33 buses/route) — apples-to-apples.

Known structural caveats (don't "fix" without intent):
- Phase-4 `Daily_Demand` uses corridor-share apportionment with the 0.18
  empirical capture scale. Most routes flag Amber_Under because demand is
  static (no Mohring elasticity). Fleet sizing is independent of this.
- Engine recommendation deliberately diverges from CHALO's *current* vehicle
  mix on SSCL routes (the 60% HPV cap) — the plan is a forward recommendation,
  not a transcription of current deployment.

---

## 8. Output artefacts (per version, in `outputs_vX.Y.Z/`)

| File | What |
|---|---|
| `Rationalised_Routes_Kashmir_v3.csv` | Full operational CSV (50+ cols). v3.3.8 audit-fix: now carries LPV_Count so HPV+MPV+LPV = Fleet_Required (was previously dropped) |
| `Kashmir_Route_Frequency_Plan_v3.xlsx` | Legacy 4-sheet workbook (engineering) |
| `Kashmir_Route_Frequency_Plan_vX.Y.Z_RTO.xlsx` | 9-sheet RTO-ready workbook (export_xlsx_rto in engine) |
| `Kashmir_Route_Frequency_Plan_vX.Y.Z_RTO_Pretty.xlsx` | **2-sheet** bus schedule (Summary + Route Plan), via `_beautify_rto_master.py`. v3.3.7: Operator Absorption + Sign-off sheets removed (RTO ask) — that detail stays in the 9-sheet RTO master. Route Plan carries Route_Code per route. **This is the dashboard's hero download.** |
| `Routes_with_Codes.xlsx` | Route plan + generated 12-char codes |
| `Master_Transit_Map_Kashmir_v3.html` | Interactive Folium map |
| `route_maps_kashmir/*.html` | 192 per-route maps |
| `Rationalised_Routes_Kashmir_v3.geojson` | 207 active features for GIS |
| `Rationalisation_Log_Kashmir_v3.csv` | Per-route reasoning strings (defend decisions) |
| `Passenger_Impact_Kashmir_v3.csv` | Public-facing summary |
| `Kashmir_Transit_Technical_Briefing.pptx` | Engineering deck |
| `Kashmir_Transit_Government_Briefing.pptx` | IAS/RTO deck |
| `Kashmir_Transit_Diagrammatic_Pitch.pptx` | 14-slide flowchart-style deck |

Standalone study PDFs in `E:\kash`:
- `Kashmir_Transit_Headway_Fleet_Fundamentals.pdf` — the maths
- `Kashmir_Transit_Outputs_Explained.pdf` — what each output file is

---

## 9. Generators / helper scripts

| Script | Purpose |
|---|---|
| `transit_kashmir_v3.py` | The engine (4-phase pipeline) |
| `cross_evaluate.py` | CHALO calibration; UTF-8 stdout; headway-scaled objective |
| `generate_route_codes.py` | 12-char codes from stops master (argv-driven) |
| `generate_presentations.py` | Technical + Government decks (live-bound to CSV) |
| `generate_kashmir_pitch.py` | Diagrammatic flowchart deck (live-bound to CSV) |
| `generate_study_pdf.py` | Headway/fleet fundamentals PDF |
| `generate_outputs_guide_pdf.py` | Outputs-explained PDF |
| `_beautify_rto_master.py` | 4-sheet pretty RTO workbook |
| `_sync_dashboard.py` | Copy assets + rebuild dashboard JSON with codes |
| `generate_timetables.py` | Departure-board timetables (Kashmir_Timetables_v1.xlsx, one sheet/district; per-route HPV/MPV/LPV mix + trips/day columns; service day 08:00–19:00 from the measured GPS operating day, SSCL 07:00–20:00; totals self-reconcile to 1,011/187/754/70) |
| `_export_route_json.py` | Slim evidence.json (fragment road coverage) + verification.json (deep-dive verdicts) per route → dashboard `data/` for the route drawer + chatbot |
| `apply_reality_v345.py` | v3.4.5 measured-cycle corrections (5 GPS-verified corridors → fleet 1,004→1,011) |
| `_patch_rto_master_v345.py` | Patch the 9-sheet RTO master to v3.4.5 (rows+totals+cover) |

**App-data ground-truth layer** lives in the companion repo `bus-sathi-trace-intelligence`
(`E:\bus-sathi-trace`) — mines the Bus Sathi app's real driver GPS into the dashboard
Reality Layer + the v3.4.5 measured-cycle correction. See that repo's README/AUDIT.md.

PPTX gotcha: `python-pptx` skips creating a run when cell text is `""` — always
pass a space placeholder, else `p.runs[0]` raises IndexError. Both deck
generators already guard this.

---

## 10. Visual QA for decks/workbooks (no LibreOffice on this box)

- PPTX → PNG via PowerPoint COM `Slide.Export(path, "PNG", 1920, 1080)`.
- XLSX → PNG via Excel COM `Range.CopyPicture(1,2)` + clipboard save. Must run
  in **-STA** mode (write a `.ps1` and call `powershell.exe -STA -File`).
- Always QA changed slides/sheets with fresh eyes (Read the PNG); recurring
  defects were text overflow and right-edge clipping past the 13.33" slide.

---

## 11. RTO meeting context

**Review r1 (→ v3.3.6):**
1. More MPVs on HPV-dominated trunks → `SSCL_HPV_SHARE_CAP = 0.60`.
2. LP-band headway 60 min too long → cut to 35 min.

**Review r2 (→ v3.3.7, CURRENT):**
1. *Completely* eliminate 60-min headways — 35 min max everywhere →
   `HEADWAY_MAX_MIN = 35` ceiling; regional 60/90, MPS 45, "regular" 60 all gone.
2. On a trunk, neither HPV nor MPV should be the majority → cap 0.60→**0.50**
   (both the SSCL cap and the long-haul non-SSCL bracket). Road-width data was
   raised as a "nice to have" — we don't have it (pending P2 ask), so the split
   is a flat balanced 50/50 for now, not road-width-aware.
3. Dashboard download clutter — RTO must reach the pretty bus-schedule Excel in
   one click → Kashmir section reworked to a hero pretty-workbook CTA + collapsed
   "Technical files" expander; `_sync_dashboard.py` now auto-copies the RTO +
   Pretty workbooks into `public/` and purges stale per-version files.

**Review r2 follow-ups (same v3.3.7 build, re-run in place):**
4. Route codes baked into the engine (see §3) — pretty workbook's Route Code
   column was blank; now fully populated (0 UNMATCHED in the published plan).
5. Pretty workbook trimmed to 2 sheets — Operator Absorption + Sign-off removed
   (see §8). The bus schedule is the focus.
6. Dashboard Phase-1 vs Phase-2 comparison removed — `KashmirServicePlans`
   now shows only Phase-1 (the recommended plan). Phase-2 data retained in
   `lib/kashmirServicePlans.ts` for reference but not rendered.
7. Pretty workbook "Pop. served" now uses `Population_Served_Raw` (the ~70k
   400m-walkshed count), not the apportioned `Population_Served` (~262 median)
   which read as absurdly small. Same fix applied to the dashboard map popup
   (geojson now carries `Population_Served_Raw` + `Route_Code`) and the table
   sort. NOTE: the walkshed figure overlaps between routes — don't sum it; the
   honest network total is the 1,158,399 deduplicated coverage figure.
8. Pretty workbook Route Plan trimmed further — Load flag / Social / Tourist
   columns removed (13 cols, ending at Pop. served).
9. Route names normalised in the engine (`_clean_route_name`, applied before
   Phase-4 so maps + CSV + workbook + dashboard all match): consistent Title
   Case with acronyms (LD/TRC/GBS…) preserved, the bidirectional "↔" separator
   unified to "to", and the SSCL "via …" detail kept. 0 ALL-CAPS / 0 "↔" remain.
11. Diagrammatic pitch (`generate_kashmir_pitch.py`) — the meeting deck —
    rewritten to be serious & defensible: formulas written out in full + a
    sources/references slide; all live v3.3.7 numbers; the version-lineage
    slide, the Phase-1-vs-Phase-2 plan comparison, all version labels and the
    "how do we know" Q&A slide REMOVED; short-forms/jargon expanded to full
    words in the narrative; demand framed as automatic open-data. QA'd via
    COM→PNG (14 slides, clean). The anticipated reviewer questions that used to
    be the Q&A slide were handed to the user in chat rather than in the deck.
10. Decks rewritten (`generate_presentations.py`) — both the Technical and
    Government briefings are now **diagram-led** (KPI cards, a 4-phase flow
    diagram, native doughnut/bar charts, formula+citation cards) with a full
    **references slide** (Vuchic, Ceder, TCQSM/TRB, Hansen, Ortúzar & Willumsen,
    Jenks, WorldPop/Tatem, OSRM/Luxen-Vetter, El-Geneidy). Phase-1 is the ONLY
    plan (the Phase-1-vs-Phase-2 comparison slides are gone). Demand is framed
    as an **automatic open-data model** (WorldPop+OSM+OSRM) — "no proprietary
    GPS/AFC feed required"; CHALO is cited only as a one-time published-aggregate
    calibration anchor (the prof flagged CHALO GPS as unobtainable — we never
    used GPS, only published totals). QA via PowerPoint COM→PNG (see §10): both
    12-slide decks render clean, no overflow. Desktop shortcuts already point at
    the outputs_v3.3.7 decks.

The pretty bus-schedule workbook is `Kashmir_Route_Frequency_Plan_vX.Y.Z_RTO_Pretty.xlsx`
(via `_beautify_rto_master.py`; also written to `C:\Users\Prash\Music\`). The old
hand-made `Formatted_Kashmir_Routes_Pretty.xlsx` is **retired** — it was a manual
Music-folder file that went stale; the dashboard now serves the engine-generated
pretty workbook directly. Desktop has `Kashmir Transit — *.lnk` shortcuts to the
latest decks/workbooks/PDFs (regenerated per build — see the shortcut script).

Data we asked the RTO for (to sharpen v3.4): P0 = master stops register, live
operator permit registry, GPS traces; P1 = Census 2021 ward pop, per-route AFC
ridership, JKTDC tourist arrivals; P2 = road operability calendar, stop/depot
inventory, bridge load/road-width registry.
