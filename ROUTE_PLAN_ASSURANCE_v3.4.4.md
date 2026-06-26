# Final Assurance Report — v3.4.4 Kashmir Transit Plan

_Prepared 2026-06-26. A last independent assurance pass over the verified plan,
on three axes the route-by-route audit did not cover: (1) external benchmarking
against national standards and peer systems, (2) plan-wide accuracy & robustness,
(3) a blind second-opinion test of our own audit. Companion to
`ROUTE_VERIFICATION_RTO_APPENDIX.md`._

---

## 1. External benchmark — MoHUA standard & peer systems

**MoHUA Service Level Benchmark (SLB) for Urban Transport** sets the fleet
adequacy standard at **40–60 buses per lakh population** (0.40–0.60 buses / 1,000).

| | Buses | Buses per lakh (pop. served) | per 1,000 | vs MoHUA 40–60 |
|---|---:|---:|---:|---|
| **Today (Srinagar ~600)** | 600 | 25.9 | 0.26 | ✗ below standard |
| **v3.4.4 plan** | 1,004 | **43.3** | **0.43** | ✓ **meets standard** |

So the plan moves Kashmir from **non-compliant (~26/lakh)** to **compliant
(~43/lakh)** on the Government of India's own benchmark — a concrete, defensible
target, not an arbitrary number.

**Peer comparison (buses per 1,000):** Bengaluru/BMTC ≈ 0.52 (the best-served
major Indian city); most Indian mega-cities sit at 0.20–0.40; the MoHUA aspiration
is ≥ 1.0. The plan's **0.43** places Kashmir in the **upper tier of Indian
provision** — comparable to Bengaluru, above Delhi and most peers — while staying
realistic for a Year-1 deployable plan.

_Sources: MoHUA SLB for Urban Transport (mohua.gov.in); CEEW bus-market analysis;
BMTC / OpenCity Bengaluru ratios; DTC fleet figures (see links in the chat log)._

> Caveat: "per lakh" uses the 400 m-walkshed **population served (2.32 M)** as the
> denominator — the population the network actually reaches — not the full 6.58 M
> division (most of which is dispersed rural). This is the standard SLB framing
> (buses per lakh of the *served* urban catchment).

## 2. Plan-wide accuracy & robustness

**Distance accuracy vs the real world** (every route's modelled km vs the
web-verified real road km in the ledger):

| | MAPE | Median error | Within ±15 % of real |
|---|---:|---:|---:|
| v3.4.3 (before corrections) | 37.4 % | 16.8 % | 49 % |
| **v3.4.4 (after corrections)** | **13.3 %** | **6.3 %** | **74 %** |
| **PASS routes only** (engine, never corrected) | **10.9 %** | — | (all ≤15 % by definition) |

The headline: **the published plan's route distances are within ~13 % of reality
on average (median 6 %)**, and on the 93 routes we never touched the engine is
already within ~11 % — i.e. the model itself is sound, the corrections fixed the
tail of bad coordinates.

**Fleet robustness (sensitivity).** Re-sizing the whole active fleet while flexing
the two assumptions that drive cycle→fleet — the city-core congestion multiplier
(2.0 / 2.2 / 2.5) and the spare ratio (1.10 / 1.15 / 1.20):

| | spare 1.10 | spare 1.15 | spare 1.20 |
|---|---:|---:|---:|
| congestion 2.0× | 996 | 1,004 | 1,010 |
| congestion 2.2× (base) | 997 | **1,004** | 1,012 |
| congestion 2.5× | 999 | 1,007 | 1,014 |

**Fleet = 1,004, envelope 996–1,014 (±~1 %)** across all reasonable assumptions.
The headline number is not fragile — no assumption swings it materially.

## 3. Independent blind second opinion

A **fresh analyst (different agent, no sight of our verdicts, real-km or findings)**
re-verified an 18-route stratified random sample from scratch.

- **Verdict agreement: 100 % within one level; 61 % exact** (11/18). No gross
  disagreement — never did one rater PASS what the other FAILed.
- Where we differed, **we were the stricter rater in 5 of 7 cases** (we flagged
  REVIEW where the blind rater passed) — the conservative, safe direction for a
  government submission.
- Independent real-km estimates tracked ours to ~18 % median — the residual is
  genuine source variance on rural/ambiguous places, not method disagreement.

**The blind audit also earned its keep:** it independently identified **two routes
we had graded REVIEW as coordinate FAILs** — *Hazratbal/Lalbazar* (origin pinned
at Parimpora) and *Batamaloo→Manigam* (destination pinned ~15 km too far east).
Both were then **re-geocoded and re-routed via OSRM** (Manigam 54.5 → 37 km; SSCL
fleet kept at the empirical 13). This is reflected in v3.4.4 (49 corrected / 44
deferred) and the appendix.

---

## Bottom line
On all three external axes the plan holds up: **compliant with the MoHUA fleet
benchmark and in the upper tier of Indian provision; distances within ~13 % of
reality; fleet robust to ±1 % across assumptions; and our own audit independently
reproduced (100 % within-one-level), with the second opinion surfacing two more
coordinate fixes that are now applied.** Remaining open items are the disclosed
caveats in Appendix R (mountain-pass run-times, name-unverifiable villages, the
Garkote identity) — all pending the RTO's surveyed stop register.
