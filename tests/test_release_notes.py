"""
tests/test_release_notes.py — Changelog (CHANGELOG.md) and release notes
=========================================================================
Each published version takes its note from CHANGELOG.md (scripts/release_notes.py,
build workflow): the current version must have its section there, otherwise
the Release would not be published.
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import release_notes  # noqa: E402
from config import APP_VERSION  # noqa: E402
from updater import parse_version  # noqa: E402

SCRIPT = os.path.join(ROOT, "scripts", "release_notes.py")


def _changelog():
    with open(os.path.join(ROOT, "CHANGELOG.md"), encoding="utf-8") as f:
        return f.read()


def test_the_current_version_has_its_notes():
    notes = release_notes.notes(APP_VERSION)
    assert notes, f"CHANGELOG.md: add a \"## {APP_VERSION}\" section"
    assert all(line.startswith("- ") for line in notes.split("\n"))


def test_newest_first_without_duplicates():
    versions = [v for v, _ in release_notes.sections(_changelog())]
    assert versions[0] == APP_VERSION
    keys = [parse_version(v) for v in versions]
    assert keys == sorted(keys, reverse=True) and len(set(keys)) == len(keys)


def test_readable_in_the_update_window():
    """No bold and no code (the window of versions ≤ 4.4 would show them as they are),
    and short enough not to be cut (800 characters)."""
    for version, notes in release_notes.sections(_changelog()):
        assert "**" not in notes and "`" not in notes, version
        assert len(notes) <= 800, version


def test_wrapped_items_and_trailing_text():
    text = ("# Title\n\n## 2.1\n\n- one\n  two\n- three\n\nA paragraph.\n\n## 2.0\n\n- naïve\n\n"
            "Earlier versions…\n")
    assert release_notes.sections(text) == [("2.1", "- one two\n- three"), ("2.0", "- naïve")]
    assert release_notes.notes("2.0", text) == "- naïve" and release_notes.notes("1.9", text) is None


def test_script_writes_utf8(tmp_path):
    target = tmp_path / "notes.md"
    result = subprocess.run([sys.executable, SCRIPT, APP_VERSION, str(target)], capture_output=True)
    assert result.returncode == 0
    assert target.read_bytes().decode("utf-8") == release_notes.notes(APP_VERSION) + "\n"


def test_script_fails_without_a_section():
    result = subprocess.run([sys.executable, SCRIPT, "0.0.1"], capture_output=True)
    assert result.returncode == 1 and b"0.0.1" in result.stderr
