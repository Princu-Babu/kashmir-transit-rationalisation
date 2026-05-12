import pandas as pd
import requests
import folium
from folium import plugins
from shapely.geometry import LineString, Polygon, mapping

# 1. Define the Kashmir Boundary
KASHMIR_BBOX = Polygon([
    (73.2, 32.2), (77.0, 32.2), (77.0, 35.3), (73.2, 35.3), (73.2, 32.2)
])

OSRM_URL = "http://localhost:5000/route/v1/driving/"

# 2. Color Dictionary for Vehicle Categories
CATEGORY_COLORS = {
    'LPV': '#e6194b',          # Red
    'MPV': '#3cb44b',          # Green
    'HPV': '#ffe119',          # Yellow
    'EBus': '#4363d8',         # Blue
    'MPS Bus': '#f58231',      # Orange
    'Regular Bus': '#911eb4',  # Purple
    'City Bus': '#46f0f0',     # Cyan
    'MTS Bus': '#f032e6',      # Magenta
    'Unknown': '#808080'       # Grey fallback
}

def get_osrm_route(start_lon, start_lat, end_lon, end_lat, via_lon=None, via_lat=None):
    """Fetches the route from OSRM, considering 'via' points if they exist."""
    # Build coordinates string based on presence of a VIA point
    if pd.notna(via_lon) and pd.notna(via_lat):
        coords = f"{start_lon},{start_lat};{via_lon},{via_lat};{end_lon},{end_lat}"
    else:
        coords = f"{start_lon},{start_lat};{end_lon},{end_lat}"
        
    url = f"{OSRM_URL}{coords}?geometries=geojson"
    
    try:
        response = requests.get(url)
        data = response.json()
        if data.get('code') == 'Ok':
            return data['routes'][0]['geometry']['coordinates']
    except Exception:
        pass
    return None

def clip_route_to_boundary(route_coords, boundary_polygon):
    """Cuts the route at the Kashmir boundary wall."""
    if not route_coords or len(route_coords) < 2:
        return None
        
    route_line = LineString(route_coords)
    clipped_line = route_line.intersection(boundary_polygon)
    
    if clipped_line.is_empty:
        return None
        
    return mapping(clipped_line)

def plot_interactive_routes(input_csv, output_file="kashmir_interactive_routes.html"):
    print(f"Loading data from {input_csv}...")
    try:
        df = pd.read_csv(input_csv)
    except FileNotFoundError:
        print(f"Error: Could not find {input_csv}.")
        return

    # Initialize Folium Map
    m = folium.Map(location=[34.0837, 74.7973], zoom_start=9)
    
    # Add the Geofence Boundary
    folium.GeoJson(
        mapping(KASHMIR_BBOX),
        name="Kashmir Boundary Wall",
        style_function=lambda x: {'color': 'black', 'fillColor': 'transparent', 'weight': 2, 'dashArray': '5, 5'}
    ).add_to(m)

    # 3. Create FeatureGroups (Checkboxes) for each Vehicle Category
    feature_groups = {}
    categories = df['Vehicle Category'].fillna('Unknown').unique()
    for cat in categories:
        # Create a layer for this category and add it to the map
        fg = folium.FeatureGroup(name=str(cat))
        feature_groups[str(cat)] = fg
        m.add_child(fg)

    count = 0
    print("Plotting routes and generating interactive layers...")
    
    for index, row in df.iterrows():
        cat = str(row.get('Vehicle Category', 'Unknown'))
        if cat == 'nan': cat = 'Unknown'
        
        route_color = CATEGORY_COLORS.get(cat, CATEGORY_COLORS['Unknown'])

        if pd.notna(row.get('From_Lat')) and pd.notna(row.get('To_Lat')):
            s_lat, s_lon = row['From_Lat'], row['From_Lon']
            e_lat, e_lon = row['To_Lat'], row['To_Lon']
            
            # Check for Via coordinates
            v_lat, v_lon = row.get('Via_Lat'), row.get('Via_Lon')
            
            # 1. Fetch Route
            raw_coords = get_osrm_route(s_lon, s_lat, e_lon, e_lat, v_lon, v_lat)
            
            if raw_coords:
                # 2. Clip at Boundary
                clipped_geometry = clip_route_to_boundary(raw_coords, KASHMIR_BBOX)
                
                if clipped_geometry:
                    # Formulate route string
                    route_name = f"{row.get('From Location')} -> {row.get('To Location')}"
                    if pd.notna(row.get('Via Location')):
                        route_name = f"{row.get('From Location')} -> {row.get('Via Location')} -> {row.get('To Location')}"

                    # 3. Create rich GeoJSON feature for Hover Tooltips
                    feature = {
                        "type": "Feature",
                        "geometry": clipped_geometry,
                        "properties": {
                            "Route": route_name,
                            "Category": cat,
                            "Permit Type": str(row.get('Permit Type', 'N/A')),
                            "Service": str(row.get('Permit Service Type Name', 'N/A'))
                        }
                    }

                    # Add route line to specific category group
                    folium.GeoJson(
                        feature,
                        style_function=lambda x, color=route_color: {
                            'color': color, 
                            'weight': 4, 
                            'opacity': 0.8
                        },
                        tooltip=folium.GeoJsonTooltip(
                            fields=['Route', 'Category', 'Permit Type', 'Service'],
                            aliases=['Route Path:', 'Vehicle:', 'Permit:', 'Service:'],
                            localize=True
                        )
                    ).add_to(feature_groups[cat])

                    # 4. Add Map Pins (Origin, Via, Destination)
                    # Origin (Green)
                    folium.Marker(
                        location=[s_lat, s_lon],
                        popup=f"Start: {row.get('From Location')}",
                        icon=folium.Icon(color='green', icon='play')
                    ).add_to(feature_groups[cat])
                    
                    # Destination (Red)
                    folium.Marker(
                        location=[e_lat, e_lon],
                        popup=f"End: {row.get('To Location')}",
                        icon=folium.Icon(color='red', icon='stop')
                    ).add_to(feature_groups[cat])
                    
                    # Via Point (Orange)
                    if pd.notna(v_lat):
                        folium.Marker(
                            location=[v_lat, v_lon],
                            popup=f"Via: {row.get('Via Location')}",
                            icon=folium.Icon(color='orange', icon='info-sign')
                        ).add_to(feature_groups[cat])

                    count += 1
                    if count % 20 == 0:
                        print(f"Processed {count} valid routes...")

    # 4. Add the Layer Control (This creates the checkbox filter UI)
    folium.LayerControl(collapsed=False).add_to(m)

    m.save(output_file)
    print(f"\nAwesome! Plotted {count} interactive routes.")
    print(f"Map saved as '{output_file}'. Open it in your browser.")

if __name__ == "__main__":
    plot_interactive_routes('kashmir_routes_geocoded.csv')


