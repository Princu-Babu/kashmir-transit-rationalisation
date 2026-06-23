# MASTER VERIFICATION PLAN — Kashmir Transit Plan, source → output, route-by-route

**Read this in a new chat together with `CONTEXT_HANDOFF.md` and `CLAUDE.md`.**
This is the fool-proof, government-grade sanity-check plan: how we verify, route by
route, that every line on the map — from the original government Excel sheets to
the final recommended bus counts — is real, drivable, and sensible. Precision
target: *"a government agency checked each route locally."*

_Last updated: 2026-06-23 (v3.4.3 — 50-min rural wait cap + route-by-route OSRM verification)._

---

## 0. Current plan snapshot (v3.4.3)
- **186 active routes**, **1,044 buses** (185 HPV / 776 MPV / 83 LPV), 30 SSCL trunks.
- Headways: city (Urban/Peri-Urban/SSCL) **15/20/35 min**; rural Regional lifelines
  **demand-responsive 35/40/45/50 min** — **hard 50-min maximum wait** (v3.4.3:
  the user capped rural waits at ~50 min; was 120).
- Coverage 2,317,958 ≈ **35.2%** of the **6,584,762** Kashmir-Division population.
- Outputs in `outputs_v3.4.3/`. Verification report:
  `outputs_v3.4.3/route_verification_report.csv`.
- Repos on `main`: engine `github.com/Princu-Babu/kashmir-transit-rationalisation`,
  dashboard `github.com/GrostesqueChip/bus-sathi-dashboard`.

---

## 1. The data chain we are verifying (source → output)
| Stage | Artefact | Verified by |
|---|---|---|
| Government source | Mini-bus permits (1,259 Srinagar-RTO rows), JKRTC DSU timetable (208), SSCL ridership (30 e-bus routes) | §2 source fidelity |
| Geocoding | `existing-routes.csv` (614 routes, O/D/via coords) + `kashmir_gazetteer.csv` | §3 coordinate layer |
| Engine | `transit_kashmir_v3.py` → `outputs_vX/Rationalised_Routes_Kashmir_v3.csv` + `.geojson` | §4 OSRM + §5 plan-realism |
| Route codes | `route_code_system.py` → `Kashmir_Stops_Master_v4.csv` | OSM point-in-polygon (district==PIP) |
| Deliverables | RTO workbooks, decks, dashboard | cross-artefact equality |

Funnel must reconcile: **644 engine routes (614 geocoded + 30 SSCL) = 186 active +
458 merged, 0 unexplained loss** (re-checked each build; see `SYSTEM_AUDIT_2026-06-22.md`).

---

## 2. Source-fidelity checks (the Excel sheets)
Already done & standing (see `AUDIT_2026-06-21_SOURCE_RECHECK.md`):
- Mini-bus xlsx 15,231 rows; 1,259 Srinagar-RTO; 806 carry no route (NA) — disclosed.
- JKRTC scanned PDF reconciles to the DSU xlsx exactly (176 timetable + 32 EBus = 208).
- SSCL constants exact to source (ridership 11.63M/yr, 30 routes, 98 buses).
- Jammu-division + JSCL files correctly EXCLUDED (Kashmir only).
**Re-run trigger:** if any source file is re-supplied, re-confirm row counts +
that only Kashmir files feed the pipeline.

---

## 3–5. Route-by-route verification — `_verify_routes.py`
Run after every build:
```
python _verify_routes.py --outdir outputs_vX.Y.Z
```
It writes `route_verification_report.csv` (one row per active route, every check +
verdict + reasons) and prints a summary. **Verdict = PASS / REVIEW / FAIL.** Three
layers per route:

### LAYER 1 — Coordinates (origin / destination / via)
- `O_in_division`, `D_in_division` — endpoint inside the 10-district union
  (point-in-polygon vs `kashmir_districts_osm.geojson`). Outside ⇒ **FAIL**.
- `O ≠ D` — not a degenerate <0.3 km route ⇒ **FAIL** if violated.
- on the Srinagar-centroid point, or on a **genuine collapse coord** (one coordinate
  shared by **≥3 distinct place names** — the historical 15-village bug) ⇒ **REVIEW**.
  (Busy hubs reused by many routes are ONE name → not flagged.)

### LAYER 2 — OSRM feasibility (is the literal route drivable & sensible?)
Uses the LOCAL OSRM (`localhost:5000`) as the ground truth for shortest drivable
distance:
- `osrm_ok` — OSRM returns a route O→D (corridor is road-connected). No ⇒ **FAIL**.
- **Impossibility test:** the engine's planned one-way length must be ≥ 0.9× the
  OSRM shortest distance. A shorter planned path is physically impossible ⇒ **FAIL**.
- `geojson_km` vs stored `Route_KM` — the saved length must match the actual planned
  geometry within 12% ⇒ **FAIL** if not (internal inconsistency).
- `detour_ratio` (planned ÷ OSRM-direct) and `circuity` (planned ÷ straight-line)
  are **reported**; a longer-than-direct path is normal (the route follows the
  permit's via-waypoints). Only circuity >4× ⇒ **REVIEW** ("verify via intended").

### LAYER 3 — Plan realism (is "X buses on this route" believable?)
- `mix_ok` — HPV+MPV+LPV = Fleet ⇒ **FAIL** if not.
- `headway_ok` — headway in the allowed tier (SSCL 15; Urban/Peri 15/20/35; rural
  35/40/45/50) ⇒ **REVIEW** if not.
- `fleet_formula_ok` — non-SSCL fleet reproduces ⌈⌈cycle/headway⌉×1.15⌉ (floor 2
  urban / 1 rural) ⇒ **REVIEW** if not.
- implied round-trip speed 8–45 km/h ⇒ **REVIEW** if not.
- `load` ≤ 1.2 (overload) and fleet ≤ 20 and > 0 ⇒ **REVIEW** / **FAIL** (zero).

### How to read the result (current: 168 PASS / 18 REVIEW / 0 FAIL)
**REVIEW is not failure** — it is "a human should glance." The 18 current REVIEWs
are all known & benign, in three classes:
1. **Disclosed district-centre approximations** (~10) — villages with no surveyed
   coords sit on their district town (Kulgam/Khull Ahmadabad, etc.). Close when
   the RTO supplies a surveyed stop register.
2. **Legitimate via-hub permits** (3) — e.g. "Rangpora → Soura via Lal Chowk"
   (circuity 7×): the filed permit really loops through the city. Correct.
3. **Known under-served busy corridors** (4) — Bandipora→Baramulla (load 1.96),
   Anantnag→Shopian (1.53): genuinely high demand the 35-min city cap can't fully
   serve; an explicit policy item (see ROUTE_LEVEL_AUDIT §B3).
**Any NEW REVIEW class, or any FAIL, is a real defect — investigate before shipping.**

---

## 6. Per-route human spot-check protocol (the "local agency" pass)
For a fully manual audit (sample or exhaustive), for each route open
`route_maps_kashmir/<id>.html` (or the master map) and confirm:
1. Origin & destination pins sit on the named town/locality (not a generic centre).
2. The drawn line follows a real road a local would recognise (NH-1A, the Srinagar
   ring, the district highway) and passes its named via-points.
3. The bus count & headway feel right for that corridor's traffic (a 121 km Tangdar
   lifeline at 50-min = 10 buses; a busy city trunk at 15-min = more).
4. Flag anything that looks wrong against `route_verification_report.csv`.
Record findings in a dated note; fix in the engine, never by hand-editing outputs.

---

## 7. Step-by-step: how to implement / re-do all of this
1. Confirm OSRM up (`localhost:5000`) and the WorldPop raster present (full-division
   crop; see CLAUDE.md §0). Prepend the conda PATH.
2. Run the engine into a fresh `outputs_vX.Y.Z/` (CLAUDE.md §2).
3. Run `_verify_routes.py --outdir outputs_vX.Y.Z` → review the report; 0 FAIL and
   only known REVIEW classes before proceeding.
4. Re-run the structural QA in the engine log (codes 0 dash/dup/UNMATCHED, funnel
   in=out, districts==PIP, headways in tier).
5. Regenerate decks / pretty workbook / dashboard; refresh Desktop; commit+push BOTH
   repos. Re-verify version labels (`grep -nE "v3\.4\." transit_kashmir_v3.py` — a
   linter has reset them mid-session before).

---

## 8. Known limitations to disclose to the RTO (not bugs)
- ~40 rural villages on a correct-DISTRICT-centre approximation (no surveyed coord).
- Demand is an open-data model (WorldPop × corridor-share × CHALO-calibrated scalar),
  static; absolute loads read low. Relative sizing is sound; exact rural frequency
  needs the RTO's per-route AFC ridership (standing P1 ask).
- Tourism/seasonality (winter pass closures, summer peaks) deliberately NOT modelled
  — the plan ships **year-round recommended** sizes; the RTO reduces at execution.
- The supplied `Kashmir_Stops_Sectored_V2.csv` had unreliable coords (Airport 80 km
  off) — RETIRED; codes now come from `route_code_system.py` + OSM polygons.

---

## 9. Data we still want from the RTO to reach full precision
P0: surveyed master stops register (lat/lon) · live operator permit registry · GPS
traces. P1: Census-2021 ward population · per-route AFC ridership · JKTDC tourist
arrivals. P2: road-operability calendar (winter closures) · stop/depot inventory ·
bridge load / road-width registry. Each closes a disclosed approximation above.
