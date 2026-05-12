<p align="center">
  <img src="https://img.shields.io/badge/Engine-v3.0-1A237E?style=for-the-badge&logo=python&logoColor=white" alt="v3.0"/>
  <img src="https://img.shields.io/badge/Kashmir_Fork-May_2026-00695C?style=for-the-badge" alt="Kashmir Fork"/>
  <img src="https://img.shields.io/badge/SSCL_CHALO-30_Trunk_Routes-D32F2F?style=for-the-badge" alt="SSCL"/>
  <img src="https://img.shields.io/badge/Routes_Processed-326+-6A1B9A?style=for-the-badge" alt="Routes"/>
</p>

# 🚌 Kashmir Valley Transit Rationalisation Engine v3.0

**A data-driven bus route optimisation system for the Srinagar / Kashmir Valley public transport network.**

Built for the Principal Secretary of Transport, J&K — this engine ingests 326+ existing bus routes (minibuses, e-buses, MPS buses, JKRTC city/regional services), overlays them against WorldPop population rasters and OpenStreetMap Points of Interest, and produces a fully rationalised frequency plan with fleet allocation, headway schedules, and interactive maps.

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

Srinagar's public transit network has grown organically over decades — 326+ registered minibus/bus permits operating on overlapping corridors with no centralised frequency plan. The result:

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
│  CDI = (Pop×0.5 + POI×0.5) × Road_Multiplier                   │
│  Jenks Natural Breaks ──► HP / MP / LP bands                    │
│  Social obligation floor: LP→MP if near KP camps/hospitals      │
│  SSCL backbone: forced TRUNK/HP with 15-min headway             │
├─────────────────────────────────────────────────────────────────┤
│              PHASE 3: FLEET & FREQUENCY PLAN                    │
│  Fleet = ⌈Cycle_Time / Headway⌉  (floor at 2 buses)            │
│  Trunk: 85% HPV + 15% MPV  │  Feeder: 100% MPV                 │
│  LPV eradicated from fleet — zero tolerance policy              │
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
| **Trunk Headway** | 10 min (BRT assumption) | 15 min (matches SSCL operational target) |
| **Bounding Box** | Jammu UA (32.5°–33.0°N) | Kashmir Valley (33.5°–34.5°N, 74.4°–75.2°E) |
| **Population** | 1,653,873 (RITES 2024) | 1,660,000 (Census 2011 + SMC projection) |
| **River Crossing** | Tawi River (74.87°E) | Jhelum River (74.81°E) — 9 historic bridges |
| **POI Tiers** | 2-tier (high/low) | 3-tier: Year-round / Secondary / **Seasonal tourism** |
| **Season Toggle** | None | `WINTER_SCENARIO` flag — zeroes tourist POIs, shrinks walksheds |
| **Gender** | Not modelled | **64.5% women riders** (CHALO data) — +25% boost on women-anchor POIs |
| **Social Anchors** | Jagti, Muthi, Purkhoo camps | KP townships (Sheikhpora, Vessu, Mattan, Veerwan) + SKIMS/SMHS/LD hospitals |

### 3-Tier POI System

| Tier | Weight | Examples | Winter Mode |
|---|---|---|---|
| **Tier 1** (year-round) | 1.0 | Hospitals, bus stations, mosques, Lal Chowk, secretariat | ✅ Active |
| **Tier 2** (secondary) | 0.4 | Colleges, markets, schools, police stations | ✅ Active |
| **Tier 3** (seasonal) | 0.6 / **0.0** | Mughal gardens, Dal Lake gates, Gulmarg gondola, yatra shrines | ❌ Zeroed in winter |

---

## 🔄 Data Pipeline

### Step-by-Step Execution

1. **Load & Geocode Routes** — Parse 326+ route permits from `routes.csv` with flexible column aliasing
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
| `routes.csv` | 326 bus route permits with origin/destination/via columns | 41 KB |
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

# 3. Generate POIs (requires internet — queries Overpass API)
python extract_pois_kashmir.py --no-osrm --output pois.csv

# 4. Ensure OSRM Docker is running on port 5000, then:
python transit_kashmir_v3.py

# 5. Open the master map
# → Master_Transit_Map_Kashmir_v3.html
```

### Winter Mode

```bash
# Edit transit_kashmir_v3.py line 136:
WINTER_SCENARIO = True
# Then re-run — Tier 3 POIs zeroed, walksheds shrunk by 35%
```

---

## 📁 Project Structure

```
kashmir-transit-rationalisation/
├── transit_kashmir_v3.py         # 🔧 Main engine (3,087 lines)
├── extract_pois_kashmir.py       # 🗺  POI extractor (Overpass API + OSRM snap)
├── latlon.py                     # 📍 ArcGIS geocoder for route terminals
├── etracter.py                   # 🗺  Interactive route mapper (Folium + OSRM)
├── poiK.py                       # 📡 Offline PBF POI extractor (osmium)
├── routes.csv                    # 📊 326 existing bus route permits
├── requirements.txt              # 📦 Python dependencies
├── .gitignore                    # 🚫 Excludes large data & generated files
└── README.md                     # 📖 This file
```

### Script Descriptions

| Script | Purpose | Dependencies |
|---|---|---|
| **`transit_kashmir_v3.py`** | Core rationalisation engine — runs the full 12-step pipeline | OSRM, WorldPop raster, pois.csv |
| **`extract_pois_kashmir.py`** | Extracts POIs from OpenStreetMap Overpass API, classifies into Kashmir 3-tier vocabulary, snaps to road network | requests, pandas, OSRM (optional) |
| **`latlon.py`** | Geocodes route terminal names to lat/lon using ArcGIS | arcgis, pandas |
| **`etracter.py`** | Plots existing routes on interactive Folium map with vehicle category layers | folium, requests, shapely |
| **`poiK.py`** | Extracts high-traffic POIs from offline India OSM PBF file | osmium, pandas |

---

## ⚙ Configuration

All tunable parameters live at the top of `transit_kashmir_v3.py` (lines 120–500). Key ones:

| Parameter | Default | Description |
|---|---|---|
| `WINTER_SCENARIO` | `False` | Toggle winter mode (zeroes Tier 3 POIs, shrinks walksheds) |
| `CITY_CORE_LAT_THRESHOLD` | `34.07` | Latitude above which Downtown Srinagar congestion (2.0×) applies |
| `SSCL_TRUNK_HEADWAY_MIN` | `15` | Hardcoded headway for all 30 SSCL backbone routes |
| `HEADWAY_HP_MIN` | `15` | HP band headway for urban/peri-urban routes |
| `HEADWAY_MP_MIN` | `30` | MP band headway |
| `HEADWAY_LP_MIN` | `60` | LP band headway |
| `POI_TIER3_WEIGHT_SUMMER` | `0.6` | Tourist POI weight in summer |
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

---

## ⚠ Known Limitations

> **Phase 1 limitations — to be addressed in v4:**

1. **Euclidean walksheds** — Dal Lake, Anchar Lake, Hokersar wetlands, and the Jhelum River act as walking barriers. Routes adjacent to these features systematically over-count "served" population by ~15–25%.

2. **Binary winter toggle** — A full seasonal-stratified run (Chillai Kalan / shoulder / summer / monsoon) requires four passes. Currently only summer vs. winter.

3. **Tourist surge not modelled** — Gulmarg/Pahalgam/Sonmarg visitor flows are captured only through Tier-3 POI weights, not through actual visitor arrival data.

4. **Military polygons** — Security/convoy windows on NH-44 and military cantonment areas are not yet subtracted from the operable network.

5. **No per-route AFC validation** — CHALO real ridership data calibrates citywide headways and gender weighting, but per-route ridership validation is still manual.

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
  <i>Engine v3.0 — May 2026</i>
</p>
