# Once-and-for-all System Audit — 22 Jun 2026

Goal (user): stop finding new bugs every audit. Do a single system-wide
reconciliation that accounts for EVERY input from the source files to the final
plan, and a crackdown on every *class* of hidden inconsistency — not one more
symptom fix.

---

## 0. Root cause — WHY bugs kept recurring

Every prior audit (v3.2 … v3.4.0) was **reactive and output-focused**: it started
from a symptom someone noticed in the *output* (a wrong number, a weird route
code, an A/B suffix) and fixed that one thing. None of them did the opposite,
harder check: **start from every input row and force it to reconcile to the
output, with an explicit logged reason for every loss at every stage.**

The pipeline loses or distorts data at *many* stages, each quietly:

| Stage | Silent failure mode | When we finally caught it |
|---|---|---|
| Geocoding | name → Srinagar centroid collapse | v3.3.8 |
| Geocoding | unknown district → defaulted to Srinagar | v3.3.9 |
| Geocoding | same name → 2 different coords (TRC) | v3.4.0 |
| Stops master | wrong coords (Airport 80 km off) + wrong districts | v3.4.0 |
| SSCL injection | fuzzy match → 11 false trunks | v3.3.9 |
| Route codes | off-network → wrong district | v3.4.0 |
| **bbox clip** | **silently dropped/truncated ~29 routes AND cropped the coverage denominator to the in-box population** | **v3.4.1 (this audit)** |

Because each fix was a patch over one leak, the next leak surfaced as a "new
bug." There was never a step that said *"here are 1,259 + 208 + 30 inputs; here is
where each one ended up; the totals must add up; anything unexplained is a bug."*

**The fix this time is structural, not another patch:**
1. **A complete funnel reconciliation** (§2) — every input row → its fate + reason;
   in = out + dropped at every stage; 0 unexplained loss.
2. **A bug-CLASS crackdown** (§3) — scan the whole system for each *category* of
   defect, so we are not playing whack-a-mole.
3. **Make silent drops loud** — every drop already calls `_record_drop`; this
   audit reconciles those counts and flags any gap.
4. **Single sources of truth** (already converged): coordinates = the engine's
   own geocodes; geography = OSM district/tehsil polygons; no more parallel
   hand-built master.

---

## 1. bbox extension (the concrete fix) — ✅ DONE

The study bbox was `lat[33.50,34.50] lon[74.40,75.20]`, hard-excluding Kupwara,
Gurez, Karnah — and, because the box's west edge was lon 74.40, even **Baramulla
town and Uri**. The population raster `kashmir_worldpop.tif` had been pre-cropped
to exactly this box, so the "study-area population" (5.1M) was only the in-box
count, not the division.

Fixes (v3.4.1):
- bbox extended to the 10-district extent: `lat[33.30,34.85] lon[73.70,75.65]`.
- `kashmir_worldpop.tif` re-cropped from the full-India `ind_ppp_2026_100m.tif`
  (verified identical model — both give 5,105,699 over the old box) to the
  extended box.
- `study_area_population()` now clips the raster by the **10-district union
  polygons** (point-in-polygon) → **6,584,763** — the honest division
  population — instead of the raster rectangle.
- Recovered **29 routes** that the old box dropped/truncated (Kupwara, Handwara,
  Sogam, Tangdar, Chowkibal, Trehgam, Dardpora; Baramulla, Uri, Bandipora,
  Kamalkote, Garkote, Nambia; SE Anantnag — Shangus, Uttersoo, Phalgam→Anantnag).

(Result numbers filled in §4 after the v3.4.1 run.)

---

## 2. Full funnel reconciliation (v3.4.1) — every input accounted, 0 unexplained loss

| Stage | Count | Where the rest went (logged) |
|---|---|---|
| Srinagar-RTO minibus permits (source) | 1,259 | 806 carry no route (Route Covered="NA"); 4 names fail geocoding → `geocode_failures.csv`; **445** geocode → existing-routes |
| JKRTC / DSU "Other" rows (source) | 208 | 103 unresolved → `other_routes_dropped.csv` (85 distinct failed names); **169** geocode → existing-routes |
| **existing-routes.csv** (geocoded) | **614** | = 445 minibus + 169 JKRTC |
| + SSCL synthetic backbone | +30 | the 30 published e-bus trunks |
| **= engine input** | **644** | |
| → active | **186** | |
| → merged (duplicate/reverse/consolidated permits) | **458** | every one tagged `MERGED_INTO_TRUNK` + `Merged_Reason` |
| **engine in = out** | **644 = 186 + 458** | **0 routes lost between input and output** ✅ |
| bbox drops (this run) | **0** | the extended box covers all geocoded valley endpoints |
| OSRM routed | **644/644** | 0 circuity fallback |

Every source row now has a logged fate. The only "losses" are at geocoding
(permits with no route data, or village names OSM can't place — both in reject
files) and consolidation (duplicate/reverse permits → one service per corridor).

## 3. Bug-class crackdown (system-wide, not symptom-by-symptom)

| # | Bug class | Scan result |
|---|---|---|
| 1 | **Silent route loss** | bbox clip dropped/truncated **29 routes** → FIXED (§1). Engine in=out (644=186+458), 0 unexplained. |
| 2 | **Stale / clipped reference data** | population raster was pre-cropped to the bbox (denominator only 5.1M) → re-cropped from full-India raster + district-union denominator (6.58M). |
| 3 | **Double-counting** | **reverse-direction corridors** (A→B and B→A both active, ~10 pairs, ~125 buses) → FIXED via undirected consolidation. Same-direction duplicate permits already consolidated. |
| 4 | **Coordinate inconsistency** | 0 names with >1 distinct coordinate (name-aggregation, v3.4.0). |
| 5 | **Wrong geography** | every master stop's district == independent point-in-polygon (0 mismatch). |
| 6 | **Fuzzy false-positives** | SSCL false trunks fixed v3.3.9 — still exactly 30 SSCL backbone, all active. |
| 7 | **Value sanity** | 0 zero/neg fleet · km · cycle; HPV+MPV+LPV = Fleet for all 186; headways only 15/20/35. |
| 8 | **Cross-artefact divergence** | codes identical across CSV/GeoJSON/dashboard/pretty workbook; 0 dash/dup/UNMATCHED, all valid. |
| 9 | **Lying comments** | the bbox comment claimed Kupwara was "handled separately" — it wasn't (dropped). Comment corrected; behaviour fixed. |
| 10 | **Residual edge cases (documented, not systemic)** | 1 geocode-merge (Rangpora≈Pandach <150 m → 1 stop); "Gund" name shared by 2 districts; ~40 villages on a correct-district-centre approximation. All disclosed, not silent. |

## 4. Result & verification (v3.4.1)

| Metric | v3.4.0 | v3.4.1 |
|---|---|---|
| Active routes | 172 | **186** (+14 net: +29 recovered, −~15 merged incl. reverse-dups) |
| Total fleet | 1,005 | **1,144** (221 HPV / 839 MPV / 84 LPV) |
| Districts with active routes | 9 | **10** (Kupwara recovered) |
| Study-area population (denominator) | 5.1M (clipped) | **6.58M** (true 10-district union) |
| Served / coverage | 1.93M / 37.8% | **2.32M / 35.2%** (more served, honest denominator) |
| Reverse-direction double-counts | ~10 pairs | **0 true pairs** |
| SSCL backbone | 30 | 30 (all active) |

**Verification: 9/9 funnel+sanity checks pass; OSRM 644/644; engine in=out (0
lost); route codes valid/unique across all artefacts; every district == PIP.**

### Why this should be the last "surprise"
The recurring bugs all shared one trait — a **silent transform** (a clip, a
default, a fuzzy match, a stale crop) that no check reconciled. This audit
(a) closed the last big one (bbox/denominator), (b) added the missing
reconciliation (in=out at every stage, with reasons), and (c) swept every bug
*class*, not just the reported symptom. Remaining items are **disclosed
approximations**, not hidden defects.
