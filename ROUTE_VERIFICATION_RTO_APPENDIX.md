# Appendix R — Independent Route-by-Route Verification & Corrections (v3.4.4)

**Kashmir Valley Transit Rationalisation Plan — verification appendix for the
Principal Secretary (Transport) / RTO, J&K.**
_Prepared 2026-06-25. Supersedes the route distances in v3.4.3 for the 48 routes
listed here; all other routes are carried forward unchanged._

---

## R.1 Purpose

Before submission, every one of the **186 active routes** in the plan was
independently checked **against the real world** — not against the model that
produced it. An analyst verified, route by route, that the corridor physically
exists, that the origin/destination/via coordinates are the actual places, that
the modelled road distance matches the real road distance (Google Maps / JKRTC
stage tables / district gazetteers / local reporting), that the travel time is
plausible, and that a known bus/SUMO service actually operates the corridor.
Every route carries a verdict and **its sources** in the verification ledger
(`ROUTE_DEEPDIVE_LEDGER.csv`); the method is documented in
`ROUTE_DEEPDIVE_METHODOLOGY.md`.

This is deliberately a *human-grade* check on top of the automated pipeline: the
engine's distance comes from the OSRM road router, which (a) cannot know that a
place name was geocoded to the wrong point, and (b) can route an unintended
detour. A screening committee will compare the plan to Google Maps and the JKRTC
timetable — so we did that first.

## R.2 Headline result

| | Routes | Meaning |
|---|---:|---|
| **PASS** | 93 | Corridor real, coordinates sound, distance within ±15 % of real road km, service plausible. Carried forward unchanged. |
| **REVIEW** | 88 | Real corridor, but ≥1 number needed checking (distance, time, or a pin). |
| **FAIL** | 5 | Geocoding error — endpoints a few hundred metres to ~3 km apart in reality, or a town pinned to the wrong point. |

No route was found to be **fabricated** — every corridor is a real, identifiable
road. The issues were concentrated in **distance modelling**, not route concept:
the *plan* is sound; specific *distances* needed correction.

## R.3 What v3.4.4 changes

The deep-dive's central finding is that the engine's `Route_KM` equals the OSRM
road distance for the input coordinates **with no inflation factor**. Where it
diverged from reality it was because of a wrong endpoint coordinate or an OSRM
detour — neither of which a blind re-run can fix. We therefore **substituted the
web-verified real road distance** (each value cited in the ledger) for the
affected routes and **recomputed Cycle Time and Fleet using the plan's exact
published formulas** (verified to reproduce every v3.4.3 route before any change).

- **48 routes corrected** — modelled distance replaced with verified real road km;
  cycle and fleet recomputed. 42 were over-modelled (shrink), 6 under-modelled
  (grow). Full list with before/after and citations: `corrections_applied_v344.csv`.
- **93 PASS routes unchanged** — byte-identical to v3.4.3.
- **SSCL e-bus trunks never touched** — their longer distances are legitimate
  designed via-loops; fleet stays the empirical CHALO figure.
- **Total fleet 1,044 → 1,004** (HPV 187 / MPV 748 / LPV 69). 186 active routes,
  10 districts, 30 SSCL trunks — all unchanged.

Every corrected route's `HPV + MPV + LPV = Fleet_Required` (checked, 0 exceptions).

## R.4 The five critical (FAIL) errors and their resolution

| Route | Issue found | Resolution in v3.4.4 |
|---|---|---|
| **Safakadal → SMHS** | 0.8–1.6 km in reality; engine stored 6.26 km | Distance set to **1.5 km**; fleet 3→2. *(HIGH)* |
| **Srinagar → Budgam** | engine 23.6 km (dest pinned ~6 km too far west) | Dest **re-geocoded to Budgam town** (34.018, 74.714); OSRM-rerouted = **15.9 km**; fleet 7→5. Map line redrawn. *(HIGH)* |
| **Rangpora → Soura** | Adjacent localities (~3 km); engine 22 km (mis-snap) | Distance set to **4 km**; fleet 5→2. *(MED)* |
| **GBS → Lal Chowk** | The two pins are ~0.3 km apart; engine 20.3 km is spurious | Origin **re-geocoded to General Bus Stand (Batamaloo)**; OSRM-rerouted = **2.93 km**; fleet 4→2. Map line redrawn. *(HIGH)* |
| **Garkote → Baramulla** | Only documented "Garkote" in the district is in Uri (~37 km), but the pin sits ~3 km from Baramulla | **Deferred** — corridor identity unresolved; numbers left unchanged pending the RTO's surveyed stop register. |

## R.5 Deferred items (45) — by reason

| Count | Reason | Action |
|---:|---|---|
| 14 | Within ±15 % tolerance after review | None — already correct |
| 19 | Distance plausible but a village/mahalla **name could not be independently verified** | Confirm against the **RTO surveyed stop register** (already on our data-ask list) |
| 12 | **SSCL e-bus trunk** — longer distance is a legitimate designed via-loop | None — by design |

Full list with per-route reasons: `corrections_deferred_v344.csv`.

## R.6 Residual caveats (disclosed)

1. **Mountain-pass cycle times** (Tangdhar/Sadhna, Uri–Baramulla gorge,
   Chowkibal): the corrected *distance* is now realistic, but the cycle time is
   derived by scaling at the corridor's average speed, which is **conservative**
   (a high pass is slower per km). Fleet on these lifelines is governed by the
   50-minute-max-wait policy and floors, so the effect on fleet is small; flagged
   for refinement when surveyed run-times are available.
2. **Map geometry**: Budgam and GBS endpoints have now been **re-geocoded and
   re-routed via OSRM**, so their map lines and numbers are both corrected. The
   remaining under-modelled mountain routes (Tangdhar, Uri, Chowkibal) carry the
   verified real distance; their drawn line still reflects the modelled pin and
   will be redrawn when surveyed terminal coordinates are supplied.
3. **One curated placeholder** (Rangpora→Soura) uses a conservative round figure;
   absolute error ≤ ~1 km on a short urban hop.

## R.7 Reproducibility / data lineage

| File | Contents |
|---|---|
| `ROUTE_DEEPDIVE_METHODOLOGY.md` | How each route was verified, sources, verdict rules |
| `ROUTE_DEEPDIVE_LEDGER.csv` | All 186 routes: real km, real time, real service, coord check, verdict, finding, **sources** |
| `ROUTE_DEEPDIVE_FINDINGS.md` | Findings classified (FAIL / over / under / minor) |
| `corrections_applied_v344.csv` | The 48 corrections: old→new km, old→new fleet, confidence, reason, sources |
| `corrections_deferred_v344.csv` | The 45 deferred items with reasons |
| `apply_corrections_v344.py` | The correction pass (self-tests the formulas, keyed by Route_Code) |
| `outputs_v3.4.4/` | The corrected plan (CSV + GeoJSON) |

**Verification basis:** every corrected distance is traceable to published
sources cited per route in the ledger. The 93 PASS routes are unchanged from the
RTO-reviewed v3.4.3 plan. — *End of Appendix R.*
