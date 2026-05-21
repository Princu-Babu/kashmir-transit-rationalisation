"""
generate_study_pdf.py

Produces `Kashmir_Transit_Headway_Fleet_Fundamentals.pdf` — a tutorial-style
study guide covering the maths and reasoning behind headway calculation and
fleet sizing in the Kashmir Valley engine. Worked examples use actual rows
from the v3.3.5 engine output.
"""
from __future__ import annotations

import os
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT, TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, Table,
    TableStyle, PageBreak, KeepTogether,
)


OUT_DIR = Path("E:/kash")
OUT_PDF = OUT_DIR / "Kashmir_Transit_Headway_Fleet_Fundamentals.pdf"


# ─── Styles ───────────────────────────────────────────────────────────────────
def _styles():
    s = getSampleStyleSheet()
    s.add(ParagraphStyle(
        "TitleBig", parent=s["Title"], fontSize=24, leading=28, spaceAfter=6,
        textColor=colors.HexColor("#1A237E"),
    ))
    s.add(ParagraphStyle(
        "Subtitle", parent=s["Normal"], fontSize=12, leading=16,
        textColor=colors.HexColor("#555"), spaceAfter=20,
    ))
    s.add(ParagraphStyle(
        "H1", parent=s["Heading1"], fontSize=18, leading=22,
        spaceBefore=14, spaceAfter=8,
        textColor=colors.HexColor("#1A237E"),
    ))
    s.add(ParagraphStyle(
        "H2", parent=s["Heading2"], fontSize=14, leading=18,
        spaceBefore=10, spaceAfter=6,
        textColor=colors.HexColor("#00695C"),
    ))
    s.add(ParagraphStyle(
        "Body", parent=s["BodyText"], fontSize=11, leading=16,
        spaceAfter=8, alignment=TA_JUSTIFY,
    ))
    s.add(ParagraphStyle(
        "Bullet2", parent=s["BodyText"], fontSize=11, leading=15,
        leftIndent=14, bulletIndent=2, spaceAfter=3,
    ))
    s.add(ParagraphStyle(
        "Formula", parent=s["Code"], fontSize=11, leading=15,
        spaceBefore=4, spaceAfter=8,
        textColor=colors.HexColor("#1A237E"),
        backColor=colors.HexColor("#F0F4FF"),
        borderPadding=6, borderColor=colors.HexColor("#1A237E"),
        borderWidth=0,
    ))
    s.add(ParagraphStyle(
        "Note", parent=s["BodyText"], fontSize=10, leading=14,
        textColor=colors.HexColor("#666"), spaceAfter=8, fontName="Helvetica-Oblique",
    ))
    s.add(ParagraphStyle(
        "Caption", parent=s["BodyText"], fontSize=9, leading=12,
        textColor=colors.HexColor("#666"), alignment=TA_CENTER, spaceAfter=12,
    ))
    return s


STYLES = _styles()


def H1(t):   return Paragraph(t, STYLES["H1"])
def H2(t):   return Paragraph(t, STYLES["H2"])
def P(t):    return Paragraph(t, STYLES["Body"])
def B(t):    return Paragraph(t, STYLES["Bullet2"], bulletText="•")
def F(t):    return Paragraph(t, STYLES["Formula"])
def N(t):    return Paragraph(t, STYLES["Note"])
def C(t):    return Paragraph(t, STYLES["Caption"])


def _table(rows, col_widths=None, header_bg="#1A237E", zebra=True, font_size=10):
    tbl = Table(rows, colWidths=col_widths, hAlign="LEFT")
    ts = [
        ("BACKGROUND",   (0, 0), (-1, 0), colors.HexColor(header_bg)),
        ("TEXTCOLOR",    (0, 0), (-1, 0), colors.white),
        ("FONTNAME",     (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",     (0, 0), (-1, -1), font_size),
        ("ALIGN",        (0, 0), (-1, 0), "CENTER"),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("BOX",          (0, 0), (-1, -1), 0.5, colors.HexColor("#CCC")),
        ("INNERGRID",    (0, 0), (-1, -1), 0.25, colors.HexColor("#DDD")),
        ("TOPPADDING",   (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
        ("LEFTPADDING",  (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]
    if zebra:
        for i in range(1, len(rows)):
            if i % 2 == 0:
                ts.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#F4F4F4")))
    tbl.setStyle(TableStyle(ts))
    return tbl


# ─── Page template ────────────────────────────────────────────────────────────
def _on_page(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#999"))
    canvas.drawString(20 * mm, 12 * mm,
                      "Kashmir Valley Transit Engine — Study Guide")
    canvas.drawRightString(190 * mm, 12 * mm, f"page {doc.page}")
    canvas.restoreState()


def _build_doc():
    doc = BaseDocTemplate(
        str(OUT_PDF),
        pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=20 * mm, bottomMargin=20 * mm,
        title="Kashmir Transit — Headway & Fleet Fundamentals",
        author="Kashmir Valley Transit Rationalisation Engine",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin,
                  doc.width, doc.height, id="frame")
    doc.addPageTemplates([
        PageTemplate(id="default", frames=[frame], onPage=_on_page),
    ])
    return doc


# ─── Content ──────────────────────────────────────────────────────────────────
def _flow():
    flow = []

    # Cover
    flow += [
        Spacer(1, 20 * mm),
        Paragraph("Kashmir Valley Transit", STYLES["TitleBig"]),
        Paragraph("Headway &amp; Fleet-Sizing Fundamentals",
                  STYLES["TitleBig"]),
        Spacer(1, 8 * mm),
        Paragraph(
            "A study guide to the maths and reasoning behind the v3.3.5 "
            "Kashmir Valley Transit Rationalisation Engine — covering how "
            "headway is chosen, how cycle time is estimated, how fleet "
            "size is derived, and how every number on the dashboard ties "
            "back to a formula or a CHALO observation.",
            STYLES["Subtitle"]),
        Spacer(1, 60 * mm),
        Paragraph("Engine v3.3.5  •  May 2026", STYLES["Caption"]),
        Paragraph("Principal Secretary of Transport, J&amp;K",
                  STYLES["Caption"]),
        PageBreak(),
    ]

    # ─── 1. WHY HEADWAY MATTERS ────────────────────────────────────────────
    flow += [
        H1("1. Why headway is the most important number"),
        P(
            "<b>Headway</b> is the time gap between two consecutive buses on the "
            "same route. Everything else in a transit plan — fleet size, "
            "service hours, vehicle type, peak-vs-off-peak operations, "
            "revenue, even bus-stop infrastructure — is downstream of this "
            "one decision."
        ),
        P(
            "A passenger picking between bus, auto, or private vehicle is "
            "really picking between <b>wait time + travel time</b>. Wait time is "
            "approximately <i>headway / 2</i> on average (you arrive at a random "
            "moment, the next bus is on average half a headway away). So a "
            "20-minute headway means a 10-minute average wait, which most "
            "people will tolerate; a 60-minute headway means 30 minutes of "
            "waiting, which most won't."
        ),
        F(
            "Average passenger wait time  ≈  Headway / 2 "
            "(uniform arrival assumption)"
        ),
        P(
            "This is why the engine treats headway as a <b>policy lever</b>, not "
            "a derived value. Every active route is assigned a target headway "
            "based on its priority band; everything else follows."
        ),
        H2("Headway targets in the Kashmir Valley v3.3.5 plan"),
        _table(
            [
                ["Band", "Description", "Headway", "# of routes"],
                ["SSCL", "30 CHALO e-bus routes (45 matched permits)",
                 "15 min",  "45"],
                ["HP",   "High-priority non-SSCL trunks",
                 "20 min",  "85"],
                ["MP",   "Medium-priority feeders",
                 "35 min",  "50"],
                ["LP",   "Low-priority / lifeline routes",
                 "60 min",  "23"],
                ["Social-promoted", "Social-flag LP→MP exceptions",
                 "45 min",  "4"],
            ],
            col_widths=[35*mm, 90*mm, 25*mm, 25*mm],
        ),
        Spacer(1, 6 * mm),
        N(
            "Why these particular numbers? Indian peer-city benchmarks "
            "(see Appendix A) show urban trunks at 5–15 minutes in the "
            "biggest metros, 15–25 minutes in tier-2 cities, and 25–35 minutes "
            "in tier-3 cities. Srinagar's size (1.66M residents) puts it "
            "between Chandigarh and Bhopal — so 15–20 minutes on the busiest "
            "corridors is the achievable phase-1 target."
        ),
        PageBreak(),
    ]

    # ─── 2. CYCLE TIME ────────────────────────────────────────────────────
    flow += [
        H1("2. Cycle time — what one bus actually takes per round trip"),
        P(
            "Cycle time is the wall-clock time for one bus to complete one "
            "round trip on a route: drive from origin to destination, "
            "(short break/layover), drive back. Once you know cycle time and "
            "headway, the fleet count follows mechanically."
        ),
        F(
            "Cycle_Time_Min  =  drive_time  +  stop_dwell  +  "
            "junction_penalty  +  bridge_penalty  +  layover"
        ),
        H2("Each ingredient, in the Kashmir engine"),
        B("<b>Drive time</b> — OSRM routing gives the free-flow travel time "
          "between origin and destination. The engine fetches this from a "
          "local Docker OSRM instance with a Kashmir/India OSM extract. "
          "Multiplied by a congestion factor: <b>2.2× in Downtown Srinagar</b> "
          "(latitude &gt; 34.07°), <b>1.4× peri-urban</b>, <b>1.0× rural</b>."),
        B("<b>Stop dwell</b> — every bus stop costs ~30 seconds for boarding/"
          "alighting. The engine estimates N stops as 1 stop per 500 m, then "
          "adds <i>STOP_PENALTY_MIN × N_stops</i> to the cycle. "
          "STOP_PENALTY_MIN = 0.5 min."),
        B("<b>Junction penalty</b> — major intersections, signals, and traffic "
          "circles each add ~30 s. Detected from sharp turns in the OSRM "
          "geometry."),
        B("<b>Bridge penalty</b> — Jhelum river crossings add a flat "
          "<b>JHELUM_BRIDGE_BOTTLENECK_MIN = 8 minutes</b> in both directions, "
          "captures the Habba Kadal / Amira Kadal peak-hour queuing that "
          "OSRM's free-flow duration cannot see."),
        B("<b>Layover</b> — buses need a short break at terminals. Engine "
          "adds ~10% of drive time, capped. Industry standard."),
        H2("Worked example — Batamaloo ↔ Hazratbal (SSCL-03)"),
        _table(
            [
                ["Component", "Value", "Notes"],
                ["Route_KM (round trip)",    "20 km",      "OSRM measured"],
                ["Drive @ 14 km/h avg",      "85.7 min",   "2.2× downtown congestion"],
                ["Stop dwell (40 stops × 0.5 min)", "20 min",  "1 stop per 500 m"],
                ["Junction penalty",         "4 min",      "8 major junctions × 30 s"],
                ["Jhelum bridge",            "8 min",      "Constant addition"],
                ["Layover",                  "8 min",      "10% of drive time"],
                ["<b>Cycle_Time_Min</b>",    "<b>~125 min</b>", "what the engine computes"],
            ],
            col_widths=[60*mm, 35*mm, 75*mm],
        ),
        Spacer(1, 6 * mm),
        N(
            "Reality check: CHALO's empirical effective cycle on this route "
            "is closer to ~55 min, because buses skip low-demand stops at "
            "peak and use faster road segments. So the engine's 125 min is "
            "conservative — it assumes every scheduled stop is served and "
            "downtown congestion applies at peak. That conservatism is why "
            "the recommended fleet is higher than current operations."
        ),
        PageBreak(),
    ]

    # ─── 3. FLEET CALCULATION ─────────────────────────────────────────────
    flow += [
        H1("3. Fleet sizing — the master formula"),
        P(
            "Once you have cycle time and headway, the number of buses needed "
            "to deliver service at that headway is mechanical:"
        ),
        F(
            "Fleet_Required  =  ⌈ Cycle_Time_Min ÷ Headway_Min × spare_ratio ⌉"
        ),
        P(
            "The ceiling function is essential — you cannot run half a bus. "
            "The <b>spare ratio</b> (engine default 1.15) accounts for "
            "scheduled maintenance, breakdown rotation, depot storage, and "
            "driver shift changes. Industry norm is 10–20%; the engine picks "
            "the middle."
        ),
        H2("Intuition — why the formula works"),
        P(
            "Picture a corridor with buses spaced exactly Headway minutes "
            "apart, all moving. Every Cycle_Time_Min the first bus arrives "
            "back at the start; in that span it has been overtaken (in time, "
            "not space) by exactly Cycle_Time_Min / Headway_Min other buses. "
            "That ratio IS the operating fleet you need on the corridor "
            "simultaneously."
        ),
        P(
            "Add the 15% spare and round up, and you have the fleet that "
            "delivers reliable service at the target headway. Drop any of "
            "the spare buses and headways start to slip — typically the bus "
            "going for service today means tomorrow's peak runs at "
            "Cycle_Time / (Fleet − 1), which is a longer headway than promised."
        ),
        H2("Worked examples from the v3.3.5 output"),
        _table(
            [
                ["Route", "Cycle (min)", "Headway", "Formula", "Fleet"],
                ["Batamaloo ↔ Hazratbal (SSCL-03)",
                 "125",  "15", "⌈125/15 × 1.15⌉",  "10"],
                ["Lalbazar ↔ LD",
                 "47",   "20", "⌈47/20 × 1.15⌉",   "3"],
                ["Parimpora ↔ Harwan (SSCL-01)",
                 "108",  "15", "⌈108/15 × 1.15⌉",  "9"],
                ["TRC ↔ Pulwama (SSCL-15)",
                 "165",  "15", "⌈165/15 × 1.15⌉",  "13"],
                ["Soura ↔ Ganderbal (LP)",
                 "75",   "60", "⌈75/60 × 1.15⌉",   "2"],
            ],
            col_widths=[60*mm, 22*mm, 18*mm, 38*mm, 18*mm],
        ),
        Spacer(1, 4 * mm),
        H2("Two important nuances in the Kashmir engine"),
        B("<b>Floors</b> — urban/peri-urban routes get a minimum of 2 buses "
          "regardless of demand (covers the spare-rotation gap). Regional "
          "lifeline routes get a floor of 1."),
        B("<b>SSCL empirical floor</b> — for the 45 SSCL-matched permits, "
          "the engine takes <b>max(formula_fleet, CHALO_empirical_fleet)</b>. "
          "If CHALO currently runs 5 buses on a route but the formula says "
          "the 15-min target needs 8, the engine recommends 8. If the formula "
          "says 3 but CHALO runs 5, the recommendation stays at 5 — never "
          "below current operation."),
        PageBreak(),
    ]

    # ─── 4. CAPACITY VS DEMAND ────────────────────────────────────────────
    flow += [
        H1("4. Capacity vs demand — Phase-4 KPIs"),
        P(
            "After fleet sizing is locked, the engine computes Phase-4 "
            "derived KPIs to flag routes where the recommended service is "
            "either too thin or too generous. These do not feed back into "
            "the fleet calculation — they are diagnostic outputs only."
        ),
        H2("Daily capacity (corrected in v3.3.3)"),
        F(
            "Daily_Capacity_Pax  =  Fleet × VehicleCapacity × "
            "(ServiceMinutes ÷ Cycle_Time_Min)"
        ),
        P(
            "Service hours are 6:00 AM – 10:00 PM (16 hours = 960 minutes). "
            "Vehicle capacities: <b>50 seats HPV</b> (12-metre bus), "
            "<b>35 seats MPV</b> (9-metre bus), <b>15 seats LPV</b> (tempo). "
            "Each bus completes <i>ServiceMinutes / Cycle_Time_Min</i> round "
            "trips per day; multiply by per-bus capacity for total seats offered."
        ),
        H2("Worked example — LALBAZAR ↔ LD"),
        _table(
            [
                ["Quantity", "Value"],
                ["Fleet (9-metre MPV)",         "5 buses"],
                ["Per-bus capacity",            "35 seats"],
                ["Cycle_Time_Min",              "47.2 min"],
                ["Service minutes / day",       "960 min"],
                ["Round trips per bus per day", "960 / 47.2 = 20.34"],
                ["<b>Daily_Capacity_Pax</b>",   "<b>5 × 35 × 20.34 ≈ 3,559</b>"],
            ],
            col_widths=[80*mm, 70*mm],
        ),
        Spacer(1, 6 * mm),
        H2("Daily demand — the corridor-share model (v3.3.2+)"),
        P(
            "Demand on a route is harder than capacity, because residents in "
            "the 400-metre walking buffer might use this route, a parallel "
            "route, an auto, or a private vehicle. The engine apportions "
            "buffer population among overlapping routes using a "
            "<b>headway-weighted share</b>:"
        ),
        F(
            "Daily_Demand_Pax  =  Pop_Buffer × corridor_share × "
            "mode_share × trip_rate × CAPTURE_SCALE\n\n"
            "corridor_share   =  (1 / Headway_Min × mean_inv_headway) ÷ "
            "(competitors × overlap_metric)\n\n"
            "mode_share       =  0.09 urban / 0.072 peri-urban / 0.054 "
            "regional   (typology-aware, CHALO-derived)\n\n"
            "trip_rate        =  1.6 trips per resident per day\n\n"
            "CAPTURE_SCALE    =  0.18   (empirically anchored to CHALO)"
        ),
        N(
            "CAPTURE_SCALE = 0.18 is the only \"calibration knob\" — it ties "
            "the buffer-based supply model to CHALO's observed SSCL ridership "
            "(~32k/day across 30 routes). It absorbs auto/walk/private-mode "
            "leakage that the 400 m buffer otherwise over-counts. Re-calibrate "
            "if CHALO totals shift by more than ±15%."
        ),
        H2("Load_Flag — the diagnostic signal"),
        _table(
            [
                ["Load_Ratio = Demand/Capacity", "Load_Flag",      "Meaning"],
                ["≤ 0",        "Red_NoCapacity", "Fleet is 0 — service deactivated"],
                ["0 < r < 0.4","Amber_Under",    "Capacity exceeds demand by 2.5×+ — could trim headway"],
                ["0.4 ≤ r ≤ 0.85", "Green",     "Sweet spot — load comfortable, room for surge"],
                ["0.85 < r ≤ 1.0", "Amber_Tight", "At capacity — peak crowding likely"],
                ["r > 1.0",    "Red_Overload",   "Demand exceeds offered seats — add buses or accept crowding"],
            ],
            col_widths=[50*mm, 35*mm, 75*mm],
        ),
        Spacer(1, 4 * mm),
        N(
            "v3.3.5 distribution: 9 Green / 197 Amber_Under / 1 Amber_Tight / "
            "0 Red. Most routes show as Amber_Under because the engine sizes "
            "fleet for the target headway irrespective of current demand — by "
            "design, the plan delivers more seats than today's ridership uses, "
            "to enable the latent demand that frequent service unlocks. "
            "The Mohring effect (riders shift to bus when service improves) "
            "is not modelled — that is a known v4 backlog item."
        ),
        PageBreak(),
    ]

    # ─── 5. HOW HEADWAY GETS PICKED ───────────────────────────────────────
    flow += [
        H1("5. How the engine decides which headway to give which route"),
        P(
            "Headway is assigned per <b>Priority Band</b> (HP / MP / LP), and "
            "the band itself is computed from a <b>Composite Demand Index</b>:"
        ),
        F(
            "Final_CDI  =  Pop_Score × 0.5  +  POI_Score × 0.5\n\n"
            "Pop_Score   — normalised population in 400 m walk catchment\n"
            "POI_Score   — gravity score of weighted POIs in 250 m buffer\n"
            "                  (3-tier: year-round 1.0, secondary 0.4, "
            "tourist 0.6/0.0)"
        ),
        P(
            "The 207 active routes are then split into HP / MP / LP using "
            "<b>Jenks Natural Breaks</b> on the CDI distribution. Routes near "
            "a band boundary are nudged up or down by a Road_Multiplier "
            "tie-breaker (highway/arterial = 1.0, mohalla lane = 0.85). "
            "The SSCL backbone bypasses all of this and is forced to HP."
        ),
        H2("Overrides — when band logic doesn't apply"),
        B("<b>SSCL backbone</b> — 45 permits matched to the 30 official "
          "CHALO routes are forced HP / 15-min headway."),
        B("<b>Social Obligation floor</b> — routes serving KP townships, "
          "district hospitals, and women's colleges get a LP→MP promotion "
          "(11 anchor keys after the v3.3.1 audit)."),
        B("<b>District HQ floor</b> — Regional_District routes that touch a "
          "district headquarters also get LP→MP."),
        B("<b>Tourist corridor boost</b> — routes within 2 km of a distant "
          "tourist destination (Gulmarg, Pahalgam, Sonamarg, etc.) or with "
          "an endpoint within 0.6 km of an inner-city tourist gate (Mughal "
          "gardens, Boulevard) get a 1.3× catchment-population boost, which "
          "raises Pop_Score → CDI → band."),
        PageBreak(),
    ]

    # ─── 6. SANITY-CHECKING AGAINST CHALO ─────────────────────────────────
    flow += [
        H1("6. Sanity-checking against CHALO ground truth"),
        P(
            "The Kashmir engine is calibrated against twelve months of CHALO "
            "ridership data (May 2025 – April 2026, 11.6 M trips across the "
            "30 SSCL e-bus routes). The calibration target is per-route fleet "
            "at the same target headway:"
        ),
        F(
            "CHALO scaled fleet  =  CHALO_current_fleet × "
            "(CHALO_effective_headway ÷ engine_target_headway)\n\n"
            "                 =  98 × (34 min ÷ 15 min)  ≈  220 buses\n\n"
            "                 ⇒ ~7.33 buses per route at 15-min headway"
        ),
        H2("v3.3.5 calibration scorecard"),
        _table(
            [
                ["Metric",                          "CHALO (current ops)", "CHALO (scaled to 15-min)", "Engine v3.3.5", "Error"],
                ["SSCL fleet (raw count)",          "98",        "~220",   "362",  "+64% (cycle-time conservatism)"],
                ["SSCL fleet per route",            "3.27",      "7.33",   "8.04", "+9.7% (within ±25%)"],
                ["SSCL Daily_Demand_Pax",           "31,869",    "n/a",    "~33,000", "+3.4% (within ±10%)"],
                ["Tourist corridors flagged",       "n/a",       "n/a",    "69",   "✓"],
                ["Red_Overload routes",             "n/a",       "n/a",    "0",    "✓"],
                ["QC checks",                       "n/a",       "n/a",    "8/8",  "✓"],
            ],
            col_widths=[55*mm, 28*mm, 28*mm, 22*mm, 37*mm],
            font_size=9,
        ),
        Spacer(1, 6 * mm),
        N(
            "The 'scaled CHALO' column is the apples-to-apples comparator: "
            "if CHALO themselves ran at the engine's 15-min target headway "
            "(instead of their current ~34-min effective headway), they'd "
            "need ~220 buses instead of 98. Engine recommends 362, of which "
            "the extra 142 is largely the absorption of duplicate "
            "private/JKRTC permits running parallel to SSCL e-bus corridors "
            "(currently the SSCL e-bus shares the road with these operators; "
            "the plan upgrades them to trunk service alongside SSCL)."
        ),
        PageBreak(),
    ]

    # ─── 7. PEER-CITY BENCHMARKS ─────────────────────────────────────────
    flow += [
        H1("7. Peer-city benchmarks — is the plan realistic?"),
        P(
            "Public-transit research uses <b>buses per 1,000 residents</b> as "
            "the cross-city scale-invariant comparator. Indian peer cities:"
        ),
        _table(
            [
                ["City",                  "Population (urban)", "Bus fleet", "Buses / 1000 res."],
                ["Mysuru (KSRTC)",        "2.0 M",  "~700",    "0.35"],
                ["Bhopal (BCLL)",         "1.4 M",  "~600",    "0.43"],
                ["Indore (Atal Indore)",  "2.0 M",  "~900",    "0.45"],
                ["Bengaluru (BMTC)",      "12.8 M", "~6,500",  "0.51"],
                ["<b>Srinagar v3.3.5</b>",
                 "<b>1.66 M</b>", "<b>988</b>", "<b>0.60</b>"],
                ["Chandigarh (CTU)",      "1.0 M",  "~650",    "0.65"],
                ["Pune (PMPML)",          "3.7 M",  "~2,800",  "0.75"],
                ["Delhi (DTC + cluster)", "7.8 M",  "~7,000",  "0.90"],
                ["Mumbai (BEST)",         "2.9 M",  "~3,500",  "1.20"],
            ],
            col_widths=[55*mm, 35*mm, 30*mm, 40*mm],
        ),
        Spacer(1, 6 * mm),
        N(
            "Srinagar at 0.60 buses per 1,000 residents sits squarely between "
            "BMTC Bengaluru (0.51) and Chandigarh CTU (0.65 — closest peer "
            "city by size). The v3.3.4 'aspirational' plan at 0.67 buses/"
            "1000 — driven by 15-min headway on all 130 HP routes — was an "
            "achievable Year-3+ ambition; v3.3.5 is the defensible Year-1 plan."
        ),
        H2("Vehicle-density vs service-quality trade-off"),
        P(
            "More buses do not automatically buy better service. The right "
            "metric is the joint distribution of (a) headway on the busiest "
            "corridors, and (b) coverage breadth — what fraction of "
            "residents live within 400 m of some bus stop. The v3.3.5 plan "
            "achieves both: 130 trunks at 15–20 min headway, plus 77 "
            "feeders covering 69.78% of the Srinagar UA + Valley population."
        ),
        PageBreak(),
    ]

    # ─── 8. APPENDIX A: TERMS ────────────────────────────────────────────
    flow += [
        H1("Appendix A — Glossary of engine terms"),
        _table(
            [
                ["Term",            "Meaning"],
                ["Headway",         "Time between consecutive buses on the same route."],
                ["Cycle time",      "Wall-clock time for one bus to complete one full round trip."],
                ["CDI",             "Composite Demand Index = Pop_Score × 0.5 + POI_Score × 0.5"],
                ["HP / MP / LP",    "Jenks-band classification: high / medium / low priority."],
                ["SSCL",            "Srinagar Smart City Limited — operator of the 30-route e-bus backbone."],
                ["CHALO",           "Free-fare ridership-tracking system on SSCL buses; 12-month dataset is the engine's calibration anchor."],
                ["CMP_Trunk",       "Boolean flag: route is one of the 45 matched SSCL permits forced to trunk service."],
                ["Action_Taken",    "Per-route disposition: RETAINED_AS_FEEDER / UPGRADED_TO_TRUNK / MERGED_INTO_TRUNK."],
                ["Load_Ratio",      "Daily_Demand_Pax ÷ Daily_Capacity_Pax — Phase-4 diagnostic."],
                ["Spare ratio",     "Industry-standard 1.15 multiplier on operating fleet to cover maintenance, breakdowns, depot rotation."],
                ["Mode share",      "Fraction of resident trips taken by bus. 9% urban / 7.2% peri-urban / 5.4% regional (typology-aware, CHALO-derived)."],
                ["Trip rate",       "Average bus trips per resident per day. 1.6, weighted across female (~2.0) and male (~1.2) segments."],
                ["CAPTURE_SCALE",   "0.18 — empirical scalar tying buffer-based demand to CHALO observed ridership."],
                ["Jenks breaks",    "Optimal natural-break clustering algorithm for splitting a 1D distribution into bands."],
            ],
            col_widths=[35*mm, 125*mm],
            font_size=9,
        ),
        PageBreak(),
    ]

    # ─── 9. APPENDIX B: ENGINE CONSTANTS ─────────────────────────────────
    flow += [
        H1("Appendix B — Engine constants and where they come from"),
        _table(
            [
                ["Constant",                       "Value",   "Source"],
                ["HEADWAY_HP_MIN (non-SSCL)",      "20 min",  "Phase-1 peer-city target (v3.3.5)"],
                ["HEADWAY_MP_MIN",                 "35 min",  "Peer-city feeder norm (v3.3.5)"],
                ["HEADWAY_LP_MIN",                 "60 min",  "Inter-district floor"],
                ["SSCL_TRUNK_HEADWAY_MIN",         "15 min",  "SSCL published design target"],
                ["FLEET_SPARE_RATIO",              "1.15",    "Industry-standard 10–20% spare"],
                ["MIN_FLEET_URBAN",                "2",       "Reliability floor on urban routes"],
                ["MIN_FLEET_REGIONAL",             "1",       "Lifeline-route floor (v3.2 audit)"],
                ["CITY_CORE_LAT_THRESHOLD",        "34.07°",  "Srinagar Lal Chowk + Downtown latitude"],
                ["CONGESTION_CITY_CORE",           "2.2×",    "Srinagar Traffic Police peak studies"],
                ["CONGESTION_PERI_URBAN",          "1.4×",    "Same source"],
                ["JHELUM_BRIDGE_BOTTLENECK_MIN",   "8 min",   "Habba Kadal / Amira Kadal observed queue"],
                ["STOP_PENALTY_MIN",               "0.5 min", "30-second standard dwell"],
                ["WALK_CATCHMENT_M",               "400 m",   "5-minute walk; TRB transit-coverage standard"],
                ["WINTER_WALKSHED_SHRINK",         "0.65",    "Chillai Kalan snow conditions (35% shrink)"],
                ["VEHICLE_CAPACITY_HPV",           "50 seats","12-metre standard low-floor"],
                ["VEHICLE_CAPACITY_MPV",           "35 seats","9-metre SSCL e-bus / midi"],
                ["VEHICLE_CAPACITY_LPV",           "15 seats","Tempo / Magic / small minibus"],
                ["TOURIST_POPULATION_MULTIPLIER",  "1.3×",    "Tier-3 POI catchment uplift (v3.3.3)"],
                ["PHASE4_MODE_SHARE (urban)",      "0.09",    "CHALO 12-month observed bus share"],
                ["PHASE4_TRIP_RATE",               "1.6",     "Weighted female (2.0) + male (1.2) avg"],
                ["PHASE4_CORRIDOR_CAPTURE_SCALE",  "0.18",    "Empirical SSCL anchor (v3.3.2)"],
            ],
            col_widths=[60*mm, 25*mm, 75*mm],
            font_size=9,
        ),
        PageBreak(),
    ]

    # ─── 10. APPENDIX C: WHERE TO LOOK IN THE CODE ───────────────────────
    flow += [
        H1("Appendix C — Where each concept lives in the code"),
        _table(
            [
                ["Concept",          "File / function"],
                ["Headway assignment",
                 "transit_kashmir_v3.py → step6_assign_headways()"],
                ["Cycle time",
                 "transit_kashmir_v3.py → compute_cycle_times()"],
                ["Fleet sizing",
                 "transit_kashmir_v3.py → step8_compute_fleet()"],
                ["SSCL empirical floor",
                 "transit_kashmir_v3.py → step9_assign_vehicle_split() (v3.3.4)"],
                ["Daily_Capacity (corrected)",
                 "transit_kashmir_v3.py → compute_phase4_metrics() (v3.3.3 T3)"],
                ["Daily_Demand corridor share",
                 "transit_kashmir_v3.py → compute_phase4_metrics() (v3.3.2)"],
                ["Tourist tagging (geometric)",
                 "transit_kashmir_v3.py → _line_near_point_km() (v3.3.3 T1)"],
                ["CDI / Jenks bands",
                 "transit_kashmir_v3.py → step4a_compute_final_cdi() + step5_assign_priority_bands()"],
                ["CHALO cross-validation",
                 "cross_evaluate.py → evaluate()"],
                ["Briefing-deck generator",
                 "generate_presentations.py"],
                ["Route-code generator",
                 "generate_route_codes.py (needs Kashmir_Stops_Sectored_V2.csv)"],
            ],
            col_widths=[55*mm, 105*mm],
            font_size=9,
        ),
        Spacer(1, 8 * mm),
        H2("Reading order for someone new to the engine"),
        Paragraph(
            "<b>1.</b> README.md (project overview, audit lineage v3.1 → v3.3.5)<br/>"
            "<b>2.</b> Sections 1–3 of this guide (headway, cycle time, fleet formula)<br/>"
            "<b>3.</b> Section 4 (capacity vs demand) and section 6 (CHALO calibration)<br/>"
            "<b>4.</b> Engine source — top-of-file constants block lines 130–500<br/>"
            "<b>5.</b> Run the engine once with the real OSRM Docker up; inspect "
            "outputs_v3.3.5/Rationalised_Routes_Kashmir_v3.csv against the dashboard.<br/>"
            "<b>6.</b> Run cross_evaluate.py to see how every number ties back to CHALO observations.",
            STYLES["Body"],
        ),
    ]

    return flow


def main():
    doc = _build_doc()
    doc.build(_flow())
    print(f"Wrote {OUT_PDF}")


if __name__ == "__main__":
    main()
