import pandas as pd
import time
import re
import os
import json

# Hardened geocoding shared with geocode_other_routes.py (audit Findings 1,2,5).
import geocode_common

# arcgis is optional now (audit remediation): if the heavy package is missing we
# fall back to the requests-based Nominatim backend so the re-geocode can run.
GEOCODE_FN, GEOCODER_NAME = geocode_common.get_default_geocoder()
print(f"[INFO] Geocoder backend: {GEOCODER_NAME}")

# Accumulates every name that could not be placed, so drops are auditable.
GEO_FAILURES = []

# ==========================================
# CONFIGURATION & FILE PATHS
# ==========================================
MINI_BUS_FILE = "Mini Buses Routes in Srinagar.xlsx"
OUTPUT_FILE = "existing-routes.csv"
CACHE_FILE = "geocode_cache.json"

# Delay between API calls (seconds) to prevent rate-limiting bans
API_DELAY = 1.0  
RETRY_DELAY = 2.0 

# Initialize GIS (Anonymous connection)
gis = GIS()

# ==========================================
# HELPER FUNCTIONS
# ==========================================
def load_cache():
    """Loads previously geocoded coordinates from disk."""
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_cache(cache_dict):
    """Saves coordinates to disk to prevent data loss."""
    with open(CACHE_FILE, 'w') as f:
        json.dump(cache_dict, f, indent=4)

def clean_location(loc):
    """Cleans location strings and scrubs all 'Vice Versa' variations."""
    if pd.isna(loc):
        return None
        
    loc_str = str(loc).strip().upper()
    
    # 1. Scrub out all variations of Vice Versa first
    loc_str = loc_str.replace("AND VICE VERSA", "")
    loc_str = loc_str.replace("& VICE VERSA", "")
    loc_str = loc_str.replace("-VICE VERSA", "")
    loc_str = loc_str.replace("VICE VERSA", "")
    
    # 2. Check if the string is now empty or invalid
    loc_str = loc_str.strip()
    if loc_str in ["NA", "N/A", ""]:
        return None
        
    # 3. Remove special characters but keep spaces and hyphens
    loc_str = re.sub(r'[^\w\s-]', '', loc_str)
    
    return loc_str.strip() if loc_str.strip() else None

def geocode_via_string(via_str, cache):
    """Parses a comma-separated via string and returns geocoded coordinates."""
    if not via_str:
        return None
    points = [p.strip() for p in str(via_str).split(',')]
    geocoded = []
    for p in points:
        cleaned = clean_location(p)
        if cleaned and cleaned in cache:
            c = cache[cleaned]
            if c.get('lat') and c.get('lon'):
                geocoded.append(f"{c['lat']},{c['lon']}")
    return ";".join(geocoded) if geocoded else None

def extract_unique_locations(df):
    """Scans the dataframe and returns a set of unique stops."""
    unique_locations = set()
    for col in ['From Location', 'To Location', 'Via Location']:
        if col in df.columns:
            for item in df[col].dropna():
                # Split 'Via' points by comma
                parts = str(item).split(',')
                for part in parts:
                    cleaned = clean_location(part)
                    if cleaned:
                        unique_locations.add(cleaned)
    return list(unique_locations)

def fetch_coordinates(location_name, is_retry=False):
    """Geocode a location with district-aware context + Srinagar-centroid
    rejection (audit Finding 1). Delegates to geocode_common.geocode_one so the
    two geocoders behave identically. Returns (lat, lon) or (None, None) and
    records any failure (incl. a rejected centroid collision) in GEO_FAILURES.
    """
    lat, lon = geocode_common.geocode_one(location_name, GEOCODE_FN,
                                          failures=GEO_FAILURES)
    status = "[RETRY OK]" if is_retry else "[OK]"
    if lat is not None and lon is not None:
        print(f"  {status} {location_name} -> {lat:.5f}, {lon:.5f}")
    else:
        print(f"  [FAILED] Could not place '{location_name}' (see geocode_failures.csv)")
    return lat, lon

# ==========================================
# MAIN EXECUTION
# ==========================================
def main():
    print("="*50)
    print("SRINAGAR MINI-BUS GEOCODER STARTED")
    print("="*50)

    # 1. Load Data
    try:
        df_minibus = pd.read_excel(MINI_BUS_FILE)
        print(f"[INFO] Loaded dataset with {len(df_minibus)} routes.")

        # Filter for SRINAGAR RTO
        if 'Office Name' in df_minibus.columns:
            df_minibus = df_minibus[df_minibus['Office Name'] == 'SRINAGAR RTO'].copy()
            print(f"[INFO] Filtered for 'SRINAGAR RTO'. Remaining routes: {len(df_minibus)}")
        else:
            print(f"[WARNING] 'Office Name' column not found. Processing all routes.")
    except FileNotFoundError:
        print(f"[FATAL] Could not find {MINI_BUS_FILE}. Please check the filename.")
        return

    # 2. Extract & Prep Cache
    unique_locations = extract_unique_locations(df_minibus)
    coord_cache = load_cache()
    
    print(f"[INFO] Found {len(unique_locations)} unique locations.")
    print(f"[INFO] Loaded {len(coord_cache)} previously cached locations from disk.")
    
    locations_to_fetch = [loc for loc in unique_locations if loc not in coord_cache]
    print(f"[INFO] Remaining locations to fetch: {len(locations_to_fetch)}\n")

    # 3. First Pass Geocoding
    failed_extractions = []
    
    for i, loc in enumerate(locations_to_fetch):
        print(f"Processing {i+1}/{len(locations_to_fetch)}: '{loc}'")
        lat, lon = fetch_coordinates(loc)
        
        if lat and lon:
            coord_cache[loc] = {'lat': lat, 'lon': lon}
            save_cache(coord_cache) # Save immediately to disk
        else:
            failed_extractions.append(loc)
            
        time.sleep(API_DELAY)

    # 4. Retry Logic for Failures
    if failed_extractions:
        print("\n" + "="*50)
        print(f"INITIATING RETRY FOR {len(failed_extractions)} FAILED LOCATIONS")
        print("="*50)
        
        for i, loc in enumerate(failed_extractions):
            print(f"Retrying {i+1}/{len(failed_extractions)}: '{loc}'")
            lat, lon = fetch_coordinates(loc, is_retry=True)
            
            if lat and lon:
                coord_cache[loc] = {'lat': lat, 'lon': lon}
                save_cache(coord_cache)
            time.sleep(RETRY_DELAY) # Slightly longer delay for retries

    # 5. Build Final CSV
    print("\n" + "="*50)
    print("BUILDING FINAL EXISTING-ROUTES.CSV")
    print("="*50)
    
    final_routes = []
    dropped_rows = []   # audit trail: every permit that did NOT make the CSV

    for index, row in df_minibus.iterrows():
        origin = clean_location(row.get('From Location'))
        destination = clean_location(row.get('To Location'))
        via_raw = clean_location(row.get('Via Location'))

        if not origin and not destination:
            dropped_rows.append({"row": index, "from": row.get('From Location'),
                                 "to": row.get('To Location'),
                                 "vehicle": row.get('Vehicle Category'),
                                 "reason": "blank_origin_and_destination"})
            continue

        origin_lat = coord_cache.get(origin, {}).get('lat') if origin else None
        origin_lon = coord_cache.get(origin, {}).get('lon') if origin else None
        dest_lat = coord_cache.get(destination, {}).get('lat') if destination else None
        dest_lon = coord_cache.get(destination, {}).get('lon') if destination else None

        # Only include route if BOTH origin and destination were successfully geocoded
        if not (origin_lat and origin_lon and dest_lat and dest_lon):
            miss = []
            if not (origin_lat and origin_lon): miss.append(f"origin '{origin}'")
            if not (dest_lat and dest_lon):     miss.append(f"destination '{destination}'")
            dropped_rows.append({"row": index, "from": row.get('From Location'),
                                 "to": row.get('To Location'),
                                 "vehicle": row.get('Vehicle Category'),
                                 "reason": "ungeocoded: " + ", ".join(miss)})
            continue

        route_data = {
            'Route_Name': row.get('Route Covered', f"Route_{index}"),
            'Origin': origin,
            'Origin_Lat': origin_lat,
            'Origin_Lon': origin_lon,
            'Destination': destination,
            'Dest_Lat': dest_lat,
            'Dest_Lon': dest_lon,
            'Via_Points_Raw': via_raw,
            'Via_Points_Geocoded': geocode_via_string(via_raw, coord_cache),
            'Vehicle_Category': row.get('Vehicle Category'),
            'Service_Type': row.get('Permit Service Type Name')
        }
        final_routes.append(route_data)

    df_output = pd.DataFrame(final_routes)
    
    # All rows in df_output now have valid coordinates
    geocoded_count = len(df_output)
    
    df_output.to_csv(OUTPUT_FILE, index=False)
    print(f"[INFO] Processing Complete!")
    print(f"[INFO] Exported {geocoded_count} routes where BOTH origin and destination were successfully geocoded.")
    print(f"[INFO] Output saved to {OUTPUT_FILE}")

    # ── Audit trail (Finding 2): make every drop loud, never silent ──
    geocode_common.write_failures(GEO_FAILURES, "geocode_failures.csv")
    if dropped_rows:
        pd.DataFrame(dropped_rows).to_csv("existing_routes_dropped.csv", index=False)
        print(f"[AUDIT] {len(dropped_rows)} of {len(df_minibus)} Srinagar-RTO permits "
              f"dropped (no usable O/D geocode) → existing_routes_dropped.csv")

if __name__ == "__main__":
    main()