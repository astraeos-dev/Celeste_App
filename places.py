"""
places.py — Recherche d'un lieu par son nom, hors ligne
=======================================================
Les villes de plus de 15 000 habitants de GeoNames (CC BY 4.0,
https://www.geonames.org), réduites par scripts/make_cities.py dans
assets/cities.tsv.gz : nom, autres noms (Londres, Moscou…), pays, région,
latitude, longitude, altitude, population.

La recherche ignore les accents, la casse, les tirets et les apostrophes ;
« Paris, US » ou « Paris US » restreint au pays (code ISO) ou à la région.
Indépendant de l'interface (pas de Qt).
"""
import functools
import gzip
import math
import os
import re
import unicodedata

CITIES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "cities.tsv.gz")


def normalize(text):
    """« Saint-Étienne » → « saint etienne » : sans accents, casse, tirets ni apostrophes."""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).casefold()
    text = re.sub(r"[-'’`.,()/]", " ", text)
    return " ".join(text.split())


@functools.lru_cache(maxsize=1)
def _cities():
    """[(fiche, noms normalisés)], des villes les plus peuplées aux moins peuplées."""
    with gzip.open(CITIES, "rt", encoding="utf-8") as f:
        rows = []
        for line in f:
            name, others, country, region, lat, lon, elev, population = line.rstrip("\n").split("\t")
            place = {"name": name, "country": country, "region": region, "lat": float(lat),
                     "lon": float(lon), "elevation": int(elev), "population": int(population)}
            names = [normalize(name)] + [normalize(o) for o in others.split("|") if o]
            rows.append((place, names))
    return rows


def _where(place, words):
    """La ville est-elle dans ce pays (code ISO) ou cette région (début du nom) ?"""
    region = normalize(place["region"])
    return all(w == place["country"].casefold() or region.startswith(w) for w in words)


def search(query, limit=12):
    """
    Villes dont un nom (ou l'un de ses mots) commence par *query* : d'abord
    les noms exacts, puis les débuts de nom, puis les mots ; les plus
    peuplées d'abord dans chaque groupe (« Pékin » : Beijing avant Pekin, Illinois).

    Returns:
        list[dict]: name, country, region, lat, lon, elevation (m), population.
    """
    city, _, where = (query or "").partition(",")
    key = normalize(city)
    words = normalize(where).split()
    if not where:                                   # « Paris us » : le dernier mot est un pays ?
        parts = key.split()
        if len(parts) > 1 and len(parts[-1]) == 2:
            key, words = " ".join(parts[:-1]), [parts[-1]]
    if not key:
        return []
    found = []
    for place, names in _cities():
        if words and not _where(place, words):
            continue
        rank = None                                 # 0 : un nom exact, 1 : son début, 2 : un mot
        for name in names:
            if name == key:
                rank = 0
                break
            if name.startswith(key):
                rank = 1
            elif rank is None and f" {key}" in f" {name}":
                rank = 2
        if rank is not None:
            found.append((rank, -place["population"], len(found), place))
    if not found and words and not where:           # « Le Havre » n'a pas de pays « re »
        return search(f"{query},", limit)
    found.sort(key=lambda r: r[:3])
    return [r[3] for r in found[:limit]]


def label(place):
    """« Cherbourg · Normandy · FR » : le nom, la région et le pays."""
    return " · ".join(p for p in (place["name"], place["region"], place["country"]) if p)


def nearest(lat, lon, max_km=25.0):
    """La ville la plus proche d'un point, à moins de *max_km* ; None sinon (en mer, au désert)."""
    best, best_d = None, max_km
    cos_lat = math.cos(math.radians(lat))
    for place, _names in _cities():
        dlat = place["lat"] - lat
        if abs(dlat) * 111.2 > best_d:
            continue
        dlon = (place["lon"] - lon + 180.0) % 360.0 - 180.0
        d = 111.2 * math.hypot(dlat, dlon * cos_lat)
        if d < best_d:
            best, best_d = place, d
    return best
