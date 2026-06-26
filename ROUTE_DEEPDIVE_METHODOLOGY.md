# Route-by-Route AI Deep-Dive Verification — Methodology

_Created 2026-06-24. This is the **human-analyst** verification layer: an AI
(Claude) researching each route against the **real world** — not a Python script
re-checking our own numbers. It complements `_verify_routes.py` (which only tests
internal consistency: our coords vs our polygons, our distance vs our OSRM). This
layer asks the question a script cannot: **does this route exist on the ground,
and do our numbers match what the world actually knows about that road?**_

---

## Why this exists (the correction)

`_verify_routes.py` trusts the engine's own OSRM distance and our own geocoded
coordinates, then checks them against our own admin polygons. If OSRM under-models
a mountain pass, the script can't see it — it has nothing external to compare to.
A government screening committee *will* compare to reality (Google Maps, JKRTC
timetables, local knowledge). So we do that first, ourselves.

**The analyst (Claude) does, per route:**
1. **Existence** — is this a real corridor? Do both endpoints exist as places?
2. **Coordinates** — are the engine's O/D (and via) coordinates the *actual*
   locations? (cross-checked vs web gazetteers + straight-line distance sanity.)
3. **Road distance** — what is the *real* road distance (Google/Yatra/distance
   sites/JKRTC)? Compare to our `Route_KM`. Flag >±15%.
4. **Travel time** — what is the *real* one-way drive time? Compare to our
   `Cycle_Time_Min`/2. Mountain passes (Sadhna, Mughal Rd, Sinthan) are the main
   failure mode — OSRM under-models switchbacks.
5. **Historic / known service** — does JKRTC / SRTC / private/sumo service
   actually run this corridor today? At what rough frequency? Is our
   headway/fleet plausible against that, or absurd (e.g. "50-min headway" on a
   5-hour-each-way border road that in reality runs 1–2 buses/day)?
6. **Real-world constraints** — permit/border zone, seasonal closure, single-lane,
   bridge limits — note even where we deliberately don't model them.

Each route gets a **verdict**:
- **PASS** — corridor real, coords good, distance within ±15%, time plausible,
  service framing sane.
- **REVIEW** — real corridor but ≥1 number is off (distance/time/headway-framing).
  Carries a specific finding + what to change.
- **FAIL** — corridor does not exist / endpoints wrong / route is impossible.

Every row cites its **sources** (URLs). This is the audit trail.

---

## Sources (in priority order)
1. **JKRTC / JKSRTC timetable** (`jksrtc.co.in/pdf/timekashmirr.pdf`) and the
   stage-carriage fare tables (`jaktrans.nic.in`) — authoritative for which
   corridors are actually operated and the official stage distances/fares.
2. **Google Maps / Yatra / distancebetween2 / distancesfrom / tourtravelworld** —
   real road distance + drive time. Cross-check ≥2 sources; mountain roads vary.
3. **Greater Kashmir / Rising Kashmir / local press** — service history, route
   openings, road status, border-permit and seasonal-closure facts.
4. **Our own engine row** — the thing being audited (Route_KM, Cycle, Headway,
   Fleet, Load, coords). Never the source of truth for reality.

## Model policy (per the volume/quality trade-off)
- **Opus 4.8 (`claude-opus-4-8`)** — the 71 long rural `Regional_District`
  lifelines + anything flagged. These need judgment (e.g. "152 km includes
  Teetwal *beyond* Tangdhar; distance-to-Tangdhar ≈ 140; our 121 is ~15% short —
  but the real problem is the cycle time, not the km"). This is what's running now.
- **Sonnet 4.6 (`claude-sonnet-4-6`)** — the 115 short Urban/Peri-Urban routes,
  where the check is mostly coordinate + distance corroboration. Cheaper, fast,
  reliable web research.
- **Haiku 4.5** — only pure coordinate/distance lookups, never a verdict.
- Spawn as `Agent(subagent_type=…, model=…)`, ~10–15 routes per agent, each
  agent writes its ledger rows and returns findings.

---

## Output
- `ROUTE_DEEPDIVE_LEDGER.csv` — one row per active route (186), columns below.
- Findings roll up into `ROUTE_DEEPDIVE_FINDINGS.md` (the REVIEW/FAIL worklist
  for the RTO, grouped by issue class).

### Ledger columns
`Route_Code, Route_Name, Eng_O, Eng_D, Eng_KM, Eng_Cycle_Min, Eng_Headway,
Eng_Fleet, Eng_Type, Eng_Load, Real_RoadKM, Real_OneWay_Time, Real_Service,
Coord_Check, KM_Delta_Pct, Time_Check, Verdict, Finding, Sources`
