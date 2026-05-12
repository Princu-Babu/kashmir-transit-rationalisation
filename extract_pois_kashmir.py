"""
extract_pois_kashmir.py  —  Kashmir POI Extractor for transit_kashmir_v3.py
================================================================================
Pulls POIs from OpenStreetMap (via Overpass API), classifies each one into
the exact Kashmir 3-tier vocabulary that transit_kashmir_v3.py expects, then
snaps each POI to the nearest road using the local OSRM server on port 5000
(Docker). POIs that are not reachable from any road (> MAX_ROAD_SNAP_M from
the network — typical for centroids in the middle of Dal Lake, mountain
summits, or cantonment interiors) are dropped from the output.

WHAT THIS SCRIPT IS / IS NOT:
  • IS:     A POI discovery + classification + road-accessibility filter.
  • IS NOT: An OSRM POI service (OSRM has no POI endpoint; it's a router).
            The POI data comes from Overpass; OSRM is only used to snap and
            filter the POIs to the actual driveable road network.

OUTPUT SCHEMA (matches transit_kashmir_v3.py / load_pois() exactly):
  lat, lon, name, category, importance, osm_id, osm_type, snap_distance_m, source

  • lat, lon         — raw POI coordinate (used by the transit script's 250m
                       buffer for POI scoring; NOT snapped to road)
  • name             — display name (from OSM, or category fallback)
  • category         — exact match against POI_TIER1/2/3_CATEGORIES sets
  • importance       — "high" (Tier 1) / "medium" (Tier 2) / "seasonal" (Tier 3)
                       Empty for unrecognized → transit script falls back to
                       category lookup, which then falls back to Tier 2 weight.
  • osm_id, osm_type — provenance (node/way/relation + OSM ID)
  • snap_distance_m  — distance from raw POI to nearest road (audit)
  • source           — always "OSM via Overpass"

USAGE:
  python extract_pois_kashmir.py                      # defaults: pois.csv
  python extract_pois_kashmir.py --no-osrm            # skip road-snap step
  python extract_pois_kashmir.py --output mypois.csv  # custom output path
  python extract_pois_kashmir.py --overpass-url ...   # use a different mirror

REQUIREMENTS:
  pip install requests pandas
  Docker OSRM running on http://localhost:5000 (or use --no-osrm)
================================================================================
"""
import argparse
import csv
import json
import logging
import math
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests


# ──────────────────────────────────────────────────────────────────────────────
#  CONFIG — Tune at the top, not in the logic
# ──────────────────────────────────────────────────────────────────────────────

# Bounding box — IDENTICAL to transit_kashmir_v3.py BOUNDS_*
# Square enclosing Srinagar UA + Budgam + Ganderbal + reach to
# Sopore/Pulwama/Anantnag. ~100 km × ~80 km.
BBOX = {
    "min_lat": 33.50,
    "max_lat": 34.50,
    "min_lon": 74.40,
    "max_lon": 75.20,
}

# Endpoints
OVERPASS_URL_DEFAULT = "https://overpass-api.de/api/interpreter"
OVERPASS_FALLBACKS   = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.openstreetmap.fr/api/interpreter",
]
OSRM_URL_DEFAULT     = "http://localhost:5000"

# OSRM behaviour
OSRM_TIMEOUT_S       = 6
OSRM_MAX_WORKERS     = 12
MAX_ROAD_SNAP_M      = 800   # POIs > this from any road are dropped
                              # (Dal Lake interiors, mountain summits,
                              #  inside cantonment polygons, etc.)

# Overpass behaviour
OVERPASS_TIMEOUT_S   = 600   # Server-side timeout (Overpass language)
OVERPASS_HTTP_TIMEOUT = 700  # Client-side HTTP timeout (>= server timeout)
OVERPASS_RETRIES     = 3
OVERPASS_RETRY_WAIT  = 30    # seconds between retries

# Output
OUTPUT_DEFAULT       = "pois.csv"


# ──────────────────────────────────────────────────────────────────────────────
#  KASHMIR CATEGORY VOCABULARY
#  Must match transit_kashmir_v3.py POI_TIER{1,2,3}_CATEGORIES exactly.
# ──────────────────────────────────────────────────────────────────────────────

# Tier 1: year-round mass attractors (transit_kashmir_v3 weight = 1.0)
TIER1 = frozenset({
    "railway_station", "railway", "train_station", "rail",
    "isbt", "bus_station", "bus_terminal", "transit_hub",
    "trc", "tourist_reception_centre",
    "batamaloo_bus_stand", "parimpora_bus_stand", "pantha_chowk_depot",
    "nishat_bus_terminal",
    "hospital", "govt_hospital", "medical_college", "major_hospital",
    "skims", "skims_soura", "smhs_hospital", "lal_ded_hospital",
    "bone_and_joint_hospital", "jlnm_rainawari", "chest_diseases_hospital",
    "gmc_srinagar",
    "mall", "supermarket", "major_market", "regal_chowk", "lal_chowk",
    "polo_view", "residency_road", "amira_kadal", "city_centre",
    "jamia_masjid", "hazratbal_shrine", "khanqah", "dastgeer_sahib",
    "shah_e_hamdan",
    "industrial_estate", "factory", "industry", "sicop",
    "khonmoh_industrial", "rangreth_industrial", "lassipora_industrial",
    "kp_migrant_camp", "kp_township", "sheikhpora_camp", "vessu_camp",
    "mattan_camp", "veerwan_camp",
    "civil_secretariat", "high_court", "rajbhawan", "raj_bhawan",
    "university_of_kashmir", "iist_awantipora", "central_university_kashmir",
    "nit_srinagar", "smvd",
})

# Tier 2: secondary anchors (transit_kashmir_v3 weight = 0.4)
TIER2 = frozenset({
    "college", "campus", "engineering_college", "school",
    "higher_education", "polytechnic", "iti", "degree_college",
    "market", "commercial", "wholesale_market", "small_shop",
    "haba_kadal_market", "maharaj_gunj",
    "army", "bsf", "crpf", "military", "cantonment",
    "stadium", "bakshi_stadium", "polo_ground",
    "government", "govt_office", "court", "clinic", "small_medical",
    "dispensary", "museum", "police_station",
    "park", "library", "auditorium", "tagore_hall",
})

# Tier 3: seasonal (transit_kashmir_v3 weight = 0.6 summer / 0.0 winter)
TIER3 = frozenset({
    "tourist_spot", "tourist_gate", "shikara_ghat",
    "dal_lake_gate", "boulevard_gate", "nigeen_lake_gate",
    "mughal_garden", "nishat_garden", "shalimar_garden",
    "chashme_shahi", "pari_mahal", "tulip_garden", "harwan_garden",
    "gulmarg", "pahalgam", "sonmarg", "doodhpathri", "yusmarg",
    "gondola", "ski_resort", "ropeway",
    "amarnath_base_camp", "kheer_bhawani",
    "houseboat", "tourist_hotel",
})

# Women-anchor categories (transit_kashmir_v3 +25% boost on top of tier weight)
WOMEN_ANCHOR = frozenset({
    "womens_college", "women_college", "girls_school", "girls_college",
    "maternity_hospital", "gynaec_hospital", "mch_centre",
    "anganwadi", "women_market", "ladies_market",
})


# ──────────────────────────────────────────────────────────────────────────────
#  NAME-BASED OVERRIDES
#  Specific Kashmir landmarks that deserve a more precise category than the
#  generic OSM tag suggests. Checked FIRST, before OSM tag mapping.
#  Each entry: (compiled regex on lowercased name, category, importance).
# ──────────────────────────────────────────────────────────────────────────────
NAME_OVERRIDES: List[Tuple[re.Pattern, str, str]] = [
    # ─── Major hospitals ────────────────────────────────────────────────────
    (re.compile(r"\bskims\b|sher-?i-?kashmir.*institute"), "skims_soura",              "high"),
    (re.compile(r"\bsmhs\b|shri maharaja hari singh"),     "smhs_hospital",            "high"),
    (re.compile(r"lal ?ded"),                              "lal_ded_hospital",         "high"),
    (re.compile(r"\bjlnm\b|jawaharlal nehru memorial"),    "jlnm_rainawari",           "high"),
    (re.compile(r"bone (and|&) joint"),                    "bone_and_joint_hospital",  "high"),
    (re.compile(r"chest diseases?|chd hospital"),          "chest_diseases_hospital",  "high"),
    (re.compile(r"gmc\b.*srinagar|govt\.? medical college.*srinagar"),
                                                            "gmc_srinagar",             "high"),
    (re.compile(r"maternity|gynae"),                       "maternity_hospital",       "high"),
    # ─── Universities / major colleges ──────────────────────────────────────
    (re.compile(r"university of kashmir|kashmir university"), "university_of_kashmir", "high"),
    (re.compile(r"\biust\b|islamic university.*science.*tech|awantipora.*university"),
                                                            "iist_awantipora",          "high"),
    (re.compile(r"central university.*kashmir|cu\b.*kashmir"),
                                                            "central_university_kashmir","high"),
    (re.compile(r"\bnit\b.*srinagar|national institute.*technology.*srinagar"),
                                                            "nit_srinagar",             "high"),
    (re.compile(r"women'?s? college|girls'? college"),     "girls_college",            "medium"),
    (re.compile(r"girls'? (high )?school"),                "girls_school",             "medium"),
    # ─── Religious / shrines (year-round, Tier 1) ──────────────────────────
    (re.compile(r"hazratbal"),                             "hazratbal_shrine",         "high"),
    (re.compile(r"jamia masjid|jama masjid|jamia mosque"), "jamia_masjid",             "high"),
    (re.compile(r"khanqah"),                               "khanqah",                  "high"),
    (re.compile(r"dastgeer sahib|dastageer"),              "dastgeer_sahib",           "high"),
    (re.compile(r"shah[- ]?e[- ]?hamdan"),                 "shah_e_hamdan",            "high"),
    # ─── Tourism (Tier 3 seasonal) — gardens, gates, gondola ───────────────
    (re.compile(r"tulip garden|indira gandhi.*tulip"),     "tulip_garden",             "seasonal"),
    (re.compile(r"nishat (bagh|garden)"),                  "nishat_garden",            "seasonal"),
    (re.compile(r"shalimar (bagh|garden)"),                "shalimar_garden",          "seasonal"),
    (re.compile(r"chashm[ae]? shahi"),                     "chashme_shahi",            "seasonal"),
    (re.compile(r"pari mahal"),                            "pari_mahal",               "seasonal"),
    (re.compile(r"harwan (garden|bagh)"),                  "harwan_garden",            "seasonal"),
    (re.compile(r"gondola|cable ?car|ropeway"),            "gondola",                  "seasonal"),
    (re.compile(r"gulmarg"),                               "gulmarg",                  "seasonal"),
    (re.compile(r"pahalgam"),                              "pahalgam",                 "seasonal"),
    (re.compile(r"sonmarg|sonamarg"),                      "sonmarg",                  "seasonal"),
    (re.compile(r"doodhpathri"),                           "doodhpathri",              "seasonal"),
    (re.compile(r"yusmarg|yousmarg"),                      "yusmarg",                  "seasonal"),
    (re.compile(r"kheer bhawani"),                         "kheer_bhawani",            "seasonal"),
    (re.compile(r"amarnath"),                              "amarnath_base_camp",       "seasonal"),
    (re.compile(r"shikara ghat|ghat"),                     "shikara_ghat",             "seasonal"),
    (re.compile(r"dal lake|dal gate"),                     "dal_lake_gate",            "seasonal"),
    (re.compile(r"boulevard"),                             "boulevard_gate",           "seasonal"),
    (re.compile(r"nigeen"),                                "nigeen_lake_gate",         "seasonal"),
    (re.compile(r"houseboat"),                             "houseboat",                "seasonal"),
    # ─── Transit hubs ──────────────────────────────────────────────────────
    (re.compile(r"\btrc\b|tourist reception"),             "tourist_reception_centre", "high"),
    (re.compile(r"parimpora.*bus|parimpora bus stand"),    "parimpora_bus_stand",      "high"),
    (re.compile(r"batamaloo.*bus|batamaloo bus stand"),    "batamaloo_bus_stand",      "high"),
    (re.compile(r"pantha ?chowk.*(bus|depot)"),            "pantha_chowk_depot",       "high"),
    (re.compile(r"nishat.*(bus|terminal)"),                "nishat_bus_terminal",      "high"),
    # ─── Commercial hubs (Tier 1) ──────────────────────────────────────────
    (re.compile(r"lal chowk|lal[- ]chowk"),                "lal_chowk",                "high"),
    (re.compile(r"polo view"),                             "polo_view",                "high"),
    (re.compile(r"regal chowk"),                           "regal_chowk",              "high"),
    (re.compile(r"residency road"),                        "residency_road",           "high"),
    (re.compile(r"amira kadal"),                           "amira_kadal",              "high"),
    (re.compile(r"city centre|city center"),               "city_centre",              "high"),
    (re.compile(r"maharaj gunj"),                          "maharaj_gunj",             "medium"),
    (re.compile(r"hab[ab]a kadal"),                        "haba_kadal_market",        "medium"),
    # ─── Government Tier 1 ─────────────────────────────────────────────────
    (re.compile(r"civil secretariat|secretariat"),         "civil_secretariat",        "high"),
    (re.compile(r"high court"),                            "high_court",               "high"),
    (re.compile(r"raj ?bhawan"),                           "raj_bhawan",               "high"),
    # ─── Industrial estates ────────────────────────────────────────────────
    (re.compile(r"khonmoh.*indust|industrial.*khonmoh"),   "khonmoh_industrial",       "high"),
    (re.compile(r"rangreth.*indust|industrial.*rangreth"), "rangreth_industrial",      "high"),
    (re.compile(r"lassipora.*indust|industrial.*lassipora"),"lassipora_industrial",     "high"),
    (re.compile(r"sicop"),                                 "sicop",                    "high"),
    # ─── KP migrant townships ──────────────────────────────────────────────
    (re.compile(r"sheikhpora"),                            "sheikhpora_camp",          "high"),
    (re.compile(r"vessu"),                                 "vessu_camp",               "high"),
    (re.compile(r"mattan"),                                "mattan_camp",              "high"),
    (re.compile(r"veerwan"),                               "veerwan_camp",             "high"),
    (re.compile(r"kp (camp|township|colony)|migrant (camp|township)"),
                                                            "kp_township",              "high"),
    # ─── Stadia / venues (Tier 2) ──────────────────────────────────────────
    (re.compile(r"bakshi stadium"),                        "bakshi_stadium",           "medium"),
    (re.compile(r"polo ground"),                           "polo_ground",              "medium"),
    (re.compile(r"tagore hall"),                           "tagore_hall",              "medium"),
    # ─── Anganwadi (women-anchor) ──────────────────────────────────────────
    (re.compile(r"anganwadi"),                             "anganwadi",                "medium"),
]


# ──────────────────────────────────────────────────────────────────────────────
#  OSM TAG MAPPING
#  Fallback when name overrides don't match. Maps raw OSM tags → Kashmir
#  category vocabulary. Tag priority: more specific tags checked first.
# ──────────────────────────────────────────────────────────────────────────────

def osm_tags_to_category(tags: Dict[str, str]) -> Tuple[Optional[str], Optional[str]]:
    """
    Map raw OSM tags to (category, importance) using the Kashmir vocabulary.
    Returns (None, None) if no recognized mapping (POI will be dropped).
    """
    amenity = tags.get("amenity", "").lower()
    shop    = tags.get("shop", "").lower()
    tourism = tags.get("tourism", "").lower()
    leisure = tags.get("leisure", "").lower()
    railway = tags.get("railway", "").lower()
    landuse = tags.get("landuse", "").lower()
    office  = tags.get("office", "").lower()
    public_transport = tags.get("public_transport", "").lower()
    military = tags.get("military", "").lower()
    healthcare = tags.get("healthcare", "").lower()

    # ─── Tier 1: Year-round mass attractors ────────────────────────────────
    if amenity == "hospital" or healthcare == "hospital":
        return ("hospital", "high")
    if amenity == "bus_station" or public_transport == "station":
        return ("bus_station", "high")
    if railway == "station" or public_transport == "railway_station":
        return ("railway_station", "high")
    if amenity == "place_of_worship":
        # Religion-aware mapping
        religion = tags.get("religion", "").lower()
        denom    = tags.get("denomination", "").lower()
        if religion == "muslim":
            if "shia" in denom or "sufi" in denom:
                return ("khanqah", "high")
            return ("jamia_masjid", "high")
        # Other religions go to a generic Tier 2 — pilgrimage sites
        # caught by name overrides above (Kheer Bhawani etc.)
        return ("jamia_masjid", "high")  # majority case in Kashmir
    if shop in ("mall", "department_store"):
        return ("mall", "high")
    if shop in ("supermarket", "wholesale"):
        return ("supermarket", "high")
    if landuse == "industrial":
        return ("industrial_estate", "high")
    if office == "government" or amenity == "townhall":
        return ("govt_office", "medium")  # govt_office is actually Tier 2
    if amenity == "courthouse":
        return ("court", "medium")

    # ─── Tier 2: Education / commerce / civic ──────────────────────────────
    if amenity == "university":
        return ("college", "medium")  # named universities caught by name override → Tier 1
    if amenity == "college":
        return ("college", "medium")
    if amenity == "school":
        return ("school", "medium")
    if amenity == "kindergarten":
        return ("school", "medium")
    if amenity == "library":
        return ("library", "medium")
    if amenity == "marketplace":
        return ("market", "medium")
    if shop == "marketplace":
        return ("market", "medium")
    if amenity == "clinic" or healthcare == "clinic":
        return ("clinic", "medium")
    if amenity == "doctors" or healthcare == "doctor":
        return ("dispensary", "medium")
    if amenity == "pharmacy":
        return ("small_medical", "medium")
    if amenity == "police":
        return ("police_station", "medium")
    if amenity == "fire_station":
        return ("govt_office", "medium")
    if leisure == "stadium":
        return ("stadium", "medium")
    if leisure == "sports_centre":
        return ("stadium", "medium")
    if leisure == "park":
        return ("park", "medium")
    if amenity == "museum" or tourism == "museum":
        return ("museum", "medium")
    if military or landuse == "military":
        return ("military", "medium")

    # ─── Tier 3: Tourism / seasonal ────────────────────────────────────────
    if tourism in ("attraction", "viewpoint", "theme_park", "picnic_site",
                    "zoo", "information", "gallery"):
        return ("tourist_spot", "seasonal")
    if tourism in ("hotel", "guest_house", "hostel"):
        return ("tourist_hotel", "seasonal")
    if leisure == "garden":
        return ("mughal_garden", "seasonal")  # generic; named gardens caught by overrides
    if tourism == "wilderness_hut":
        return ("tourist_spot", "seasonal")

    # ─── Unknown — drop ────────────────────────────────────────────────────
    return (None, None)


# ──────────────────────────────────────────────────────────────────────────────
#  LOGGING
# ──────────────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
)
log = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
#  OVERPASS FETCHER
# ──────────────────────────────────────────────────────────────────────────────

def _build_overpass_query() -> str:
    """
    One consolidated Overpass query for all POI types we care about within
    the Srinagar bounding box. Uses `nwr` (nodes + ways + relations) and
    `out center tags` so that polygon POIs (hospitals as ways) emit a
    single centroid lat/lon.
    """
    bbox = f"{BBOX['min_lat']},{BBOX['min_lon']},{BBOX['max_lat']},{BBOX['max_lon']}"
    return f"""
[out:json][timeout:{OVERPASS_TIMEOUT_S}];
(
  // ── Healthcare (Tier 1 + Tier 2) ─────────────────────────────────────
  nwr["amenity"~"^(hospital|clinic|doctors|pharmacy|dentist)$"]({bbox});
  nwr["healthcare"]({bbox});
  // ── Education (Tier 2; named institutions promoted to Tier 1 by name) ─
  nwr["amenity"~"^(school|college|university|kindergarten)$"]({bbox});
  // ── Transit infrastructure (Tier 1) ───────────────────────────────────
  nwr["amenity"~"^(bus_station|taxi)$"]({bbox});
  nwr["railway"="station"]({bbox});
  nwr["public_transport"~"^(station|stop_position)$"]({bbox});
  // ── Religious (Tier 1 — mosques/shrines year-round) ──────────────────
  nwr["amenity"="place_of_worship"]({bbox});
  // ── Commerce / markets (Tier 1 mall/supermarket, Tier 2 marketplace) ─
  nwr["amenity"~"^(marketplace|bank|atm|fuel)$"]({bbox});
  nwr["shop"~"^(mall|supermarket|department_store|wholesale|marketplace)$"]({bbox});
  // ── Tourism (Tier 3 seasonal) ─────────────────────────────────────────
  nwr["tourism"~"^(attraction|museum|hotel|viewpoint|theme_park|gallery|guest_house|hostel|picnic_site|zoo|information|wilderness_hut)$"]({bbox});
  // ── Leisure (Tier 2 park/stadium; Tier 3 named gardens by name) ──────
  nwr["leisure"~"^(park|garden|stadium|sports_centre)$"]({bbox});
  // ── Government / civic (Tier 1 secretariat/court, Tier 2 police/lib) ─
  nwr["amenity"~"^(police|courthouse|townhall|fire_station|library)$"]({bbox});
  nwr["office"="government"]({bbox});
  // ── Military / cantonment (Tier 2 — operational constraint) ──────────
  nwr["military"]({bbox});
  nwr["landuse"="military"]({bbox});
  // ── Industrial (Tier 1) ──────────────────────────────────────────────
  nwr["landuse"~"^(industrial|commercial)$"]({bbox});
);
out center tags;
""".strip()


def fetch_overpass(overpass_url: str) -> List[Dict]:
    """
    Query Overpass with retry across mirrors. Returns the raw `elements` list.
    """
    query = _build_overpass_query()
    log.info("Querying Overpass for Srinagar bbox %.2f,%.2f → %.2f,%.2f",
             BBOX["min_lat"], BBOX["min_lon"], BBOX["max_lat"], BBOX["max_lon"])

    urls_to_try = [overpass_url] + [u for u in OVERPASS_FALLBACKS if u != overpass_url]

    for url in urls_to_try:
        for attempt in range(1, OVERPASS_RETRIES + 1):
            try:
                log.info("  Attempt %d via %s …", attempt, url)
                t0 = time.perf_counter()
                resp = requests.post(
                    url,
                    data={"data": query},
                    timeout=OVERPASS_HTTP_TIMEOUT,
                    headers={"User-Agent": "transit-kashmir-extractor/1.0"},
                )
                dt = time.perf_counter() - t0
                if resp.status_code == 200:
                    elements = resp.json().get("elements", [])
                    log.info("  ✓ Overpass returned %d raw elements (%.1fs)",
                             len(elements), dt)
                    return elements
                elif resp.status_code in (429, 504):
                    log.warning("  Rate-limited / timeout (HTTP %d). Waiting %ds…",
                                resp.status_code, OVERPASS_RETRY_WAIT)
                    time.sleep(OVERPASS_RETRY_WAIT)
                else:
                    log.warning("  Overpass HTTP %d. Trying next mirror.", resp.status_code)
                    break
            except (requests.Timeout, requests.ConnectionError) as e:
                log.warning("  Network error: %s. Waiting %ds…", e, OVERPASS_RETRY_WAIT)
                time.sleep(OVERPASS_RETRY_WAIT)
            except Exception as e:
                log.error("  Unexpected error: %s", e)
                break
        log.warning("  Mirror %s exhausted; moving on.", url)

    raise RuntimeError("All Overpass mirrors failed. Try again later or pass --overpass-url.")


def _element_lat_lon(el: Dict) -> Optional[Tuple[float, float]]:
    """Extract a single (lat, lon) from an Overpass element (node or way/relation centre)."""
    if el.get("type") == "node":
        return el.get("lat"), el.get("lon")
    centre = el.get("center")
    if centre:
        return centre.get("lat"), centre.get("lon")
    return None


# ──────────────────────────────────────────────────────────────────────────────
#  CLASSIFICATION — name override first, then OSM tag fallback
# ──────────────────────────────────────────────────────────────────────────────

def classify(name: str, tags: Dict[str, str]) -> Tuple[Optional[str], Optional[str]]:
    """
    Returns (category, importance) for a POI. None if unrecognized.
    """
    name_lc = (name or "").lower().strip()

    # 1. Name-based override (specific landmarks)
    if name_lc:
        for pattern, category, importance in NAME_OVERRIDES:
            if pattern.search(name_lc):
                return (category, importance)

    # 2. OSM tag fallback
    return osm_tags_to_category(tags)


def _resolve_importance(category: str, suggested: Optional[str]) -> str:
    """
    Cross-check the suggested importance against actual tier membership.
    Lets the name-override imply 'high' but verifies against TIER1 set;
    similarly for medium → TIER2, seasonal → TIER3. Mismatches are
    corrected so downstream weight lookup is consistent.
    """
    if category in TIER1:
        return "high"
    if category in TIER3:
        return "seasonal"
    if category in TIER2:
        return "medium"
    # Unknown category → use the suggested or blank
    return suggested or ""


# ──────────────────────────────────────────────────────────────────────────────
#  OSRM SNAP-TO-ROAD  (the use of the local Docker OSRM on port 5000)
# ──────────────────────────────────────────────────────────────────────────────

def _osrm_nearest_one(osrm_url: str, lat: float, lon: float) -> Optional[Tuple[float, float, float]]:
    """
    Hit OSRM /nearest. Returns (snap_lat, snap_lon, distance_m) or None on fail.
    """
    try:
        url = f"{osrm_url}/nearest/v1/driving/{lon},{lat}"
        resp = requests.get(url, timeout=OSRM_TIMEOUT_S)
        if resp.status_code != 200:
            return None
        data = resp.json()
        if data.get("code") != "Ok" or not data.get("waypoints"):
            return None
        wp = data["waypoints"][0]
        snap_lon, snap_lat = wp["location"]
        dist = float(wp.get("distance", 0.0))
        return (snap_lat, snap_lon, dist)
    except Exception:
        return None


def osrm_snap_concurrent(rows: List[Dict], osrm_url: str) -> List[Dict]:
    """
    Concurrent OSRM /nearest calls for all rows.
    Adds 'snap_distance_m', 'snap_lat', 'snap_lon' to each row.
    Rows that fail OSRM get snap_distance_m = -1 (kept, will be filtered later).
    """
    log.info("Snapping %d POIs to road network via OSRM (%d workers, timeout=%ds)…",
             len(rows), OSRM_MAX_WORKERS, OSRM_TIMEOUT_S)
    t0 = time.perf_counter()

    def worker(i: int, row: Dict):
        res = _osrm_nearest_one(osrm_url, row["lat"], row["lon"])
        return i, res

    with ThreadPoolExecutor(max_workers=OSRM_MAX_WORKERS) as pool:
        futures = {pool.submit(worker, i, r): i for i, r in enumerate(rows)}
        ok = 0
        for fut in as_completed(futures):
            i, res = fut.result()
            if res is not None:
                snap_lat, snap_lon, dist = res
                rows[i]["snap_lat"] = round(snap_lat, 6)
                rows[i]["snap_lon"] = round(snap_lon, 6)
                rows[i]["snap_distance_m"] = round(dist, 1)
                ok += 1
            else:
                rows[i]["snap_lat"] = None
                rows[i]["snap_lon"] = None
                rows[i]["snap_distance_m"] = -1.0

    dt = time.perf_counter() - t0
    log.info("  ✓ OSRM snap done in %.1fs (%d/%d succeeded)", dt, ok, len(rows))
    return rows


def filter_by_road_access(rows: List[Dict], max_snap_m: float) -> List[Dict]:
    """
    Drop POIs whose nearest road is > max_snap_m away. These are typically
    centroids in the middle of Dal Lake, mountain summits, or interior of
    military cantonments — not actually reachable by any bus route.
    POIs that failed OSRM entirely (snap_distance_m = -1) are kept by default
    so we don't punish them for an OSRM hiccup.
    """
    kept   = []
    dropped = []
    for r in rows:
        d = r.get("snap_distance_m", -1)
        if d == -1:
            kept.append(r)              # OSRM error — keep (don't penalize)
        elif d <= max_snap_m:
            kept.append(r)
        else:
            dropped.append(r)

    if dropped:
        # Sample a few for the log
        sample = dropped[:5]
        log.warning("  Dropped %d POIs > %dm from nearest road (likely unreachable):",
                    len(dropped), int(max_snap_m))
        for r in sample:
            log.warning("    - %s (%s) — %.0f m from road",
                        r.get("name", "?")[:50],
                        r.get("category", "?"),
                        r["snap_distance_m"])
        if len(dropped) > 5:
            log.warning("    … and %d more", len(dropped) - 5)

    return kept


# ──────────────────────────────────────────────────────────────────────────────
#  REPORT & EXPORT
# ──────────────────────────────────────────────────────────────────────────────

def write_csv(rows: List[Dict], path: str) -> None:
    cols = ["lat", "lon", "name", "category", "importance",
            "osm_id", "osm_type", "snap_distance_m", "source"]
    df = pd.DataFrame(rows, columns=cols)
    df.to_csv(path, index=False, encoding="utf-8-sig")
    log.info("Wrote %d POIs → %s", len(df), path)


def report_distribution(rows: List[Dict]) -> None:
    if not rows:
        log.warning("No POIs to report on.")
        return

    df = pd.DataFrame(rows)

    log.info("=" * 68)
    log.info("CATEGORY DISTRIBUTION (top 20)")
    log.info("=" * 68)
    for cat, n in df["category"].value_counts().head(20).items():
        tier = ("T1" if cat in TIER1 else
                "T2" if cat in TIER2 else
                "T3" if cat in TIER3 else
                "??")
        women = " ★W" if cat in WOMEN_ANCHOR else ""
        log.info("  [%s%s] %-32s  %d", tier, women, cat, n)

    log.info("=" * 68)
    log.info("TIER SUMMARY")
    log.info("=" * 68)
    t1 = df["category"].isin(TIER1).sum()
    t2 = df["category"].isin(TIER2).sum()
    t3 = df["category"].isin(TIER3).sum()
    wa = df["category"].isin(WOMEN_ANCHOR).sum()
    unk = len(df) - (t1 + t2 + t3)
    log.info("  Tier 1 (high, w=1.0)   : %5d  (%.1f%%)", t1, 100 * t1 / len(df))
    log.info("  Tier 2 (medium, w=0.4) : %5d  (%.1f%%)", t2, 100 * t2 / len(df))
    log.info("  Tier 3 (seasonal)      : %5d  (%.1f%%)", t3, 100 * t3 / len(df))
    log.info("  Unrecognised           : %5d  (%.1f%%)", unk, 100 * unk / len(df))
    log.info("  Women-anchor (+25%%)    : %5d  (overlap with above)", wa)


# ──────────────────────────────────────────────────────────────────────────────
#  ORCHESTRATOR
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract Kashmir POIs for transit_kashmir_v3.py")
    parser.add_argument("--output", default=OUTPUT_DEFAULT,
                        help=f"Output CSV path (default: {OUTPUT_DEFAULT})")
    parser.add_argument("--osrm-url", default=OSRM_URL_DEFAULT,
                        help=f"OSRM URL (default: {OSRM_URL_DEFAULT})")
    parser.add_argument("--overpass-url", default=OVERPASS_URL_DEFAULT,
                        help=f"Overpass URL (default: {OVERPASS_URL_DEFAULT})")
    parser.add_argument("--no-osrm", action="store_true",
                        help="Skip OSRM snap-to-road & access filtering")
    parser.add_argument("--max-snap-distance", type=float, default=MAX_ROAD_SNAP_M,
                        help=f"Drop POIs > this metres from any road "
                             f"(default: {MAX_ROAD_SNAP_M})")
    parser.add_argument("--keep-unrecognised", action="store_true",
                        help="Keep POIs with no Kashmir category (default: drop)")
    args = parser.parse_args()

    t_start = time.perf_counter()

    log.info("=" * 68)
    log.info("Kashmir POI Extractor — for transit_kashmir_v3.py")
    log.info("=" * 68)
    log.info("  Bounding box       : %.2f,%.2f → %.2f,%.2f (matches transit script)",
             BBOX["min_lat"], BBOX["min_lon"], BBOX["max_lat"], BBOX["max_lon"])
    log.info("  Source             : OpenStreetMap (Overpass API)")
    log.info("  Road-snap / filter : %s", "DISABLED (--no-osrm)" if args.no_osrm
             else f"ENABLED ({args.osrm_url}, max {args.max_snap_distance:.0f} m)")
    log.info("  Output             : %s", args.output)
    log.info("=" * 68)

    # 1. Fetch from Overpass
    elements = fetch_overpass(args.overpass_url)

    # 2. Classify each element
    log.info("Classifying %d raw OSM elements …", len(elements))
    rows: List[Dict] = []
    no_coords = 0
    no_class  = 0
    for el in elements:
        coords = _element_lat_lon(el)
        if coords is None or coords[0] is None:
            no_coords += 1
            continue
        lat, lon = coords
        tags = el.get("tags", {}) or {}
        name = tags.get("name", "")
        category, importance = classify(name, tags)
        if category is None:
            no_class += 1
            if not args.keep_unrecognised:
                continue
            category, importance = ("Other", "")
        else:
            importance = _resolve_importance(category, importance)

        rows.append({
            "lat":             round(float(lat), 6),
            "lon":             round(float(lon), 6),
            "name":            (name or category).strip(),
            "category":        category,
            "importance":      importance,
            "osm_id":          el.get("id", ""),
            "osm_type":        el.get("type", ""),
            "snap_distance_m": None,
            "source":          "OSM via Overpass",
        })

    log.info("  ✓ Classified %d POIs (skipped: %d no-coords, %d unrecognised)",
             len(rows), no_coords, no_class)

    # 3. OSRM snap + road-access filter
    if not args.no_osrm and rows:
        rows = osrm_snap_concurrent(rows, args.osrm_url)
        rows = filter_by_road_access(rows, args.max_snap_distance)

    # 4. Deduplicate by (category, rounded lat/lon) — Overpass often returns
    #    a POI as both a node AND its enclosing way; keep one.
    seen = set()
    deduped = []
    for r in rows:
        key = (r["category"], round(r["lat"], 4), round(r["lon"], 4))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(r)
    if len(deduped) != len(rows):
        log.info("  ✓ Deduplicated: %d → %d POIs (removed node/way duplicates)",
                 len(rows), len(deduped))
    rows = deduped

    # 5. Write & report
    write_csv(rows, args.output)
    report_distribution(rows)

    elapsed = time.perf_counter() - t_start
    log.info("=" * 68)
    log.info("DONE in %.1f s → %s (%d POIs)", elapsed, args.output, len(rows))
    log.info("Feed this into transit_kashmir_v3.py via POIS_CSV = '%s'", args.output)
    log.info("=" * 68)


if __name__ == "__main__":
    main()
