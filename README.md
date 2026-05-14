<p align="center">
  <img src="https://img.shields.io/badge/Engine-v3.2-1A237E?style=for-the-badge&logo=python&logoColor=white" alt="v3.2"/>
  <img src="https://img.shields.io/badge/Kashmir_Fork-May_2026-00695C?style=for-the-badge" alt="Kashmir Fork"/>
  <img src="https://img.shields.io/badge/SSCL_CHALO-30_Trunk_Routes-D32F2F?style=for-the-badge" alt="SSCL"/>
  <img src="https://img.shields.io/badge/In--Scope_Routes-342-6A1B9A?style=for-the-badge" alt="Routes"/>
</p>

# 🚌 Kashmir Valley Transit Rationalisation Engine v3.2

**A data-driven bus route optimisation system for the Srinagar / Kashmir Valley public transport network.**

Built for the Principal Secretary of Transport, J&K — this engine ingests 613+ registered route permits (minibuses, e-buses, MPS buses, JKRTC city/regional services), clips them to the **Srinagar Valley study area** (33.5°–34.5° N, 74.4°–75.2° E), and produces a fully rationalised frequency plan for the **342 in-scope routes**. Routes serving Kupwara, Karnah, Gurez, and remote Anantnag/Kishtwar tehsils fall outside this bounding box and are out of scope for this engine. The full-valley model (all 613) is a v4 expansion. Results are overlaid against WorldPop population rasters and OpenStreetMap Points of Interest to generate fleet allocation, headway schedules, and interactive maps.

---

## 📋 Table of Contents

- [Why This Exists](#-why-this-exists)
- [Architecture](#-architecture)
- [Kashmir-Specific Features](#-kashmir-specific-features)
- [Data Pipeline](#-data-pipeline)
- [Input Files](#-input-files)
- [Output Files](#-output-files)
- [Prerequisites](#-prerequisites)
- [Quick Start](#-quick-start)
- [Project Structure](#-project-structure)
- [Configuration](#-configuration)
- [SSCL E-Bus Backbone](#-sscl-e-bus-backbone)
- [Known Limitations](#-known-limitations)
- [License](#-license)

---

## 🎯 Why This Exists

Srinagar's public transit network has grown organically over decades — 613+ registered minibus/bus permits operating on overlapping corridors with no centralised frequency plan. Of these, **342 fall within the Srinagar Valley study area** (bounded 33.5°–34.5° N, 74.4°–75.2° E); the remaining permits serve remote tehsils (Kupwara/Karnah/Gurez/Kishtwar) which require a separate district-level pass. The result for the Srinagar core:

- **Over-served corridors**: 15+ buses on Parimpora ↔ Pantha Chowk ↔ Dalgate, competing for the same riders
- **Transit deserts**: South Srinagar industrial belt (Khonmoh, Rangreth), satellite towns (Ganderbal, Pulwama) grossly underserved
- **No headway discipline**: Buses bunch at peak hours, vanish off-peak
- **Fleet mismatch**: Large HPV buses on narrow Downtown mohalla lanes; minibuses on 40km inter-district highways

This engine solves these problems systematically using spatial analysis, demand modelling, and operations research.

---

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    PHASE 1: DATA INGESTION                      │
│  routes.csv ──► Column aliasing ──► OSRM routing ──► Geometries │
│  pois.csv   ──► 3-tier classify ──► Women-anchor boost          │
│  SSCL 30 routes injected as synthetic trunk backbone            │
├─────────────────────────────────────────────────────────────────┤
│                 PHASE 2: SPATIAL ANALYSIS                       │
│  Walk catchments (400m) ──► WorldPop raster ──► Population      │
│  POI buffer (250m) ──► Weighted gravity scores                  │
│  Junction penalties ──► Realistic cycle times (D2)              │
│  Corridor overlap ──► Union-Find clustering                     │
├─────────────────────────────────────────────────────────────────┤
│              PHASE 2b: ROUTE CLASSIFICATION                     │
│  CDI = Pop×0.5 + POI×0.5  (Road_Multiplier → tie-breaker only)  │
│  Jenks Natural Breaks ──► HP / MP / LP bands                    │
│  Social obligation floor: LP→MP if near KP camps/hospitals      │
│  SSCL backbone: forced TRUNK/HP with 15-min headway             │
├─────────────────────────────────────────────────────────────────┤
│              PHASE 3: FLEET & FREQUENCY PLAN                    │
│  Fleet = ⌈Cycle_Time / Headway⌉  (floor 2 urban / 1 regional)   │
│  Trunk HPV share by Route_KM brackets (<12 / 12-22 / 22+ km)    │
│  SSCL routes: empirical 9m/12m counts from CMP_TRUNK_ROUTES     │
│  LPV retention/rationalisation based on Vehicle_Category        │
├─────────────────────────────────────────────────────────────────┤
│              PHASE 4: EXPORT & CARTOGRAPHY                      │
│  4-sheet XLSX workbook  │  Interactive Folium maps               │
│  GeoJSON network  │  CSV audit log  │  Passenger impact report   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🏔 Kashmir-Specific Features

This is a **clean fork** from the Jammu Transit Engine v3 — every Jammu-specific assumption has been rebuilt for the Kashmir Valley:

| Feature | Jammu v3 | Kashmir v3 (this repo) |
|---|---|---|
| **Backbone** | 13 RITES CMP routes (BRT proposal) | 30 SSCL e-bus routes from CHALO ridership data |
| **Trunk Headway** | 10 min (BRT assumption) | 15 min (matches SSCL operational target) ¹ |
| **Bounding Box** | Jammu UA (32.5°–33.0°N) | Kashmir Valley (33.5°–34.5°N, 74.4°–75.2°E) |
| **Population** | 1,653,873 (RITES 2024) | 1,660,000 (Census 2011 + SMC projection) |
| **River Crossing** | Tawi River (74.87°E) | Jhelum River (74.81°E) — 9 historic bridges |
| **POI Tiers** | 2-tier (high/low) | 3-tier: Year-round / Secondary / **Seasonal tourism** |
| **Season Toggle** | None | `WINTER_SCENARIO` flag — zeroes tourist POIs, shrinks walksheds |
| **Gender** | Not modelled | **64.5% women riders** (CHALO data) — +25% boost on women-anchor POIs |
| **Social Anchors** | Jagti, Muthi, Purkhoo camps | KP townships (Sheikhpora, Vessu, Mattan, Veerwan) + SKIMS/SMHS/LD hospitals |

¹ In v3.1 the documentation said 15 min but the `SSCL_TRUNK_HEADWAY_MIN` constant was actually `45` (a leftover Jammu value). This was corrected in v3.2 — see the v3.2 changes section below.

### 3-Tier POI System

| Tier | Weight | Examples | Winter Mode |
|---|---|---|---|
| **Tier 1** (year-round) | 1.0 | Hospitals, bus stations, mosques, Lal Chowk, secretariat | ✅ Active |
| **Tier 2** (secondary) | 0.4 | Colleges, markets, schools, police stations | ✅ Active |
| **Tier 3 — tourist-only** | 0.6 / **0.0** | Gulmarg gondola, ski resorts, Amarnath base camp, houseboats | ❌ Zeroed in winter |
| **Tier 3 — residential anchor** ² | 0.6 / **0.4** | Boulevard / Dalgate / Nigeen gates, Mughal gardens | ⚠ Demoted to Tier-2 weight in winter (year-round residential pull preserved) |

² New in v3.2 — the previous code zeroed every Tier-3 POI in winter, which artificially demoted the Boulevard/Dalgate corridors that carry year-round local ridership.

---

## 🔄 Data Pipeline

### Step-by-Step Execution

1. **Load & Geocode Routes** — Parse 613+ route permits from `existing-routes.csv` with flexible column aliasing (342 remain after bounding-box clip)
2. **Inject SSCL Backbone** — Append 30 synthetic e-bus routes with hardcoded lat/lon
3. **OSRM Routing** — Concurrent geometry fetching from a local OSRM Docker instance
4. **Bounding Box Truncation** — Clip routes exceeding the Kashmir Valley study area
5. **Walk Catchments** — 400m buffers around virtual stops every 250m
6. **Population Scoring** — WorldPop raster zonal statistics per catchment
7. **POI Gravity** — Weighted POI count within 250m buffer, normalised by route-km
8. **Cycle Times** — Congestion-adjusted (2.0× Downtown, 1.5× peri-urban) + stop dwell + junction penalties
9. **Route Classification** — Union-Find clustering → CDI → Jenks breaks → HP/MP/LP bands
10. **Fleet Allocation** — `⌈Cycle_Time / Headway⌉` with 85/15 HPV-MPV split for trunks
11. **QC Checks** — 8 automated checks must pass before any export
12. **Export** — XLSX workbook, Folium maps, GeoJSON, CSV logs

---

## 📂 Input Files

| File | Description | Size |
|---|---|---|
| `existing-routes.csv` | 613 registered route permits; 342 in-scope after bounding-box clip | 85 KB |
| `pois.csv` | Points of Interest (generated by `extract_pois_kashmir.py`) | ~73 KB |
| `kashmir_worldpop.tif` | WorldPop 100m population raster (not in repo — download separately) | ~50 MB |

---

## 📦 Output Files

The engine produces 6 output files per run:

| Output | Description |
|---|---|
| `Kashmir_Route_Frequency_Plan_v3.xlsx` | 4-sheet workbook: Cover, Route Plan, Priority Summary, Route Type Summary |
| `Master_Transit_Map_Kashmir_v3.html` | Interactive Folium map with all trunk/feeder/regional layers + POIs |
| `Rationalised_Routes_Kashmir_v3.csv` | Full operational CSV with CDI scores, fleet, headways |
| `Rationalisation_Log_Kashmir_v3.csv` | Detailed audit log with reasoning strings for every route decision |
| `Passenger_Impact_Kashmir_v3.csv` | Per-route passenger impact analysis |
| `Rationalised_Routes_Kashmir_v3.geojson` | GeoJSON of the active network for GIS integration |

---

## ⚙ Prerequisites

### Required
- **Python 3.10+**
- **OSRM Docker** — Local routing engine on port 5000

### OSRM Setup (one-time)

```bash
# Download Kashmir/India OSM extract
wget https://download.geofabrik.de/asia/india-latest.osm.pbf

# Pre-process for OSRM
docker run -t -v "${PWD}:/data" osrm/osrm-backend osrm-extract -p /opt/car.lua /data/india-latest.osm.pbf
docker run -t -v "${PWD}:/data" osrm/osrm-backend osrm-partition /data/india-latest.osrm
docker run -t -v "${PWD}:/data" osrm/osrm-backend osrm-customize /data/india-latest.osrm

# Start the server
docker run -t -p 5000:5000 -v "${PWD}:/data" osrm/osrm-backend osrm-routed --algorithm mld /data/india-latest.osrm
```

### WorldPop Raster

Download the Kashmir region population raster from [WorldPop](https://www.worldpop.org/) and save as `kashmir_worldpop.tif` in the project root.

---

## 🚀 Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/Princu-Babu/kashmir-transit-rationalisation.git
cd kashmir-transit-rationalisation

# 2. Install dependencies
pip install -r requirements.txt

# 3. (Recommended) Set MapmyIndia API key for India-correct political boundaries
#    Get a free developer key at https://about.mappls.com/api/
set MAPPLS_API_KEY=your_key_here        # Windows
# export MAPPLS_API_KEY=your_key_here  # Linux / macOS
#
# Without a key, maps fall back to ESRI World Light Gray which is also
# India-correct. CartoDB / OpenStreetMap tiles are NOT used (they show
# international boundary conventions that conflict with India's official position).

# 4. Generate POIs (requires internet — queries Overpass API)
python extract_pois_kashmir.py --no-osrm --output pois.csv

# 5. Ensure OSRM Docker is running on port 5000, then:
python transit_kashmir_v3.py

# 6. Open the master map
# → Master_Transit_Map_Kashmir_v3.html
```

### Winter Mode

For J&K presentations, **run both scenarios and show the delta** — the seasonal-aware engine is the key differentiator from static RITES/CMP planning:

```bash
# Summer run (default — already complete after step 4)
python transit_kashmir_v3.py
# → outputs: Kashmir_Route_Frequency_Plan_v3.xlsx, Master_Transit_Map_Kashmir_v3.html

# Winter run (Chillai Kalan — Tier 3 tourist POIs zeroed, walksheds shrunk 35%)
# Edit transit_kashmir_v3.py line ~149:
#   WINTER_SCENARIO = True
# Then rename outputs to avoid overwriting summer run:
python transit_kashmir_v3.py
# → rename: Kashmir_Route_Frequency_Plan_v3_Winter.xlsx, etc.
```

The winter vs summer delta reveals which routes lose viability under snow conditions — typically the Tier-3 tourist corridors (Gulmarg, Pahalgam, Sonmarg gateways) drop to LP or are deactivated, while lifeline routes serving KP townships and district hospitals are protected by Social_Flag.

---

## 📁 Project Structure

```
kashmir-transit-rationalisation/
├── transit_kashmir_v3.py         # 🔧 Main engine (v3.1, vehicle-category aware)
├── extract_pois_kashmir.py       # 🗺  POI extractor (Overpass API + OSRM snap)
├── crop_raster.py                # ✂️ Population raster cropper (WorldPop → Study Area)
├── latlon.py                     # 📍 ArcGIS geocoder for route terminals
├── geocode_other_routes.py       # 📡 Specialized geocoder for Other-routes.csv
├── cross_evaluate.py             # ⚖️ Ground-truth calibration loop vs CHALO data
├── etracter.py                   # 🗺  Interactive route mapper (Folium + OSRM)
├── existing-routes.csv           # 📊 613 existing bus route permits (Master)
├── requirements.txt              # 📦 Python dependencies
├── .gitignore                    # 🚫 Excludes large data & generated files
└── README.md                     # 📖 This file
```

### Script Descriptions

| Script | Purpose | Dependencies |
|---|---|---|
| **`transit_kashmir_v3.py`** | Core rationalisation engine — runs the full 12-step pipeline | OSRM, WorldPop raster, pois.csv |
| **`extract_pois_kashmir.py`** | Extracts POIs from OpenStreetMap Overpass API, classifies into Kashmir 3-tier vocabulary, snaps to road network | requests, pandas, OSRM (optional) |
| **`crop_raster.py`** | Crops the large India-wide WorldPop raster (ind_ppp_2026_100m.tif) to the Srinagar study area | rasterio |
| **`latlon.py`** | Geocodes route terminal names to lat/lon using ArcGIS | arcgis, pandas |
| **`cross_evaluate.py`** | Cross-evaluates engine outputs against 3 CHALO ground-truth datasets (Fleet, KM, Trips, Demand Shape) | pandas, numpy |
| **`etracter.py`** | Plots existing routes on interactive Folium map with vehicle category layers | folium, requests, shapely |
| **`poiK.py`** | Extracts high-traffic POIs from offline India OSM PBF file | osmium, pandas |

---

## ⚙ Configuration

All tunable parameters live at the top of `transit_kashmir_v3.py` (lines 120–500). Key ones:

| Parameter | Default | Description |
|---|---|---|
| `WINTER_SCENARIO` | `False` | Toggle winter mode (zeroes tourist-only Tier 3, demotes residential-anchor Tier 3, shrinks walksheds) |
| `CITY_CORE_LAT_THRESHOLD` | `34.07` | Latitude above which Downtown Srinagar congestion applies |
| `CONGESTION_CITY_CORE` | `2.2` | Downtown Srinagar peak-hour congestion multiplier (bumped from 1.4 in v3.2) |
| `CONGESTION_PERI_URBAN` | `1.4` | Peri-urban congestion multiplier (bumped from 1.1 in v3.2) |
| `SSCL_TRUNK_HEADWAY_MIN` | `15` | Hardcoded headway for all 30 SSCL backbone routes (was wrongly `45` in v3.1) |
| `JHELUM_BRIDGE_BOTTLENECK_MIN` | `8.0` | New in v3.2 — additive bridge-queue minutes for Jhelum crossings (applied even when OSRM succeeds) |
| `STOP_PENALTY_MIN` | `0.5` | Stop dwell time penalty (calibrated to 30s) |
| `HEADWAY_HP_MIN` | `15` | HP band headway for urban/peri-urban routes |
| `HEADWAY_MP_MIN` | `30` | MP band headway |
| `HEADWAY_LP_MIN` | `60` | LP band headway |
| `MIN_FLEET_URBAN` | `2` | Fleet floor for Urban / Peri_Urban routes |
| `MIN_FLEET_REGIONAL` | `1` | Fleet floor for Regional_District lifelines (was a blanket 2 in v3.1) |
| `POI_TIER3_WEIGHT_SUMMER` | `0.6` | Tier-3 POI weight in summer (tourist-only AND residential-anchor) |
| `POI_TIER3_RES_WEIGHT_WINTER` | `0.4` | Tier-3 residential-anchor weight in winter (v3.2 — was `0.0` for everything) |
| `WOMEN_ANCHOR_BOOST` | `1.25` | +25% demand boost for women-anchor POIs |
| `OVERLAP_THRESHOLD` | `0.65` | Minimum overlap for route merging |
| `TRUNK_CDI_GATE_PERCENTILE` | `30` | CDI percentile gate for trunk promotion |
| `TRUNK_MIN_LENGTH_KM` | `5.0` | Anti-stranding: minimum length for trunk eligibility |

---

## 🚍 SSCL E-Bus Backbone

All **30 SSCL (Srinagar Smart City Limited) e-bus routes** from CHALO ridership data (April 2026) are hardcoded as the backbone trunk network:

| ID | Route | Fleet | Bus Type |
|---|---|---|---|
| SSCL-01 | Parimpora → Harwan | 7 | 9m |
| SSCL-02 | Batamaloo → Nasrullah Pora | 5 | 9m |
| SSCL-03 | Batamaloo → Hazratbal | 6 | 9m |
| SSCL-07 | Batamaloo → Drussu Pulwama | 4 | 12m |
| SSCL-14 | TRC → Central University Ganderbal | 6 | 9m |
| SSCL-19 | Pantha Chowk → Sumbal | 4 | 12m |
| SSCL-24 | Pantha Chowk → Palhalan | 6 | 12m |
| ... | *+ 23 more routes* | | |

**Total deployed fleet**: 98 buses (73 × 9-metre + 25 × 12-metre)

### Fleet context: SSCL deployed vs engine-recommended

The engine's total fleet recommendation of **~1,059 buses** covers the entire 342-route rationalised network — not just the SSCL e-bus pilot. These are not comparable numbers:

| Segment | Currently deployed | Engine-recommended |
|---|---|---|
| SSCL e-buses (30 routes) | **98** (CHALO data, Apr 2026) | **~140–180** (demand-justified at 15-min headway) |
| Private minibuses + JKRTC + MPS (212 active routes) | ~500–800 permits (existing) | **~880** (rationalised) |
| **Total in-scope network** | ~600–900 | **~1,059** |

The SSCL-only fleet comparison (engine vs CHALO) is within ±15% — see `cross_evaluate.py` for the full calibration report.

---

## ⚠ Known Limitations

> **Phase 1 limitations — to be addressed in v4:**

1. **Euclidean walksheds** — Dal Lake, Anchar Lake, Hokersar wetlands, and the Jhelum River act as walking barriers. Routes adjacent to these features systematically over-count "served" population by ~15–25%.

2. **Binary winter toggle** — A full seasonal-stratified run (Chillai Kalan / shoulder / summer / monsoon) requires four passes. Currently only summer vs. winter.

3. **Tourist surge not modelled** — Gulmarg/Pahalgam/Sonmarg visitor flows are captured only through Tier-3 POI weights, not through actual visitor arrival data.

4. **Military polygons** — Security/convoy windows on NH-44 and military cantonment areas are not yet subtracted from the operable network.

5. **No per-route AFC validation** — The new `cross_evaluate.py` module calibrates system-level fleet size and total KM against CHALO data, but strict route-by-route AFC ridership comparison is still manual.

6. **WorldPop raster uses an absolute path** — `RASTER_PATH` in `transit_kashmir_v3.py` is hardcoded to `E:/kash/kashmir_worldpop.tif`. Change this constant before running on a different machine, or the engine will raise a `RuntimeError` rather than silently produce zero population scores.

7. **No headway elasticity (Mohring effect)** — The engine treats demand as exogenous. Doubling SSCL frequency would attract additional riders away from autos; this demand-response feedback is not modelled. v4 target.

8. **115 merged routes carry political risk** — `MERGED_INTO_TRUNK` routes represent absorbed operator permits. The `Displaced_Operator_Class` column in the XLSX/CSV export breaks these down by operator type (Private Minibus / MPS / JKRTC). Operator absorption or buyback recommendations should accompany the plan before submission to the All J&K Transport Welfare Association.

---

## 🛠 Changes in v3.2 (Audit Response)

A senior transit planner's audit of v3.1 surfaced three presentation-blockers, six logic flaws, and four code-hygiene issues. v3.2 fixes them all without changing the architecture. Each fix is keyed (A1 … C4) so the audit trail is reviewable.

### A. Presentation blockers

| ID | What was wrong | Fix |
|---|---|---|
| **A1** | `RASTER_PATH = "kashmir_worldpop.tif"` (relative) caused `Population_Served = 0` and `Pop_Score = 0.5` for every route because the raster lives at `E:/kash/kashmir_worldpop.tif`, outside the worktree. The engine silently swallowed this. | Absolute path; missing raster or missing `rasterstats` now raises `RuntimeError`; sum-to-zero post-condition added in `compute_population` (`transit_kashmir_v3.py`). |
| **A2** | `SSCL_TRUNK_HEADWAY_MIN = 45` while every docstring and the brief said `15`. Caused the engine fleet to come in 60–70% below CHALO. | Constant set to `15`; log messages and docstrings cleaned up (`transit_kashmir_v3.py:413`, step6 docstring). |
| **A3** | `existing-routes.csv` has a literal but empty `Route_Name` column, so the engine's "construct from `Route_From`/`Route_To`" fallback never fired and the audit log emitted `Route_Name=nan` on every row. SSCL fuzzy-matching silently degraded. | `load_routes` now treats empty/blank/`nan` as missing, surfaces `Origin`/`Destination` aliases, and reconstructs `"A ↔ B"` for any blank row. |

### B. Logic flaws

| ID | What was wrong | Fix |
|---|---|---|
| **B1** | `Final_CDI = raw_cdi × Road_Multiplier` was circular — `Road_Multiplier` is derived from `Action_Taken`, so already-promoted trunks received a 1.67× advantage that contaminated Jenks band thresholds. | `Final_CDI = Pop×0.5 + POI×0.5` only. `Road_Multiplier` is now a Step-5 tie-breaker — routes within ±5% of a Jenks break get promoted up / demoted down one band by the multiplier (`step4a_compute_final_cdi`, `step5_assign_priority_bands`). |
| **B2** | Blanket 85% HPV / 15% MPV on every trunk contradicted SSCL's actual fleet (74% MPV / 26% HPV; short urban loops are 100% 9m). | Step 9 now (a) reads `bus_9m`/`bus_12m` directly from `CMP_TRUNK_ROUTES` for SSCL routes and (b) for non-SSCL trunks applies a Route_KM bracket: `<12 km → 0% HPV`, `12–22 km → 50/50`, `≥22 km → 85/15`. QC Check 5 relaxed accordingly. |
| **B3** | Jhelum bridge bottleneck minutes only counted in the OSRM-fallback branch. When OSRM succeeded (the common case), bridge-queue time was silently zero. | New constant `JHELUM_BRIDGE_BOTTLENECK_MIN = 8.0`; `apply_geometries` detects Jhelum crossing once and adds the bottleneck to `duration_s` on both branches. |
| **B4** | `CONGESTION_CITY_CORE = 1.4` was too gentle for Nawakadal–Habba Kadal at peak. | Bumped to `2.2` (Downtown) and `1.4` (peri-urban). Step-7 docstring and `_detect_congestion_zone` docstring rewritten to drop the stale `lat > 32.72` Jammu reference. |
| **B5** | `MIN_FLEET_THRESHOLD = 2` was applied blanket — every rural lifeline got at least 2 buses regardless of demand. | Split into `MIN_FLEET_URBAN = 2` and `MIN_FLEET_REGIONAL = 1`. Step 8 applies the right floor per `Route_Type`. |
| **B6** | Winter mode zeroed *every* Tier-3 POI, demoting Boulevard / Dalgate / Mughal-garden corridors even though those neighbourhoods carry year-round residential demand. | `POI_TIER3_CATEGORIES` split into `POI_TIER3_TOURIST_ONLY` (zeroed in winter) and `POI_TIER3_RESIDENTIAL_ANCHOR` (demoted to `0.4`, not zeroed). |

### C. Code hygiene

| ID | What was wrong | Fix |
|---|---|---|
| **C1** | `TAWI_RIVER_LON = JHELUM_RIVER_LON` alias and a comment still referenced the Jammu river. | Alias removed; the header-comment line rewritten. `grep TAWI` now returns nothing. |
| **C2** | Several docstrings still cited `lat > 32.72`, "v6 used a 4-tier system", and "1,653,873" (Jammu CMP figure). | `_detect_congestion_zone`, `compute_cycle_times`, `count_weighted_poi_scores`, and `step1_normalise_population_score` docstrings rewritten to describe the current Kashmir reality. |
| **C3** | `compute_overlap_matrix` had its multiprocessing block commented out because of an OpenBLAS-Windows hang. | `OMP_NUM_THREADS=1` / `OPENBLAS_NUM_THREADS=1` / `MKL_NUM_THREADS=1` pinned at the top of the file *before* multiprocessing imports. Parallel `ProcessPoolExecutor` re-enabled inside a `try/except` that logs and falls back to the existing sequential loop on any failure — never regresses. |
| **C4** | `cross_evaluate.py` sampled only May (peak tourist month), divided by a hardcoded `/ 31`, and baked in `mode_share=0.06` / `trip_rate=1.3` constants with no sourcing. No objective number for a calibration loop. | 12-month average across the full FY 2025-26 + April 2026 rows, per-month days from `calendar.monthrange`, named module constants `MODE_SHARE=0.09` / `TRIP_RATE=1.6` documented against SSCL's free-fare regime, and a new objective output `sum(% error²)` across {SSCL fleet, daily KM, daily trips}. Loud warning if `Population_Served` sums to zero (catches A1 regressions). |

### What's still v4 (intentionally not changed)

The audit's longer-horizon recommendations are scoped to v4 and have NOT been attempted in v3.2:

- Network-graph walkshed (OSMnx isochrones clipped against Dal/Anchar/Nigeen/Hokersar polygons + Jhelum centreline + military cantonments).
- Per-bridge node graph with daily operability status (replaces the single-longitude Jhelum approximation).
- NH-44 / Srinagar–Sonmarg convoy time-of-day operability mask.
- Tourist surge volume model (Gulmarg ski-season vs. shoulder).
- Inter-modal connectivity to the upcoming Srinagar Metro and Banihal/Baramulla rail.
- Demand elasticity (Mohring effect from headway reductions).
- Equity audit / Gini coefficient across tehsils.

---

## 🔑 Key CHALO/SSCL Data Points

| Metric | Value | Source |
|---|---|---|
| Total ridership (12-month) | 11,632,326 | CHALO May 2025 – Apr 2026 |
| Women rider share | 64.5% | CHALO (free-fare effect) |
| Peak hour | 9:00 AM | Citywide observed |
| Peak pax/hour | 4,346 | Apr 2026 mean |
| Operated/Scheduled KM ratio | 84.5% | Annual mean |
| Service hours | 6 AM – 10 PM | SSCL operational window |

---

## 📄 License

This project is developed for the Government of Jammu & Kashmir, Principal Secretary of Transport. The source code is provided as-is for academic and governmental use.

---

<p align="center">
  <i>Built with 🏔️ for the Kashmir Valley</i><br>
  <i>Engine v3.2 — May 2026 (audit response)</i>
</p>
