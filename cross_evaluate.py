"""
cross_evaluate.py — v3.2

Compares the rationalisation engine's outputs against three CHALO ground-truth
datasets (Ridership monthly totals, Route-Wise deployed buses, Hourly passenger
counts). Reports system-level fleet / KM / trip parity plus a single objective
value (sum of squared % errors) that a future calibration loop can minimise.

v3.2 changes vs v3.1:
  • 12-month average instead of cherry-picked May (May = tourist peak, January
    = Chillai Kalan trough; using one month produced misleading targets).
  • Per-month days-of-month divisor via calendar.monthrange (not a fixed /31).
  • mode_share / trip_rate promoted to named module constants documented
    against SSCL's free-fare ridership regime.
  • Objective function: SSE of % errors across {SSCL fleet, daily KM, daily trips}.
  • Loud message when Population_Served sums to zero (catches regressions of the
    WorldPop raster bug, which was the original v3.1 silent failure).
"""

import calendar
import pandas as pd
import numpy as np
import json
import re

# ─── Calibration constants (v3.2) ─────────────────────────────────────────────
# Citywide observed bus mode share under SSCL's free-fare regime — higher than
# the 6% the v3.1 module assumed (that figure was a pre-free-fare estimate).
MODE_SHARE = 0.09
# Trip rate (trips per served person per day). SSCL data shows ~1.6 for the
# women segment, dragging the citywide mean above the original 1.3 estimate.
TRIP_RATE  = 1.6

# Calendar (matches the FY 2025-26 + April 2026 rows in Ridership Data.csv)
MONTH_ORDER = [
    ("May",       2025, 5),
    ("June",      2025, 6),
    ("July",      2025, 7),
    ("August",    2025, 8),
    ("September", 2025, 9),
    ("October",   2025, 10),
    ("November",  2025, 11),
    ("December",  2025, 12),
    ("January",   2026, 1),
    ("Feburary",  2026, 2),  # note: typo "Feburary" exists in source CSV
    ("March",     2026, 3),
    ("April",     2026, 4),
]


def parse_indian_number(val):
    if pd.isna(val):
        return 0
    if isinstance(val, (int, float)):
        return float(val)
    cleaned = re.sub(r'[^\d.]', '', str(val))
    if not cleaned:
        return 0
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
        return pd.read_csv('e:/kash/.claude/worktrees/busy-euclid-7fcf2e/'
                           'Rationalised_Routes_Kashmir_v3.csv')
    except Exception:
        try:
            return pd.read_csv('Rationalised_Routes_Kashmir_v3.csv')
        except Exception as e:
            print(f"Could not load engine output: {e}")
            return None


def _twelve_month_daily_avg(ridership: pd.DataFrame, col: str) -> float:
    """
    Compute a per-day average across all 12 months in MONTH_ORDER, weighted
    by each month's actual number of days. This is structurally more honest
    than dividing one month's total by 31 — May has 31 days, February 28.

    Values may arrive as Indian-format strings ("10,10,193") if `load_chalo_data`'s
    auto-parser didn't strip them, so we route every read through `parse_indian_number`.
    """
    total_value = 0.0
    total_days  = 0
    for name, year, month in MONTH_ORDER:
        sub = ridership[ridership['Month'] == name]
        if sub.empty:
            continue
        row = sub.iloc[0]
        raw = row[col]
        if pd.isna(raw):
            continue
        val = parse_indian_number(raw)
        days_in_month = calendar.monthrange(year, month)[1]
        total_value += val
        total_days  += days_in_month
    return total_value / total_days if total_days > 0 else 0.0


def evaluate(ridership, buses, hourly, engine_out):
    print("=== CHALO vs Engine Cross-Evaluation (v3.2 — 12-month average) ===\n")

    if engine_out is None:
        print("Run transit_kashmir_v3.py first to generate outputs for comparison.")
        return None

    # ─── Level 1: System-wide totals (12-month daily average) ────────────────
    print("--- Level 1: System-Wide Totals (12-month daily averages) ---")
    chalo_daily_pax   = _twelve_month_daily_avg(ridership, 'Total')
    chalo_daily_km    = _twelve_month_daily_avg(ridership, 'Operated KM')
    chalo_daily_trips = _twelve_month_daily_avg(ridership, 'Trip Count')

    print(f"CHALO Daily Pax (12-mo avg): ~{chalo_daily_pax:,.0f}")
    print(f"CHALO Daily Operated KM:     ~{chalo_daily_km:,.0f}")
    print(f"CHALO Daily Trips:           ~{chalo_daily_trips:,.0f}")

    engine_active = engine_out[engine_out['Action_Taken'] != 'MERGED_INTO_TRUNK'].copy()
    total_fleet = engine_active['Fleet_Required'].sum()
    print(f"\nEngine Total Fleet Required (all routes): {total_fleet:.0f} buses")

    service_hours = 16  # 6 AM to 10 PM (SSCL operational window)
    engine_active['Daily_Trips'] = (service_hours * 60) / engine_active['Headway_Min'] * 2
    engine_active['Daily_KM']    = engine_active['Daily_Trips'] * engine_active['Route_KM']

    # Scope match: CHALO ridership data covers SSCL routes only. Compare like
    # to like — pull the engine's SSCL-only subset for the KM/Trips error
    # calculation, but keep the full-network numbers in the printout for context.
    engine_sscl_only = engine_active[engine_active['CMP_Trunk'] == True]
    engine_daily_trips     = engine_active['Daily_Trips'].sum()
    engine_daily_km        = engine_active['Daily_KM'].sum()
    engine_sscl_daily_trips = engine_sscl_only['Daily_Trips'].sum()
    engine_sscl_daily_km    = engine_sscl_only['Daily_KM'].sum()

    print(f"Engine Daily Trips (all): ~{engine_daily_trips:,.0f}  "
          f"(SSCL-only: ~{engine_sscl_daily_trips:,.0f})")
    print(f"Engine Daily KM    (all): ~{engine_daily_km:,.0f}  "
          f"(SSCL-only: ~{engine_sscl_daily_km:,.0f})")

    # Catch the WorldPop-zero regression case loudly
    pop_total = engine_active['Population_Served'].sum() if 'Population_Served' in engine_active else 0
    if pop_total <= 0:
        print("⚠ Engine Population_Served sums to ZERO — WorldPop raster bug is back. "
              "Check RASTER_PATH and rasterstats installation before trusting any "
              "downstream comparison.")

    engine_implied_pax = pop_total * MODE_SHARE * TRIP_RATE
    print(f"Engine Implied Daily Pax ({MODE_SHARE*100:.0f}% mode share, "
          f"{TRIP_RATE} trips/day): ~{engine_implied_pax:,.0f}")

    # ─── Level 2: SSCL route-level fleet ──────────────────────────────────────
    print("\n--- Level 2: SSCL Route Fleet ---")
    chalo_total_fleet = buses['New Deployement'].sum()
    engine_sscl       = engine_out[engine_out['CMP_Trunk'] == True]
    engine_sscl_fleet = engine_sscl['Fleet_Required'].sum()
    print(f"CHALO Total SSCL Fleet Deployed:   {chalo_total_fleet}")
    print(f"Engine Total SSCL Fleet Recommended: {engine_sscl_fleet}")

    # ─── Level 3: Temporal shape (informational; engine is flat-headway) ─────
    print("\n--- Level 3: Temporal Shape ---")
    avg_hourly  = hourly.groupby('Hours')['Passenger Count'].mean()
    peak_hour   = avg_hourly.idxmax()
    peak_pax    = avg_hourly.max()
    trough_hour = avg_hourly.idxmin()
    trough_pax  = avg_hourly.min()
    print(f"CHALO Peak Hour:   {peak_hour}:00 with ~{peak_pax:.0f} pax")
    print(f"CHALO Trough Hour: {trough_hour}:00 with ~{trough_pax:.0f} pax")
    print("Engine currently uses flat headways — time-of-day multipliers are v4.")

    # ─── Objective ────────────────────────────────────────────────────────────
    def _pct_err(engine, chalo):
        return 0.0 if chalo == 0 else ((engine - chalo) / chalo) * 100.0

    # All errors computed on the SSCL-only subset for apples-to-apples
    # comparison against CHALO ridership data (which is SSCL-only).
    fleet_err = _pct_err(engine_sscl_fleet,        chalo_total_fleet)
    km_err    = _pct_err(engine_sscl_daily_km,     chalo_daily_km)
    trips_err = _pct_err(engine_sscl_daily_trips,  chalo_daily_trips)
    objective = fleet_err ** 2 + km_err ** 2 + trips_err ** 2

    print("\n--- Objective (sum of squared %% errors, SSCL-only vs CHALO) ---")
    print(f"  SSCL fleet  : {fleet_err:+.1f}%")
    print(f"  Daily KM    : {km_err:+.1f}%")
    print(f"  Daily trips : {trips_err:+.1f}%")
    print(f"  Objective   : {objective:,.1f}   (lower = closer to CHALO ground truth)")

    # ─── Calibration advice ──────────────────────────────────────────────────
    print("\n--- Calibration Advice ---")
    if engine_sscl_fleet > chalo_total_fleet * 1.15:
        print(f"Engine SSCL fleet ({engine_sscl_fleet}) is >15% above CHALO ({chalo_total_fleet}).")
        print("→ Try: raise SSCL_TRUNK_HEADWAY_MIN, lower STOP_PENALTY_MIN, or relax "
              "CONGESTION_CITY_CORE.")
    elif engine_sscl_fleet < chalo_total_fleet * 0.85:
        print(f"Engine SSCL fleet ({engine_sscl_fleet}) is >15% below CHALO ({chalo_total_fleet}).")
        print("→ Try: lower SSCL_TRUNK_HEADWAY_MIN, raise CONGESTION_CITY_CORE.")
    else:
        print(f"Engine SSCL fleet within ±15% of CHALO ({engine_sscl_fleet} vs {chalo_total_fleet}).")

    if engine_daily_km > chalo_daily_km * 1.2:
        print("Engine Daily KM is >20% higher than CHALO — consider lowering "
              "OVERLAP_THRESHOLD or TRUNK_CDI_GATE_PERCENTILE to thin the active set.")

    return {
        "fleet_err_pct": fleet_err,
        "km_err_pct":    km_err,
        "trips_err_pct": trips_err,
        "objective":     objective,
    }


if __name__ == "__main__":
    ridership, buses, hourly = load_chalo_data()
    engine_out = load_engine_output()
    evaluate(ridership, buses, hourly, engine_out)
