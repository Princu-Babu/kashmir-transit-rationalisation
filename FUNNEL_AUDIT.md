# Honest funnel audit — from raw Excel rows to 104 active routes / 670 buses

Purpose: the user is (rightly) skeptical that "all those permits" reduce to only
~104 routes and ~670 buses. This traces EVERY route through every step so we can
see exactly where each one went, and judge whether the consolidation is honest or
whether we over-merged legitimate distinct routes. Resumable — continue from the
first ☐ step.

## Steps
| # | Step | Status | Finding |
|---|---|---|---|
| A | Raw source counts: permits by office, expiry status, usable route data | ✅ | see A |
| B | DISTINCT corridors in the raw source (dedup by O–D name, pre-geocode) — the true route count | ✅ | see B |
| C | Geocoding funnel: usable → geocoded → failed (with reasons) | ✅ | see C |
| D | Engine funnel: bbox drops + merge breakdown | ✅ | see D |
| E | Fleet derivation + sanity | ✅ | see E |
| F | Honest verdict | ✅ | see F |

## Findings (fill as we go)

### B — DISTINCT corridors in the raw source
- **Minibus: 453 usable permits → only 74 distinct undirected corridors** (78
  directed). Heavily duplicated: HAZRATBAL↔LD = 42 permits, BUDGAM↔PARIMPORA = 25,
  PANTHACHOWK↔PARIMPORA = 25, LD↔SOURA = 23 … So consolidating the minibus permits
  hard is HONEST — 453 permits really are ~74 routes.
- **JKRTC: 168 geocodable rows → 122 distinct (from,to) directed pairs** (mostly
  "Srinagar → distinct town"). This is the largest candidate block and the place to
  scrutinise for over-merging (step D).
- **SSCL: 30.**
- Naive distinct-corridor ceiling ≈ 74 + 122 + 30 = **~226 directed corridors**
  BEFORE geocoding losses, undirected dedup, and overlap-merging. Final active = 104.
  So the question for steps C–D: is 226→104 honest (real overlap/geocode losses) or
  did overlap-clustering collapse genuinely-different destinations?

### A — Raw source counts (SRINAGAR RTO minibus permits)
- 1,259 permits total. **806 have NO route data** (Route Covered="NA", blank From/To);
  only **453 carry a usable From+To**.
- **883 of 1,259 are EXPIRED** (Permit Upto < 2026-06-20; dates are mostly 2017–2021).
  Only **376 valid**. Of the 453 *usable* permits, only **96 are valid** (357 expired).
- We deliberately used ALL usable permits (expired + valid) as candidate corridors —
  so the plan is built on the *historical* permitted network, not just live permits.
  (If restricted to valid+usable, the minibus base would be ~96 permits.)
- KEY: "permits" ≠ "routes". 453 usable permits are NOT 453 distinct routes — many
  are duplicate permits for the same corridor (next step quantifies this).

### C — Geocoding funnel (THE bottleneck)
- Minibus: 453 usable permits → **335 geocoded** (118 lost an endpoint) → **51
  distinct geocoded corridors** (from 74 raw — 23 corridors lost to geocoding).
- JKRTC: 168 candidates → **66 geocoded** (102 lost) → **33 distinct geocoded
  corridors** (from 122 raw — **89 corridors lost to geocoding**).
- Combined distinct geocoded corridors: **84** (+30 SSCL = 114).
- Reject files: geocode_failures.csv (40 minibus names) + geocode_failures_other.csv
  (85 JKRTC names); other_routes_dropped.csv = 103 JKRTC rows with **74 distinct
  failed destinations** — and these are REAL Kashmir villages/towns (Aboora, Arizal,
  Beeru, Chewdara, Gaguldara, Isganderpora, Karhama, Khag, Loolpora, Baderkote,
  Dardpora …), not junk. They fail because OSM/Nominatim has poor coverage of tiny
  valley villages and the "X- Srinagar" compound names.

### D — Engine funnel (consolidation is NOT the culprit)
- 401 geocoded rows + 30 SSCL − 11 bbox = 420 → **104 active, 316 merged**.
- But 84 distinct geocoded corridors + 30 SSCL = 114 → 104 active. So only ~10
  corridors merged by overlap/bbox; the 316 "merged" are overwhelmingly DUPLICATE
  PERMITS of the same 84 corridors (e.g. 42 HAZRATBAL↔LD permits → 1). That is
  honest de-duplication, not loss of distinct routes.

### E — Fleet sanity
- Fleet formula reproduces 100% of rows; consolidated busy corridor (Batamaloo→
  Pantha Chowk) load 0.12 → not under-served. 670 is correct FOR a 104-route
  network. It is low only because the network itself is small (step C), not because
  fleet was mis-sized.

### F — HONEST VERDICT
- **104 routes / 670 buses is arithmetically correct, but it UNDER-REPRESENTS the
  real network.** The consolidation is honest (453 minibus permits genuinely = 74
  corridors). The shrinkage is at GEOCODING: of ~226 distinct source corridors only
  ~84 geocode, so **~110+ distinct corridors — mostly real rural JKRTC destinations
  — are dropped because the geocoder can't place small valley villages.**
- The fleet "bouncing" (1009→670) was two different things: (a) correctly removing
  duplicate over-provisioning [good, real], and (b) the base network being small
  due to geocoding recall [the real limitation].
- **To grow the plan to its true size honestly: improve geocoding recall** — add a
  curated gazetteer for the ~110 failed village names (coordinates from the JKRTC
  depot lists / Survey of India / manual), which would lift the network toward
  ~150–200 corridors and the fleet toward ~900–1,000. This is the single highest-
  value next step, and it ADDS routes legitimately (no methodology change).
- NOT recommended: reverting the de-duplication (the 453→74 minibus collapse is
  real) or padding the fleet (the headway-based sizing is correct).

## Change journal
- 2026-06-20: Funnel audit A–F complete. Root cause of "only 104" = geocoding
  recall (122 JKRTC corridors → 33), NOT over-consolidation. Fleet 670 correct for
  the (under-sized) network. Fix = gazetteer the ~110 failed villages.
- 2026-06-20: ledger created.
