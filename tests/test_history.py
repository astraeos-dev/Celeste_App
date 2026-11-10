"""
tests/test_history.py — The last calculations (history.py)
"""
import json
import os
import sys
from datetime import datetime

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import history  # noqa: E402


@pytest.fixture(autouse=True)
def user_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(history, "FILE", str(tmp_path / "user" / "history.json"))


def _item(minute=30, name="Cherbourg-en-Cotentin", lat=49.6333, tz="auto", second=0):
    return history.entry(datetime(2026, 11, 1, 21, minute, second), lat, -1.6167, 4.6, name, tz)


def test_entry():
    item = _item(second=42)
    assert item == {"date": "2026-11-01T21:30:42", "lat": 49.6333, "lon": -1.6167, "elev": 5,
                    "name": "Cherbourg-en-Cotentin", "tz": "auto"}
    assert history.when(item) == datetime(2026, 11, 1, 21, 30, 42)


def test_newest_first():
    entries = history.add(history.add([], _item(30)), _item(31))
    assert [e["date"][14:16] for e in entries] == ["31", "30"]


def test_same_calculation_moves_back_to_the_top():
    entries = []
    for item in (_item(30), _item(31), _item(30, second=20)):       # same minute, same place
        entries = history.add(entries, item)
    assert [e["date"] for e in entries] == ["2026-11-01T21:30:20", "2026-11-01T21:31:00"]


def test_another_place_or_zone_is_another_calculation():
    entries = []
    for item in (_item(30), _item(30, lat=48.8566, name="Paris"), _item(30, tz="Asia/Tokyo")):
        entries = history.add(entries, item)
    assert len(entries) == 3


def test_oldest_leave():
    entries = []
    for minute in range(history.MAX_ENTRIES + 5):
        entries = history.add(entries, _item(minute))
    assert len(entries) == history.MAX_ENTRIES
    assert entries[0]["date"][14:16] == "24" and entries[-1]["date"][14:16] == "05"


def test_saved_and_loaded():
    assert history.load() == []
    entries = history.add([], _item(name="Pékin"))
    assert history.save(entries) and history.load() == entries
    assert "Pékin" in open(history.FILE, encoding="utf-8").read()


def test_unreadable_entries_are_left_out():
    os.makedirs(os.path.dirname(history.FILE))
    good = _item()
    with open(history.FILE, "w", encoding="utf-8") as f:
        json.dump([good, {"date": "hier"}, dict(good, lat=123), "x", dict(good, date="2026-13-01T00:00:00")], f)
    assert history.load() == [good]
    with open(history.FILE, "w", encoding="utf-8") as f:
        f.write("{not json")
    assert history.load() == []
    with open(history.FILE, "w", encoding="utf-8") as f:
        f.write('{"date": 1}')
    assert history.load() == []


def test_save_reports_a_failure(tmp_path, monkeypatch):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    monkeypatch.setattr(history, "FILE", str(blocker / "history.json"))
    assert history.save([_item()]) is False
