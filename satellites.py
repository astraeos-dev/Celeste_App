"""
satellites.py — Orbits of the bright satellites (TLE), downloaded and kept
============================================================================
Céleste predicts the visible passes of the International Space Station, the
Chinese station Tiangong and the Hubble Space Telescope. Their orbits change
every day (atmospheric drag, reboosts): the two-line elements (TLE) come from
CelesTrak (celestrak.org), or from AMSAT for the two stations when CelesTrak
does not answer, and are kept in ~/.celeste/satellites.tle. A pass computed
from elements a few days old is good to about a minute; past two weeks, Céleste
says the orbits are too old.

No Qt here: the interface calls refresh() in the background (gui.py).
"""
import calendar
import os
import re
import time
import urllib.request

import settings

# name in Céleste: NORAD catalogue number
SATELLITES = {"ISS": 25544, "Tiangong": 48274, "Hubble": 20580}
CELESTRAK = "https://celestrak.org/NORAD/elements/gp.php?CATNR={number}&FORMAT=tle"
AMSAT = "https://www.amsat.org/tle/current/nasabare.txt"
CACHE = os.path.join(settings.USER_DIR, "satellites.tle")
MAX_AGE_DAYS = 2.0          # refreshed after two days
STALE_DAYS = 14.0           # too old to trust beyond


class SatelliteError(RuntimeError):
    """No orbit could be downloaded."""


def _checksum_ok(line):
    """TLE line checksum: digits count, minus signs count 1, modulo 10."""
    if len(line) < 69 or not line[68].isdigit():
        return False
    total = sum(int(c) if c.isdigit() else 1 if c == "-" else 0 for c in line[:68])
    return total % 10 == int(line[68])


def parse(text):
    """{catalogue number: (line1, line2)} of the valid element sets of a TLE text
    (with or without name lines)."""
    lines = [line.rstrip() for line in text.splitlines()]
    found = {}
    for first, second in zip(lines, lines[1:]):
        if (first.startswith("1 ") and second.startswith("2 ") and first[2:7] == second[2:7]
                and _checksum_ok(first) and _checksum_ok(second)):
            found[int(first[2:7])] = (first, second)
    return found


def _get(url, timeout):
    request = urllib.request.Request(url, headers={"User-Agent": "Celeste (satellites.py)"})
    with urllib.request.urlopen(request, timeout=timeout) as resp:
        return resp.read().decode("ascii", "replace")


def download(timeout=15):
    """
    Downloads the elements of SATELLITES: CelesTrak one by one, then AMSAT for
    those still missing (it carries the two stations).

    Returns:
        dict: {name: (line1, line2)}.

    Raises:
        SatelliteError: when nothing could be downloaded.
    """
    found, errors = {}, []
    for name, number in SATELLITES.items():
        try:
            elements = parse(_get(CELESTRAK.format(number=number), timeout)).get(number)
        except Exception as exc:                            # network, refusal, rate limit
            errors.append(f"CelesTrak {number}: {exc}")
            elements = None
        if elements:
            found[name] = elements
    missing = [name for name in SATELLITES if name not in found]
    if missing:
        try:
            amsat = parse(_get(AMSAT, timeout))
            for name in missing:
                if SATELLITES[name] in amsat:
                    found[name] = amsat[SATELLITES[name]]
        except Exception as exc:
            errors.append(f"AMSAT: {exc}")
    if not found:
        raise SatelliteError("; ".join(errors) or "no elements")
    return found


def save(elements, path=None):
    path = path or CACHE
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="ascii", newline="\n") as f:
        for name, (line1, line2) in elements.items():
            f.write(f"{name}\n{line1}\n{line2}\n")


def load(path=None):
    """{name: (line1, line2)} kept on disk ({} when none)."""
    try:
        with open(path or CACHE, encoding="ascii") as f:
            text = f.read()
    except OSError:
        return {}
    by_number = parse(text)
    return {name: by_number[number] for name, number in SATELLITES.items() if number in by_number}


def cache_stamp(path=None):
    """When the elements on disk were last written (None without any)."""
    try:
        return os.path.getmtime(path or CACHE)
    except OSError:
        return None


def epoch_age_days(elements, now=None):
    """Age in days of the oldest element set (its epoch, not the download)."""
    now = time.time() if now is None else now
    ages = []
    for line1, _line2 in elements.values():
        match = re.match(r"(\d{2})(\d{3}\.\d+)", line1[18:32])
        year = 2000 + int(match.group(1)) if int(match.group(1)) < 57 else 1900 + int(match.group(1))
        start = calendar.timegm((year, 1, 1, 0, 0, 0))
        ages.append((now - (start + (float(match.group(2)) - 1.0) * 86400.0)) / 86400.0)
    return max(ages) if ages else float("inf")


def refresh(max_age_days=MAX_AGE_DAYS, timeout=15):
    """
    The elements to use: those on disk when recent enough, else downloaded
    (and kept). When the download fails, the elements on disk, however old.

    Returns:
        tuple: ({name: (line1, line2)}, error or None).
    """
    kept = load()
    if kept and len(kept) == len(SATELLITES) and epoch_age_days(kept) <= max_age_days:
        return kept, None
    try:
        elements = download(timeout)
    except SatelliteError as exc:
        return kept, exc
    save(elements)
    return elements, None
