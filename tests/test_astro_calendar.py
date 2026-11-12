"""
tests/test_astro_calendar.py — The astronomical calendar (astro_calendar.py)
"""
import os
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import astro_calendar  # noqa: E402

START = datetime(2026, 11, 12)


def test_a_year_of_events():
    items = astro_calendar.collect(START, START + timedelta(days=365), 49.63, -1.62, 0, ZoneInfo("Europe/Paris"))
    cats = {c: [i for i in items if i["category"] == c] for c in astro_calendar.CATEGORIES}
    assert 48 <= len(cats["phases"]) <= 50                          # ~12.4 lunations × 4
    assert len(cats["seasons"]) >= 4 and len(cats["meteors"]) >= 10
    assert any(i["kind"] == "solar" for i in cats["eclipses"])      # 2027-08-02 total eclipse
    assert [i["date"] for i in items] == sorted(i["date"] for i in items)
    assert all(START <= i["date"] < START + timedelta(days=365) for i in items)
    full = [i for i in cats["phases"] if i["kind"] == "full_moon"]
    assert full[0]["date"].date() == datetime(2026, 11, 24).date()   # full moon of 24 November 2026


def test_only_the_categories_asked():
    items = astro_calendar.collect(START, START + timedelta(days=60), categories=("phases", "seasons"))
    assert {i["category"] for i in items} <= {"phases", "seasons"}
    assert len([i for i in items if i["category"] == "phases"]) in (8, 9)


def test_month_grid():
    weeks = astro_calendar.month_grid(2026, 12)
    assert len(weeks) == 6 and all(len(w) == 7 for w in weeks)
    assert weeks[0][0].isoformat() == "2026-11-30" and weeks[0][1].isoformat() == "2026-12-01"   # Monday first
