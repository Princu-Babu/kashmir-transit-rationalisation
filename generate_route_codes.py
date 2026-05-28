"""
generate_route_codes.py

Reads the engine's Route-Level Plan sheet, matches each route's origin and
destination against the Kashmir master stops file, and emits a 12-character
deterministic Route_Code in the form:

    <TehsilOrig><TehsilDest><SectorOrig><SectorDest><StopOrig><StopDest>

Five matching strategies cascade from strict to loose so that mild spelling
drift in the route name still resolves to the right stop row.

Usage
-----
    python generate_route_codes.py
        — uses defaults: outputs_v3.3.6/Kashmir_Route_Frequency_Plan_v3.xlsx
                         + Kashmir_Stops_Sectored_V2.csv
                         → outputs_v3.3.6/Routes_with_Codes.xlsx

    python generate_route_codes.py --routes <xlsx> --stops <csv> --out <xlsx>
        — explicit paths.

Output: the same workbook with a Route_Code column inserted right after
Route_Name (overwrites if already present), plus a console summary of how
many matched vs UNMATCHED.
"""
from __future__ import annotations

import argparse
import difflib
import re
import sys
from pathlib import Path

import pandas as pd

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


# ─── Reference data ──────────────────────────────────────────────────────────
# District mapping — kept for reference; the actual tehsil code is read from
# the stops CSV's Tehsil_Code column.
DISTRICT_MAP = {
    "SRINAGAR": "SR", "GANDERBAL": "GB", "BANDIPORA": "BP", "BARAMULLA": "BR",
    "KUPWARA":  "KW", "BUDGAM":    "BG", "PULWAMA":  "PW", "SHOPIAN":   "SP",
    "ANANTNAG": "AN", "KULGAM":    "KG",
}

NOISE_SUFFIXES = [
    "BUS STAND", "BUS STATION", "RAILWAY STATION", "CROSSING",
    "CHOWK", "CHOK", "HOSPITAL", "COLLEGE", "STOP", "STAND",
]


def _compact(s) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(s).upper())


def _strip_noise(name: str) -> str:
    n = name
    for w in NOISE_SUFFIXES:
        n = re.sub(rf"\b{w}\b", "", n)
    return re.sub(r"\s+", " ", n).strip()


def _extract_origin_dest(route_name):
    rn = str(route_name).upper().strip()
    if " ↔ " in rn:
        a, b = rn.split(" ↔ ", 1)
        return a.strip(), b.strip()
    if " TO " in rn:
        origin, rest = rn.split(" TO ", 1)
        dest = rest.split(" VIA ")[0] if " VIA " in rest else rest
        return origin.strip(), dest.strip()
    return None, None


def _get_stop_info(stop_name, stops_df: pd.DataFrame):
    """Try matching strategies from strict to loose."""
    if not stop_name:
        return None

    name = stop_name.strip()
    name_compact = _compact(name)
    name_stripped = _strip_noise(name)
    name_stripped_compact = _compact(name_stripped)

    # 1. Exact match
    m = stops_df[stops_df["Stop_Name_Clean"] == name]
    # 2. Compact exact match
    if m.empty and name_compact:
        m = stops_df[stops_df["Stop_Name_Compact"] == name_compact]
    # 3. Stripped-suffix compact match
    if m.empty and name_stripped_compact:
        m = stops_df[stops_df["Stop_Name_Compact"] == name_stripped_compact]
    # 4. Substring match
    if m.empty and name_stripped_compact:
        m = stops_df[stops_df["Stop_Name_Compact"]
                       .str.contains(name_stripped_compact, regex=False, na=False)]
    if m.empty and name_stripped_compact:
        m = stops_df[stops_df["Stop_Name_Compact"]
                       .apply(lambda s: s in name_stripped_compact and len(s) >= 4)]
    # 5. Close-match fallback (catches BATAMALOO vs BATAMALLO)
    if m.empty and name_stripped_compact:
        close = difflib.get_close_matches(
            name_stripped_compact,
            stops_df["Stop_Name_Compact"].tolist(),
            n=1, cutoff=0.85)
        if close:
            m = stops_df[stops_df["Stop_Name_Compact"] == close[0]]

    if m.empty:
        return None
    row = m.iloc[0]
    return {
        "Tehsil_Code": str(row["Tehsil_Code"]).strip()[:2].upper(),
        "Sector_ID":   f"{row['Sector_ID']:02d}",
        "Stop_No":     f"{row['Stop_No']:02d}",
    }


# ─── Pipeline ────────────────────────────────────────────────────────────────
def generate(routes_path: Path, stops_path: Path, output_path: Path) -> dict:
    if not routes_path.exists():
        raise FileNotFoundError(f"Routes workbook missing: {routes_path}")
    if not stops_path.exists():
        raise FileNotFoundError(f"Stops master missing: {stops_path}")

    routes_df = pd.read_excel(routes_path, sheet_name="Route-Level Plan")
    stops_df  = pd.read_csv(stops_path)

    stops_df["Sector_ID"] = pd.to_numeric(stops_df["Sector_ID"],
                                            errors="coerce").fillna(0).astype(int)
    stops_df["Stop_No"]   = pd.to_numeric(stops_df["Stop_No"],
                                            errors="coerce").fillna(0).astype(int)
    stops_df["Stop_Name_Clean"]   = (stops_df["Stop_Name"].astype(str)
                                                            .str.upper()
                                                            .str.strip())
    stops_df["Stop_Name_Compact"] = stops_df["Stop_Name_Clean"].apply(_compact)

    codes = []
    unmatched_pairs = []
    for _, row in routes_df.iterrows():
        origin, dest = _extract_origin_dest(row.get("Route_Name"))
        orig_info = _get_stop_info(origin, stops_df)
        dest_info = _get_stop_info(dest, stops_df)

        if orig_info and dest_info:
            code = (orig_info["Tehsil_Code"] + dest_info["Tehsil_Code"]
                    + orig_info["Sector_ID"]  + dest_info["Sector_ID"]
                    + orig_info["Stop_No"]    + dest_info["Stop_No"])
            codes.append(code)
        else:
            codes.append("UNMATCHED")
            unmatched_pairs.append((origin, dest))

    if "Route_Code" in routes_df.columns:
        routes_df["Route_Code"] = codes
    else:
        idx = routes_df.columns.get_loc("Route_Name")
        routes_df.insert(idx + 1, "Route_Code", codes)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    routes_df.to_excel(output_path, index=False)

    matched = sum(1 for c in codes if c != "UNMATCHED")
    print(f"Saved {output_path}")
    print(f"  Matched : {matched}/{len(codes)}  ({100*matched/len(codes):.1f}%)")
    print(f"  UNMATCHED: {len(codes) - matched}")
    if unmatched_pairs[:5]:
        print("  First 5 unmatched origin/dest pairs:")
        for o, d in unmatched_pairs[:5]:
            print(f"    {o!r}  ↔  {d!r}")

    return {
        "total":     len(codes),
        "matched":   matched,
        "unmatched": len(codes) - matched,
        "codes":     codes,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Generate Route_Code values for the Kashmir route plan."
    )
    parser.add_argument(
        "--routes", default="outputs_v3.3.6/Kashmir_Route_Frequency_Plan_v3.xlsx",
        help="Path to the engine's 4-sheet workbook")
    parser.add_argument(
        "--stops", default="Kashmir_Stops_Sectored_V2.csv",
        help="Path to the master stops CSV")
    parser.add_argument(
        "--out", default="outputs_v3.3.6/Routes_with_Codes.xlsx",
        help="Output workbook")
    args = parser.parse_args()
    generate(Path(args.routes), Path(args.stops), Path(args.out))


if __name__ == "__main__":
    main()
