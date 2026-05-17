# Problems Found in Teammate's Phase-1 Proposal (Rounds 1 & 2)

Independent review by the engine maintainer. Date: 2026-05-18. Engine version: v3.3.1.

This document records the **proposed Phase-1 changes that were rejected** during implementation, with the reason in each case. The accepted subset has already landed (commits 017f1dd + the follow-up that introduced this file).

Audience: the proposing teammate. The goal is to make the rejections easy to challenge, not to win an argument. Each rejection is keyed back to the specific STEP from the proposal so the conversation can be precise.

---

## ROUND 1 — `Final Phase 1 Pipeline — All Change.txt`

### ❌ R1-A: Inverted headway table  *(Phase 3)*

> *"ClassUrbanPeri-urbanInter-districtLP5 min8 min15 minMP10 min15 min30 minHP20 min30 min60 min"*

In the engine's classification semantics, **HP = High Priority = highest-CDI route = the routes that most need frequent service.** The proposal as written would assign 20-minute headway to the highest-demand routes and 5-minute headway to the lowest-demand routes — the opposite of what any transit-planning textbook would prescribe and the opposite of what your current `HEADWAY_HP_MIN=15 / MP=30 / LP=60` correctly does.

Two possibilities:

1. **It's a typo and HP↔LP are swapped.** If so, the corrected table is reasonable and adds typology variation that the current flat scheme lacks. **Please confirm so I can implement it.**
2. **You're using HP/MP/LP with different meanings than the engine** (e.g. "HP = highway / inter-district priority"). If so, the proposal needs a rename to avoid collision with the engine's existing HP/MP/LP bands.

Until you tell me which, I cannot implement this safely. Same issue carried into Round-2 STEP 2 unchanged.

### ❌ R1-B: Triple-counted tourism multipliers  *(Phase 2 + 2b + 9)*

The proposal stacks three tourism boosts on the same routes:

| Layer | Effect on Gulmarg-type route |
|---|---|
| Existing Tier-3 POI weight | 0.6 summer / 0.0 winter |
| Proposed catchment population × 1.4 | +40% pop credit |
| Proposed CDI × 1.3 | +30% CDI |

Compound: a tourist route's effective CDI moves by **~1.4 × 1.3 × Tier-3 = ~1.8×** with no validation against actual ridership data. The Tier-3 POI weight already captures the demand signal CHALO observes; layering catchment and CDI multipliers on top is unmotivated double/triple counting.

Same issue carried into Round-2 STEP 9 unchanged.

### ❌ R1-C: CDI floor of 0.2 for HP classification

> *"CDI floor of 0.2 for HP classification regardless of Jenks output"*

Jenks Natural Breaks classifies routes **relative to the network's actual CDI distribution**. An absolute 0.2 floor would force-promote a long tail of marginal routes into HP whenever the network-wide distribution sits low (winter mode, sparse-data runs, etc.). The v3.2 audit (commit message: "B1") explicitly removed circular Road_Multiplier compounding from `Final_CDI` for exactly this reason. Bringing back an absolute floor would re-introduce the same class of bug from the opposite direction.

### ❌ R1-D: Peak Cycle Time Multiplier on top of existing congestion

> *"Peak Cycle Time Multiplier — Urban base × 1.25, Peri-urban base × 1.15, Inter-district base × 1.05"*

The engine already applies `CONGESTION_CITY_CORE=2.2` and `CONGESTION_PERI_URBAN=1.4` inside `compute_cycle_times`. (These were just bumped from 1.4/1.1 in the v3.2 audit response B4 because the original values under-counted downtown.) Adding another 1.25× multiplier means downtown cycle times scale by **2.2 × 1.25 = 2.75×** without any new calibration data backing that number.

Same issue carried into Round-2 STEP 1 unchanged (the "× peak multiplier after cap" line).

### ❌ R1-E: Wrong vehicle capacities  *(Phase 3)*

> *"HP class → HPV (capacity 44), MP class → MPV (capacity 22), LP class → LPV (capacity 9)"*

These do not match Kashmir's actual fleet:

| Class | Proposal | Real (SSCL deployment) |
|---|---|---|
| HPV (12m) | 44 | 60–70 seated+standing |
| MPV (9m) | 22 | 35–45 |
| LPV (minibus) | 9 | 20–25 |

A 9-passenger vehicle is a **Tata Sumo or shared jeep**, not a feeder bus. Using these in the Load_Ratio computation would inflate the apparent overload signal across the board.

### ⚠️ R1-F: Route Typology Flag already exists

> *"Route Typology Flag — Urban / Peri-urban / Inter-district on every route at ingestion"*

Already present as the `Route_Type` column, assigned in `apply_geometries` (Urban < 15km, Peri-Urban 15–40km, Regional_District ≥ 40km, with operator-category overrides). Step 8 fleet floors already branch on it. No action needed.

---

## ROUND 2 — *"Steps To Be Done — In Order"*

### ❌ R2-1 / STEP 2: Inverted headway table — repeat of R1-A

Identical table to Round 1. Same blocker. Same question: HP↔LP swap or rename?

### ❌ R2-2 / STEP 9: Tourist CDI × 1.3 — repeat of R1-B

Same triple-count concern. The tourist-corridor flag is already implemented as a **tag** (no CDI impact, surfaced for planner review and map layering) in commit 017f1dd. Promoting it to a CDI multiplier is the issue.

### ❌ R2-3 / STEP 4: Vehicle assignment reverts the v3.2 audit fix B2

The v3.2 audit response B2 explicitly removed the blanket 85% HPV split because **"it contradicted SSCL's actual fleet (74% MPV / 26% HPV; short urban loops are 100% 9m)."** The fix was Route_KM-bracketed share: `<12km → 0% HPV, 12-22km → 50/50, ≥22km → 85% HPV`. STEP 4 throws that out and goes back to CDI-class primary (HP→HPV blanket), which would re-introduce the bug the audit just fixed.

The Route_KM bracket logic is empirically anchored in `CMP_TRUNK_ROUTES` (the per-route 9m/12m counts from CHALO). CDI-class primary is unanchored.

### ❌ R2-4 / STEP 1: Second peak multiplier — repeat of R1-D

The per-km cap part of STEP 1 (Urban capped at 4 min/km × Route_KM × 2) was **accepted and implemented** as `CYCLE_TIME_CAP_MIN_PER_KM`. The "× 1.25 peak multiplier after cap" part was rejected for the R1-D double-count reason.

### ❌ R2-5 / STEP 5: Load Ratio formula has a unit mismatch

> *"Trips_Per_Day = Operating_Hours (16) / (Peak_Cycle_Time / 60)"*
> *"Daily_Capacity = Fleet × Vehicle_Capacity × Trips_Per_Day"*

The first expression computes **trips per bus per day** (one bus, 16h ÷ cycle hours = cycles per bus). The second multiplies by `Fleet × Vehicle_Capacity` again — so the formula sneaks in a "per-bus × all buses × per-bus capacity" chain that double-counts.

The engine's current formula is correct:
```
daily_trips    = (service_hours × 60 / headway) × 2     # per-route round trips/day
daily_capacity = avg_cap × daily_trips                  # avg_cap is SUM across fleet
```

### ⚠️ R2-6 / STEP 8: PJT already implemented identically

`PJT = 5.5 + Headway/2 + Cycle/2`, flag >45 min — already shipped in commit 017f1dd as `Pax_Journey_Time_Min` + `Journey_Time_Flag`.

### ⚠️ R2-7 / STEP 12: Procedural — engine reruns all exports every invocation

No work needed; the existing pipeline already regenerates XLSX, Folium maps, GeoJSON, passenger impact CSV, and audit log on every run. The "confidence caveat sheet" is a reasonable add for the next round if you want me to wire it in.

---

## ✅ ACCEPTED and IMPLEMENTED in v3.3.1

| ID | Source | Implementation |
|---|---|---|
| STEP 10 | R2 | `SOCIAL_FLAG_BUFFER_M` 500 → 250m; attractor list pruned 17 → 11 (industrial estates removed; they get fair treatment via POI gravity already) |
| STEP 11 | R2 | `SSCL_CDI_Conflict_Strong` (non-SSCL within 0.2 of max SSCL CDI) + `SSCL_CDI_Conflict_Weak_SSCL` (SSCL ≥0.2 below max non-SSCL) |
| STEP 1 cap part | R2 | `CYCLE_TIME_CAP_MIN_PER_KM = {Urban: 4.0, Peri_Urban: 2.5, Regional_District: 1.5}` applied as upper bound only |
| STEP 6 | R2 | `PHASE4_MODE_SHARE_BY_TYPE = {Urban: 0.090, Peri_Urban: 0.072, Regional_District: 0.054}` in `compute_phase4_metrics` |
| STEP 7 | R2 | `PHASE4_SUBSIDY_RISK_THRESHOLD = 0.6` (was 0.5) |

## ✅ ACCEPTED earlier in v3.3 (commit 017f1dd)

| ID | Source | Implementation |
|---|---|---|
| Tourist Corridor flag | R1 (Phase 1) | `Tourist_Corridor` column at ingestion (tag only — no CDI impact) |
| Seasonal Operability flag | R1 (Phase 1) | `Seasonal_Operability` column (Year_Round / Seasonal / Winter_Suspended) |
| Spare ratio 1.15 | R1 + R2 STEP 3 | `FLEET_SPARE_RATIO = 1.15` applied in step8 |
| District-HQ LP→MP floor | R1 (Phase 2b) | Applied in step5 for Regional_District + Social_Flag routes; `District_HQ_Floor` audit column |
| SSCL conflict planner-review flag | R1 (Phase 2b) | step5b — tightened in R2 STEP 11 above |
| Load_Ratio, PJT, Viability, Emissions, Equity | R1 (Phase 4) + R2 STEP 5/7/8 | `compute_phase4_metrics` |
| Seasonal map / GeoJSON layer | R1 (Phase 4) | Columns surfaced in GeoJSON export |

---

## What I need from you to unblock the rest

1. **Headway table (R1-A / R2-2)** — confirm HP↔LP swap, or rename your bands so the engine can be patched without colliding with the existing HP/MP/LP semantics.
2. **Tourism multiplier (R1-B / R2-9)** — if you want a tourism boost beyond the existing Tier-3 POI weight, propose a *single* multiplier with a calibration target (e.g. a CHALO ridership delta on Gulmarg-corridor routes vs control), not a stack of three.
3. **Vehicle capacities (R1-E)** — confirm whether 44/22/9 is from a source document I'm missing, or whether the SSCL operational figures (60/35/20) should be used. The Load_Ratio output is sensitive to this.

Everything else is either already shipped or rejected for the reasons above.
