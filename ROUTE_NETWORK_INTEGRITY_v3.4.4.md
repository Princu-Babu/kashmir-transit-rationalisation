# Network-Integrity & Fleet-Validity Audit — v3.4.4

_Created 2026-06-26. Validates the 186 active routes **as a system** (not route-by-route)
and stress-tests fleet sizing. Companion to `ROUTE_PLAN_ASSURANCE_v3.4.4.md`._

---

## Why this audit
Everything prior validated each route in isolation (real corridor, correct
coordinates, real road distance). This pass asks the questions only a *network*
view can answer — do the routes connect, are they redundant, are there gaps —
plus the honest limit on fleet validity.

## 1. Connectivity — STRONG ✅
- **184 of 186 routes form a single connected network** (3 components; the other
  two are the 2 orphan routes below). Riders can transfer across essentially the
  whole network.
- Clear **radial hub-and-spoke** structure: the **Srinagar central terminal**
  touches **81 routes**, **Parimpora 19**, then Lal Chowk / LD-Hospital-area hubs.
- **97 single-end "stub" routes** — these are rural lifelines that terminate at
  their own village (only they serve it) but connect to the network at the
  Srinagar end. This is expected and healthy, not a defect.
- **2 true orphan routes** (neither end shared with any other route) — review:
  `SRSR02023314`, `SRPW02022104`.

## 2. Redundancy — LOW ✅ (confirms the engine's consolidation worked)
~25 route-pairs share >90% of their path, but **almost all are legitimate
shared-trunk lifelines** — different villages riding a common corridor into
Srinagar, each serving a distinct tail (e.g. Srinagar→Beeru vs Srinagar→Budgam:
Beeru extends past Budgam; Srinagar→Trehgam vs →Chowkibal: distinct Kupwara
villages on the same trunk). These are *not* waste.

**True near-duplicate candidates for RTO merge-review (handful):**
- `SRPW02033906` Srinagar→Ratnipora ↔ `SRPW02033907` Srinagar→**Ratnipura** — same
  place, spelling variant. Clearest merge.
- `BPSR01020239` Bandipora→Srinagar ↔ `BPSR01020139` Bankoot→Srinagar (Bankoot
  route subsumes the Bandipora trunk).
- `BRSR01020139` Baramulla→Srinagar ↔ `BRSR01020239` Fathgath→Srinagar.
- `SRGB02033903`/`SRGB02033902` Srinagar→Safapora (Sumbal vs GBL routings).

Net: minimal fleet savings available — the network is **not** carrying wasteful
parallel service.

## 3. Coverage gaps — 3 real, actionable
Of 39 OSM tehsils, 31 have a served stop. Of the 8 without one, route geometry
shows most are still **traversed**; only three are genuine gaps:

| Tehsil | Status | Action |
|---|---|---|
| **Gurez** | no route passes through | Add a Bandipora–Gurez lifeline (its own remote tehsil) |
| **Kokernag** | no route passes through | Add Anantnag–Kokernag service |
| **Karnah** | not reached — the Srinagar→Tangdhar endpoint is pinned *short* of Karnah | Re-geocode the Tangdhar terminal to the real Karnah town (also a `ROUTE_DEEPDIVE` flag) |
| Awantipora (35 km in), Bijbehara (26 km), Uri (8.5 km), Khag (3.6 km) | **traversed** by routes — no real gap | none |

## 4. District balance — Srinagar-centric (expected)
Endpoint counts: Srinagar 251 ≫ Budgam 28, Pulwama 21, Baramulla 19, Ganderbal 11,
Kupwara/Anantnag 10, Kulgam 8, Bandipora/Shopian 7. This mirrors where population
and demand concentrate; the rural districts are served by long radial lifelines.

## 5. Fleet validity — the honest ceiling
The fleet is sized to a **service standard** (headways), which is the correct
method and is the only one defensible without ridership data. Modeled load
factors are low (median 0.09) **by design** — the demand model is static
open-data with no frequency-elasticity (Mohring) and no per-route AFC feed, so a
"load-factor audit" would *wrongly* suggest cutting ~800 buses. **Deeper fleet
validation requires the RTO's per-route AFC/ticketing data** — the #1 data ask.

What the model *can* surface reliably is the **under**-provisioned tail — 6
corridors where demand exceeds capacity even on the pessimistic model. These
genuinely warrant **higher frequency than the standard**:

| Route | Load | Now |
|---|---|---|
| Bandipora→Baramulla | 1.96 | 5 buses @ 35 min |
| Anantnag→Shopian | 1.53 | 5 @ 35 min |
| Bandipora→Soura | 1.28 | 6 @ 35 min |
| Pahalgam→Anantnag | 1.23 | 7 @ 35 min |
| Batamaloo→Charar-i-Sharief | 1.12 | 12 @ 15 min |
| Baramulla→Kupwara | 1.03 | 5 @ 35 min |

## Verdict
The 186 routes form a **coherent, well-connected, low-redundancy radial network**
— it passes as a *system*, not just route-by-route. Open actionables (all RTO
execution calls, not engine bugs): **6 frequency boosts**, **~4 merge-reviews**,
**3 coverage gaps** (Gurez, Kokernag, Karnah/Tangdhar pin). True fleet-vs-demand
validation is gated on AFC ridership data.
