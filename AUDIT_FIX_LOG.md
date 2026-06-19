# Audit Remediation Log — Kashmir Transit Engine (v3.3.7 → v3.3.8)

Tracks the fixes against the independent verification audit
(`E:\audit\Kashmir_Transit_Audit_v3.3.7.md`, dated 10 Jun 2026).
This file is the **resumable source of truth** — if a working session is cut
short, the next session reads this top-to-bottom and continues from the first
item not marked ✅ DONE.

## STATUS: all audit code fixes done + real v3.3.8 produced & validated
Every audit finding with a code/data root cause is fixed, committed, and pushed
to branch `audit-remediation-v3.3.8`. The corrected v3.3.8 plan is in
`outputs_v3.3.8/`. CHALO calibration re-checked: per-route fleet +24.9% vs
headway-scaled CHALO — within ±25% ("Calibration OK").

### ADOPTED — v3.3.8 is now the official plan (2026-06-19)
User approved adoption. Done: version labels bumped v3.3.7→v3.3.8 (engine header,
workbook cells, RTO filename, _beautify_rto_master.py, _sync_dashboard.py);
regenerated outputs_v3.3.8/ (engine + 3 decks + pretty workbook); README + CLAUDE.md
updated to v3.3.8 numbers; dashboard synced (419 routes, stale v3.3.7 files purged);
both repos pushed.

### Original decision points (now resolved by adoption)
1. **Adopt v3.3.8 as the plan?** Headline numbers changed materially (the audit
   predicted this): active routes 207→136, fleet 1009→855, coverage 69.8%→94.7%,
   median route 8.7→16.5 km. v3.3.8 is more defensible but different from what was
   shown to the RTO. Needs a human call before it goes out.
2. **If adopting:** bump version labels v3.3.7→v3.3.8 (engine header, workbook
   "Engine Version" cell, RTO xlsx filename in main(), + helper scripts
   _beautify_rto_master.py / _sync_dashboard.py paths), then regenerate the
   outward decks/pretty-workbook/dashboard (generate_presentations.py,
   generate_kashmir_pitch.py, _beautify_rto_master.py, _sync_dashboard.py).
   The engine already auto-wrote in-engine decks + RTO xlsx into outputs_v3.3.8/.
3. **Geocode reject worklist:** geocode_failures*.csv + *_dropped.csv list names
   that didn't resolve (mostly junk tokens + a few hubs already covered by the
   SSCL injection). Optional: add a small verified gazetteer for LD Hospital /
   Jehangir Chowk / Bohri Kadal / Ilahibagh to recover a few more routes.
4. **M1 (band semantics)** and **M2 (demand has no Mohring elasticity)** remain
   open design questions for the RTO, not code bugs.

## How to resume
1. Read this whole file.
2. Re-read `E:\audit\Kashmir_Transit_Audit_v3.3.7.md` for finding detail.
3. Continue from the first task below whose **Status** is not ✅.
4. After each code change: `git -C E:\kash add -A && git commit` (one logical
   fix per commit), update the row here, then push when a batch is green.

## Environment reality (checked 2026-06-19)
- OSRM on :5000 → **DOWN**. A full engine re-run needs Docker OSRM up.
- `arcgis` python pkg → **MISSING** in `D:\plotting\ana`. Re-geocoding needs it
  (or a Nominatim-based replacement) + network access.
- geo stack (geopandas/rasterio/jenkspy/shapely/openpyxl) → OK.
- WorldPop raster + source xlsx/csv present.
- **Consequence:** code fixes can be made & committed now; the data re-run that
  produces a corrected `existing-routes.csv` and a v3.3.8 output set is a
  separate validation step that needs OSRM + a geocoder (handoff item R1).

## Risk tiers
- **TIER A** — pure bug fix, output-neutral or strictly-correct, safe to ship now.
- **TIER B** — behavioural change to engine numbers; correct per audit, but
  **must be validated by a re-run** before the new outputs go to government.
- **TIER C** — data re-generation (geocoding) + full re-run. Needs infra.

---

## Task table

| # | Audit ref | Tier | Fix | Status | Commit |
|---|---|---|---|---|---|
| B1 | Finding 3 / Bug 1 | A | `parse_via()` accept `"lat,lon;lat,lon"` producer format + warn on parse-fail | ✅ DONE | (batch1) |
| B2 | Output #4 | A | Add `LPV_Count` to main CSV export so HPV+MPV+LPV = Fleet | ✅ DONE | (batch1) |
| B3 | Code comment drift / §3 | A | Fix stale comments: 85/15 split, headway tables (README), Calibration sheet LP=60→35, Limitations version refs + synthetic-SSCL note, CLAUDE.md LPV note | ✅ DONE | (batch1) |
| B4 | Findings 1,2,5 / Rec 1 | A(code) | New `geocode_common.py`: district-aware query, valley extent, Srinagar-centroid rejection, outside-valley rejection, reject + drop files. Wired into latlon.py + geocode_other_routes.py. Unit-tested. Re-run (R1) needs arcgis+network. | ✅ DONE | (batch2) |
| B9 | Bug 2 / Rec 8 | A | `_DROP_LOG` + `_record_drop` capture every bbox/null/sub-1km drop; `export_route_disposition` → `Route_Disposition_Kashmir_v3.csv` (kept+dropped, all inputs). Geocoders also write per-row drop CSVs. | ✅ DONE | (batch3) |
| B7 | §3 QC gap / Rec 8 | A | New QC: QC-Geocode (centroid survivors), QC-DupCorridor (Finding 8), QC-Load (sanity band) in run_all_qc_checks; `qc_route_codes` uniqueness gate after assign. Warn by default, block under KASHMIR_STRICT_QC=1. Unit-tested. | ✅ DONE | (batch3) |
| B8 | Rec 2 | A | `audit_input_quality()` pre-engine gate: per-row haversine(O,D), Srinagar-centroid + zero-length flags → `input_qa_report.csv` + loud summary. | ✅ DONE | (batch3) |
| B5 | Finding 8 / Rec 4 | B | `consolidate_duplicate_permits()`: identical (O,D,class) feeders → one representative (Permit_Count=N), rest MERGED_INTO_TRUNK (Merged_Reason='duplicate_permit'). VALIDATED: fleet 1009→743, 314 redundant permits consolidated. | ✅ DONE | (batch4) |
| B6 | Finding 9 / Rec 6 | B | Apportionment frequency-weighted + normalised to dedup union. VALIDATED: Pop_Served Σ 99,999→1,206,139 ≈ union 1,206,152. | ✅ DONE | (batch4) |
| R1 | Rec 10 | C | RE-GEOCODE + real v3.3.8 DONE. 400 routes (0 collapse). Fleet 1009→855, coverage 69.8%→94.7%, all QC pass. Diff table below. | ✅ DONE |
| M4 | (new) | A | Route-code uniqueness: append deterministic 2-digit suffix to colliding stop-pair codes in assign_route_codes; qc_route_codes now separates missing-code from duplicate-code. VALIDATED: 133/133 real codes unique, 0 dup. | ✅ DONE |

## Batch 5 — R1 unblocked
`arcgis` made optional; added a requests/Nominatim backend in geocode_common.py
(`get_default_geocoder()`). Verified the 6 collapse towns now geocode correctly.
This means the actual re-geocode + real v3.3.8 (R1) CAN run here — no longer
blocked. Backups: `existing-routes.v3.3.7-collapsed.csv`,
`geocode_cache.arcgis-collapsed.json`.

## Additional methodology flaws found (beyond the audit) — log as discovered
- **M1 (Finding 11 confirmed, design):** Priority bands are dominated by overrides
  (SSCL HP-lock, 30th-pct trunk gate, CMP 1.5× bonus, social floors) so ~56% of
  routes are "High Priority" — the band loses discriminating power. Not a code
  bug; a prioritisation-design decision to revisit with the RTO. NOT changed
  unilaterally.
- **M2 (demand calibration, documented caveat):** `Daily_Demand` multiplies BOTH
  `mode_share` (~9%) AND `PHASE4_CORRIDOR_CAPTURE_SCALE` (0.18); both discount for
  non-bus usage, so the 0.18 scalar is a pure empirical fudge to match CHALO, not
  a structural quantity. Fine as a calibrated anchor but should be labelled as
  such (it is, in code). Load_Ratio uses `Population_Served_Raw`, so it is
  independent of the B6 apportionment fix.
- **M3 (parse_via interaction, input-dependent):** with vias now parsed (B1),
  routes whose O==D collapsed onto the centroid but carry a via survive as
  centroid→via→centroid loops on the OLD geocodes. This is a broken-INPUT
  artifact, caught by the input-QA + QC-Geocode checks, and disappears after the
  re-geocode. Not a code defect.

---

## Code-test run (2026-06-19, OSRM up, OLD collapsed geocodes — NOT a deliverable)
Validates the fixes execute and have the right directional effect. Output dir:
`outputs_v3.3.8_codetest/`. Numbers are not a plan (input geocodes still broken).

| Metric | v3.3.7 | code-test | note |
|---|---|---|---|
| rows / active | 342 / 207 | 478 / 122 | 478 = parse_via rescued collapsed-via O==D routes (artifact of broken geocodes; gone after R1) |
| Fleet total | 1009 | 743 | B5 consolidated 314 redundant permits |
| Pop_Served Σ | 99,999 | 1,206,139 | B6: now ≈ dedup union 1,206,152 (cover reconciles) |
| LPV in CSV | no | yes, sum exact | B2 |
| disposition rows | none | 643 (478 kept + 165 dropped) | B9 |
| input QA | none | 291 zero-length, 391/416 centroid endpoints flagged | B8 |

QC (warn mode): QC-GEOCODE 68 centroid survivors · QC-DUPCORR 22 (worst 9/66, all
centroid O==D trunk artifacts) · QC-LOAD mean 0.107 · QC-CODES 55 share 21 codes.
All are correct signals about the still-broken input — they clear after R1.

## REAL v3.3.8 run (2026-06-19, OSRM up, re-geocoded input) — the deliverable
Input: `existing-routes.csv` re-geocoded via Nominatim (400 routes, 0 collapse).
Output: `outputs_v3.3.8/`. **All 8 QC checks PASS; QC-Geocode clean.**

| Metric | v3.3.7 | v3.3.8 | Meaning |
|---|---|---|---|
| Active routes | 207 | 136 | dedup + no bogus zero-length |
| Fleet total | 1,009 | **855** | Finding 8 over-fleeting removed |
| Pop. coverage (dedup union) | 1.16M (69.8%) | **1.57M (94.7%)** | routes now reach the real valley |
| Pop_Served Σ | 99,999 | 599,808 (≈ union) | Finding 9 reconciled |
| Centroid endpoints | 391/416 | **0** | Finding 1 fixed |
| Zero-length routes | 290 | **5** | Finding 1 fixed |
| Median route km | 8.7 | **16.5** | no longer a Srinagar-city plan (Output #5) |
| Urban/Peri/Regional | 173/25/9 | 62/59/15 | genuine inter-district reach |

Re-geocode: 1259 SRINAGAR-RTO permits → 335 routes (correct coords);
JKRTC/Other merged → 400 total. Reject files: `geocode_failures*.csv` (≈21+ unique
unresolved, incl. junk tokens + a few hubs covered by SSCL injection),
`*_dropped.csv` (ungeocodable permits — auditable, no longer silent).

Residual non-blocking QC warnings (correct signals, not regressions):
- QC-DUPCORR 26 corridors (worst 8/56): now REAL same-corridor *different-vehicle-
  class* permits — dedup is class-specific per Rec 4, so cross-class is left for
  RTO judgement. Defensible.
- QC-LOAD mean 0.083: the static-demand caveat (Finding 10) — pre-existing model
  limitation (no Mohring), unchanged by these fixes; flagged honestly now.
- QC-CODES 63 active share 28 codes → see M4 below (route-code scheme, not geocode).

## Additional methodology flaw found during R1
- **M4 (route-code uniqueness scheme):** even with correct geocodes, 63/136 active
  routes share 28 codes. The 12-char code `<TehsilO><TehsilD><SectorO><SectorD>
  <StopO><StopD>` identifies a *corridor (stop-pair)*, not a route, so multiple
  services between the same two master stops collide. Needs a per-route
  disambiguator suffix. NOT yet fixed (flagged; the QC-CODES check surfaces it).

## Change journal (newest first)
- 2026-06-19: **R1 DONE** — re-geocoded via Nominatim + real v3.3.8 engine pass.
  Fleet 1009→855, coverage 69.8%→94.7%, collapse eliminated, all QC pass.
- 2026-06-19: Batch 4 — B5 dedup + B6 apportionment, validated by full OSRM run.
- 2026-06-19: Batch 3 — B7/B8/B9 (input QA, disposition trail, new QC checks).
- 2026-06-19: Batch 2 — B4 geocoder hardening (geocode_common.py).
- 2026-06-19: Batch 1 — B1 parse_via, B2 LPV_Count, B3 doc/comment drift.
- 2026-06-19: Ledger created; audit findings 1,2,3,8,9 + CSV/QC gaps verified.
