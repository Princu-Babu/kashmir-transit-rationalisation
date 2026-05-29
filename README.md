<p align="center">
  <img src="https://img.shields.io/badge/Engine-v3.3.7-1A237E?style=for-the-badge&logo=python&logoColor=white" alt="v3.3.7"/>
  <img src="https://img.shields.io/badge/Kashmir_Fork-May_2026-00695C?style=for-the-badge" alt="Kashmir Fork"/>
  <img src="https://img.shields.io/badge/SSCL_CHALO-30_Trunk_Routes-D32F2F?style=for-the-badge" alt="SSCL"/>
  <img src="https://img.shields.io/badge/In--Scope_Routes-342-6A1B9A?style=for-the-badge" alt="Routes"/>
</p>

# 🚌 Kashmir Valley Transit Rationalisation Engine v3.3.7

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
10. **Fleet Allocation** — `⌈Cycle_Time / Headway⌉` with a balanced 50/50 HPV-MPV split for trunks (v3.3.7 — neither class a majority)
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

## 🗺️ Route Code Methodology

*(This logic is implemented in the `generate_route_codes.py` script)*

Every route in the network is assigned a deterministic 12-character `Route_Code` derived from its origin and destination stops. The code is a compact, human-inspectable identifier that encodes administrative location, network sector, and stop position — allowing engineers reading the code to infer roughly where the route runs without consulting a lookup table.

### Anatomy of a Route Code

A Route Code consists of exactly 12 alphanumeric characters arranged in three blocks of four:

```
SRBG  1002  0705
│     │     │
│     │     └── Stop block (4 digits): origin stop no. + destination stop no.
│     └──────── Sector block (4 digits): origin sector ID + destination sector ID
└────────────── Tehsil block (4 letters): origin tehsil code + destination tehsil code

```

* **Tehsil block (positions 1–4):** Two two-letter tehsil codes concatenated. The first pair identifies the origin's administrative tehsil, the second pair the destination's.
* *Example:* `SRBG` means the route starts in Srinagar tehsil (`SR`) and ends in Budgam tehsil (`BG`).


* **Sector block (positions 5–8):** Two two-digit sector IDs concatenated, each zero-padded. Sectors are the operational sub-zones within a tehsil used for route planning.
* *Example:* `1002` means origin is in Sector 10, destination is in Sector 02.


* **Stop block (positions 9–12):** Two two-digit stop numbers concatenated, each zero-padded. The stop number is the stop's sequence position within its sector.
* *Example:* `0705` means stop 07 (origin) and stop 05 (destination).


### Source of Truth

All three components are read from the master stops file (`Kashmir_Stops_Sectored_V2.csv`), which lists every served stop along with its `Tehsil_Code`, `Sector_ID`, and `Stop_No`. The Route Code is therefore a pure function of the stops master — if a stop's sector or stop number changes upstream, regenerating the codes will reflect that automatically. The route plan itself never assigns these IDs.

### Construction Procedure

For each route in the route plan:

1. **Parse the route name** to extract origin and destination. Two name patterns are supported: bidirectional (`A ↔ B`) and directional (`A to B via X Y Z`). The *via* segment is discarded — only endpoints participate in the code.
2. **Look up the origin** in the stops master to retrieve its `Tehsil_Code`, `Sector_ID`, and `Stop_No`.
3. **Look up the destination** using the same process.
4. **Assemble the three blocks** by concatenating origin and destination values in order: tehsils, then sectors, then stops.

#### Worked Example

Take the route **Parimpora ↔ Hazratbal**:

| Endpoint | Source | Tehsil | Sector | Stop No. |
| --- | --- | --- | --- | --- |
| **Parimpora (origin)** | From stops master | `BG` | `02` | `22` |
| **Hazratbal (destination)** | From stops master | `SR` | `10` | `18` |

* **Concatenation Process:** * `BG` + `SR` → `BGSR`
* `02` + `10` → `0210`
* `22` + `18` → `2218`


* **Final Route Code:** `BGSR02102218`

### Name Normalization for Matching

Route names and stop names are not guaranteed to match character-for-character across different datasets. To keep the matcher tolerant without producing false matches, lookups are executed in escalating order of looseness until a match is found:

* **Exact match** after uppercasing and trimming whitespace.
* **Compact match** — both names are reduced to uppercase alphanumerics only, removing spaces and punctuation. This resolves mismatches like `PANTHA CHOWK` ↔ `PANTHACHOWK`.
* **Suffix-stripped match** — common landmark suffixes (`CHOWK`, `CROSSING`, `HOSPITAL`, `BUS STAND`, `RAILWAY STATION`, `COLLEGE`, `STOP`) are dropped before compacting. This resolves issues like `CHADOORA CHOWK` ↔ `CHADOORA`.
* **Substring match** in either direction on the compacted form.
* **Fuzzy close match** using a similarity ratio of 0.85 or higher via `difflib.get_close_matches`. This serves as the last resort to resolve single-character spelling drifts like `BATAMALOO` ↔ `BATAMALLO`.

### Core Design Rules

* **Deterministic and Idempotent:** Re-running the generator on unchanged inputs always produces identical codes.
* **Direction-Sensitive:** `A → B` and `B → A` produce different codes. For bidirectional (`↔`) routes, the side written first in the route name is treated as the origin.
* **Not Globally Unique Alone:** Two distinct routes that happen to share the exact same origin and destination stops will receive the same code. If your network configuration allows duplicate terminal routings, pair `Route_Code` with `New_Route_ID` to preserve uniqueness.
* **Stable Under Unrelated Edits:** Adding new stops to other sectors does not change existing codes; edits only impact routes if they modify the origin or destination stop's specific tehsil, sector, or stop number properties.

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

# 3. Generate POIs (requires internet — queries Overpass API)
python extract_pois_kashmir.py --no-osrm --output pois.csv

# 4. Ensure OSRM Docker is running on port 5000, then:
python transit_kashmir_v3.py

# 5. Open the master map
# → Master_Transit_Map_Kashmir_v3.html
# Note: Maps use OpenStreetMap/CartoDB tiles which may not reflect
# India's official political boundaries for J&K.
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
├── transit_kashmir_v3.py         # 🔧 Main engine (v3.3.5 — honest fleet sizing)
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
| `HEADWAY_HP_MIN` | `20` | HP band headway for urban/peri-urban routes (v3.3.5: was 15) |
| `HEADWAY_MP_MIN` | `35` | MP band headway (v3.3.5: was 30) |
| `HEADWAY_LP_MIN` | `35` | LP band headway (v3.3.6: was 60 — RTO ask) |
| `HEADWAY_MAX_MIN` | `35` | **v3.3.7** — hard network-wide ceiling; every headway is clamped to this, so no route waits longer than 35 min |
| `SSCL_HPV_SHARE_CAP` | `0.50` | **v3.3.7** — per-route HPV cap on SSCL trunks (was 0.60); keeps neither vehicle class a majority |
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

> **Effective headway note** — at 98 buses across 30 routes, CHALO's observed bus-trip count (~855/day → ~28.5 round trips/route) implies an *effective* average headway of ~34 min, not 15. The 15-min target is the engine's recommended service level, not the current operating state.

### Fleet context: SSCL deployed vs engine-recommended

The engine's total fleet recommendation of **~1,009 buses** covers the entire 342-route rationalised network — not just the SSCL e-bus pilot. These are not comparable numbers:

| Segment | Currently deployed | Engine-recommended |
|---|---|---|
| SSCL e-buses (30 routes / 45 matched permits) | **98** (CHALO data, Apr 2026) | **362** (demand-justified at 15-min headway) |
| Private minibuses + JKRTC + MPS (~190 active routes) | ~500–800 permits (existing) | **~647** (rationalised) |
| **Total in-scope network** | ~600–900 | **1,009** |

The SSCL-only fleet comparison (v3.3.7, 35-min headway ceiling + 50/50 trunk split): engine recommends **362 buses across the 45 matched permits** at the **SSCL design target of 15-min headway** (unchanged from v3.3.4). Non-SSCL trunks are now sized at a more realistic 20-min target headway. The +269% raw fleet delta vs CHALO's 98 buses is *not* a calibration error — it absorbs (a) the 15 duplicate private/JKRTC permits upgraded into trunk service alongside the SSCL e-bus and (b) the headway upgrade from CHALO's ~34-min effective service to the 15-min target. On the apples-to-apples basis — engine fleet/route vs **headway-scaled CHALO** (220 buses at 15-min) — the engine recommends **8.04 buses/route vs scaled CHALO 7.33 = +9.7%, within the ±25% calibration band**. See `cross_evaluate.py`.

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

8. **Demand-elasticity not modelled.** Engine produces fleet recommendations for the 15-min target headway, then computes `Load_Ratio` against a static demand model. Because the static model doesn't add riders when frequency increases (Mohring effect), Load_Ratio looks low across the network and `Subsidy_Risk_Flag` flags 184/237 routes. The fleet recommendation is still correct (it sizes supply for the target service level), but the financial KPIs assume current ridership at improved frequency, which is pessimistic. v4 target.

9. **115 merged routes carry political risk** — `MERGED_INTO_TRUNK` routes represent absorbed operator permits. The `Displaced_Operator_Class` column in the XLSX/CSV export breaks these down by operator type (Private Minibus / MPS / JKRTC). Operator absorption or buyback recommendations should accompany the plan before submission to the All J&K Transport Welfare Association.

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

## 🛠 Changes in v3.3 (Phase-1 Audit, round 1)

v3.3 layered planner-review flags and a derived KPI sheet on top of v3.2 without altering the rationalisation maths.

| Area | Change |
|---|---|
| **Ingestion** | New flags per route: `Route_Type` (Urban / Peri_Urban / Regional_District), `Tourist_Corridor`, `Seasonal_Operability` (Year-round / Seasonal / Winter-suspended). |
| **Fleet sizing** | Post-cycle spare ratio of 1.15 applied to `Fleet_Required` (was 1.0). Industry-standard buffer for breakdowns, deadheading, and shift changes. |
| **Classification** | Step 5b: `SSCL_CDI_Conflict` flag surfaces non-SSCL routes whose CDI exceeds the worst SSCL trunk — planner-review only, no auto-reclassification. |
| **Phase 4 (new)** | Derived per-route KPIs computed *after* fleet locks (no feedback into CDI): `Daily_Trips`, `Daily_KM`, `Daily_Capacity_Pax`, `Daily_Demand_Pax`, `Load_Ratio`, `Load_Flag`, `Pax_Journey_Time_Min`, `Daily_Revenue_INR`, `Daily_Op_Cost_INR`, `Viability_Ratio`, `Subsidy_Risk_Flag`, `Emissions_GCO2_Daily`, `Equity_Score`. |

## 🛠 Changes in v3.3.1 (Phase-1 Audit, round 2)

Round 2 was a tightening pass on the v3.3 additions — each fix keyed STEP 1 … STEP 11 in code.

| ID | What was wrong | Fix |
|---|---|---|
| **STEP 1** | OSRM glitches and long inter-district highway routes occasionally produced Cycle_Time_Min values implying >5 min/km, which then sized absurd fleet on those routes. | Per-km cycle-time sanity cap. Routes exceeding the cap are clipped and logged. |
| **STEP 6** | `PHASE4_MODE_SHARE` was a single 9% constant for all routes, but inter-district routes face heavier shared-sumo / private-auto competition. | Typology-aware modal capture: Urban 9% (CHALO baseline), Peri_Urban ×0.8, Regional_District ×0.6. |
| **STEP 7** | `Subsidy_Risk_Flag` threshold of 0.5 hid many marginal routes that would still be politically risky if unsubsidised. | Threshold raised 0.5 → 0.6 (any route with Viability_Ratio < 0.6 and not Social_Flag is flagged). |
| **STEP 10** | Social Obligation list had 17 entries, including industrial estates that don't actually need the lifeline floor. | Pruned to 11 entries (KP townships + district hospitals + camps). |
| **STEP 11** | `SSCL_CDI_Conflict` triggered on 78% of active routes — any route with CDI ≥ worst SSCL trunk. Useless as a planner-review filter. | Tightened with a +0.2 CDI delta; `SSCL_CDI_Conflict_Strong` vs `_Weak_SSCL` split for review prioritisation. |
| **cross_evaluate (round 2)** | Objective mixed engine one-way trips with CHALO bus-trips; SSCL "implied pax" used dedup-residual catchment. Produced 561,389 objective and a misleading 0.21× pax ratio. | Round-trip normalisation; headway-adjusted SSCL fleet parity as the sole objective. UTF-8 stdout for Windows. |

---

## 🛠 Changes in v3.3.2 (Phase-4 calibration + portability)

| Area | Change |
|---|---|
| **Phase-4 demand model** | `Daily_Demand_Pax` rewritten to use `Population_Served_Raw` × headway-weighted corridor share × typology mode-share × trip-rate × empirical capture-scale. New columns exported: `Population_Served_Raw`, `Corridor_Competitors`. SSCL trunk demand now sums to ~32.5k/day vs CHALO observed 31.9k — **engine/CHALO ratio 1.02× (was 0.21× in v3.3.1)**. |
| **Capture-scale calibration** | New constant `PHASE4_CORRIDOR_CAPTURE_SCALE = 0.18` empirically anchors the buffer-based supply model to CHALO observed ridership. Absorbs auto/walk/private-mode leakage that the 400m buffer can't see. Documented for re-calibration when CHALO totals shift more than ±15%. |
| **cross_evaluate objective** | Replaced misleading "headway-normalised SSCL fleet" objective with **per-route fleet parity** (engine fleet/route vs CHALO fleet/route). Acknowledges operator-absorption explicitly: the +34.7% total-fleet delta is 15 duplicate permits being upgraded, not a calibration error. Per-route fleet error: **-10.2%, within ±15%**. |
| **cross_evaluate demand check** | Now reads engine's `Daily_Demand_Pax` directly instead of recomputing from the apportioned `Population_Served` (which under-counts SSCL by 5-10×). |
| **RASTER_PATH portability** | `RASTER_PATH` resolution order: `--raster <path>` CLI flag → `$KASHMIR_WORLDPOP` env var → local `./kashmir_worldpop.tif` next to the engine → legacy `E:/kash/kashmir_worldpop.tif`. Makes the engine runnable on any machine without editing the source. |

### Calibration scorecard (v3.3.2 vs CHALO Apr 2026)

| Metric | CHALO | Engine v3.3.2 | Delta |
|---|---|---|---|
| SSCL fleet (raw count) | 98 | 132 | +34.7% (operator absorption — by design) |
| SSCL fleet per route | 3.27 | 2.93 | **-10.2%** (within ±15%) |
| SSCL Daily_Demand_Pax | 31,869 | 32,469 | **+1.9%** (within ±10%) |
| QC checks | n/a | 8/8 passing | ✓ |

---

## 🛠 Changes in v3.3.3 (Teammate review)

Three concrete corrections raised in code review, applied without changing the rationalisation maths.

| ID | What was wrong | Fix |
|---|---|---|
| **T1** | Only **4 routes** (all "Parimpora–Harwan" variants) were getting `Tourist_Corridor=True`. The keyword check missed everything else because the permit data records urban hub names at the endpoints (SRINAGAR/PARIMPORA/SOURA), not the tourist destinations along the route. | New tourist-zone centroid set, split into two classes (post-audit tightening): **DISTANT** (Gulmarg, Pahalgam, Sonamarg, Tangmarg, Doodhpathri, Yusmarg, Aharbal, Kokernag, Verinag, Achabal, Mughal Garden Achabal, Harwan, Tulip Garden) → geometry within 2 km auto-tags; **INNER_CITY** (Shalimar, Nishat, Cheshma, Pari Mahal, Boulevard, Nigeen) → endpoint within 0.6 km only, to stop downtown-traversing commuter routes being over-tagged. Similar geometry check for Mughal Road / Sinthan / Sadhna / Z-Morh / Zojila → `Winter_Suspended`. **Tagged routes 4 → 69 (post-audit, after tightening).** |
| **T2** | The proposed tourist boost was supposed to apply ONCE — at catchment-population level — but the existing code had no tourist boost at all (CDI ×1.3 had been rejected in audit, and no replacement was wired). Tier-3 POI weight alone was insufficient. | New `TOURIST_POPULATION_MULTIPLIER = 1.3` applied inside `compute_population()` to routes flagged `Tourist_Corridor`. Single multiplier — propagates consistently through Pop_Score → Final_CDI → classification and through Population_Served_Raw → Phase-4 Daily_Demand. No CDI multiplier and no second POI bump on top. |
| **T3** | `Daily_Capacity = avg_cap × daily_trips` double-counted — `avg_cap` is fleet-summed seat capacity, `daily_trips` is route-total one-way trips. Result: Load_Ratio collapsed to ~0.001 on every route, so all 237 active routes showed `Amber_Under`. | Replaced with the correct cycle-time-based formula: `Daily_Capacity = Fleet × VehicleCapacity × (ServiceMinutes / Cycle_Time_Min)`. Worked example (LALBAZAR, 9 buses × 35 seats, cycle 99 min): 9 × 35 × 9.7 = **3,058 seats/day** (was an inflated multiple of this). |

### Phase-4 KPI distribution before / after v3.3.3

| Phase-4 outcome | v3.3.2 (broken capacity) | v3.3.3 |
|---|---|---|
| `Load_Flag = Green` | 0 | 7 |
| `Load_Flag = Amber_Under` | 237 | 187 |
| `Load_Flag = Amber_Tight` | 0 | 1 |
| `Load_Flag = Red_Overload` | 0 | 12 |
| `Subsidy_Risk_Flag = True` | 184 | 154 |

Red_Overload routes are the new actionable insight — corridors where the recommended fleet at the 15-min target headway is **still short of demand**. All 12 are SSCL-table-fleet trunks where the empirical fleet (2–4 buses) cannot sustain a 15-min headway on a 100–180 min cycle. **Interpretation:** either SSCL increases fleet on these corridors, or they accept a longer effective headway. Worth a separate planner review.

### Calibration scorecard (v3.3.3 vs CHALO Apr 2026)

| Metric | CHALO | Engine v3.3.3 | Delta |
|---|---|---|---|
| SSCL fleet (raw count) | 98 | 132 | +34.7% (operator absorption — by design) |
| SSCL fleet per route | 3.27 | 2.93 | **-10.2%** (within ±15%) |
| SSCL Daily_Demand_Pax | 31,869 | 32,686 | **+2.6%** (within ±10%) |
| Tourist corridors flagged | n/a | 69 (was 4 in v3.3.2) | ✓ |
| QC checks | n/a | 8/8 passing | ✓ |

---

## 🛠 Changes in v3.3.4 (Honest fleet sizing)

An independent audit of the dashboard caught two real bugs and one engine inconsistency.

| ID | What was wrong | Fix |
|---|---|---|
| **A1** | Hero subtitle showed `"61 large + 676 medium = 737"` but total fleet was 883 — the **146 LPV** were dropped from the breakdown text. | Dashboard text now reads `large + medium + small`. The lib also had `lpvTotal: 0` hardcoded; `lpvCount` is now read from the CSV and summed across active routes. |
| **A2** | SSCL trunks used the CHALO empirical fleet (132 buses) as a hard override on Fleet_Required, contradicting the 15-min target headway. All 12 Red_Overload signals in v3.3.3 were SSCL routes where the empirical 2–4 buses could not actually sustain a 100–180 min cycle at 15-min headway. | Empirical SSCL fleet is now a **floor**, not an override. If the cycle-time formula demands more buses, the engine recommends the higher number and scales the 9m/12m split proportionally. Fleet rose 883 → **1,113** (140 HPV / 827 MPV / 146 LPV). Red_Overload → 0. |
| **A3** | cross_evaluate's per-route objective compared engine fleet at 15-min headway against CHALO fleet at 34-min headway — apples to oranges. | Per-route comparison now uses the **headway-scaled CHALO equivalent** (98 × 34/15 = 220 buses → 7.33 buses/route). Engine recommendation 8.04 buses/route → **+9.7%, within ±25%**. |

### Calibration scorecard (v3.3.4 vs CHALO Apr 2026)

| Metric | CHALO (current) | CHALO (scaled to 15-min) | Engine v3.3.4 | Calibration error |
|---|---|---|---|---|
| SSCL fleet | 98 buses @ ~34-min headway | ~220 buses | 362 | +64% vs scaled (cycle-time conservatism) |
| SSCL fleet/route | 3.27 buses | 7.33 buses | 8.04 | **+9.7% vs scaled — OK** |
| SSCL Daily_Demand_Pax | 31,869 | n/a | ~33k | within ±10% |
| Tourist corridors flagged | n/a | n/a | 69 | (unchanged from v3.3.3) |
| Active routes / total fleet | n/a | n/a | 207 / 1,113 | |
| Red_Overload routes | n/a | n/a | **0** (was 12 in v3.3.3) | ✓ |
| QC checks | n/a | n/a | 8/8 passing | ✓ |

Fleet density: **0.67 buses per 1000 study-area residents** (vs Indian peer-city benchmarks: BMTC 0.5, Delhi DTC+cluster 0.9, Mumbai BEST 1.2). Sits in the defensible range.

---

## 🛠 Changes in v3.3.5 (Conservative phase-1 headways)

After v3.3.4 the fleet recommendation came in at 1,113 buses, an **+85% expansion over Srinagar's current operations** (~600 buses). Reality check raised a fair concern: is 15-min headway on **130 trunk routes** politically and operationally achievable in Year-1? Indian peer cities (Chandigarh CTU at the closest size) hit 15-min on only a handful of routes; most run at 20-30 min.

v3.3.5 rebalances to a **phase-1 plan** that's still ambitious but defensibly achievable:

| Band | v3.3.4 headway | v3.3.5 headway | Rationale |
|---|---|---|---|
| **SSCL trunks** (45 permits / 30 CHALO routes) | 15 min | **15 min (unchanged)** | Matches SSCL's published design target — this is their commitment, not the engine's |
| **Non-SSCL trunks** (HP band, ~85 routes) | 15 min | **20 min** | Matches BMTC Volvo trunks (10–15) / Chandigarh CTU (15–20). Realistic phase-1 service |
| **MP feeders** (~54 routes) | 30 min | **35 min** | Closer to peer feeder norms (Pune PMPML, BMTC ordinary) |
| **LP lifelines** (~23 routes) | 60 min | 60 min (unchanged) | Already at floor for inter-district / lifeline service |

### Outcome (vs v3.3.4)

| Metric | v3.3.4 | v3.3.5 | Δ |
|---|---|---|---|
| Total fleet | 1,113 | **988** | **−125 (−11%)** |
| HPV / MPV / LPV | 140 / 827 / 146 | 138 / 730 / 120 | |
| Buses per 1000 residents | 0.67 | **0.60** | Between BMTC (0.51) and Chandigarh (0.65) — peer-city band |
| Active routes / structure | 207 / 50T 157F | 207 / 50T 157F | unchanged |
| Tourist corridors | 69 | 69 | unchanged |
| QC checks | 8/8 | 8/8 | ✓ |
| Red_Overload | 0 | 0 | ✓ |
| Expansion over current (~600 buses) | +85% | **+65%** | More politically palatable |

This is the **recommended phase-1 plan**. A future "phase-2 aspirational" run can revert to v3.3.4's 15-min HP / 30-min MP for the long-term ambition.

---

## 🛠 Changes in v3.3.6 (First RTO Kashmir review)

The RTO Kashmir reviewed the plan in person. Two asks, both applied:

| Ask | Change |
|---|---|
| "Lifeline routes at 60 min — 1 hour is too long." | `HEADWAY_LP_MIN` cut **60 → 35 min**. |
| "Trunks are dominated by 12 m buses; give MPVs more share." | New per-route `SSCL_HPV_SHARE_CAP = 0.60` on SSCL-matched trunks + long-haul non-SSCL bracket cut 85% → 60% HPV. |

Also integrated `generate_route_codes.py` (deterministic 12-char route codes from the master stops file) into the standard build, and wired the dashboard to carry official codes forward across runs.

---

## 🛠 Changes in v3.3.7 (Second RTO Kashmir review — current)

The RTO came back with two sharper asks plus a dashboard request. All applied:

| Ask | Change |
|---|---|
| **"Eliminate the 60-minute headways entirely — 35 minutes maximum, everywhere."** | The rural-lifeline bands (`HEADWAY_REGIONAL_HP_MIN` 60, `HEADWAY_REGIONAL_MP_MIN` 90), the 45-min MPS floor, and the 60-min "regular"-category bucket are all gone. A new hard ceiling `HEADWAY_MAX_MIN = 35` clamps every assigned headway. **Headways in the published plan are now only 15 / 20 / 35 min — 0 routes above 35.** |
| **"On a trunk route, neither HPV nor MPV should be the majority — balance them."** | `SSCL_HPV_SHARE_CAP` 0.60 → **0.50** and the long-haul non-SSCL bracket 0.60 → **0.50**. With integer rounding MPV ends at most one bus ahead of HPV. **0 trunk routes have an HPV majority.** Road-width data (a pending P2 RTO data ask) would let us bias narrow corridors toward MPV per-segment later. |
| **"Clean up the dashboard downloads — the RTO needs one-click access to the pretty bus-schedule Excel."** | Dashboard Kashmir section reworked: the pretty bus-schedule workbook is now the single hero download; the 9-sheet master workbook + map sit beside it; every other artefact is tucked into a collapsed "Technical files" expander. Stale per-version workbooks are auto-purged on sync. |

### Outcome (vs v3.3.6)

| Metric | v3.3.6 | v3.3.7 | Δ |
|---|---|---|---|
| Total fleet | 1,003 | **1,009** | +6 (35-min ceiling raised a few rural/operator routes) |
| HPV / MPV / LPV | 84 / 797 / 122 | **80 / 807 / 122** | 0.50 cap shifted ~4 HPV → MPV |
| Max headway anywhere | 60 min | **35 min** | the directive |
| Headway values present | 15 / 20 / 35 / 60 / 90 | **15 / 20 / 35** | 60- and 90-min bands eliminated |
| Trunk routes with HPV majority | some | **0** | neither class dominant |
| Buses per 1000 residents | 0.60 | **0.61** | still in the Chandigarh CTU peer band |
| Active routes / structure | 207 / 50T 157F | 207 / 50T 157F | unchanged |
| Per-route SSCL fleet vs scaled CHALO | +9.7% | **+9.7%** | calibration unchanged, within ±25% |
| QC checks / Red_Overload | 8/8 · 0 | **8/8 · 0** | ✓ |

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
  <i>Engine v3.3.7 — May 2026 (35-min headway ceiling · balanced 50/50 trunk fleet)</i>
</p>
