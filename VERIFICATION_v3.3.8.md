# v3.3.8 Independent Re-Verification — outputs & methodology vs government source files

Fresh, detailed re-check requested 2026-06-19, AFTER the audit remediation that
produced v3.3.8. Verifies the **v3.3.8** outputs (`outputs_v3.3.8/`) and the
engine methodology against the original government-provided source files. This
file is the **resumable source of truth** — if a session is cut short, the next
one reads this and continues from the first ☐ step.

## Source files under verification (as re-supplied by the user)
| Key | Path | Shape |
|---|---|---|
| MINI | `C:\Users\Prash\Downloads\Mini Buses Routes in Srinagar (1).csv` | 15,231 rows × 22 cols (full J&K permit dump) |
| SSCL | `C:\Users\Prash\Downloads\SSCL Data Updated.xlsx` | Ridership(1004×13) · Route Wise deployed Buses(38×5) · Hourly(540×4) |
| JKRTC | `E:\kash\Time_Table_of_DSU-Kashmir_MTS___City_Buses.xlsx` | DSU-Kashmir(988×11) |
| SMART | `E:\kash\SMART CITY BUS LIST - Copy.xlsx` | INTRA CITY(108×5) · INTERCITY(32×5) |

## Verification steps
| # | Check | Status | Verdict |
|---|---|---|---|
| V1 | MINI source fidelity — re-supplied CSV vs repo copy; SRINAGAR-RTO subset count; both-endpoints-present count | ✅ DONE | PASS + audit correction (see F-V1) |
| V2 | SSCL constants — engine vs SSCL.xlsx: 12-mo ridership, women share, op ratio, hourly peak/trough, service window, 30-route 98-bus table | ✅ DONE | PASS (see F-V2) |
| V3 | MINI → existing-routes.csv derivation (v3.3.8 re-geocode): permit→route counts, geocode correctness spot-check, drop accounting | ☐ TODO | |
| V4 | JKRTC timetable → Other-routes.csv transcription fidelity (counts + sample content) | ☐ TODO | |
| V5 | SMART CITY BUS LIST — is it Jammu data, unused in Kashmir pipeline? | ☐ TODO | |
| V6 | Methodology re-check of the v3.3.8 fixes (parse_via, dedup, apportionment, geocoder) — sound? regressions? | ☐ TODO | |
| V7 | v3.3.8 output sanity — fleet sums, route-code uniqueness, coverage claim, headways, load/QC | ☐ TODO | |

## Findings (log as discovered)

### F-V1 — MINI source fidelity PASS, and a correction to the original audit ✅/⚠
- Re-supplied `Mini Buses Routes in Srinagar (1).csv` = **15,231 rows, byte-for-row
  identical to the repo xlsx** (0 registration-number differences). Source fidelity intact.
- SRINAGAR RTO subset = **1,259** rows (matches). Vehicle classes HPV 548 / MPV 517
  / LPV 181 / blank 13 (matches audit).
- **CORRECTION to original audit Finding 2:** the audit claimed "all 1,259 have both
  From and To filled" and that geocoding lost 544/548 HPV permits. **FALSE.** In the
  actual source, only **453 of 1,259 have both From+To**; the other **806 have
  From='', To='', Via='NA', Route Covered='NA' — 0 recoverable.** Of the 548 HPV
  permits, **544 have no route data at all** (Route Covered='NA'). So the HPV permit
  base is absent due to a **source-data limitation (the RTO's HPV register records no
  routes), not a geocoding bug or engine defect.**
- Our v3.3.8 pipeline handles this correctly: it geocoded 335 of the 453 usable
  permits and logged the rest in `existing_routes_dropped.csv` (no silent loss).
  The "~814 lost permits" framing was overstated; the real geocode-miss count among
  usable permits is ~118 (logged in geocode_failures.csv), the other ~806 have no
  route endpoints to begin with.

### F-V2 — SSCL constants FAITHFUL to source ✅ (one minor source-data note)
Recomputed from the re-supplied `SSCL Data Updated.xlsx` and matched to the engine:
- 12-month Total ridership **11,632,326** = engine constant (exact, to the passenger).
- Women share **64.52%** ≈ engine 64.5%. Operated/Scheduled KM **0.8446** ≈ 0.845.
- Hourly **peak 4,346 pax/hr @ 09:00** (exact), 21:00 = 521 (engine trough). Service
  window 06–22.
- Route Wise sheet = 30 routes + TOTAL row. Engine per-route **`fleet` = sheet
  "New Deployement" for all 30, total 98 = 98** (exact).
- Minor note: engine 9m/12m split = **73/25**; the sheet's raw 9m/12m columns sum
  to only **90 (67/23)** because the SOURCE sheet leaves 8 buses unsplit on 5 rows
  (e.g. row 7: 9m=0,12m=2 but New Deployement=4). The engine reconciled the
  unsplit buses into the split. Source quirk, not an engine error; total is exact.

## Change journal (newest first)
- 2026-06-19: V1–V2 done. V1 PASS + audit correction (806/1259 SGR permits have no
  route data, not a geocode loss). V2 PASS (SSCL faithful, 98 fleet exact).
- 2026-06-19: Ledger created; source files inventoried.
