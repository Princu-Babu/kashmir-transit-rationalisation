# 📑 Project Index — Kashmir Valley Transit Rationalisation

_The master map of **where everything lives**. Last updated 2026-06-27 (v3.4.4)._

Two repositories:
| Repo | What | Remote |
|---|---|---|
| **Engine** (this repo) | the model, all methodology + audit docs, the source data | `github.com/Princu-Babu/kashmir-transit-rationalisation` |
| **Dashboard** (Next.js) | the public presentation site + the served deliverables/data | `github.com/GrostesqueChip/bus-sathi-dashboard` |

---

## ▶ Start here (read in this order)
| File | What it tells you |
|---|---|
| [`README.md`](README.md) | Project overview + **"current plan at a glance"** box + full version history |
| [`CONTEXT_HANDOFF.md`](CONTEXT_HANDOFF.md) | Living state-of-the-world — read first in any new session |
| [`CLAUDE.md`](CLAUDE.md) | Operating manual: how to run the engine, per-build workflow, constants, version table |

## 📊 The plan (current = v3.4.4)
186 active routes · 1,004 buses (187 HPV / 748 MPV / 69 LPV) · 30 SSCL trunks ·
10 districts · 35.2% coverage · MoHUA-compliant (43 buses/lakh). The operational
data ships in the **dashboard repo** under `public/route-rationalization-kashmir/`
(CSV, GeoJSON, the three RTO workbooks, per-route maps, `data/*.json`) and is
regenerated locally into `outputs_v3.4.4/` (git-ignored; large).

## ✅ Verification & assurance (the v3.4.4 work)
| File | What it documents |
|---|---|
| [`ROUTE_DEEPDIVE_METHODOLOGY.md`](ROUTE_DEEPDIVE_METHODOLOGY.md) | How every route was verified against the real world (sources, verdict rules) |
| [`ROUTE_DEEPDIVE_LEDGER.csv`](ROUTE_DEEPDIVE_LEDGER.csv) | **All 186 routes**: real km, real time, real service, verdict, finding, **sources** |
| [`ROUTE_DEEPDIVE_FINDINGS.md`](ROUTE_DEEPDIVE_FINDINGS.md) | The findings classified (FAIL / over / under / minor) |
| [`ROUTE_VERIFICATION_RTO_APPENDIX.md`](ROUTE_VERIFICATION_RTO_APPENDIX.md) | **Appendix R** — the RTO-facing verification + corrections write-up |
| [`ROUTE_PLAN_ASSURANCE_v3.4.4.md`](ROUTE_PLAN_ASSURANCE_v3.4.4.md) | External benchmark (MoHUA/peers) + accuracy (MAPE) + sensitivity + blind re-verification |
| [`ROUTE_NETWORK_INTEGRITY_v3.4.4.md`](ROUTE_NETWORK_INTEGRITY_v3.4.4.md) | Network-level validity: connectivity, redundancy, coverage gaps, fleet-validity ceiling |
| [`corrections_applied_v344.csv`](corrections_applied_v344.csv) | The 49 distance corrections (old→new km/fleet, confidence, reason, sources) |
| [`corrections_deferred_v344.csv`](corrections_deferred_v344.csv) | The 44 deferred items + reasons |
| [`deepdive_parts/`](deepdive_parts/) | Per-batch verification fragments + `check_progress.py` (resumable) + `blind_sample.csv` |

## 🧭 Route-code & stops system (v4 geo-canonical)
| File | What |
|---|---|
| [`ROUTE_CODE_METHODOLOGY.md`](ROUTE_CODE_METHODOLOGY.md) | The 12-char code design + point-in-polygon district/tehsil method |
| [`route_code_system.py`](route_code_system.py) | The code/registry generator |
| [`Kashmir_Stops_Master_v4.csv`](Kashmir_Stops_Master_v4.csv) | The **143 canonical stops** (code, district, tehsil/sector, coords) |
| `kashmir_districts_osm.geojson` / `kashmir_tehsils_osm.geojson` | OSM admin boundaries (10 districts / 39 tehsils) |

## 🛠 Engine & scripts
| File | Purpose |
|---|---|
| [`transit_kashmir_v3.py`](transit_kashmir_v3.py) | The 4-phase engine (geocode → OSRM → demand → fleet) |
| [`apply_corrections_v344.py`](apply_corrections_v344.py) | Applies the audited distance corrections (self-tests the formulas) |
| [`_build_verification_appendix_xlsx.py`](_build_verification_appendix_xlsx.py) | Builds the RTO verification appendix workbook |
| [`cross_evaluate.py`](cross_evaluate.py) · [`_beautify_rto_master.py`](_beautify_rto_master.py) · [`_sync_dashboard.py`](_sync_dashboard.py) · [`generate_presentations.py`](generate_presentations.py) · [`generate_kashmir_pitch.py`](generate_kashmir_pitch.py) | CHALO calibration · pretty workbook · dashboard sync · decks |

## 📜 Earlier audit trail (history, version-stamped)
`SYSTEM_AUDIT_2026-06-22.md`, `ROUTE_LEVEL_AUDIT_2026-06-22.md`,
`AUDIT_2026-06-21_SOURCE_RECHECK.md`, `AUDIT_FIX_LOG.md`, `FUNNEL_AUDIT.md`,
`VERIFICATION_v3.3.8.md`, `GAZETTEER_RECOVERY.md`, `MASTER_VERIFICATION_PLAN.md`.

## 🖥 Dashboard repo (the presentation)
`E:\dash\bus-sathi-dashboard` — key files:
- `KASHMIR_DASHBOARD_REWORK.md` — the dashboard rework log
- `components/rationalization-kashmir/` — `KashmirPresentationDashboard`, `KashmirAssurance`
  (verification + limitations), `KashmirStopsCodes` (stops/codes browser), `KashmirSourceFiles` (downloads)
- `lib/routeRationalizationKashmir.ts`, `lib/kashmirServicePlans.ts` — the plan numbers + download manifest
- `public/route-rationalization-kashmir/` — the served deliverables (workbooks, GeoJSON, maps, `data/*.json`)
