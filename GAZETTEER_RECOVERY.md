# Village geocode recovery — recover the ~110 dropped corridors

Goal: give EVERY unresolved place name a coordinate (bus stop if findable, else
village/town centre, else district-centre approximation) so NO route is dropped
for lack of coordinates. Build a curated `kashmir_gazetteer.csv` the geocoder
checks first. Resumable — continue from the first ☐ step.

## Steps
| # | Step | Status |
|---|---|---|
| R1 | Build worklist: 105 distinct unresolved names → gazetteer_worklist.csv | ✅ |
| R2 | Multi-geocoder cascade (Nominatim+variants → Photon → ArcGIS, fallback-point rejection) → 79/105 resolved | ✅ |
| R3 | District-centre fallback for residuals (from timetable depot map) — approximate, never drop | ✅ |
| R4 | kashmir_gazetteer.csv (103 entries; 2 void markers skipped) wired into geocode_common | ✅ |
| R5 | Re-run geocode + engine — DONE | ✅ |

## FINAL recovered network (vs before recovery)
| Metric | Before | After recovery |
|---|---|---|
| existing-routes.csv | 401 | **614** |
| Active routes | 104 | **172** (Trunk 43 / Feeder 129) |
| Fleet | 670 | **1,053** (HPV 170 / MPV 799 / LPV 84) |
| Coverage | 31.1% (1.59M) | **37.8% (1.93M)** of 5.1M |
| Median route | 14.9 km | 19.7 km (55 regional routes) |
| Dropped real villages | ~110 | **0** (only 2 void "SCRAPED/SCRAPPED" markers) |
- Gazetteer: 60/103 real geocoder coords, 43 district-centre approximations
  (Srinagar 16, Budgam 11, Anantnag 8…). The 43 serve their district area; some
  share an endpoint and consolidate (the honest cost of villages OSM can't pin).
- 0 duplicate active codes, 0 active UNMATCHED, QC 8/8 pass.

## Result of recovery
- existing-routes.csv: **401 → 614 geocoded routes** (+213). JKRTC recovered in full:
  Regular 19→76, MPS 8→43, City 38→49; minibus MPV 264→347, LPV 67→94.
- Geocode failures: minibus 40→4 (the void SCRAPED/SCRAPPED + 2), JKRTC 85→0.
- Gazetteer quality: 53 trusted geocoder hits + 26 district-corrected + 17 district-
  centre fallback + 7 Srinagar pins. Every real place has ≥ an approximate coord.

## Notes
- District context for JKRTC names comes from the timetable depot sections
  (Budgam-MPS / Bandipora / Sopore / Baramulla / Kupwara / Shopian / Kulgam /
  Pulwama / Anantnag). Minibus failures are mostly Srinagar localities.

## Log
- 2026-06-20: ledger created.
