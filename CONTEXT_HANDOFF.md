# CONTEXT / HANDOFF — Kashmir Valley Transit Rationalisation

Read this first in a new chat, then `CLAUDE.md` for the run mechanics. This file
is the living state-of-the-world; `CLAUDE.md` is the operating manual.

_Last updated: 2026-06-22 (v3.4.1 — once-and-for-all system audit)._

---

## 1. What this project is
A data-driven bus route-rationalisation plan for the **Kashmir Division** (10
districts), built for the Principal Secretary (Transport) / RTO, J&K. An engine
ingests government permit/timetable data, geocodes it, routes it on real roads
(OSRM), scores demand from open data (WorldPop + OSM POIs), and sizes frequency
and fleet. It must be **government-presentable and defensible line by line.**

## 2. Two repos (commit/push BOTH when the engine changes)
| Repo | Remote | Local |
|---|---|---|
| Engine | github.com/Princu-Babu/kashmir-transit-rationalisation | `E:\kash` |
| Dashboard (Next.js) | github.com/GrostesqueChip/bus-sathi-dashboard | `E:\dash\bus-sathi-dashboard` |

Current HEADs after v3.4.1: _(fill in after push — see git log)_. Both on `main`.

## 3. How to run (full detail in CLAUDE.md §0 + §2)
- Python = conda env `D:\plotting\ana` (NOT system Python). Prepend PATH first.
- Needs **OSRM in Docker on localhost:5000** (else circuity fallback — invalid).
- Needs the WorldPop raster `kashmir_worldpop.tif` (now the **full-division crop**
  from `ind_ppp_2026_100m.tif`; see §6 below). `KASHMIR_WORLDPOP` env or cwd.
- Per-build workflow: bump version → fresh `outputs_vX.Y.Z/` → run engine from
  inside it → `generate_presentations.py` + `generate_kashmir_pitch.py` →
  `_beautify_rto_master.py` → `_sync_dashboard.py` → commit+push both repos.
- `_beautify_rto_master.py` / `_sync_dashboard.py` have the version path hardcoded
  near the top — update when bumping. **GOTCHA:** an external linter has twice
  reset the engine's version-label lines back a version mid-session — after
  bumping, `grep -nE "v3\.4\.0" transit_kashmir_v3.py` and re-fix before the run.

## 4. CURRENT PLAN (v3.4.1) — the live numbers
- **186 active routes** (32 trunk / 154 feeder) from 644 engine routes
  (614 geocoded permits/JKRTC + 30 SSCL). Engine in = out (644 = 186 + 458 merged),
  **0 routes lost**.
- **1,144 buses** = 221 HPV / 839 MPV / 84 LPV (+91% over today's ~600).
- **Exactly 30 SSCL e-bus trunks** (the published CHALO backbone), all active.
- Headways only **15 / 20 / 35 min** (hard 35 ceiling).
- Coverage: **2,317,958 residents within 400 m = 35.2%** of the **6,584,762**
  Kashmir-Division population (10-district union, point-in-polygon).
- All **10 districts** now have active routes (Kupwara recovered in v3.4.1).
- Median route 22.8 km; longest Srinagar→Tangdar 121 km.
- Outputs in `outputs_v3.4.1/`. RTO hero file:
  `Kashmir_Route_Frequency_Plan_v3.4.1_RTO_Pretty.xlsx`.

## 5. Route-code system — v4 "geo-canonical" (`route_code_system.py`)
The structural rebuild. Full method: `ROUTE_CODE_METHODOLOGY.md`, summary in
CLAUDE.md §3. Codes are built FROM the engine's own geocoded endpoints (exact
route→stop linkage), with District + Tehsil(=Sector) from **point-in-polygon**
against OSM boundaries (`kashmir_districts_osm.geojson` admin_level 5;
`kashmir_tehsils_osm.geojson` admin_level 6 — both committed). Registry =
`Kashmir_Stops_Master_v4.csv`. Code = `<Do><Dd><So><Sd><No><Nd>` (e.g.
`SRGB-0102-0305`). The old hand-built `Kashmir_Stops_Sectored_V2.csv` +
`generate_route_codes.py` are RETIRED (bad coords / wrong districts).

## 6. The audit journey — WHY bugs kept recurring, and what's fixed
Every prior audit was **output-focused** (fix the symptom someone noticed). None
reconciled the **input funnel**, so each silent transform surfaced later as a
"new bug." The fixes, in order:
| Version | Fix |
|---|---|
| v3.3.8 | 118-name geocode→Srinagar-centroid collapse (was deleting ~290 routes) |
| v3.3.9 | 11 false SSCL trunks (loose fuzzy matcher) + 15-village district-geocode collapse |
| v3.4.0 | route codes rebuilt geo-canonically (old master coords bad: Airport 80 km off) |
| **v3.4.1** | **bbox was clipped (dropped ~29 routes + cropped the 5.1M denominator) → extended to the 10-district division (6.58M); reverse-direction double-counting (A→B & B→A both active) → undirected consolidation; full funnel reconciliation (0 unexplained loss) + 10-class bug crackdown** |

The v3.4.1 system audit is documented in `SYSTEM_AUDIT_2026-06-22.md` — it is the
"once and for all" pass: every input row reconciles to the output, and every
bug *class* (not just one symptom) was swept.

## 7. Open items / candidate next steps
- **Kupwara service level**: now recovered but the routes are long lifelines
  (103–121 km) at 35-min headway. Confirm the RTO wants this frequency / whether
  Gurez (admin_level shows a Gurez tehsil) needs explicit routes.
- **Disclosed approximations (not bugs):** ~40 rural villages sit on a
  correct-district-centre approximation (no surveyed coords); "Gund" name is
  shared by Budgam & Ganderbal; 1 geocode-merge (Rangpora≈Pandach). All in the
  audit docs. Sharpen when the RTO ships a surveyed stop register.
- **Stops master coordinate quality** (the supplied `Kashmir_Stops_Sectored_V2`):
  flag to RTO that its coords are unreliable (Airport 80 km off). We no longer
  depend on it.
- The raster `kashmir_worldpop.tif` and `ind_ppp_2026_100m.tif` are **untracked**
  (large binaries). A fresh clone must re-crop the raster from the India layer to
  the extended bbox (`lon[73.70,75.65] lat[33.30,34.85]`).

## 8. Key files (engine repo)
- `transit_kashmir_v3.py` — the 4-phase engine. bbox constants ~line 311;
  `study_area_population` (district-union clip); `consolidate_duplicate_permits`
  (undirected key); `assign_route_codes` (calls route_code_system).
- `route_code_system.py` — the route-code engine (v4).
- `kashmir_districts_osm.geojson` / `kashmir_tehsils_osm.geojson` — OSM admin.
- `kashmir_gazetteer.csv` — curated village coords (geocoding recovery).
- Docs: `CLAUDE.md`, `ROUTE_CODE_METHODOLOGY.md`, `SYSTEM_AUDIT_2026-06-22.md`,
  `AUDIT_2026-06-21_SOURCE_RECHECK.md`, `METHODOLOGY_WALKTHROUGH.md`,
  `AUDIT_FIX_LOG.md`, `FUNNEL_AUDIT.md`, `GAZETTEER_RECOVERY.md`.
- Desktop deliverables: `…\Desktop\Kashmir_Transit_v3.4.1_Deliverables\`.

## 9. Working agreements
- Government work → strict uniformity, verify in detail, disclose approximations,
  never hide a drop. Numbers must reconcile across CSV/GeoJSON/dashboard/workbook.
- After ANY engine change: re-run, re-verify (codes 0 dash/dup/UNMATCHED, funnel
  in=out, districts==PIP), regenerate decks/pretty/dashboard, refresh Desktop,
  push both repos.
