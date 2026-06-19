"""
geocode_other_routes.py — Geocode Other-routes.csv and merge into existing-routes.csv
======================================================================================
Reads the non-standard Other-routes.csv format, cleans location names,
geocodes using ArcGIS (with cache reuse from latlon.py), and appends
results to existing-routes.csv in matching column format.

FILTERS:
  - SKIP EBus routes (already hardcoded as SSCL backbone in transit engine)
  - SKIP MTS Bus routes (extend beyond Kashmir bounding box)
======================================================================================
"""
import json
import os
import re
import time

import pandas as pd

# Hardened geocoding shared with latlon.py (audit Findings 1,2,5).
import geocode_common

# arcgis is optional now (audit remediation) — fall back to Nominatim if missing.
GEOCODE_FN, GEOCODER_NAME = geocode_common.get_default_geocoder()
print(f"[INFO] Geocoder backend: {GEOCODER_NAME}")

GEO_FAILURES = []   # auditable record of names that could not be placed

# ── CONFIG ──
OTHER_ROUTES_FILE = "Other-routes.csv"
EXISTING_ROUTES_FILE = "existing-routes.csv"
CACHE_FILE = "geocode_cache.json"
API_DELAY = 1.0

# ── ABBREVIATION MAP (Kashmir-specific) ──
ABBREVIATIONS = {
    "SGR": "SRINAGAR",
    "BPR": "BANDIPORA",
    "BLA": "BARAMULLA",
    "GBL": "GANDERBAL",
    "ANG": "ANANTNAG",
    "TRC": "TRC SRINAGAR",
    "LD": "LAL DED HOSPITAL SRINAGAR",
}

# (GIS session, if any, is created inside get_default_geocoder().)


def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    return {}


def save_cache(cache):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=4)


def clean_location(loc):
    """Clean location string: strip noise, expand abbreviations, handle compounds."""
    if pd.isna(loc):
        return None
    loc_str = str(loc).strip()
    if not loc_str or loc_str.upper() in ("NA", "N/A", ""):
        return None

    loc_str = loc_str.upper().strip()

    # Remove trailing hyphens/spaces
    loc_str = loc_str.rstrip("- ")

    # Remove 'AND VICE VERSA' variations
    for vv in ["AND VICE VERSA", "& VICE VERSA", "-VICE VERSA", "VICE VERSA"]:
        loc_str = loc_str.replace(vv, "")

    # Handle compound destination names like "Sopore-Srinagar", "Kupwara- Srinagar"
    # These are "Destination-Origin" patterns — extract just the destination
    compound_pattern = re.compile(r'^(.+?)[\s]*-[\s]*(SRINAGAR|SGR|ANANTNAG|ANG)$', re.IGNORECASE)
    match = compound_pattern.match(loc_str)
    if match:
        loc_str = match.group(1).strip().rstrip("-")

    # Handle "Keller-Shopian-Sgr" → "KELLER"
    parts = [p.strip() for p in loc_str.split("-") if p.strip()]
    if len(parts) > 1:
        # Remove known city suffixes from compound names
        filtered = [p for p in parts if p.upper() not in ("SRINAGAR", "SGR", "ANANTNAG", "ANG", "BARAMULLA", "BLA")]
        if filtered:
            loc_str = filtered[0]  # Take the first meaningful part
        else:
            loc_str = parts[0]

    # Expand abbreviations
    loc_str = loc_str.strip()
    if loc_str in ABBREVIATIONS:
        loc_str = ABBREVIATIONS[loc_str]

    # Remove special characters except spaces and hyphens
    loc_str = re.sub(r'[^A-Z0-9\s\-]', '', loc_str)
    loc_str = re.sub(r'\s+', ' ', loc_str).strip()

    return loc_str if loc_str else None


# F-V4b: depot timetable rows record the whole corridor as a dash-pair in the
# 'to' field (e.g. "Bandipora-Soura", "Sopore-Srinagar") while 'from' defaults to
# "Srinagar". Splitting the pair recovers the true O/D (a local Bandipora↔Soura
# route) instead of a wrong Srinagar→Bandipora one.
_HUB_TOKENS = {
    "SRINAGAR", "SGR", "ANANTNAG", "ANANTNAGH", "ANG", "BARAMULLA", "BARAMULA",
    "BLA", "BANDIPORA", "BPR", "SOPORE", "KUPWARA", "SHOPIAN", "KULGAM",
    "PULWAMA", "GANDERBAL", "GBL", "SOURA",
}


def _split_route_pair(raw_to):
    """If a 'to' value is a dash-separated corridor pair with a known hub on one
    side, return (origin, destination); else None."""
    if not isinstance(raw_to, str):
        return None
    parts = [p.strip() for p in re.split(r"\s*-\s*", raw_to) if p.strip()]
    if len(parts) == 2 and any(p.upper() in _HUB_TOKENS for p in parts):
        return parts[0], parts[1]
    return None


def _row_endpoints(row):
    """Return (origin_clean, dest_clean) for a JKRTC/Other row, applying the
    depot-pair split (F-V4b)."""
    pair = _split_route_pair(row.get("To"))
    if pair:
        return clean_location(pair[0]), clean_location(pair[1])
    return clean_location(row.get("From")), clean_location(row.get("To"))


def fetch_coordinates(location_name, cache, is_retry=False):
    """Geocode with district-aware context + Srinagar-centroid rejection
    (audit Finding 1). Delegates to geocode_common.geocode_one so both
    geocoders behave identically; caches and records failures."""
    if location_name in cache:
        return cache[location_name].get("lat"), cache[location_name].get("lon")

    lat, lon = geocode_common.geocode_one(location_name, GEOCODE_FN,
                                          failures=GEO_FAILURES)
    if lat is not None and lon is not None:
        status = "[RETRY OK]" if is_retry else "[OK]"
        print(f"  {status} {location_name} -> {lat:.5f}, {lon:.5f}")
        cache[location_name] = {"lat": lat, "lon": lon}
        save_cache(cache)
        return lat, lon
    print(f"  [FAIL] Could not place '{location_name}' (see geocode_failures.csv)")
    return None, None


def geocode_via_string(via_str, cache):
    """Parse comma-separated via string and return geocoded coords."""
    if not via_str:
        return None
    points = [p.strip() for p in str(via_str).split(",")]
    geocoded = []
    for p in points:
        cleaned = clean_location(p)
        if cleaned and cleaned in cache:
            c = cache[cleaned]
            if c.get("lat") and c.get("lon"):
                geocoded.append(f"{c['lat']},{c['lon']}")
    return ";".join(geocoded) if geocoded else None


def main():
    print("=" * 60)
    print("OTHER-ROUTES GEOCODER — Kashmir Transit Engine")
    print("=" * 60)

    # 1. Load Other-routes.csv
    df = pd.read_csv(OTHER_ROUTES_FILE)
    print(f"[INFO] Loaded {len(df)} routes from {OTHER_ROUTES_FILE}")

    # Standardise column names
    df.columns = [c.strip() for c in df.columns]

    # Map to canonical names (the CSV has 'office name', 'Vehicle Category', 'from', 'to', 'via')
    col_map = {}
    for c in df.columns:
        cl = c.lower().strip()
        if cl == "office name":
            col_map[c] = "Office_Name"
        elif cl == "vehicle category":
            col_map[c] = "Vehicle_Category"
        elif cl == "from":
            col_map[c] = "From"
        elif cl == "to":
            col_map[c] = "To"
        elif cl == "via":
            col_map[c] = "Via"
    df.rename(columns=col_map, inplace=True)

    # Drop unnamed columns
    df = df[[c for c in df.columns if not c.startswith("Unnamed")]]

    # 2. Filter out EBus (already SSCL backbone) and MTS Bus (out of study area).
    #    F-V4a: the MTS section is mostly inter-state (Srinagar↔Jammu/Delhi/Leh/…)
    #    but ALSO contains the in-valley "TRC to Airport" link (8 daily departures).
    #    Keep any MTS row that mentions the airport so the airport connection is
    #    retained; drop the rest of MTS.
    before = len(df)
    cat = df["Vehicle_Category"].astype(str).str.strip()
    def _col(name):
        return df[name].fillna("").astype(str) if name in df.columns else pd.Series("", index=df.index)
    rowtext = (_col("From") + " " + _col("To") + " " + _col("Via")).str.lower()
    is_airport_mts = (cat == "MTS Bus") & rowtext.str.contains("airport", na=False)
    ebus_count = int((cat == "EBus").sum())
    mts_count = int((cat == "MTS Bus").sum())
    drop_mask = cat.isin(["EBus", "MTS Bus"]) & ~is_airport_mts
    kept_airport = int(is_airport_mts.sum())
    df = df[~drop_mask]
    print(f"[INFO] Filtered out {ebus_count} EBus routes (already SSCL backbone)")
    print(f"[INFO] Filtered out {mts_count - kept_airport} MTS Bus routes (inter-state, out of area); "
          f"KEPT {kept_airport} in-valley MTS airport link (F-V4a)")
    print(f"[INFO] Remaining: {len(df)} routes to geocode")

    # 3. Extract unique locations
    cache = load_cache()
    unique_locs = set()
    for _, row in df.iterrows():
        o, d = _row_endpoints(row)               # F-V4b depot-pair aware
        for x in (o, d, clean_location(row.get("Via"))):
            if x:
                unique_locs.add(x)

    print(f"[INFO] Found {len(unique_locs)} unique locations")
    to_fetch = [loc for loc in unique_locs if loc not in cache]
    print(f"[INFO] Already cached: {len(unique_locs) - len(to_fetch)}")
    print(f"[INFO] Need to geocode: {len(to_fetch)}")

    # 4. Geocode
    for i, loc in enumerate(to_fetch):
        print(f"  [{i+1}/{len(to_fetch)}] Geocoding: '{loc}'")
        fetch_coordinates(loc, cache)
        time.sleep(API_DELAY)

    # 5. Build output in existing-routes.csv format
    print(f"\n{'='*60}")
    print("BUILDING MERGED OUTPUT")
    print("=" * 60)

    new_routes = []
    dropped_rows = []   # audit trail: every JKRTC row that did NOT make the CSV
    for _, row in df.iterrows():
        origin, destination = _row_endpoints(row)   # F-V4b depot-pair aware
        via_raw = clean_location(row.get("Via"))

        origin_lat = cache.get(origin, {}).get("lat") if origin else None
        origin_lon = cache.get(origin, {}).get("lon") if origin else None
        dest_lat = cache.get(destination, {}).get("lat") if destination else None
        dest_lon = cache.get(destination, {}).get("lon") if destination else None

        # Only include if both origin and destination are geocoded
        if not (origin_lat and origin_lon and dest_lat and dest_lon):
            miss = []
            if not (origin_lat and origin_lon): miss.append(f"origin '{origin}'")
            if not (dest_lat and dest_lon):     miss.append(f"destination '{destination}'")
            dropped_rows.append({"from": row.get("From"), "to": row.get("To"),
                                 "vehicle": row.get("Vehicle_Category"),
                                 "reason": "ungeocoded: " + ", ".join(miss)})
            continue

        route_name = f"{origin} to {destination}"
        if via_raw:
            route_name += f" via {via_raw}"

        route_data = {
            "Route_Name": route_name,
            "Origin": origin,
            "Origin_Lat": origin_lat,
            "Origin_Lon": origin_lon,
            "Destination": destination,
            "Dest_Lat": dest_lat,
            "Dest_Lon": dest_lon,
            "Via_Points_Raw": via_raw,
            "Via_Points_Geocoded": geocode_via_string(via_raw, cache),
            "Vehicle_Category": str(row.get("Vehicle_Category", "")).strip(),
            "Service_Type": "Ordinary Service",
        }
        new_routes.append(route_data)

    df_new = pd.DataFrame(new_routes)
    print(f"[INFO] Successfully geocoded {len(df_new)} routes from Other-routes.csv")

    # 6. Load existing and merge
    if os.path.exists(EXISTING_ROUTES_FILE):
        df_existing = pd.read_csv(EXISTING_ROUTES_FILE)
        print(f"[INFO] Loaded {len(df_existing)} existing routes from {EXISTING_ROUTES_FILE}")

        # Ensure column alignment
        for col in df_existing.columns:
            if col not in df_new.columns:
                df_new[col] = None
        for col in df_new.columns:
            if col not in df_existing.columns:
                df_existing[col] = None

        df_merged = pd.concat([df_existing, df_new], ignore_index=True)
    else:
        df_merged = df_new

    df_merged.to_csv(EXISTING_ROUTES_FILE, index=False)

    # 7. Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print("=" * 60)
    print(f"  Total routes in {EXISTING_ROUTES_FILE}: {len(df_merged)}")
    vc_counts = df_merged["Vehicle_Category"].value_counts()
    for cat, count in vc_counts.items():
        print(f"    {cat}: {count}")
    print(f"[DONE] Merged output saved to {EXISTING_ROUTES_FILE}")

    # ── Audit trail (Finding 2): make every drop loud, never silent ──
    geocode_common.write_failures(GEO_FAILURES, "geocode_failures_other.csv")
    if dropped_rows:
        pd.DataFrame(dropped_rows).to_csv("other_routes_dropped.csv", index=False)
        print(f"[AUDIT] {len(dropped_rows)} JKRTC/Other rows dropped "
              f"(no usable O/D geocode) → other_routes_dropped.csv")


if __name__ == "__main__":
    main()
