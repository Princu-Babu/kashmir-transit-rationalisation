import pandas as pd
import numpy as np
import json
import re

def parse_indian_number(val):
    if pd.isna(val):
        return 0
    if isinstance(val, (int, float)):
        return float(val)
    # Remove rupees, commas, spaces
    cleaned = re.sub(r'[^\d.]', '', str(val))
    if not cleaned: return 0
    return float(cleaned)

def load_chalo_data():
    ridership = pd.read_csv('e:/kash/Ridership Data.csv', skip_blank_lines=True)
    ridership = ridership.dropna(how='all')
    
    for col in ridership.columns:
        if ridership[col].dtype == object and ridership[col].str.contains(',|₹').any():
            ridership[col] = ridership[col].apply(parse_indian_number)
            
    buses = pd.read_csv('e:/kash/Route Wise deployed Buses.csv')
    buses = buses.dropna(subset=['PROPSED ROUTE NO', 'PROPOSED ROUTE NAME'])
    
    hourly = pd.read_csv('e:/kash/Hourly Passenger Count.csv', skiprows=1)
    hourly = hourly.dropna(subset=['DATE', 'Hours'])
    
    return ridership, buses, hourly

def load_engine_output():
    try:
        return pd.read_csv('e:/kash/Rationalised_Routes_Kashmir_v3.csv')
    except Exception as e:
        print(f"Could not load engine output: {e}")
        return None

def evaluate(ridership, buses, hourly, engine_out):
    print("=== CHALO vs Engine Cross-Evaluation ===\n")
    
    if engine_out is None:
        print("Run transit_kashmir_v3.py first to generate outputs for comparison.")
        return
        
    # Level 1: System-wide
    print("--- Level 1: System-Wide Totals ---")
    
    # Estimate CHALO daily metrics based on May 2025
    may_data = ridership[(ridership['Month'] == 'May')].iloc[0]
    chalo_daily_pax = may_data['Total'] / 31
    chalo_daily_km = may_data['Operated KM'] / 31
    chalo_daily_trips = may_data['Trip Count'] / 31
    
    print(f"CHALO Daily Pax (May): ~{chalo_daily_pax:,.0f}")
    print(f"CHALO Daily Operated KM: ~{chalo_daily_km:,.0f}")
    print(f"CHALO Daily Trips: ~{chalo_daily_trips:,.0f}")
    
    engine_active = engine_out[engine_out['Action_Taken'] != 'MERGED_INTO_TRUNK']
    total_fleet = engine_active['Fleet_Required'].sum()
    print(f"\nEngine Total Fleet Required: {total_fleet:.0f} buses")
    
    # Estimate engine trips and KM
    service_hours = 16 # 6 AM to 10 PM
    engine_active['Daily_Trips'] = (service_hours * 60) / engine_active['Headway_Min'] * 2
    engine_active['Daily_KM'] = engine_active['Daily_Trips'] * engine_active['Route_KM']
    
    engine_daily_trips = engine_active['Daily_Trips'].sum()
    engine_daily_km = engine_active['Daily_KM'].sum()
    
    print(f"Engine Estimated Daily Trips: ~{engine_daily_trips:,.0f}")
    print(f"Engine Estimated Daily KM: ~{engine_daily_km:,.0f}")
    
    # Engine implied pax (assuming mode share and trip rate)
    mode_share = 0.06
    trip_rate = 1.3
    engine_implied_pax = engine_active['Population_Served'].sum() * mode_share * trip_rate
    print(f"Engine Implied Daily Pax (6% mode share, 1.3 trips/day): ~{engine_implied_pax:,.0f}")
    
    # Level 2: Route-level
    print("\n--- Level 2: SSCL Route Fleet ---")
    chalo_total_fleet = buses['New Deployement'].sum()
    engine_sscl = engine_out[engine_out['CMP_Trunk'] == True]
    engine_sscl_fleet = engine_sscl['Fleet_Required'].sum()
    
    print(f"CHALO Total SSCL Fleet Deployed: {chalo_total_fleet}")
    print(f"Engine Total SSCL Fleet Recommended: {engine_sscl_fleet}")
    
    # Level 3: Temporal
    print("\n--- Level 3: Temporal Shape ---")
    avg_hourly = hourly.groupby('Hours')['Passenger Count'].mean()
    peak_hour = avg_hourly.idxmax()
    peak_pax = avg_hourly.max()
    trough_hour = avg_hourly.idxmin()
    trough_pax = avg_hourly.min()
    
    print(f"CHALO Peak Hour: {peak_hour}:00 with ~{peak_pax:.0f} pax")
    print(f"CHALO Trough Hour: {trough_hour}:00 with ~{trough_pax:.0f} pax")
    print("Engine currently uses flat headways. Consider implementing time-of-day multipliers.")
    
    print("\n--- Calibration Advice ---")
    if engine_sscl_fleet > chalo_total_fleet * 1.2:
        print("Engine fleet is >20% higher than CHALO.")
        print("-> Tweak: Increase SSCL_TRUNK_HEADWAY_MIN, decrease STOP_PENALTY_MIN or CONGESTION multipliers.")
    elif engine_sscl_fleet < chalo_total_fleet * 0.8:
        print("Engine fleet is >20% lower than CHALO.")
        print("-> Tweak: Decrease SSCL_TRUNK_HEADWAY_MIN, increase CONGESTION multipliers.")
    else:
        print("Engine fleet is within reasonable bounds of CHALO data.")
        
    if engine_daily_km > chalo_daily_km * 1.2:
        print("Engine Daily KM is >20% higher than CHALO.")
        print("-> Tweak: Decrease OVERLAP_THRESHOLD, lower TRUNK_CDI_GATE_PERCENTILE to reduce active routes.")

if __name__ == "__main__":
    ridership, buses, hourly = load_chalo_data()
    engine_out = load_engine_output()
    evaluate(ridership, buses, hourly, engine_out)
