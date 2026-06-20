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
| V3 | MINI → existing-routes.csv derivation (v3.3.8 re-geocode): permit→route counts, geocode correctness spot-check, drop accounting | ✅ DONE | PASS, 1 accuracy fix (F-V3) |
| V4 | JKRTC timetable → Other-routes.csv transcription fidelity (counts + sample content) | ✅ DONE | PASS on counts; 2 minor data issues (F-V4a/b) |
| V5 | SMART CITY BUS LIST — is it Jammu data, unused in Kashmir pipeline? | ✅ DONE | audit correction (F-V5) |
| V6 | Methodology re-check of the v3.3.8 fixes (parse_via, dedup, apportionment, geocoder) — sound? regressions? | ✅ DONE | mostly sound; F-V6 apportionment residual |
| V7 | v3.3.8 output sanity — fleet sums, route-code uniqueness, coverage claim, headways, load/QC | ✅ DONE | PASS (integrity); demand-model observation |

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

### F-V3 — derivation correct; one geocode-accuracy fix on the busiest hub ⚠ (fixable)
- existing-routes.csv = 400 = 335 minibus (SGR) + 65 JKRTC/Other. Reconciles with
  453 usable SGR permits → 335 geocoded (118 endpoint misses logged).
- No collapse: the high-count shared coordinates are legitimate single-name hubs —
  Parimpora 98, generic "Srinagar" 59, Soura 58, Hazratbal 42. Sampled towns
  (Bandipora/Shopian/Pulwama/Soura/Hazratbal) geocode within ~1.5 km. ✅
- **F-V3 (FIX): "Parimpora" — the single busiest origin hub (98 routes) — geocodes
  to (34.0814, 74.7131), a bypass service road ~4.6 km SW of the actual Parimpora
  bus-stand/fruit-mandi (~34.11, 74.75, the value the SSCL synthetic routes use).**
  98 routes inherit a ~4.6 km origin error → systematic length/cycle-time bias on
  those routes. FIX: pin Parimpora (and other key hubs) in a verified gazetteer /
  NAME_ALIASES. → see remediation R-V at end.

### F-V4 — JKRTC transcription: counts faithful, two minor content issues ⚠
- xlsx "DSU-Kashmir" → Other-routes.csv: **208 rows, all categories reconcile**
  (Regular 76 / City 49 / MPS 43 / EBus 32 / MTS 8). Faithful to the xlsx.
- "Buchpora" (City Sch-1 #6, JK01Y-0843) is **what the source xlsx says** — our
  "Srinagar to Buchpora" route is correct vs the government source. (The prior
  audit's "should be Soura" was a PDF→xlsx claim; we have no PDF and the xlsx is
  authoritative, so this is a source matter, not our pipeline.)
- PDF→xlsx drift (audit Finding 4: Ratinpora/Ratnipora, AM/PM time errors) is
  **unverifiable without the scanned PDF**; our chain is faithful to the xlsx.
- **F-V4a (FIX, minor): TRC→Airport is dropped.** It sits in the MTS section
  (timetable r235) alongside genuinely out-of-scope inter-state routes
  (Srinagar→Jammu/Delhi/Leh…); geocode_other_routes.py skips the whole MTS
  category, so the in-valley airport link (8 daily departures) is lost. 0 Airport
  routes in existing-routes.csv and v3.3.8 output. Fix: special-case TRC→Airport.
- **F-V4b (FIX, minor): depot "A - B" route pairs mislabeled.** The depot sections
  (Anantnag/Pulwama/etc.) list routes as "Phalgam- Anantnagh", "Lammer- Anantnagh"
  etc.; the transcription defaulted from='Srinagar' and put the pair in 'to', so
  the cleaner yields Srinagar→Phalgam (a ~90 km route) instead of the real
  Anantnag→Pahalgam (~45 km). Affects ~a dozen local depot routes (audit Finding 5
  persists — we fixed geocoding, not the transcription layer). Inflates length/
  fleet for those routes.

### F-V5 — SMART CITY BUS LIST is Kashmir e-bus data (audit Finding 6 was wrong) ✅
- Re-supplied `SMART CITY BUS LIST - Copy.xlsx` is **Srinagar Smart City e-bus
  data**, NOT Jammu: INTRA CITY = 8 routes / 32 buses (PARIMPORA TO HARWAN 7,
  BATAMALLO TO HAZRATBAL 6, LD TO PANDACH 5, PANTHACHOWK TO NARBAL 2, …). The
  prior audit's "Jammu data (Raipur Talab/Janipur/Katra)" claim does not match
  this file.
- **Not ingested by the engine** (no read_excel/open of it anywhere). The SSCL
  backbone correctly comes from `SSCL Data Updated.xlsx` (V2). The "Smart City"
  strings in generate_kashmir_pitch.py are narrative framing, which is accurate.
- It corroborates the SSCL routes (names + counts align). It's a smaller 32-bus
  intra-city snapshot vs the fuller 98-bus deployment in SSCL Data Updated; the
  engine uses 98 (the more comprehensive/recent figure) — correct.

### F-V6 — fixes are sound; one residual on apportionment ⚠ (FIX)
Sound / no regression:
- parse_via: vias populated (257/400) and routed; bbox truncation 0 spurious (0 truncated, 11 dropped started-outside).
- Route lengths all plausible (median 16.5 km; longest Srinagar→Qazigund 71 km, Srinagar→Kulgam 66 km — real distances). **No geocode-error artifacts** like v3.3.7's 1.5 km "Bandipora–Baramulla" trunk. Shortest are legit downtown loops (Old City 1.17 km).
- Dedup: 52 corridors, 265 consolidated, largest 38 — plausible on real geocodes.
- F-V4b real-world impact small: 0 Pahalgam routes survive into the active plan.
- **F-V6 (FIX): apportionment residual of Finding 9.** B6 normalised the *all-419-row*
  Population_Served to the union (Σ=1,572,610 ≈ 1.57M, 1.00×), but **972,802 of that
  is stranded on the 283 merged/consolidated rows** (fleet-zeroed, not population-
  zeroed). So the **active 136-route plan sums to 599,808 = 0.38× the cover**
  (1,572,627). Cover-vs-detail still doesn't reconcile in the published plan
  (milder than v3.3.7's 0.06×, but present). FIX: credit a merged route's
  population to its absorbing trunk, or re-normalise Population_Served over the
  ACTIVE set after clustering. → R-V.

### F-V7 — output integrity PASS, one demand observation
- CSV 419/136 active; HPV+MPV+LPV=Fleet (0 mismatch); LPV present; headways
  15/20/35; route codes 133 real, all unique (0 dupes); QC all pass; 0 Red_Overload.
- Cross-artefact consistent: geojson 136 = impact.json 136; routes.json 419.
- OBSERVATION (not a bug): **134/136 active routes are Amber_Under** — the static
  demand model (no Mohring elasticity) + the wider geographic spread means modelled
  demand < capacity almost everywhere. Pre-existing limitation (audit Finding 10);
  relates to F-V6. The economics/load-ratio story is the weakest part of the plan
  and should be framed as a forward service-level plan, not demand-matched.

---

## OVERALL VERDICT
Source fidelity and the SSCL backbone are **faithful** (V1, V2, V5). The v3.3.8
geocode remediation **holds** — no centroid collapse, plausible route lengths, no
fake trunks (V3, V6). Two prior-audit claims were **overstated/wrong** and are
corrected here (F-V1: 806/1259 permits have no source route data, not a geocode
loss; F-V5: SMART CITY list is Kashmir e-bus data, not Jammu). Remaining real
issues are **minor-to-medium and fixable** (below). The plan is materially sound;
the weakest area is demand/load (static model).

## Remediation plan R-V — ✅ ALL DONE (re-released 2026-06-20)
| ID | Fix | Value | Status |
|---|---|---|---|
| R-V1 | F-V6: `reconcile_active_population()` rescales active Population_Served to the dedup union + zeros merged rows. VALIDATED: Σ active 1,588,967 ≈ union 1,588,964 (1.01×). Finding 9 / Output #2 fully closed. | HIGH | ✅ DONE |
| R-V2 | F-V3: `GAZETTEER` in geocode_common pins Parimpora (34.1112,74.7475) + LD/Airport/TRC. VALIDATED: all 98 Parimpora-origin routes now at the true bus-stand coord. | MED-HIGH | ✅ DONE |
| R-V3 | F-V4a: TRC→Airport kept (fixed a NaN-concat bug in the keep-filter). VALIDATED: 1 airport route now in the plan. | LOW | ✅ DONE |
| R-V4 | F-V4b: depot "A - B" pairs split in both extraction+build loops. VALIDATED: e.g. Bandipora-Soura → local Bandipora↔Soura, not Srinagar→Bandipora. | LOW-MED | ✅ DONE |

**Post-R-V headline (re-released):** 420 routes / **133 active** / **fleet 817**
(HPV 76 / MPV 627 / LPV 114) / **coverage 95.72%** (1,588,964) / median route
14.4 km / SSCL 348 / headways 15-20-35 / route codes 130/130 unique / QC 8/8 pass
/ active Population_Served reconciles to cover. Decks + pretty workbook + dashboard
all regenerated; both repos pushed.

## Change journal (newest first)
- 2026-06-19: V7 done + overall verdict + R-V remediation plan. VERIFICATION COMPLETE.
- 2026-06-19: V6 done. Fixes sound, route lengths plausible; F-V6 apportionment
  active-sum residual (active Pop_Served 0.38× cover).
- 2026-06-19: V5 done. SMART CITY is Kashmir e-bus data (audit Finding 6 corrected),
  not engine-ingested, corroborates SSCL.
- 2026-06-19: V4 done. Counts faithful; F-V4a (airport dropped via MTS skip),
  F-V4b (depot A-B pairs mislabeled Srinagar→X).
- 2026-06-19: V3 done. PASS (derivation correct, no collapse) + F-V3: Parimpora hub
  geocoded 4.6 km off (98 routes) — pin in gazetteer.
- 2026-06-19: V1–V2 done. V1 PASS + audit correction (806/1259 SGR permits have no
  route data, not a geocode loss). V2 PASS (SSCL faithful, 98 fleet exact).
- 2026-06-19: Ledger created; source files inventoried.
