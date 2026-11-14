"""
tests/test_month_sheet.py — The sky of the month, on one page to print (month_sheet.py, v4.19)
"""
import math
import os
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import month_sheet  # noqa: E402

PARIS = ZoneInfo("Europe/Paris")
CHERBOURG = (49.6333, -1.6167)


@pytest.fixture(scope="module")
def november():
    return month_sheet.collect(2026, 11, *CHERBOURG, 0.0, PARIS)


def _area(points):
    x, y = points[:, 0], points[:, 1]
    return 0.5 * abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))


def test_the_local_month():
    start, end = month_sheet.month_span(2026, 11, PARIS)
    assert start == datetime(2026, 10, 31, 23) and end == datetime(2026, 11, 30, 23)     # midnights in CET
    assert month_sheet.days_in_month(2026, 2) == 28 and month_sheet.days_in_month(2028, 2) == 29
    assert month_sheet.month_span(2026, 12, PARIS)[1] == datetime(2026, 12, 31, 23)


def test_the_map_and_when_it_shows(november):
    assert november["map_time"] == datetime(2026, 11, 15, 21)                           # 22:00 CET
    first, last = november["same_sky"]
    assert first.date() == datetime(2026, 11, 1).date() and last.date() == datetime(2026, 11, 30).date()
    assert (first - datetime(2026, 11, 1, 21)).total_seconds() / 60 == pytest.approx(55, abs=2)  # 4 min a day earlier
    assert (datetime(2026, 11, 30, 21) - last).total_seconds() / 60 == pytest.approx(59, abs=2)
    stars = november["scene"]["stars"]
    assert len(stars) > 500 and all(s["mag"] <= month_sheet.MAP_MAG and s["alt"] > 0 for s in stars)


def test_the_moon_and_the_events(november):
    assert len(november["moon_days"]) == 30
    phases = [i["kind"] for i in november["events"] if i["category"] == "phases"]
    assert sorted(phases) == sorted(["last_quarter", "new_moon", "first_quarter", "full_moon"])
    assert all(november["start"] <= i["date"] < november["end"] for i in november["events"])
    assert any(i["category"] == "variables" for i in november["events"])                 # Algol's minima
    assert not any(i["category"] == "satellites" for i in november["events"])


@pytest.mark.parametrize("phase, share, side", [(90.0, 0.5, 1), (180.0, 1.0, 0), (300.0, 0.25, -1), (45.0, 0.146, 1)])
def test_the_lit_part_of_the_moon(phase, share, side):
    points = month_sheet._moon_outline(phase, 1.0)
    assert _area(points) == pytest.approx(share * math.pi, rel=0.02)
    if side:
        assert (side * points[:, 0] >= -1e-9).all()                         # waxing: lit on the right (north)
        south = month_sheet._moon_outline(phase, 1.0, southern=True)
        assert (-side * south[:, 0] >= -1e-9).all()                         # the other way round in the south
    assert month_sheet._moon_outline(0.5, 1.0) is None                      # new moon


def test_the_page(november, tmp_path):
    from config import Config
    texts = {"kicker": "Le ciel du mois", "title": "Novembre 2026", "subtitle": "Cherbourg",
             "map_labels": {"title": "", "sun": "Soleil", "moon": "Lune", "horizon": "Horizon",
                            "cardinals": ["N", "NE", "E", "SE", "S", "SO", "O", "NO"], "planets": {}},
             "map_caption": "Le ciel le 15/11 à 22:00", "moon_title": "La Lune", "phases": ["Pleine lune · 24/11"],
             "planets_title": "Les planètes", "planets": ["Jupiter · le matin"], "events_title": "Évènements",
             "events": [(f"{d:02d}/11 21:00", f"Évènement {d}") for d in range(1, 45)], "no_events": "Rien",
             "footer": "Céleste"}
    path = tmp_path / "ciel.pdf"
    month_sheet.save(str(path), november, texts)
    data = path.read_bytes()
    assert data.startswith(b"%PDF") and data.count(b"/Type /Page\n") + data.count(b"/Type /Page>") <= 1
    from matplotlib.figure import Figure
    fig = month_sheet.draw(Figure(figsize=(8.27, 11.69)), november, texts)
    shown = [t.get_text() for t in fig.texts]
    assert "Novembre 2026" in shown and "Évènement 38" in shown and "Évènement 39" not in shown   # two columns of 19
    assert Config.THEME == "nuit"
