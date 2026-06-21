# Source-to-Output Re-Audit — 21 Jun 2026 (government-screening grade)

Full re-check of the Kashmir plan against the **original government source files**,
re-supplied by the user. Scope = Kashmir only (Jammu Division timetable and the
JSCL/Jammu e-bus document were excluded as out-of-scope). Goal: weed out anything
an IAS / government screening could challenge; every step must be defensible.

Kashmir source files audited:
1. `Schedule- Time Table of JKRTC Buses in Kashmir Div.pdf` (scanned, 12 pp)
2. `Time Table of DSU-Kashmir MTS & City Buses.xlsx`
3. `SMART CITY BUS LIST - Copy.xlsx`
4. `SSCL Data Updated.xlsx`
5. `Mini Buses Routes in Srinagar.xlsx`

---

## A. Source completeness — ✅ PASS (reconciled exactly)

The JKRTC PDF is a **scanned image** with no text layer; it was transcribed into
`Other-routes.csv`. Page-by-page inventory vs `Other-routes.csv`:

| PDF section | PDF count | Other-routes.csv |
|---|---|---|
| MPS buses (pp 1–2) | 43 | MPS Bus 43 ✅ |
| Anantnag Depot (p3) | 24 | Anantnagh Depot 24 ✅ |
| B/O Pulwama (p4) | 13 | 13 ✅ |
| B/O Kulgam (p5) | 6 | 6 ✅ |
| B/O Bandipora (p6) | 8 | 8 ✅ |
| B/O Shopian (p7) | 5 | 5 ✅ |
| Baramulla Depot (p8) | 11 | 11 ✅ |
| Kupwara Depot (p9) | 5 | 5 ✅ |
| Sopore Depot (p10) | 4 | 4 ✅ |
| MTS buses (p11) | 8 | MTS Bus 8 ✅ |
| City buses (p12) | 49 | City Bus 49 ✅ |
| **PDF subtotal** | **176** | |
| EBus (SSCL, from SSCL sheet) | 32 | EBus 32 |
| **Total** | | **208 = Other-routes.csv** ✅ |

The PDF and the DSU-Kashmir xlsx are the **same source** (xlsx = digitised PDF;
both titled "Time Table of District Services Unit Kashmir"). **No routes missed.**
The Mini-bus xlsx (15,231 permits → 1,259 Srinagar-RTO rows) and SSCL ridership
constants were re-verified byte-for-byte against the supplied files (23-check QA).

## B. Inter-state MTS routes correctly excluded — ✅ PASS

The 8 MTS routes are mostly inter-state (Srinagar→Jammu / Delhi / Poonch /
Rajouri / Kishtwar / Leh / Amritsar). These must NOT appear in a **valley** plan.
Verified: **0 active routes** touch any inter-state destination (they fall outside
the valley bbox / fail valley-extent and are logged, not silently dropped). The
one valley MTS route — **TRC→Airport — is correctly KEPT** (fleet 5).

---

## C. BUG #1 — SSCL false-trunk fuzzy matches — 🔴 FOUND → ✅ FIXED

**Symptom.** Output showed 41 "SSCL/CMP trunks", but only 30 are the real SSCL
e-bus backbone. The other **11 were conventional JKRTC permits mislabelled as SSCL
e-bus trunks**, e.g.:

| Permit route | Wrongly tagged | Reality of that SSCL id |
|---|---|---|
| Anantnag → Srinagar (59 km) | SSCL-12 | Rangreth → District Court Srinagar (11 km) |
| Srinagar → Tangmarg (41 km) | SSCL-12 | (same) |
| Haftnar → Anantnag (62 km) | SSCL-20 | Pantha Chowk → Safapora |
| Anantnag → Shopian (44 km) | SSCL-05 | LD Hospital → Pandach |
| Phalgam → Anantnag | SSCL-24 | Pantha Chowk → Palhalan |

**Root cause.** `_terminal_matches_cmp()` matched on a 0.45 character-ratio OR a
raw substring. "srinagar" (8 chars) scores 0.52 against "District Court Srinagar"
(23 chars), so **any "X to Srinagar" route matched SSCL-12**; weak collisions like
"tangmarg"↔"rangreth" also cleared 0.45.

**Impact (indefensible).** These 11 got a fake `CMP_Route_ID`, HP priority, the
15-min SSCL headway (vs the 20-min trunk headway), and **~115 inflated buses**.
An IAS reviewer comparing to the published 30-route SSCL deployment would
immediately flag "Anantnag→Srinagar" tagged as an SSCL e-bus route.

**Fix.** `_terminal_matches_cmp()` rewritten to require a strong full-string fuzzy
match (≥0.80) OR a shared *meaningful* token (≥4 chars, generic place-words —
srinagar/chowk/road/… — excluded), plus a length-sanity guard in the injection
loop (a real permit can only BE an SSCL corridor if its routed length is within
0.45–2.2× the SSCL nominal km). Unit-tested: **0/11 false positives remain, 0/5
genuine SSCL matches lost.** The 30-route backbone is untouched (self-routes
bypass the matcher). [engine `_terminal_matches_cmp`, `inject_cmp_trunk_routes`]

## D. BUG #2 — Geocoding district mis-assignment (collapse) — 🔴 FOUND → ✅ FIXED

**Symptom.** 15 villages from **six different districts** all geocoded to the
**single point (34.083, 74.797) in central Srinagar** — Garkote, Kamalkote,
Nambia, Pehilpora, Maidanan, Ijara (Baramulla); Haftnar, Vailo (Anantnag);
Harman (Shopian); Khull Ahmadabad (Kulgam); Malangam (Bandipora); etc. Plus
Pahalgam ("PHALGAM") — a major tourist town — sat 4 km from Anantnag.

**Root cause.** `_build_gazetteer.py` defaulted any name not found in
`dest_district_map.csv` to district **"Srinagar"**, then used the Srinagar centre
as the approximate coordinate. The true district is knowable from the **source
depot** in `Other-routes.csv` ("Baramulla Depot", "Anantnagh Depot", …).

**Impact.** Geographically indefensible (a Baramulla village in downtown
Srinagar); distorts route lengths, demand catchments and the corridor map for
those rural routes.

**Fix.** `_fix_gazetteer_districts.py` reassigns every district-centre
approximation to its **depot's district centre** (honest-approximation policy —
per the brief, approximate rather than drop, but to the *correct* district),
and pins six well-known towns to **real coordinates** (Pahalgam 34.0149,75.3318;
Tangdhar; Kamalkote/Uri; Kupwara ×2; D.H. Pora). Stale `geocode_cache.json`
entries (103) invalidated so the corrected gazetteer wins. Result: only the two
legitimate Srinagar city features (By-Pass, Ex-Crossing) remain on the Srinagar
point. district_centre rows are labelled `district_centre(<district>)` so QA/
disposition can disclose them as indicative, not surveyed.

---

## E. Ground-truth cross-check (PDF route lengths)

The Anantnag-depot PDF page carries government route lengths/fares. Spot-check:
Anantnag–Srinagar round-trip ≈ 121 km ⇒ ~60 km one-way vs engine OSRM 59 km ✅.
(The depot "route length" column mixes round-trip and daily-km entries and is not
a clean per-route length source, so it is used only as a loose sanity anchor.)

---

## F. Net effect on the plan (v3.3.8 → v3.3.9)

| Metric | v3.3.8 | v3.3.9 | Why |
|---|---|---|---|
| Active routes | 172 | 172 | unchanged |
| Total fleet | 1,053 | **1,005** | false SSCL trunks removed (15-min → demand-based) |
| HPV / MPV / LPV | 170/799/84 | **165/751/89** | re-banded |
| SSCL/CMP trunks | 41 | **30** | 11 false trunks removed; backbone is exactly the 30 |
| SSCL trunk fleet | 398 | **283** | honest (no false-trunk inflation) |
| Trunk / feeder | — | **32 / 140** | by Action_Taken |
| Coverage | 37.81% | **37.81%** | unchanged (geocode fix moved points within-valley) |
| Buses / 1,000 served | — | **0.52** | 1,005 / 1.930 M served (BMTC peer band) |

## Verification — ✅ 24/24 checks pass
Source fidelity, geocode-collapse (≤4 on Srinagar point — only By-Pass/Ex-Crossing),
fleet identity, headways 15/20/35, codes (0 dash / 0 unmatched / 0 dup), **CMP trunks
== exactly the 30 SSCL backbone (0 false trunks)**, all 30 backbone upgraded, 0 active
inter-state, airport kept, QC pass, coverage 37.81%, geojson/dashboard/pretty-workbook
all 172 & code-clean, stale v3.3.8 downloads purged. Engine QC 8/8.

## Known minor items (documented, not blocking)
- 1 route (R0018 Soura→Hazratbal) is Action=UPGRADED_TO_TRUNK but demand-banded MP
  (35-min) — it lies on a trunk corridor but its standalone demand is medium.
  Defensible if asked; not a fabrication or fleet inflation.
- district-centre approximations remain for ~40 small rural villages (grouped at
  their CORRECT district centre now, labelled `district_centre(<district>)`) —
  honest "approximate, don't drop" policy per the brief; disclose as indicative.

## Status — ✅ COMPLETE
- [x] Source completeness, inter-state exclusion verified
- [x] Bug #1 (SSCL false trunks) fixed + unit-tested
- [x] Bug #2 (geocode district collapse) fixed; gazetteer + cache corrected
- [x] Engine re-run (v3.3.9); 24/24 QA pass
- [x] Workbooks/decks/dashboard/geojson regenerated; dashboard numbers updated
- [ ] Refresh Desktop; push both repos
