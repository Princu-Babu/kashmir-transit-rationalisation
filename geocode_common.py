"""
geocode_common.py — shared, hardened geocoding for latlon.py and
geocode_other_routes.py.
======================================================================================
Fixes audit Findings 1, 2 and 5 (Recommendation 1) at the root.

ROOT CAUSE the audit found
--------------------------
Both geocoders queried ArcGIS with the over-narrow context
``"{place}, Srinagar, Kashmir, India"``. For any valley town ArcGIS could not
resolve, it fell back to matching the next token — **"Srinagar"** — and returned
the city centroid (34.085650, 74.805550). 118 distinct valley place names
(Anantnag, Pampore, Budgam, Pulwama, Sopore, Kulgam, Shopian, …) collapsed onto
that single point, so 290 routes became zero-length and were silently dropped at
the engine's sub-1 km filter. The plan then "rationalised" a network missing
most of JKRTC's actual inter-district operation.

WHAT THIS MODULE CHANGES
------------------------
1. **District-aware query.** Known valley towns carry their district into the
   query: ``"Anantnag, Anantnag, Jammu and Kashmir, India"`` instead of
   ``"Anantnag, Srinagar, …"`` — so the geocoder is not pulled toward Srinagar.
2. **Valley study extent.** Results are constrained to the Kashmir-valley
   bounding box (passed to ArcGIS as ``search_extent`` when available).
3. **Centroid-collision rejection.** Any result within
   ``CENTROID_REJECT_M`` of the Srinagar centroid is REJECTED (returns None)
   unless the input name is itself Srinagar — a snap to the exact LD-Hospital
   centroid means the geocoder fell back, not that it found the place. The row
   is then recorded as a failure to be resolved manually, never silently
   collapsed onto Srinagar.
4. **Auditable failures.** ``write_failures()`` emits ``geocode_failures.csv``
   so every name that could not be placed is recorded with a reason.

This module has NO hard dependency on arcgis: callers pass a ``geocode_fn`` that
returns a list of result dicts (the arcgis.geocoding.geocode signature) OR None.
That keeps it testable and lets a future Nominatim/Photon backend drop in.
"""
from __future__ import annotations

import csv
import math
import re
from typing import Callable, Dict, List, Optional, Tuple

# ── Srinagar centroid the broken context collapsed everything onto ──
SRINAGAR_CENTROID = (34.085650, 74.805550)   # (lat, lon) — LD Hospital area
CENTROID_REJECT_M = 300.0                     # reject snaps within this radius

# ── Kashmir-valley study extent (generous; the engine still bbox-clips) ──
#   covers Anantnag/Kulgam/Shopian in the south up to Bandipora/Handwara north.
VALLEY_EXTENT = {  # xmin/ymin/xmax/ymax in lon/lat (ArcGIS search_extent order)
    "xmin": 74.10, "ymin": 33.45, "xmax": 75.45, "ymax": 34.75,
    "spatialReference": {"wkid": 4326},
}

# ── District hints for the known out-of-Srinagar valley towns ──
# token (UPPERCASE) -> district. Only high-confidence town->district pairs; any
# name not listed falls back to a valley-wide context, and the extent + centroid
# rejection remain the safety net regardless.
DISTRICT_HINTS: Dict[str, str] = {
    # Anantnag
    "ANANTNAG": "Anantnag", "ANANTNAGH": "Anantnag", "BIJBEHARA": "Anantnag",
    "MATTAN": "Anantnag", "PAHALGAM": "Anantnag", "PHALGAM": "Anantnag",
    "DOORU": "Anantnag", "KOKERNAG": "Anantnag", "ACHABAL": "Anantnag",
    "SHANGUS": "Anantnag", "LARNOO": "Anantnag", "VERINAG": "Anantnag",
    "QAZIGUND": "Anantnag", "SALIA": "Anantnag", "LAMMER": "Anantnag",
    "KHERUM": "Anantnag", "MATIGAWRAN": "Anantnag",
    # Pulwama
    "PULWAMA": "Pulwama", "PAMPORE": "Pulwama", "TRAL": "Pulwama",
    "AWANTIPORA": "Pulwama", "AWANTIPURA": "Pulwama", "KAKAPORA": "Pulwama",
    "RAJPORA": "Pulwama", "PINGLENA": "Pulwama", "GALANDAR": "Pulwama",
    "NEWA": "Pulwama", "KHREW": "Pulwama", "RATNIPORA": "Pulwama",
    "RATINPORA": "Pulwama", "LELHAR": "Pulwama",
    # Shopian
    "SHOPIAN": "Shopian", "KELLER": "Shopian", "ZAINAPORA": "Shopian",
    # Kulgam
    "KULGAM": "Kulgam", "QAIMOH": "Kulgam", "FRISAL": "Kulgam",
    "DEVSAR": "Kulgam", "DAMHAL": "Kulgam", "YARIPORA": "Kulgam",
    # Budgam
    "BUDGAM": "Budgam", "CHADOORA": "Budgam", "CHADURA": "Budgam",
    "BEERWAH": "Budgam", "KHANSAHIB": "Budgam", "MAGAM": "Budgam",
    "CHRAR": "Budgam", "CHARARI SHARIEF": "Budgam", "KHANSHAIB": "Budgam",
    # Baramulla
    "BARAMULLA": "Baramulla", "BARAMULA": "Baramulla", "SOPORE": "Baramulla",
    "PATTAN": "Baramulla", "URI": "Baramulla", "TANGMARG": "Baramulla",
    "KUNZER": "Baramulla", "BONIYAR": "Baramulla", "WAGOORA": "Baramulla",
    "RAFIABAD": "Baramulla", "SANGRAMA": "Baramulla",
    # Bandipora
    "BANDIPORA": "Bandipora", "SUMBAL": "Bandipora", "HAJIN": "Bandipora",
    "GUREZ": "Bandipora", "ALOOSA": "Bandipora", "ARIN": "Bandipora",
    # Ganderbal
    "GANDERBAL": "Ganderbal", "KANGAN": "Ganderbal", "LAR": "Ganderbal",
    "SONAMARG": "Ganderbal", "GUND": "Ganderbal", "WAYIL": "Ganderbal",
    # Kupwara
    "KUPWARA": "Kupwara", "HANDWARA": "Kupwara", "CHOWKIBAL": "Kupwara",
    "CHOWKBAL": "Kupwara", "KARNAH": "Kupwara", "TANGDAR": "Kupwara",
    "TANGDHAR": "Kupwara", "SOGAM": "Kupwara", "TREHGAM": "Kupwara",
    "KRALPORA": "Kupwara", "LANGATE": "Kupwara",
}


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def is_srinagar_centroid(lat: float, lon: float,
                         tol_m: float = CENTROID_REJECT_M) -> bool:
    """True if (lat, lon) is within tol_m of the Srinagar collapse point."""
    return _haversine_m(lat, lon, *SRINAGAR_CENTROID) <= tol_m


def _first_token(name: str) -> str:
    return re.split(r"[\s\-]+", name.strip().upper(), maxsplit=1)[0] if name else ""


def build_query(location_name: str) -> str:
    """District-aware query string. Falls back to a valley-wide context."""
    up = location_name.strip().upper()
    district = DISTRICT_HINTS.get(up) or DISTRICT_HINTS.get(_first_token(up))
    if district:
        return f"{location_name}, {district}, Jammu and Kashmir, India"
    # Srinagar localities and everything else: keep the city/valley context but
    # NOT as the sole disambiguator — the extent + centroid rejection guard it.
    return f"{location_name}, Srinagar, Jammu and Kashmir, India"


def geocode_one(location_name: str,
                geocode_fn: Callable[..., Optional[list]],
                failures: Optional[List[Dict]] = None
                ) -> Tuple[Optional[float], Optional[float]]:
    """Geocode a single name with all guards applied.

    geocode_fn(query, search_extent=...) -> list of {'location': {'x','y'}} | None
    Returns (lat, lon) or (None, None). On failure, appends a reason row to
    ``failures`` if provided.
    """
    name_is_srinagar = "SRINAGAR" in location_name.upper()
    query = build_query(location_name)
    try:
        try:
            results = geocode_fn(query, search_extent=VALLEY_EXTENT)
        except TypeError:
            # geocode_fn without search_extent support (older signature / tests)
            results = geocode_fn(query)
    except Exception as exc:  # noqa: BLE001 — record, don't crash the batch
        if failures is not None:
            failures.append({"name": location_name, "query": query,
                             "reason": f"api_error: {exc}"})
        return None, None

    if not results:
        if failures is not None:
            failures.append({"name": location_name, "query": query,
                             "reason": "no_result"})
        return None, None

    loc = results[0]["location"]
    lat, lon = float(loc["y"]), float(loc["x"])

    # Reject a fallback snap to the Srinagar centroid for non-Srinagar names.
    if not name_is_srinagar and is_srinagar_centroid(lat, lon):
        if failures is not None:
            failures.append({"name": location_name, "query": query,
                             "reason": "rejected_srinagar_centroid_collision"})
        return None, None

    # Reject anything well outside the valley extent.
    if not (VALLEY_EXTENT["ymin"] <= lat <= VALLEY_EXTENT["ymax"] and
            VALLEY_EXTENT["xmin"] <= lon <= VALLEY_EXTENT["xmax"]):
        if failures is not None:
            failures.append({"name": location_name, "query": query,
                             "reason": f"outside_valley_extent ({lat:.4f},{lon:.4f})"})
        return None, None

    return lat, lon


def write_failures(failures: List[Dict], path: str = "geocode_failures.csv") -> None:
    """Emit an auditable reject file so no drop is ever silent (Finding 2)."""
    if not failures:
        print(f"[OK] No geocode failures to report ({path} not written).")
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["name", "query", "reason"])
        w.writeheader()
        w.writerows(failures)
    print(f"[AUDIT] {len(failures)} geocode failures written to {path} "
          f"(resolve these manually — they are NOT in existing-routes.csv).")
