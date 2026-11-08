"""
scripts/make_star_catalog.py — Generates star_catalog.py from the Yale Bright Star Catalogue

Usage: python scripts/make_star_catalog.py bsc5.json . star_catalog.py
(bsc5.json: the full catalogue in JSON, for instance the one of the
brettonw/YaleBrightStarCatalog repository; the folder given holds constellations.py.)
"""
import json, math, re, sys
bsc_path, stars_module_dir, out_path = sys.argv[1:4]
sys.path.insert(0, stars_module_dir)
from constellations import STARS                     # the 45 named stars of the figures

GREEK = dict(Alp="α", Bet="β", Gam="γ", Del="δ", Eps="ε", Zet="ζ", Eta="η", The="θ", Iot="ι",
             Kap="κ", Lam="λ", Mu="μ", Nu="ν", Xi="ξ", Omi="ο", Pi="π", Rho="ρ", Sig="σ",
             Tau="τ", Ups="υ", Phi="φ", Chi="χ", Psi="ψ", Ome="ω")
SUP = {"1": "¹", "2": "²", "3": "³", "4": "⁴", "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹"}

def designation(raw, hr):
    m = re.match(r"^\s*(\d+)?\s*([A-Z][a-z]{1,2})?(\d)?\s*([A-Z][A-Za-z]{2})\s*$", raw or "")
    if not m:
        return f"HR {hr}"
    flam, bayer, sup, const = m.groups()
    if bayer and bayer in GREEK:
        return f"{GREEK[bayer]}{SUP.get(sup, '')} {const}"
    if flam:
        return f"{flam} {const}"
    return f"HR {hr}"

def hours(ra):
    h, m, s = re.match(r"(\d+)h\s*(\d+)m\s*([\d.]+)s", ra).groups()
    return int(h) + int(m) / 60 + float(s) / 3600

def degrees(dec):
    sg, d, m, s = re.match(r"([+-])(\d+)°\s*(\d+)′\s*(\d+)″", dec).groups()
    v = int(d) + int(m) / 60 + int(s) / 3600
    return -v if sg == "-" else v

def note_name(row):
    for note in row.get("Notes") or []:
        if note.get("Category") == "Star names":
            first = re.split(r"[;,.]", note.get("Remark", ""))[0].strip()
            if first and first.upper() == first and re.fullmatch(r"[A-Z' -]+", first):
                return " ".join(w.capitalize() for w in first.split())
    return ""

rows = [r for r in json.load(open(bsc_path, encoding="utf-8"))
        if r.get("Vmag") and float(r["Vmag"]) < 4.0 and r.get("RA") and r.get("Dec")]
cat = []
for r in rows:
    cat.append([designation(r.get("Name"), r["HR"]), hours(r["RA"]), degrees(r["Dec"]), float(r["Vmag"]),
                round(float(r.get("pmRA") or 0) * 1000), round(float(r.get("pmDE") or 0) * 1000), note_name(r)])

def sep(ra1, d1, ra2, d2):
    a1, a2, d1, d2 = math.radians(ra1 * 15), math.radians(ra2 * 15), math.radians(d1), math.radians(d2)
    c = math.sin(d1) * math.sin(d2) + math.cos(d1) * math.cos(d2) * math.cos(a1 - a2)
    return math.degrees(math.acos(max(-1.0, min(1.0, c))))

missing = []
for name, (ra, dec, mag) in STARS.items():
    best = min(cat, key=lambda c: sep(ra, dec, c[1], c[2]))
    if sep(ra, dec, best[1], best[2]) < 0.2:
        best[6] = name
    else:
        missing.append(name)
cat.sort(key=lambda c: c[3])
names = [c[6] for c in cat if c[6]]
assert len(names) == len(set(names)), "duplicate names"
with open(out_path, "w", encoding="utf-8") as f:
    f.write('"""\nstar_catalog.py — Bright stars of the sky map (generated, do not edit)\n'
            '=====================================================================\n'
            "Stars brighter than magnitude 4 of the Yale Bright Star Catalogue, 5th ed.\n"
            "(Hoffleit & Warren 1991, public domain): J2000 position (FK5), visual\n"
            "magnitude, proper motion (μα·cos δ, μδ in mas/year), Bayer or Flamsteed\n"
            "designation, and the usual name (that of constellations.STARS for the stars\n"
            "of the figures, else the first one of the catalogue's notes).\n"
            '"""\n\n'
            "# (designation, RA hours, Dec degrees, V mag, pm RA mas/yr, pm Dec mas/yr, name)\n"
            "CATALOG = (\n")
    for d, ra, dec, mag, pa, pd, name in cat:
        f.write(f"    ({d!r}, {ra:.6f}, {dec:+.5f}, {mag:.2f}, {pa}, {pd}, {name!r}),\n")
    f.write(")\n")
print(len(cat), "stars;", len(names), "named;", "not found:", missing)
