# Kashmir Valley Transit Rationalisation — Methodology Walkthrough (v3.3.9)

Plain-English, stage-by-stage account of how the plan is built **from the four
government source files to the final results**, with what was verified at each
stage and an honest "does it make sense?" verdict. Companion to `AUDIT_FIX_LOG.md`
(what was fixed) and `VERIFICATION_v3.3.8.md` + `AUDIT_2026-06-21_SOURCE_RECHECK.md` (line-by-line re-checks).

All numbers reflect the FINAL post-recovery, source-re-audited network (172 active
routes / 1,005 buses), re-verified against the live v3.3.9 outputs on 2026-06-21.

---

## The shape of it
Four government files feed one engine. Two are **plan inputs** (the permit dump +
the JKRTC timetable become candidate routes), one is the **calibration anchor**
(SSCL ridership), and one is **corroboration only** (the Smart City e-bus list).
The engine geocodes them, routes them on real roads, scores demand from open data,
then sizes frequency and fleet. Final: **615 routes → 172 active → 1,005 buses** (after village-geocode recovery + source re-audit).

---

## STAGE 0 — Source files
| File | What it is | What we take | Verdict |
|---|---|---|---|
| Mini Buses…xlsx | 15,231 permits, 22 J&K RTOs | the 1,259 SRINAGAR-RTO rows | ✅ used correctly |
| SSCL Data Updated.xlsx | CHALO e-bus ridership + 30-route deployment | calibration constants + backbone | ✅ exact to source |
| Time_Table…DSU-Kashmir.xlsx | JKRTC timetable | 208 routes (Regular/City/MPS + airport) | ✅ counts reconcile |
| SMART CITY BUS LIST.xlsx | Srinagar Smart City e-bus list | nothing — corroboration only | ✅ not ingested |

**Key source fact:** of the 1,259 Srinagar-RTO permits, only **453 carry a usable
origin+destination**; the other **806 have `Route Covered = "NA"` and blank From/To**
— including **544 of 548 big-bus (HPV) permits**. The thin big-bus base in the plan
is a **government data-availability fact** (the permit register has no routes for
them), not an engine fault. (This corrects the original audit's claim that all
1,259 had endpoints.)

**Verdict: ✅ sound, one caveat** — ~64% of Srinagar permits carry no route and
cannot be planned from this file; ask the RTO for the HPV permit routes.

## STAGE 1 — Geocoding (place names → coordinates) — *the most-fixed stage*
**Was broken:** the old `"{place}, Srinagar, Kashmir"` query fell back to the
Srinagar centroid for any town it couldn't resolve → **118 names collapsed onto one
point**, 290 routes became zero-length and were silently deleted (a Srinagar-city
plan masquerading as a valley plan).

**Now:** district-aware queries + valley viewbox + **hard Srinagar-centroid
rejection** + spelling aliases + **gazetteer pins** for mis-placed hubs (e.g.
Parimpora, which OSM put 4.6 km off); `arcgis` made optional with a Nominatim/OSM
backend so the re-geocode can run anywhere.

**Verified:** `existing-routes.csv` = **614 routes, 0 centroid-collapse, 0
zero-length**; unresolved names logged to `geocode_failures*.csv` (nothing dropped
silently). Spot-checked towns within ~1 km of truth.

**Verdict: ✅ this is the fix that makes the whole plan legitimate.** Residue: only 2 void permit markers (SCRAPED/SCRAPPED) excluded; the ~110 rural
villages OSM couldn't place were recovered via kashmir_gazetteer.csv (GAZETTEER_RECOVERY.md).

## STAGE 2 — Ingestion + SSCL backbone injection
614 geocoded routes − some outside the study box + **30 hardcoded SSCL/CHALO trunks**
= **615 routes**. SSCL fleet (98 buses) matches the SSCL sheet's "New Deployment"
column route-by-route. **Verdict: ✅** — the backbone is a published government
commitment, correctly treated as a fixed input.

## STAGE 3 — Real road geometry (OSRM) + study-area clip
Each route routed on real OSM roads via OSRM; +8-min Jhelum-bridge penalty, 2.2×
downtown congestion; clipped to the valley; classified Urban/Peri/Regional by
length. Fixed a bug that silently discarded via-waypoints (now routed via their waypoints).

**Verified:** lengths physically sane — median 19.7 km, longest Srinagar→Qazigund
71 km; **implied round-trip speeds 15–40 km/h** (median 16 — correct for congested
Srinagar). No 1.5 km "trunk" artifacts. **Verdict: ✅.**

## STAGE 4 — Demand inputs from open data
400 m walksheds + WorldPop population raster + OSM POIs (hospitals/schools/shrines
/markets) as attractors. No proprietary GPS/AFC needed. **Verdict: ✅ mostly** —
standard open-data proxy; caveats: POI weighting is worship-heavy (sensitivity
check advised), walksheds are straight-line not river-aware (disclosed).

## STAGE 5 — Consolidation, clustering, priority bands — *over-fleeting fixed*
Overlapping corridors merged to trunks; rest become feeders; a Composite Demand
Index (population + POIs + road class) + Jenks breaks set HP/MP/LP bands.

**Fixed:** ~380 duplicate permits were each getting their own fleet (one corridor
drew **108 buses**) → added duplicate-permit consolidation **by corridor across both
trunks and feeders** (~291 redundant permits collapsed to one service per corridor;
a real SSCL backbone route is never merged away). This also caught duplicate
*trunks* the first pass missed (e.g. 6 identical Batamaloo→Pantha Chowk permit-
trunks, ~48 buses → one 7-bus service at load 0.12). Fixed population apportionment
so the active plan sums to the network total.

**Verdict: ✅ mechanics; ⚠ one design choice** — after the overrides (SSCL HP-lock,
bonuses, social floors), **65/172 routes (~38%) are "High Priority,"** so
the band loses discriminating power. Not a bug; rebalance thresholds with the RTO
if bands must drive phasing.

## STAGE 6 — Frequency + fleet + bus mix — *the engineering core*
Headways 15 (SSCL) / 20 (trunks) / 35 (feeders) with a hard 35-min ceiling.
Fleet = `⌈cycle ÷ headway⌉ × 1.15`, floored 2 urban / 1 regional. Trunks 50/50
big/medium, feeders 100% medium.

**Verified independently:** fleet formula **reproduces 100%** of routes;
HPV+MPV+LPV = Fleet for all 172. Totals: **1,005 buses, +68% over ~600 today, ~0.52
buses/1,000 served** — a redistribution of an over-concentrated fleet, not a build-out.

**Verdict: ✅ the most solid part** — textbook (Vuchic), reproduces exactly,
credible Year-1 ask.

## STAGE 7 — Demand & economics — *the honest weak spot*
Per-route ridership → load factor → fare revenue vs operating cost → subsidy flag.

**Fixed (F-V8):** the demand scalar was fit to the old broken geometry and
under-counted ~2×; re-anchored so SSCL modelled ridership = **31,636/day vs CHALO
31,869 (0.99×)**.

**Verdict: ⚠ numbers now honest, and they tell a hard truth** — ~**3.9% farebox
cost-recovery**; most routes carry less than capacity. **Normal for a public-service
network, not a flaw — but must be framed on access/equity/women's-safety/induced
demand, never on farebox.** This is where presentation, not maths, decides the
outcome.

## STAGE 8 — Coverage — *the metric corrected hardest*
**Fixed (F-V9):** the old "coverage %" divided served population by the Srinagar
urban-area figure (1.66 M), but the study area holds **5.1 M people (WorldPop)** —
so "95.7%" was inflated ~3×. **Honest figure: 1,930,287 residents within 400 m =
37.8% of the 5.1 M study-area population** (after recovering the rural JKRTC routes).

**Verdict: ✅ 38% is defensible** (≈ the full Srinagar urban core + district reach;
the rest of the valley is rural, beyond walking range). **Do NOT reinstate 95.7%** —
it would not survive a census/WorldPop cross-check.

## STAGE 9 — QC + exports
8 arithmetic QC checks + new plausibility checks (geocode-collision, duplicate-
corridor, load-sanity, route-code uniqueness); CSV/workbooks/maps/decks/dashboard;
per-route disposition file accounting for every input.

**Verified:** QC 8/8 pass, all 172 active route codes unique, **0 UNMATCHED
anywhere**, every one of 615 inputs accounted for. **Verdict: ✅.**

---

## BOTTOM LINE — does it make sense from those Excel sheets?
**Yes — the chain is sound and traceable, with three honest framing points (not bugs):**

- ✅ **Solid:** source fidelity, geocoding (now correct), road geometry, fleet
  sizing (100% reproducible), SSCL calibration (0.99× CHALO), QC + audit trail.
  The scrutinised core — **1,005 buses, +68%, 15–35 min frequency** — holds up.
- ⚠ **Frame, don't fix:** (1) economics are weak by design (3.9% recovery) → sell
  on access/equity, never farebox; (2) coverage is 31% of the study area → the
  honest number, don't oversell; (3) half the routes are "High Priority" → rebalance
  bands with the RTO if needed.
- ℹ️ **Source-data limits to disclose:** 806/1,259 permits (incl. most big-bus
  permits) carry no route in the government file; ~21 minor localities still need
  manual coding — both fully logged.
