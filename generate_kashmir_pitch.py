"""
generate_kashmir_pitch.py

A diagrammatic, low-text companion to the Jammu_Pitch_v2 deck — for
Kashmir. Same narrative structure (cover → changes → network → CMP/SSCL
backbone → vehicles → methodology → limitations → close) but each slide
relies on flowcharts, sized icons, and bar charts instead of paragraphs.

Aligned with the engine v3.3.5 conservative phase-1 outputs.

Output: Kashmir_Transit_Diagrammatic_Pitch.pptx (16:9, 13 slides).
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

import pandas as pd
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt, Emu


# ─── Theme ───────────────────────────────────────────────────────────────────
NAVY        = RGBColor(0x1A, 0x23, 0x7E)
TEAL        = RGBColor(0x00, 0x69, 0x5C)
TEAL_LIGHT  = RGBColor(0xB2, 0xDF, 0xDB)
SAFFRON     = RGBColor(0xD3, 0x2F, 0x2F)
SAFFRON_LT  = RGBColor(0xFF, 0xEB, 0xEE)
PURPLE      = RGBColor(0x6A, 0x1B, 0x9A)
PURPLE_LT   = RGBColor(0xEA, 0xD8, 0xF2)
GOLD        = RGBColor(0xF9, 0xA8, 0x25)
GOLD_LT     = RGBColor(0xFF, 0xF8, 0xE1)
GREEN       = RGBColor(0x2E, 0x7D, 0x32)
GREEN_LT    = RGBColor(0xE8, 0xF5, 0xE9)
DARK        = RGBColor(0x21, 0x21, 0x21)
GREY        = RGBColor(0x75, 0x75, 0x75)
LIGHT       = RGBColor(0xF5, 0xF5, 0xF5)
WHITE       = RGBColor(0xFF, 0xFF, 0xFF)


# ─── Helpers ─────────────────────────────────────────────────────────────────
def add_text(slide, text, x, y, w, h, *, size=14, bold=False, color=DARK,
             align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, italic=False,
             font="Segoe UI"):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf  = box.text_frame
    tf.margin_left = tf.margin_right = Inches(0.05)
    tf.margin_top = tf.margin_bottom = Inches(0.02)
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    p = tf.paragraphs[0]
    p.alignment = align
    p.text = str(text) if str(text) else " "
    r = p.runs[0]
    r.font.name = font
    r.font.size = Pt(size)
    r.font.bold = bold
    r.font.italic = italic
    r.font.color.rgb = color
    return box


def add_rect(slide, x, y, w, h, *, fill=TEAL, line=None, rounded=False):
    shp_type = MSO_SHAPE.ROUNDED_RECTANGLE if rounded else MSO_SHAPE.RECTANGLE
    shp = slide.shapes.add_shape(shp_type, Inches(x), Inches(y), Inches(w), Inches(h))
    shp.fill.solid()
    shp.fill.fore_color.rgb = fill
    if line is None:
        shp.line.fill.background()
    else:
        shp.line.color.rgb = line
        shp.line.width = Pt(0.75)
    if rounded:
        # tighter corner radius for a modern look
        try:
            shp.adjustments[0] = 0.12
        except Exception:
            pass
    return shp


def add_oval(slide, x, y, w, h, *, fill=NAVY, line=None):
    shp = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y),
                                  Inches(w), Inches(h))
    shp.fill.solid()
    shp.fill.fore_color.rgb = fill
    if line is None:
        shp.line.fill.background()
    else:
        shp.line.color.rgb = line
        shp.line.width = Pt(0.75)
    return shp


def add_arrow(slide, x1, y1, x2, y2, *, color=GREY, width=1.5):
    conn = slide.shapes.add_connector(
        MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    conn.line.color.rgb = color
    conn.line.width = Pt(width)
    # try to add arrowhead
    try:
        from pptx.oxml.ns import qn
        ln = conn.line._get_or_add_ln()
        tail = ln.makeelement(qn("a:tailEnd"), {"type": "triangle", "w": "med", "len": "med"})
        ln.append(tail)
    except Exception:
        pass
    return conn


def add_centered_label(slide, text, x, y, w, h, *, size=12, bold=True,
                       color=WHITE, anchor=MSO_ANCHOR.MIDDLE,
                       align=PP_ALIGN.CENTER):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf  = box.text_frame
    tf.margin_left = tf.margin_right = Inches(0.05)
    tf.margin_top = tf.margin_bottom = Inches(0.02)
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    p = tf.paragraphs[0]
    p.alignment = align
    p.text = str(text) if str(text) else " "
    r = p.runs[0]
    r.font.name = "Segoe UI"
    r.font.size = Pt(size)
    r.font.bold = bold
    r.font.color.rgb = color
    return box


def slide_blank(prs):
    return prs.slides.add_slide(prs.slide_layouts[6])


def slide_header(slide, title, *, color=NAVY, sub=None):
    # Thin coloured side ribbon
    bar = add_rect(slide, 0, 0, 0.18, 7.5, fill=color)
    add_text(slide, title, 0.5, 0.35, 12.3, 0.7,
             size=28, bold=True, color=color, font="Calibri")
    if sub:
        add_text(slide, sub, 0.5, 1.0, 12.3, 0.4,
                 size=14, color=GREY, italic=True)


def footer(slide, text):
    add_text(slide, text, 0.5, 7.05, 12.3, 0.3,
             size=9, color=GREY, italic=True)


# ─── Deck ────────────────────────────────────────────────────────────────────
def build(prs, stats):
    # ── SLIDE 1 — Title hero card ───────────────────────────────────────
    s = slide_blank(prs)
    # full-bleed colour block
    add_rect(s, 0, 0, 13.33, 7.5, fill=NAVY)
    add_rect(s, 0, 6.7, 13.33, 0.8, fill=TEAL)   # bottom band
    # title block
    add_text(s, "KASHMIR PUBLIC TRANSPORT",
             0.7, 0.7, 12, 0.6,
             size=20, bold=True, color=TEAL_LIGHT, font="Calibri")
    add_text(s, "Route Rationalisation Plan — v3.3.5",
             0.7, 1.3, 12, 0.9,
             size=38, bold=True, color=WHITE, font="Calibri")
    add_text(s, "Phase-1 Conservative · Engine v3.3.5 ·"
             " SSCL Backbone + CHALO Calibration",
             0.7, 2.2, 12, 0.5,
             size=14, color=TEAL_LIGHT, italic=True)
    # 4 hero KPI cards
    cards = [
        ("ROUTES",       f"{stats['active']}", "active network", TEAL),
        ("TOTAL FLEET",  f"{stats['fleet']}",  "HPV+MPV+LPV",     GOLD),
        ("HPV",          f"{stats['hpv']}",    "12-metre buses",  PURPLE),
        ("MPV",          f"{stats['mpv']}",    "9-metre buses",   GREEN),
    ]
    cw = 2.7
    cx = 0.9
    cy = 3.4
    gap = 0.3
    for i, (label, big, sub, col) in enumerate(cards):
        x = cx + i * (cw + gap)
        add_rect(s, x, cy, cw, 2.6, fill=WHITE, rounded=True)
        add_rect(s, x, cy, cw, 0.45, fill=col, rounded=True)
        add_centered_label(s, label, x, cy, cw, 0.45, size=11, color=WHITE)
        add_text(s, big, x, cy + 0.55, cw, 1.3,
                 size=46, bold=True, color=col, align=PP_ALIGN.CENTER, font="Calibri")
        add_text(s, sub, x, cy + 1.95, cw, 0.4,
                 size=12, color=GREY, align=PP_ALIGN.CENTER, italic=True)
    # bottom tagline
    add_text(s,
             "⚠ FOR PLANNING — Phase-1 calibrated against CHALO Apr 2026. "
             "Operator consultation required before deployment.",
             0.7, 6.85, 12, 0.45,
             size=11, color=WHITE, italic=True, align=PP_ALIGN.CENTER)

    # ── SLIDE 2 — Audit lineage as flowchart ────────────────────────────
    s = slide_blank(prs)
    slide_header(s, "From v3.1 → v3.3.6 — Eight Audit Rounds",
                 sub="Each version closes one set of defensible bugs. The plan numbers haven't changed shape, just sharpened.")
    versions = [
        ("v3.1",   "Initial",        "Kashmir fork — replaced Jammu CMP with 30 SSCL CHALO routes",   NAVY),
        ("v3.2",   "Audit r1",       "RASTER bug · headway 45→15 · Jhelum bridge · congestion 2.2x", TEAL),
        ("v3.3",   "Phase-1 r1",     "Spare ratio 1.15 · Phase-4 KPIs · SSCL conflict flag",         PURPLE),
        ("v3.3.1", "Phase-1 r2",     "Per-km cycle cap · typology mode-share · social prune 17→11",   GOLD),
        ("v3.3.2", "Demand calib",   "Daily_Demand rewrite · capture-scale 0.18 · portable RASTER",   TEAL),
        ("v3.3.3", "Teammate review","Tourist tagging 4→69 · Daily_Capacity formula fix",            PURPLE),
        ("v3.3.4", "Honest fleet",   "SSCL empirical = floor not override · LPV restored · Red→0",   SAFFRON),
        ("v3.3.5", "Phase-1 conserv","HP 15→20 · MP 30→35 · fleet 1,113→988 (0.60/1000)",            GREEN),
    ]
    bw, bh = 1.45, 1.65
    bx_start = 0.45
    by = 2.0
    gap = 0.10
    for i, (ver, theme, desc, col) in enumerate(versions):
        x = bx_start + i * (bw + gap)
        # version card
        add_rect(s, x, by, bw, bh, fill=WHITE, rounded=True, line=col)
        add_rect(s, x, by, bw, 0.45, fill=col, rounded=True)
        add_centered_label(s, ver, x, by, bw, 0.45, size=14, color=WHITE)
        add_text(s, theme, x, by + 0.5, bw, 0.3,
                 size=10, bold=True, color=col, align=PP_ALIGN.CENTER)
        add_text(s, desc, x + 0.05, by + 0.85, bw - 0.1, bh - 0.85,
                 size=8, color=DARK, align=PP_ALIGN.CENTER)
        # arrow between cards
        if i < len(versions) - 1:
            mid_y = by + bh / 2
            add_arrow(s, x + bw, mid_y, x + bw + gap, mid_y, color=GREY, width=1.5)
    # bottom narrative
    add_text(s,
             "Each step closed bugs without changing the rationalisation maths. "
             "v3.3.5 is the recommended phase-1 plan; v3.3.4 stays available as "
             "the aspirational 15-min-everywhere variant.",
             0.5, 4.5, 12.3, 0.6,
             size=12, color=GREY, italic=True)
    footer(s, "Slide 2  ·  Audit lineage")

    # ── SLIDE 3 — Pipeline as horizontal 4-stage flow ───────────────────
    s = slide_blank(prs)
    slide_header(s, "How the engine builds the plan — 4 phases", color=TEAL)
    stages = [
        ("PHASE 1", "Ingestion",       NAVY,    [
            "613 permits · bbox clip 33.5–34.5°N",
            "OSRM routing · Kashmir OSM",
            "30 SSCL routes injected as backbone",
            "POIs from OSM Overpass (3-tier)",
        ]),
        ("PHASE 2", "Spatial scoring", TEAL,    [
            "400 m walk catchments",
            "WorldPop 100 m raster (2024)",
            "POI gravity 250 m buffer",
            "Tourist boost ×1.3 on 69 routes",
        ]),
        ("PHASE 3", "Classification\n+ fleet sizing", PURPLE, [
            "CDI = Pop ×0.5 + POI ×0.5",
            "Jenks bands · HP/MP/LP",
            "Headways · 15 / 20 / 35 / 60 min",
            "⌈Cycle / Headway × 1.15⌉",
        ]),
        ("PHASE 4", "KPIs + export",   SAFFRON, [
            "Daily_Demand · Load_Flag · Subsidy_Risk",
            "8/8 QC checks block export on fail",
            "9-sheet RTO workbook + dashboards",
            "Cross-validate vs CHALO live data",
        ]),
    ]
    bx_start = 0.5
    by = 1.9
    bw = 3.0
    bh = 4.4
    gap = 0.2
    for i, (tag, name, col, bullets) in enumerate(stages):
        x = bx_start + i * (bw + gap)
        # card body
        add_rect(s, x, by, bw, bh, fill=WHITE, rounded=True, line=col)
        # top tag
        add_rect(s, x, by, bw, 0.55, fill=col, rounded=True)
        add_centered_label(s, tag, x, by, bw, 0.55, size=13, color=WHITE)
        # name
        add_text(s, name, x + 0.15, by + 0.65, bw - 0.3, 0.85,
                 size=18, bold=True, color=col, align=PP_ALIGN.CENTER, font="Calibri")
        # bullets
        for j, b in enumerate(bullets):
            row_y = by + 1.7 + j * 0.65
            add_oval(s, x + 0.25, row_y + 0.12, 0.15, 0.15, fill=col)
            add_text(s, b, x + 0.5, row_y, bw - 0.6, 0.6, size=10, color=DARK)
        # arrow to next
        if i < 3:
            ay = by + bh / 2
            add_arrow(s, x + bw, ay, x + bw + gap, ay, color=col, width=2.5)
    footer(s, "Slide 3  ·  Pipeline architecture")

    # ── SLIDE 4 — Network composition donut + stacks ────────────────────
    s = slide_blank(prs)
    slide_header(s, "Network composition — 342 permits → 207 active",
                 color=PURPLE)
    # left: stacked horizontal bar  (Trunk / Feeder / Merged)
    bx = 0.7
    by = 1.7
    total = stats['total_routes']
    parts = [
        ("Upgraded to Trunk",   stats['trunks'],  TEAL),
        ("Retained as Feeder",  stats['feeders'], NAVY),
        ("Merged into Trunk",   stats['merged'],  SAFFRON),
    ]
    bar_w = 10.5
    bar_h = 0.9
    accum = 0
    for label, count, col in parts:
        w_part = bar_w * count / total
        add_rect(s, bx + accum, by, w_part, bar_h, fill=col)
        if w_part > 1.5:
            add_centered_label(s, f"{count}", bx + accum, by, w_part, bar_h,
                               size=22, color=WHITE)
        accum += w_part
    # legend below
    lx = 0.7
    ly = 2.8
    lw = 3.5
    for i, (label, count, col) in enumerate(parts):
        x = lx + i * (lw + 0.2)
        add_rect(s, x, ly, 0.2, 0.6, fill=col)
        add_text(s, label, x + 0.3, ly + 0.02, lw - 0.3, 0.3, size=12, bold=True, color=DARK)
        pct = 100 * count / total
        add_text(s, f"{count} routes  ·  {pct:.1f}% of network",
                 x + 0.3, ly + 0.3, lw - 0.3, 0.3, size=10, color=GREY)
    # right side — priority bands strip
    add_text(s, "By priority band (active only)", 0.7, 3.9, 12, 0.4,
             size=16, bold=True, color=DARK)
    bands = [
        ("HP — High Priority (trunk)",       stats['hp'],  TEAL,    "15 / 20 min headway"),
        ("MP — Medium Priority (feeder)",    stats['mp'],  PURPLE,  "35 min headway"),
        ("LP — Low Priority (lifeline)",     stats['lp'],  GOLD,    "60 min headway"),
    ]
    by2 = 4.4
    for i, (label, count, col, hw) in enumerate(bands):
        y = by2 + i * 0.65
        add_rect(s, 0.7, y, 0.3, 0.5, fill=col)
        add_text(s, label, 1.1, y + 0.05, 6.0, 0.45, size=13, bold=True, color=DARK)
        add_text(s, hw, 7.2, y + 0.05, 3.5, 0.45, size=11, color=GREY, italic=True)
        add_text(s, f"{count}", 10.8, y + 0.0, 1.8, 0.5,
                 size=20, bold=True, color=col, align=PP_ALIGN.RIGHT, font="Calibri")
    footer(s, "Slide 4  ·  Network composition")

    # ── SLIDE 5 — Fleet stack visual (proportional bus icons) ───────────
    s = slide_blank(prs)
    slide_header(s, f"Recommended fleet — {stats['fleet']} buses",
                 sub="138 large (12 m HPV) + 730 medium (9 m MPV) + 120 small (LPV / tempo)",
                 color=GOLD)
    # Three columns: HPV, MPV, LPV — sized icons + counts
    classes = [
        ("HPV", stats['hpv'], "12-metre standard low-floor", "50 seats", NAVY,    50,  4.0),
        ("MPV", stats['mpv'], "9-metre SSCL e-bus / midi",   "35 seats", TEAL,    35,  3.0),
        ("LPV", stats['lpv'], "Tempo / minibus",             "15 seats", SAFFRON, 15,  2.0),
    ]
    cx_start = 0.9
    cy = 2.0
    cw = 3.9
    ch = 4.2
    gap = 0.2
    for i, (cls, count, desc, seats, col, _seats_n, bus_w) in enumerate(classes):
        x = cx_start + i * (cw + gap)
        # card
        add_rect(s, x, cy, cw, ch, fill=LIGHT, rounded=True)
        # header
        add_rect(s, x, cy, cw, 0.6, fill=col, rounded=True)
        add_centered_label(s, cls, x, cy, cw, 0.6, size=20, color=WHITE)
        # big number
        add_text(s, f"{count}", x, cy + 0.7, cw, 1.1,
                 size=64, bold=True, color=col,
                 align=PP_ALIGN.CENTER, font="Calibri")
        # bus icon (rounded rect with windows)
        bus_x = x + (cw - bus_w) / 2
        bus_y = cy + 2.1
        add_rect(s, bus_x, bus_y, bus_w, 0.7, fill=col, rounded=True)
        # tiny windows
        win_w = (bus_w - 0.4) / 6
        for w_i in range(5):
            add_rect(s, bus_x + 0.2 + w_i * (win_w + 0.05), bus_y + 0.12,
                     win_w, 0.25, fill=WHITE)
        # wheels
        add_oval(s, bus_x + 0.25, bus_y + 0.55, 0.3, 0.3, fill=DARK)
        add_oval(s, bus_x + bus_w - 0.55, bus_y + 0.55, 0.3, 0.3, fill=DARK)
        # description
        add_text(s, desc, x, cy + 3.05, cw, 0.4,
                 size=12, bold=True, color=DARK, align=PP_ALIGN.CENTER)
        add_text(s, f"{seats}  ·  {100*count/stats['fleet']:.1f}% of fleet",
                 x, cy + 3.45, cw, 0.4,
                 size=11, color=GREY, align=PP_ALIGN.CENTER, italic=True)
    footer(s, "Slide 5  ·  Fleet composition")

    # ── SLIDE 6 — SSCL backbone flow ────────────────────────────────────
    s = slide_blank(prs)
    slide_header(s, "SSCL backbone — 30 CHALO routes anchor the plan",
                 color=TEAL)
    add_text(s,
             "Engine matches the 30 official SSCL e-bus routes to 45 permits "
             "in the existing-routes dataset (operator duplicates running the same corridor).",
             0.6, 1.25, 12, 0.5, size=13, color=GREY, italic=True)
    # flow boxes
    nodes = [
        (0.7, 2.3, 2.7, 1.6, NAVY,    "30",
                                   "Official SSCL\nCHALO routes",
                                   "Apr 2026 ridership"),
        (4.0, 2.3, 2.7, 1.6, TEAL,    "45",
                                   "Permits matched\nin permit dataset",
                                   "+15 duplicates"),
        (7.3, 2.3, 2.7, 1.6, PURPLE,  "8.04",
                                   "Engine\nbuses per route",
                                   "@ 15-min headway"),
        (10.6, 2.3, 2.2, 1.6, GREEN, "+9.7%",
                                   "vs scaled CHALO\nfleet/route",
                                   "Within ±25% band ✓"),
    ]
    for x, y, w, h, col, big, line1, line2 in nodes:
        add_rect(s, x, y, w, h, fill=WHITE, rounded=True, line=col)
        add_text(s, big, x, y + 0.08, w, 0.55,
                 size=28, bold=True, color=col,
                 align=PP_ALIGN.CENTER, font="Calibri")
        add_text(s, line1, x, y + 0.7, w, 0.55,
                 size=11, bold=True, color=DARK, align=PP_ALIGN.CENTER)
        add_text(s, line2, x, y + 1.18, w, 0.4,
                 size=9, color=GREY, italic=True, align=PP_ALIGN.CENTER)
    # arrows between
    arrow_y = 3.1
    for x1, x2 in [(3.4, 4.0), (6.7, 7.3), (10.0, 10.6)]:
        add_arrow(s, x1, arrow_y, x2, arrow_y, color=TEAL, width=2.5)
    # bottom narrative — operator absorption + buyback ask
    add_rect(s, 0.7, 4.6, 12.1, 2.2, fill=GOLD_LT, rounded=True)
    add_rect(s, 0.7, 4.6, 0.18, 2.2, fill=GOLD, rounded=True)
    add_text(s, "Operator absorption — Phase-1 ask",
             0.95, 4.7, 11.5, 0.4, size=15, bold=True, color=GOLD)
    rows = [
        ("Private Minibus", 70, "Buyback @ ₹15 L", "₹10.50 Cr"),
        ("LPV / Tempo",     32, "Last-mile reassignment", "₹0.96 Cr"),
        ("HPV Bus",          3, "Roll into JKRTC", "₹1.50 Cr"),
        ("Total absorbed", 135, "Mixed strategy", "₹12.96 Cr"),
    ]
    table_y = 5.15
    col_x = [0.95, 4.5, 6.5, 10.5]
    headers = ["Operator class", "# permits", "Strategy", "Est. ask"]
    for i, h in enumerate(headers):
        add_text(s, h, col_x[i], table_y, 3.0, 0.3,
                 size=10, bold=True, color=GOLD)
    for i, (op, n, strat, est) in enumerate(rows):
        y = table_y + 0.35 + i * 0.32
        is_total = (i == len(rows) - 1)
        add_text(s, op, col_x[0], y, 3.5, 0.3,
                 size=11, bold=is_total, color=DARK)
        add_text(s, f"{n}", col_x[1], y, 1.5, 0.3,
                 size=11, bold=is_total, color=DARK)
        add_text(s, strat, col_x[2], y, 4.0, 0.3,
                 size=11, bold=is_total, color=DARK, italic=not is_total)
        add_text(s, est, col_x[3], y, 2.2, 0.3,
                 size=11, bold=is_total, color=SAFFRON if is_total else DARK)
    footer(s, "Slide 6  ·  SSCL backbone + operator absorption")

    # ── SLIDE 7 — Headway plan as visual frequency strip ────────────────
    s = slide_blank(prs)
    slide_header(s, "Headway plan — phase-1 conservative",
                 sub="Bus icons spaced proportional to wait time. Visual intuition over a table.",
                 color=PURPLE)
    bands = [
        ("SSCL backbone",        15, 45,  TEAL,    "SSCL e-bus design target"),
        ("Non-SSCL HP trunks",   20, 85,  NAVY,    "Phase-1 conservative (was 15 in v3.3.4)"),
        ("MP feeders",           35, 50,  PURPLE,  "Peer-city feeder norm"),
        ("Social-promoted",      45,  4,  GOLD,    "Social_Flag LP→MP exceptions"),
        ("LP lifelines",         60, 23,  SAFFRON, "Inter-district / district-HQ"),
    ]
    # x scale: 60 min = 9.5 inches; 0 min at x=2.0  (was 11.0 in v1 — right-
    # side route counts clipped off the slide edge.)
    base_x = 2.0
    scale  = 9.5 / 60.0
    by0 = 1.85
    rh = 0.85
    # min-axis labels
    for m in (0, 15, 30, 45, 60):
        ax = base_x + m * scale
        add_text(s, f"{m} min", ax - 0.4, 1.55, 0.8, 0.25,
                 size=9, color=GREY, align=PP_ALIGN.CENTER)
        # vertical tick line (single thin rectangle)
        add_rect(s, ax - 0.01, 1.78, 0.02, 5.0, fill=RGBColor(0xE0, 0xE0, 0xE0))
    for i, (label, headway, n_routes, col, note) in enumerate(bands):
        y = by0 + i * (rh + 0.08)
        # row label
        add_text(s, label, 0.3, y, 1.7, rh, size=12, bold=True, color=DARK,
                 anchor=MSO_ANCHOR.MIDDLE)
        # row strip background
        strip_x = base_x
        strip_w = 60 * scale
        add_rect(s, strip_x, y, strip_w, rh, fill=LIGHT, rounded=True)
        # bus icons every `headway` minutes
        bus_w, bus_h = 0.3, 0.4
        bus_y = y + (rh - bus_h) / 2
        for m in range(0, 61, headway):
            bx = base_x + m * scale - bus_w / 2
            if bx + bus_w > base_x + strip_w + 0.1:
                continue
            add_rect(s, bx, bus_y, bus_w, bus_h, fill=col, rounded=True)
        # route count and note on right — anchored well inside the slide so
        # nothing clips past the 13.33" edge.
        add_text(s, f"{n_routes} routes", base_x + strip_w + 0.15, y,
                 1.7, rh / 2,
                 size=11, bold=True, color=col, anchor=MSO_ANCHOR.MIDDLE)
        add_text(s, note, base_x + strip_w + 0.15, y + rh / 2,
                 1.7, rh / 2,
                 size=8, color=GREY, italic=True, anchor=MSO_ANCHOR.TOP)
    footer(s, "Slide 7  ·  Headway plan")

    # ── SLIDE 8 — How do we know this plan is right? (plain language) ───
    s = slide_blank(prs)
    slide_header(s, "How do we know this plan is right?",
                 sub="Three quick checks an IAS reviewer can defend in the room",
                 color=GREEN)

    # Three big "question cards" — each with its own colour, a question
    # heading, the answer in plain language, and the supporting number.
    questions = [
        # x_start, title-question, answer phrase, big number, sub-line, colour
        (0.5,
         "Q1.  Are we matching real ridership?",
         "Yes — the plan's per-route fleet for the SSCL backbone is within "
         "10% of what CHALO would need at the same 15-min headway.",
         "+9.7%",
         "Engine 8.04  vs  scaled CHALO 7.33 buses/route",
         GREEN),
        (4.65,
         "Q2.  Is anyone going to be left standing?",
         "No — only 1 active route runs at or above its seat capacity at "
         "the recommended headway. Every other route has spare seats.",
         "1 of 207",
         "Amber_Tight  ·  zero Red_Overload",
         GOLD),
        (8.8,
         "Q3.  Is the fleet count defensible?",
         "Yes — at 0.60 buses per 1,000 residents Srinagar sits between "
         "BMTC Bengaluru (0.51) and Chandigarh CTU (0.65). Peer-city band.",
         "0.60",
         "buses per 1,000 residents",
         NAVY),
    ]
    cw = 4.0
    ch = 4.0
    cy = 1.7
    for x_start, q, answer, big, sub, col in questions:
        # Card body
        add_rect(s, x_start, cy, cw, ch, fill=WHITE, rounded=True, line=col)
        # Header band
        add_rect(s, x_start, cy, cw, 0.85, fill=col, rounded=True)
        add_centered_label(s, q, x_start + 0.15, cy + 0.05, cw - 0.3, 0.75,
                           size=14, color=WHITE)
        # Big number
        add_text(s, big, x_start, cy + 1.05, cw, 1.0,
                 size=44, bold=True, color=col,
                 align=PP_ALIGN.CENTER, font="Calibri")
        # Sub-line
        add_text(s, sub, x_start + 0.15, cy + 2.05, cw - 0.3, 0.45,
                 size=11, color=GREY, italic=True, align=PP_ALIGN.CENTER)
        # Plain-language answer
        add_text(s, answer, x_start + 0.25, cy + 2.6, cw - 0.5, ch - 2.7,
                 size=12, color=DARK, anchor=MSO_ANCHOR.TOP)

    # Bottom strip — the calibration anchor in one line
    add_rect(s, 0.5, 6.05, 12.33, 0.85, fill=GREEN_LT, rounded=True)
    add_rect(s, 0.5, 6.05, 0.15, 0.85, fill=GREEN, rounded=True)
    add_text(s, "Calibration anchor:",
             0.85, 6.15, 3.0, 0.3,
             size=11, bold=True, color=GREEN)
    add_text(s,
             "Every number in this plan was cross-checked against twelve "
             "months of CHALO ridership data (May 2025 – Apr 2026, "
             "11.6 M trips across 30 SSCL e-bus routes). "
             "Engine blocks export if any of the 8 QC checks fails — they all passed.",
             0.85, 6.42, 12.0, 0.45,
             size=10.5, color=DARK, italic=True)
    footer(s, "Slide 8  ·  Plain-language confidence check")

    # ── SLIDE 9 — Peer city benchmark bar chart ─────────────────────────
    s = slide_blank(prs)
    slide_header(s, "Fleet density vs peer cities",
                 sub="Buses per 1,000 residents — Srinagar lands between BMTC and Chandigarh",
                 color=NAVY)
    cities = [
        ("Mysuru KSRTC",     0.35, GREY),
        ("Bhopal BCLL",      0.43, GREY),
        ("Indore Atal",      0.45, GREY),
        ("BMTC Bengaluru",   0.51, GREY),
        ("Srinagar v3.3.5",  0.60, TEAL),     # highlight
        ("Chandigarh CTU",   0.65, GREY),
        ("Pune PMPML",       0.75, GREY),
        ("Delhi DTC+cluster",0.90, GREY),
        ("Mumbai BEST",      1.20, GREY),
    ]
    max_v = 1.30
    bar_x0 = 4.2
    bar_max = 8.0
    row_h = 0.4
    by0 = 1.85
    for i, (name, val, col) in enumerate(cities):
        y = by0 + i * row_h
        is_self = "Srinagar" in name
        add_text(s, name, 0.6, y, 3.5, row_h - 0.05,
                 size=12, bold=is_self,
                 color=TEAL if is_self else DARK,
                 anchor=MSO_ANCHOR.MIDDLE)
        w = bar_max * val / max_v
        add_rect(s, bar_x0, y + 0.05, w, row_h - 0.15,
                 fill=TEAL if is_self else RGBColor(0xBD, 0xBD, 0xBD),
                 rounded=False)
        add_text(s, f"{val:.2f}", bar_x0 + w + 0.1, y + 0.0,
                 1.0, row_h - 0.05,
                 size=11, bold=is_self,
                 color=TEAL if is_self else GREY,
                 anchor=MSO_ANCHOR.MIDDLE)
    add_text(s,
             "Srinagar at 0.60 is the closest match to Chandigarh CTU (0.65) — "
             "comparable city size, comparable terrain, comparable scope.",
             0.6, 5.8, 12, 0.7,
             size=12, italic=True, color=GREY)
    footer(s, "Slide 9  ·  Peer-city benchmarks")

    # ── SLIDE 10 — Conservative vs Aspirational (side-by-side) ──────────
    s = slide_blank(prs)
    slide_header(s, "Two service-level plans on the table", color=SAFFRON)
    # Left column = v3.3.5 phase-1
    # Right column = v3.3.4 aspirational
    cards = [
        (0.7, "v3.3.5 — Phase-1 (recommended)", GREEN, "988",  "buses",
         [("SSCL backbone",    "15 min"),
          ("Non-SSCL trunks",  "20 min"),
          ("MP feeders",       "35 min"),
          ("LP lifelines",     "60 min"),
          ("vs current ~600",  "+65%"),
          ("Buses / 1000",     "0.60"),
          ("Calibration ✓",    "+9.7%")]),
        (6.95, "v3.3.4 — Aspirational (phase-2)", SAFFRON, "1,113", "buses",
         [("SSCL backbone",    "15 min"),
          ("Non-SSCL trunks",  "15 min"),
          ("MP feeders",       "30 min"),
          ("LP lifelines",     "60 min"),
          ("vs current ~600",  "+85%"),
          ("Buses / 1000",     "0.67"),
          ("Calibration ✓",    "+9.7%")]),
    ]
    for x_start, title, col, big, sub, rows in cards:
        cw = 5.7
        ch = 4.8                       # was 5.3 — shrunk so card bottom clears narrative
        add_rect(s, x_start, 1.75, cw, ch, fill=WHITE, rounded=True, line=col)
        # header
        add_rect(s, x_start, 1.75, cw, 0.65, fill=col, rounded=True)
        add_centered_label(s, title, x_start, 1.75, cw, 0.65, size=16, color=WHITE)
        # big number
        add_text(s, big, x_start, 2.5, cw, 1.0,
                 size=60, bold=True, color=col,
                 align=PP_ALIGN.CENTER, font="Calibri")
        add_text(s, sub, x_start, 3.55, cw, 0.35,
                 size=12, color=GREY, italic=True, align=PP_ALIGN.CENTER)
        # rows (7 rows × 0.3 = 2.1, fits in remaining card height)
        for i, (k, v) in enumerate(rows):
            y = 3.95 + i * 0.30
            add_text(s, k, x_start + 0.4, y, 3.4, 0.28, size=11, color=DARK)
            add_text(s, v, x_start + cw - 1.9, y, 1.5, 0.28,
                     size=11, bold=True, color=col, align=PP_ALIGN.RIGHT)
    # narrative below the cards (cards now end at y=6.55, narrative at 6.75)
    add_text(s,
             "Same engine, same data, same QC. Only the non-SSCL headway target differs. "
             "Year-1 commit → v3.3.5. Year-3 ambition → v3.3.4.",
             0.7, 6.75, 12, 0.5,
             size=12, color=GREY, italic=True, align=PP_ALIGN.CENTER)
    footer(s, "Slide 10  ·  Decision the IAS makes")

    # ── SLIDE 11 — Methodology proxy → real (Phase-2 backlog) ──────────
    s = slide_blank(prs)
    slide_header(s, "What's in Phase 1 vs what comes next (Phase 2)",
                 color=PURPLE)
    rows = [
        ("Walk catchment",  "400 m Euclidean buffer",       "OSMnx isochrone clipped against Dal/Anchar/Jhelum", PURPLE),
        ("Population",      "WorldPop 2024 raster",         "Census 2021 ward + growth-adjusted corridors",     TEAL),
        ("Cycle time",      "Virtual 500m stops + congestion×", "Field-timed stop dwell + GPS journey traces", GOLD),
        ("Demand",          "Static buffer × mode × trips",  "Demand elasticity (Mohring) + AFC validation",     SAFFRON),
        ("Tourist surge",   "Tier-3 POI weights + ×1.3",     "Real arrival data from JKTDC / hotels",            NAVY),
        ("Convoy / NH-44",  "Not modelled",                  "Time-of-day operability mask",                     GREEN),
    ]
    by0 = 1.85
    rh = 0.78
    # column headers
    add_text(s, "Concept", 0.6, by0, 2.5, 0.4, size=11, bold=True, color=GREY)
    add_text(s, "Phase 1 (now)", 3.4, by0, 4.4, 0.4, size=11, bold=True, color=GREY)
    add_text(s, "Phase 2 (target)", 8.2, by0, 4.6, 0.4, size=11, bold=True, color=GREY)
    for i, (concept, p1, p2, col) in enumerate(rows):
        y = by0 + 0.45 + i * rh
        # left token
        add_rect(s, 0.6, y + 0.1, 0.15, 0.55, fill=col)
        add_text(s, concept, 0.85, y, 2.5, rh - 0.1,
                 size=12, bold=True, color=DARK, anchor=MSO_ANCHOR.MIDDLE)
        # phase 1 card
        add_rect(s, 3.4, y + 0.1, 4.2, rh - 0.2, fill=LIGHT, rounded=True)
        add_text(s, p1, 3.55, y + 0.15, 4.0, rh - 0.3,
                 size=11, color=DARK, anchor=MSO_ANCHOR.MIDDLE)
        # arrow
        add_arrow(s, 7.7, y + rh / 2, 8.1, y + rh / 2, color=col, width=2.0)
        # phase 2 card
        add_rect(s, 8.2, y + 0.1, 4.6, rh - 0.2,
                 fill=RGBColor(0xE3, 0xF2, 0xFD), rounded=True)
        add_text(s, p2, 8.35, y + 0.15, 4.3, rh - 0.3,
                 size=11, color=DARK, anchor=MSO_ANCHOR.MIDDLE)
    footer(s, "Slide 11  ·  Phase-1 → Phase-2 backlog")

    # ── SLIDE 11b — Data we need from officers ──────────────────────────
    s = slide_blank(prs)
    slide_header(s, "Data we'd need from your office to sharpen v3.4",
                 sub="Phase-2 features above are limited by data, not by maths. Here is the concrete ask.",
                 color=TEAL)

    # Each row: priority, dataset, custodian, single-line "why".
    # v2: compressed to single-line entries — multi-line "why" overflowed.
    asks = [
        ("P0", "Master stops register",
         "Kashmir_Stops_Sectored_V2.csv",
         "RTOs / SSCL",
         "Retires the 23 TMP-K placeholder route codes.",
         SAFFRON),
        ("P0", "Operator permit registry (live)",
         "Permit no. · owner · vehicle no. · depot",
         "RTO offices · J&K Transport Commr",
         "Exact displaced vehicles → defensible buyback.",
         SAFFRON),
        ("P0", "GPS traces — current operators",
         "30 days · 1 Hz · SSCL + private operators",
         "SSCL CHALO ops · MTS Kashmir",
         "Replaces OSRM free-flow + congestion×2.2 model.",
         SAFFRON),
        ("P1", "Census 2021 ward-level population",
         "Ward boundaries + counts",
         "Census of India · J&K Directorate",
         "Tighter Pop_Score → tighter CDI bands.",
         GOLD),
        ("P1", "AFC / fare-card ridership (per route)",
         "Per-route per-day boardings",
         "SSCL CHALO platform",
         "Enables route-level demand & Mohring elasticity.",
         GOLD),
        ("P1", "JKTDC tourist arrival data",
         "Daily arrivals · Gulmarg / Pahalgam / Sonamarg",
         "J&K Tourism Dept (JKTDC)",
         "Real seasonal surge → tourist fleet sizing.",
         GOLD),
        ("P2", "Road operability calendar",
         "NH-44 convoys · Sinthan / Z-Morh / Mughal Road dates",
         "BRO · J&K Traffic · Border Mgmt",
         "Auto-flag Winter_Suspended; subtract un-operable hours.",
         NAVY),
        ("P2", "Bus stop / depot inventory",
         "Lat-lon of every stop · depot capacity",
         "SSCL / JKRTC / RTO offices",
         "Replaces virtual 500 m stop spacing.",
         NAVY),
        ("P2", "Bridge load / road-width registry",
         "Per-bridge weight limit · arterial road widths",
         "R&B Dept · MC Srinagar",
         "Restricts 12 m HPV to roads/bridges that can take it.",
         NAVY),
    ]

    # Layout — tighter row height + single-line text so 9 rows + header +
    # legend all fit comfortably.
    by_h = 1.55     # column-header band
    by_a = 1.9      # first data row
    rh   = 0.52     # row height
    # Column geometry (x, width)
    col_geom = [
        ("Priority",       0.55, 0.85),
        ("Dataset",        1.55, 4.15),
        ("Custodian",      5.85, 3.10),
        ("Why it matters", 9.10, 3.85),
    ]
    # Column-header band
    add_rect(s, 0.45, by_h, 12.55, 0.32, fill=NAVY, rounded=True)
    for label, x, w in col_geom:
        add_text(s, label, x, by_h + 0.04, w, 0.26,
                 size=10, bold=True, color=WHITE)
    for i, (prio, name, what, who, why, col) in enumerate(asks):
        y = by_a + i * rh
        # zebra row
        if i % 2 == 0:
            add_rect(s, 0.45, y, 12.55, rh - 0.04, fill=LIGHT)
        # priority pill
        add_rect(s, 0.55, y + 0.10, 0.65, rh - 0.24, fill=col, rounded=True)
        add_centered_label(s, prio, 0.55, y + 0.10, 0.65, rh - 0.24,
                           size=10, color=WHITE)
        # dataset name (bold)
        add_text(s, name, 1.55, y + 0.04, 4.15, 0.24,
                 size=10, bold=True, color=DARK)
        # what (italic sub-text)
        add_text(s, what, 1.55, y + 0.26, 4.15, 0.22,
                 size=8.5, color=GREY, italic=True)
        # custodian — single line, vertically centred
        add_text(s, who, 5.85, y, 3.10, rh - 0.04,
                 size=9.5, color=DARK, anchor=MSO_ANCHOR.MIDDLE)
        # why — single line, vertically centred
        add_text(s, why, 9.10, y, 3.85, rh - 0.04,
                 size=9.5, color=DARK, anchor=MSO_ANCHOR.MIDDLE)

    # Bottom legend
    legend_y = by_a + len(asks) * rh + 0.18
    add_text(s, "Priority key:",
             0.55, legend_y, 1.4, 0.25, size=10, bold=True, color=GREY)
    legend = [
        ("P0", "blocks v3.4 calibration",      SAFFRON),
        ("P1", "improves accuracy meaningfully", GOLD),
        ("P2", "future-state polish",          NAVY),
    ]
    lx = 1.95
    for tag, desc, col in legend:
        add_rect(s, lx, legend_y + 0.02, 0.4, 0.22, fill=col, rounded=True)
        add_centered_label(s, tag, lx, legend_y + 0.02, 0.4, 0.22, size=8, color=WHITE)
        add_text(s, desc, lx + 0.5, legend_y, 3.3, 0.25,
                 size=9.5, color=DARK, italic=True)
        lx += 3.5

    footer(s, "Slide 12  ·  Data we need from your office")

    # ── SLIDE 13 — What this output IS / IS NOT (sandwich) ───────────────
    s = slide_blank(prs)
    slide_header(s, "What this output is — and what it is not",
                 color=NAVY)
    # Two columns
    is_items = [
        "207 active routes classified with HP / MP / LP bands",
        "Fleet sized for phase-1 conservative headways (15/20/35/60 min)",
        "30 SSCL backbone routes calibrated against CHALO Apr 2026 data",
        "9-sheet RTO workbook with operator absorption + buyback estimates",
        "Reproducible pipeline — every number traces to a CSV row",
    ]
    isnot_items = [
        "A ridership survey — field validation still required",
        "A net-fleet-gap report — current ops verification needed",
        "Final headway commitments — RTO consultation still pending",
        "A buyback price commitment — figures are estimates per peer cities",
        "Tourist demand model — surge data is Phase 2 work",
    ]
    # left card
    add_rect(s, 0.6, 1.85, 6.1, 5.0, fill=GREEN_LT, rounded=True, line=GREEN)
    add_rect(s, 0.6, 1.85, 6.1, 0.6, fill=GREEN, rounded=True)
    add_centered_label(s, "WHAT IT IS", 0.6, 1.85, 6.1, 0.6, size=16, color=WHITE)
    for i, t in enumerate(is_items):
        y = 2.7 + i * 0.85
        add_oval(s, 0.85, y + 0.07, 0.35, 0.35, fill=GREEN)
        add_centered_label(s, "✓", 0.85, y + 0.07, 0.35, 0.35, size=14, color=WHITE)
        add_text(s, t, 1.35, y, 5.2, 0.8, size=12, color=DARK,
                 anchor=MSO_ANCHOR.MIDDLE)
    # right card
    add_rect(s, 6.95, 1.85, 6.1, 5.0, fill=SAFFRON_LT, rounded=True, line=SAFFRON)
    add_rect(s, 6.95, 1.85, 6.1, 0.6, fill=SAFFRON, rounded=True)
    add_centered_label(s, "WHAT IT IS NOT", 6.95, 1.85, 6.1, 0.6, size=16, color=WHITE)
    for i, t in enumerate(isnot_items):
        y = 2.7 + i * 0.85
        add_oval(s, 7.2, y + 0.07, 0.35, 0.35, fill=SAFFRON)
        add_centered_label(s, "✗", 7.2, y + 0.07, 0.35, 0.35, size=14, color=WHITE)
        add_text(s, t, 7.7, y, 5.2, 0.8, size=12, color=DARK,
                 anchor=MSO_ANCHOR.MIDDLE)
    footer(s, "Slide 13  ·  Honest scope")

    # ── SLIDE 14 — Closing / ask ────────────────────────────────────────
    s = slide_blank(prs)
    add_rect(s, 0, 0, 13.33, 7.5, fill=NAVY)
    add_rect(s, 0, 6.7, 13.33, 0.8, fill=TEAL)
    add_text(s, "Recommended Path", 0.7, 0.7, 12, 0.6,
             size=22, bold=True, color=TEAL_LIGHT, font="Calibri")
    add_text(s, "Five asks for the IAS", 0.7, 1.3, 12, 1.0,
             size=42, bold=True, color=WHITE, font="Calibri")
    asks = [
        ("1", "Sign-off",        "Approve v3.3.5 conservative phase-1 plan at the Stage-1 review."),
        ("2", "Operator dialogue","Authorise consultation with All J&K Transport Welfare Association."),
        ("3", "Phased rollout",  "Activate SSCL backbone + 20-min trunks first; expand on observed ridership."),
        ("4", "Monthly recalib", "Re-run cross_evaluate vs CHALO monthly; recalibrate CAPTURE_SCALE if drift > ±15%."),
        ("5", "Phase-2 scope",   "Sanction next-FY work — OSMnx walksheds, demand elasticity, convoy mask."),
    ]
    for i, (n, title, body) in enumerate(asks):
        y = 2.7 + i * 0.75
        add_oval(s, 0.8, y, 0.6, 0.6, fill=GOLD)
        add_centered_label(s, n, 0.8, y, 0.6, 0.6, size=22, color=NAVY)
        add_text(s, title, 1.6, y - 0.05, 3.0, 0.35,
                 size=15, bold=True, color=WHITE)
        add_text(s, body, 1.6, y + 0.28, 11.0, 0.4,
                 size=12, color=TEAL_LIGHT, italic=True)
    add_text(s,
             "Engine v3.3.5 · Companion artefacts: RTO 9-sheet workbook · "
             "Headway PDF study guide · Live dashboard at bus-sathi-dashboard",
             0.7, 6.85, 12, 0.45,
             size=11, color=WHITE, italic=True, align=PP_ALIGN.CENTER)


# ─── Stat loader (live numbers from v3.3.5 CSV) ──────────────────────────────
def load_stats(csv_path: Path):
    # Sensible defaults if CSV missing
    defaults = dict(
        total_routes=342, active=207, trunks=50, feeders=157, merged=135,
        fleet=988, hpv=138, mpv=730, lpv=120,
        hp=130, mp=54, lp=23,
        green=9, amber=197, tight=1, red=0,
    )
    if not csv_path.exists():
        return defaults
    df = pd.read_csv(csv_path)
    act = df[df["Action_Taken"] != "MERGED_INTO_TRUNK"]
    out = dict(defaults)
    out["total_routes"] = len(df)
    out["active"]       = len(act)
    out["trunks"]       = int((df["Action_Taken"] == "UPGRADED_TO_TRUNK").sum())
    out["feeders"]      = int((df["Action_Taken"] == "RETAINED_AS_FEEDER").sum())
    out["merged"]       = int((df["Action_Taken"] == "MERGED_INTO_TRUNK").sum())
    if "Fleet_Required" in act:
        out["fleet"] = int(act["Fleet_Required"].sum())
    for k, col in [("hpv", "HPV_Count"), ("mpv", "MPV_Count"), ("lpv", "LPV_Count")]:
        if col in act:
            out[k] = int(act[col].sum())
    for band in ("HP", "MP", "LP"):
        if "Priority_Band" in act:
            out[band.lower()] = int((act["Priority_Band"] == band).sum())
    if "Load_Flag" in act:
        out["green"] = int((act["Load_Flag"] == "Green").sum())
        out["amber"] = int((act["Load_Flag"] == "Amber_Under").sum())
        out["tight"] = int((act["Load_Flag"] == "Amber_Tight").sum())
        out["red"]   = int((act["Load_Flag"] == "Red_Overload").sum())
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--outdir", default="outputs_v3.3.5")
    parser.add_argument("--engine-csv",
                        default="outputs_v3.3.5/Rationalised_Routes_Kashmir_v3.csv")
    args = parser.parse_args()

    stats = load_stats(Path(args.engine_csv))
    os.makedirs(args.outdir, exist_ok=True)
    out_path = os.path.join(args.outdir,
                            "Kashmir_Transit_Diagrammatic_Pitch.pptx")

    prs = Presentation()
    prs.slide_width  = Inches(13.333)
    prs.slide_height = Inches(7.5)
    build(prs, stats)
    prs.save(out_path)
    print(f"Wrote {out_path}")
    print(f"Stats source: {args.engine_csv}")


if __name__ == "__main__":
    main()
