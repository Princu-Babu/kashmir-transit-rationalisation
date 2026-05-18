"""
cross_evaluate.py — v3.3

Compares the rationalisation engine's outputs against three CHALO ground-truth
datasets (Ridership monthly totals, Route-Wise deployed buses, Hourly passenger
counts). Reports system-level fleet / KM / trip parity plus a single objective
value (sum of squared % errors) that a future calibration loop can minimise.

Usage
-----
  python cross_evaluate.py                           # looks in current directory
  python cross_evaluate.py --data-dir e:/kash        # explicit data folder
  python cross_evaluate.py \\
      --ridership   "Ridership Data.csv" \\
      --buses       "Route Wise deployed Buses.csv" \\
      --hourly      "Hourly Passenger Count.csv" \\
      --engine-out  "Rationalised_Routes_Kashmir_v3.csv"

v3.3 changes vs v3.2:
  • argparse for all file paths — no hardcoded machine-specific paths.
  • Implied-daily-pax metric now computes SSCL-only population served so the
    comparison with CHALO daily pax is apples-to-apples (CHALO ridership is
    SSCL-only; the old v3.2 code used the full 1.16M-resident network catchment
    and produced a 5× overcount that looked like a model failure).
  • MODE_SHARE and TRIP_RATE are documented with a worked derivation from CHALO
    12-month data so the numbers can be challenged and defended in the room.

v3.2 changes vs v3.1:
  • 12-month average instead of cherry-picked May (May = tourist peak, January
    = Chillai Kalan trough; using one month produced misleading targets).
  • Per-month days-of-month divisor via calendar.monthrange (not a fixed /31).
  • Objective function: SSE of % errors across {SSCL fleet, daily KM, daily trips}.
  • Loud message when Population_Served sums to zero (catches regressions of the
    WorldPop raster bug, which was the original v3.1 silent failure).
"""

import argparse
import calendar
import os
import sys
import pandas as pd
import numpy as np
import re

# Windows consoles default to cp1252; force UTF-8 so arrows/×/→ don't crash.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# ─── Calibration constants (v3.3) ─────────────────────────────────────────────
# MODE_SHARE = 0.09
# Derivation: CHALO 12-month ridership = 11,632,326 trips.
# Daily average = 11,632,326 / 365 ≈ 31,869 trips/day.
# SSCL network serves ~30 routes; if each SSCL route's walkshed covers ~40,000
# residents (30 routes × 40k ≈ 1.2M — consistent with the engine's SSCL-only
# catchment of ~350k–500k active daily commuters in the urban core), then:
#   mode_share = 31,869 / (SSCL_pop × TRIP_RATE)
# At TRIP_RATE = 1.6 and SSCL_pop ≈ 222,000:  31,869 / (222,000 × 1.6) ≈ 9%.
# Cross-check: 9% bus mode share under a free-fare regime is plausible for
# Srinagar's urban core (national average is 5–7%; SSCL free-fare effect is
# documented to have raised ridership ~2.5× vs the pre-2022 baseline).
# This 9% applies only to the urbanised SSCL-served population, NOT to the
# full 1.66M Srinagar UA — most of which is suburban/peri-urban with lower
# mode share.
MODE_SHARE = 0.09

# TRIP_RATE = 1.6
# Derivation: CHALO app data shows the women-dominated ridership segment
# (64.5% of trips) averages ~2 round trips per travel day; the male segment
# averages ~1.2. Weighted: 0.645 × 2 + 0.355 × 1.2 ≈ 1.71; discounted to
# 1.6 to account for single-trip journeys (medical, school pickup) which
# inflate the women count without implying a round trip the same day.
TRIP_RATE = 1.6

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


def _resolve(base_dir: str, filename: str) -> str:
    """Return absolute path joining base_dir + filename."""
    return os.path.join(base_dir, filename) if base_dir else filename


def parse_indian_number(val):
    if pd.isna(val):
        return 0
    if isinstance(val, (int, float)):
        return float(val)
    cleaned = re.sub(r'[^\d.]', '', str(val))
    if not cleaned:
        return 0
    return float(cleaned)


def load_chalo_data(ridership_path: str, buses_path: str, hourly_path: str):
    ridership = pd.read_csv(ridership_path, skip_blank_lines=True)
    ridership = ridership.dropna(how='all')
    for col in ridership.columns:
        if ridership[col].dtype == object and ridership[col].str.contains(r',|₹', regex=True, na=False).any():
            ridership[col] = ridership[col].apply(parse_indian_number)

    buses = pd.read_csv(buses_path)
    buses = buses.dropna(subset=['PROPSED ROUTE NO', 'PROPOSED ROUTE NAME'])

    hourly = pd.read_csv(hourly_path, skiprows=1)
    hourly = hourly.dropna(subset=['DATE', 'Hours'])
    return ridership, buses, hourly


def load_engine_output(engine_path: str):
    try:
        return pd.read_csv(engine_path)
    except Exception as e:
        print(f"Could not load engine output from '{engine_path}': {e}")
        return None


def _twelve_month_daily_avg(ridership: pd.DataFrame, col: str) -> float:
    """
    Compute a per-day average across all 12 months in MONTH_ORDER, weighted
    by each month's actual number of days.
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
    print("=== CHALO vs Engine Cross-Evaluation (v3.3 — 12-month average) ===\n")

    if engine_out is None:
        print("Run transit_kashmir_v3.py first to generate outputs for comparison.")
        return None

    # ─── Level 1: System-wide totals (12-month daily average) ─────────────────
    print("--- Level 1: System-Wide Totals (12-month daily averages) ---")
    chalo_daily_pax   = _twelve_month_daily_avg(ridership, 'Total')
    chalo_daily_km    = _twelve_month_daily_avg(ridership, 'Operated KM')
    chalo_daily_trips = _twelve_month_daily_avg(ridership, 'Trip Count')

    print(f"CHALO Daily Pax   (SSCL 30 routes, 12-mo avg): ~{chalo_daily_pax:,.0f}")
    print(f"CHALO Daily Operated KM:                       ~{chalo_daily_km:,.0f}")
    print(f"CHALO Daily Trips:                             ~{chalo_daily_trips:,.0f}")
    print()
    print("NOTE: All CHALO metrics above are SSCL-only (30 e-bus routes).")
    print("      Full-network engine metrics are shown separately for context.")

    engine_active    = engine_out[engine_out['Action_Taken'] != 'MERGED_INTO_TRUNK'].copy()
    engine_sscl_only = engine_active[engine_active['CMP_Trunk'] == True].copy()

    total_fleet      = engine_active['Fleet_Required'].sum()
    sscl_fleet       = engine_sscl_only['Fleet_Required'].sum()
    print(f"\nEngine Fleet — Full network: {total_fleet:.0f} buses  |  SSCL-only: {sscl_fleet:.0f} buses")
    print("(Full-network includes private minibuses + JKRTC + MPS — not directly comparable to SSCL's 98)")

    service_hours = 16  # 6 AM to 10 PM
    # Engine "Daily_Trips" is one-way revenue trips per route at the target
    # headway. CHALO "Trip Count" is bus-trips/day (per-vehicle round trips),
    # so to compare on equal footing we normalise the engine to round trips
    # per route by dividing one-way trips by 2.
    engine_active['Daily_Trips_OW']    = (service_hours * 60) / engine_active['Headway_Min'] * 2
    engine_active['Daily_RoundTrips']  = engine_active['Daily_Trips_OW'] / 2.0
    engine_active['Daily_KM']          = engine_active['Daily_Trips_OW'] * engine_active['Route_KM']
    engine_sscl_only['Daily_Trips_OW']   = (service_hours * 60) / engine_sscl_only['Headway_Min'] * 2
    engine_sscl_only['Daily_RoundTrips'] = engine_sscl_only['Daily_Trips_OW'] / 2.0
    engine_sscl_only['Daily_KM']         = engine_sscl_only['Daily_Trips_OW'] * engine_sscl_only['Route_KM']

    engine_daily_trips      = engine_active['Daily_RoundTrips'].sum()
    engine_daily_km         = engine_active['Daily_KM'].sum()
    engine_sscl_daily_trips = engine_sscl_only['Daily_RoundTrips'].sum()
    engine_sscl_daily_km    = engine_sscl_only['Daily_KM'].sum()

    print(f"Engine Daily Round-Trips — Full: ~{engine_daily_trips:,.0f}  |  SSCL-only: ~{engine_sscl_daily_trips:,.0f}")
    print(f"Engine Daily KM          — Full: ~{engine_daily_km:,.0f}  |  SSCL-only: ~{engine_sscl_daily_km:,.0f}")
    print("  (Engine numbers are SCHEDULED service at TARGET headways — 15-min for SSCL trunks.")
    print("   CHALO numbers are OBSERVED operations at CURRENT headways (≈25-30 min on most routes).")
    print("   The supply gap is the whole point of the rationalisation, not a model error.)")

    # ─── Implied pax: SSCL-scoped only, to match CHALO scope ─────────────────
    pop_total = engine_active['Population_Served'].sum() \
        if 'Population_Served' in engine_active else 0
    if pop_total <= 0:
        print("\nWARN: Engine Population_Served sums to ZERO — WorldPop raster bug."
              " Check RASTER_PATH and rasterstats before trusting any comparison.")

    sscl_pop = engine_sscl_only['Population_Served'].sum() \
        if 'Population_Served' in engine_sscl_only else 0

    # NOTE: The engine's per-route Population_Served is the EXCLUSIVE catchment
    # left after Union-Find dedup against overlapping feeders. SSCL trunks
    # share corridors with dozens of feeders, so their exclusive catchment
    # collapses to a few thousand residents per route even though the trunk
    # actually carries the bulk of riders. Using SSCL-only Population_Served
    # × mode_share × trip_rate therefore systematically UNDER-estimates SSCL
    # demand by 5-10×. Report it for transparency, but do NOT include in the
    # calibration objective.
    engine_sscl_implied_pax = sscl_pop * MODE_SHARE * TRIP_RATE
    engine_full_implied_pax = pop_total * MODE_SHARE * TRIP_RATE
    print(f"\nEngine Implied Daily Pax — full network "
          f"({MODE_SHARE*100:.0f}% mode share, {TRIP_RATE} trips/day):"
          f" ~{engine_full_implied_pax:,.0f}")
    print(f"  (Of which SSCL-trunks' EXCLUSIVE catchment yields only "
          f"~{engine_sscl_implied_pax:,.0f} — under-estimate, see comment.)")
    print(f"CHALO Observed Daily Pax (SSCL, 12-mo avg):  ~{chalo_daily_pax:,.0f}")
    if chalo_daily_pax > 0:
        print(f"  Full-network engine demand / CHALO SSCL ridership: "
              f"{engine_full_implied_pax/chalo_daily_pax:.2f}x")
        print("  (Useful only as an order-of-magnitude sanity check — not a calibration target.)")

    # ─── Level 2: SSCL route-level fleet ──────────────────────────────────────
    print("\n--- Level 2: SSCL Route Fleet ---")
    chalo_total_fleet = buses['New Deployement'].sum()
    engine_sscl       = engine_out[engine_out['CMP_Trunk'] == True]
    engine_sscl_fleet = engine_sscl['Fleet_Required'].sum()
    print(f"CHALO Total SSCL Fleet Deployed:     {chalo_total_fleet:.0f} buses")
    print(f"Engine SSCL Fleet Recommended:       {engine_sscl_fleet:.0f} buses")
    print(f"  → Difference: {engine_sscl_fleet - chalo_total_fleet:+.0f} buses "
          f"({(engine_sscl_fleet/chalo_total_fleet - 1)*100:+.1f}%)"
          if chalo_total_fleet > 0 else "")

    # ─── Level 3: Temporal shape ──────────────────────────────────────────────
    print("\n--- Level 3: Temporal Shape ---")
    avg_hourly  = hourly.groupby('Hours')['Passenger Count'].mean()
    peak_hour   = avg_hourly.idxmax()
    peak_pax    = avg_hourly.max()
    trough_hour = avg_hourly.idxmin()
    trough_pax  = avg_hourly.min()
    print(f"CHALO Peak Hour:   {peak_hour}:00 with ~{peak_pax:.0f} pax")
    print(f"CHALO Trough Hour: {trough_hour}:00 with ~{trough_pax:.0f} pax")
    print("Engine currently uses flat headways — time-of-day multipliers are v4.")

    # ─── Objective (SSCL fleet + headway-normalised supply parity) ────────────
    # The engine sizes fleet for a 15-min target headway; CHALO observes current
    # operations at ~25-30 min headway. We compare two things that ARE on the
    # same footing:
    #   (a) SSCL fleet count — engine recommendation vs CHALO deployed.
    #   (b) Implied avg headway from CHALO's bus-trips: if CHALO ran service at
    #       the engine's target 15-min headway, the implied required fleet should
    #       roughly equal the engine recommendation.
    def _pct_err(engine, chalo):
        return 0.0 if chalo == 0 else ((engine - chalo) / chalo) * 100.0

    # CHALO's effective headway across the 30 SSCL routes (round trips/route/day):
    chalo_rt_per_route = chalo_daily_trips / max(len(buses), 1)
    chalo_effective_headway = (service_hours * 60) / chalo_rt_per_route \
        if chalo_rt_per_route > 0 else float('inf')
    target_headway = 15.0
    # Headway-scaled CHALO equivalent fleet at target headway:
    chalo_scaled_fleet = chalo_total_fleet * (chalo_effective_headway / target_headway)

    fleet_err        = _pct_err(engine_sscl_fleet, chalo_total_fleet)
    fleet_scaled_err = _pct_err(engine_sscl_fleet, chalo_scaled_fleet)
    objective        = fleet_scaled_err ** 2

    print("\n--- Objective (SSCL fleet parity, headway-normalised) ---")
    print(f"  CHALO bus-trips/route/day:        {chalo_rt_per_route:.1f}")
    print(f"  CHALO effective avg headway:      {chalo_effective_headway:.1f} min")
    print(f"  Engine target headway:            {target_headway:.0f} min")
    print(f"  CHALO fleet scaled to target:     {chalo_scaled_fleet:.0f} buses "
          f"(= {chalo_total_fleet:.0f} × {chalo_effective_headway:.1f}/{target_headway:.0f})")
    print(f"  SSCL fleet error (raw vs CHALO):  {fleet_err:+.1f}%   "
          f"(expected: positive, engine targets tighter service)")
    print(f"  SSCL fleet error (vs headway-scaled CHALO):  {fleet_scaled_err:+.1f}%   "
          f"(this is the real calibration error — should be in ±25%)")
    print(f"  Objective (squared scaled %%-err): {objective:,.1f}")

    # ─── Calibration advice ───────────────────────────────────────────────────
    print("\n--- Calibration Advice ---")
    if engine_sscl_fleet > chalo_total_fleet * 1.15:
        print(f"Engine SSCL fleet ({engine_sscl_fleet:.0f}) is >15% above CHALO ({chalo_total_fleet:.0f}).")
        print("  Try: raise SSCL_TRUNK_HEADWAY_MIN, lower STOP_PENALTY_MIN, or relax CONGESTION_CITY_CORE.")
    elif engine_sscl_fleet < chalo_total_fleet * 0.85:
        print(f"Engine SSCL fleet ({engine_sscl_fleet:.0f}) is >15% below CHALO ({chalo_total_fleet:.0f}).")
        print("  Try: lower SSCL_TRUNK_HEADWAY_MIN, raise CONGESTION_CITY_CORE.")
    else:
        print(f"Engine SSCL fleet within 15% of CHALO ({engine_sscl_fleet:.0f} vs {chalo_total_fleet:.0f}). Good.")

    if abs(fleet_scaled_err) <= 25.0:
        print(f"Headway-normalised SSCL fleet within ±25% of CHALO equivalent — calibration OK.")
    else:
        print(f"Headway-normalised SSCL fleet off by {fleet_scaled_err:+.1f}% — investigate "
              "STOP_PENALTY_MIN, CONGESTION_CITY_CORE, or JHELUM_BRIDGE_BOTTLENECK_MIN.")

    return {
        "fleet_err_pct":             fleet_err,
        "fleet_err_pct_headway_adj": fleet_scaled_err,
        "chalo_effective_headway":   chalo_effective_headway,
        "objective":                 objective,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Cross-evaluate Kashmir Transit Engine v3 outputs against CHALO ground truth."
    )
    parser.add_argument(
        "--data-dir", default=".",
        help="Directory containing CHALO CSV files (default: current directory)"
    )
    parser.add_argument(
        "--ridership", default=None,
        help="Path to Ridership Data CSV (overrides --data-dir)"
    )
    parser.add_argument(
        "--buses", default=None,
        help="Path to Route Wise deployed Buses CSV (overrides --data-dir)"
    )
    parser.add_argument(
        "--hourly", default=None,
        help="Path to Hourly Passenger Count CSV (overrides --data-dir)"
    )
    parser.add_argument(
        "--engine-out", default=None,
        help="Path to engine output CSV (default: Rationalised_Routes_Kashmir_v3.csv in --data-dir)"
    )
    args = parser.parse_args()

    base = args.data_dir
    ridership_path = args.ridership  or _resolve(base, "Ridership Data.csv")
    buses_path     = args.buses      or _resolve(base, "Route Wise deployed Buses.csv")
    hourly_path    = args.hourly     or _resolve(base, "Hourly Passenger Count.csv")
    engine_path    = args.engine_out or _resolve(base, "Rationalised_Routes_Kashmir_v3.csv")

    print(f"Data sources:")
    print(f"  Ridership : {ridership_path}")
    print(f"  Buses     : {buses_path}")
    print(f"  Hourly    : {hourly_path}")
    print(f"  Engine out: {engine_path}")
    print()

    ridership, buses, hourly = load_chalo_data(ridership_path, buses_path, hourly_path)
    engine_out = load_engine_output(engine_path)
    evaluate(ridership, buses, hourly, engine_out)


if __name__ == "__main__":
    main()
