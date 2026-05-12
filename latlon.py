import pandas as pd
from arcgis.gis import GIS
from arcgis.geocoding import geocode
import time
import re
import os
import json

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
    """Uses ArcGIS to fetch coordinates with Srinagar/Kashmir context."""
    # Aggressively adding context. Added 'Srinagar' for tighter precision.
    search_query = f"{location_name}, Srinagar, Kashmir, India"
    
    try:
        results = geocode(search_query)
        if results:
            best_match = results[0]['location']
            status = "[RETRY SUCCESS]" if is_retry else "[SUCCESS]"
            print(f"  {status} {location_name} -> {best_match['y']:.5f}, {best_match['x']:.5f}")
            return best_match['y'], best_match['x']
        else:
            status = "[RETRY FAILED]" if is_retry else "[FAILED]"
            print(f"  {status} Could not locate: {search_query}")
            return None, None
    except Exception as e:
        print(f"  [ERROR] API Exception for {search_query}: {e}")
        return None, None

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
    
    for index, row in df_minibus.iterrows():
        origin = clean_location(row.get('From Location'))
        destination = clean_location(row.get('To Location'))
        via_raw = clean_location(row.get('Via Location'))
        
        if not origin and not destination:
            continue
            
        route_data = {
            'Route_Name': row.get('Route Covered', f"Route_{index}"),
            'Origin': origin,
            'Origin_Lat': coord_cache.get(origin, {}).get('lat') if origin else None,
            'Origin_Lon': coord_cache.get(origin, {}).get('lon') if origin else None,
            'Destination': destination,
            'Dest_Lat': coord_cache.get(destination, {}).get('lat') if destination else None,
            'Dest_Lon': coord_cache.get(destination, {}).get('lon') if destination else None,
            'Via_Points_Raw': via_raw,
            'Vehicle_Category': row.get('Vehicle Category'),
            'Service_Type': row.get('Permit Service Type Name')
        }
        final_routes.append(route_data)

    df_output = pd.DataFrame(final_routes)
    
    # Calculate success metrics
    total_origins = df_output['Origin'].notna().sum()
    geocoded_origins = df_output['Origin_Lat'].notna().sum()
    
    df_output.to_csv(OUTPUT_FILE, index=False)
    print(f"[INFO] Processing Complete!")
    print(f"[INFO] Successfully geocoded ~{(geocoded_origins/total_origins)*100:.1f}% of origin points.")
    print(f"[INFO] Exported {len(df_output)} mapped routes to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()