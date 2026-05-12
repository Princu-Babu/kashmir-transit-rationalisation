import pandas as pd
import os
import json

MINI_BUS_FILE = "Mini Buses Routes in Srinagar.xlsx"
CACHE_FILE = "geocode_cache.json"

def clean_location(loc):
    if pd.isna(loc):
        return None
    loc_str = str(loc).strip().upper()
    loc_str = loc_str.replace("AND VICE VERSA", "").replace("& VICE VERSA", "").replace("-VICE VERSA", "").replace("VICE VERSA", "")
    return loc_str.strip() if loc_str.strip() else None

def main():
    if not os.path.exists(MINI_BUS_FILE):
        print(f"Error: {MINI_BUS_FILE} not found.")
        return

    # Load data
    df = pd.read_excel(MINI_BUS_FILE)
    
    # Load cache
    cache = {}
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r') as f:
            cache = json.load(f)
    
    # Filter for SRINAGAR RTO
    if 'Office Name' in df.columns:
        df = df[df['Office Name'] == 'SRINAGAR RTO']
    
    unique_locations = set()
    for col in ['From Location', 'To Location', 'Via Location']:
        if col in df.columns:
            for loc in df[col].dropna():
                if col == 'Via Location':
                    parts = [p.strip() for p in str(loc).split(',')]
                    for p in parts:
                        cleaned = clean_location(p)
                        if cleaned:
                            unique_locations.add(cleaned)
                else:
                    cleaned = clean_location(loc)
                    if cleaned:
                        unique_locations.add(cleaned)
    
    # Build list with coordinates
    data = []
    for loc in sorted(list(unique_locations)):
        coords = cache.get(loc, {})
        data.append({
            'Location': loc,
            'Latitude': coords.get('lat'),
            'Longitude': coords.get('lon')
        })
    
    output_file = "srinagar_unique_locations.csv"
    pd.DataFrame(data).to_csv(output_file, index=False)
    
    print(f"Successfully extracted {len(data)} unique locations with coordinates.")
    print(f"Saved to {output_file}")

if __name__ == "__main__":
    main()
