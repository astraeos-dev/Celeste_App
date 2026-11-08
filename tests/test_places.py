"""
tests/test_places.py — Search for a place by its name (places.py, offline)
===========================================================================
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import places  # noqa: E402


def _names(query, limit=3):
    return [(p["name"], p["country"]) for p in places.search(query, limit)]


def test_normalize():
    assert places.normalize("Saint-Étienne") == "saint etienne"
    assert places.normalize("  L’Haÿ-les-Roses ") == "l hay les roses"


def test_accents_case_and_hyphens():
    assert _names("cherbourg", 1) == [("Cherbourg", "FR")]
    assert _names("SAINT ETIENNE", 1) == [("Saint-Étienne", "FR")]
    assert _names("sao paulo", 1) == [("São Paulo", "BR")]


def test_other_names():
    """Londres, Moscou, Pékin: the French names find the city, the most populated first."""
    assert _names("Londres", 1) == [("London", "GB")]
    assert _names("moscou", 1) == [("Moscow", "RU")]
    assert _names("Pékin", 1) == [("Beijing", "CN")]


def test_exact_names_first_then_population():
    assert _names("paris", 2) == [("Paris", "FR"), ("Paris", "US")]
    assert _names("mexico", 1) == [("Mexico City", "MX")]


def test_country_or_region():
    assert _names("Paris, US", 1) == [("Paris", "US")]
    assert _names("paris us", 1) == [("Paris", "US")]
    assert _names("Paris, Texas", 1) == [("Paris", "US")]
    assert _names("Le Havre", 1) == [("Le Havre", "FR")]       # "re" is not a country


def test_fields_and_label():
    place = places.search("Cherbourg", 1)[0]
    assert abs(place["lat"] - 49.64) < 0.01 and abs(place["lon"] + 1.62) < 0.01
    assert place["elevation"] >= 0 and place["population"] > 15000
    assert places.label(place) == "Cherbourg · Normandy · FR"


def test_nothing():
    assert places.search("") == [] and places.search("zzzqqq") == []


def test_nearest():
    assert places.nearest(49.6333, -1.6167)["name"] == "Cherbourg"
    assert places.nearest(48.0, -30.0) is None                  # mid-Atlantic
    assert places.nearest(-36.85, 174.76)["name"] == "Auckland"  # across the 180° meridian
