"""
scripts/make_messier.py — The Messier catalogue (assets/messier.csv)
=====================================================================
Extracts the 110 Messier objects from OpenNGC (https://github.com/mattiaverga/OpenNGC,
CC BY-SA 4.0), at a fixed commit so that the file can be rebuilt identically:

    M;id;type;ra;dec;const;mag;major;minor;name

- id: the NGC/IC (or other) designation of OpenNGC, without leading zeros (NGC 224)
- type: galaxy, globular_cluster, open_cluster, nebula, planetary_nebula,
  supernova_remnant, star_cloud, asterism, double_star
- ra, dec: J2000, degrees; mag: visual magnitude (blue when no visual one,
  SEDS for the seven clusters OpenNGC gives none);
  major, minor: apparent size in arcminutes (empty when unknown)
- name: the first English common name, if any

The output keeps OpenNGC's licence (CC BY-SA 4.0): see assets/README.md.

    python scripts/make_messier.py
"""
import csv
import io
import os
import re
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "messier.csv")
COMMIT = "be3cd6c5498806a2fbb2f7e0452ef802dbb02be0"          # OpenNGC master, 2026-11-08
BASE = f"https://raw.githubusercontent.com/mattiaverga/OpenNGC/{COMMIT}/database_files/"

TYPES = {"G": "galaxy", "GCl": "globular_cluster", "OCl": "open_cluster", "PN": "planetary_nebula",
         "Neb": "nebula", "HII": "nebula", "RfN": "nebula", "Cl+N": "nebula", "SNR": "supernova_remnant",
         "*Ass": "star_cloud", "Other": "asterism", "**": "double_star"}
# M102 is not certain; OpenNGC files it as a duplicate of M101. Most catalogues
# take it to be NGC 5866, the Spindle Galaxy.
M102 = "NGC5866"
# Visual magnitudes OpenNGC lacks, from the SEDS Messier database
# (http://www.messier.seds.org/data.html)
SEDS_MAGNITUDES = {22: 5.1, 35: 5.3, 62: 6.5, 69: 7.6, 70: 7.9, 71: 8.2, 107: 7.9}
# English common names where OpenNGC's differ from the usual ones (M11's is in
# French, M24's abbreviated) or are missing; M99's « Coma Pinwheel » is little used
NAMES = {11: "Wild Duck Cluster", 17: "Omega Nebula", 24: "Sagittarius Star Cloud", 42: "Orion Nebula",
         44: "Beehive Cluster", 76: "Little Dumbbell Nebula", 87: "Virgo A", 99: "",
         101: "Pinwheel Galaxy", 102: "Spindle Galaxy"}


def fetch(name):
    request = urllib.request.Request(BASE + name, headers={"User-Agent": "Celeste (make_messier.py)"})
    with urllib.request.urlopen(request, timeout=120) as resp:
        return list(csv.DictReader(io.StringIO(resp.read().decode("utf-8")), delimiter=";"))


def degrees(text, hours):
    sign = -1.0 if text.startswith("-") else 1.0
    parts = [float(p) for p in text.lstrip("+-").split(":")]
    value = parts[0] + parts[1] / 60.0 + (parts[2] if len(parts) > 2 else 0.0) / 3600.0
    return sign * value * (15.0 if hours else 1.0)


def designation(name):
    """NGC0224 → NGC 224, IC4715 → IC 4715, Mel022 → Mel 22, M040 → M 40."""
    match = re.match(r"([A-Za-z]+)0*(\d+.*)", name)
    return f"{match.group(1)} {match.group(2)}" if match else name


def main():
    rows = fetch("NGC.csv") + fetch("addendum.csv")
    by_m = {}
    for r in rows:
        if r["Name"] == M102:
            r = dict(r, M="102")
        if r["M"] and r["Type"] != "Dup":
            by_m.setdefault(int(r["M"]), r)
    assert sorted(by_m) == list(range(1, 111)), sorted(set(range(1, 111)) - set(by_m))
    with open(OUT, "w", encoding="utf-8", newline="") as out:
        out.write("M;id;type;ra;dec;const;mag;major;minor;name\n")
        for m in range(1, 111):
            r = by_m[m]
            mag = r["V-Mag"] or r["B-Mag"] or SEDS_MAGNITUDES[m]
            name = NAMES[m] if m in NAMES else (r["Common names"] or "").split(",")[0].strip()
            out.write(";".join([
                str(m), designation(r["Name"]), TYPES[r["Type"]],
                f"{degrees(r['RA'], True):.5f}", f"{degrees(r['Dec'], False):.5f}", r["Const"],
                f"{float(mag):.1f}" if mag else "", r["MajAx"] or "", r["MinAx"] or "", name]) + "\n")
    print(f"110 objects: {OUT}")


if __name__ == "__main__":
    main()
