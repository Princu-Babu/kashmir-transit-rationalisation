import pandas as pd
import re
import difflib

# --- File names ---
routes_file = 'Kashmir_Route_Frequency_Plan_v3.xlsx'
stops_file = 'Kashmir_Stops_Sectored_V2.csv'
output_file = 'Routes_with_Codes.xlsx'

# District mapping (kept for reference)
district_map = {
    'SRINAGAR': 'SR', 'GANDERBAL': 'GB', 'BANDIPORA': 'BP', 'BARAMULLA': 'BR',
    'KUPWARA': 'KW', 'BUDGAM': 'BG', 'PULWAMA': 'PW', 'SHOPIAN': 'SP',
    'ANANTNAG': 'AN', 'KULGAM': 'KG'
}

routes_df = pd.read_excel(routes_file, sheet_name='Route-Level Plan')
stops_df = pd.read_csv(stops_file)

stops_df['Sector_ID'] = pd.to_numeric(stops_df['Sector_ID'], errors='coerce').fillna(0).astype(int)
stops_df['Stop_No']   = pd.to_numeric(stops_df['Stop_No'],   errors='coerce').fillna(0).astype(int)
stops_df['Stop_Name_Clean'] = stops_df['Stop_Name'].astype(str).str.upper().str.strip()

# A "compact" version: uppercase, no spaces, no punctuation. Helps match
# "PANTHA CHOWK" <-> "PANTHACHOWK", "CHAKIL PORA- SGR" <-> "CHAKILPORASGR" etc.
def compact(s):
    return re.sub(r'[^A-Z0-9]', '', str(s).upper())

stops_df['Stop_Name_Compact'] = stops_df['Stop_Name_Clean'].apply(compact)

# Words that often appear in route names but not in the stops table
NOISE_SUFFIXES = [
    'BUS STAND', 'BUS STATION', 'RAILWAY STATION', 'CROSSING',
    'CHOWK', 'CHOK', 'HOSPITAL', 'COLLEGE', 'STOP', 'STAND',
]

def strip_noise(name):
    n = name
    for w in NOISE_SUFFIXES:
        n = re.sub(rf'\b{w}\b', '', n)
    return re.sub(r'\s+', ' ', n).strip()

def extract_origin_dest(route_name):
    route_name = str(route_name).upper().strip()
    if ' ↔ ' in route_name:
        a, b = route_name.split(' ↔ ', 1)
        return a.strip(), b.strip()
    if ' TO ' in route_name:
        origin, rest = route_name.split(' TO ', 1)
        dest = rest.split(' VIA ')[0] if ' VIA ' in rest else rest
        return origin.strip(), dest.strip()
    return None, None

def get_stop_info(stop_name):
    """Try a sequence of matching strategies, from strict to loose."""
    if not stop_name:
        return None

    name = stop_name.strip()
    name_compact = compact(name)
    name_stripped = strip_noise(name)
    name_stripped_compact = compact(name_stripped)

    # 1. Exact match on cleaned name
    m = stops_df[stops_df['Stop_Name_Clean'] == name]
    # 2. Compact (whitespace/punct removed) exact match -> handles "PANTHA CHOWK" vs "PANTHACHOWK"
    if m.empty and name_compact:
        m = stops_df[stops_df['Stop_Name_Compact'] == name_compact]
    # 3. Compact match after stripping common suffixes ("CHADOORA CHOWK" -> "CHADOORA")
    if m.empty and name_stripped_compact:
        m = stops_df[stops_df['Stop_Name_Compact'] == name_stripped_compact]
    # 4. Substring either way
    if m.empty and name_stripped_compact:
        m = stops_df[stops_df['Stop_Name_Compact'].str.contains(name_stripped_compact, regex=False, na=False)]
    if m.empty and name_stripped_compact:
        m = stops_df[stops_df['Stop_Name_Compact'].apply(lambda s: s in name_stripped_compact and len(s) >= 4)]
    # 5. Close-match fallback (catches "BATAMALOO" vs "BATAMALLO")
    if m.empty and name_stripped_compact:
        close = difflib.get_close_matches(name_stripped_compact, stops_df['Stop_Name_Compact'].tolist(), n=1, cutoff=0.85)
        if close:
            m = stops_df[stops_df['Stop_Name_Compact'] == close[0]]

    if m.empty:
        return None

    row = m.iloc[0]
    return {
        'Tehsil_Code': str(row['Tehsil_Code']).strip()[:2].upper(),
        'Sector_ID':   f"{row['Sector_ID']:02d}",
        'Stop_No':     f"{row['Stop_No']:02d}",
    }

route_codes = []
for _, row in routes_df.iterrows():
    origin, dest = extract_origin_dest(row['Route_Name'])
    orig_info = get_stop_info(origin)
    dest_info = get_stop_info(dest)

    if orig_info and dest_info:
        district_block = orig_info['Tehsil_Code'] + dest_info['Tehsil_Code']
        sector_block   = orig_info['Sector_ID']   + dest_info['Sector_ID']
        stop_block     = orig_info['Stop_No']     + dest_info['Stop_No']
        # <-- THE CHANGE YOU ASKED FOR: no hyphens.
        final_code = f"{district_block}{sector_block}{stop_block}"
        route_codes.append(final_code)
    else:
        route_codes.append("UNMATCHED")

# Insert / replace Route_Code column right after Route_Name
if 'Route_Code' in routes_df.columns:
    routes_df['Route_Code'] = route_codes
else:
    idx = routes_df.columns.get_loc('Route_Name')
    routes_df.insert(idx + 1, 'Route_Code', route_codes)

routes_df.to_excel(output_file, index=False)
print(f"Saved {output_file}. Matched: {sum(c != 'UNMATCHED' for c in route_codes)} / {len(route_codes)}")
