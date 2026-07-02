#!/usr/bin/env python
"""
Export slim per-route JSON for the dashboard route drawer + chatbot:

  data/evidence.json      — route_id -> {obs, drv, runs}  (from bus-sathi-trace
                            route_evidence.csv — fragment road-coverage)
  data/verification.json  — Route_Code -> {verdict, finding, service, sources}
                            (from ROUTE_DEEPDIVE_LEDGER.csv — the AI real-world
                            verification, v3.4.4)

Run:  & "D:\\plotting\\ana\\python.exe" _export_route_json.py
"""
import sys, json, os
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import pandas as pd

DASH_DATA = r"E:\dash\bus-sathi-dashboard\public\route-rationalization-kashmir\data"
TRACE = r"E:\bus-sathi-trace\data\route_evidence.csv"
LEDGER = "ROUTE_DEEPDIVE_LEDGER.csv"

ev = pd.read_csv(TRACE)
evidence = {r.route_id: {"obs": round(float(r.obs_frac), 2), "drv": int(r.n_drivers),
                         "runs": int(r.n_runs), "km": round(float(r.obs_km), 1)}
            for r in ev.itertuples()}
with open(os.path.join(DASH_DATA, "evidence.json"), "w", encoding="utf-8") as f:
    json.dump(evidence, f, separators=(",", ":"))
print(f"evidence.json: {len(evidence)} routes")

led = pd.read_csv(LEDGER)
verification = {}
for r in led.itertuples():
    verification[r.Route_Code] = {
        "verdict": r.Verdict,
        "finding": (str(r.Finding) or "")[:400],
        "service": (str(r.Real_Service) or "")[:200],
        "sources": (str(r.Sources) or "")[:200],
    }
with open(os.path.join(DASH_DATA, "verification.json"), "w", encoding="utf-8") as f:
    json.dump(verification, f, separators=(",", ":"), ensure_ascii=False)
print(f"verification.json: {len(verification)} routes")
