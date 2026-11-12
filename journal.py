"""
journal.py — The observation log
================================
What the observer saw, night after night: an entry per observation, with its
date (UT, shown in the place's time), its place, the target, the instrument, the seeing and the transparency
(1 to 5), the quality of the night computed by Céleste (night_quality.py) and
free notes. Kept in ~/.celeste/journal.json (or $CELESTE_DATA), on the user's
computer only; exported as CSV (a spreadsheet) on request.

No Qt: the interface (ui/observe.py) shows the entries in Observer › Journal
and adds one from the Targets list.
"""
import csv
import json
import os
import uuid
from datetime import datetime, timezone

import settings as prefs

FIELDS = ("date", "target", "place", "lat", "lon", "instrument", "seeing", "transparency",
          "quality", "notes")
SCALE = (1, 5)                 # seeing and transparency: 1 (poor) to 5 (excellent)


def journal_file():
    return os.path.join(prefs.USER_DIR, "journal.json")


def _clean(entry):
    """An entry with every field, the right types, and an id."""
    out = {"id": str(entry.get("id") or uuid.uuid4().hex)}
    date = entry.get("date")
    if isinstance(date, datetime):
        date = date.replace(microsecond=0).isoformat()
    out["date"] = str(date or datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0).isoformat())
    for key in ("target", "place", "instrument", "notes"):
        out[key] = str(entry.get(key) or "").strip()
    for key in ("lat", "lon"):
        value = entry.get(key)
        out[key] = None if value in (None, "") else float(value)
    for key in ("seeing", "transparency"):
        value = entry.get(key)
        out[key] = None if value in (None, "", 0) else max(SCALE[0], min(SCALE[1], int(value)))
    quality = entry.get("quality")
    out["quality"] = None if quality in (None, "") else int(quality)
    return out


def load(path=None):
    """The entries, newest first ([] without a journal or with an unreadable one)."""
    try:
        with open(path or journal_file(), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return []
    entries = [_clean(e) for e in data.get("entries", []) if isinstance(e, dict)]
    return sorted(entries, key=lambda e: e["date"], reverse=True)


def save(entries, path=None):
    """Writes the entries (through a temporary file: an interrupted write loses nothing)."""
    path = path or journal_file()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    partial = path + ".part"
    with open(partial, "w", encoding="utf-8") as f:
        json.dump({"version": 1, "entries": [_clean(e) for e in entries]}, f, ensure_ascii=False, indent=1)
    os.replace(partial, path)


def add(entry, path=None):
    """Adds an entry; returns it as kept (with its id)."""
    entries = load(path)
    kept = _clean(entry)
    entries.append(kept)
    save(entries, path)
    return kept


def update(entry, path=None):
    """Replaces the entry of the same id; returns it, or None when it is not in the journal."""
    entries = load(path)
    kept = _clean(entry)
    for i, old in enumerate(entries):
        if old["id"] == kept["id"]:
            entries[i] = kept
            save(entries, path)
            return kept
    return None


def delete(entry_id, path=None):
    """Removes an entry; True when it was there."""
    entries = load(path)
    left = [e for e in entries if e["id"] != entry_id]
    if len(left) == len(entries):
        return False
    save(left, path)
    return True


def export_csv(entries, path, headers=None):
    """
    The entries as a CSV file (UTF-8 with a BOM, which spreadsheets read):
    one line per entry, the columns of FIELDS (titled by *headers*, a dict
    field → title in the user's language, when given).
    """
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([(headers or {}).get(key, key) for key in FIELDS])
        for entry in entries:
            row = []
            for key in FIELDS:
                value = entry.get(key)
                row.append("" if value is None else value)
            writer.writerow(row)
    return path
