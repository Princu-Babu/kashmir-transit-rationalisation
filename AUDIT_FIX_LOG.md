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
| B4 | Findings 1,2,5 / Rec 1,3,7 | A(code) | Harden geocoders: drop over-narrow ", Srinagar" context, valley viewbox, reject Srinagar-centroid snaps, gazetteer for known towns, write reject + disposition files | ☐ TODO | |
| B9 | Bug 2 / Rec 8 | A | Per-input-row disposition log (kept/merged/dropped+reason) covering all inputs | ☐ TODO | |
| B7 | §3 QC gap / Rec 8 | A | New QC checks: route-code uniqueness, geocode-collision plausibility, duplicate-corridor over-fleet, load-ratio sanity band | ☐ TODO | |
| B8 | Rec 2 | A | Pre-engine endpoint QA gate: haversine(O,D) ≥ 1 km, OSRM/haversine ratio sane, centroid-collision flag | ☐ TODO | |
| B5 | Finding 8 / Rec 4 | B | Deduplicate identical O–D–class permits → corridor + permit-count weight; fleet at corridor level (kills 108-bus corridor) | ☐ TODO | |
| B6 | Finding 9 / Rec 6 | B | Apportionment shares sum to union population (not divide-by-competitor-count) | ☐ TODO | |
| R1 | Rec 10 | C | Re-geocode + re-run engine → v3.3.8; diff vs v3.3.7 route-by-route | ☐ BLOCKED (needs OSRM+geocoder) |

## Additional methodology flaws found (beyond the audit) — log as discovered
(none yet)

---

## Change journal (newest first)
- 2026-06-19: Ledger created; audit findings 1,2,3,8,9 + CSV/QC gaps verified against current source.
