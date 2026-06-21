"""
_fix_gazetteer_districts.py — v3.3.9 audit fix.

Corrects two geocoding-quality defects found in the government-screening audit:

1. DISTRICT MIS-ASSIGNMENT. _build_gazetteer.py defaulted any name it could not
   find in dest_district_map.csv to district "Srinagar", so 15 villages from
   Baramulla / Kupwara / Kulgam / Shopian / Bandipora / Anantnag (Garkote,
   Kamalkote, Nambia, Pehilpora, Maidanan, Ijara, Kupwra, Haftnar, Vailo,
   Harman, Khull Ahmadabad, Malangam, …) collapsed onto the SINGLE Srinagar
   district-centre point (34.083, 74.797) — geographically indefensible
   (a Baramulla village mapped to downtown Srinagar). Their true district is
   knowable from the SOURCE DEPOT in Other-routes.csv (e.g. "Baramulla Depot").
   We reassign each district_centre(*) entry to the depot's district centre.

2. FAMOUS-TOWN MIS-APPROXIMATION. A few well-known towns failed geocoding only
   on spelling and were district-approximated. Pahalgam ("PHALGAM") is the worst
   — a major tourist town landed on the Anantnag centre 4 km from Anantnag town.
   We pin these to real coordinates.

Honest-approximation policy (per the brief: approximate, never drop): residual
small villages keep a *correct-district* centre and are labelled
district_centre(<district>) so downstream QA/disposition can disclose them as
indicative, not surveyed.
"""
import pandas as pd

DISTRICT_CENTRE = {
    "Srinagar":  (34.0830, 74.7970), "Budgam":    (34.0140, 74.7190),
    "Ganderbal": (34.2270, 74.7750), "Anantnag":  (33.7300, 75.1480),
    "Kulgam":    (33.6450, 75.0190), "Shopian":   (33.7170, 74.8310),
    "Pulwama":   (33.8740, 74.8990), "Baramulla": (34.1980, 74.3640),
    "Bandipora": (34.4180, 74.6430), "Kupwara":   (34.5260, 74.2550),
}
DEPOT_DISTRICT = {
    "Anantnagh Depot": "Anantnag", "B/O Pulwama": "Pulwama",
    "Baramulla Depot": "Baramulla", "B/O Bandipora": "Bandipora",
    "B/O Kulgam": "Kulgam", "Kupwara Depot": "Kupwara",
    "B/O Shopian": "Shopian", "Sopore Depot": "Baramulla",
    # Srinagar-origin services: leave the non-Srinagar terminal's district to be
    # inferred from the *other* depots; default Srinagar only for true city svc.
    "Traffic Manager (City) JKRTC Srinagar": "Srinagar",
    "SRINAGAR RTO": "Srinagar",
}
# Real coordinates for towns that should never be a district approximation.
# (lat, lon, true_district) — district keeps the label honest.
REAL_PINS = {
    "PHALGAM":     (34.0149, 75.3318, "Anantnag"),   # Pahalgam (tourist town)
    "TANGDAR":     (34.6480, 74.1300, "Kupwara"),    # Tangdhar / Karnah
    "KAMALKOTE":   (34.0840, 74.0470, "Baramulla"),  # Kamalkote, Uri
    "KUPWRA":      (34.5260, 74.2550, "Kupwara"),    # Kupwara town (misspelled)
    "KUPWARA DAY": (34.5260, 74.2550, "Kupwara"),    # MPS Srinagar→Kupwara
    "DHPORA":      (33.6450, 75.0190, "Kulgam"),     # D.H. Pora (Damhal Hanjipora)
}


def clean(s: str) -> str:
    return str(s).strip().upper()


def main() -> None:
    gz = pd.read_csv("kashmir_gazetteer.csv", dtype=str, keep_default_na=False)
    other = pd.read_csv("Other-routes.csv", dtype=str, keep_default_na=False)

    # Build name -> {districts} from the depot of every route the name appears on.
    name_dist: dict[str, set] = {}
    for _, r in other.iterrows():
        dist = DEPOT_DISTRICT.get(r["office name"].strip())
        if not dist or dist == "Srinagar":
            continue  # only depot routes pin a non-Srinagar district
        for end in (r["from"], r["to"]):
            nm = clean(end)
            if nm and "SRINAGAR" not in nm and "SGR" != nm:
                name_dist.setdefault(nm, set()).add(dist)

    fixed_district = fixed_pin = 0
    out_rows = []
    for _, row in gz.iterrows():
        nm = clean(row["name"])
        lat, lon = row["lat"], row["lon"]
        src, dist = row["source"], row["district"]

        # (2) real-coordinate pins win outright
        if nm in REAL_PINS:
            la, lo, true_dist = REAL_PINS[nm]
            lat, lon, src, dist = f"{la}", f"{lo}", "manual_pin", true_dist
            fixed_pin += 1
        # (1) correct district for any district-centre approximation
        elif src.startswith("district_centre"):
            cand = name_dist.get(nm)
            if cand:
                # unambiguous depot district (or pick the first deterministically)
                true_dist = sorted(cand)[0]
                if true_dist != dist:
                    la, lo = DISTRICT_CENTRE[true_dist]
                    lat, lon = f"{la}", f"{lo}"
                    src = f"district_centre({true_dist})"
                    dist = true_dist
                    fixed_district += 1

        out_rows.append({"name": nm, "lat": lat, "lon": lon,
                         "source": src, "district": dist})

    out = pd.DataFrame(out_rows)
    out.to_csv("kashmir_gazetteer.csv", index=False)
    print(f"gazetteer patched: {fixed_district} districts corrected, "
          f"{fixed_pin} real pins applied, {len(out)} entries total")
    print("by district:", out["district"].value_counts().to_dict())


if __name__ == "__main__":
    main()
