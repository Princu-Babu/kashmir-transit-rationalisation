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

## 3. Route_Code generation (NEW — integrated v3.3.6)

- `generate_route_codes.py` + `Kashmir_Stops_Sectored_V2.csv` (the master stops
  file, 187 stops, columns: Master_Stop_Code, Stop_Name, Sector_ID, Latitude,
  Longitude, Stop_No, Tehsil_Code).
- Produces a deterministic 12-char code: `<TehsilO><TehsilD><SectorO><SectorD><StopO><StopD>`
  e.g. `PWSP08091215` = Pulwama→Shopian, sector 08→09, stop 12→15.
- Match cascade: exact → compact → suffix-stripped → substring → fuzzy 0.85.
- Latest run: **313/342 matched (91.5%)**, 29 UNMATCHED (small stops not yet in
  master: PANZINARA, BATWARA, BONE JOINT HOSPITAL BARZALLA, JAWAHAIRNAGAR…).
- `_sync_dashboard.py` code precedence: embedded CSV code → fresh
  Routes_with_Codes.xlsx → prior dashboard commit → TMP-K#### placeholder.
  Current dashboard state: **342/342 real codes, 0 TMP, 0 UNMATCHED.**
- When the RTO ships an updated stops master, drop it in, re-run
  `generate_route_codes.py` then `_sync_dashboard.py` — dashboard auto-updates.

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
| **v3.3.6** | **RTO Kashmir asks (CURRENT)** | **SSCL_HPV_SHARE_CAP=0.60 (more MPV on HPV-dominated trunks); LP headway 60→35 min; route-code generator integrated** |

---

## 5. Current key constants (v3.3.6)

```
HEADWAY_HP_MIN              = 20        # non-SSCL trunks
HEADWAY_MP_MIN             = 35        # feeders
HEADWAY_LP_MIN             = 35        # lifelines (was 60 — RTO ask)
SSCL_TRUNK_HEADWAY_MIN     = 15        # SSCL backbone (their design target)
SSCL_HPV_SHARE_CAP         = 0.60      # cap HPV per SSCL route (RTO ask)
FLEET_SPARE_RATIO          = 1.15      # maintenance/breakdown buffer
PHASE4_CORRIDOR_CAPTURE_SCALE = 0.18   # empirical CHALO demand anchor
CONGESTION_CITY_CORE       = 2.2       # downtown peak multiplier
JHELUM_BRIDGE_BOTTLENECK_MIN = 8.0
TOURIST_POPULATION_MULTIPLIER = 1.3    # tourist-corridor catchment boost
SSCL_HPV cap binding → SSCL HPV share 34% → 19%
```

---

## 6. Current numbers (v3.3.6, the live plan)

- 342 in-scope permits → **207 active** (Trunk 50 / Feeder 157 / Merged 135)
- **Total fleet 1,003** = HPV 84 / MPV 797 / LPV 122
- 45 SSCL permits matched to 30 CHALO routes
- 69 tourist corridors, 87 social-obligation routes (53 active)
- LP-band mean headway 38 min, LP fleet 91
- Network coverage 69.78% of 1.66M (deduplicated 1,158,399 residents)
- **0.60 buses / 1000 residents** (peer band: BMTC 0.51, Chandigarh CTU 0.65, Pune 0.75)
- **QC 8/8 passing, 0 Red_Overload**
- Calibration vs CHALO Apr 2026: per-route SSCL fleet **+9.7%** vs headway-scaled
  CHALO (within ±25% band) — this is THE calibration signal. Raw total-fleet
  +269% is NOT an error (operator absorption + 34→15 min headway upgrade).

### Two service-level plans on the table
- **v3.3.6 (recommended phase-1)**: ~1,003 buses, +65% over current ~600,
  conservative headways. This is the deployable Year-1 plan.
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
| `Rationalised_Routes_Kashmir_v3.csv` | Full operational CSV (50+ cols). NOTE: drops LPV_Count — derive as Fleet−HPV−MPV |
| `Kashmir_Route_Frequency_Plan_v3.xlsx` | Legacy 4-sheet workbook (engineering) |
| `Kashmir_Route_Frequency_Plan_vX.Y.Z_RTO.xlsx` | 9-sheet RTO-ready workbook (export_xlsx_rto in engine) |
| `Kashmir_Route_Frequency_Plan_vX.Y.Z_RTO_Pretty.xlsx` | 4-sheet cut-down (Summary/Route Plan/Operator Absorption/Sign-off), via `_beautify_rto_master.py` |
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

The RTO Kashmir reviewed the plan in person and asked for two changes
(both applied in v3.3.6):
1. More MPVs on HPV-dominated trunks → `SSCL_HPV_SHARE_CAP = 0.60`.
2. LP-band headway 60 min too long → cut to 35 min.

Talking points + the beautified Formatted_Kashmir_Routes_Pretty.xlsx live in
`C:\Users\Prash\Music\`. Desktop has 8 `Kashmir Transit — *.lnk` shortcuts to
the latest decks/workbooks/PDFs.

Data we asked the RTO for (to sharpen v3.4): P0 = master stops register, live
operator permit registry, GPS traces; P1 = Census 2021 ward pop, per-route AFC
ridership, JKTDC tourist arrivals; P2 = road operability calendar, stop/depot
inventory, bridge load/road-width registry.
