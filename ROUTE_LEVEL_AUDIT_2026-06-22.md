# Route-level methodology audit — does the textbook method fit Kashmir? (22 Jun 2026)

Scope: every one of the **186 active routes** (v3.4.1), checked individually for
(a) whether its direction/geometry makes sense and (b) whether the textbook
rationalisation method (constant-headway fleet sizing + open-data demand) is
accurate for that route's *local* context. Conclusions are evidence-based, per
route-class.

---

## A. Direction & geometry — ✅ sensible for all 186

- **Implied round-trip speeds 15–40 km/h** (median 24) — every route physically
  plausible; none <8 or >45. OSRM routed 644/644 on real roads (0 fallback).
- **Circuity (Route_KM ÷ straight-line): median 1.34**, i.e. routes are ~34%
  longer than the crow-flies line — exactly what road networks give.
- **9 routes have circuity >2.3.** Each was checked individually: every one is a
  *legitimately circuitous permitted route with a via-point through a city hub*,
  e.g. "Rangpora → Soura **via Lal Chowk**" (22 km vs 3 km straight — it dips
  south to Lal Chowk then back north), "Qamarwari → Parimpora **via LD**",
  "Soura → Gadoora **via Ganderbal**". The engine honours the filed via-waypoints,
  so the geometry reflects the *real permitted corridor*, not an error.
  → Direction makes sense for all 186. (Optional future refinement: some filed
  permits are inherently circuitous; straightening them is a corridor *redesign*
  decision, not a data fix.)

---

## B. Textbook method fit — accurate for the city core, NOT for rural lifelines

The fleet rule is the classic `fleet = ⌈cycle ÷ headway⌉ × spare` (Vuchic),
with a 15/20/35-min headway by band and a hard 35-min ceiling (an RTO ask). That
is a **dense-urban** assumption: it sets frequency by a clock, independent of how
many people actually ride. Three regimes:

### B1. Urban Srinagar core — ✅ textbook is appropriate
High, fairly uniform demand; congestion ×2.2 and the Jhelum-bridge penalty are
modelled; frequent service is justified. The method fits.

### B2. Long rural lifelines — ❌ textbook massively OVER-provisions
The 35-min ceiling forces a **uniform ~55 trips/day** on *every* Regional route,
regardless of demand, so the fleet is driven by route length, not ridership:

| Route | km | trips/day | fleet | demand (pax/day) | load |
|---|---|---|---|---|---|
| Srinagar → Tangdar (Karnah) | 121 | 55 | 13 | 268 | 0.18 |
| Srinagar → Handwara | 74 | 55 | 9 | 165 | 0.10 |
| Zaloora → Srinagar | 63 | 55 | 7 | 133 | 0.08 |
| Bankoot → Srinagar (Bandipora) | 61 | 55 | 7 | 135 | 0.08 |

Running a **121 km mountain bus 55 times a day for ~270 riders (~5 per trip)** is
operationally unreal — a real Tangdar/Karnah lifeline runs ~4–8 round trips/day.
Across the network: **Regional_District = 71 routes, 481 buses (42% of the
fleet), median load 0.11.** This is the single largest methodology↔context
mismatch. The clock-headway concept simply doesn't belong on a 100 km rural
lifeline.

### B3. High-demand inter-district corridors — ❌ textbook UNDER-provisions
The same flat ceiling *starves* the genuinely busy corridors (load >1.0):

| Route | km | fleet | load | demand |
|---|---|---|---|---|
| Bandipora → Baramulla | 46 | 5 | **1.92** | 3,000 |
| Anantnag → Shopian | 44 | 5 | **1.50** | 2,461 |
| Bandipora → Soura | 51 | 6 | 1.25 | 2,029 |
| Phalgam → Anantnag | 40 | 7 | 1.20 | 1,854 |

So the constant-headway rule is wrong in *both* directions: it over-serves the
empty lifelines and under-serves the full inter-district routes.

**Recommendation (B):** for non-urban routes, size frequency from **demand** with
a **social-minimum floor** — e.g. trips/day = clamp(demand-implied, min ≈ 4–6,
max ≈ 16) — instead of a flat 35-min clock. Indicative effect: Regional fleet
~481 → ~150–200, freeing ~250–300 buses to (i) relieve the overloaded corridors
and (ii) lower the headline ask to a more credible level. **This contradicts the
earlier RTO "≤35 min everywhere" directive, which was an *urban* ask — so it is a
policy decision, not a silent fix.**

---

## C. Local-context modelling gaps (seasonality & tourism) — ⚠ under-modelled

- **Winter pass closures not represented.** `Seasonal_Operability` flags only 8
  routes. **Srinagar → Tangdar is marked "Year_Round"** — but the Sadhna Pass to
  Tangdar/Karnah closes under snow each winter. Same physical reality applies to
  Gurez (Razdan Pass) and the Sonamarg side (Zojila). These should be Seasonal.
- **Tourism under-tagged.** Only 8 `Tourist_Corridor` routes (Pahalgam, Tangmarg
  correct). The Sonamarg gateway (via Kangan), Gulmarg (via Tangmarg), Yusmarg,
  Doodhpathri, Aharbal, Kokernag/Verinag corridors are largely unflagged — so
  their strong *summer* peak and *winter* trough aren't in the demand profile.
- Consequence: a single year-round average over- or under-states service on the
  routes whose demand is most seasonal. A summer/winter scenario split (the engine
  already has a `WINTER_SCENARIO` hook for walkshed shrink) should extend to
  operability + tourist demand.

---

## D. Demand-model caveat (already disclosed, restated for this lens)
Load ratios are computed from the open-data demand proxy (WorldPop catchment ×
corridor-share × capture scalar), which is static and conservative — so the
*absolute* loads read low network-wide. That doesn't change the **relative**
conclusion (fleet is decoupled from demand by the flat headway), but it means the
exact "right" rural frequency needs the RTO's per-route AFC/ridership (a standing
P1 data ask) to pin down.

---

## E. Verdict
- **Directions/geometry: sound for every route.**
- **Textbook method: right for the Srinagar urban core; wrong for the ~71 rural
  Regional lifelines (over-served) and ~6 busy inter-district corridors
  (under-served).** The fix is demand-responsive frequency with a social floor —
  a policy choice that reduces the fleet and improves equity, but overrides the
  "35-min everywhere" RTO ask.
- **Seasonality/tourism: under-modelled** for winter-closure and tourist
  corridors — a correctness fix (Tangdar etc. should be Seasonal) plus a
  summer/winter scenario.

_Decisions for the user: (1) adopt demand-responsive rural sizing? (2) fix the
seasonal-operability flags now? (3) expand tourist tagging + add a winter
scenario?_
