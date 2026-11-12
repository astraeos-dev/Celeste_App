"""
scripts/make_deep_sky.py — The deep-sky catalogue of the night planner (assets/deep_sky.csv.gz)
================================================================================================
Every object of OpenNGC (https://github.com/mattiaverga/OpenNGC, CC BY-SA 4.0)
that is not a star, at the same fixed commit as scripts/make_messier.py: the
NGC and IC catalogues and OpenNGC's addendum (Caldwell objects outside NGC/IC,
Melotte, Collinder…), about 12,000 objects.

    id;type;ra;dec;const;mag;major;minor;M;C;name

- id: "NGC 224", "IC 434"… (make_messier.designation)
- type: as in messier.csv (galaxy, globular_cluster, open_cluster, nebula,
  planetary_nebula, supernova_remnant, star_cloud, asterism, double_star),
  plus galaxy_group and dark_nebula
- ra, dec: J2000, degrees; mag: visual (blue when no visual one), empty when
  unknown; major, minor: arcminutes, empty when unknown
- M: Messier number (with M102 = NGC 5866), C: Caldwell number, empty otherwise
- name: the first English common name, if any

The output keeps OpenNGC's licence (CC BY-SA 4.0): see assets/README.md.

    python scripts/make_deep_sky.py
"""
import gzip
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_messier import M102, NAMES, ROOT, SEDS_MAGNITUDES, TYPES, degrees, designation, fetch  # noqa: E402

OUT = os.path.join(ROOT, "assets", "deep_sky.csv.gz")
TYPES = dict(TYPES, GPair="galaxy_group", GTrpl="galaxy_group", GGroup="galaxy_group", EmN="nebula",
             DrkN="dark_nebula")
LEFT_OUT = {"*", "Dup", "NonEx", "Nova"}                  # stars, duplicates, objects that do not exist


def caldwell(row):
    """Caldwell number from OpenNGC's identifiers ("C 020") or its addendum name ("C009")."""
    match = re.search(r"(?:^|,)C (\d{3})(?:,|$)", row["Identifiers"] or "") or re.fullmatch(r"C(\d{3})", row["Name"])
    return int(match.group(1)) if match else None


def main():
    rows = fetch("NGC.csv") + fetch("addendum.csv")
    out, caldwells = [], set()
    for r in rows:
        if r["Type"] in LEFT_OUT or not r["RA"] or r["Type"] not in TYPES:
            continue
        m = 102 if r["Name"] == M102 else (int(r["M"]) if r["M"] else None)
        c = caldwell(r)
        if c:
            caldwells.add(c)
        mag = r["V-Mag"] or r["B-Mag"] or (SEDS_MAGNITUDES.get(m) if m else "")
        name = NAMES[m] if m in NAMES else (r["Common names"] or "").split(",")[0].strip()
        out.append(";".join([
            designation(r["Name"]), TYPES[r["Type"]],
            f"{degrees(r['RA'], True):.5f}", f"{degrees(r['Dec'], False):.5f}", r["Const"],
            f"{float(mag):.1f}" if mag else "", r["MajAx"] or "", r["MinAx"] or "",
            str(m or ""), str(c or ""), name.replace(";", ",")]))
    missing = set(range(1, 110)) - caldwells
    data = ("id;type;ra;dec;const;mag;major;minor;M;C;name\n" + "\n".join(out) + "\n").encode("utf-8")
    with open(OUT, "wb") as f:
        f.write(gzip.compress(data, compresslevel=9, mtime=0))
    print(f"{len(out)} objects, {len(caldwells)} Caldwell (missing: {sorted(missing)}): {OUT}")


if __name__ == "__main__":
    main()
