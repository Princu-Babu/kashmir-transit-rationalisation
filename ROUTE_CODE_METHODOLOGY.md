# Kashmir Valley Route-Code Methodology (v4 — "geo-canonical")

**Status:** authoritative. Supersedes the name-match-against-hand-built-master
approach. Implemented in [`route_code_system.py`](route_code_system.py), invoked
by the engine's `assign_route_codes()`. Last rebuilt 2026-06-21.

This document is written to be read by a non-specialist reviewer (RTO / IAS) and
to be reproducible by any engineer. Every rule is deterministic.

---

## 1. What a Route Code is

Each route carries a **12-character code**:

```
        S R G B 0 1 0 2 0 3 0 5
        └─┘ └─┘ └┘ └┘ └┘ └┘
        Do  Dd  So Sd No Nd
```

| Block | Chars | Meaning |
|---|---|---|
| `Do Dd` | 4 letters | 2-letter **District** of origin + of destination |
| `So Sd` | 4 digits | 2-digit **Sector** of origin + of destination |
| `No Nd` | 4 digits | 2-digit **Stop number** of origin + of destination |

Readable (hyphenated) display form: **`SRGB-0102-0305`**
= *Srinagar→Ganderbal, sector 01→02, stop 03→05.*

A route entirely inside one sector of Srinagar reads e.g. `SRSR-0202-0407`.

**District 2-letter codes** (the only ten in the Kashmir division):

| Code | District | Code | District |
|---|---|---|---|
| SR | Srinagar | PW | Pulwama |
| BG | Budgam | SP | Shopian |
| GB | Ganderbal | AN | Anantnag |
| BR | Baramulla | KG | Kulgam |
| BP | Bandipore | KW | Kupwara |

A trailing letter (`…A`, `…B`) appears **only** when two *active* routes share the
exact same origin **and** destination stop — the standard "5A / 5B" bus
convention for two services on one terminal pair. Distinct places never collide.

---

## 2. Why this was rebuilt (the problem with the old scheme)

The earlier codes were produced by fuzzy-matching each route's terminal **name**
against a hand-maintained master (`Kashmir_Stops_Sectored_V2.csv`). That master
had defects that are unacceptable for a government submission:

- **Unreliable coordinates** — `AIRPORT` recorded ~80 km from the real airport,
  `PARIMPORA` ~18 km off; many stops were rough manual estimates.
- **Undeduplicated spelling variants** — `R S PURA`, `RS PURA`, `RSPURA` each a
  separate "stop" with its own number.
- **Wrong district tags** — `LALCHOWK` → Anantnag, `AMRITSAR`/`LEH` → Shopian.
- **Fuzzy matching errors** — e.g. "Srinagar→Gund" matched the *Budgam* Gund
  while the route runs to the *Ganderbal* Gund; rural terminals with no nearby
  master stop snapped to a wrong-district stop and collapsed onto one code.

The result was wrong-district codes, spurious A/B collisions, and a scheme that
could not be audited. **v4 removes that master from the pipeline entirely.**

---

## 3. The two trustworthy foundations

**(a) Coordinates — the engine's own geocoded route endpoints.** Every route
already has an origin and destination coordinate produced by the engine's
district-aware geocoder (Nominatim/OSM + the curated `kashmir_gazetteer.csv`),
which was itself audited. The stop registry is built **from these endpoints**, so
a route's link to its stop is **exact** — there is no second, independent name
list to fuzzy-match against.

**(b) Administrative geography — authoritative OpenStreetMap boundaries.**
- `kashmir_districts_osm.geojson` — the 10 districts (OSM `admin_level = 5`).
- `kashmir_tehsils_osm.geojson` — the 39 tehsils (OSM `admin_level = 6`),
  each tagged with its parent district.

Every stop's **District** and **Tehsil** are decided by **point-in-polygon**
against these real boundaries — not reverse-geocoding, not nearest-centroid, not
a typed column. Verified spot-checks: Hazratbal / Lal Chowk / Batamaloo →
Srinagar; Airport → Budgam (correct — the airport is in Budgam district);
Kangan / Manigam / Gund → Ganderbal; Pampore → Pulwama; Pahalgam → Anantnag;
Tangmarg / Sopore → Baramulla.

These two files are committed to the repo so the build is fully reproducible
offline. They were fetched once from the OSM Overpass API and assembled with
`osm2geojson`.

---

## 4. The build pipeline (deterministic, stage by stage)

Run inside the engine for every build; also runnable standalone.

**Stage 1 — Collect endpoints.** For every route, take its origin and
destination (name from the route name via the "A to B via C" grammar; coordinate
from the routed geometry's first/last point).

**Stage 2 — One coordinate per name.** Group endpoints by *normalised* name
(upper-cased, punctuation and decorative words like "Bus Stand"/"Chowk" removed)
and give each name a single representative coordinate (its most-frequent rounded
coordinate). This guarantees a place name always resolves to one stop — the
geocoder occasionally returned two slightly different coordinates for one name
(e.g. "TRC"), which must not split into two stops.

**Stage 3 — Canonical stops (proximity merge).** Merge named places whose
representative coordinates are within **150 m** of each other into one canonical
stop, using *fixed-anchor* clustering (the first point in a fixed sort order
anchors the cluster; the anchor never moves). Fixed anchors prevent "chaining"
(a running-mean centroid would let A–B–C, each 150 m apart, drift into one
450 m blob — e.g. LD and TRC, 2 km apart, wrongly merging). This merges spelling
variants and genuinely co-located terminals, while keeping distinct localities
(e.g. HMT and Parimpora, ~300 m apart) separate.

**Stage 4 — District + Sector (point-in-polygon).** For each canonical stop's
coordinate: District = the containing OSM district polygon; Sector = the
containing OSM **tehsil**. A point just outside all polygons (a slightly-off
geocode, a lakeshore) snaps to the nearest polygon.

**Stage 5 — Number sectors and stops.**
- **Sectors** are numbered 1..N within each district by listing **all** of that
  district's tehsils alphabetically. Numbering over the full tehsil list (not
  just populated ones) makes a sector number **stable** — it never shifts when
  stop coverage changes. A sector is therefore a real revenue tehsil, not an
  arbitrary cluster.
- **Stops** are numbered 1..M within each (district, sector) alphabetically by
  canonical name.
- `Master_Stop_Code = <DIST>-<SS>-<NN>` (e.g. `GB-02-05`).

**Stage 6 — Route codes.** A route's origin name → its canonical stop → its
`(district, sector, stop)`; same for the destination; concatenate. A trailing
letter is added only for a genuine same-stop-pair collision among active routes,
assigned by sorted route name (deterministic).

**Outputs.** `Kashmir_Stops_Master_v4.csv` (the new authoritative registry, with
reliable coordinates + District/Tehsil/Sector/Stop) and a `Route_Code` on every
route, propagated to the CSV, GeoJSON, RTO workbooks and the dashboard.

---

## 5. Determinism & uniformity (required for government use)

Every step is a pure function of the inputs — no randomness, no run-to-run drift.
Endpoints are sorted before clustering; the merge radius is fixed; sectors come
from the fixed OSM tehsil list; stops are alphabetical; letter suffixes follow
sorted route names. **Re-running on the same inputs yields byte-identical codes.**

Validity contract enforced by QC (the engine blocks/► warns on violation):
- every active code matches `^[A-Z]{4}[0-9]{8}[A-Z]?$`;
- 0 hyphens, 0 blanks/UNMATCHED, 0 duplicate active codes;
- both district letters are among the 10 valid codes;
- the code's `Route_Code` is identical across CSV / GeoJSON / dashboard / pretty
  workbook (cross-artefact check).

---

## 6. How to reproduce or update

1. If the route network changes, the engine rebuilds codes automatically on the
   next run (`assign_route_codes()` calls `route_code_system.assign`).
2. To refresh administrative boundaries (rare — districts/tehsils seldom change),
   re-fetch from OSM Overpass (`admin_level` 5 and 6 within `IN-JK`), assemble
   with `osm2geojson`, and overwrite the two `*_osm.geojson` files.
3. Standalone check:
   ```python
   import geopandas as gpd, route_code_system as rcs
   g = gpd.read_file("outputs_vX/Rationalised_Routes_Kashmir_v3.geojson")
   routes = [{"route_name": r.Route_Name,
              "o_lat": r.geometry.coords[0][1], "o_lon": r.geometry.coords[0][0],
              "d_lat": r.geometry.coords[-1][1], "d_lon": r.geometry.coords[-1][0],
              "active": True} for _, r in g.iterrows()]
   codes, master, stats = rcs.assign(routes, rcs.load_admin())
   ```

---

## 7. Known, documented limitations (honest disclosure)

- **District-centre-approximated villages.** ~40 small rural terminals that OSM
  could not place precisely are represented by their **district town's**
  coordinate (correct district, approximate point — see
  `GAZETTEER_RECOVERY.md`). Several such villages therefore share one canonical
  stop and their routes carry an A/B suffix (e.g. *Khull Ahmadabad* and *Kulgam*
  both resolve to the Kulgam-town stop). This is the honest "approximate, never
  drop" policy; these stops are flagged in the master by their coordinate equal
  to the district centre and should be sharpened when a surveyed stop register
  arrives.
- **Ambiguous place names.** Where the *geocoder* placed a name (e.g. a village
  shared between two districts), the code follows that coordinate. The point-in-
  polygon district is always correct for the coordinate used.

These are data-availability limits, not methodology faults, and they are
surfaced rather than hidden.
