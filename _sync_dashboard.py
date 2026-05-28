"""
_sync_dashboard.py — copies the latest engine outputs into the
bus-sathi-dashboard public folder and regenerates the JSON data files.

Preserves prior official Route_Codes via Route_ID lookup and mints
TMP-K#### placeholders for any genuinely-new routes.
"""

from __future__ import annotations

import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

ENGINE_OUT = Path("E:/kash/outputs_v3.3.6")
ENGINE_LOG = Path("E:/kash/engine_run_v3.3.6.log")

DASH_PUBLIC = Path("E:/dash/bus-sathi-dashboard/public/route-rationalization-kashmir")
DASH_DATA   = DASH_PUBLIC / "data"

COPY_FILES = [
    "Rationalised_Routes_Kashmir_v3.csv",
    "Rationalised_Routes_Kashmir_v3.geojson",
    "Passenger_Impact_Kashmir_v3.csv",
    "Rationalisation_Log_Kashmir_v3.csv",
    "Kashmir_Route_Frequency_Plan_v3.xlsx",
    "Master_Transit_Map_Kashmir_v3.html",
]
COPY_DIRS = ["route_maps_kashmir"]


def _temp_route_code(seq: int) -> str:
    return f"TMP-K{seq:04d}"


def _copy_assets():
    for fname in COPY_FILES:
        src = ENGINE_OUT / fname
        if not src.exists():
            print(f"  ! missing {src}", file=sys.stderr); continue
        shutil.copy2(src, DASH_PUBLIC / fname)
        print(f"  copied {fname}")
    if ENGINE_LOG.exists():
        shutil.copy2(ENGINE_LOG, DASH_PUBLIC / "transit_v3.log.txt")
        print("  copied engine log -> transit_v3.log.txt")
    for dname in COPY_DIRS:
        src_dir = ENGINE_OUT / dname
        dst_dir = DASH_PUBLIC / dname
        if not src_dir.is_dir():
            print(f"  ! missing dir {src_dir}", file=sys.stderr); continue
        if dst_dir.exists():
            shutil.rmtree(dst_dir)
        shutil.copytree(src_dir, dst_dir)
        n = sum(1 for _ in dst_dir.rglob("*.html"))
        print(f"  copied {dname}/ ({n} html files)")


def _read_csv_rows(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def _write_json(path: Path, rows: List[Dict[str, str]]):
    with path.open("w", encoding="utf-8") as fh:
        json.dump(rows, fh, ensure_ascii=False, separators=(",", ":"))
    print(f"  wrote {path.name} ({len(rows)} rows)")


def _load_prior_codes() -> Dict[str, str]:
    out: Dict[str, str] = {}
    try:
        res = subprocess.run(
            ["git", "show", "HEAD:public/route-rationalization-kashmir/data/routes.json"],
            cwd=str(DASH_PUBLIC.parents[1]),
            capture_output=True, text=True, encoding="utf-8", check=True,
        )
        data = json.loads(res.stdout)
        for r in data if isinstance(data, list) else []:
            rid  = str(r.get("Route_ID") or "").strip()
            code = str(r.get("Route_Code") or "").strip()
            # Skip blank, TMP- placeholders, and UNMATCHED entries from the
            # generate_route_codes.py output — those should re-mint as TMP- this run.
            if (rid and code
                    and not code.startswith("TMP-")
                    and code.upper() != "UNMATCHED"):
                out[rid] = code
    except Exception as exc:
        print(f"  ! could not load prior route codes ({exc})", file=sys.stderr)
    return out


def _add_codes(rows: List[Dict[str, str]],
               prior: Dict[str, str]) -> List[Dict[str, str]]:
    out, preserved, minted = [], 0, 0
    seq = 0
    for r in rows:
        seq += 1
        existing = (r.get("Route_Code") or "").strip()
        rid      = (r.get("Route_ID") or "").strip()
        # A literal "UNMATCHED" from generate_route_codes.py is not a real code.
        is_unmatched = existing.upper() == "UNMATCHED"
        if existing and not existing.startswith("TMP-") and not is_unmatched:
            code = existing
        elif rid in prior:
            code = prior[rid]; preserved += 1
        else:
            code = _temp_route_code(seq); minted += 1
        new = {"Route_Code": code}
        for k, v in r.items():
            if k == "Route_Code":
                continue
            new[k] = v
        out.append(new)
    print(f"  Route_Code: {preserved} preserved, {minted} fresh TMP-K codes minted")
    return out


def _build_jsons():
    prior = _load_prior_codes()
    routes_rows = _add_codes(_read_csv_rows(ENGINE_OUT / "Rationalised_Routes_Kashmir_v3.csv"), prior)
    code_by_id = {r["Route_ID"]: r["Route_Code"] for r in routes_rows if r.get("Route_ID")}

    def _backfill(rows):
        out = []
        seq = 0
        for r in rows:
            seq += 1
            rid = (r.get("Route_ID") or "").strip()
            existing = (r.get("Route_Code") or "").strip()
            if existing and not existing.startswith("TMP-") and existing.upper() != "UNMATCHED":
                code = existing
            elif rid in code_by_id:
                code = code_by_id[rid]
            else:
                code = _temp_route_code(seq)
            new = {"Route_Code": code}
            for k, v in r.items():
                if k == "Route_Code":
                    continue
                new[k] = v
            out.append(new)
        return out

    impact_rows = _backfill(_read_csv_rows(ENGINE_OUT / "Passenger_Impact_Kashmir_v3.csv"))
    log_rows    = _backfill(_read_csv_rows(ENGINE_OUT / "Rationalisation_Log_Kashmir_v3.csv"))

    _write_json(DASH_DATA / "routes.json", routes_rows)
    _write_json(DASH_DATA / "impact.json", impact_rows)
    _write_json(DASH_DATA / "log.json",    log_rows)

    csv_path = DASH_DATA / "Rationalised_Routes_Kashmir_v3.csv"
    if routes_rows:
        with csv_path.open("w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(routes_rows[0].keys()))
            writer.writeheader()
            writer.writerows(routes_rows)
        print(f"  wrote data/Rationalised_Routes_Kashmir_v3.csv ({len(routes_rows)} rows)")


def main():
    print(f"Sync {ENGINE_OUT.name} engine outputs -> dashboard...")
    DASH_DATA.mkdir(parents=True, exist_ok=True)
    _copy_assets()
    _build_jsons()
    print("Done.")


if __name__ == "__main__":
    main()
