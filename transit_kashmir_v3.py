"""
transit_kashmir_v3.py  —  Srinagar / Kashmir Valley Transit Rationalisation Engine v3.0
================================================================================
Principal Secretary of Transport / IAS Officer — Srinagar / Kashmir Valley
Route Rationalisation Project | Forked from Jammu v3 | May 2026

WHY THIS FORK EXISTS:
  Jammu (32.7° N, plain, hot-dry, RITES CMP, no e-bus deployment) and the
  Kashmir Valley (~34° N, bowl-shaped, hill-divided, Chillai Kalan winters,
  SSCL e-bus + CHALO data already live) are structurally different transit
  problems. Tuning Jammu constants for Kashmir produces confidently wrong
  outputs. This is a clean fork — every Jammu-specific assumption rebuilt.

KEY CHANGES FROM JAMMU v3:

  SSCL BACKBONE INJECTION  — 30 Hardcoded Trunk Routes from CHALO Data
    REPLACED: The 13 RITES CMP Jammu Table 4.2 routes have been removed
              entirely. inject_cmp_trunk_routes() now injects all 30 SSCL
              (Srinagar Smart City Limited) e-bus routes from CHALO ridership
              data (Apr 2026), forcing each one to UPGRADED_TO_TRUNK/HP.
    HEADWAY:  Hardcoded to 15 min for SSCL trunks (was 10 in Jammu). 15 min
              matches the SSCL operational headway target (25-min stop-to-stop)
              and Srinagar's actual peak demand (~4,346 pax/hr citywide at 9 AM
              across the network, not radial-CBD).

  GEOGRAPHIC RE-CENTRING
    • Bounding box: Srinagar UA + Budgam/Ganderbal peri-urban + valley
      reach to Sopore/Pulwama/Anantnag/Kupwara
      Lat 33.50–34.50  Lon 74.40–75.20
    • CITY_CORE_LAT_THRESHOLD: 32.72 (old Jammu) → 34.07 (Srinagar
      Lal Chowk + Downtown / mohalla quarters above this latitude).
    • Jhelum river crossing: TAWI_RIVER_LON 74.87 → JHELUM_RIVER_LON 74.81.
      Same circuity logic; routes crossing Jhelum forced through one of the
      nine historic bridges get +60% circuity penalty.

  CMP POPULATION BASELINE
    Replaced Jammu's 1,653,873 (2024 RITES) with Srinagar UA population from
    Census 2011 + projection: 1,180,570 (2011) → ~1,660,000 (2024) →
    2,100,000 (2034). Source: Census of India 2011 + SMC projections.

  SEASONAL POI TIER (Kashmir-specific, new in this fork)
    Tier 1 (1.0, year-round) : hospitals, transit hubs, govt offices, mosques
    Tier 2 (0.4, year-round) : colleges, markets, schools
    Tier 3 (0.6 summer / 0.0 winter) : tourist gates, gardens, gondola,
                                        shrines on yatra calendar
    Winter mode (WINTER_SCENARIO=True) zeroes Tier 3 and applies a
    snow-walkshed shrink. Default: summer.

  GENDER-WEIGHTED DEMAND (CHALO calibration)
    Observed share: 64.5% of riders are women (free-fare effect).
    Women-anchor POIs (women's colleges, hospitals, markets, schools)
    get a +25% demand boost in the POI gravity score.

  SOCIAL_OBLIGATION_ATTRACTORS
    Replaced 11 Jammu-specific attractors (Jagti, Muthi, Purkhoo, GMC etc.)
    with 13 Kashmir-specific anchors: KP migrant camps (Sheikhpora,
    Vessu, Mattan, Veerwan), tertiary hospitals (SKIMS Soura, SMHS, LD,
    Bone & Joint, JLNM Rainawari), industrial estates (Khonmoh, Rangreth,
    Lassipora), and Sumbal/Ganderbal/Pulwama district HQ hospitals.

  QC SANITY TERMS
    Narwal/Amphalla (Jammu) → Lal Chowk / Hazratbal / Batamaloo (Srinagar).

WHAT IS KEPT INTACT FROM JAMMU v3:
  • All Directive logic (D1 lifeline retention, D2 realistic cycle times,
    D5 95th-percentile pop cap, D6 audit logging)
  • OSRM concurrent fetcher + circuity fallback
  • LPV eradication (HPV/MPV-only fleet)
  • Anti-stranding 5km min trunk length
  • CDI 30th-pct gate
  • Connectivity bonus 1.5× for routes touching the backbone
  • All Folium + XLSX export pipelines

KASHMIR-SPECIFIC LIMITATIONS (Phase 1, to be addressed in v4):
  • Walksheds remain Euclidean buffers. Dal Lake / Anchar / Hokersar /
    Jhelum acting as barriers, and slope-impeded walking, are NOT yet
    modelled. Routes adjacent to these features will systematically
    over-count "served" population by ~15–25%.
  • Winter scenario is binary (flag). A full seasonal-stratified run
    (Chillai Kalan / shoulder / summer / monsoon) requires four passes.
  • Tourist arrival surge (Gulmarg/Pahalgam/Sonmarg) is captured only
    through the Tier-3 seasonal POI weight, not through actual visitor
    flow modelling.
  • Security/convoy windows on NH-44 and military polygons not yet
    subtracted from operable network.
  • CHALO real ridership data is used here to calibrate SSCL trunk
    headways and women-share weighting, but per-route AFC validation
    is still a v4 task.
================================================================================
"""
import concurrent.futures
import multiprocessing
from typing import Dict, List, Optional, Tuple
def _intersection_worker(args):
    """Worker function for parallel overlap computation."""
    i, buf_i, area_i, candidates = args
    results = []
    
    # Clean geometry if invalid
    if not buf_i.is_valid:
        buf_i = buf_i.buffer(0)
        
    for j, buf_j, area_j in candidates:
        if not buf_j.is_valid:
            buf_j = buf_j.buffer(0)
        try:
            inter_area = buf_i.intersection(buf_j).area
            ratio_i_j = inter_area / area_i if area_i > 0 else 0.0
            ratio_j_i = inter_area / area_j if area_j > 0 else 0.0
            results.append((j, ratio_i_j, ratio_j_i))
        except Exception:
            # Fallback to 0 if the geometry math fundamentally crashes
            results.append((j, 0.0, 0.0))
            
    return i, results

# ──────────────────────────────────────────────────────────────────────────────
#  CONFIGURATION  (every tunable parameter lives here — never buried in logic)
# ──────────────────────────────────────────────────────────────────────────────

# ─── Directive 2: Congestion zones ──────────────────────────────────────────
# City core = Downtown Srinagar / mohalla quarters (lat > 34.07):
#             Nawakadal, Rajouri Kadal, Khanyar, Gojwara, Habba Kadal,
#             Lal Chowk, Hawal — narrow lanes, bridge bottlenecks, bazaar grids
# Peri-urban = Hyderpora, Rangreth, Pampore, Pantha Chowk, Bemina,
#              Budgam, Ganderbal — mixed urban/highway, lower congestion
CITY_CORE_LAT_THRESHOLD     = 34.07   # SRINAGAR (was 32.72 for Jammu)
CONGESTION_CITY_CORE        = 2.0    # 2× free-flow (peak hour gridlock — bridges, bazaars)
CONGESTION_PERI_URBAN       = 1.5    # 1.5× free-flow (peri-urban mixed traffic)

# ─── Kashmir-specific: Seasonal scenario flag ───────────────────────────────
# True  → Chillai Kalan / winter mode: Tier-3 (tourist) POIs zeroed,
#         walkshed shrunk, snow-prone routes flagged Lifeline,
#         operated/scheduled KM penalty 15% reflects CHALO Jan data.
# False → Default summer / shoulder season run.
WINTER_SCENARIO             = False
WINTER_WALKSHED_SHRINK      = 0.65   # Effective walkshed = 65% of summer (snow + cold)
WINTER_OP_RATIO_PENALTY     = 0.85   # Operated/scheduled KM ratio in winter (CHALO observed)

# ─── Directive 2: Stop penalty ───────────────────────────────────────────────
STOP_SPACING_M              = 500    # One virtual stop every 500m along route
STOP_PENALTY_MIN            = 1.5    # 1.5 min dwell per stop (boarding/alighting)

# ─── Directive 2: Layover buffer ─────────────────────────────────────────────
TERMINAL_LAYOVER_FACTOR     = 1.10   # 10% terminal layover (was 15% blanket in v6)

# ─── Minimum viable fleet (LPV downgrade removed; floor enforced directly) ───
MIN_FLEET_THRESHOLD         = 2      # Below this → raise to MIN_FLEET_THRESHOLD directly

# ─── Directive 1: Route type thresholds ──────────────────────────────────────
URBAN_KM_THRESHOLD          = 15.0   # < 15km = Urban
PERIURBAN_KM_THRESHOLD      = 40.0   # 15–40km = Peri-Urban, > 40km = Regional_District

# ─── Directive 1: Headways for Regional_District routes ──────────────────────
HEADWAY_REGIONAL_HP_MIN     = 60     # Rural lifeline HP: 60 min
HEADWAY_REGIONAL_MP_MIN     = 90     # Rural lifeline MP: 90 min

# ─── Directive 5: Population normalisation cap ────────────────────────────────
POP_CAP_PERCENTILE          = 95     # Cap at 95th percentile before normalising

# ─── Srinagar / Kashmir Valley Study-Area Population ─────────────────────────
# Source: Census of India 2011 (Srinagar UA = 1,180,570) + SMC Master Plan
# 2035 + RITES Srinagar CMP projections + Smart City DPR.
# Used to convert raw Population_Served counts → % of study-area population.
# Note: This is Srinagar UA + immediate peri-urban (Budgam, Ganderbal fringe).
# A full Valley-wide model would need ~7M (all districts) but ridership data
# is currently SSCL/CHALO-bound to Srinagar metropolitan reach.
CMP_POPULATION_BY_YEAR = {
    2011: 1_180_570,
    2018: 1_420_000,
    2024: 1_660_000,
    2034: 2_100_000,
    2044: 2_580_000,
}
CMP_REFERENCE_YEAR       = 2024          # Nearest planning horizon
CMP_TOTAL_POPULATION     = CMP_POPULATION_BY_YEAR[CMP_REFERENCE_YEAR]  # 16,60,000

# ─── Kashmir 3-Tier POI Weights (was 2-tier in Jammu v3) ──────────────────────
# Tier 1 (w=1.0): Year-round mass attractors with high sustained ridership
# Tier 2 (w=0.4): Education / secondary commerce (lower than Jammu's 0.2 because
#                 CHALO data shows education trips drive ~30% of women ridership)
# Tier 3 (w=0.6 summer / 0.0 winter): Tourism, gardens, shrines on yatra calendar
#                 Toggled by WINTER_SCENARIO flag
POI_TIER1_WEIGHT            = 1.0
POI_TIER2_WEIGHT            = 0.4
POI_TIER3_WEIGHT_SUMMER     = 0.6
POI_TIER3_WEIGHT_WINTER     = 0.0
POI_TIER3_WEIGHT            = (POI_TIER3_WEIGHT_WINTER if WINTER_SCENARIO
                                else POI_TIER3_WEIGHT_SUMMER)

# Women-anchor POI boost (CHALO calibration: 64.5% of riders are women)
# These categories receive +25% weighted demand to reflect observed gender split
WOMEN_ANCHOR_BOOST          = 1.25
WOMEN_ANCHOR_CATEGORIES = frozenset({
    "womens_college", "women_college", "girls_school", "girls_college",
    "maternity_hospital", "gynaec_hospital", "mch_centre",
    "anganwadi", "women_market", "ladies_market",
})

POI_TIER1_CATEGORIES = frozenset({
    # Transit infrastructure (Srinagar hubs)
    "railway_station", "railway", "train_station", "rail",
    "isbt", "bus_station", "bus_terminal", "transit_hub",
    "trc", "tourist_reception_centre",
    "batamaloo_bus_stand", "parimpora_bus_stand", "pantha_chowk_depot",
    "nishat_bus_terminal",
    # Tertiary / major health (Kashmir-specific)
    "hospital", "govt_hospital", "medical_college", "major_hospital",
    "skims", "skims_soura", "smhs_hospital", "lal_ded_hospital",
    "bone_and_joint_hospital", "jlnm_rainawari", "chest_diseases_hospital",
    "gmc_srinagar",
    # Commercial / mass attractors (Srinagar bazaars + malls)
    "mall", "supermarket", "major_market", "regal_chowk", "lal_chowk",
    "polo_view", "residency_road", "amira_kadal", "city_centre",
    # Religious mass attractors (year-round)
    "jamia_masjid", "hazratbal_shrine", "khanqah", "dastgeer_sahib",
    "shah_e_hamdan",
    # Industrial estates (mass employment)
    "industrial_estate", "factory", "industry", "sicop",
    "khonmoh_industrial", "rangreth_industrial", "lassipora_industrial",
    # KP migrant townships (social obligation anchor — Kashmir-specific)
    "kp_migrant_camp", "kp_township", "sheikhpora_camp", "vessu_camp",
    "mattan_camp", "veerwan_camp",
    # Government / IT
    "civil_secretariat", "high_court", "rajbhawan", "raj_bhawan",
    # University main campuses (year-round, very high ridership)
    "university_of_kashmir", "iist_awantipora", "central_university_kashmir",
    "nit_srinagar", "smvd",
})

POI_TIER2_CATEGORIES = frozenset({
    # Education (secondary — colleges, schools)
    "college", "campus", "engineering_college", "school",
    "higher_education", "polytechnic", "iti", "degree_college",
    # Local commerce
    "market", "commercial", "wholesale_market", "small_shop",
    "haba_kadal_market", "maharaj_gunj",
    # Defence / civic
    "army", "bsf", "crpf", "military", "cantonment",
    "stadium", "bakshi_stadium", "polo_ground",
    # Government services (lower tier)
    "government", "govt_office", "court", "clinic", "small_medical",
    "dispensary", "museum", "police_station",
    # Recreation (year-round)
    "park", "library", "auditorium", "tagore_hall",
})

# Tier 3: Seasonal / tourist (zeroed in winter mode)
POI_TIER3_CATEGORIES = frozenset({
    # Tourism gates (Srinagar + Valley)
    "tourist_spot", "tourist_gate", "shikara_ghat",
    "dal_lake_gate", "boulevard_gate", "nigeen_lake_gate",
    # Mughal gardens
    "mughal_garden", "nishat_garden", "shalimar_garden",
    "chashme_shahi", "pari_mahal", "tulip_garden", "harwan_garden",
    # High-altitude tourism
    "gulmarg", "pahalgam", "sonmarg", "doodhpathri", "yusmarg",
    "gondola", "ski_resort", "ropeway",
    # Yatra-calendar shrines (seasonal)
    "amarnath_base_camp", "kheer_bhawani",
    # Tourist info / hotels
    "houseboat", "tourist_hotel",
})

DEFAULT_POI_WEIGHT_V2       = POI_TIER2_WEIGHT   # Unmapped → Tier 2
# ─── Bounding Box: Kashmir Valley reachable by SSCL network ─────────────────
# Covers: Srinagar UA + Budgam + Ganderbal + Sumbal/Safapora + Pulwama +
#         Anantnag (south) + Sopore/Baramulla outskirts (NW) + Tral (SE)
# Excludes: Kupwara, Karnah, Gurez, Marwa/Warwan (handled separately as
#           Regional_District lifelines flagged in main()).
BOUNDS_MIN_LAT = 33.50
BOUNDS_MAX_LAT = 34.50
BOUNDS_MIN_LON = 74.40
BOUNDS_MAX_LON = 75.20

# Speed zones — Kashmir-specific (was Jammu zones)
# Old city Srinagar (Downtown): narrow lanes, bridges, bazaars
# Peri-urban Srinagar: Hyderpora-Rangreth-Bemina belt
# Valley / district highway: NH-1A, Srinagar-Sopore highway, etc.
SPEED_OLD_CITY_KMH          = 10.0   # Downtown Srinagar mohallas
SPEED_VALLEY_HIGHWAY_KMH    = 28.0   # NH-1A and inter-district roads
SPEED_DEFAULT_KMH           = 18.0   # Suburban / mixed corridors

# Geometry / Routing (unchanged)
MAX_IMPUTED_SL_KM           = 999    # DIRECTIVE 1: No hard cap — process all routes
CIRCUITY_FACTOR             = 1.25
CIRCUITY_FACTOR_RIVER       = 1.60   # Jhelum crossings: must use one of 9 bridges
JHELUM_RIVER_LON            = 74.81  # Approx longitude of Jhelum through Srinagar
                                     # (was TAWI_RIVER_LON = 74.87 for Jammu)
TAWI_RIVER_LON              = JHELUM_RIVER_LON  # backward-compat alias for legacy callers
MIN_ROUTE_KM                = 1.0
VIRTUAL_STOP_SPACING_M      = 250    # For catchment / population (Step 1)
# Walkshed: 400m summer, ~260m winter (snow shrink). Applied to both catchment
# and POI buffer so that demand contracts realistically during Chillai Kalan.
WALK_CATCHMENT_M            = int(400 * (WINTER_WALKSHED_SHRINK if WINTER_SCENARIO else 1.0))
POI_BUFFER_M                = int(250 * (WINTER_WALKSHED_SHRINK if WINTER_SCENARIO else 1.0))
OVERLAP_BUFFER_M            = 80
OVERLAP_THRESHOLD           = 0.65
OD_PROXIMITY_TOLERANCE_M    = 2500
SIMPLIFY_TOL_M              = 2.0

# Step 3: Road Multiplier (unchanged)
ROAD_MULTIPLIER_TRUNK       = 1.25
ROAD_MULTIPLIER_FEEDER      = 0.75
ROAD_MULTIPLIER_DEFAULT     = 1.00

# CDI weights (unchanged)
CDI_POP_WEIGHT              = 0.50
CDI_POI_WEIGHT              = 0.50

# Social Obligation (unchanged)
SOCIAL_FLAG_BUFFER_M        = 500

# Step 6: Headway per Priority Band for Urban/Peri-Urban routes
HEADWAY_HP_MIN              = 15
HEADWAY_MP_MIN              = 30
HEADWAY_LP_MIN              = 60

# Junction penalty (unchanged)
JUNCTION_PENALTY_PER_TURN_MIN = 0.5
SHARP_TURN_DEG              = 75

# Fleet cap (unchanged)
STD_TO_MINI_RATIO           = 2.5
TERMINAL_BUFFER_M           = 300
FLEET_CAP_HARD              = 45
GRAVITY_EPSILON             = 0.1
TRANSFER_PENALTY_MIN        = 5

# OSRM (unchanged)
OSRM_BASE_URL               = "http://localhost:5000"
OSRM_TIMEOUT_S              = 8
OSRM_MAX_WORKERS            = 12

# CRS (unchanged)
UTM_CRS                     = "EPSG:32643"
WGS84_CRS                   = "EPSG:4326"

# I/O
RASTER_PATH                 = "kashmir_worldpop.tif"
ROUTES_CSV                  = "routes.csv"
POIS_CSV                    = "pois.csv"
OUTPUT_DIR                  = "route_maps_kashmir"
LOG_CSV                     = "Rationalisation_Log_Kashmir_v3.csv"
ROUTES_OUT_CSV              = "Rationalised_Routes_Kashmir_v3.csv"
ROUTES_OUT_XLSX             = "Kashmir_Route_Frequency_Plan_v3.xlsx"
PASSENGER_IMPACT_CSV        = "Passenger_Impact_Kashmir_v3.csv"
MASTER_MAP_HTML             = "Master_Transit_Map_Kashmir_v3.html"
ROUTES_GEOJSON              = "Rationalised_Routes_Kashmir_v3.geojson"

# ─── CHALO / SSCL ridership calibration constants ───────────────────────────
# Sourced from SSCL_Data_Updated.xlsx (April 2026 + 12-month series)
CHALO_TOTAL_RIDERSHIP_12M   = 11_632_326   # May 2025 – Apr 2026
CHALO_WOMEN_SHARE           = 0.645         # 64.5% women (free-fare effect)
CHALO_PEAK_HOUR             = 9             # 9 AM — observed citywide peak
CHALO_SECONDARY_PEAK_HOUR   = 17            # 5 PM
CHALO_PEAK_PAX_PER_HOUR     = 4346          # Citywide pax/hr at peak (Apr 2026 mean)
CHALO_TROUGH_PAX_PER_HOUR   = 521           # Citywide pax/hr at 9 PM (Apr 2026 mean)
CHALO_OP_RATIO              = 0.845         # Operated / Scheduled KM (annual mean)
CHALO_SERVICE_START_HR      = 6
CHALO_SERVICE_END_HR        = 22

# Social Obligation Attractors — Kashmir / Srinagar specific (was Jammu)
SOCIAL_OBLIGATION_ATTRACTORS = [
    # KP migrant townships (Govt of India ORM-managed)
    ("Sheikhpora KP Township Budgam",  33.9683, 74.6736),
    ("Vessu KP Township Qazigund",     33.6478, 75.1431),
    ("Mattan KP Township Anantnag",    33.7406, 75.2347),
    ("Veerwan KP Camp Baramulla",      34.2025, 74.3450),
    # Tertiary hospitals (Srinagar metropolitan)
    ("SKIMS Soura",                    34.1308, 74.8472),
    ("SMHS Hospital Karan Nagar",      34.0842, 74.7956),
    ("Lal Ded Hospital",               34.0822, 74.8059),
    ("Bone & Joint Hospital Barzulla", 34.0539, 74.8095),
    ("JLNM Hospital Rainawari",        34.1019, 74.8311),
    ("GMC Srinagar",                   34.0842, 74.7956),
    # Industrial estates (Kashmir Valley)
    ("Khonmoh Industrial Estate",      34.0419, 74.8825),
    ("Rangreth Industrial Estate",     34.0244, 74.7906),
    ("Lassipora Industrial Pulwama",   33.8569, 74.9156),
    # District-HQ hospitals (lifeline routes)
    ("DH Pulwama",                     33.8716, 74.8983),
    ("DH Ganderbal",                   34.2275, 74.7775),
    ("DH Budgam",                      33.9908, 74.7115),
    ("DH Anantnag",                    33.7311, 75.1497),
]

# Sheet 1 column layout (Groups A / B / C) — v2 adds Route_Type
SHEET1_GROUP_A = ["New_Route_ID", "Route_Name", "Action_Taken", "Route_KM",
                  "Route_Type", "Social_Flag"]
SHEET1_GROUP_B = ["Priority_Band", "Headway_Min", "Cycle_Time_Min",
                  "Fleet_Required", "HPV_Count", "MPV_Count",
                  "CMP_Trunk"]
SHEET1_GROUP_C = ["Pop_Score", "POI_Score", "Road_Multiplier", "Final_CDI",
                  "Population_Served", "Population_Served_Pct",
                  "OSRM_Duration_S", "Sharp_Turns",
                  "Junction_Penalty_Min", "Congestion_Zone",
                  "N_Stops_Estimated", "Stop_Penalty_Min"]
SHEET1_ALL_COLS = SHEET1_GROUP_A + SHEET1_GROUP_B + SHEET1_GROUP_C

TERMINAL_CATEGORIES = frozenset({"bus_terminal", "market"})

# ─── SSCL / CHALO: 30 Official Srinagar Smart City E-Bus Routes ─────────────
# Source: SSCL_Data_Updated.xlsx, "Route Wise deployed Buses" sheet (Apr 2026)
# Total fleet deployed: 98 buses (73 × 9-metre + 25 × 12-metre)
# These 30 routes are injected as UPGRADED_TO_TRUNK/HP before Step 4.
# Headway is fixed at SSCL_TRUNK_HEADWAY_MIN (15 min) — matches the SSCL
# operational target of 25-min stop-to-stop frequency and Srinagar's
# observed peak demand (~4,346 pax/hr citywide at 9 AM from CHALO data).
# 12-metre buses (HPV) are deployed on long-haul / inter-district routes;
# 9-metre buses (MPV) cover intra-city loops. The 85/15 HPV-MPV split in
# Step 9 reflects this real deployment ratio.
SSCL_TRUNK_HEADWAY_MIN = 15   # SSCL e-bus trunk headway (was 10 for Jammu BRT)

# Alias for backward compatibility with downstream functions that reference
# CMP_TRUNK_HEADWAY_MIN (no need to rename across the entire codebase).
CMP_TRUNK_HEADWAY_MIN  = SSCL_TRUNK_HEADWAY_MIN

# Each route carries:
#   id     — SSCL route ID (SSCL-01 … SSCL-30)
#   origin — start terminal (used for fuzzy match against dataset)
#   dest   — end terminal
#   km     — approximate route length (used as fallback when OSRM fails)
#   fleet  — buses deployed (from CHALO data, for audit only)
#   bus_9m — 9m bus count (MPV-equivalent)
#   bus_12m — 12m bus count (HPV-equivalent)
CMP_TRUNK_ROUTES: List[Dict] = [
    {"id": "SSCL-01", "origin": "Parimpora",       "dest": "Harwan",                      "km": 18, "fleet": 7, "bus_9m": 7, "bus_12m": 0},
    {"id": "SSCL-02", "origin": "Batamaloo",       "dest": "Nasrullah Pora",              "km": 12, "fleet": 5, "bus_9m": 5, "bus_12m": 0},
    {"id": "SSCL-03", "origin": "Batamaloo",       "dest": "Hazratbal",                   "km": 10, "fleet": 6, "bus_9m": 6, "bus_12m": 0},
    {"id": "SSCL-04", "origin": "Batamaloo",       "dest": "Chadoora Chowk",              "km": 13, "fleet": 3, "bus_9m": 3, "bus_12m": 0},
    {"id": "SSCL-05", "origin": "LD Hospital",     "dest": "Pandach",                     "km": 11, "fleet": 4, "bus_9m": 4, "bus_12m": 0},
    {"id": "SSCL-06", "origin": "Pantha Chowk",    "dest": "Narbal Crossing",             "km": 22, "fleet": 2, "bus_9m": 0, "bus_12m": 2},
    {"id": "SSCL-07", "origin": "Batamaloo",       "dest": "Drussu Pulwama",              "km": 28, "fleet": 4, "bus_9m": 0, "bus_12m": 4},
    {"id": "SSCL-08", "origin": "Batamaloo",       "dest": "Budgam Railway Station",      "km": 14, "fleet": 4, "bus_9m": 4, "bus_12m": 0},
    {"id": "SSCL-09", "origin": "Parimpora",       "dest": "Naseem Bagh",                 "km":  9, "fleet": 4, "bus_9m": 4, "bus_12m": 0},
    {"id": "SSCL-10", "origin": "Pantha Chowk",    "dest": "Agri Kalan Kanihama",         "km": 24, "fleet": 5, "bus_9m": 0, "bus_12m": 5},
    {"id": "SSCL-11", "origin": "Old City",        "dest": "Old City Loop",               "km":  8, "fleet": 1, "bus_9m": 1, "bus_12m": 0},
    {"id": "SSCL-12", "origin": "Rangreth",        "dest": "District Court Srinagar",     "km": 11, "fleet": 3, "bus_9m": 3, "bus_12m": 0},
    {"id": "SSCL-13", "origin": "Batamaloo",       "dest": "Beehama Ganderbal",           "km": 25, "fleet": 4, "bus_9m": 4, "bus_12m": 0},
    {"id": "SSCL-14", "origin": "TRC",             "dest": "Central University Ganderbal","km": 28, "fleet": 6, "bus_9m": 6, "bus_12m": 0},
    {"id": "SSCL-15", "origin": "TRC",             "dest": "Pulwama",                     "km": 32, "fleet": 4, "bus_9m": 4, "bus_12m": 0},
    {"id": "SSCL-16", "origin": "Batamaloo",       "dest": "Khonmoh",                     "km": 15, "fleet": 2, "bus_9m": 2, "bus_12m": 0},
    {"id": "SSCL-17", "origin": "Batamaloo",       "dest": "Womens College Batpora",      "km":  7, "fleet": 2, "bus_9m": 2, "bus_12m": 0},
    {"id": "SSCL-18", "origin": "Jehangir Chowk",  "dest": "Wadwan",                      "km": 12, "fleet": 2, "bus_9m": 2, "bus_12m": 0},
    {"id": "SSCL-19", "origin": "Pantha Chowk",    "dest": "Sumbal",                      "km": 38, "fleet": 4, "bus_9m": 0, "bus_12m": 4},
    {"id": "SSCL-20", "origin": "Pantha Chowk",    "dest": "Safapora",                    "km": 42, "fleet": 2, "bus_9m": 0, "bus_12m": 2},
    {"id": "SSCL-21", "origin": "Batamaloo",       "dest": "Arath",                       "km": 11, "fleet": 2, "bus_9m": 2, "bus_12m": 0},
    {"id": "SSCL-22", "origin": "Batamaloo",       "dest": "Khrew Bus Stand",             "km": 16, "fleet": 4, "bus_9m": 4, "bus_12m": 0},
    {"id": "SSCL-23", "origin": "Batamaloo",       "dest": "Charesharief",                "km": 28, "fleet": 2, "bus_9m": 2, "bus_12m": 0},
    {"id": "SSCL-24", "origin": "Pantha Chowk",    "dest": "Palhalan",                    "km": 30, "fleet": 6, "bus_9m": 0, "bus_12m": 6},
    {"id": "SSCL-25", "origin": "Batamaloo",       "dest": "Dadsara Tral",                "km": 36, "fleet": 2, "bus_9m": 2, "bus_12m": 0},
    {"id": "SSCL-26", "origin": "Batamaloo",       "dest": "Kangan",                      "km": 35, "fleet": 2, "bus_9m": 2, "bus_12m": 0},
    {"id": "SSCL-27", "origin": "Batamaloo",       "dest": "Manigam",                     "km": 32, "fleet": 2, "bus_9m": 2, "bus_12m": 0},
    {"id": "SSCL-28", "origin": "Batamaloo",       "dest": "Pinglena Pampore",            "km": 22, "fleet": 2, "bus_9m": 0, "bus_12m": 2},
    {"id": "SSCL-29", "origin": "Pantha Chowk",    "dest": "Panzinara",                   "km":  8, "fleet": 1, "bus_9m": 1, "bus_12m": 0},
    {"id": "SSCL-30", "origin": "Batamaloo",       "dest": "DC Office Budgam",            "km": 14, "fleet": 1, "bus_9m": 1, "bus_12m": 0},
]

# Fuzzy-match tolerance: a dataset terminal must score ≥ this similarity ratio
# (0–1) against a CMP terminal to be considered a match.
CMP_FUZZY_THRESHOLD = 0.55   # ~55% character overlap via SequenceMatcher

# Minimum route length to be eligible for Trunk promotion (anti-stranding rule)
TRUNK_MIN_LENGTH_KM = 5.0    # No route < 5 km can be promoted to Trunk

# CDI percentile gate for Trunk eligibility (lowered from 50th to 30th)
TRUNK_CDI_GATE_PERCENTILE = 30   # 30th percentile — aggressive trunk promotion

# Demand multiplier for routes that intersect a CMP backbone trunk corridor
CMP_CONNECTIVITY_BONUS = 1.5  # 1.5× combined demand score for connected routes

COLOUR = {
    "trunk":          "#1A237E",
    "feeder":         "#00695C",
    "regional":       "#6A1B9A",
    "current_net":    "#9E9E9E",
    "catchment_fill": "#80DEEA",
    "catchment_line": "#0097A7",
    "poi_high":       "#D32F2F",
    "poi_secondary":  "#F57F17",
    "start_pin":      "#1B5E20",
    "end_pin":        "#B71C1C",
    "via_dot":        "#5C6BC0",
}
TILE_URL  = "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
TILE_ATTR = "© OpenStreetMap contributors © CARTO"

FG = {
    "heatmap":   "Population Heatmap",
    "trunk":     "Trunk Corridors",
    "feeder":    "Feeder Routes",
    "regional":  "Regional District Routes",
    "original":  "Original Network",
    "hv_poi":    "High Priority POIs",
    "sec_poi":   "Secondary POIs",
    "catchment": "Route Catchments",
    "pins":      "Start End Terminals",
    "via":       "Via Waypoints",
}

# ──────────────────────────────────────────────────────────────────────────────
#  IMPORTS
# ──────────────────────────────────────────────────────────────────────────────
import json
import math
import sys
import time
import logging
import warnings
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd
import geopandas as gpd
import requests
from shapely.geometry import LineString, MultiLineString, Point, shape, mapping
from shapely.ops import unary_union
from shapely.strtree import STRtree
import rasterstats
import folium
from folium.plugins import AntPath, HeatMap
try:
    from folium.plugins import PolyLineTextPath
    _HAS_PLTPATH = True
except ImportError:
    _HAS_PLTPATH = False
import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

try:
    import jenkspy
    _HAS_JENKSPY = True
except ImportError:
    _HAS_JENKSPY = False

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

# ──────────────────────────────────────────────────────────────────────────────
#  LOGGING
# ──────────────────────────────────────────────────────────────────────────────
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("transit_v3.log", mode="w", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
#  PHASE 1  ─  DATA INGESTION
# ══════════════════════════════════════════════════════════════════════════════
def truncate_routes_to_bbox(df: pd.DataFrame) -> pd.DataFrame:
    """
    Truncates routes using a strict latitude/longitude bounding box.
    Any point falling outside the box triggers a cut-off, and the 
    last valid point inside the box becomes the new End Terminal.
    """
    log.info("Truncating routes to strict bounding box (Lat: %s to %s, Lon: %s to %s)…",
             BOUNDS_MIN_LAT, BOUNDS_MAX_LAT, BOUNDS_MIN_LON, BOUNDS_MAX_LON)

    new_rows = []
    dropped_count = 0
    truncated_count = 0

    def _is_inside(lon, lat):
        return (BOUNDS_MIN_LON <= lon <= BOUNDS_MAX_LON) and \
               (BOUNDS_MIN_LAT <= lat <= BOUNDS_MAX_LAT)

    for _, row in df.iterrows():
        start_lon, start_lat = float(row["Start_Lon"]), float(row["Start_Lat"])
        end_lon, end_lat     = float(row["End_Lon"]), float(row["End_Lat"])
        vias                 = parse_via(row.get("Via_Coordinates"))

        # Assemble the full ordered sequence of coordinates
        all_pts = [(start_lon, start_lat)] + vias + [(end_lon, end_lat)]
        valid_pts = []

        # Iterate and cut off at the first point outside the bounding box
        for lon, lat in all_pts:
            if _is_inside(lon, lat):
                valid_pts.append((lon, lat))
            else:
                break  # Hit the boundary! Cut off the rest of the route here.

        # If it started outside the box, or we don't have enough points left to make a line
        if len(valid_pts) < 2:
            log.debug("  Route %s dropped (Started outside bounding box or too short).", row["Route_ID"])
            dropped_count += 1
            continue

        if len(valid_pts) < len(all_pts):
            truncated_count += 1

        # The last valid point inside the box is now the new End Terminal
        row["Start_Lon"], row["Start_Lat"] = valid_pts[0]
        row["End_Lon"], row["End_Lat"]     = valid_pts[-1]

        # Re-pack the remaining middle points into the via JSON format
        new_vias = valid_pts[1:-1]
        if new_vias:
            row["Via_Coordinates"] = json.dumps([{"lat": lat, "lon": lon} for lon, lat in new_vias])
        else:
            row["Via_Coordinates"] = None

        new_rows.append(row)

    log.info("  Bounding Box Truncation: %d routes truncated, %d dropped entirely.", 
             truncated_count, dropped_count)
    
    return pd.DataFrame(new_rows)

def load_routes(path: str) -> pd.DataFrame:
    """
    Load routes CSV with flexible column aliasing.
    All ~700 routes are loaded regardless of length — filtering
    for length is NO LONGER performed here (Directive 1).
    """
    log.info("Loading routes from '%s'", path)
    df = pd.read_csv(path)
    df.columns = df.columns.str.strip().str.replace(" ", "_")
    col_map = {c.lower(): c for c in df.columns}

    def _resolve(targets):
        for k in targets:
            if k in col_map:
                return col_map[k]
        return None

    alias = {
        "Start_Lat":          ["start_lat", "startlat", "origin_lat", "from_lat"],
        "Start_Lon":          ["start_lon", "startlon", "origin_lon", "start_lng",
                               "from_lon"],
        "End_Lat":            ["end_lat",   "endlat",   "dest_lat",   "to_lat"],
        "End_Lon":            ["end_lon",   "endlon",   "dest_lon",   "end_lng",
                               "to_lon"],
        "Via_Coordinates":    ["via_coordinates", "via_coords", "waypoints"],
        "Minibus_Count":      ["minibus_count", "minibuses", "mini_bus_count"],
        "Standard_Bus_Count": ["standard_bus_count", "std_bus", "standard_buses"],
        "Route_Name":         ["route_name", "name", "route"],
    }
    rename = {}
    for canon, targets in alias.items():
        found = _resolve(targets)
        if found and found != canon:
            rename[found] = canon
    df.rename(columns=rename, inplace=True)

    if "Route_ID" not in df.columns:
        df["Route_ID"] = [f"R{i+1:04d}" for i in range(len(df))]
    if "Route_Name" not in df.columns:
        if "Route_From" in df.columns and "Route_To" in df.columns:
            df["Route_Name"] = (df["Route_From"].astype(str) + " ↔ "
                                + df["Route_To"].astype(str))
        else:
            df["Route_Name"] = df["Route_ID"]
    for col, default in [("Minibus_Count", 0), ("Standard_Bus_Count", 0),
                          ("Via_Coordinates", None)]:
        if col not in df.columns:
            df[col] = default

    df["Minibus_Count"]      = (pd.to_numeric(df["Minibus_Count"],
                                               errors="coerce")
                                  .fillna(0).astype(int))
    df["Standard_Bus_Count"] = (pd.to_numeric(df["Standard_Bus_Count"],
                                               errors="coerce")
                                  .fillna(0).astype(int))
    log.info("  Loaded %d routes (no length filter applied — Directive 1).", len(df))
    return df


def load_pois(path: str) -> gpd.GeoDataFrame:
    """
    Load POIs with the Kashmir 3-tier system + women-anchor boost.

    Tier 1 (w=1.0): hospitals, transit hubs, govt offices, mosques, malls
    Tier 2 (w=0.4): colleges, markets, schools, recreation
    Tier 3 (w=0.6 summer / 0.0 winter): tourism, gardens, gondola, shrines
                    Toggled by WINTER_SCENARIO flag.

    Women-anchor categories (girls' colleges, maternity hospitals, women's
    markets) receive a +25% boost on top of their tier weight, calibrated
    to CHALO observation that 64.5% of riders are women (free-fare effect).
    """
    log.info("Loading POIs from '%s' (Kashmir 3-tier + women-anchor boost)…", path)
    df = pd.read_csv(path)

    # Standardise column names to lowercase to handle Capitalised headers
    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")

    # Map 'latitude'/'longitude' to the expected 'lat'/'lon'
    rename_map = {
        "latitude": "lat",
        "longitude": "lon"
    }
    df.rename(columns=rename_map, inplace=True)

    if "category" not in df.columns:
        df["category"] = "Other"
    if "name" not in df.columns:
        df["name"] = df["category"]

    # Assign Kashmir 3-tier weights + women-anchor boost
    def _poi_weight(row) -> float:
        # Priority 1: Use the 'Importance' column if it exists
        base = None
        if "importance" in row and pd.notna(row["importance"]):
            imp = str(row["importance"]).lower().strip()
            if imp == "high":
                base = POI_TIER1_WEIGHT    # 1.0
            elif imp == "seasonal":
                base = POI_TIER3_WEIGHT    # 0.6 summer / 0.0 winter
            elif imp in ["medium", "low"]:
                base = POI_TIER2_WEIGHT    # 0.4

        # Priority 2: Fallback to category-based tier mapping
        if base is None:
            c = str(row["category"]).lower().strip()
            if c in POI_TIER1_CATEGORIES:
                base = POI_TIER1_WEIGHT    # 1.0
            elif c in POI_TIER3_CATEGORIES:
                base = POI_TIER3_WEIGHT    # 0.6 summer / 0.0 winter
            elif c in POI_TIER2_CATEGORIES:
                base = POI_TIER2_WEIGHT    # 0.4
            else:
                base = DEFAULT_POI_WEIGHT_V2

        # Women-anchor boost (+25%) — CHALO calibration
        c = str(row["category"]).lower().strip()
        if c in WOMEN_ANCHOR_CATEGORIES:
            base *= WOMEN_ANCHOR_BOOST

        return base

    # Apply the weight function row-wise
    df["POI_Weight"] = df.apply(_poi_weight, axis=1)

    # Flag high-value POIs for map popups (anything ≥ Tier 1 weight)
    df["Is_HV_POI"] = df["POI_Weight"] >= POI_TIER1_WEIGHT

    # Tier audit
    tier1_n   = (df["POI_Weight"] >= POI_TIER1_WEIGHT).sum()
    tier3_n   = ((df["POI_Weight"] > POI_TIER2_WEIGHT) &
                 (df["POI_Weight"] < POI_TIER1_WEIGHT)).sum()
    tier2_n   = (df["POI_Weight"] <= POI_TIER2_WEIGHT).sum()
    women_n   = df["category"].str.lower().str.strip().isin(
                    WOMEN_ANCHOR_CATEGORIES).sum()
    season    = "WINTER" if WINTER_SCENARIO else "SUMMER"
    log.info("  Loaded %d POIs — T1 (≥1.0): %d  T2 (≤0.4): %d  T3 mid: %d "
             "[scenario=%s, T3 weight=%.2f]",
             len(df), tier1_n, tier2_n, tier3_n, season, POI_TIER3_WEIGHT)
    if women_n:
        log.info("  Women-anchor POIs boosted by %.0f%%: %d",
                 (WOMEN_ANCHOR_BOOST - 1) * 100, women_n)

    gdf = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df["lon"], df["lat"]),
        crs=WGS84_CRS,
    )
    return gdf


def parse_via(via_raw) -> List[Tuple[float, float]]:
    """Parse Via_Coordinates field to list of (lon, lat) tuples."""
    if via_raw is None or (isinstance(via_raw, float) and math.isnan(via_raw)):
        return []
    if not isinstance(via_raw, str) or not via_raw.strip():
        return []
    try:
        pts = json.loads(via_raw)
        result = []
        for p in pts:
            if isinstance(p, dict):
                result.append(
                    (float(p.get("lon", p.get("lng", 0))),
                     float(p.get("lat", 0)))
                )
            elif isinstance(p, (list, tuple)) and len(p) >= 2:
                a, b = float(p[0]), float(p[1])
                result.append((b, a) if 6 <= a <= 40 else (a, b))
        return result
    except (json.JSONDecodeError, TypeError, ValueError):
        return []


def _build_osrm_url(coords: List[Tuple[float, float]]) -> str:
    return (f"{OSRM_BASE_URL}/route/v1/driving/"
            + ";".join(f"{lon},{lat}" for lon, lat in coords)
            + "?overview=full&geometries=geojson&steps=false")


def _fetch_osrm_single(route_id: str, coords: List[Tuple[float, float]]) -> Dict:
    """Fetch a single route from OSRM. Returns dict with geometry and duration."""
    try:
        resp = requests.get(_build_osrm_url(coords), timeout=OSRM_TIMEOUT_S)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") == "Ok" and data.get("routes"):
            r0 = data["routes"][0]
            return {
                "route_id":        route_id,
                "geometry":        shape(r0["geometry"]),
                "osrm_km":         r0["distance"] / 1000.0,
                "osrm_duration_s": float(r0["duration"]),
                "success":         True,
            }
    except Exception as exc:
        log.debug("OSRM failed [%s]: %s", route_id, exc)
    return {"route_id": route_id, "geometry": None, "osrm_km": None,
            "osrm_duration_s": None, "success": False}


def fetch_all_osrm(df: pd.DataFrame) -> Dict[str, Dict]:
    """Concurrent OSRM fetches for all routes."""
    log.info("Fetching OSRM geometries (%d routes, %d workers)…",
             len(df), OSRM_MAX_WORKERS)
    tasks = {}
    for _, row in df.iterrows():
        via = parse_via(row.get("Via_Coordinates"))
        tasks[row["Route_ID"]] = (
            [(float(row["Start_Lon"]), float(row["Start_Lat"]))]
            + via
            + [(float(row["End_Lon"]), float(row["End_Lat"]))]
        )
    results = {}
    with ThreadPoolExecutor(max_workers=OSRM_MAX_WORKERS) as pool:
        futures = {pool.submit(_fetch_osrm_single, rid, coords): rid
                   for rid, coords in tasks.items()}
        for fut in as_completed(futures):
            rid = futures[fut]
            try:
                res = fut.result()
                results[res["route_id"]] = res
            except Exception as exc:
                log.warning("Future error [%s]: %s", rid, exc)
                results[rid] = {"route_id": rid, "geometry": None,
                                "osrm_km": None, "osrm_duration_s": None,
                                "success": False}
    ok = sum(1 for r in results.values() if r["success"])
    log.info("  OSRM: %d/%d ok, %d use circuity fallback.", ok, len(df),
             len(df) - ok)
    return results


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi  = math.radians(lat2 - lat1)
    dlam  = math.radians(lon2 - lon1)
    a = (math.sin(dphi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(a))


def apply_geometries(df: pd.DataFrame, osrm_results: Dict) -> gpd.GeoDataFrame:
    """
    Merge OSRM routing results with the route dataframe.

    DIRECTIVE 1 FIX:
    The v6 hard filter `gdf = gdf[gdf["Route_KM"] <= 60].copy()` has been
    removed entirely. All routes are retained. Instead, a Route_Type column
    is assigned:
      - Urban          : Route_KM < 15
      - Peri_Urban     : 15 ≤ Route_KM < 40
      - Regional_District : Route_KM ≥ 40  (rural lifeline — flagged, not dropped)

    Regional_District routes receive relaxed headway targets in Step 6.
    """
    log.info("Merging geometries — ALL routes retained (Directive 1)…")
    rows = []
    for _, row in df.iterrows():
        rid       = row["Route_ID"]
        res       = osrm_results.get(rid, {})
        via       = parse_via(row.get("Via_Coordinates"))
        raw_coords = (
            [(float(row["Start_Lon"]), float(row["Start_Lat"]))]
            + via
            + [(float(row["End_Lon"]), float(row["End_Lat"]))]
        )
        fallback_geom = LineString(raw_coords) if len(raw_coords) >= 2 else None

        if res.get("success") and res["geometry"] is not None:
            geom       = res["geometry"]
            dist_km    = max(0.0, res["osrm_km"])
            duration_s = max(0.0, res["osrm_duration_s"])
            source     = "OSRM"
        else:
            geom    = fallback_geom
            sl_km   = _haversine_km(
                float(row["Start_Lat"]), float(row["Start_Lon"]),
                float(row["End_Lat"]),   float(row["End_Lon"]))
            crosses = (float(row["Start_Lon"]) < TAWI_RIVER_LON) != \
                      (float(row["End_Lon"])   < TAWI_RIVER_LON)
            cf      = CIRCUITY_FACTOR_RIVER if crosses else CIRCUITY_FACTOR
            dist_km = sl_km * cf

            start_lat = float(row["Start_Lat"])
            end_lat   = float(row["End_Lat"])
            # Kashmir-specific speed zones:
            #  - Both terminals in Downtown Srinagar (lat > 34.07) → old-city speed
            #  - Both terminals on valley periphery (lat < 34.00) → highway speed
            #  - Otherwise mixed corridor → default suburban speed
            if start_lat > CITY_CORE_LAT_THRESHOLD and end_lat > CITY_CORE_LAT_THRESHOLD:
                local_speed = SPEED_OLD_CITY_KMH
            elif start_lat < 34.00 and end_lat < 34.00:
                local_speed = SPEED_VALLEY_HIGHWAY_KMH
            else:
                local_speed = SPEED_DEFAULT_KMH

            duration_s = (dist_km / local_speed) * 3600.0
            source     = "Circuity-River" if crosses else "Circuity"

        # DIRECTIVE 1: Classify route type — no dropping
        km = max(0.0, dist_km)
        if km < URBAN_KM_THRESHOLD:
            route_type = "Urban"
        elif km < PERIURBAN_KM_THRESHOLD:
            route_type = "Peri_Urban"
        else:
            route_type = "Regional_District"

        rows.append({**row.to_dict(),
                     "geometry":        geom,
                     "Route_KM":        round(km, 3),
                     "OSRM_Duration_S": round(max(0.0, duration_s), 1),
                     "Geo_Source":      source,
                     "Route_Type":      route_type})

    gdf  = gpd.GeoDataFrame(rows, geometry="geometry", crs=WGS84_CRS)
    n0   = len(gdf)
    # Only drop null geometry and sub-minimum length routes
    gdf  = gdf[gdf.geometry.notna()].copy()
    gdf  = gdf[gdf["Route_KM"] >= MIN_ROUTE_KM].copy()

    # Count route types for audit
    type_counts = gdf["Route_Type"].value_counts().to_dict()
    log.info("  Directive 1 — Route type breakdown after geometry: "
             "Urban=%d  Peri_Urban=%d  Regional_District=%d  (total=%d, dropped=%d for "
             "null geometry or sub-1km)",
             type_counts.get("Urban", 0),
             type_counts.get("Peri_Urban", 0),
             type_counts.get("Regional_District", 0),
             len(gdf), n0 - len(gdf))
    return gdf.reset_index(drop=True)


def impute_fleet(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Impute existing fleet sizes for context only. Not used in Step 8."""
    log.info("Imputing existing fleet sizes for context…")
    gdf = gdf.copy()
    gdf["Total_Minibuses_Existing"] = (
        gdf["Minibus_Count"] + gdf["Standard_Bus_Count"] * STD_TO_MINI_RATIO
    ).round(1).clip(lower=0)

    mask = gdf["Total_Minibuses_Existing"] == 0

    def _ghost_fleet(km):
        cycle = (km * 2 / SPEED_DEFAULT_KMH) * 60
        return max(1, math.ceil(cycle / 60))

    gdf.loc[mask, "Total_Minibuses_Existing"] = gdf.loc[mask, "Route_KM"].apply(
        _ghost_fleet)
    log.info("  Fleet imputed for %d zero-bus routes (context only).", mask.sum())
    return gdf


# ══════════════════════════════════════════════════════════════════════════════
#  CMP TRUNK INJECTION  ─  Pre-classification override for 13 CMP Table 4.2 routes
# ══════════════════════════════════════════════════════════════════════════════

def _fuzzy_match_score(a: str, b: str) -> float:
    """
    Return SequenceMatcher similarity ratio (0–1) between two terminal name strings.
    Both strings are lowercased and stripped before comparison so that minor
    capitalisation/punctuation differences do not reduce match quality.
    """
    from difflib import SequenceMatcher
    a_clean = a.lower().strip()
    b_clean = b.lower().strip()
    return SequenceMatcher(None, a_clean, b_clean).ratio()


def _terminal_matches_cmp(dataset_terminal: str, cmp_terminal: str) -> bool:
    """
    Returns True if `dataset_terminal` fuzzy-matches `cmp_terminal` above the
    CMP_FUZZY_THRESHOLD.  Also returns True if the CMP terminal name appears
    as a substring inside the dataset terminal name (case-insensitive) —
    this catches common abbreviations (e.g. "BC Road Bus Stand" ↔ "B.C. Road Bus Terminal").
    """
    score  = _fuzzy_match_score(dataset_terminal, cmp_terminal)
    substr = cmp_terminal.lower().strip() in dataset_terminal.lower().strip()
    return score >= CMP_FUZZY_THRESHOLD or substr


def inject_cmp_trunk_routes(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Pre-classification SSCL E-Bus Backbone Injection.

    For each of the 30 SSCL routes (from CHALO Apr 2026 data), this function
    scans the dataset for routes whose origin–destination pair fuzzy-matches
    the SSCL terminals (using SequenceMatcher with CMP_FUZZY_THRESHOLD = 0.55).

    On a match:
      • Action_Taken   → "UPGRADED_TO_TRUNK"
      • Priority_Band  → "HP"
      • CMP_Trunk      → True            (legacy flag name; means SSCL trunk)
      • CMP_Route_ID   → e.g. "SSCL-01"  (audit trail)

    Headway for matched routes is hardcoded to SSCL_TRUNK_HEADWAY_MIN (15 min)
    in step6_assign_headways() via the CMP_Trunk flag — matches actual SSCL
    operational targets, not the Jammu BRT 10-min assumption.

    Note: in this Kashmir fork the "CMP_*" column names are retained for
    backward compatibility with downstream functions (QC, export, mapping)
    but the underlying data is SSCL e-bus routes, NOT RITES CMP routes.

    This function must be called AFTER apply_geometries() and BEFORE
    classify_routes().
    """
    log.info("SSCL Injection: scanning dataset against %d SSCL e-bus trunk routes "
             "(from CHALO data)…", len(CMP_TRUNK_ROUTES))
    gdf = gdf.copy()

    # Ensure marker columns exist
    if "CMP_Trunk" not in gdf.columns:
        gdf["CMP_Trunk"]    = False
    if "CMP_Route_ID" not in gdf.columns:
        gdf["CMP_Route_ID"] = ""
    if "Priority_Band" not in gdf.columns:
        gdf["Priority_Band"] = ""
    if "Action_Taken" not in gdf.columns:
        gdf["Action_Taken"] = "RETAINED_AS_FEEDER"

    # Build terminal name series — prefer dedicated terminal columns if present,
    # fall back to Route_Name parsing.
    def _get_terminal(row, end: str) -> str:
        col = f"{'Start' if end == 'start' else 'End'}_Terminal"
        if col in row.index and pd.notna(row[col]) and str(row[col]).strip():
            return str(row[col]).strip()
        # Fallback: parse from Route_Name "A to B" pattern
        name = str(row.get("Route_Name", ""))
        parts = [p.strip() for p in name.lower().split(" to ")]
        if end == "start" and len(parts) >= 1:
            return parts[0]
        if end == "end"   and len(parts) >= 2:
            return parts[-1]
        return name

    matched_total = 0
    for cmp_route in CMP_TRUNK_ROUTES:
        cmp_origin = cmp_route["origin"]
        cmp_dest   = cmp_route["dest"]
        cmp_id     = cmp_route["id"]

        matched_idx = []
        for idx, row in gdf.iterrows():
            ds_start = _get_terminal(row, "start")
            ds_end   = _get_terminal(row, "end")

            # Check both directions (route may be stored A→B or B→A)
            fwd = (_terminal_matches_cmp(ds_start, cmp_origin) and
                   _terminal_matches_cmp(ds_end,   cmp_dest))
            rev = (_terminal_matches_cmp(ds_start, cmp_dest) and
                   _terminal_matches_cmp(ds_end,   cmp_origin))
            if fwd or rev:
                matched_idx.append(idx)

        if matched_idx:
            for idx in matched_idx:
                gdf.at[idx, "Action_Taken"]  = "UPGRADED_TO_TRUNK"
                gdf.at[idx, "Priority_Band"] = "HP"
                gdf.at[idx, "CMP_Trunk"]     = True
                gdf.at[idx, "CMP_Route_ID"]  = cmp_id
            log.info("  ✓ CMP %s (%s → %s): matched %d dataset route(s) — forced TRUNK/HP.",
                     cmp_id, cmp_origin, cmp_dest, len(matched_idx))
            matched_total += len(matched_idx)
        else:
            log.warning("  ⚠ CMP %s (%s → %s): NO dataset match found at "
                        "threshold=%.2f.  Route absent from dataset.",
                        cmp_id, cmp_origin, cmp_dest, CMP_FUZZY_THRESHOLD)

    log.info("SSCL Injection complete: %d dataset routes forcibly upgraded to TRUNK/HP.",
             matched_total)
    return gdf


# ══════════════════════════════════════════════════════════════════════════════
#  PHASE 2  ─  SPATIAL ANALYSIS: CATCHMENTS, POPULATION, POIs, JUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def _pts_along_line(geom: LineString, spacing_m: float) -> List[Point]:
    length = geom.length
    if length < spacing_m:
        return [geom.interpolate(0.5, normalized=True)]
    return [geom.interpolate(d) for d in np.arange(0, length + spacing_m, spacing_m)
            if d <= length]


def build_catchments(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    log.info("Building walk catchments (stop spacing=%dm, walk radius=%dm)…",
             VIRTUAL_STOP_SPACING_M, WALK_CATCHMENT_M)
    gdf_utm = gdf.to_crs(UTM_CRS).copy()
    gdf_utm.geometry = gdf_utm.geometry.simplify(SIMPLIFY_TOL_M)
    catchments = []
    for geom in gdf_utm.geometry:
        pts  = _pts_along_line(geom, VIRTUAL_STOP_SPACING_M)
        poly = unary_union([p.buffer(WALK_CATCHMENT_M) for p in pts])
        catchments.append(poly)
    gdf_utm["_catch"] = catchments
    catch_series = (
        gdf_utm.set_geometry("_catch")
               .set_crs(UTM_CRS)
               .to_crs(WGS84_CRS)["_catch"]
    )
    gdf["Catchment"] = catch_series.values
    log.info("  Catchments built for %d routes.", len(gdf))
    return gdf


def _read_raster_nodata(raster_path: str) -> Optional[float]:
    try:
        import rasterio
        with rasterio.open(raster_path) as src:
            return src.nodata
    except Exception:
        return -9999.0


def compute_population(gdf: gpd.GeoDataFrame, raster_path: str) -> gpd.GeoDataFrame:
    """
    Per-route population from WorldPop raster using catchment polygons.

    KASHMIR-FORK NOTE:
    Raw raster counts are converted to a percentage of the Srinagar UA + Valley
    study-area population for the reference year (CMP_REFERENCE_YEAR = 2024,
    total = 1,660,000 — projection from Census 2011 + SMC Master Plan).
    Replaces the Jammu CMP 1,653,873 baseline from the original engine.
    The walkshed used for the catchment polygon is contracted in winter mode
    (WALK_CATCHMENT_M scaled by WINTER_WALKSHED_SHRINK).

    New columns added:
      Population_Served      — raw raster head-count (unchanged, for audit)
      Population_Served_Pct  — % of Srinagar 2024 study-area population served
    """
    log.info("Computing per-route population from raster: %s", raster_path)
    log.info("  CMP reference: Year=%d  Total study-area population=%s",
             CMP_REFERENCE_YEAR, f"{CMP_TOTAL_POPULATION:,}")

    if not Path(raster_path).exists():
        log.warning("  Raster not found — Population_Served = 0 / Pct = 0.00%%.")
        gdf["Population_Served"]     = 0
        gdf["Population_Served_Pct"] = 0.0
        return gdf

    nodata    = _read_raster_nodata(raster_path)
    catch_gdf = gpd.GeoDataFrame(
        gdf[["Route_ID"]], geometry=gdf["Catchment"], crs=WGS84_CRS)
    stats     = rasterstats.zonal_stats(
        catch_gdf, raster_path, stats=["sum"], nodata=nodata, geojson_out=False)

    raw_counts = [
        min(2_000_000, max(0, int(s["sum"]))) if s.get("sum") is not None else 0
        for s in stats
    ]
    gdf["Population_Served"] = raw_counts

    # Convert to % of CMP 2024 total — capped at 100% to guard against raster overcount
    gdf["Population_Served_Pct"] = (
        (gdf["Population_Served"] / CMP_TOTAL_POPULATION * 100)
        .clip(upper=100.0)
        .round(4)
    )

    log.info("  Population_Served     — max raw count : %s",
             f"{gdf['Population_Served'].max():,}")
    log.info("  Population_Served_Pct — max: %.2f%%  mean: %.2f%%  "
             "(denominator: CMP %d total = %s)",
             gdf["Population_Served_Pct"].max(),
             gdf["Population_Served_Pct"].mean(),
             CMP_REFERENCE_YEAR,
             f"{CMP_TOTAL_POPULATION:,}")
    return gdf


def compute_network_population_total(gdf: gpd.GeoDataFrame,
                                      raster_path: str) -> int:
    """Deduplicated network population via dissolved catchment union."""
    log.info("Computing deduplicated network population (dissolved union)…")
    if not Path(raster_path).exists():
        return int(gdf["Population_Served"].max())
    valid     = [c for c in gdf["Catchment"]
                 if c is not None and hasattr(c, "is_empty") and not c.is_empty]
    if not valid:
        return 0
    dissolved = unary_union(valid)
    nodata    = _read_raster_nodata(raster_path)
    stats     = rasterstats.zonal_stats(
        [dissolved], raster_path, stats=["sum"], nodata=nodata, geojson_out=False)
    val    = stats[0].get("sum") if stats else None
    result = min(2_000_000, max(0, int(val))) if val is not None else 0
    pct    = min(100.0, result / CMP_TOTAL_POPULATION * 100) if CMP_TOTAL_POPULATION else 0.0
    log.info("  Deduplicated network population: %s  (%.2f%% of CMP %d total: %s)",
             f"{result:,}", pct, CMP_REFERENCE_YEAR, f"{CMP_TOTAL_POPULATION:,}")
    return result


def count_weighted_poi_scores(gdf_routes: gpd.GeoDataFrame,
                               gdf_pois:   gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Step 2 preparation: raw weighted POI score per route.

    DIRECTIVE 5 FIX (POI weights):
    v6 used a 4-tier system (weights: 1, 3, 6, 10) which compressed the
    signal — all scores ended up within a narrow band, making Tier-3 clinics
    nearly as valuable as Tier-1 hospitals for demand modelling.

    v2 uses a binary 2-tier system:
      Tier 1 (w=1.0): Hospitals, Transit hubs, Malls, Major shrines,
                       Industrial estates, Migrant townships
      Tier 2 (w=0.2): Colleges, Markets, Military, Clinics, Schools,
                       Govt offices

    POI_Score_Raw = Σ(tier_weight_i for POIs within 250m) / Route_KM
    """
    log.info("Counting POI weighted scores (250m buffer, 2-tier weights "
             "per Directive 5)…")

    gdf_pois_w       = gdf_pois.copy()
    # POI_Weight already assigned in load_pois()
    gdf_pois_w["_w"] = gdf_pois_w["POI_Weight"]
    gdf_pois_w["_hv"] = gdf_pois_w["Is_HV_POI"].astype(int)

    r_utm         = gdf_routes.to_crs(UTM_CRS).copy()
    r_utm["_buf"] = r_utm.geometry.simplify(SIMPLIFY_TOL_M).buffer(POI_BUFFER_M)
    buf_gdf       = r_utm[["Route_ID", "_buf"]].set_geometry("_buf")

    p_utm  = gdf_pois_w[["_w", "_hv", "geometry"]].to_crs(UTM_CRS)
    joined = gpd.sjoin(p_utm, buf_gdf, how="inner", predicate="within")

    weight_sums = joined.groupby("Route_ID")["_w"].sum()
    hv_counts   = joined.groupby("Route_ID")["_hv"].sum()
    route_km    = (gdf_routes.set_index("Route_ID")["Route_KM"]
                   .clip(lower=GRAVITY_EPSILON))

    gdf_routes["_poi_weight_sum"] = (gdf_routes["Route_ID"]
                                     .map(weight_sums).fillna(0.0))
    gdf_routes["POI_Score_Raw"]   = (gdf_routes["_poi_weight_sum"]
                                     / route_km.values).clip(lower=0.0)
    gdf_routes["HV_POI_Count"]    = (gdf_routes["Route_ID"]
                                     .map(hv_counts).fillna(0).astype(int))
    gdf_routes.drop(columns=["_poi_weight_sum"], inplace=True)

    log.info("  POI raw score mean: %.4f  max: %.4f",
             gdf_routes["POI_Score_Raw"].mean(),
             gdf_routes["POI_Score_Raw"].max())
    return gdf_routes


def _deflection_deg(A, B, C) -> float:
    ba = (A[0] - B[0], A[1] - B[1])
    bc = (C[0] - B[0], C[1] - B[1])
    mag_ba, mag_bc = math.hypot(*ba), math.hypot(*bc)
    if mag_ba < 1e-6 or mag_bc < 1e-6:
        return 0.0
    cos_t = max(-1.0, min(1.0,
                (ba[0]*bc[0] + ba[1]*bc[1]) / (mag_ba * mag_bc)))
    return 180.0 - math.degrees(math.acos(cos_t))


def compute_junction_penalties(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Junction_Penalty_Min = Sharp_Turns × 0.5 min per turn > 75°."""
    log.info("Computing junction penalties (threshold=%d°, %.1f min/turn)…",
             SHARP_TURN_DEG, JUNCTION_PENALTY_PER_TURN_MIN)
    gdf_utm = gdf.to_crs(UTM_CRS).copy()
    gdf_utm.geometry = gdf_utm.geometry.simplify(SIMPLIFY_TOL_M)
    n_sharp_list, penalty_list = [], []
    for geom in gdf_utm.geometry:
        if geom is None or geom.is_empty:
            n_sharp_list.append(0)
            penalty_list.append(0.0)
            continue
        coords  = list(geom.coords)
        n_sharp = sum(
            1 for i in range(1, len(coords) - 1)
            if _deflection_deg(coords[i-1], coords[i], coords[i+1]) > SHARP_TURN_DEG
        )
        n_sharp_list.append(n_sharp)
        penalty_list.append(float(n_sharp * JUNCTION_PENALTY_PER_TURN_MIN))
    gdf["Sharp_Turns"]          = n_sharp_list
    gdf["Junction_Penalty_Min"] = penalty_list
    log.info("  %d routes have junction penalties.",
             sum(1 for p in penalty_list if p > 0))
    return gdf


def _detect_congestion_zone(start_lat: float, end_lat: float) -> Tuple[str, float]:
    """
    DIRECTIVE 2 — Congestion zone detection.

    Decision rule:
      If EITHER terminal is in the old city core (lat > 32.72), the route
      encounters city-core congestion at least at one end → apply 2.0×.
      Otherwise → peri-urban 1.5×.

    Returns (zone_label, multiplier).
    """
    if start_lat > CITY_CORE_LAT_THRESHOLD or end_lat > CITY_CORE_LAT_THRESHOLD:
        return "City_Core", CONGESTION_CITY_CORE
    return "Peri_Urban", CONGESTION_PERI_URBAN


def compute_cycle_times(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Step 7: Realistic Cycle Time (Directive 2 — complete rewrite from v6).

    v6 formula (WRONG):
      Cycle = (OSRM_s / 60 + Junction_Penalty) × 2 × 1.15
      Problem: OSRM seconds = midnight free-flow. On a 30km route, this
               produces a 40-min cycle time and a 2-bus allocation — a
               spreadsheet fantasy.

    v2 formula (CORRECT):
      One_Way_Time = (OSRM_Base_Min × Congestion_Multiplier)
                     + (N_Stops × Stop_Penalty_Min)
                     + Junction_Penalty_Min
      Cycle_Time   = One_Way_Time × 2 × Terminal_Layover_Factor (1.10)

    Where:
      • OSRM_Base_Min        = OSRM_Duration_S / 60
      • Congestion_Multiplier = 2.0 (city core, lat > 32.72) or 1.5 (peri-urban)
      • N_Stops               = Route_KM × 1000 / STOP_SPACING_M  (every 500m)
      • Stop_Penalty_Min      = 1.5 min per stop (boarding + alighting dwell)
      • Junction_Penalty_Min  = from compute_junction_penalties() (unchanged)
      • Terminal_Layover      = 1.10 (10%) — covers driver rest + schedule recovery

    Audit columns added: Congestion_Zone, N_Stops_Estimated, Stop_Penalty_Min
    """
    log.info("Step 7: Computing REALISTIC cycle times (Directive 2)…")
    log.info("  Congestion: City_Core=%.1f×  Peri_Urban=%.1f×",
             CONGESTION_CITY_CORE, CONGESTION_PERI_URBAN)
    log.info("  Stop spacing=%dm, penalty=%.1f min/stop, "
             "layover buffer=%.0f%%",
             STOP_SPACING_M, STOP_PENALTY_MIN,
             (TERMINAL_LAYOVER_FACTOR - 1) * 100)

    zones, n_stops_list, stop_penalties, cycle_times = [], [], [], []

    for _, row in gdf.iterrows():
        start_lat = float(row.get("Start_Lat", 0.0))
        end_lat   = float(row.get("End_Lat",   0.0))
        osrm_min  = float(row["OSRM_Duration_S"]) / 60.0
        junc_pen  = float(row["Junction_Penalty_Min"])
        route_km  = float(row["Route_KM"])

        # Congestion zone (Directive 2)
        zone, cong_mult = _detect_congestion_zone(start_lat, end_lat)

        # Stop penalty: one stop every STOP_SPACING_M metres
        n_stops    = max(1, int((route_km * 1000) / STOP_SPACING_M))
        stop_pen   = n_stops * STOP_PENALTY_MIN

        # One-way travel time (congestion-adjusted + stops + junctions)
        one_way = (osrm_min * cong_mult) + stop_pen + junc_pen

        # Round-trip + terminal layover buffer
        cycle = one_way * 2 * TERMINAL_LAYOVER_FACTOR

        zones.append(zone)
        n_stops_list.append(n_stops)
        stop_penalties.append(round(stop_pen, 1))
        cycle_times.append(round(max(1.0, cycle), 1))

    gdf = gdf.copy()
    gdf["Congestion_Zone"]    = zones
    gdf["N_Stops_Estimated"]  = n_stops_list
    gdf["Stop_Penalty_Min"]   = stop_penalties
    gdf["Cycle_Time_Min"]     = cycle_times

    city_core_n  = gdf["Congestion_Zone"].eq("City_Core").sum()
    periurban_n  = gdf["Congestion_Zone"].eq("Peri_Urban").sum()
    log.info("  Zone split — City_Core: %d  Peri_Urban: %d",
             city_core_n, periurban_n)
    log.info("  Cycle_Time_Min — mean: %.1f  max: %.1f  min: %.1f",
             gdf["Cycle_Time_Min"].mean(),
             gdf["Cycle_Time_Min"].max(),
             gdf["Cycle_Time_Min"].min())
    return gdf


# ══════════════════════════════════════════════════════════════════════════════
#  STEPS 1 & 2  ─  NORMALISED DEMAND SCORES
# ══════════════════════════════════════════════════════════════════════════════

def step1_normalise_population_score(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Step 1: Pop_Score (0–1 normalised population density per route).

    CMP INTEGRATION — percentage-based scoring (Chapter 3, RITES Ltd.):
    Raw head-counts are replaced by Population_Served_Pct (% of CMP 2024 total
    = 16,53,873).  This grounds the score in the CMP demand framework:
      • A route serving 3.0% of the study area (≈49,616 residents) is scored
        relative to the highest-serving route in the dataset.
      • The 95th-percentile cap (Directive 5) is applied to the percentage
        density (Pct / Route_KM), preventing a single hyper-dense corridor
        from compressing scores across the network — same logic as before,
        now in CMP-percentage space.

    DIRECTIVE 5 FIX (population cap) — still fully active:
    v6 normalised against the raw maximum, meaning one ultra-dense ward
    mathematically suppressed the CDI of all other routes.  The 95th-pct
    cap prevents that outlier effect; routes above the cap clip to 1.0.

    Columns used:  Population_Served_Pct  (set by compute_population)
    Column set:    Pop_Score              (0–1, used in CDI formula)
    """
    log.info("Step 1: Normalising population score from CMP %d percentages "
             "(0–1, %dth pct density cap — Directive 5)…",
             CMP_REFERENCE_YEAR, POP_CAP_PERCENTILE)

    if "Population_Served_Pct" not in gdf.columns or gdf["Population_Served_Pct"].sum() == 0:
        log.warning("  Population_Served_Pct missing or all-zero — "
                    "falling back to raw Population_Served for scoring.")
        pop_series = gdf["Population_Served"]
    else:
        pop_series = gdf["Population_Served_Pct"]

    # Percentage density: pct of CMP population per km of route
    # (normalises for route length so a 2km stub through a dense ward
    #  doesn't automatically outrank a 20km trunk serving the same zone)
    raw = (pop_series / gdf["Route_KM"].clip(lower=GRAVITY_EPSILON)).clip(lower=0)

    # Directive 5: Cap at 95th percentile of the percentage-density distribution
    cap_val    = float(np.percentile(raw, POP_CAP_PERCENTILE))
    raw_capped = raw.clip(upper=cap_val)

    log.info("  Pct-density 95th pct cap = %.4f %%/km  (raw max was %.4f %%/km)",
             cap_val, raw.max())

    n_capped = (raw > cap_val).sum()
    if n_capped:
        log.info("  %d routes capped at density ceiling (Pop_Score clipped to 1.0).",
                 n_capped)

    min_val = raw_capped.min()
    max_val = raw_capped.max()
    if max_val > min_val:
        gdf["Pop_Score"] = ((raw_capped - min_val) / (max_val - min_val)).round(4)
    else:
        gdf["Pop_Score"] = 0.5
        log.warning("  All routes have equal pct-density — assigning Pop_Score = 0.5.")

    log.info("  Pop_Score mean: %.4f  max: %.4f  "
             "(based on %% of CMP %d study-area population)",
             gdf["Pop_Score"].mean(), gdf["Pop_Score"].max(), CMP_REFERENCE_YEAR)
    return gdf


def step2_normalise_poi_score(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Step 2: POI_Score (0–1 normalised weighted POI gravity per route).
    POI weights are the 2-tier system from load_pois() / count_weighted_poi_scores().
    """
    log.info("Step 2: Normalising POI gravity score (0–1, 2-tier weights)…")
    raw     = gdf["POI_Score_Raw"].clip(lower=0)
    min_val = raw.min()
    max_val = raw.max()
    if max_val > min_val:
        gdf["POI_Score"] = ((raw - min_val) / (max_val - min_val)).round(4)
    else:
        gdf["POI_Score"] = 0.5
        log.warning("  All routes have equal POI_Score_raw — assigning 0.5.")
    log.info("  POI_Score mean: %.4f  max: %.4f",
             gdf["POI_Score"].mean(), gdf["POI_Score"].max())
    return gdf


# ══════════════════════════════════════════════════════════════════════════════
#  PHASE 2b  ─  CORRIDOR FREQUENCY, CLUSTERING & ROUTE CLASSIFICATION
# ══════════════════════════════════════════════════════════════════════════════
def apportion_route_population(gdf: gpd.GeoDataFrame, freq_scores: np.ndarray) -> gpd.GeoDataFrame:
    """
    Divides a route's catchment population by the number of competing routes 
    sharing its corridor. This genuinely fixes the double-counting in Excel sums 
    by assigning 'Market Share' rather than absolute catchment.
    """
    log.info("Apportioning population among overlapping routes (Competitive Market Share)…")
    gdf = gdf.copy()
    
    # freq_scores = number of OTHER overlapping routes. 
    # Total routes sharing the market = freq_scores + 1
    competitors = freq_scores + 1
    
    # Preserve the raw density for the logs, but overwrite the main column for Excel
    gdf["Population_Served_Raw"] = gdf["Population_Served"] 
    gdf["Population_Served"] = (gdf["Population_Served"] / competitors).astype(int)
    
    log.info("  Apportioned Population_Served. New naive sum: %s (much closer to deduplicated reality)", 
             f"{gdf['Population_Served'].sum():,}")
    return gdf

def compute_frequency_scores(gdf: gpd.GeoDataFrame) -> np.ndarray:
    log.info("Computing corridor frequency scores (STRtree)…")
    gdf_utm = gdf.to_crs(UTM_CRS).copy()
    gdf_utm.geometry = gdf_utm.geometry.simplify(SIMPLIFY_TOL_M)
    bufs   = [g.buffer(OVERLAP_BUFFER_M) for g in gdf_utm.geometry]
    tree   = STRtree(bufs)
    scores = np.zeros(len(bufs), dtype=int)
    for i, buf_i in enumerate(bufs):
        candidates = tree.query(buf_i)
        scores[i]  = sum(
            1 for j in candidates if j != i and bufs[j].intersects(buf_i))
    log.info("  Frequency scores — mean: %.1f  max: %d",
             scores.mean(), scores.max())
    return scores


def compute_overlap_matrix(gdf: gpd.GeoDataFrame) -> np.ndarray:
    log.info("Computing pairwise overlap matrix (Multiprocessed)…")
    gdf_utm = gdf.to_crs(UTM_CRS).copy()

    # 1. VECTORIZATION: Use GeoPandas built-in C-level methods instead of Python loops
    log.info("  Simplifying and buffering geometries at C-level...")
    geom_series = gdf_utm.geometry.simplify(SIMPLIFY_TOL_M * 2)
    geom_series = geom_series.buffer(OVERLAP_BUFFER_M, resolution=2)
    geom_series = geom_series.simplify(5.0)

    bufs = geom_series.tolist()
    areas = np.array([b.area for b in bufs])
    n = len(bufs)
    matrix = np.zeros((n, n), dtype=np.float32)

    log.info("  Building spatial index...")
    tree = STRtree(bufs)

    # 2. PREPARE TASKS: Map out only the necessary comparisons
    log.info("  Preparing parallel intersection tasks...")
    tasks = []
    for i, buf_i in enumerate(bufs):
        candidate_indices = tree.query(buf_i)
        # Only check j > i to avoid duplicate math (if A overlaps B, B overlaps A)
        valid_j = [j for j in candidate_indices if j > i]
        if not valid_j:
            continue
            
        candidates = [(j, bufs[j], areas[j]) for j in valid_j]
        tasks.append((i, buf_i, areas[i], candidates))

    total_tasks = len(tasks)
    if total_tasks == 0:
        return matrix

    # 3. EXECUTE: Flood the CPU cores
    num_cores = max(1, multiprocessing.cpu_count() - 1) # Leave 1 core for OS stability
    log.info("  Computing %d route clusters across %d CPU cores...", total_tasks, num_cores)

    completed = 0
    sys.stdout.write(f"\r  Progress: [0/{total_tasks}] 0.0%")
    sys.stdout.flush()

    with ThreadPoolExecutor() as _dummy: pass # Just ensuring the import is active
    
    # ProcessPoolExecutor bypasses the GIL to use full CPU power
    with concurrent.futures.ProcessPoolExecutor(max_workers=num_cores) as executor:
        futures = {executor.submit(_intersection_worker, task): task[0] for task in tasks}

        for future in concurrent.futures.as_completed(futures):
            i, results = future.result()
            
            # Populate matrix symmetrically
            for j, ratio_i_j, ratio_j_i in results:
                matrix[i, j] = ratio_i_j
                matrix[j, i] = ratio_j_i

            # 4. PROGRESS BAR UPDATE
            completed += 1
            percent = (completed / total_tasks) * 100
            sys.stdout.write(f"\r  Progress: [{completed}/{total_tasks}] {percent:.1f}%")
            sys.stdout.flush()

    print() # Clear the progress bar line
    log.info("  Overlap matrix (%d×%d) done.", n, n)
    return matrix


def cluster_routes(gdf: gpd.GeoDataFrame,
                   overlap_matrix: np.ndarray) -> gpd.GeoDataFrame:
    log.info("Union-Find clustering (threshold=%.0f%%)…",
             OVERLAP_THRESHOLD * 100)
    n      = len(gdf)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x

    def union(x, y):
        parent[find(x)] = find(y)

    for r, c in zip(*np.where(overlap_matrix >= OVERLAP_THRESHOLD)):
        union(int(r), int(c))

    gdf = gdf.copy()
    gdf["Cluster_ID"]   = [find(i) for i in range(n)]
    gdf["Cluster_Size"] = gdf["Cluster_ID"].map(gdf["Cluster_ID"].value_counts())
    log.info("  %d clusters formed.", gdf["Cluster_ID"].nunique())
    return gdf


def backfill_overlap_metric(gdf: gpd.GeoDataFrame,
                             overlap_matrix: np.ndarray) -> gpd.GeoDataFrame:
    n     = len(gdf)
    gdf   = gdf.copy()
    means = []
    for i in range(n):
        row = np.concatenate([overlap_matrix[i, :i], overlap_matrix[i, i+1:]])
        means.append(float(row.mean()) if len(row) else 0.0)
    gdf["Overlap_Metric"] = [round(v, 4) for v in means]
    return gdf


def classify_routes(gdf: gpd.GeoDataFrame,
                    freq_scores: np.ndarray,
                    overlap_matrix: np.ndarray) -> gpd.GeoDataFrame:
    """
    Classifies routes into UPGRADED_TO_TRUNK / MERGED_INTO_TRUNK /
    RETAINED_AS_FEEDER.

    v3 CHANGES (three new rules):

    1. CDI Gate lowered to 30th percentile (was median / 50th in v2).
       Aggressively promotes more corridors to trunk status.

    2. Anti-Stranding (Length constraint):
       No route under TRUNK_MIN_LENGTH_KM (5.0 km) can be promoted to Trunk.
       This prevents isolated 1–4 km city-centre stubs from entering the trunk
       network as disconnected artefacts.

    3. Network Connectivity Bonus:
       Before evaluating cluster leadership, any candidate route whose geometry
       spatially intersects (Shapely intersection) a CMP backbone trunk corridor
       receives a CMP_CONNECTIVITY_BONUS (1.5×) multiplier on its combined
       demand score.  This ensures newly promoted trunks physically attach to
       the CMP backbone rather than floating in isolation.

    CMP-injected routes (CMP_Trunk == True) already carry Action_Taken =
    UPGRADED_TO_TRUNK from inject_cmp_trunk_routes() and are NOT re-classified
    here — they are preserved as-is and merely receive a New_Route_ID.
    """
    log.info("Classifying routes — v3 aggressive trunk rules…")
    log.info("  CDI gate: %dth percentile (was 50th in v2)", TRUNK_CDI_GATE_PERCENTILE)
    log.info("  Anti-stranding: routes < %.1f km ineligible for Trunk", TRUNK_MIN_LENGTH_KM)
    log.info("  CMP connectivity bonus: %.1f× for routes intersecting CMP backbone",
             CMP_CONNECTIVITY_BONUS)

    gdf = gdf.copy()

    # Preserve CMP-injected routes; initialise all others as feeders
    non_cmp_mask = ~gdf.get("CMP_Trunk", pd.Series(False, index=gdf.index))
    gdf.loc[non_cmp_mask, "Action_Taken"] = "RETAINED_AS_FEEDER"

    # Initialise ID and headway placeholders
    gdf["New_Route_ID"] = ""
    gdf["Headway_Min"]  = HEADWAY_MP_MIN   # Placeholder; overwritten by Step 6

    # ── Combined demand score ──────────────────────────────────────────────────
    gdf["_combined_demand"] = gdf["Pop_Score"] + gdf["POI_Score"]

    # ── CDI gate at 30th percentile (v3: lowered from median) ─────────────────
    gate_threshold = float(np.percentile(gdf["_combined_demand"].values,
                                         TRUNK_CDI_GATE_PERCENTILE))
    log.info("  Demand gate threshold (%dth pct): %.4f",
             TRUNK_CDI_GATE_PERCENTILE, gate_threshold)

    # ── Build CMP backbone geometry union for connectivity bonus ───────────────
    cmp_geoms = []
    cmp_mask  = gdf.get("CMP_Trunk", pd.Series(False, index=gdf.index))
    if cmp_mask.any():
        gdf_utm_cmp = gdf[cmp_mask].to_crs(UTM_CRS)
        for geom in gdf_utm_cmp.geometry:
            if geom is not None and not geom.is_empty:
                cmp_geoms.append(geom.buffer(OVERLAP_BUFFER_M))
        if cmp_geoms:
            cmp_backbone_union = unary_union(cmp_geoms)
            log.info("  CMP backbone union built from %d trunk geometries.", len(cmp_geoms))
        else:
            cmp_backbone_union = None
            log.warning("  CMP backbone union is empty — connectivity bonus inactive.")
    else:
        cmp_backbone_union = None
        log.warning("  No CMP_Trunk routes found — connectivity bonus inactive.")

    gdf_utm_all = gdf.to_crs(UTM_CRS).copy()

    trunk_n = feeder_n = 1
    cluster_no_trunk = 0

    # ── First pass: assign IDs to CMP-injected routes already marked Trunk ─────
    cmp_trunk_indices = gdf[cmp_mask & (gdf["Action_Taken"] == "UPGRADED_TO_TRUNK")].index
    for idx in cmp_trunk_indices:
        if not gdf.at[idx, "New_Route_ID"]:
            cmp_rid = gdf.at[idx, "CMP_Route_ID"]
            gdf.at[idx, "New_Route_ID"] = cmp_rid if cmp_rid else f"TRK-{trunk_n:03d}"
            trunk_n += 1

    # ── Second pass: classify non-CMP routes cluster by cluster ───────────────
    for cluster_id, grp in gdf.groupby("Cluster_ID"):
        idxs = grp.index.tolist()

        if len(idxs) == 1:
            # Single-route cluster
            idx0 = idxs[0]
            if gdf.at[idx0, "Action_Taken"] == "UPGRADED_TO_TRUNK":
                # Already a CMP trunk with ID assigned above
                if not gdf.at[idx0, "New_Route_ID"]:
                    gdf.at[idx0, "New_Route_ID"] = f"TRK-{trunk_n:03d}"
                    trunk_n += 1
            else:
                gdf.at[idx0, "New_Route_ID"] = f"FDR-{feeder_n:03d}"
                feeder_n += 1
            continue

        # Sort by combined demand (with connectivity bonus applied)
        def _boosted_demand(i) -> float:
            base = gdf.at[i, "_combined_demand"]
            # Anti-stranding: routes < TRUNK_MIN_LENGTH_KM get zero demand
            if gdf.at[i, "Route_KM"] < TRUNK_MIN_LENGTH_KM:
                return 0.0
            # CMP already-trunk routes need no additional promotion
            if gdf.at[i, "CMP_Trunk"]:
                return base
            # Connectivity bonus: does this route's geometry touch CMP backbone?
            if cmp_backbone_union is not None:
                geom_utm = gdf_utm_all.at[i, "geometry"]
                if geom_utm is not None and not geom_utm.is_empty:
                    try:
                        if geom_utm.intersects(cmp_backbone_union):
                            return base * CMP_CONNECTIVITY_BONUS
                    except Exception:
                        pass
            return base

        sorted_idxs = sorted(idxs, key=_boosted_demand, reverse=True)
        ti = sorted_idxs[0]   # Candidate Trunk (highest boosted demand)

        # If candidate is already a CMP Trunk, skip gate evaluation
        if gdf.at[ti, "CMP_Trunk"] and gdf.at[ti, "Action_Taken"] == "UPGRADED_TO_TRUNK":
            if not gdf.at[ti, "New_Route_ID"]:
                gdf.at[ti, "New_Route_ID"] = f"TRK-{trunk_n:03d}"
                trunk_n += 1
            for idx in sorted_idxs[1:]:
                if gdf.at[idx, "CMP_Trunk"]:
                    continue
                pos_i = gdf.index.get_loc(idx)
                pos_t = gdf.index.get_loc(ti)
                overlap = float(overlap_matrix[pos_i, pos_t])
                start_i = gpd.GeoSeries(
                    [Point(float(gdf.at[idx, "Start_Lon"]),
                           float(gdf.at[idx, "Start_Lat"]))],
                    crs=WGS84_CRS).to_crs(UTM_CRS).iloc[0]
                start_t = gpd.GeoSeries(
                    [Point(float(gdf.at[ti, "Start_Lon"]),
                           float(gdf.at[ti, "Start_Lat"]))],
                    crs=WGS84_CRS).to_crs(UTM_CRS).iloc[0]
                if (overlap >= OVERLAP_THRESHOLD
                        and start_i.distance(start_t) <= OD_PROXIMITY_TOLERANCE_M):
                    gdf.at[idx, "Action_Taken"] = "MERGED_INTO_TRUNK"
                    gdf.at[idx, "New_Route_ID"] = gdf.at[ti, "New_Route_ID"]
                else:
                    if not gdf.at[idx, "New_Route_ID"]:
                        gdf.at[idx, "New_Route_ID"] = f"FDR-{feeder_n:03d}"
                        feeder_n += 1
            continue

        # Anti-stranding: top candidate must meet min length
        if gdf.at[ti, "Route_KM"] < TRUNK_MIN_LENGTH_KM:
            cluster_no_trunk += 1
            log.debug(
                "  Cluster %s: top candidate %.1f km < %.1f km anti-stranding "
                "floor — all %d routes remain feeders.",
                cluster_id, gdf.at[ti, "Route_KM"], TRUNK_MIN_LENGTH_KM, len(idxs))
            for idx in idxs:
                if not gdf.at[idx, "New_Route_ID"]:
                    gdf.at[idx, "New_Route_ID"] = f"FDR-{feeder_n:03d}"
                    feeder_n += 1
            continue

        # v3 CDI gate at 30th percentile (raw, un-boosted demand used for gate)
        candidate_demand_raw = gdf.at[ti, "_combined_demand"]
        if candidate_demand_raw <= gate_threshold:
            cluster_no_trunk += 1
            log.debug(
                "  Cluster %s: top candidate demand %.4f ≤ %dth pct gate %.4f "
                "— NO trunk promoted (all %d routes remain feeders).",
                cluster_id, candidate_demand_raw, TRUNK_CDI_GATE_PERCENTILE,
                gate_threshold, len(idxs))
            for idx in idxs:
                if not gdf.at[idx, "New_Route_ID"]:
                    gdf.at[idx, "New_Route_ID"] = f"FDR-{feeder_n:03d}"
                    feeder_n += 1
            continue

        # Passed gate → promote to Trunk
        gdf.at[ti, "Action_Taken"] = "UPGRADED_TO_TRUNK"
        gdf.at[ti, "New_Route_ID"] = f"TRK-{trunk_n:03d}"

        for idx in sorted_idxs[1:]:
            if gdf.at[idx, "CMP_Trunk"]:
                continue
            pos_i   = gdf.index.get_loc(idx)
            pos_t   = gdf.index.get_loc(ti)
            overlap = float(overlap_matrix[pos_i, pos_t])
            start_i = gpd.GeoSeries(
                [Point(float(gdf.at[idx, "Start_Lon"]),
                       float(gdf.at[idx, "Start_Lat"]))],
                crs=WGS84_CRS).to_crs(UTM_CRS).iloc[0]
            start_t = gpd.GeoSeries(
                [Point(float(gdf.at[ti, "Start_Lon"]),
                       float(gdf.at[ti, "Start_Lat"]))],
                crs=WGS84_CRS).to_crs(UTM_CRS).iloc[0]
            if (overlap >= OVERLAP_THRESHOLD
                    and start_i.distance(start_t) <= OD_PROXIMITY_TOLERANCE_M):
                gdf.at[idx, "Action_Taken"] = "MERGED_INTO_TRUNK"
                gdf.at[idx, "New_Route_ID"] = f"TRK-{trunk_n:03d}"
            else:
                if not gdf.at[idx, "New_Route_ID"]:
                    gdf.at[idx, "New_Route_ID"] = f"FDR-{feeder_n:03d}"
                    feeder_n += 1

        trunk_n += 1

    gdf.drop(columns=["_combined_demand"], inplace=True)

    log.info("  v3 gate (30th pct) — %d clusters had no eligible Trunk "
             "(all assigned as feeders).", cluster_no_trunk)
    log.info("  Trunks: %d | Merged: %d | Feeders: %d",
             (gdf["Action_Taken"] == "UPGRADED_TO_TRUNK").sum(),
             (gdf["Action_Taken"] == "MERGED_INTO_TRUNK").sum(),
             (gdf["Action_Taken"] == "RETAINED_AS_FEEDER").sum())
    return gdf


def apply_terminal_capacity(gdf: gpd.GeoDataFrame,
                              gdf_pois: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    log.info("Applying terminal capacity constraints…")
    term_pois = gdf_pois[
        gdf_pois["category"].str.lower().isin(TERMINAL_CATEGORIES)
    ].to_crs(UTM_CRS)
    if term_pois.empty:
        return gdf
    term_tree  = STRtree(term_pois.geometry.tolist())
    gdf        = gdf.copy()
    downgraded = 0
    for idx, row in gdf.iterrows():
        if row["Action_Taken"] != "UPGRADED_TO_TRUNK":
            continue
        if row.get("Fleet_Required", 0) <= FLEET_CAP_HARD:
            continue
        has_cap = False
        for lon, lat in [(float(row["Start_Lon"]), float(row["Start_Lat"])),
                          (float(row["End_Lon"]),   float(row["End_Lat"]))]:
            pt_utm = (gpd.GeoSeries([Point(lon, lat)], crs=WGS84_CRS)
                      .to_crs(UTM_CRS).iloc[0])
            if len(term_tree.query(pt_utm.buffer(TERMINAL_BUFFER_M))) > 0:
                has_cap = True
                break
        if not has_cap:
            if row.get("CMP_Trunk", False):
                continue
            gdf.at[idx, "Action_Taken"] = "RETAINED_AS_FEEDER"
            log.debug("  Route %s capacity-downgraded to feeder.",
                      row["Route_ID"])
            downgraded += 1
    log.info("  %d trunks capacity-downgraded to feeder.", downgraded)
    return gdf


# ══════════════════════════════════════════════════════════════════════════════
#  STEPS 3 – 9  ─  CDI PIPELINE
# ══════════════════════════════════════════════════════════════════════════════

def step3_compute_road_multiplier(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Step 3: Road_Multiplier via Action_Taken fallback.
    Primary OSM method deferred to Phase 2 GIS work.
    """
    log.info("Step 3: Assigning Road_Multiplier (Action_Taken fallback)…")

    def _road_multiplier(action: str) -> float:
        if action in ("UPGRADED_TO_TRUNK", "MERGED_INTO_TRUNK"):
            return ROAD_MULTIPLIER_TRUNK
        elif action == "RETAINED_AS_FEEDER":
            return ROAD_MULTIPLIER_FEEDER
        return ROAD_MULTIPLIER_DEFAULT

    gdf["Road_Multiplier"] = gdf["Action_Taken"].apply(_road_multiplier)
    log.info("  Road_Multiplier — Trunk: %.2f  Feeder: %.2f",
             ROAD_MULTIPLIER_TRUNK, ROAD_MULTIPLIER_FEEDER)
    return gdf


def step4a_compute_final_cdi(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Step 4a: Final_CDI = (Pop_Score×0.50 + POI_Score×0.50) × Road_Multiplier.
    50/50 weighting — Phase 1 only. Will be calibrated against ridership in Phase 2.
    """
    log.info("Step 4a: Computing Final_CDI = (Pop×%.2f + POI×%.2f) × Road_Multiplier…",
             CDI_POP_WEIGHT, CDI_POI_WEIGHT)
    raw_cdi          = (gdf["Pop_Score"] * CDI_POP_WEIGHT +
                        gdf["POI_Score"] * CDI_POI_WEIGHT)
    gdf["Final_CDI"] = (raw_cdi * gdf["Road_Multiplier"]).round(4).clip(lower=0.0)
    log.info("  Final_CDI mean: %.4f  max: %.4f  min: %.4f",
             gdf["Final_CDI"].mean(), gdf["Final_CDI"].max(),
             gdf["Final_CDI"].min())
    return gdf


def step4b_compute_social_flag(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Step 4b: Social_Flag = TRUE if route passes within 500m of any
    Social Obligation attractor (migrant camps, industrial estates, hospitals).
    LP routes flagged TRUE are overridden to MP in Step 5.
    """
    log.info("Step 4b: Computing Social_Flag (500m buffer, %d attractors)…",
             len(SOCIAL_OBLIGATION_ATTRACTORS))
    attractor_points = [Point(lon, lat)
                        for _, lat, lon in SOCIAL_OBLIGATION_ATTRACTORS]
    gdf_attractors   = gpd.GeoDataFrame(
        {"label": [a[0] for a in SOCIAL_OBLIGATION_ATTRACTORS]},
        geometry=attractor_points, crs=WGS84_CRS,
    ).to_crs(UTM_CRS)

    attractor_union  = unary_union(
        [p.buffer(SOCIAL_FLAG_BUFFER_M) for p in gdf_attractors.geometry])
    gdf_utm          = gdf.to_crs(UTM_CRS).copy()
    gdf["Social_Flag"] = (
        gdf_utm.geometry.simplify(SIMPLIFY_TOL_M).intersects(attractor_union))
    log.info("  %d routes flagged as Social Obligation.", gdf["Social_Flag"].sum())
    return gdf


def step5_assign_priority_bands(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Step 5: Priority Band (HP / MP / LP) via Jenks Natural Breaks on Final_CDI.
    Social Obligation floor: LP → MP if Social_Flag = TRUE.
    """
    log.info("Step 5: Assigning Priority Bands via Jenks Natural Breaks…")
    cdi_values = gdf["Final_CDI"].fillna(0.0).values

    if not _HAS_JENKSPY:
        log.warning("  ⚠ jenkspy not installed — falling back to 33rd/66th percentile.")
        thresh_lp_mp = float(np.percentile(cdi_values, 33.33))
        thresh_mp_hp = float(np.percentile(cdi_values, 66.67))
    else:
        n = len(cdi_values)
        if n < 3:
            log.warning("  Fewer than 3 routes — assigning MP to all.")
            gdf["Priority_Band"] = "MP"
            return gdf
        breaks       = jenkspy.jenks_breaks(cdi_values.tolist(), n_classes=3)
        thresh_lp_mp = float(breaks[1])
        thresh_mp_hp = float(breaks[2])
        log.info("  Jenks breaks → LP < %.4f  ≤ MP < %.4f  ≤ HP",
                 thresh_lp_mp, thresh_mp_hp)

    def _band(cdi: float) -> str:
        if cdi >= thresh_mp_hp:   return "HP"
        elif cdi >= thresh_lp_mp: return "MP"
        return "LP"

    gdf["Priority_Band"]  = gdf["Final_CDI"].apply(_band)
    social_lp_mask        = (gdf["Social_Flag"] == True) & (gdf["Priority_Band"] == "LP")
    gdf.loc[social_lp_mask, "Priority_Band"] = "MP"

    n_hp, n_mp, n_lp = ((gdf["Priority_Band"] == b).sum() for b in ("HP","MP","LP"))
    log.info("  Priority bands — HP: %d  MP: %d  LP: %d  (%d Social LP→MP upgrades)",
             n_hp, n_mp, n_lp, social_lp_mask.sum())
    return gdf


def step6_assign_headways(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Step 6: Headway_Min from Priority Band and Route_Type.

    DIRECTIVE 1 INTEGRATION:
    Regional_District routes are rural lifelines with relaxed headways.

    CMP OVERRIDE (v3):
    Any route flagged CMP_Trunk = True receives a hardcoded headway of
    CMP_TRUNK_HEADWAY_MIN (10 min), bypassing the Priority Band logic entirely.
    10 min is the researched optimal trunk frequency for Tier-2 Indian cities
    undergoing BRT/City Bus overhauls to ensure high ridership attraction.

    Headway rules:
      CMP Trunk routes                   → 10 min (hardcoded)
      Urban / Peri_Urban routes          → HP=10  MP=20  LP=45  (UDPFI 2015)
      Regional_District routes           → HP=45  MP=60  LP=60  (rural lifeline)
    """
    log.info("Step 6: Assigning headways by Priority Band + Route_Type…")
    log.info("  CMP Trunk routes: hardcoded %d min (research-optimal Tier-2 BRT)",
             CMP_TRUNK_HEADWAY_MIN)
    log.info("  Urban/Peri-Urban: HP=%d  MP=%d  LP=%d min",
             HEADWAY_HP_MIN, HEADWAY_MP_MIN, HEADWAY_LP_MIN)
    log.info("  Regional_District lifelines: HP=%d  MP=%d min",
             HEADWAY_REGIONAL_HP_MIN, HEADWAY_REGIONAL_MP_MIN)

    def _headway(row) -> int:
        # CMP bypass — hardcoded 10 min regardless of priority band
        if row.get("CMP_Trunk", False):
            return CMP_TRUNK_HEADWAY_MIN

        band       = row["Priority_Band"]
        route_type = row.get("Route_Type", "Urban")

        if route_type == "Regional_District":
            if band == "HP": return HEADWAY_REGIONAL_HP_MIN
            return HEADWAY_REGIONAL_MP_MIN

        if band == "HP": return HEADWAY_HP_MIN
        if band == "MP": return HEADWAY_MP_MIN
        return HEADWAY_LP_MIN

    gdf["Headway_Min"] = gdf.apply(_headway, axis=1).astype(int)

    cmp_n      = gdf.get("CMP_Trunk", pd.Series(False, index=gdf.index)).sum()
    regional_n = (gdf.get("Route_Type", pd.Series()) == "Regional_District").sum()
    log.info("  %d CMP Trunk routes → hardcoded %d-min headway.", cmp_n, CMP_TRUNK_HEADWAY_MIN)
    log.info("  %d Regional_District routes assigned relaxed headways.", regional_n)
    return gdf


def step8_compute_fleet_required(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Step 8: Fleet_Required = CEILING(Cycle_Time_Min / Headway_Min).

    v3 CHANGE — LPV Downgrade Removed:
    v2 would downgrade routes with fleet < MIN_FLEET_THRESHOLD to LPVs.
    v3 eliminates LPVs entirely from the fleet.  Instead, any route whose
    computed fleet falls below MIN_FLEET_THRESHOLD is raised directly to
    MIN_FLEET_THRESHOLD (no class change, no LPV substitution).
    This maintains minimum operational viability while keeping all vehicles
    in the HPV/MPV category.
    """
    log.info("Step 8: Computing Fleet_Required = CEILING(Cycle_Time / Headway), "
             "floor at MIN_FLEET_THRESHOLD=%d (no LPV downgrade in v3)…",
             MIN_FLEET_THRESHOLD)

    fleet_required_list = []

    for _, row in gdf.iterrows():
        raw_fleet = max(1, math.ceil(
            row["Cycle_Time_Min"] / max(1, row["Headway_Min"])))

        # Floor at MIN_FLEET_THRESHOLD — no downgrade, no LPV
        fleet_required_list.append(max(raw_fleet, MIN_FLEET_THRESHOLD))

    gdf = gdf.copy()
    gdf["Fleet_Required"] = fleet_required_list

    n_floored = sum(1 for raw, final in zip(
        [max(1, math.ceil(r["Cycle_Time_Min"] / max(1, r["Headway_Min"])))
         for _, r in gdf.iterrows()],
        fleet_required_list
    ) if final > raw)

    log.info("  %d routes had fleet raised to MIN_FLEET_THRESHOLD=%d.",
             n_floored, MIN_FLEET_THRESHOLD)
    log.info("  Fleet_Required — mean: %.1f  max: %d  total: %d",
             gdf["Fleet_Required"].mean(),
             gdf["Fleet_Required"].max(),
             gdf["Fleet_Required"].sum())
    return gdf


def step9_compute_vehicle_split(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Step 9: HPV/MPV vehicle type split  (LPV eliminated in v3).

    Split rules:
      UPGRADED_TO_TRUNK or MERGED_INTO_TRUNK → 85% HPV  15% MPV  (0% LPV)
        Rationale: Trunk corridors carry the highest sustained passenger loads.
        Aggressively favouring HPVs maximises capacity, reduces per-seat cost,
        and aligns with CMP BRT intent.  The 15% MPV buffer handles off-peak /
        terminal layover slots without over-committing large vehicles.

      RETAINED_AS_FEEDER → 0% HPV  100% MPV  (0% LPV)
        Rationale: Feeder routes serve last-mile and low-frequency corridors.
        MPVs offer better maneuverability on narrow feeder roads and flexible
        scheduling.  No HPV allocation — these routes cannot justify large
        vehicle operations financially or operationally.

    QC: HPV is STRICTLY reserved for Trunk corridors (HPV_Count > 0 only on
    UPGRADED_TO_TRUNK / MERGED_INTO_TRUNK).  RETAINED_AS_FEEDER routes always
    have HPV_Count = 0 and LPV_Count = 0.
    """
    log.info("Step 9: Computing HPV/MPV vehicle split (LPV removed in v3)…")
    log.info("  Trunk/Merged: 85%% HPV + 15%% MPV | Feeder: 100%% MPV")
    gdf = gdf.copy()

    def _split(row) -> pd.Series:
        fleet  = int(row["Fleet_Required"])
        action = row["Action_Taken"]

        if fleet == 0:
            return pd.Series({"HPV_Count": 0, "MPV_Count": 0})

        if action in ("UPGRADED_TO_TRUNK", "MERGED_INTO_TRUNK"):
            # 85% HPV, 15% MPV — ceiling arithmetic, then clip to fleet total
            hpv = math.ceil(fleet * 0.85)
            mpv = fleet - hpv   # remainder goes to MPV
            mpv = max(0, mpv)   # safety floor
            if hpv + mpv > fleet:
                mpv = max(0, fleet - hpv)
        else:
            # RETAINED_AS_FEEDER → 100% MPV
            hpv = 0
            mpv = fleet

        return pd.Series({"HPV_Count": hpv, "MPV_Count": mpv})

    split_df          = gdf.apply(_split, axis=1)
    gdf["HPV_Count"]  = split_df["HPV_Count"].astype(int)
    gdf["MPV_Count"]  = split_df["MPV_Count"].astype(int)

    # v3: no LPV column — set to zero for any legacy references
    gdf["LPV_Count"]  = 0

    log.info("  HPV total: %d  MPV total: %d  (LPV: 0 by policy)",
             gdf["HPV_Count"].sum(), gdf["MPV_Count"].sum())
    return gdf


def zero_merged_route_fleet(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Zero fleet for MERGED_INTO_TRUNK routes — service absorbed by Trunk."""
    merged_mask = gdf["Action_Taken"] == "MERGED_INTO_TRUNK"
    gdf = gdf.copy()
    gdf.loc[merged_mask,
            ["Fleet_Required", "HPV_Count", "MPV_Count", "LPV_Count"]] = 0
    n_merged = merged_mask.sum()
    if n_merged:
        log.info("  Zeroed fleet for %d MERGED_INTO_TRUNK routes.", n_merged)
    return gdf


# ══════════════════════════════════════════════════════════════════════════════
#  QUALITY CONTROL  ─  All 8 Checks Must Pass Before Export
# ══════════════════════════════════════════════════════════════════════════════

def run_all_qc_checks(gdf: gpd.GeoDataFrame) -> None:
    """
    8 pre-submission QC checks for v3 (LPV removed, HPV/MPV enforced).
    Any failure raises RuntimeError and blocks the export pipeline.
    """
    log.info("Running QC checks (8 checks — v3 HPV/MPV only policy)…")
    failures = []

    # Check 1: HPV + MPV = Fleet_Required for every row
    check1 = gdf[gdf["HPV_Count"] + gdf["MPV_Count"] != gdf["Fleet_Required"]]
    if not check1.empty:
        failures.append(
            f"CHECK 1 FAIL — {len(check1)} rows where HPV+MPV ≠ Fleet_Required "
            f"(LPV_Count should be 0 for all rows in v3)")
        for _, r in check1.iterrows():
            failures.append(
                f"  {r['Route_ID']} | Fleet={r['Fleet_Required']} | "
                f"HPV={r['HPV_Count']} MPV={r['MPV_Count']}"
            )
    else:
        log.info("  ✓ Check 1: Vehicle count integrity — HPV+MPV = Fleet_Required for all rows.")

    # Check 2: Zero LPV across the entire dataset (v3 policy: LPV eradicated)
    if "LPV_Count" in gdf.columns:
        check2 = gdf[gdf["LPV_Count"] > 0]
        if not check2.empty:
            failures.append(
                f"CHECK 2 FAIL — {len(check2)} rows still have LPV_Count > 0. "
                f"LPV is eradicated in v3 — step9 may have a regression.")
        else:
            log.info("  ✓ Check 2: LPV_Count = 0 for all rows (v3 policy confirmed).")
    else:
        log.info("  ✓ Check 2: LPV_Count column absent — LPV fully eradicated.")

    # Check 3: No null Priority_Band
    check3 = gdf[gdf["Priority_Band"].isna() | (gdf["Priority_Band"] == "")]
    if not check3.empty:
        failures.append(
            f"CHECK 3 FAIL — {len(check3)} rows with null Priority_Band.")
    else:
        log.info("  ✓ Check 3: No null Priority_Band values.")

    # Check 4: Feeder routes must have HPV_Count = 0
    check4 = gdf[(gdf["Action_Taken"] == "RETAINED_AS_FEEDER") &
                 (gdf["HPV_Count"] > 0)]
    if not check4.empty:
        failures.append(
            f"CHECK 4 FAIL — {len(check4)} FEEDER routes have HPV_Count > 0.")
        for _, r in check4.iterrows():
            failures.append(f"  {r['Route_ID']} | HPV={r['HPV_Count']}")
    else:
        log.info("  ✓ Check 4: All feeder routes have HPV_Count = 0 (100%% MPV confirmed).")

    # Check 5: All active Trunk routes must have HPV_Count > 0
    trunks = gdf[gdf["Action_Taken"] == "UPGRADED_TO_TRUNK"]
    check5 = trunks[trunks["HPV_Count"] == 0]
    if not check5.empty:
        failures.append(
            f"CHECK 5 FAIL — {len(check5)} TRUNK routes have HPV_Count = 0. "
            f"v3 mandates ≥1 HPV on every active trunk.")
        for _, r in check5.iterrows():
            failures.append(
                f"  {r['Route_ID']} | Fleet={r['Fleet_Required']} "
                f"HPV={r['HPV_Count']} MPV={r['MPV_Count']}")
    else:
        log.info("  ✓ Check 5: All active Trunk routes have HPV_Count > 0.")

    # Check 6: Fleet_Required > 0 for all active routes
    active = gdf[gdf["Action_Taken"] != "MERGED_INTO_TRUNK"]
    check6 = active[active["Fleet_Required"] <= 0]
    if not check6.empty:
        failures.append(
            f"CHECK 6 FAIL — {len(check6)} active routes have Fleet_Required ≤ 0.")
    else:
        total_fleet = int(active["Fleet_Required"].sum())
        log.info("  ✓ Check 6: All active routes have Fleet_Required > 0 "
                 "(total fleet = %d).", total_fleet)

    # Check 7: Known corridor sanity (Kashmir landmarks should appear in HP band)
    hp_names     = gdf[gdf["Priority_Band"] == "HP"]["Route_Name"].str.lower().tolist()
    sanity_terms = ["lal chowk", "hazratbal", "batamaloo"]
    found_terms  = [t for t in sanity_terms if any(t in n for n in hp_names)]
    if len(found_terms) < len(sanity_terms):
        missing = [t for t in sanity_terms if t not in found_terms]
        log.warning("  CHECK 7 WARN — %s not found in HP band. "
                    "Review CDI normalisation.", missing)
    else:
        log.info("  ✓ Check 7: %s corridors confirmed in HP band.", found_terms)

    # Check 8: No Social_Flag route in LP band
    check8 = gdf[(gdf["Social_Flag"] == True) & (gdf["Priority_Band"] == "LP")]
    if not check8.empty:
        failures.append(
            f"CHECK 8 FAIL — {len(check8)} Social Obligation routes in LP band.")
    else:
        log.info("  ✓ Check 8: No Social Obligation routes in LP band.")

    # Additional: all CMP Trunk routes must be UPGRADED_TO_TRUNK
    if "CMP_Trunk" in gdf.columns:
        cmp_not_trunk = gdf[(gdf["CMP_Trunk"] == True) &
                            (gdf["Action_Taken"] != "UPGRADED_TO_TRUNK")]
        if not cmp_not_trunk.empty:
            failures.append(
                f"CHECK CMP FAIL — {len(cmp_not_trunk)} CMP-injected routes "
                f"are NOT marked UPGRADED_TO_TRUNK.")
        else:
            cmp_n = (gdf["CMP_Trunk"] == True).sum()
            log.info("  ✓ Check CMP: All %d CMP-injected routes confirmed as "
                     "UPGRADED_TO_TRUNK.", cmp_n)

    if failures:
        for msg in failures:
            log.error(msg)
        raise RuntimeError(
            f"QC FAILED: {len(failures)} issue(s). Fix before export. "
            f"See transit_v3.log for details.")
    log.info("  ✓ ALL QC CHECKS PASSED — workbook ready for export.")


# ══════════════════════════════════════════════════════════════════════════════
#  NETWORK SCORE
# ══════════════════════════════════════════════════════════════════════════════

def compute_network_score(gdf: gpd.GeoDataFrame, net_pop: int) -> float:
    active      = gdf[gdf["Action_Taken"] != "MERGED_INTO_TRUNK"]
    total_fleet = int(active["Fleet_Required"].sum())
    efficiency  = net_pop / max(1, total_fleet)
    cmp_n       = int(gdf.get("CMP_Trunk", pd.Series(False, index=gdf.index)).sum())
    log.info("=" * 68)
    log.info("  NETWORK EFFICIENCY SUMMARY (v3)")
    log.info("  Deduplicated Pop. Served : %s residents",  f"{net_pop:,}")
    log.info("  Active Fleet Required    : %d buses",       total_fleet)
    log.info("  Fleet Efficiency         : %.0f res/bus",   efficiency)
    log.info("  CMP Backbone Trunks      : %d routes (hardcoded 10-min headway)", cmp_n)
    log.info("  Routes > 40km (lifelines): %d (Directive 1 — retained, not dropped)",
             (gdf["Route_Type"] == "Regional_District").sum())
    log.info("  LPV fleet                : 0 (eradicated in v3)")
    log.info("=" * 68)
    return float(efficiency)


# ══════════════════════════════════════════════════════════════════════════════
#  PHASE 3  ─  RATIONALISATION LOG
# ══════════════════════════════════════════════════════════════════════════════

def _reasoning(row: pd.Series) -> str:
    action    = row["Action_Taken"]
    old_id    = row["Route_ID"]
    new_id    = row["New_Route_ID"]
    pop       = f"{row.get('Population_Served_Pct', 0.0):.2f}% of CMP 2024 pop."
    km        = f"{row['Route_KM']:.1f}"
    fleet     = row["Fleet_Required"]
    band      = row.get("Priority_Band", "?")
    hw        = row.get("Headway_Min", "?")
    cdi       = f"{row.get('Final_CDI', 0):.4f}"
    rt        = row.get("Route_Type", "?")
    social    = "🚩 Social Obligation" if row.get("Social_Flag") else ""
    zone      = row.get("Congestion_Zone", "?")
    hpv       = row.get("HPV_Count", 0)
    mpv       = row.get("MPV_Count", 0)
    cmp_tag   = f" [CMP-{row['CMP_Route_ID']}]" if row.get("CMP_Trunk") else ""

    if action == "UPGRADED_TO_TRUNK":
        return (
            f"Route {old_id} ({row['Route_Name']}) → Trunk {new_id}{cmp_tag}. "
            f"Route_Type={rt} | Zone={zone} | CDI={cdi} | Band={band} | "
            f"Headway={hw} min | Fleet={fleet} (HPV={hpv} MPV={mpv}). "
            f"Serves ~{pop} residents over {km} km. {social}"
        )
    elif action == "MERGED_INTO_TRUNK":
        return (
            f"Route {old_id} ({row['Route_Name']}) merged into Trunk {new_id}. "
            f"Spatial overlap with trunk corridor. CDI={cdi}. "
            f"Fleet=0 (counted under Trunk). {social}"
        )
    else:
        return (
            f"Route {old_id} ({row['Route_Name']}) → Feeder {new_id}. "
            f"Route_Type={rt} | Zone={zone} | CDI={cdi} | Band={band} | "
            f"Headway={hw} min | Fleet={fleet} (HPV=0 enforced, MPV={mpv} — 100%% MPV). "
            f"Distinct catchment: {pop} residents over {km} km. {social}"
        )


def generate_log(gdf: gpd.GeoDataFrame, out_path: str) -> pd.DataFrame:
    log.info("Generating Rationalisation Log → %s", out_path)
    cols = [c for c in [
        "Route_ID", "Route_Name", "Action_Taken", "New_Route_ID",
        "Route_KM", "Route_Type", "Congestion_Zone",
        "Pop_Score", "POI_Score", "Road_Multiplier", "Final_CDI",
        "Social_Flag", "Priority_Band", "Headway_Min",
        "Fleet_Required", "HPV_Count", "MPV_Count",
        "CMP_Trunk", "CMP_Route_ID",
        "Overlap_Metric", "Population_Served",
        "HV_POI_Count", "Sharp_Turns", "Junction_Penalty_Min",
        "N_Stops_Estimated", "Stop_Penalty_Min",
        "OSRM_Duration_S", "Cycle_Time_Min", "Geo_Source",
    ] if c in gdf.columns]
    df_log                     = gdf[cols].copy()
    df_log["Reasoning_String"] = gdf.apply(_reasoning, axis=1)
    df_log.to_csv(out_path, index=False, encoding="utf-8-sig")
    log.info("  Log written: %d rows.", len(df_log))
    return df_log


def export_csv(gdf: gpd.GeoDataFrame, file_map: dict, out_path: str) -> None:
    log.info("Exporting CSV → %s", out_path)
    export_cols = [c for c in [
        "Route_ID", "Route_Name", "Action_Taken", "New_Route_ID",
        "Route_KM", "Route_Type", "OSRM_Duration_S", "Cycle_Time_Min",
        "Congestion_Zone", "N_Stops_Estimated", "Stop_Penalty_Min",
        "Sharp_Turns", "Junction_Penalty_Min",
        "Pop_Score", "POI_Score", "Road_Multiplier", "Final_CDI",
        "Social_Flag", "Priority_Band",
        "Headway_Min", "Fleet_Required",
        "HPV_Count", "MPV_Count",
        "CMP_Trunk", "CMP_Route_ID",
        "Population_Served", "HV_POI_Count",
        "Overlap_Metric", "Geo_Source",
    ] if c in gdf.columns]
    df_out = gdf[export_cols].copy()
    df_out["Map_File"] = df_out["New_Route_ID"].map(file_map).fillna("")
    df_out.to_csv(out_path, index=False, encoding="utf-8-sig")
    log.info("  CSV written: %d rows.", len(df_out))


def export_geojson(gdf: gpd.GeoDataFrame, out_path: str) -> None:
    log.info("Exporting Network GeoJSON → %s", out_path)
    active_gdf = gdf[gdf["Action_Taken"] != "MERGED_INTO_TRUNK"].copy()
    keep_cols  = [c for c in [
        "New_Route_ID", "Route_Name", "Action_Taken", "Route_KM",
        "Route_Type", "Priority_Band", "Headway_Min", "Fleet_Required",
        "HPV_Count", "MPV_Count",
        "Social_Flag", "Population_Served", "Final_CDI",
        "CMP_Trunk", "CMP_Route_ID",
        "Congestion_Zone", "geometry",
    ] if c in active_gdf.columns]
    export_gdf = active_gdf[keep_cols]
    if export_gdf.crs != WGS84_CRS:
        export_gdf = export_gdf.to_crs(WGS84_CRS)
    export_gdf = export_gdf[
        export_gdf.geometry.notnull() & ~export_gdf.geometry.is_empty]
    export_gdf.to_file(out_path, driver="GeoJSON")
    log.info("  GeoJSON written: %d active features.", len(export_gdf))


# ══════════════════════════════════════════════════════════════════════════════
#  PHASE 4  ─  CARTOGRAPHY (geometry pipeline preserved from v6)
# ══════════════════════════════════════════════════════════════════════════════

def _safe_coords(geom) -> List[Tuple[float, float]]:
    if geom is None:
        return []
    coords = ([c for line in geom.geoms for c in line.coords]
              if isinstance(geom, MultiLineString) else list(geom.coords))
    return [(lat, lon) for lon, lat in coords]


def _popup_html(row: pd.Series) -> str:
    action_col = {
        "UPGRADED_TO_TRUNK":   "#1A237E",
        "MERGED_INTO_TRUNK":   "#880E4F",
        "RETAINED_AS_FEEDER":  "#00695C",
    }.get(row.get("Action_Taken", ""), "#333")
    band_colour = {"HP": "#1B5E20", "MP": "#E65100", "LP": "#B71C1C"}.get(
        row.get("Priority_Band", ""), "#333")
    social_tag  = ("🚩 <b>Social Obligation Route</b><br>"
                   if row.get("Social_Flag") else "")
    cmp_tag     = (f"🏛 <b>CMP Backbone Trunk [{row.get('CMP_Route_ID','')}]"
                   f" — 10 min fixed headway</b><br>"
                   if row.get("CMP_Trunk") else "")
    hpv_pct     = (f"{int(row.get('HPV_Count',0)/max(1,row.get('Fleet_Required',1))*100)}%"
                   if row.get("Fleet_Required", 0) > 0 else "0%")
    return f"""
<div style="font-family:'Segoe UI',Arial,sans-serif;min-width:280px;font-size:12px">
  <div style="color:{action_col};font-size:15px;font-weight:700">{row.get('New_Route_ID','N/A')}</div>
  <div style="background:{action_col};color:#fff;display:inline-block;border-radius:4px;
    padding:1px 8px;font-size:10px;margin:3px 0 4px">{row.get('Action_Taken','').replace('_',' ')}</div>
  <div style="font-size:10px;color:#6A1B9A;margin-bottom:2px">
    Route Type: {row.get('Route_Type','?')} | Zone: {row.get('Congestion_Zone','?')}</div>
  <div style="color:{band_colour};font-weight:700;font-size:11px;margin-bottom:6px">
    Priority: {row.get('Priority_Band','?')} | Headway: {row.get('Headway_Min','?')} min
  </div>
  {social_tag}{cmp_tag}
  <table style="width:100%;border-collapse:collapse;line-height:1.7">
    <tr><td style="color:#666">Route Name</td><td>{row.get('Route_Name','')}</td></tr>
    <tr><td style="color:#666">Length</td><td><b>{row.get('Route_KM',0):.1f} km</b></td></tr>
    <tr><td style="color:#666">Fleet</td><td><b>{row.get('Fleet_Required','?')} buses</b></td></tr>
    <tr><td style="color:#888;font-size:11px">HPV / MPV</td>
        <td style="font-size:11px">{row.get('HPV_Count',0)} / {row.get('MPV_Count',0)}
        <span style="color:#888;font-size:10px">({hpv_pct} HPV)</span></td></tr>
    <tr style="border-top:1px solid #f0f0f0">
      <td style="color:#666">Cycle Time</td><td>{row.get('Cycle_Time_Min',0):.1f} min</td></tr>
    <tr><td style="color:#666">Stops (est.)</td><td>{row.get('N_Stops_Estimated',0)}</td></tr>
    <tr style="border-top:1px solid #f0f0f0">
      <td style="color:#1565C0">Pop_Score</td><td><b>{row.get('Pop_Score',0):.3f}</b></td></tr>
    <tr><td style="color:#E65100">POI_Score</td><td><b>{row.get('POI_Score',0):.3f}</b></td></tr>
    <tr><td style="color:#4A148C">Road ×</td><td><b>{row.get('Road_Multiplier',1.0):.2f}</b></td></tr>
    <tr><td style="color:#333"><b>Final CDI</b></td><td><b>{row.get('Final_CDI',0):.4f}</b></td></tr>
    <tr><td style="color:#666">Pop. Served</td><td><b>{row.get('Population_Served_Pct', row.get('Population_Served_Pct', 0.0)):.2f}% of CMP 2024</b></td></tr>
  </table>
</div>"""


def build_individual_maps(gdf: gpd.GeoDataFrame,
                           gdf_pois: gpd.GeoDataFrame,
                           out_dir: str) -> dict:
    """Build individual route HTML maps. Returns {New_Route_ID: filepath}."""
    log.info("Building individual route maps → %s/", out_dir)
    Path(out_dir).mkdir(exist_ok=True)
    active = gdf[gdf["Action_Taken"] != "MERGED_INTO_TRUNK"].copy()
    file_map = {}
    for _, row in active.iterrows():
        coords = _safe_coords(row.get("geometry"))
        if not coords:
            continue
        rid    = row["New_Route_ID"]
        centre = (sum(c[0] for c in coords) / len(coords),
                  sum(c[1] for c in coords) / len(coords))
        m = folium.Map(location=centre, zoom_start=13,
                       tiles=TILE_URL, attr=TILE_ATTR)
        colour = (COLOUR["trunk"] if row["Action_Taken"] == "UPGRADED_TO_TRUNK"
                  else COLOUR["feeder"])
        folium.PolyLine(coords, color=colour, weight=4,
                        popup=folium.Popup(_popup_html(row),
                                           max_width=320)).add_to(m)
        fname = f"{out_dir}/{rid.replace('/', '_')}.html"
        m.save(fname)
        file_map[rid] = fname
    log.info("  %d individual maps saved.", len(file_map))
    return file_map


def build_master_map(gdf: gpd.GeoDataFrame,
                     gdf_pois: gpd.GeoDataFrame,
                     raster_path: str,
                     out_html: str,
                     net_pop: int,
                     network_score: float) -> None:
    """Build master Folium map with all route layers."""
    log.info("Building master transit map → %s", out_html)
    # Centre on Srinagar Lal Chowk (was Jammu 32.73, 74.87)
    centre = [34.08, 74.81]
    m = folium.Map(location=centre, zoom_start=12,
                   tiles=TILE_URL, attr=TILE_ATTR)

    fg_trunk   = folium.FeatureGroup(name=FG["trunk"],   show=True)
    fg_feeder  = folium.FeatureGroup(name=FG["feeder"],  show=True)
    fg_regional = folium.FeatureGroup(name=FG.get("regional","Regional Routes"),
                                      show=True)
    fg_hv_poi  = folium.FeatureGroup(name=FG["hv_poi"],  show=True)
    fg_sec_poi = folium.FeatureGroup(name=FG["sec_poi"], show=False)

    # Plot routes
    for _, row in gdf.iterrows():
        if row["Action_Taken"] == "MERGED_INTO_TRUNK":
            continue
        coords = _safe_coords(row.get("geometry"))
        if not coords:
            continue

        rt     = row.get("Route_Type", "Urban")
        action = row["Action_Taken"]

        if action == "UPGRADED_TO_TRUNK":
            colour = COLOUR["trunk"]
            weight = 5
            fg     = fg_trunk
        elif rt == "Regional_District":
            colour = COLOUR["regional"]
            weight = 3
            fg     = fg_regional
        else:
            colour = COLOUR["feeder"]
            weight = 2
            fg     = fg_feeder

        folium.PolyLine(
            coords, color=colour, weight=weight, opacity=0.8,
            popup=folium.Popup(_popup_html(row), max_width=320),
        ).add_to(fg)

    # Plot POIs
    for _, poi in gdf_pois.iterrows():
        if poi.get("Is_HV_POI"):
            folium.CircleMarker(
                location=[poi.geometry.y, poi.geometry.x],
                radius=6, color=COLOUR["poi_high"], fill=True, fill_opacity=0.9,
                tooltip=f"{poi.get('name','POI')} (Tier 1)",
            ).add_to(fg_hv_poi)
        else:
            folium.CircleMarker(
                location=[poi.geometry.y, poi.geometry.x],
                radius=4, color=COLOUR["poi_secondary"], fill=True, fill_opacity=0.6,
                tooltip=f"{poi.get('name','POI')} (Tier 2)",
            ).add_to(fg_sec_poi)

    for fg in [fg_trunk, fg_feeder, fg_regional, fg_hv_poi, fg_sec_poi]:
        fg.add_to(m)
    folium.LayerControl(collapsed=False).add_to(m)
    m.save(out_html)
    log.info("  Master map saved.")


# ══════════════════════════════════════════════════════════════════════════════
#  XLSX EXPORT (4-sheet workbook, formulas on Summary sheets)
# ══════════════════════════════════════════════════════════════════════════════

def export_xlsx(gdf: gpd.GeoDataFrame, out_path: str, net_pop: int) -> None:
    """
    4-sheet XLSX workbook:
      Sheet 0 — Cover Sheet (methodology, v2 directives summary, limitations)
      Sheet 1 — Route-Level Plan (Groups A / B / C)
      Sheet 2 — Priority Band Summary (Excel SUMIF formulas)
      Sheet 3 — Route Type Summary (Excel SUMIF formulas)
    """
    log.info("Exporting XLSX → %s", out_path)
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    wb   = Workbook()
    thin = Side(style="thin", color="CCCCCC")
    thin_border = Border(left=thin, right=thin, top=thin, bottom=thin)
    S1   = "Route-Level Plan"

    # ── Cover Sheet ──────────────────────────────────────────────────────────
    ws0 = wb.active
    ws0.title = "Cover Sheet"
    cover_lines = [
        ("Srinagar / Kashmir Valley Public Transport — Route Frequency Plan v3", True, 16),
        ("Engine v3.0 Kashmir Fork | SSCL/CHALO Backbone Injection | May 2026", False, 11),
        ("", False, 11),
        ("KEY KASHMIR-SPECIFIC CHANGES FROM JAMMU v3:", True, 12),
        ("• SSCL e-bus backbone — 30 hardcoded trunks from CHALO data "
         "(15-min headway, not Jammu's 10-min BRT assumption).", False, 10),
        ("• Geographic re-centring: bounding box, lat thresholds, river coords "
         "rebuilt for Srinagar UA + Valley districts.", False, 10),
        ("• Population baseline: 1,660,000 (Srinagar UA 2024 projection) "
         "replaces Jammu 1,653,873.", False, 10),
        ("• 3-tier POI system + seasonal toggle: T1 (1.0), T2 (0.4), T3 "
         "(0.6 summer / 0.0 winter for tourism/yatra POIs).", False, 10),
        ("• Women-anchor +25% boost: calibrated to CHALO data showing 64.5% "
         "of riders are women (free-fare effect).", False, 10),
        ("• Kashmir social-obligation anchors: KP migrant camps + tertiary "
         "hospitals (SKIMS/SMHS/LD) + Khonmoh/Rangreth/Lassipora industrial.", False, 10),
        ("", False, 11),
        ("CORE DIRECTIVES (retained from Jammu v3):", True, 12),
        ("D1: Zero Route Truncation — ALL routes retained. >40km flagged "
         "as Regional_District with relaxed headways.", False, 10),
        ("D2: Realistic Cycle Times — congestion multiplier (2.0× Downtown "
         "Srinagar, 1.5× peri-urban) + stop penalties + 10% layover.", False, 10),
        ("D3: Minimum Viable Fleet — fleet below threshold raised directly. "
         "LPV eradicated — all fleet is HPV or MPV.", False, 10),
        ("D4: Trunk CDI gate = 30th percentile (aggressive). Anti-stranding: "
         "routes < 5 km ineligible for Trunk.", False, 10),
        ("D5: Population 95th-pct cap + 3-tier POI weights.", False, 10),
        ("D6: Full audit trail in log file. All functions modular.", False, 10),
        ("", False, 11),
        ("KASHMIR-SPECIFIC LIMITATIONS (Phase 1, to address in v4):", True, 11),
        ("• Walksheds are still Euclidean buffers. Dal Lake / Anchar / "
         "Hokersar / Jhelum barriers and slope not yet modelled.", False, 10),
        ("• Winter scenario is a binary flag (WINTER_SCENARIO). A full "
         "seasonal-stratified run needs four passes.", False, 10),
        ("• Per-route AFC validation against CHALO ridership is still "
         "manual. Automated calibration is a v4 task.", False, 10),
        ("• Security/convoy windows on NH-44 and military polygons not "
         "yet subtracted from operable network.", False, 10),
    ]
    for row_i, (text, bold, size) in enumerate(cover_lines, start=1):
        c = ws0.cell(row=row_i, column=1, value=text)
        c.font = Font(name="Calibri", bold=bold, size=size)
        c.alignment = Alignment(wrap_text=True)
    ws0.column_dimensions["A"].width = 100

    # ── Route-Level Plan ─────────────────────────────────────────────────────
    ws1 = wb.create_sheet(S1)

    # Build export dataframe — keep cols that exist
    df_out = gdf[[c for c in SHEET1_ALL_COLS if c in gdf.columns]].copy()

    # Write header
    for col_i, col_name in enumerate(df_out.columns, start=1):
        c = ws1.cell(row=1, column=col_i, value=col_name)
        c.font = Font(name="Calibri", bold=True, color="FFFFFF", size=10)
        c.fill = PatternFill("solid", fgColor="1F3864")
        c.alignment = Alignment(horizontal="center", vertical="center",
                                 wrap_text=True)
        c.border = thin_border
        ws1.column_dimensions[get_column_letter(col_i)].width = 16

    # Write data rows
    bool_cols = {"Social_Flag", "CMP_Trunk"}
    for row_i, (_, row_data) in enumerate(df_out.iterrows(), start=2):
        for col_i, col_name in enumerate(df_out.columns, start=1):
            val = row_data[col_name]
            if col_name in bool_cols:
                val = bool(val)
            elif isinstance(val, (np.integer,)):
                val = int(val)
            elif isinstance(val, (np.floating,)):
                val = float(val)
            c = ws1.cell(row=row_i, column=col_i, value=val)
            c.font = Font(name="Calibri", size=9)
            c.border = thin_border
            c.alignment = Alignment(horizontal="center", vertical="center")

    ws1.freeze_panes = "A2"

    # ── Priority Band Summary ────────────────────────────────────────────────
    ws2 = wb.create_sheet("Priority Band Summary")
    bands = [("HP — High Priority", "HP", "70AD47"),
             ("MP — Medium Priority", "MP", "FFD966"),
             ("LP — Low Priority", "LP", "FF7070")]
    hdrs  = ["Priority Band", "No. of Routes", "Est. Total Fleet",
             "HPV", "MPV", "Pop. Served (% of CMP 2024)"]
    for ci, h in enumerate(hdrs, 1):
        c = ws2.cell(row=1, column=ci, value=h)
        c.font = Font(name="Calibri", bold=True, color="FFFFFF", size=10)
        c.fill = PatternFill("solid", fgColor="1F3864")
        c.border = thin_border
        c.alignment = Alignment(horizontal="center")

    # Map column names to Excel letters
    col_letter = {col: get_column_letter(i+1)
                  for i, col in enumerate(df_out.columns)}

    def _col(name):
        return col_letter.get(name, "A")

    pb_col  = _col("Priority_Band")
    fr_col  = _col("Fleet_Required")
    hpv_col = _col("HPV_Count")
    mpv_col = _col("MPV_Count")
    pop_col = _col("Population_Served_Pct")   # CMP % — not raw raster count
    fa_col  = _col("Action_Taken")

    for ri, (label, code, colour) in enumerate(bands, 2):
        ws2.cell(row=ri, column=1, value=label).font = Font(
            name="Calibri", bold=True, color=f"00{colour}")
        formulas = [
            f"=COUNTIF('{S1}'!{pb_col}:{pb_col},\"{code}\")",
            f"=SUMIF('{S1}'!{pb_col}:{pb_col},\"{code}\",'{S1}'!{fr_col}:{fr_col})",
            f"=SUMIF('{S1}'!{pb_col}:{pb_col},\"{code}\",'{S1}'!{hpv_col}:{hpv_col})",
            f"=SUMIF('{S1}'!{pb_col}:{pb_col},\"{code}\",'{S1}'!{mpv_col}:{mpv_col})",
            # AVERAGEIF: avg % per route in this band — summing % makes no sense
            f"=IFERROR(AVERAGEIF('{S1}'!{pb_col}:{pb_col},\"{code}\",'{S1}'!{pop_col}:{pop_col}),0)",
        ]
        for ci, f in enumerate(formulas, 2):
            c = ws2.cell(row=ri, column=ci, value=f)
            c.font = Font(name="Calibri", size=10)
            c.fill = PatternFill("solid", fgColor=f"FF{colour}")
            c.alignment = Alignment(horizontal="center")
            c.border = thin_border

    # Totals row — fleet/HPV/MPV summed; pop is network average (not sum)
    total_row = len(bands) + 2
    ws2.cell(row=total_row, column=1, value="NETWORK AVG %").font = Font(
        name="Calibri", bold=True, color="FFFFFF")
    ws2.cell(row=total_row, column=1).fill = PatternFill("solid", fgColor="1F3864")
    for ci, (col_ref, use_avg) in enumerate(
            [(fr_col, False), (hpv_col, False), (mpv_col, False), (pop_col, True)], 3):
        formula = (f"=IFERROR(AVERAGE('{S1}'!{col_ref}:{col_ref}),0)"
                   if use_avg
                   else f"=SUM('{S1}'!{col_ref}:{col_ref})")
        c = ws2.cell(row=total_row, column=ci, value=formula)
        c.font = Font(name="Calibri", bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="1F3864")
        c.alignment = Alignment(horizontal="center")
        c.border = thin_border

    # ── Route Type Summary (v2 addition) ────────────────────────────────────
    ws3 = wb.create_sheet("Route Type Summary")
    rt_col   = _col("Route_Type")
    rt_types = [("Urban", "2196F3"), ("Peri_Urban", "66BB6A"),
                ("Regional_District", "9C27B0")]
    hdrs3 = ["Route Type", "No. of Routes", "Est. Total Fleet",
             "HPV", "MPV", "Pop. Served (% of CMP 2024)"]
    for ci, h in enumerate(hdrs3, 1):
        c = ws3.cell(row=1, column=ci, value=h)
        c.font = Font(name="Calibri", bold=True, color="FFFFFF", size=10)
        c.fill = PatternFill("solid", fgColor="1F3864")
        c.border = thin_border
        c.alignment = Alignment(horizontal="center")

    for ri, (rt_label, colour) in enumerate(rt_types, 2):
        ws3.cell(row=ri, column=1, value=rt_label).font = Font(
            name="Calibri", bold=True)
        formulas = [
            f"=COUNTIF('{S1}'!{rt_col}:{rt_col},\"{rt_label}\")",
            f"=SUMIF('{S1}'!{rt_col}:{rt_col},\"{rt_label}\",'{S1}'!{fr_col}:{fr_col})",
            f"=SUMIF('{S1}'!{rt_col}:{rt_col},\"{rt_label}\",'{S1}'!{hpv_col}:{hpv_col})",
            f"=SUMIF('{S1}'!{rt_col}:{rt_col},\"{rt_label}\",'{S1}'!{mpv_col}:{mpv_col})",
            # AVERAGEIF: avg % per route in this type — summing % makes no sense
            f"=IFERROR(AVERAGEIF('{S1}'!{rt_col}:{rt_col},\"{rt_label}\",'{S1}'!{pop_col}:{pop_col}),0)",
        ]
        for ci, f in enumerate(formulas, 2):
            c = ws3.cell(row=ri, column=ci, value=f)
            c.font = Font(name="Calibri", size=10)
            c.fill = PatternFill("solid", fgColor=f"FF{colour}")
            c.alignment = Alignment(horizontal="center")
            c.border = thin_border

    ws3.cell(row=len(rt_types) + 2, column=1,
             value="⚠ NOTE: Regional_District routes use relaxed headways "
                   "(60–90 min) per Directive 1. Fleet figures reflect this. "
                   "Pop. Served = avg % of CMP 2024 study-area population per route.").font = Font(
                       name="Calibri", italic=True, size=9, color="595959")

    # Reorder sheets
    wb.move_sheet("Cover Sheet", offset=-wb.index(wb["Cover Sheet"]))
    wb.save(out_path)
    log.info("  XLSX written: %d data rows, 4 sheets.", len(df_out))


def export_passenger_impact(gdf: gpd.GeoDataFrame, out_path: str) -> None:
    log.info("Exporting Passenger Impact → %s", out_path)
    active = gdf[gdf["Action_Taken"] != "MERGED_INTO_TRUNK"].copy()
    cols   = [c for c in [
        "New_Route_ID", "Route_Name", "Action_Taken", "Route_Type",
        "Priority_Band", "Headway_Min", "Fleet_Required",
        "HPV_Count", "MPV_Count",
        "CMP_Trunk", "CMP_Route_ID",
        "Population_Served", "Social_Flag",
    ] if c in active.columns]
    active[cols].to_csv(out_path, index=False, encoding="utf-8-sig")
    log.info("  Passenger impact written: %d rows.", len(active))


# ══════════════════════════════════════════════════════════════════════════════
#  ORCHESTRATOR
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    t0 = time.perf_counter()
    log.info("=" * 70)
    log.info("  Srinagar / Kashmir Valley Transit Rationalisation — ENGINE v3.0 (Kashmir Fork)")
    log.info("  SSCL/CHALO Backbone Injection + Kashmir Geographic Recentre | May 2026")
    log.info("=" * 70)
    log.info("  Scenario              : %s",
             "WINTER (Chillai Kalan)" if WINTER_SCENARIO else "SUMMER / SHOULDER")
    log.info("  Walkshed (effective)  : %d m  (POI buffer: %d m)",
             WALK_CATCHMENT_M, POI_BUFFER_M)
    log.info("  Tier-3 POI weight     : %.2f (tourism POIs)", POI_TIER3_WEIGHT)
    log.info("  Women-anchor boost    : %.0f%% (CHALO: %.1f%% female ridership)",
             (WOMEN_ANCHOR_BOOST - 1) * 100, CHALO_WOMEN_SHARE * 100)
    log.info("  CHALO observed peak   : %d pax/hr @ %d:00 (citywide)",
             CHALO_PEAK_PAX_PER_HOUR, CHALO_PEAK_HOUR)
    log.info("  CHALO op ratio        : %.1f%% (operated / scheduled KM)",
             CHALO_OP_RATIO * 100)
    log.info("=" * 70)
    log.info("  Directive 1: Zero Route Truncation — ALL routes processed")
    log.info("  Directive 2: Realistic Cycle Times (Srinagar congestion zones)")
    log.info("  Directive 3: Min Fleet = %d (floor, no LPV downgrade)",
             MIN_FLEET_THRESHOLD)
    log.info("  Directive 4: Trunk CDI gate = %dth percentile (aggressive) | "
             "Anti-stranding: %.1f km min | SSCL connectivity bonus: %.1fx",
             TRUNK_CDI_GATE_PERCENTILE, TRUNK_MIN_LENGTH_KM, CMP_CONNECTIVITY_BONUS)
    log.info("  Directive 5: Pop cap = %dth percentile | POI tiers: 1.0/0.4/%.1f",
             POP_CAP_PERCENTILE, POI_TIER3_WEIGHT)
    log.info("  Directive 6: Full audit logging throughout")
    log.info("  SSCL Injection: %d e-bus routes hardcoded TRUNK/HP @ %d-min headway",
             len(CMP_TRUNK_ROUTES), SSCL_TRUNK_HEADWAY_MIN)
    log.info("  Vehicle Split: Trunk=85%%HPV+15%%MPV | Feeder=100%%MPV | LPV=0")
    log.info("=" * 70)

    if not _HAS_JENKSPY:
        log.warning("  ⚠ jenkspy not installed — priority bands will use "
                    "percentile fallback. Run: pip install jenkspy")

    # ── PHASE 1: Data Ingestion, OSRM, Geometry ───────────────────────────
    log.info("\n── PHASE 1: Data Ingestion & OSRM ──────────────────────────────────")
    df_routes    = load_routes(ROUTES_CSV)
    # --- SSCL E-BUS ROUTE INJECTION (replaces Jammu CMP synthetic routes) ----
    # All 30 SSCL routes from CHALO Apr 2026 data with approximated lat/lon
    # for major Srinagar / Valley terminals. These will be matched by
    # inject_cmp_trunk_routes() and forced to UPGRADED_TO_TRUNK / HP / 15-min.
    log.info("  Injecting all %d SSCL e-bus routes (CHALO Apr 2026)…",
             len(CMP_TRUNK_ROUTES))
    synthetic_routes = pd.DataFrame([
        # SSCL-01: Parimpora to Harwan via Brein Nishat
        {"Route_ID": "SSCL-01", "Route_Name": "Parimpora to Harwan via Brein Nishat",
         "Start_Lat": 34.1112, "Start_Lon": 74.7475,
         "End_Lat":   34.1481, "End_Lon":   74.9101},
        # SSCL-02: Batamaloo to Nasrullah Pora via Jehangir Chowk, Rambagh, Hyderpora
        {"Route_ID": "SSCL-02", "Route_Name": "Batamaloo to Nasrullah Pora via Jehangir Chowk Rambagh Hyderpora",
         "Start_Lat": 34.0689, "Start_Lon": 74.7795,
         "End_Lat":   34.0440, "End_Lon":   74.7320},
        # SSCL-03: Batamaloo to Hazratbal via Khanyar
        {"Route_ID": "SSCL-03", "Route_Name": "Batamaloo to Hazratbal via Khanyar",
         "Start_Lat": 34.0689, "Start_Lon": 74.7795,
         "End_Lat":   34.1342, "End_Lon":   74.8451},
        # SSCL-04: Batamaloo to Chadoora Chowk via Jehangir Chowk
        {"Route_ID": "SSCL-04", "Route_Name": "Batamaloo to Chadoora Chowk via Jehangir Chowk",
         "Start_Lat": 34.0689, "Start_Lon": 74.7795,
         "End_Lat":   34.0511, "End_Lon":   74.7124},
        # SSCL-05: LD Hospital to Pandach via Jehangir Chowk, Dalgate, Khanyar
        {"Route_ID": "SSCL-05", "Route_Name": "LD Hospital to Pandach via Jehangir Chowk Dalgate Khanyar",
         "Start_Lat": 34.0822, "Start_Lon": 74.8059,
         "End_Lat":   34.1611, "End_Lon":   74.8167},
        # SSCL-06: Pantha Chowk to Narbal Crossing via Sonwar, Jehangir Chowk, Qamarwari
        {"Route_ID": "SSCL-06", "Route_Name": "Pantha Chowk to Narbal Crossing via Sonwar Jehangir Chowk Qamarwari",
         "Start_Lat": 34.0445, "Start_Lon": 74.8341,
         "End_Lat":   34.1052, "End_Lon":   74.6809},
        # SSCL-07: Batamaloo to Drussu Pulwama via Marwal
        {"Route_ID": "SSCL-07", "Route_Name": "Batamaloo to Drussu Pulwama via Marwal",
         "Start_Lat": 34.0689, "Start_Lon": 74.7795,
         "End_Lat":   33.8830, "End_Lon":   74.9250},
        # SSCL-08: Batamaloo to Budgam Railway Station via Khumeni Chowk
        {"Route_ID": "SSCL-08", "Route_Name": "Batamaloo to Budgam Railway Station via Khumeni Chowk",
         "Start_Lat": 34.0689, "Start_Lon": 74.7795,
         "End_Lat":   33.9908, "End_Lon":   74.7115},
        # SSCL-09: Parimpora to Naseem Bagh via Noorbagh, Gojwara, Mill Stop
        {"Route_ID": "SSCL-09", "Route_Name": "Parimpora to Naseem Bagh via Noorbagh Gojwara Mill Stop",
         "Start_Lat": 34.1112, "Start_Lon": 74.7475,
         "End_Lat":   34.1334, "End_Lon":   74.8385},
        # SSCL-10: Pantha Chowk to Agri Kalan Kanihama via Bypass
        {"Route_ID": "SSCL-10", "Route_Name": "Pantha Chowk to Agri Kalan Kanihama via Bypass",
         "Start_Lat": 34.0445, "Start_Lon": 74.8341,
         "End_Lat":   34.0980, "End_Lon":   74.6500},
        # SSCL-11: Old City Loop (Downtown Srinagar circular)
        {"Route_ID": "SSCL-11", "Route_Name": "Old City Loop Downtown Srinagar",
         "Start_Lat": 34.0942, "Start_Lon": 74.8128,
         "End_Lat":   34.1027, "End_Lon":   74.8088},
        # SSCL-12: Rangreth to District Court Srinagar via Barzulla, Jehangir Chowk
        {"Route_ID": "SSCL-12", "Route_Name": "Rangreth to District Court Srinagar via Barzulla Jehangir Chowk",
         "Start_Lat": 34.0244, "Start_Lon": 74.7906,
         "End_Lat":   34.1006, "End_Lon":   74.7975},
        # SSCL-13: Batamaloo to Beehama Ganderbal via Hazratbal, Zakura
        {"Route_ID": "SSCL-13", "Route_Name": "Batamaloo to Beehama Ganderbal via Hazratbal Zakura",
         "Start_Lat": 34.0689, "Start_Lon": 74.7795,
         "End_Lat":   34.2403, "End_Lon":   74.8211},
        # SSCL-14: TRC to Central University Ganderbal via Karan Nagar, Zoonimar, 90ft Road
        {"Route_ID": "SSCL-14", "Route_Name": "TRC to Central University Ganderbal via Karan Nagar Zoonimar 90ft Road",
         "Start_Lat": 34.0833, "Start_Lon": 74.8089,
         "End_Lat":   34.2725, "End_Lon":   74.8245},
        # SSCL-15: TRC to Pulwama via Nowgam, Kaanipora
        {"Route_ID": "SSCL-15", "Route_Name": "TRC to Pulwama via Nowgam Kaanipora",
         "Start_Lat": 34.0833, "Start_Lon": 74.8089,
         "End_Lat":   33.8716, "End_Lon":   74.8983},
        # SSCL-16: Batamaloo Circular via Khonmoh
        {"Route_ID": "SSCL-16", "Route_Name": "Batamaloo Circular via Khonmoh",
         "Start_Lat": 34.0689, "Start_Lon": 74.7795,
         "End_Lat":   34.0419, "End_Lon":   74.8825},
        # SSCL-17: Batamaloo to Womens College Batpora via Rainawari
        {"Route_ID": "SSCL-17", "Route_Name": "Batamaloo to Womens College Batpora via Rainawari",
         "Start_Lat": 34.0689, "Start_Lon": 74.7795,
         "End_Lat":   34.0875, "End_Lon":   74.8083},
        # SSCL-18: JKPDC Jehangir Chowk to Wadwan
        {"Route_ID": "SSCL-18", "Route_Name": "JKPDC Jehangir Chowk to Wadwan",
         "Start_Lat": 34.0772, "Start_Lon": 74.8035,
         "End_Lat":   34.0200, "End_Lon":   74.9300},
        # SSCL-19: Pantha Chowk to Sumbal
        {"Route_ID": "SSCL-19", "Route_Name": "Pantha Chowk to Sumbal",
         "Start_Lat": 34.0445, "Start_Lon": 74.8341,
         "End_Lat":   34.2649, "End_Lon":   74.6606},
        # SSCL-20: Pantha Chowk to Safapora
        {"Route_ID": "SSCL-20", "Route_Name": "Pantha Chowk to Safapora",
         "Start_Lat": 34.0445, "Start_Lon": 74.8341,
         "End_Lat":   34.3592, "End_Lon":   74.7406},
        # SSCL-21: Batamaloo to Arath
        {"Route_ID": "SSCL-21", "Route_Name": "Batamaloo to Arath",
         "Start_Lat": 34.0689, "Start_Lon": 74.7795,
         "End_Lat":   34.0414, "End_Lon":   74.8462},
        # SSCL-22: Batamaloo to Khrew Bus Stand
        {"Route_ID": "SSCL-22", "Route_Name": "Batamaloo to Khrew Bus Stand",
         "Start_Lat": 34.0689, "Start_Lon": 74.7795,
         "End_Lat":   34.0407, "End_Lon":   74.9269},
        # SSCL-23: Batamaloo to Charesharief via Chadoora
        {"Route_ID": "SSCL-23", "Route_Name": "Batamaloo to Charesharief via Chadoora",
         "Start_Lat": 34.0689, "Start_Lon": 74.7795,
         "End_Lat":   33.8806, "End_Lon":   74.7372},
        # SSCL-24: Pantha Chowk to Palhalan (extends to Sangrama / Sopore)
        {"Route_ID": "SSCL-24", "Route_Name": "Pantha Chowk to Palhalan extendable to Sangrama Sopore",
         "Start_Lat": 34.0445, "Start_Lon": 74.8341,
         "End_Lat":   34.1825, "End_Lon":   74.5450},
        # SSCL-25: Batamaloo to Dadsara Tral via Awantipora
        {"Route_ID": "SSCL-25", "Route_Name": "Batamaloo to Dadsara Tral via Awantipora",
         "Start_Lat": 34.0689, "Start_Lon": 74.7795,
         "End_Lat":   33.9300, "End_Lon":   75.1100},
        # SSCL-26: Batamaloo to Kangan via Hazratbal, Manigam
        {"Route_ID": "SSCL-26", "Route_Name": "Batamaloo to Kangan via Hazratbal Manigam",
         "Start_Lat": 34.0689, "Start_Lon": 74.7795,
         "End_Lat":   34.2683, "End_Lon":   74.9962},
        # SSCL-27: Batamaloo to Manigam
        {"Route_ID": "SSCL-27", "Route_Name": "Batamaloo to Manigam",
         "Start_Lat": 34.0689, "Start_Lon": 74.7795,
         "End_Lat":   34.2272, "End_Lon":   74.9536},
        # SSCL-28: Batamaloo to Pinglena via Galandar Pampore
        {"Route_ID": "SSCL-28", "Route_Name": "Batamaloo to Pinglena Pampore via Galandar",
         "Start_Lat": 34.0689, "Start_Lon": 74.7795,
         "End_Lat":   33.9999, "End_Lon":   74.9356},
        # SSCL-29: Pantha Chowk to Panzinara
        {"Route_ID": "SSCL-29", "Route_Name": "Pantha Chowk to Panzinara",
         "Start_Lat": 34.0445, "Start_Lon": 74.8341,
         "End_Lat":   34.0593, "End_Lon":   74.7647},
        # SSCL-30: Batamaloo to DC Office Budgam
        {"Route_ID": "SSCL-30", "Route_Name": "Batamaloo to DC Office Budgam",
         "Start_Lat": 34.0689, "Start_Lon": 74.7795,
         "End_Lat":   33.9908, "End_Lon":   74.7115},
    ])

    # Fill defaults so the rest of the pipeline doesn't break
    synthetic_routes["Minibus_Count"]      = 0
    synthetic_routes["Standard_Bus_Count"] = 0
    synthetic_routes["Via_Coordinates"]    = None

    # Append to the main dataframe
    df_routes = pd.concat([df_routes, synthetic_routes], ignore_index=True)
    log.info("  %d SSCL routes appended (will be force-matched to TRUNK in inject step).",
             len(synthetic_routes))
    # ----------------------------------
    df_routes    = truncate_routes_to_bbox(df_routes)
    gdf_pois     = load_pois(POIS_CSV)
    osrm_results = fetch_all_osrm(df_routes)
    gdf          = apply_geometries(df_routes, osrm_results)
    gdf          = impute_fleet(gdf)

    # ── SSCL INJECTION: Force 30 CHALO/SSCL e-bus routes to TRUNK/HP ───────
    log.info("\n── SSCL BACKBONE INJECTION ──────────────────────────────────────────")
    gdf = inject_cmp_trunk_routes(gdf)

    # ── PHASE 2: Spatial Analysis ─────────────────────────────────────────
    log.info("\n── PHASE 2: Spatial Analysis ────────────────────────────────────────")
    gdf = build_catchments(gdf)
    gdf = compute_population(gdf, RASTER_PATH)
    gdf = count_weighted_poi_scores(gdf, gdf_pois)
    gdf = compute_junction_penalties(gdf)
    gdf = compute_cycle_times(gdf)          # DIRECTIVE 2: Realistic cycle times

    # ── STEPS 1 & 2: Normalise Demand Scores ─────────────────────────────
    log.info("\n── STEPS 1–2: Normalised Demand Scores ─────────────────────────────")
    gdf = step1_normalise_population_score(gdf)   # DIRECTIVE 5: 95th pct cap
    gdf = step2_normalise_poi_score(gdf)          # DIRECTIVE 5: 2-tier weights

    # ── Route Classification ──────────────────────────────────────────────
    log.info("\n── ROUTE CLASSIFICATION ─────────────────────────────────────────────")
    freq_scores    = compute_frequency_scores(gdf)
    gdf            = apportion_route_population(gdf, freq_scores)
    overlap_matrix = compute_overlap_matrix(gdf)
    gdf            = cluster_routes(gdf, overlap_matrix)
    gdf            = backfill_overlap_metric(gdf, overlap_matrix)
    gdf            = classify_routes(gdf, freq_scores, overlap_matrix)  # v3: 30th pct + CMP bonus
    gdf            = apply_terminal_capacity(gdf, gdf_pois)

    # ── STEPS 3–9: CDI Pipeline ──────────────────────────────────────────
    log.info("\n── STEPS 3–9: CDI Pipeline ──────────────────────────────────────────")
    gdf = step3_compute_road_multiplier(gdf)
    gdf = step4a_compute_final_cdi(gdf)
    gdf = step4b_compute_social_flag(gdf)
    gdf = step5_assign_priority_bands(gdf)
    gdf = step6_assign_headways(gdf)         # CMP override: 10-min hardcoded
    gdf = step8_compute_fleet_required(gdf)  # v3: floor at MIN, no LPV downgrade
    gdf = step9_compute_vehicle_split(gdf)   # v3: Trunk=85/15 | Feeder=100% MPV
    gdf = zero_merged_route_fleet(gdf)

    # ── QC ────────────────────────────────────────────────────────────────
    log.info("\n── QC CHECKS ────────────────────────────────────────────────────────")
    run_all_qc_checks(gdf)

    # ── Network Totals ────────────────────────────────────────────────────
    net_pop       = compute_network_population_total(gdf, RASTER_PATH)
    network_score = compute_network_score(gdf, net_pop)

    # ── PHASE 3: Log ──────────────────────────────────────────────────────
    log.info("\n── PHASE 3: Rationalisation Log ─────────────────────────────────────")
    generate_log(gdf, LOG_CSV)

    # ── PHASE 4: Export ───────────────────────────────────────────────────
    log.info("\n── PHASE 4: Cartography & Export ────────────────────────────────────")
    build_master_map(gdf, gdf_pois, RASTER_PATH, MASTER_MAP_HTML,
                     net_pop, network_score)
    file_map = build_individual_maps(gdf, gdf_pois, OUTPUT_DIR)
    export_csv(gdf, file_map, ROUTES_OUT_CSV)
    export_xlsx(gdf, out_path=ROUTES_OUT_XLSX, net_pop=net_pop)
    export_passenger_impact(gdf, PASSENGER_IMPACT_CSV)
    export_geojson(gdf, ROUTES_GEOJSON)

    elapsed = time.perf_counter() - t0
    active  = gdf[gdf["Action_Taken"] != "MERGED_INTO_TRUNK"]
    cmp_n   = int(gdf.get("CMP_Trunk", pd.Series(False, index=gdf.index)).sum())

    log.info("\n" + "=" * 70)
    log.info("  PIPELINE v3 COMPLETE  (%.1f s)", elapsed)
    log.info("  Total routes in dataset : %d (no length truncation — D1)",
             len(gdf))
    log.info("  Active routes           : %d  (Trunk: %d  Feeder: %d  Merged: %d)",
             len(active),
             (gdf["Action_Taken"] == "UPGRADED_TO_TRUNK").sum(),
             (gdf["Action_Taken"] == "RETAINED_AS_FEEDER").sum(),
             (gdf["Action_Taken"] == "MERGED_INTO_TRUNK").sum())
    log.info("  SSCL backbone trunks    : %d / %d matched (%d-min headway)",
             cmp_n, len(CMP_TRUNK_ROUTES), SSCL_TRUNK_HEADWAY_MIN)
    log.info("  Route types             : Urban=%d  Peri_Urban=%d  "
             "Regional_District=%d",
             (gdf["Route_Type"] == "Urban").sum(),
             (gdf["Route_Type"] == "Peri_Urban").sum(),
             (gdf["Route_Type"] == "Regional_District").sum())
    log.info("  Priority bands          : HP=%d  MP=%d  LP=%d  (Social: %d)",
             (active["Priority_Band"] == "HP").sum(),
             (active["Priority_Band"] == "MP").sum(),
             (active["Priority_Band"] == "LP").sum(),
             active["Social_Flag"].sum())
    log.info("  Total fleet             : %d buses (HPV: %d  MPV: %d  LPV: 0 eradicated)",
             int(active["Fleet_Required"].sum()),
             int(active["HPV_Count"].sum()),
             int(active["MPV_Count"].sum()))
    log.info("  Trunk vehicle split     : 85%% HPV / 15%% MPV")
    log.info("  Feeder vehicle split    : 100%% MPV")
    log.info("  Network pop.            : %s residents  (%.2f%% of CMP %d total: %s)",
             f"{net_pop:,}",
             min(100.0, net_pop / CMP_TOTAL_POPULATION * 100),
             CMP_REFERENCE_YEAR,
             f"{CMP_TOTAL_POPULATION:,}")
    log.info("  Jenks engine            : %s",
             "jenkspy" if _HAS_JENKSPY else "percentile fallback")
    log.info("  Outputs:")
    log.info("    %-44s  4-sheet workbook", ROUTES_OUT_XLSX)
    log.info("    %-44s  sidebar + KPI map", MASTER_MAP_HTML)
    log.info("    %-44s  full audit log", LOG_CSV)
    log.info("    %-44s  passenger impact", PASSENGER_IMPACT_CSV)
    log.info("    %-44s  operational CSV", ROUTES_OUT_CSV)
    log.info("    %-44s  GeoJSON network", ROUTES_GEOJSON)
    log.info("=" * 70)


if __name__ == "__main__":
    main()
