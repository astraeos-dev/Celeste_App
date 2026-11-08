"""
scripts/make_cities.py — Cities for the place search (assets/cities.tsv.gz)
============================================================================
Downloads the GeoNames list of the cities of more than 15,000 inhabitants
(cities15000, CC BY 4.0 licence, https://www.geonames.org) and reduces it to
what the place search needs, one city per line, from the most populated to
the least:

    name  other names (separated by |)  country  region  latitude  longitude  elevation  population

The other names (Londres, Moscou, Pékin…) are kept only for the cities of more
than 100,000 inhabitants, and only in Latin script: the file stays small and
the search is typed on a keyboard.

Usage: python scripts/make_cities.py      (a few seconds, 3 MB to download)
"""
import gzip
import io
import os
import unicodedata
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "cities.tsv.gz")
BASE = "https://download.geonames.org/export/dump/"
ALT_NAMES_POPULATION = 100_000


def fetch(name):
    request = urllib.request.Request(BASE + name, headers={"User-Agent": "Celeste (make_cities.py)"})
    with urllib.request.urlopen(request, timeout=120) as resp:
        return resp.read()


def latin(text):
    """Latin script only (accented letters included), a capital first, no codes in
    capitals, lower-case transliterations or nicknames."""
    if not text or len(text) < 3 or len(text) > 40 or not text[0].isupper() \
            or (text.isupper() and len(text) <= 4):
        return False
    if len(text.split()) > 3 or " of " in text:        # nicknames: "Paris of the North"
        return False
    for ch in text:
        if ch.isalpha() and not unicodedata.name(ch, "").startswith("LATIN"):
            return False
    return True


def main():
    regions = {}
    for line in fetch("admin1CodesASCII.txt").decode("utf-8").splitlines():
        code, name, _ascii, _id = line.split("\t")
        regions[code] = name
    with zipfile.ZipFile(io.BytesIO(fetch("cities15000.zip"))) as archive:
        text = archive.read("cities15000.txt").decode("utf-8")
    rows = []
    for line in text.splitlines():
        f = line.split("\t")
        name, ascii_name, alternates = f[1], f[2], f[3]
        country, population = f[8], int(f[14] or 0)
        elevation = f[15] or f[16]
        elevation = int(elevation) if elevation and int(elevation) > -500 else 0
        others = []
        if population >= ALT_NAMES_POPULATION:
            for alt in alternates.split(","):
                if latin(alt) and alt not in (name, ascii_name) and alt not in others:
                    others.append(alt)
        if ascii_name != name and ascii_name not in others:
            others.insert(0, ascii_name)
        rows.append((population, "\t".join([
            name, "|".join(others), country, regions.get(f"{country}.{f[10]}", ""),
            f"{float(f[4]):.4f}", f"{float(f[5]):.4f}", str(elevation), str(population)])))
    rows.sort(key=lambda r: -r[0])
    data = ("\n".join(r[1] for r in rows) + "\n").encode("utf-8")
    with open(OUT, "wb") as out:
        out.write(gzip.compress(data, compresslevel=9, mtime=0))
    print(f"{len(rows)} cities, {os.path.getsize(OUT) / 1e6:.2f} MB: {OUT}")


if __name__ == "__main__":
    main()
