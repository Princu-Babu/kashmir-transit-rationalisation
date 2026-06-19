# Audit Remediation Log — Kashmir Transit Engine (v3.3.7 → v3.3.8)

Tracks the fixes against the independent verification audit
(`E:\audit\Kashmir_Transit_Audit_v3.3.7.md`, dated 10 Jun 2026).
This file is the **resumable source of truth** — if a working session is cut
short, the next session reads this top-to-bottom and continues from the first
item not marked ✅ DONE.

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
| R1 | Rec 10 | C | Re-geocode (needs `arcgis`) + re-run → real v3.3.8; diff vs v3.3.7. Code-test (OSRM up, OLD geocodes) PASSED — fixes run & behave correctly. Still BLOCKED on `arcgis` for the actual re-geocode. | ⏳ BLOCKED on arcgis |

## Additional methodology flaws found (beyond the audit) — log as discovered
(none yet)

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

## Change journal (newest first)
- 2026-06-19: Batch 4 — B5 dedup + B6 apportionment, validated by full OSRM run.
- 2026-06-19: Batch 3 — B7/B8/B9 (input QA, disposition trail, new QC checks).
- 2026-06-19: Batch 2 — B4 geocoder hardening (geocode_common.py).
- 2026-06-19: Batch 1 — B1 parse_via, B2 LPV_Count, B3 doc/comment drift.
- 2026-06-19: Ledger created; audit findings 1,2,3,8,9 + CSV/QC gaps verified.
