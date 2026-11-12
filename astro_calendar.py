"""
astro_calendar.py — The astronomical calendar
=============================================
Every event Céleste computes, over a period chosen by the user (a year by
default), in one list the interface lays out as a month grid and exports as an
iCalendar file (.ics):

- the phases of the Moon (new, first quarter, full, last quarter);
- the solar and lunar eclipses;
- conjunctions, oppositions and greatest elongations of the planets, those of
  the minor planets, the comets' perihelia and closest approaches;
- the Moon's events (perigee, apogee, conjunctions with the planets and the
  bright stars), the seasons and the Earth's perihelion and aphelion;
- the peaks of the meteor showers;
- the visible passes of the ISS, Tiangong and Hubble (the next 10 days only,
  from the orbits kept on disk: no download here).

No Qt: the interface (gui.py) runs collect() in the background.
"""
import math
from datetime import timedelta

from engine import AstroEngine

# The categories, in the order of the interface's filters
CATEGORIES = ("phases", "eclipses", "planets", "minor", "comets", "moon", "seasons", "meteors", "satellites")
DEFAULT_DAYS = 365
_PHASES = ("new_moon", "first_quarter", "full_moon", "last_quarter")


def collect(start, end, lat=None, lon=None, elevation_m=0.0, tz=0, satellite_elements=None,
            categories=CATEGORIES):
    """
    The events between *start* and *end* (UT datetimes), sorted by date.

    Args:
        lat, lon: the place, for the visibility of the events (None: not computed).
        tz: tzinfo of the place (the nights of the visibility).
        satellite_elements: {name: (line1, line2)} for the satellite passes, or None.
        categories: the categories to compute (the others are skipped, faster).

    Returns:
        list[dict]: date (UT), end (UT or None), category (one of CATEGORIES),
        kind (phase name, eclipse type, the engine's event type…), event (the
        engine's dict, for the details).
    """
    days = max(1, math.ceil((end - start).total_seconds() / 86400.0))
    wanted = set(categories)
    items = []
    if "phases" in wanted:
        jd0 = AstroEngine.julian_day(start) + AstroEngine._delta_t_days(AstroEngine.julian_day(start))
        jds, phases = AstroEngine._phases_between(jd0, jd0 + days)
        for jd, index in zip(jds, phases):
            date = AstroEngine._tt_to_datetime(jd, start)
            items.append({"date": date, "end": None, "category": "phases", "kind": _PHASES[index],
                          "event": {"phase": _PHASES[index]}})
    if "eclipses" in wanted:
        for ec in AstroEngine.find_eclipses(start, num_months=math.ceil(days / 29.53) + 1):
            date = ec.get("greatest", ec["date"])
            items.append({"date": date, "end": None, "category": "eclipses", "kind": ec["type"], "event": ec})
    events = []
    if wanted & {"planets", "minor"}:
        events += AstroEngine.find_conjunctions(start, num_days=days, minor_planets="minor" in wanted)
    if "moon" in wanted:
        events += AstroEngine.find_moon_events(start, num_days=days)
    if "seasons" in wanted:
        events += AstroEngine.find_seasons(start, num_days=days)
    if "meteors" in wanted:
        events += AstroEngine.find_meteor_showers(start, num_days=days)
    if "comets" in wanted:
        events += AstroEngine.find_comet_events(start, num_days=days)
    events = [e for e in events if e.get("group", "planets") in wanted]
    if lat is not None and events:
        AstroEngine.event_visibility(events, lat, lon, elevation_m, tz)
    for ev in events:
        items.append({"date": ev["date"], "end": None, "category": ev.get("group", "planets"),
                      "kind": ev["type"], "event": ev})
    if "satellites" in wanted and satellite_elements and lat is not None:
        span = min(days, 10)
        for p in AstroEngine.satellite_passes(satellite_elements, start, lat, lon, elevation_m, span):
            items.append({"date": p["start"], "end": p["end"], "category": "satellites", "kind": "pass",
                          "event": p})
    items = [i for i in items if start <= i["date"] < end]
    items.sort(key=lambda i: i["date"])
    return items


def by_day(items, local):
    """{date: [items]} by the local day of each event (*local*: UT datetime → local datetime)."""
    out = {}
    for item in items:
        out.setdefault(local(item["date"]).date(), []).append(item)
    return out


def month_grid(year, month):
    """The 6 weeks (Monday first) of the month's grid: lists of 7 dates."""
    from datetime import date
    first = date(year, month, 1)
    begin = first - timedelta(days=first.weekday())
    return [[begin + timedelta(days=7 * w + d) for d in range(7)] for w in range(6)]
