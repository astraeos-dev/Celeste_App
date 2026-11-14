"""
scripts/make_constellations.py — Figures of the 88 constellations (assets/constellations.json)
===============================================================================================
Reads the constellation lines and label points of d3-celestial (Olaf Frohn,
BSD 3-Clause licence, https://github.com/ofrohn/d3-celestial: files
data/constellations.lines.json and data/constellations.json) and writes, for
each constellation, its lines as J2000 positions and the point of its name:

    {"Ori": {"center": [RA hours, Dec degrees],
             "lines": [[[RA hours, Dec degrees], ...], ...]}, ...}

Usage: python scripts/make_constellations.py constellations.lines.json constellations.json
With --names, prints the names in the interface languages instead (for locales/).

With --bounds constellations.bounds.json (the same project, the IAU boundaries
of Delporte, 1930, brought to J2000), writes assets/constellation_bounds.json
instead: {"Ori": [[[RA hours, Dec degrees], ...], ...]}, the outline of each
constellation (Serpens in two), for the constellation charts (4.24).
"""
import json
import os
import sys

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "constellations.json")
BOUNDS_OUT = os.path.join(os.path.dirname(OUT), "constellation_bounds.json")


def hours(longitude):
    """d3-celestial counts the right ascension in degrees from −180 to 180."""
    return round((longitude % 360.0) / 15.0, 5)


def figures(lines_path, names_path):
    with open(lines_path, encoding="utf-8") as f:
        lines = {feat["id"]: feat["geometry"]["coordinates"] for feat in json.load(f)["features"]}
    with open(names_path, encoding="utf-8") as f:
        points = {feat["id"]: feat for feat in json.load(f)["features"]}
    out = {}
    for key in sorted(points):
        lon, lat = points[key]["geometry"]["coordinates"]
        out[key] = {"center": [hours(lon), round(lat, 3)],
                    "lines": [[[hours(x), round(y, 4)] for x, y in line] for line in lines.get(key, [])]}
    return out, points


def bounds(path):
    """The outlines of the constellations: {IAU abbreviation: [[[RA hours, Dec degrees], ...], ...]}."""
    with open(path, encoding="utf-8") as f:
        features = json.load(f)["features"]
    out = {}
    for feat in features:
        geometry = feat["geometry"]
        polygons = geometry["coordinates"] if geometry["type"] == "MultiPolygon" else [geometry["coordinates"]]
        for polygon in polygons:
            ring = polygon[0]                                  # the outer ring (none has holes)
            out.setdefault(feat["id"], []).append([[hours(x), round(y, 4)] for x, y in ring])
    return dict(sorted(out.items()))


def main(argv):
    if "--bounds" in argv:
        out = bounds(argv[argv.index("--bounds") + 1])
        with open(BOUNDS_OUT, "w", encoding="utf-8") as f:
            json.dump(out, f, separators=(",", ":"))
            f.write("\n")
        print(f"{len(out)} constellations: {BOUNDS_OUT} ({os.path.getsize(BOUNDS_OUT) / 1000:.0f} kB)")
        return
    out, points = figures(argv[1], argv[2])
    if "--names" in argv:
        print(json.dumps({lang: {key: points[key]["properties"][lang] for key in sorted(points)}
                          for lang in ("fr", "en", "es", "de")}, ensure_ascii=False, indent=1))
        return
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, separators=(",", ":"))
        f.write("\n")
    segments = sum(len(line) - 1 for c in out.values() for line in c["lines"])
    print(f"{len(out)} constellations, {segments} segments: {OUT} ({os.path.getsize(OUT) / 1000:.0f} kB)")


if __name__ == "__main__":
    main(sys.argv)
