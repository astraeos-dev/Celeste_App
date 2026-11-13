"""
neo.py — Near-Earth asteroids passing close to the Earth
========================================================
Every day the surveys find small asteroids passing near the Earth. The Center
for Near-Earth Object Studies (CNEOS, NASA/JPL) lists their close approaches
from the orbits of its Small-Body Database. Céleste asks its Close-Approach
Data API for the approaches within 0.05 au (19.5 lunar distances, the limit
of the "potentially hazardous" asteroids) from a week ago to a year ahead. It
keeps the list in ~/.celeste/neo_approaches.json and downloads it again after
12 hours: new asteroids are found every day, and passing ones are measured.

Most of these asteroids are a few metres to a few tens of metres across. The
size comes from the absolute magnitude H, for the albedos of the dark and
bright asteroids (0.05 to 0.25), unless a measured diameter is known. Those
of 140 m and more, or passing nearer than the Moon, are the notable ones of
the calendar.

How bright one gets depends on its phase as much as on its distance: an
asteroid coming from the Sun's side is seen as a crescent. For those that
could reach magnitude 16, the interface asks JPL Horizons for the asteroid's
geocentric positions and magnitude around its approach (ephemeris(); the
place is not sent). Céleste then computes where it is seen from the place
(seen_from(): the Earth's radius shifts a close asteroid by degrees) and
when it is high in a dark sky (windows()).

No Qt: the interface calls refresh() and ephemeris() in the background.
"""
import json
import math
import os
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

import numpy as np

import settings

CAD_URL = "https://ssd-api.jpl.nasa.gov/cad.api"
HORIZONS_URL = "https://ssd.jpl.nasa.gov/api/horizons.api"
SOURCE_URL = "https://cneos.jpl.nasa.gov/ca/"
CACHE = os.path.join(settings.USER_DIR, "neo_approaches.json")
EPHEMERIS_DIR = os.path.join(settings.USER_DIR, "neo")
MAX_AGE_HOURS = 12.0
EPHEMERIS_AGE_HOURS = 24.0
DIST_MAX_AU = 0.05                      # 19.5 lunar distances
PAST_DAYS, AHEAD_DAYS = 7, 366
AU_KM = 149597870.7
LUNAR_DISTANCE_KM = 384400.0
LD_AU = LUNAR_DISTANCE_KM / AU_KM
NOTABLE_H = 22.0                        # about 140 m and more
FAINTEST = 16.0                         # could get brighter than this: ask Horizons
ALBEDOS = (0.25, 0.05)                  # bright and dark asteroids
VISIBLE_ALT, DARK_SUN = 15.0, -12.0     # high enough, in a dark sky
WINDOW_DAYS = 2.0                       # ephemeris: two days either side of the approach
STEP_MINUTES = 20


class NeoError(RuntimeError):
    """The approaches or the ephemeris could not be read."""


# ── The close approaches (CNEOS) ──────────────────────────────────────────────

def _float(text):
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _sigma_minutes(text):
    """The 3-sigma uncertainty of the time, "< 00:01", "00:14" or "2_19:21" (d_hh:mm), in minutes."""
    if not text:
        return None
    text = text.strip()
    if text.startswith("<"):
        return 0.0
    match = re.fullmatch(r"(?:(\d+)_)?(\d+):(\d+)", text)
    if not match:
        return None
    days, hours, minutes = (int(g) if g else 0 for g in match.groups())
    return float(days * 1440 + hours * 60 + minutes)


def _name(fullname, designation):
    """"99942 Apophis" for " 99942 Apophis (2004 MN4)", "2026 VP8" for "(2026 VP8)";
    "137108 (1999 AN10)" as it is (numbered, not named)."""
    name = " ".join((fullname or "").split())
    if name.startswith("(") and name.endswith(")"):
        return name[1:-1]
    named = re.fullmatch(r"(\d+) ([^(].*?) \([^)]*\)", name)
    if named:
        return f"{named.group(1)} {named.group(2)}"
    return name or designation


def _ut(jd_tdb):
    """UT datetime of a Julian day in TDB."""
    from engine import _sky
    jd_ut = float(_sky()["ts"].tdb_jd(jd_tdb).ut1)
    return datetime(2000, 1, 1, 12) + timedelta(seconds=round((jd_ut - 2451545.0) * 86400.0))


def parse(payload):
    """
    The approaches of a Close-Approach Data API answer (dict), by date.

    Returns:
        list[dict]: designation, name, date (UT), distance_au and its 3-sigma
        range (distance_min_au, distance_max_au), speed (km/s, relative),
        h (absolute magnitude, or None), diameter_km (measured, or None),
        sigma_minutes (3-sigma uncertainty of the time, or None), orbit.
    """
    fields = payload.get("fields") or []
    found = []
    for row in payload.get("data") or []:
        item = dict(zip(fields, row))
        try:
            designation = str(item["des"]).strip()
            jd = float(item["jd"])
            distance = float(item["dist"])
        except (KeyError, TypeError, ValueError):
            continue
        found.append({
            "designation": designation, "name": _name(item.get("fullname"), designation),
            "date": _ut(jd), "distance_au": distance,
            "distance_min_au": _float(item.get("dist_min")) or distance,
            "distance_max_au": _float(item.get("dist_max")) or distance,
            "speed": _float(item.get("v_rel")), "h": _float(item.get("h")),
            "diameter_km": _float(item.get("diameter")),
            "sigma_minutes": _sigma_minutes(item.get("t_sigma_f")), "orbit": item.get("orbit_id"),
        })
    found.sort(key=lambda a: a["date"])
    return found


def _get(url, params, timeout):
    request = urllib.request.Request(f"{url}?{urllib.parse.urlencode(params)}",
                                     headers={"User-Agent": "Celeste (neo.py)"})
    with urllib.request.urlopen(request, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def cache_age_hours(path=None):
    try:
        return (time.time() - os.path.getmtime(path or CACHE)) / 3600.0
    except OSError:
        return None


_LOADED = {}                  # path: (its time, its approaches), read once


def load():
    """The approaches kept on disk (not to be changed: they are shared); [] without them."""
    try:
        stamp = os.path.getmtime(CACHE)
        kept = _LOADED.get(CACHE)
        if kept is not None and kept[0] == stamp:
            return kept[1]
        with open(CACHE, encoding="utf-8") as f:
            found = parse(json.load(f))
    except (OSError, ValueError):
        return []
    _LOADED[CACHE] = (stamp, found)
    return found


def cache_stamp():
    """When the kept list last changed (None without one)."""
    try:
        return os.path.getmtime(CACHE)
    except OSError:
        return None


def refresh(now=None, timeout=30, max_age_hours=MAX_AGE_HOURS):
    """
    The approaches from a week ago to a year ahead, downloaded again when the
    kept list is older than *max_age_hours* (12).

    Returns:
        tuple: (approaches, error or None) — the kept ones when the download fails.
    """
    age = cache_age_hours()
    if age is not None and age < max_age_hours:
        kept = load()
        if kept:
            return kept, None
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    params = {"date-min": f"{now - timedelta(days=PAST_DAYS):%Y-%m-%d}",
              "date-max": f"{now + timedelta(days=AHEAD_DAYS):%Y-%m-%d}",
              "dist-max": f"{DIST_MAX_AU}", "fullname": "true", "diameter": "true"}
    try:
        payload = _get(CAD_URL, params, timeout)
        if "fields" not in payload:
            raise NeoError(payload.get("message") or "unexpected answer")
        found = parse(payload)
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        with open(CACHE + ".part", "w", encoding="utf-8") as f:
            json.dump(payload, f)
        os.replace(CACHE + ".part", CACHE)
        return found, None
    except Exception as exc:                  # network, API refusal: the kept list
        return load(), str(exc)


# ── What the figures mean ─────────────────────────────────────────────────────

def lunar_distances(au):
    return au / LD_AU


def size_m(approach):
    """(smallest, largest) diameter in metres: the measured one twice, or from H for
    bright and dark surfaces; None without H."""
    if approach.get("diameter_km"):
        d = approach["diameter_km"] * 1000.0
        return d, d
    h = approach.get("h")
    if h is None:
        return None
    return tuple(1329e3 / math.sqrt(p) * 10.0 ** (-h / 5.0) for p in ALBEDOS)


def best_magnitude(approach):
    """The magnitude it would reach seen full at its approach: a bound (it is seldom
    seen full); None without H."""
    h = approach.get("h")
    return None if h is None else h + 5.0 * math.log10(approach["distance_au"])


def notable(approach):
    """Large (H ≤ 22, about 140 m and more) or passing nearer than the Moon."""
    h = approach.get("h")
    return approach["distance_au"] <= LD_AU or (h is not None and h <= NOTABLE_H)


def worth_an_ephemeris(approach):
    """Could get brighter than magnitude 16: worth asking Horizons."""
    best = best_magnitude(approach)
    return best is not None and best <= FAINTEST


# ── Where it is seen (JPL Horizons) ───────────────────────────────────────────

def _command(designation):
    """Horizons' name of a small body: its number ("99942;") or designation ("DES=2016 NV;")."""
    return f"'{designation};'" if designation.isdigit() else f"'DES={designation};'"


def parse_ephemeris(text):
    """
    The rows of a Horizons observer table (quantities 1, 9, 20 as CSV, UT).

    Returns:
        list[dict]: date (UT), ra (hours), dec (degrees), geocentric and
        astrometric (ICRF); mag (None when Horizons has no magnitude),
        distance_au.
    """
    start, end = text.find("$$SOE"), text.find("$$EOE")
    if start < 0 or end < 0:
        raise NeoError(" ".join(text.split())[:200] or "no ephemeris")
    header = next((line for line in reversed(text[:start].splitlines()) if "Date__(UT)" in line), "")
    names = [c.strip() for c in header.split(",")]

    def column(*prefixes):
        return next((i for i, n in enumerate(names) if n.startswith(prefixes)), None)
    ra_i, dec_i, mag_i, dist_i = column("R.A."), column("DEC"), column("APmag", "T-mag"), column("delta")
    if None in (ra_i, dec_i, dist_i):
        raise NeoError("unexpected ephemeris columns")
    rows = []
    for line in text[start + 5:end].splitlines():
        cells = [c.strip() for c in line.split(",")]
        if len(cells) <= max(ra_i, dec_i, dist_i):
            continue
        try:
            date = datetime.strptime(cells[0], "%Y-%b-%d %H:%M")
            rows.append({"date": date, "ra": float(cells[ra_i]) / 15.0, "dec": float(cells[dec_i]),
                         "mag": _float(cells[mag_i]) if mag_i is not None else None,
                         "distance_au": float(cells[dist_i])})
        except ValueError:
            continue
    return rows


def _ephemeris_path(designation, start, end):
    safe = re.sub(r"[^A-Za-z0-9]+", "_", designation)
    return os.path.join(EPHEMERIS_DIR, f"{safe}_{start:%Y%m%d%H%M}_{end:%Y%m%d%H%M}.txt")


def ephemeris(approach, timeout=30):
    """
    Horizons' geocentric positions and magnitude of the asteroid from two
    days before its approach to two days after, every 20 minutes; kept a day.

    Returns:
        list[dict]: parse_ephemeris()'s rows.
    """
    middle = approach["date"].replace(second=0, microsecond=0)
    start = middle - timedelta(days=WINDOW_DAYS)
    end = middle + timedelta(days=WINDOW_DAYS)
    path = _ephemeris_path(approach["designation"], start, end)
    age = cache_age_hours(path)
    if age is not None and age < EPHEMERIS_AGE_HOURS:
        try:
            with open(path, encoding="utf-8") as f:
                return parse_ephemeris(f.read())
        except (OSError, NeoError):
            pass
    params = {"format": "json", "COMMAND": _command(approach["designation"]), "OBJ_DATA": "'NO'",
              "MAKE_EPHEM": "'YES'", "EPHEM_TYPE": "'OBSERVER'", "CENTER": "'500@399'",
              "START_TIME": f"'{start:%Y-%m-%d %H:%M}'", "STOP_TIME": f"'{end:%Y-%m-%d %H:%M}'",
              "STEP_SIZE": f"'{STEP_MINUTES} m'", "QUANTITIES": "'1,9,20'", "ANG_FORMAT": "'DEG'",
              "EXTRA_PREC": "'YES'", "TIME_TYPE": "'UT'", "CSV_FORMAT": "'YES'"}
    payload = _get(HORIZONS_URL, params, timeout)
    text = payload.get("result") or payload.get("error") or ""
    rows = parse_ephemeris(text)
    os.makedirs(EPHEMERIS_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return rows


def seen_from(rows, lat, lon, elevation_m=0.0):
    """
    The ephemeris seen from the place: the geocentric positions moved to the
    place (the parallax of a close asteroid reaches degrees), then turned to
    the horizon.

    Returns:
        list[dict]: the rows with alt, az (degrees), sun (the Sun's altitude),
        ra, dec (from the place, astrometric), distance_km (from the place),
        rate (its motion on the sky, arcseconds a minute).
    """
    if not rows:
        return []
    from skyfield.api import wgs84
    from skyfield.framelib import itrs
    from engine import AstroEngine, _sky
    sky = _sky()
    times = sky["ts"].ut1_jd(np.array([AstroEngine.julian_day(r["date"]) for r in rows]))
    place = wgs84.latlon(lat, lon, elevation_m=elevation_m)
    ra = np.radians([r["ra"] * 15.0 for r in rows])
    dec = np.radians([r["dec"] for r in rows])
    dist = np.array([r["distance_au"] for r in rows])
    geo = dist * np.array([np.cos(dec) * np.cos(ra), np.cos(dec) * np.sin(ra), np.sin(dec)])
    topo = geo - place.at(times).position.au
    km = np.linalg.norm(topo, axis=0)
    unit = topo / km
    t_ra = np.degrees(np.arctan2(topo[1], topo[0])) % 360.0
    t_dec = np.degrees(np.arcsin(unit[2]))
    # to the horizon: the Earth-fixed frame (precession, nutation, the Earth's turn), then up, east, north
    fixed = np.einsum("ij...,j...->i...", itrs.rotation_at(times), unit)
    phi, lam = math.radians(lat), math.radians(lon)
    up = np.array([math.cos(phi) * math.cos(lam), math.cos(phi) * math.sin(lam), math.sin(phi)])
    east = np.array([-math.sin(lam), math.cos(lam), 0.0])
    north = np.array([-math.sin(phi) * math.cos(lam), -math.sin(phi) * math.sin(lam), math.cos(phi)])
    alt = np.degrees(np.arcsin(np.clip(up @ fixed, -1.0, 1.0)))
    az = np.degrees(np.arctan2(east @ fixed, north @ fixed)) % 360.0
    sun = (sky["earth"] + place).at(times).observe(sky["sun"]).apparent().altaz()[0].degrees
    cosines = np.clip((unit[:, 1:] * unit[:, :-1]).sum(0), -1.0, 1.0)
    minutes = np.array([(b["date"] - a["date"]).total_seconds() / 60.0 for a, b in zip(rows, rows[1:])])
    rate = np.degrees(np.arccos(cosines)) * 3600.0 / np.maximum(minutes, 1e-9)
    rate = np.concatenate([rate[:1], (rate[:-1] + rate[1:]) / 2.0, rate[-1:]]) if len(rows) > 1 else [0.0]
    return [dict(r, alt=float(a), az=float(z), sun=float(s), ra=float(ra_) / 15.0, dec=float(de),
                 distance_km=float(k * AU_KM), rate=float(v))
            for r, a, z, s, ra_, de, k, v in zip(rows, alt, az, sun, t_ra, t_dec, km, rate)]


def windows(seen, min_alt=VISIBLE_ALT, dark_sun=DARK_SUN):
    """
    The stretches of the ephemeris when the asteroid is high enough in a dark
    sky.

    Returns:
        list[dict]: start, end (UT), best (the row where it looks brightest
        through the air: its magnitude plus 0.25 per airmass).
    """
    def through_the_air(row):
        return (row["mag"] if row["mag"] is not None else 0.0) + 0.25 / math.sin(math.radians(row["alt"]))

    found, current = [], []
    for row in list(seen) + [None]:
        if row is not None and row["alt"] >= min_alt and row["sun"] <= dark_sun:
            current.append(row)
            continue
        if current:
            found.append({"start": current[0]["date"], "end": current[-1]["date"],
                          "best": min(current, key=through_the_air)})
            current = []
    return found
