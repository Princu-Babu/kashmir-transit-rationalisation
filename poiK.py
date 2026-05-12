import osmium
import pandas as pd
import time

print("🚀 Initializing HIGH-TRAFFIC Offline PBF POI Extractor...")

PBF_FILE = "india-latest.osm.pbf"
OUTPUT_FILE = "kashmir_hightraffic_pois.csv"

# Greater Kashmir Bounding Box
MIN_LAT, MIN_LON = 33.10, 73.70
MAX_LAT, MAX_LON = 34.90, 75.60

class HighTrafficPOIHandler(osmium.SimpleHandler):
    def __init__(self):
        super(HighTrafficPOIHandler, self).__init__()
        self.poi_list = []
        self.count = 0

    def node(self, n):
        # 1. Bounding box check
        if MIN_LAT <= n.location.lat <= MAX_LAT and MIN_LON <= n.location.lon <= MAX_LON:
            tags = n.tags
            
            # 2. RUTHLESS FILTER #1: If it doesn't have a name, drop it immediately.
            if 'name' not in tags and 'name:en' not in tags:
                return

            # 3. Check for broad categories to save processing time
            if not any(k in tags for k in ('amenity', 'shop', 'tourism', 'historic', 'leisure')):
                return

            poi_type = "Other"
            importance = "None"
            category_found = False
            
            # --- RUTHLESS FILTER #2: Only keep High/Medium traffic targets ---
            
            # Healthcare (Dropped pharmacies/doctors)
            if tags.get('amenity') == 'hospital': 
                poi_type, importance, category_found = 'Major Hospital', 'High', True
            elif tags.get('amenity') == 'clinic': 
                poi_type, importance, category_found = 'Clinic', 'Medium', True
            
            # Education (Kept all, schools generate massive daily traffic)
            elif tags.get('amenity') in ['university', 'college']: 
                poi_type, importance, category_found = 'Higher Education', 'High', True
            elif tags.get('amenity') == 'school': 
                poi_type, importance, category_found = 'School', 'Medium', True
            
            # Markets (Dropped generic 'shop' tag, kept large retail)
            elif tags.get('shop') == 'mall' or tags.get('amenity') == 'marketplace': 
                poi_type, importance, category_found = 'Major Market/Mall', 'High', True
            elif tags.get('shop') in ['supermarket', 'department_store', 'wholesale']: 
                poi_type, importance, category_found = 'Supermarket/Wholesale', 'Medium', True
            
            # Tourism (Kept major attractions)
            elif tags.get('tourism') in ['museum', 'attraction'] or 'historic' in tags: 
                poi_type, importance, category_found = 'Tourist Spot', 'High', True
            elif tags.get('amenity') in ['cinema', 'theatre', 'events_venue']: 
                poi_type, importance, category_found = 'Entertainment', 'Medium', True
            
            # Leisure (Dropped generic parks/playgrounds)
            elif tags.get('leisure') in ['stadium', 'nature_reserve']: 
                poi_type, importance, category_found = 'Major Leisure/Stadium', 'High', True

            # If it survived the gauntlet, save it
            if category_found:
                name = tags.get('name', tags.get('name:en'))
                self.poi_list.append({
                    'Name': name,
                    'Category': poi_type,
                    'Importance': importance,
                    'Latitude': n.location.lat,
                    'Longitude': n.location.lon,
                    'City/Town': tags.get('addr:city', 'Greater Kashmir Region')
                })
                
                self.count += 1
                if self.count % 500 == 0:
                    print(f"   ⚡ Found {self.count} High-Traffic POIs so far...")

# --- EXECUTION ---
start_time = time.time()
handler = HighTrafficPOIHandler()

print(f"📡 Scanning {PBF_FILE} for heavy-hitter locations...")
handler.apply_file(PBF_FILE)

if handler.poi_list:
    df = pd.DataFrame(handler.poi_list)
    
    importance_map = {'High': 1, 'Medium': 2}
    df['Rank'] = df['Importance'].map(importance_map)
    df = df.sort_values(by=['Rank', 'Category']).drop(columns=['Rank'])
    
    df.to_csv(OUTPUT_FILE, index=False)
    print(f"\n🎉 DONE! Distilled the data down to {len(df)} High-Traffic POIs.")
else:
    print("\n❌ No POIs found. Check your bounding box.")

print(f"⏱️ Total execution time: {round(time.time() - start_time, 2)} seconds.")