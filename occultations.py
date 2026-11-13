"""
occultations.py — Stars hidden by asteroids, seen from the place
================================================================
When an asteroid passes in front of a star, its shadow sweeps the Earth in a
band as wide as the asteroid, from a few kilometres to a few hundred: there,
the star disappears for a few seconds. Timed by observers spread across the
band, these occultations give the asteroid's size and shape to a kilometre.

The predictions are those of the International Occultation Timing Association
(IOTA): the "occelmnt" files that Steve Preston computes each year with Occult
(David Herald), from the stars of Gaia DR3 and the orbits of JPL. The IOTA
selection, about 5,000 events a year with bright enough stars and well-known
paths, is at asteroidoccultation.com (<year>-iota.zip, about 1 MB). Céleste
keeps the files in ~/.celeste/occultations/ and downloads them again after
30 days.

Each event gives the shadow's path as Besselian elements: on the fundamental
plane, through the Earth's centre and perpendicular to the star, the shadow's
axis is at X(t), Y(t) Earth radii. These are cubic polynomials of the time in
hours from the event's middle (UT). X points east and Y north of the star's
direction of date. Céleste puts the place on the same plane (ξ, η), turning
with the Earth, and finds when the shadow passes nearest. The place is inside
the band when that distance is under the asteroid's radius. The distance on
the ground, and the band's width there, follow from the local slope of the
projection: the band is wider on the ground when the star is low.

These predictions are made months ahead. The band may move by more than its
width when the asteroid's orbit is refined. OccultWatcher gives the updated
paths during the two months before an event.

No Qt: the interface runs refresh() and near() in the background.
"""
import html
import io
import math
import os
import re
import time
import urllib.request
import zipfile
from datetime import datetime, timedelta

import numpy as np

import settings

URL = "https://asteroidoccultation.com/{year}/{year}-iota.zip"
SOURCE_URL = "https://asteroidoccultation.com/"
CACHE_DIR = os.path.join(settings.USER_DIR, "occultations")
MAX_AGE_DAYS = 30.0           # downloaded again after a month
MAX_KM = 100.0                # bands passing within this distance of the place
MIN_ALT = 10.0                # the star at least this high…
DARK_SUN = -12.0              # …in a dark enough sky
EARTH_KM = 6378.137           # the elements' unit, the Earth's equatorial radius
_FLATTENING = 1.0 / 298.257223563
_SIDEREAL = math.radians(15.04106864)     # the Earth turns under the stars, radians per hour
_SOLAR = math.radians(15.0)               # and under the Sun
_KM_PER_RAD = 6371.0                      # ground steps for the local slope (mean radius)
_MAX_UNZIPPED = 64 * 1024 * 1024          # a year's file is about 3 MB unzipped
_EVENT = re.compile(r"<Event>(.*?)</Event>", re.S)
_FIELD = re.compile(r"<(Elements|Earth|Star|Object|Errors|ID)>(.*?)</\1>", re.S)


class OccultationError(RuntimeError):
    """A year's predictions could not be read."""


# ── The predictions ───────────────────────────────────────────────────────────

def _float(text, default=None):
    try:
        return float(text)
    except (TypeError, ValueError):
        return default


def parse(text):
    """
    The events of an occelmnt text (Occult's XML), those that cannot be read
    left out.

    Returns:
        list[dict]: id; name, number (text, empty when unnumbered); middle
        (UT datetime of the elements' origin); elements (X, Y, dX, dY, d2X,
        d2Y, d3X, d3Y: Earth radii and hours); substar, subsolar (longitude
        east and latitude at the middle, degrees); star (catalogue name),
        star_mag (V), ra, dec (of date: hours, degrees), ra2000, dec2000;
        mag (the asteroid's), diameter_km, distance_au, max_duration (s),
        orbit (its source).
    """
    events = []
    for block in _EVENT.findall(text):
        fields = {tag: value.strip() for tag, value in _FIELD.findall(block)}
        try:
            el = fields["Elements"].split(",")
            earth = fields["Earth"].split(",")
            star = fields["Star"].split(",")
            obj = fields["Object"].split(",")
            year, month, day, hours = int(el[2]), int(el[3]), int(el[4]), float(el[5])
            event = {
                "id": fields.get("ID", "").split(",")[0],
                "number": obj[0].strip(), "name": html.unescape(obj[1].strip()),
                "middle": datetime(year, month, day) + timedelta(hours=hours),
                "elements": tuple(float(v) for v in el[6:14]),
                "substar": (float(earth[0]), float(earth[1])),
                "subsolar": (float(earth[2]), float(earth[3])),
                "star": html.unescape(star[0].strip()), "star_mag": _float(star[4]),
                "ra2000": float(star[1]), "dec2000": float(star[2]),
                "ra": float(star[9]), "dec": float(star[10]),
                "mag": _float(obj[2]), "diameter_km": float(obj[3]), "distance_au": _float(obj[4]),
                "max_duration": _float(el[1]), "orbit": el[0].strip(),
            }
        except (KeyError, IndexError, ValueError):
            continue
        if len(event["elements"]) == 8 and event["diameter_km"] > 0:
            events.append(event)
    return events


def read_zip(data):
    """The events of a downloaded <year>-iota.zip (bytes)."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            infos = [i for i in archive.infolist() if i.filename.lower().endswith(".xml")]
            if not infos:
                raise OccultationError("no prediction file in the archive")
            if infos[0].file_size > _MAX_UNZIPPED:
                raise OccultationError("prediction file too large")
            text = archive.read(infos[0]).decode("utf-8", "replace")
    except zipfile.BadZipFile as exc:
        raise OccultationError(f"unreadable archive ({exc})") from exc
    return parse(text)


def cache_path(year):
    return os.path.join(CACHE_DIR, f"{year}-iota.zip")


def cache_age_days(year):
    """Age of the kept file of *year* in days; None without one."""
    try:
        return (time.time() - os.path.getmtime(cache_path(year))) / 86400.0
    except OSError:
        return None


_LOADED = {}                  # path: (its time, its events), read once


def load(year):
    """The events of the kept file of *year* (not to be changed: they are shared); [] without one."""
    path = cache_path(year)
    try:
        stamp = os.path.getmtime(path)
        kept = _LOADED.get(path)
        if kept is not None and kept[0] == stamp:
            return kept[1]
        with open(path, "rb") as f:
            events = read_zip(f.read())
    except (OSError, OccultationError):
        return []
    _LOADED[path] = (stamp, events)
    return events


def cache_stamp():
    """When the kept files last changed (None without any): the interface computes again then."""
    try:
        return max((entry.stat().st_mtime for entry in os.scandir(CACHE_DIR) if entry.name.endswith(".zip")),
                   default=None)
    except OSError:
        return None


def _download(year, timeout):
    request = urllib.request.Request(URL.format(year=year), headers={"User-Agent": "Celeste (occultations.py)"})
    with urllib.request.urlopen(request, timeout=timeout) as resp:
        return resp.read()


def refresh(years, timeout=60):
    """
    The events of *years*, from the kept files when younger than a month,
    else downloaded again (the kept ones when the download fails).

    Returns:
        tuple: (events sorted by their middle, {year: reason} for the years
        with no predictions: not published yet, or no connection).
    """
    events, missing = [], {}
    for year in sorted(set(years)):
        age = cache_age_days(year)
        found = load(year) if age is not None and age < MAX_AGE_DAYS else []
        if not found:
            try:
                data = _download(year, timeout)
                found = read_zip(data)
                if not found:
                    raise OccultationError("no event in the file")
                os.makedirs(CACHE_DIR, exist_ok=True)
                part = cache_path(year) + ".part"
                with open(part, "wb") as f:
                    f.write(data)
                os.replace(part, cache_path(year))
            except Exception as exc:              # network, not published yet (404), damaged file
                found = load(year)
                if not found:
                    missing[year] = str(exc)
        events += found
    events.sort(key=lambda e: e["middle"])
    return events, missing


def years_between(start, end):
    """The years of the files covering *start* to *end*."""
    return list(range(start.year, end.year + 1))


# ── The band, seen from the place ─────────────────────────────────────────────

def mag_drop(star_mag, asteroid_mag):
    """How much fainter the star and the asteroid get together when the star is hidden."""
    if star_mag is None or asteroid_mag is None:
        return None
    both = -2.5 * math.log10(10.0 ** (-0.4 * star_mag) + 10.0 ** (-0.4 * asteroid_mag))
    return asteroid_mag - both


def _place(lat, lon, elevation_m=0.0):
    """ρ cos φ′ and ρ sin φ′ of the place, in Earth radii (WGS84)."""
    phi = math.radians(lat)
    c = 1.0 / math.sqrt(math.cos(phi) ** 2 + (1.0 - _FLATTENING) ** 2 * math.sin(phi) ** 2)
    s = (1.0 - _FLATTENING) ** 2 * c
    h = elevation_m / 1000.0 / EARTH_KM
    return (c + h) * math.cos(phi), (s + h) * math.sin(phi)


def _shadow(e, tau):
    """X, Y of the shadow's axis at *tau* hours from the middle, and their first two derivatives."""
    x, y, dx, dy, d2x, d2y, d3x, d3y = e
    return (x + tau * (dx + tau * (d2x + tau * d3x)), y + tau * (dy + tau * (d2y + tau * d3y)),
            dx + tau * (2.0 * d2x + 3.0 * d3x * tau), dy + tau * (2.0 * d2y + 3.0 * d3y * tau),
            2.0 * d2x + 6.0 * d3x * tau, 2.0 * d2y + 6.0 * d3y * tau)


def _observer(pc, ps, dec, hour_angle):
    """ξ, η of the place on the fundamental plane (the star's hour angle *hour_angle*,
    radians) and their first two derivatives (the Earth turning)."""
    sin_h, cos_h, sin_d, cos_d = np.sin(hour_angle), np.cos(hour_angle), np.sin(dec), np.cos(dec)
    w = _SIDEREAL
    return (pc * sin_h, ps * cos_d - pc * sin_d * cos_h,
            pc * cos_h * w, pc * sin_d * sin_h * w,
            -pc * sin_h * w * w, pc * sin_d * cos_h * w * w)


def _hour_angle(lon, substar_lon, tau):
    """The star's hour angle at the place (radians), *tau* hours from the middle."""
    return np.radians(lon - substar_lon) + _SIDEREAL * tau


def _altitude_azimuth(lat, dec, hour_angle):
    """Altitude and azimuth (degrees, azimuth from north through east) for a declination and hour angle."""
    phi = math.radians(lat)
    sin_alt = math.sin(phi) * math.sin(dec) + math.cos(phi) * math.cos(dec) * math.cos(hour_angle)
    az = math.atan2(-math.cos(dec) * math.sin(hour_angle),
                    math.cos(phi) * math.sin(dec) - math.sin(phi) * math.cos(dec) * math.cos(hour_angle))
    return math.degrees(math.asin(max(-1.0, min(1.0, sin_alt)))), math.degrees(az) % 360.0


def _nearest(arrays, pc, ps, lon, margin):
    """
    For every event at once: the time (hours from the middle) when the shadow's
    axis passes nearest to the place on the fundamental plane, and that
    distance (Earth radii); NaN for the shadows that pass farther than
    *margin* from the Earth's disc.
    """
    el = arrays["elements"]                                         # (n, 8)
    x0, y0, dx, dy = el[:, 0], el[:, 1], el[:, 2], el[:, 3]
    speed2 = np.maximum(dx * dx + dy * dy, 1e-9)
    centre = -(x0 * dx + y0 * dy) / speed2                         # straight-line crossing of the disc
    impact = np.abs(x0 * dy - y0 * dx) / np.sqrt(speed2)
    reach = 1.0 + margin
    half = np.sqrt(np.maximum(reach * reach - impact * impact, 0.0)) / np.sqrt(speed2) + 0.05
    tau = centre[:, None] + half[:, None] * np.linspace(-1.0, 1.0, 161)[None, :]
    dec = arrays["dec"][:, None]
    coeffs = [el[:, i][:, None] for i in range(8)]
    x, y, *_ = _shadow(coeffs, tau)
    xi, eta, *_ = _observer(pc, ps, dec, _hour_angle(lon, arrays["substar_lon"][:, None], tau))
    best = tau[np.arange(len(tau)), np.argmin((x - xi) ** 2 + (y - eta) ** 2, axis=1)]
    coeffs = [el[:, i] for i in range(8)]
    for _ in range(5):                                              # Newton on d(distance²)/dt = 0
        x, y, x1, y1, x2, y2 = _shadow(coeffs, best)
        xi, eta, xi1, eta1, xi2, eta2 = _observer(pc, ps, arrays["dec"],
                                                  _hour_angle(lon, arrays["substar_lon"], best))
        ux, uy, vx, vy = x - xi, y - eta, x1 - xi1, y1 - eta1
        slope = vx * vx + vy * vy + ux * (x2 - xi2) + uy * (y2 - eta2)
        step = (ux * vx + uy * vy) / np.where(np.abs(slope) > 1e-12, slope, 1e-12)
        best = np.clip(best - step, centre - half, centre + half)
    x, y, *_ = _shadow(coeffs, best)
    xi, eta, *_ = _observer(pc, ps, arrays["dec"], _hour_angle(lon, arrays["substar_lon"], best))
    distance = np.hypot(x - xi, y - eta)
    return best, np.where(impact <= reach, distance, np.nan)


def _arrays(events):
    return {"elements": np.array([e["elements"] for e in events], dtype=float).reshape(-1, 8),
            "dec": np.radians([e["dec"] for e in events]),
            "substar_lon": np.array([e["substar"][0] for e in events], dtype=float)}


def _ground(event, tau, lat, lon, elevation_m):
    """
    The place against the band at *tau*: the signed distance to the centre
    line on the fundamental plane (Earth radii), its rate per kilometre on the
    ground towards the east and the north, and the relative speed (Earth radii
    per hour).
    """
    dec = math.radians(event["dec"])
    x, y, x1, y1, _x2, _y2 = _shadow(event["elements"], tau)

    def plane(la, lo):
        pc, ps = _place(la, lo, elevation_m)
        xi, eta, xi1, eta1, _a, _b = _observer(pc, ps, dec, float(_hour_angle(lo, event["substar"][0], tau)))
        return xi, eta, xi1, eta1

    xi, eta, xi1, eta1 = plane(lat, lon)
    vx, vy = x1 - xi1, y1 - eta1
    speed = math.hypot(vx, vy)
    px, py = -vy / speed, vx / speed                         # across the band
    signed = px * (xi - x) + py * (eta - y)
    step_lat = math.degrees(1.0 / _KM_PER_RAD)
    step_lon = math.degrees(1.0 / (_KM_PER_RAD * max(math.cos(math.radians(lat)), 1e-6)))
    east = plane(lat, lon + step_lon)
    north = plane(lat + step_lat, lon)
    rate_e = px * (east[0] - xi) + py * (east[1] - eta)
    rate_n = px * (north[0] - xi) + py * (north[1] - eta)
    return signed, rate_e, rate_n, speed


def pass_at(event, lat, lon, elevation_m=0.0):
    """
    The event seen from the place: when the shadow passes nearest, how far
    from the centre line and how wide the band is there, on the ground.

    Returns:
        dict: date (UT), distance_km (from the centre line), half_width_km,
        inside, edge_km (from the band's edge; 0 inside), direction (azimuth
        from the place towards the centre line, degrees; None on it),
        duration (seconds hidden here; 0 outside), alt, az (the star's), sun
        (the Sun's altitude), drop (the magnitude drop).
    """
    pc, ps = _place(lat, lon, elevation_m)
    tau, _ = _nearest(_arrays([event]), pc, ps, lon, margin=1.0)
    return _describe(event, float(tau[0]), lat, lon, elevation_m)


def _describe(event, tau, lat, lon, elevation_m):
    signed, rate_e, rate_n, speed = _ground(event, tau, lat, lon, elevation_m)
    rate = math.hypot(rate_e, rate_n)
    radius = event["diameter_km"] / 2.0 / EARTH_KM
    distance = abs(signed) / rate
    half = radius / rate
    inside = abs(signed) < radius
    direction = None
    if distance > 0.05:                                  # the centre line, from the place
        direction = math.degrees(math.atan2(-math.copysign(1.0, signed) * rate_e,
                                            -math.copysign(1.0, signed) * rate_n)) % 360.0
    dec = math.radians(event["dec"])
    alt, az = _altitude_azimuth(lat, dec, float(_hour_angle(lon, event["substar"][0], tau)))
    sun_lon, sun_lat = event["subsolar"]
    sun, _ = _altitude_azimuth(lat, math.radians(sun_lat), math.radians(lon - sun_lon) + _SOLAR * tau)
    duration = 2.0 * math.sqrt(max(radius * radius - signed * signed, 0.0)) / speed * 3600.0
    return {"event": event, "date": event["middle"] + timedelta(hours=tau),
            "distance_km": distance, "half_width_km": half, "inside": inside,
            "edge_km": max(distance - half, 0.0), "direction": direction, "duration": duration,
            "alt": alt, "az": az, "sun": sun, "drop": mag_drop(event["star_mag"], event["mag"])}


def moonlight(found):
    """
    The Moon at each pass of *found* (near()'s list): adds moon_fraction (its
    lit share, 0 to 1) and moon_separation (its distance from the star,
    degrees). The Moon's glare drowns the faint stars.
    """
    if not found:
        return found
    from skyfield import almanac
    from engine import AstroEngine, _sky
    sky = _sky()
    times = sky["ts"].ut1_jd(np.array([AstroEngine.julian_day(s["date"]) for s in found]))
    ra, dec, _ = sky["earth"].at(times).observe(sky["moon"]).apparent().radec()
    fraction = np.atleast_1d(almanac.fraction_illuminated(sky["eph"], "moon", times))
    for seen, m_ra, m_dec, lit in zip(found, np.atleast_1d(ra.radians), np.atleast_1d(dec.radians), fraction):
        s_ra, s_dec = math.radians(seen["event"]["ra2000"] * 15.0), math.radians(seen["event"]["dec2000"])
        cosine = (math.sin(m_dec) * math.sin(s_dec)
                  + math.cos(m_dec) * math.cos(s_dec) * math.cos(m_ra - s_ra))
        seen["moon_separation"] = math.degrees(math.acos(max(-1.0, min(1.0, cosine))))
        seen["moon_fraction"] = float(lit)
    return found


def near(events, lat, lon, elevation_m=0.0, start=None, end=None, max_km=MAX_KM, min_alt=MIN_ALT,
         dark_sun=DARK_SUN):
    """
    The events whose band passes within *max_km* of the place between *start*
    and *end* (UT datetimes, None: no limit), with the star at least *min_alt*
    high and the Sun lower than *dark_sun* there.

    Returns:
        list[dict] by date: pass_at()'s dicts.
    """
    chosen = [e for e in events
              if (start is None or e["middle"] >= start - timedelta(days=1))
              and (end is None or e["middle"] < end + timedelta(days=1))]
    if not chosen:
        return []
    pc, ps = _place(lat, lon, elevation_m)
    radius = np.array([e["diameter_km"] for e in chosen]) / 2.0 / EARTH_KM
    margin = (max_km + 600.0) / EARTH_KM                     # the largest asteroids' radius, and some
    tau, distance = _nearest(_arrays(chosen), pc, ps, lon, margin)
    # on the ground a band is never narrower, nor a place nearer, than on the plane
    keep = np.nonzero(np.nan_to_num(distance - radius, nan=np.inf) * EARTH_KM <= max_km)[0]
    found = []
    for i in keep:
        seen = _describe(chosen[i], float(tau[i]), lat, lon, elevation_m)
        if (seen["edge_km"] <= max_km and seen["alt"] >= min_alt and seen["sun"] <= dark_sun
                and (start is None or seen["date"] >= start) and (end is None or seen["date"] < end)):
            found.append(seen)
    found.sort(key=lambda s: s["date"])
    return found
