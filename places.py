"""
places.py — Search for a place by its name, offline
====================================================
The cities of more than 15,000 inhabitants of GeoNames (CC BY 4.0,
https://www.geonames.org), reduced by scripts/make_cities.py into
assets/cities.tsv.gz: name, other names (Londres, Moscou…), country, region,
latitude, longitude, elevation, population.

The search ignores accents, case, hyphens and apostrophes; "Paris, US" or
"Paris US" narrows it to a country (ISO code) or a region. Independent of the
interface (no Qt).
"""
import functools
import gzip
import math
import os
import re
import unicodedata

CITIES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "cities.tsv.gz")


def normalize(text):
    """"Saint-Étienne" → "saint etienne": without accents, case, hyphens or apostrophes."""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).casefold()
    text = re.sub(r"[-'’`.,()/]", " ", text)
    return " ".join(text.split())


@functools.lru_cache(maxsize=1)
def _cities():
    """[(record, normalized names)], from the most populated cities to the least."""
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
    """Is the city in this country (ISO code) or this region (start of its name)?"""
    region = normalize(place["region"])
    return all(w == place["country"].casefold() or region.startswith(w) for w in words)


def search(query, limit=12):
    """
    Cities with a name (or a word of it) starting with *query*: exact names
    first, then name beginnings, then words; the most populated first in
    each group ("Pékin": Beijing before Pekin, Illinois).

    Returns:
        list[dict]: name, country, region, lat, lon, elevation (m), population.
    """
    city, _, where = (query or "").partition(",")
    key = normalize(city)
    words = normalize(where).split()
    if not where:                                   # "Paris us": is the last word a country?
        parts = key.split()
        if len(parts) > 1 and len(parts[-1]) == 2:
            key, words = " ".join(parts[:-1]), [parts[-1]]
    if not key:
        return []
    found = []
    for place, names in _cities():
        if words and not _where(place, words):
            continue
        rank = None                                 # 0: an exact name, 1: its beginning, 2: a word
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
    if not found and words and not where:           # "Le Havre" has no country "re"
        return search(f"{query},", limit)
    found.sort(key=lambda r: r[:3])
    return [r[3] for r in found[:limit]]


def label(place):
    """"Cherbourg · Normandy · FR": the name, the region and the country."""
    return " · ".join(p for p in (place["name"], place["region"], place["country"]) if p)


def nearest(lat, lon, max_km=25.0):
    """The city nearest to a point, within *max_km*; None otherwise (at sea, in a desert)."""
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
