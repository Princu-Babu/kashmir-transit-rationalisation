"""
generate_outputs_guide_pdf.py

Produces Kashmir_Transit_Outputs_Explained.pdf — a reader's guide to every
file the engine emits. Tells the RTO / IAS reviewer:
  • what each output file is,
  • who should open it,
  • which sheet / column to focus on,
  • how it ties back to the plan numbers in the briefing decks.

Companion to Kashmir_Transit_Headway_Fleet_Fundamentals.pdf (which covers
the maths). This one covers the *artefacts*.
"""
from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, Table,
    TableStyle, PageBreak,
)


OUT_PDF = Path("E:/kash/Kashmir_Transit_Outputs_Explained.pdf")


# ─── Styles ───────────────────────────────────────────────────────────────────
def _styles():
    s = getSampleStyleSheet()
    s.add(ParagraphStyle("TitleBig", parent=s["Title"], fontSize=24,
                          leading=28, spaceAfter=6,
                          textColor=colors.HexColor("#1A237E")))
    s.add(ParagraphStyle("Subtitle", parent=s["Normal"], fontSize=12,
                          leading=16, textColor=colors.HexColor("#555"),
                          spaceAfter=18))
    s.add(ParagraphStyle("H1", parent=s["Heading1"], fontSize=18, leading=22,
                          spaceBefore=14, spaceAfter=8,
                          textColor=colors.HexColor("#1A237E")))
    s.add(ParagraphStyle("H2", parent=s["Heading2"], fontSize=14, leading=18,
                          spaceBefore=10, spaceAfter=6,
                          textColor=colors.HexColor("#00695C")))
    s.add(ParagraphStyle("Body", parent=s["BodyText"], fontSize=11,
                          leading=16, spaceAfter=8, alignment=TA_JUSTIFY))
    s.add(ParagraphStyle("Note", parent=s["BodyText"], fontSize=10,
                          leading=14, textColor=colors.HexColor("#666"),
                          spaceAfter=8, fontName="Helvetica-Oblique"))
    s.add(ParagraphStyle("Cap", parent=s["BodyText"], fontSize=9,
                          leading=12, textColor=colors.HexColor("#666"),
                          alignment=TA_CENTER, spaceAfter=12))
    s.add(ParagraphStyle("Bullet2", parent=s["BodyText"], fontSize=11,
                          leading=15, leftIndent=14, bulletIndent=2,
                          spaceAfter=3))
    return s


STYLES = _styles()


def H1(t):   return Paragraph(t, STYLES["H1"])
def H2(t):   return Paragraph(t, STYLES["H2"])
def P(t):    return Paragraph(t, STYLES["Body"])
def B(t):    return Paragraph(t, STYLES["Bullet2"], bulletText="•")
def N(t):    return Paragraph(t, STYLES["Note"])
def C(t):    return Paragraph(t, STYLES["Cap"])


def _table(rows, col_widths=None, header_bg="#1A237E", font_size=10):
    tbl = Table(rows, colWidths=col_widths, hAlign="LEFT")
    ts = [
        ("BACKGROUND",    (0, 0), (-1, 0), colors.HexColor(header_bg)),
        ("TEXTCOLOR",     (0, 0), (-1, 0), colors.white),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), font_size),
        ("ALIGN",         (0, 0), (-1, 0), "CENTER"),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("BOX",           (0, 0), (-1, -1), 0.5, colors.HexColor("#CCC")),
        ("INNERGRID",     (0, 0), (-1, -1), 0.25, colors.HexColor("#DDD")),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
    ]
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
    canvas.drawString(20 * mm, 12 * mm, "Kashmir Engine — Outputs Explained")
    canvas.drawRightString(190 * mm, 12 * mm, f"page {doc.page}")
    canvas.restoreState()


def _build_doc():
    doc = BaseDocTemplate(
        str(OUT_PDF), pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=20 * mm, bottomMargin=20 * mm,
        title="Kashmir Transit — Outputs Explained",
        author="Kashmir Valley Transit Rationalisation Engine",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin,
                  doc.width, doc.height, id="frame")
    doc.addPageTemplates([PageTemplate(id="default", frames=[frame],
                                        onPage=_on_page)])
    return doc


# ─── Content ──────────────────────────────────────────────────────────────────
def _flow():
    flow = []

    # Cover
    flow += [
        Spacer(1, 22 * mm),
        Paragraph("Kashmir Valley Transit", STYLES["TitleBig"]),
        Paragraph("Outputs Explained — Reader's Guide", STYLES["TitleBig"]),
        Spacer(1, 6 * mm),
        Paragraph(
            "Every artefact the engine emits, who should open it, which "
            "section to focus on, and how it ties back to the briefing-deck "
            "numbers. Companion to Kashmir_Transit_Headway_Fleet_Fundamentals.pdf "
            "(which covers the maths).",
            STYLES["Subtitle"]),
        Spacer(1, 60 * mm),
        Paragraph("Engine v3.3.5  ·  May 2026", STYLES["Cap"]),
        Paragraph("For Principal Secretary, RTOs, and the operations team",
                  STYLES["Cap"]),
        PageBreak(),
    ]

    # ── 1. AT-A-GLANCE MAP ───────────────────────────────────────────────
    flow += [
        H1("1. The artefact map"),
        P(
            "Every engine run produces the same eight artefacts in the "
            "<b>outputs_v3.3.5/</b> directory. Different audiences open different "
            "files; pick the row that matches you."
        ),
        _table(
            [
                ["Artefact", "File", "Best read by"],
                ["RTO Master Workbook",
                 "Kashmir_Route_Frequency_Plan_v3.3.5_RTO.xlsx",
                 "RTOs, Principal Secretary, IAS reviewers"],
                ["Legacy 4-sheet Workbook",
                 "Kashmir_Route_Frequency_Plan_v3.xlsx",
                 "Engineering team, internal review"],
                ["Master Transit Map (HTML)",
                 "Master_Transit_Map_Kashmir_v3.html",
                 "Anyone wanting an interactive overview"],
                ["Per-route maps",
                 "route_maps_kashmir/&lt;ID&gt;.html  (one per active route)",
                 "RTO drilling into a single corridor"],
                ["Operational CSV",
                 "Rationalised_Routes_Kashmir_v3.csv",
                 "Data team, dashboard, statisticians"],
                ["GeoJSON network",
                 "Rationalised_Routes_Kashmir_v3.geojson",
                 "GIS team (load into QGIS / ArcGIS)"],
                ["Rationalisation Log",
                 "Rationalisation_Log_Kashmir_v3.csv",
                 "Anyone questioning why a route was merged / upgraded"],
                ["Passenger Impact",
                 "Passenger_Impact_Kashmir_v3.csv",
                 "Communications team, public-facing summaries"],
                ["Pipeline log",
                 "engine_run_v3.3.5.log",
                 "Debugging only — QC trace from the engine"],
            ],
            col_widths=[42*mm, 70*mm, 60*mm],
            font_size=9,
        ),
        PageBreak(),
    ]

    # ── 2. RTO MASTER WORKBOOK ───────────────────────────────────────────
    flow += [
        H1("2. The RTO Master Workbook — sheet by sheet"),
        P(
            "<b>Kashmir_Route_Frequency_Plan_v3.3.5_RTO.xlsx</b> is the "
            "primary deliverable for sign-off. Nine sheets, each with a "
            "specific reader."
        ),
        _table(
            [
                ["Sheet", "Purpose", "Who reads it", "Focus on"],
                ["1. Cover & Sign-off",
                 "Title block, 8 KPI tiles, legend, signature lines.",
                 "Principal Secretary",
                 "KPI tiles + sign-off block at bottom."],
                ["2. Network Summary",
                 "Network composition, fleet composition, headway distribution.",
                 "RTO, IAS",
                 "Headway distribution table + total reconciliation."],
                ["3. Route-Level Plan",
                 "All 342 routes with action, headway, fleet, load flag, map link.",
                 "RTOs (workhorse sheet)",
                 "Filter on Action_Taken or Priority_Band. Click Map_Link cells to open the corridor's HTML map."],
                ["4. Operator Absorption",
                 "Permits merged into trunks, broken down by operator class with starting buyback estimates.",
                 "Finance, Welfare Assn liaison",
                 "₹12.96 Cr starting buyback ask (TOTAL row, last column)."],
                ["5. Trunk Detail",
                 "All 50 UPGRADED_TO_TRUNK + HP routes only.",
                 "Backbone reviewers",
                 "Fleet vs headway vs SSCL_ID — verify SSCL coverage."],
                ["6. Social Obligation",
                 "All Social_Flag routes (KP townships, hospitals, women's colleges).",
                 "Political clearance reviewers",
                 "Verify nothing critical demoted to LP."],
                ["7. Tourist & Seasonal",
                 "Tourist_Corridor + Seasonal_Operability routes.",
                 "JKTDC, JKRTC seasonal planners",
                 "Winter-suspended list (Mughal Road, Sinthan, Z-Morh)."],
                ["8. Calibration & Sources",
                 "Headway targets, CHALO calibration scorecard, data sources.",
                 "Anyone questioning the numbers",
                 "Mode-share assumption + capture-scale derivation."],
                ["9. Limitations",
                 "Known gaps (Phase-2 backlog).",
                 "IAS — must see before sign-off",
                 "All bullets — these are caveats that need to ride along with the plan."],
            ],
            col_widths=[35*mm, 50*mm, 38*mm, 45*mm],
            font_size=9,
        ),
        Spacer(1, 6*mm),
        H2("How to read Sheet 3 (Route-Level Plan) — column groups"),
        P(
            "The 28 columns are organised into five visual groups by colour:"
        ),
        _table(
            [
                ["Group (column-header colour)", "What it tells you"],
                ["Identity (navy)",
                 "Route_Code, Old_Route_ID, New_Route_ID, Route_Name, Action_Taken, Priority_Band. "
                 "Frozen pane — always visible while scrolling."],
                ["Service (teal)",
                 "Route_KM, Cycle_Time_Min, Headway_Min, Fleet_Required, HPV/MPV/LPV counts, "
                 "Bus_Type_Rec, Service_Hours. The 'what to operate' block."],
                ["Demand (purple)",
                 "Population_Served, Daily_Demand_Pax, Daily_Capacity_Pax, Load_Flag, "
                 "Subsidy_Risk_Flag, Social_Flag, Tourist_Corridor. The 'who uses it' block."],
                ["Impact (red)",
                 "Displaced_Operator_Class, Num_Permits_Affected, Recommended_Action, "
                 "RTO_Remarks (blank for hand-fill). Operator-side consequences."],
                ["Audit (amber)",
                 "Final_CDI, Map_Link. Why this route got its band, plus a hyperlink to its individual map."],
            ],
            col_widths=[55*mm, 115*mm],
            font_size=9,
        ),
        Spacer(1, 4*mm),
        N(
            "Sheet 3 is set up for landscape A3 printing. Headers repeat on "
            "each page, auto-filter is on, and the identity block (cols A–F) "
            "freezes when you scroll right."
        ),
        PageBreak(),
    ]

    # ── 3. ROUTE-LEVEL CSV COLUMN REFERENCE ──────────────────────────────
    flow += [
        H1("3. Rationalised_Routes_Kashmir_v3.csv — column by column"),
        P(
            "The single most useful file for anyone working with the data "
            "downstream. Every column the engine writes; every column the "
            "dashboard reads."
        ),
        _table(
            [
                ["Column", "Meaning"],
                ["Route_Code",          "12-char tehsil+sector+stop code — or TMP-K#### placeholder while the stops-master is pending"],
                ["Route_ID",            "Source permit ID from existing-routes.csv (R0001…R0342)"],
                ["Route_Name",          "ORIGIN ↔ DESTINATION (engine reconstructs from Origin/Destination when blank)"],
                ["Action_Taken",        "UPGRADED_TO_TRUNK · RETAINED_AS_FEEDER · MERGED_INTO_TRUNK"],
                ["New_Route_ID",        "TRK-NNN for trunks, FDR-NNN for feeders, blank for merged"],
                ["Displaced_Operator_Class", "Private Minibus / LPV / Tempo / HPV Bus / JKRTC. Only for MERGED rows."],
                ["Route_KM",            "Route length from OSRM (or circuity fallback)"],
                ["Route_Type",          "Urban · Peri_Urban · Regional_District (typology)"],
                ["OSRM_Duration_S",     "Free-flow OSRM travel time in seconds, no congestion"],
                ["Cycle_Time_Min",      "Round-trip cycle including congestion, dwells, junctions, bridge bottleneck"],
                ["Congestion_Zone",     "City_Core · Peri_Urban · Highway (drives the congestion multiplier)"],
                ["N_Stops_Estimated",   "Virtual stops counted at 500m spacing"],
                ["Stop_Penalty_Min",    "Total dwell penalty on the route"],
                ["Sharp_Turns",         "Junction count from OSRM geometry (each adds 30s)"],
                ["Junction_Penalty_Min","Total junction-time penalty"],
                ["Pop_Score",           "Normalised catchment population (0–1)"],
                ["POI_Score",           "Normalised POI gravity score (0–1)"],
                ["Road_Multiplier",     "Tie-breaker for routes near a Jenks band boundary"],
                ["Final_CDI",           "= Pop_Score × 0.5 + POI_Score × 0.5  → input to Jenks bands"],
                ["Social_Flag",         "True for KP townships / hospitals / women's colleges (LP→MP floor)"],
                ["Priority_Band",       "HP / MP / LP (high / medium / low)"],
                ["Headway_Min",         "Recommended target headway"],
                ["Fleet_Required",      "Recommended bus count = CEIL(Cycle/Headway × 1.15)"],
                ["HPV_Count",           "12-metre buses on this route"],
                ["MPV_Count",           "9-metre buses on this route"],
                ["LPV_Count",           "Tempo / minibus on this route (feeder LPV-category only)"],
                ["CMP_Trunk",           "True for the 45 permits matched to the 30 SSCL CHALO routes"],
                ["CMP_Route_ID",        "Matched SSCL ID (SSCL-01…SSCL-30) for CMP_Trunk routes"],
                ["Population_Served",   "Apportioned (dedup-residual) catchment count for the route"],
                ["Population_Served_Raw","Pre-apportionment buffer count (used in Phase-4 demand)"],
                ["Corridor_Competitors","# overlapping route buffers in the corridor"],
                ["HV_POI_Count",        "High-value POI count in the route's 250m buffer"],
                ["Overlap_Metric",      "Mean overlap with peer routes (0–1)"],
                ["Geo_Source",          "OSRM · OSRM+JhelumBridge · Circuity · Circuity-River"],
                ["Tourist_Corridor",    "True if route passes near a tourist zone (geom or endpoint test)"],
                ["Seasonal_Operability","Year_Round · Seasonal · Winter_Suspended"],
                ["District_HQ_Floor",   "True if route touches a district HQ (LP→MP floor)"],
                ["SSCL_CDI_Conflict",   "True for non-SSCL routes with CDI ≥ worst SSCL trunk + 0.2 (planner review)"],
                ["Daily_Trips",         "Service-day one-way trips offered at the target headway"],
                ["Daily_KM",            "Service-day scheduled KM = Daily_Trips × Route_KM"],
                ["Daily_Capacity_Pax",  "Daily seats offered = Fleet × Capacity × (960 / Cycle_Time_Min)"],
                ["Daily_Demand_Pax",    "Estimated daily riders (Phase-4 corridor-share model)"],
                ["Load_Ratio",          "Daily_Demand_Pax ÷ Daily_Capacity_Pax"],
                ["Load_Flag",           "Diagnostic: Green / Amber_Under / Amber_Tight / Red_Overload / Red_NoCapacity"],
                ["Pax_Journey_Time_Min","Estimated total passenger journey time (access + wait + ride)"],
                ["Journey_Time_Flag",   "True if Pax_Journey_Time exceeds the 45-min comfort threshold"],
                ["Daily_Revenue_INR",   "Daily fare-recovery estimate at ₹10/trip"],
                ["Daily_Op_Cost_INR",   "Daily operating cost at ₹65/km"],
                ["Viability_Ratio",     "Daily_Revenue ÷ Daily_Op_Cost (1.0 = self-funding)"],
                ["Subsidy_Risk_Flag",   "True if Viability_Ratio < 0.60 AND not Social_Flag"],
                ["Emissions_GCO2_Daily","Daily emissions estimate (lower for SSCL e-bus routes)"],
                ["Equity_Score",        "Composite equity score normalised across the network"],
                ["Map_File",            "Relative path to the route's individual HTML map"],
            ],
            col_widths=[55*mm, 115*mm],
            font_size=8.5,
        ),
        PageBreak(),
    ]

    # ── 4. THE OTHER FILES ───────────────────────────────────────────────
    flow += [
        H1("4. Master & per-route HTML maps"),
        P(
            "<b>Master_Transit_Map_Kashmir_v3.html</b> is a Folium-rendered "
            "interactive map. Opens in any modern browser — no GIS skills "
            "required. Use it for:"
        ),
        B("<b>Overview presentations</b> — toggle the trunk / feeder / "
          "SSCL / regional layers in the right sidebar."),
        B("<b>Selecting a route</b> — click any line; the popup shows the "
          "route's headway, fleet, KPIs and a link to the individual map."),
        B("<b>POI overlay</b> — turn on the POI layer to see why a route "
          "scored highly on its POI_Score."),
        B("<b>Winter / summer comparison</b> — re-run the engine with "
          "WINTER_SCENARIO=True to generate the winter version of the map."),
        N(
            "Map tiles are OpenStreetMap / CartoDB. They do not represent "
            "the official J&K political boundary — a disclaimer is shown "
            "in the map's footer."
        ),
        Spacer(1, 4*mm),
        H2("Per-route maps under route_maps_kashmir/"),
        P(
            "One HTML file per active route, named after its New_Route_ID "
            "(e.g. <b>TRK-001.html</b>, <b>FDR-047.html</b>, <b>SSCL-15.html</b>). "
            "Each shows just that route's geometry, its catchment polygon, "
            "the POIs it touches, and a popup with all key KPIs. Linked from "
            "the Master map and from the RTO workbook's Sheet 3."
        ),
        Spacer(1, 4*mm),
        H1("5. GeoJSON for GIS teams"),
        P(
            "<b>Rationalised_Routes_Kashmir_v3.geojson</b> contains the 207 "
            "active routes as LineString features. Load into QGIS or ArcGIS "
            "for spatial joins, road-segment analysis, or overlay against "
            "your own datasets (ward boundaries, depot locations, accident "
            "hotspots, etc.). Every property field is the same as the CSV "
            "column."
        ),
        Spacer(1, 4*mm),
        H1("6. Rationalisation Log — defending decisions"),
        P(
            "<b>Rationalisation_Log_Kashmir_v3.csv</b> is identical to the "
            "main routes CSV except for one extra column at the end: "
            "<b>Reasoning_String</b>. This is the human-readable explanation "
            "of why each route got its band, action, fleet, and headway."
        ),
        P(
            "Use this when an operator or RTO official questions a specific "
            "decision. Example reasoning string for a merged route:"
        ),
        _table(
            [["MERGED_INTO_TRUNK · TRK-047 absorbs this permit "
              "(overlap 0.78 with parallel trunk; CDI 0.51 vs neighbour 0.78). "
              "Distinct catchment: 262 residents over 7.5 km. Social_Flag: True."]],
            col_widths=[170*mm], header_bg="#FAFAFA", font_size=9,
        ),
        PageBreak(),
    ]

    # ── 5. PASSENGER IMPACT + LOG ────────────────────────────────────────
    flow += [
        H1("7. Passenger Impact CSV — the public-facing summary"),
        P(
            "<b>Passenger_Impact_Kashmir_v3.csv</b> is the simplified, "
            "passenger-facing view. Only active routes, only the columns "
            "a citizen reading a notice would care about."
        ),
        _table(
            [
                ["Column", "What it tells the passenger"],
                ["New_Route_ID",      "The route number you'll see on the bus"],
                ["Route_Name",        "Origin ↔ Destination"],
                ["Action_Taken",      "Trunk / Feeder / Merged"],
                ["Route_Type",        "Urban / Peri-urban / Regional"],
                ["Priority_Band",     "HP / MP / LP"],
                ["Headway_Min",       "Wait time between buses"],
                ["Fleet_Required",    "Number of buses on this route"],
                ["HPV_Count",         "Large buses"],
                ["MPV_Count",         "Medium buses"],
                ["LPV_Count",         "Small minibuses / tempos"],
                ["CMP_Trunk",         "Yes/No — is this an SSCL e-bus route?"],
                ["Population_Served", "Residents in the 400m walking buffer"],
                ["Social_Flag",       "Yes/No — is this a protected lifeline?"],
            ],
            col_widths=[55*mm, 115*mm], font_size=9,
        ),
        Spacer(1, 4*mm),
        N(
            "Use this CSV as the source for citizen-facing materials: "
            "notice-board posters, app schedules, the website route list, "
            "and the bus-stop printed timetable."
        ),
        Spacer(1, 4*mm),
        H1("8. The pipeline log — when something looks off"),
        P(
            "<b>engine_run_v3.3.5.log</b> contains the full step-by-step "
            "trace of what the engine did. Don't open it day-to-day — "
            "it's diagnostic. Open it when:"
        ),
        B("A QC check fails — the log will name the check and the offending routes."),
        B("Calibration drifts more than ±15% from CHALO — check the population fallback and capture-scale lines."),
        B("Outputs don't match what the dashboard shows — the log is the source of truth, the CSV is the export."),
        Spacer(1, 4*mm),
        H2("Key log lines and what they mean"),
        _table(
            [
                ["Log line",                          "Means"],
                ["Tourist boost applied: 1.30x on N routes",
                 "Population multiplier applied to N tourist routes"],
                ["Apportioned Population_Served. New naive sum: X",
                 "Population deduplication ran; X is the sum after sharing"],
                ["Priority bands — HP: N · MP: N · LP: N",
                 "Jenks classification result"],
                ["Load_Flag: Green=N Amber_Under=N Amber_Tight=N Red_Overload=N",
                 "Phase-4 diagnostic spread"],
                ["✓ ALL QC CHECKS PASSED — workbook ready for export",
                 "Engine cleared all 8 quality checks — outputs are safe to ship"],
                ["✗ rasterstats not importable / WorldPop raster not found",
                 "Population source missing — engine will refuse to ship unless KASHMIR_ALLOW_DUMMY_POP=1"],
            ],
            col_widths=[100*mm, 70*mm], font_size=9,
        ),
        PageBreak(),
    ]

    # ── 6. CROSS-REFERENCE ───────────────────────────────────────────────
    flow += [
        H1("9. Tying outputs back to the briefing decks"),
        P(
            "Every number on every slide of the briefing decks traces back "
            "to one of these files. Quick cross-reference for an IAS "
            "reviewer asking 'where does that number come from?'"
        ),
        _table(
            [
                ["Slide / number",                        "Source"],
                ["207 active routes",
                 "Routes CSV — COUNT WHERE Action_Taken ≠ MERGED_INTO_TRUNK"],
                ["988 total fleet (138/730/120)",
                 "Routes CSV — SUM(Fleet_Required) on active rows; HPV+MPV+LPV cols"],
                ["1,158,399 residents covered (69.78%)",
                 "engine_run log line 'Deduplicated network population'"],
                ["45 SSCL trunks / 30 matched",
                 "Routes CSV — COUNT WHERE CMP_Trunk=True"],
                ["69 tourist corridors",
                 "Routes CSV — COUNT WHERE Tourist_Corridor=True"],
                ["12.96 Cr buyback ask",
                 "RTO Workbook · Sheet 4 · TOTAL row, F column (SUM formula)"],
                ["+9.7% per-route calibration",
                 "cross_eval_v3.3.5.log — objective section"],
                ["8/8 QC checks",
                 "engine_run log — '✓ ALL QC CHECKS PASSED' line"],
                ["0 Red_Overload routes",
                 "Routes CSV — COUNT WHERE Load_Flag='Red_Overload'"],
            ],
            col_widths=[60*mm, 115*mm], font_size=9,
        ),
        Spacer(1, 8*mm),
        H2("Reading order for a brand-new reviewer"),
        Paragraph(
            "<b>1.</b> Open the diagrammatic pitch deck — Kashmir_Transit_Diagrammatic_Pitch.pptx.<br/>"
            "<b>2.</b> Open the RTO Workbook · Sheet 1 (Cover) for the headline numbers.<br/>"
            "<b>3.</b> Open the Master HTML map and click 5–10 random routes to feel the geography.<br/>"
            "<b>4.</b> If you want to defend a number — find it here in this guide and follow the trace.<br/>"
            "<b>5.</b> If the maths bothers you — open Kashmir_Transit_Headway_Fleet_Fundamentals.pdf instead. "
            "That covers the formulas; this guide covers the artefacts.",
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
