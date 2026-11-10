"""
history.py — The last calculations
===================================
The dates and places the user stopped on, the most recent first, kept in
~/.celeste/history.json: one click brings a calculation back (date, place,
elevation, time zone). Independent of the interface (no Qt).

An entry:
    {"date": "2026-11-01T21:30:00",        UT, to the second
     "lat": 49.6333, "lon": -1.6167, "elev": 0,
     "name": "Cherbourg-en-Cotentin",      "" for typed coordinates
     "tz": "auto"}                         IANA time zone, or "auto"
"""
import json
import os
from datetime import datetime

import settings

FILE = os.path.join(settings.USER_DIR, "history.json")
MAX_ENTRIES = 20


def entry(dte, lat, lon, elev=0, name="", tz="auto"):
    """A calculation as it is stored; *dte*: datetime in UT, without time zone."""
    return {"date": dte.replace(microsecond=0).isoformat(), "lat": round(float(lat), 4),
            "lon": round(float(lon), 4), "elev": int(round(float(elev))),
            "name": str(name or ""), "tz": str(tz or "auto")}


def when(item):
    """The date of an entry (datetime in UT, without time zone)."""
    return datetime.fromisoformat(item["date"])


def _key(item):
    """Two calculations are the same at the same minute, place and time zone."""
    return (item["date"][:16], item["lat"], item["lon"], item["elev"], item["tz"])


def _valid(item):
    try:
        when(item)
        return (isinstance(item["name"], str) and isinstance(item["tz"], str)
                and -90 <= float(item["lat"]) <= 90 and -180 <= float(item["lon"]) <= 180
                and float(item["elev"]) == float(item["elev"]))
    except (KeyError, TypeError, ValueError):
        return False


def add(entries, item):
    """*entries* with *item* first: an identical calculation moves back to the
    top instead of appearing twice, and the oldest ones leave beyond MAX_ENTRIES."""
    key = _key(item)
    return ([item] + [e for e in entries if _key(e) != key])[:MAX_ENTRIES]


def load():
    """The saved history; [] without a file, and without the entries that cannot be read."""
    try:
        with open(FILE, "r", encoding="utf-8") as f:
            entries = json.load(f)
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(entries, list):
        return []
    return [e for e in entries if isinstance(e, dict) and _valid(e)][:MAX_ENTRIES]


def save(entries):
    """Writes the history; False when the file cannot be written."""
    try:
        os.makedirs(os.path.dirname(FILE), exist_ok=True)
        with open(FILE, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False, indent=2)
        return True
    except OSError:
        return False
