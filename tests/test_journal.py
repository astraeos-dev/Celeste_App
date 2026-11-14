"""
tests/test_journal.py — The observation log (journal.py)

Entries added, changed and removed, kept on disk newest first, read back
whatever the file holds, exported as CSV.
"""
import csv
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import journal  # noqa: E402


def _entry(**kw):
    entry = {"date": datetime(2026, 11, 12, 21, 30), "target": "M31 Galaxie d'Andromède",
             "place": "Cherbourg-en-Cotentin", "lat": 49.6333, "lon": -1.6167,
             "instrument": "Lunette 80/480", "seeing": 4, "transparency": 3, "quality": 72,
             "notes": "Bras de poussière visibles en vision décalée"}
    entry.update(kw)
    return entry


def test_add_and_read_back(tmp_path):
    path = str(tmp_path / "journal.json")
    kept = journal.add(_entry(), path)
    assert kept["id"] and kept["date"] == "2026-11-12T21:30:00"
    entries = journal.load(path)
    assert entries == [kept]
    assert entries[0]["seeing"] == 4 and entries[0]["quality"] == 72 and entries[0]["lat"] == 49.6333


def test_newest_first(tmp_path):
    path = str(tmp_path / "journal.json")
    journal.add(_entry(date=datetime(2026, 10, 1, 22, 0), target="M42"), path)
    journal.add(_entry(date=datetime(2026, 11, 12, 21, 30), target="M31"), path)
    journal.add(_entry(date=datetime(2026, 11, 1, 20, 0), target="M45"), path)
    assert [e["target"] for e in journal.load(path)] == ["M31", "M45", "M42"]


def test_update_and_delete(tmp_path):
    path = str(tmp_path / "journal.json")
    kept = journal.add(_entry(), path)
    kept["notes"] = "Ciel voilé vers minuit"
    kept["seeing"] = 9                                    # out of the scale: 5
    assert journal.update(kept, path)["seeing"] == 5
    assert journal.load(path)[0]["notes"] == "Ciel voilé vers minuit"
    assert journal.update(_entry(id="unknown"), path) is None
    assert journal.delete(kept["id"], path) and journal.load(path) == []
    assert not journal.delete(kept["id"], path)


def test_empty_values(tmp_path):
    path = str(tmp_path / "journal.json")
    kept = journal.add({"target": " Jupiter ", "seeing": "", "transparency": 0, "lat": ""}, path)
    assert kept["target"] == "Jupiter" and kept["seeing"] is None and kept["transparency"] is None
    assert kept["lat"] is None and kept["quality"] is None and kept["date"]


def test_unreadable_or_missing_file(tmp_path):
    path = tmp_path / "journal.json"
    assert journal.load(str(path)) == []
    path.write_text("{ not json", encoding="utf-8")
    assert journal.load(str(path)) == []
    path.write_text(json.dumps({"entries": ["text", {"target": "M13"}]}), encoding="utf-8")
    assert [e["target"] for e in journal.load(str(path))] == ["M13"]


def test_default_place_is_the_user_folder(monkeypatch, tmp_path):
    import settings as prefs
    monkeypatch.setattr(prefs, "USER_DIR", str(tmp_path))
    journal.add(_entry())
    assert os.path.isfile(tmp_path / "journal.json") and not os.path.exists(tmp_path / "journal.json.part")


def test_csv_export(tmp_path):
    path = str(tmp_path / "journal.json")
    journal.add(_entry(notes="Virgule, et « guillemets »"), path)
    out = journal.export_csv(journal.load(path), str(tmp_path / "journal.csv"),
                             headers={"date": "Date", "target": "Cible"})
    with open(out, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    assert rows[0][:2] == ["Date", "Cible"] and rows[0][2] == "place"
    assert rows[1][1] == "M31 Galaxie d'Andromède" and rows[1][-1] == "Virgule, et « guillemets »"
    assert len(rows) == 2
