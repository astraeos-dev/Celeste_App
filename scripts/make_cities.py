"""
scripts/make_cities.py — Villes pour la recherche de lieu (assets/cities.tsv.gz)
================================================================================
Télécharge la liste GeoNames des villes de plus de 15 000 habitants
(cities15000, licence CC BY 4.0, https://www.geonames.org) et la réduit à ce
dont la recherche de lieu a besoin, une ville par ligne, des plus peuplées aux
moins peuplées :

    nom  autres noms (séparés par |)  pays  région  latitude  longitude  altitude  population

Les autres noms (Londres, Moscou, Pékin…) ne sont gardés que pour les villes de
plus de 100 000 habitants, et seulement en écriture latine : le fichier reste
petit et la recherche se tape au clavier.

Usage : python scripts/make_cities.py      (quelques secondes, 3 Mo à télécharger)
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
    """Écriture latine seulement (lettres accentuées comprises), une majuscule en tête,
    sans codes en capitales, translittérations en minuscules ni surnoms."""
    if not text or len(text) < 3 or len(text) > 40 or not text[0].isupper() \
            or (text.isupper() and len(text) <= 4):
        return False
    if len(text.split()) > 3 or " of " in text:        # surnoms : « Paris of the North »
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
    print(f"{len(rows)} villes, {os.path.getsize(OUT) / 1e6:.2f} Mo : {OUT}")


if __name__ == "__main__":
    main()
