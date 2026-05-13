import rasterio
from rasterio.windows import from_bounds
import math

in_path = "ind_ppp_2026_100m.tif"
out_path = "kashmir_worldpop.tif"

# Srinagar / Kashmir Bounding Box from transit_kashmir_v3.py
BOUNDS_MIN_LON = 74.40
BOUNDS_MIN_LAT = 33.50
BOUNDS_MAX_LON = 75.20
BOUNDS_MAX_LAT = 34.50

print(f"Opening {in_path}...")
with rasterio.open(in_path) as src:
    print(f"Original raster size: {src.width}x{src.height}")
    print(f"Original raster bounds: {src.bounds}")
    
    # Get window from geographic bounds
    window = from_bounds(BOUNDS_MIN_LON, BOUNDS_MIN_LAT, BOUNDS_MAX_LON, BOUNDS_MAX_LAT, src.transform)
    
    # The window coordinates might be floats; round them to integers for reading
    # from_bounds returns a Window object which can be read directly by rasterio.
    
    print(f"Cropping to window: {window}")
    
    # Read the data within the window
    data = src.read(window=window)
    
    # Calculate the transform for the new window
    window_transform = src.window_transform(window)
    
    # Update the metadata for the output file
    meta = src.meta.copy()
    meta.update({
        'height': window.height,
        'width': window.width,
        'transform': window_transform
    })
    
    print(f"Writing cropped data to {out_path}...")
    with rasterio.open(out_path, 'w', **meta) as dst:
        dst.write(data)
        
print("Done! kashmir_worldpop.tif is ready.")
