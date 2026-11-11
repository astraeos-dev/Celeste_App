"""
scripts/make_star_catalog.py — Generates star_catalog.py from the Yale Bright Star Catalogue
=============================================================================================
Reads the catalogue as the CDS distributes it (V/50, file catalog.gz, public
domain: https://cdsarc.cds.unistra.fr/ftp/V/50/ or a VizieR mirror) and keeps
the stars down to magnitude 6.5: J2000 position, visual magnitude, proper
motion, Bayer or Flamsteed designation. The usual names are those of
constellations.STARS (the bright stars and the old figures) and those already
in star_catalog.py, which the script reads before writing it again.

Usage: python scripts/make_star_catalog.py catalog.gz        (run from the repository)
"""
import gzip
import math
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from constellations import STARS                     # noqa: E402  (named stars)

MAG_LIMIT = 6.5
OUT = os.path.join(ROOT, "star_catalog.py")
GREEK = dict(Alp="α", Bet="β", Gam="γ", Del="δ", Eps="ε", Zet="ζ", Eta="η", The="θ", Iot="ι",
             Kap="κ", Lam="λ", Mu="μ", Nu="ν", Xi="ξ", Omi="ο", Pi="π", Rho="ρ", Sig="σ",
             Tau="τ", Ups="υ", Phi="φ", Chi="χ", Psi="ψ", Ome="ω")
SUP = {"1": "¹", "2": "²", "3": "³", "4": "⁴", "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹"}


def designation(raw, hr):
    """"  9Alp CMa" → "α CMa"; " 61    Cyg" → "61 Cyg"; no name → "HR 1234"."""
    m = re.match(r"^\s*(\d+)?\s*([A-Z][a-z]{1,2})?\s*(\d)?\s*([A-Z][A-Za-z]{2})\s*$", raw or "")
    if not m:
        return f"HR {hr}"
    flam, bayer, sup, const = m.groups()
    if bayer and bayer in GREEK:
        return f"{GREEK[bayer]}{SUP.get(sup, '')} {const}"
    if flam:
        return f"{flam} {const}"
    return f"HR {hr}"


def rows(path):
    """(designation, RA hours, Dec degrees, V, pm RA mas/yr, pm Dec mas/yr) of each star kept."""
    with gzip.open(path, "rt", encoding="latin-1") as f:
        for line in f:
            if len(line) < 107 or not line[75:77].strip() or not line[102:107].strip():
                continue                                  # the 14 entries that are not stars
            mag = float(line[102:107])
            if mag > MAG_LIMIT:
                continue
            ra = int(line[75:77]) + int(line[77:79]) / 60 + float(line[79:83]) / 3600
            dec = int(line[84:86]) + int(line[86:88]) / 60 + int(line[88:90]) / 3600
            if line[83] == "-":
                dec = -dec
            pm_ra = round(float(line[148:154] or 0) * 1000) if line[148:154].strip() else 0
            pm_dec = round(float(line[154:160] or 0) * 1000) if line[154:160].strip() else 0
            yield [designation(line[4:14], int(line[0:4])), ra, dec, mag, pm_ra, pm_dec, ""]


def sep(ra1, d1, ra2, d2):
    a1, a2, d1, d2 = math.radians(ra1 * 15), math.radians(ra2 * 15), math.radians(d1), math.radians(d2)
    c = math.sin(d1) * math.sin(d2) + math.cos(d1) * math.cos(d2) * math.cos(a1 - a2)
    return math.degrees(math.acos(max(-1.0, min(1.0, c))))


def main(path):
    cat = list(rows(path))
    named = {name: (ra, dec) for name, (ra, dec, _mag) in STARS.items()}
    try:                                                  # the names of the catalogue in place
        from star_catalog import CATALOG
        for _d, ra, dec, _mag, _pa, _pd, name in CATALOG:
            if name:
                named.setdefault(name, (ra, dec))
    except ImportError:
        pass
    for name, (ra, dec) in named.items():
        near = [c for c in cat if abs(c[2] - dec) < 0.3]
        best = min(near, key=lambda c: (sep(ra, dec, c[1], c[2]) > 0.05, c[3]))   # the brightest of a pair
        assert sep(ra, dec, best[1], best[2]) < 0.2, name
        best[6] = name
    cat.sort(key=lambda c: c[3])
    names = [c[6] for c in cat if c[6]]
    assert len(names) == len(set(names)), "duplicate names"
    with open(OUT, "w", encoding="utf-8") as f:
        f.write('"""\nstar_catalog.py — Stars of the sky map (generated, do not edit)\n'
                '===============================================================\n'
                f"Stars down to magnitude {MAG_LIMIT} of the Yale Bright Star Catalogue, 5th ed.\n"
                "(Hoffleit & Warren 1991, public domain): J2000 position (FK5), visual\n"
                "magnitude, proper motion (μα·cos δ, μδ in mas/year), Bayer or Flamsteed\n"
                "designation, and the usual name of the brightest ones.\n"
                "Written by scripts/make_star_catalog.py, the brightest first.\n"
                '"""\n\n'
                "# (designation, RA hours, Dec degrees, V mag, pm RA mas/yr, pm Dec mas/yr, name)\n"
                "CATALOG = (\n")
        for d, ra, dec, mag, pa, pd, name in cat:
            f.write(f"    ({d!r}, {ra:.6f}, {dec:+.5f}, {mag:.2f}, {pa}, {pd}, {name!r}),\n")
        f.write(")\n")
    print(f"{len(cat)} stars, {len(names)} named: {OUT}")


if __name__ == "__main__":
    main(sys.argv[1])
