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


def test_minima_of_algol():
    """v4.18: the minima of Algol worth watching from the place (variables.py), none without a place."""
    items = astro_calendar.collect(START, START + timedelta(days=60), 49.63, -1.62, 0, ZoneInfo("Europe/Paris"),
                                   categories=("variables",))
    assert items and {i["category"] for i in items} == {"variables"}
    assert all(i["kind"] == "algol_minimum" and i["event"]["alt"] >= 15 for i in items)
    assert not astro_calendar.collect(START, START + timedelta(days=60), categories=("variables",))


def test_asteroids(tmp_path, monkeypatch):
    """v4.20: the notable approaches of CNEOS' list, the occultations whose band passes near the
    place (the IOTA predictions): from the files on disk only."""
    import shutil
    import zipfile
    import neo
    import occultations
    data = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    monkeypatch.setattr(neo, "CACHE", str(tmp_path / "neo_approaches.json"))
    monkeypatch.setattr(occultations, "CACHE_DIR", str(tmp_path / "occultations"))
    assert not astro_calendar.collect(START, START + timedelta(days=365), 48.85, 2.35,
                                      categories=("neo", "occultations"))
    shutil.copy(os.path.join(data, "cad_sample.json"), neo.CACHE)
    os.makedirs(occultations.CACHE_DIR)
    with zipfile.ZipFile(occultations.cache_path(2026), "w") as archive:
        archive.write(os.path.join(data, "occelmnt_sample.xml"), "2026-iota-all.xml")
    items = astro_calendar.collect(datetime(2026, 6, 1), datetime(2027, 6, 1), 48.85, 2.35,
                                   categories=("neo", "occultations"))
    approaches = [i["event"]["designation"] for i in items if i["category"] == "neo"]
    assert approaches == ["2016 NV", "506074"]                      # notable, in the period (not 2026 VP8)
    hidden = [i for i in items if i["category"] == "occultations"]
    assert [i["event"]["event"]["name"] for i in hidden] == ["Li", "Juno"]
    assert all(i["event"]["inside"] for i in hidden)
    near = astro_calendar.collect(datetime(2026, 6, 1), datetime(2027, 6, 1), 48.85, 2.35,
                                  categories=("occultations",), occultation_km=0)
    assert len(near) == 2                                            # both bands over Paris itself
    assert not astro_calendar.collect(datetime(2026, 6, 1), datetime(2027, 6, 1), categories=("occultations",))


def test_month_grid():
    weeks = astro_calendar.month_grid(2026, 12)
    assert len(weeks) == 6 and all(len(w) == 7 for w in weeks)
    assert weeks[0][0].isoformat() == "2026-11-30" and weeks[0][1].isoformat() == "2026-12-01"   # Monday first
