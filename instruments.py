"""
instruments.py — Astronomical instruments to print and build
============================================================
The geometry of instruments drawn for the observer's place, to print at true
scale and build from card (workshop.py draws the pages):

- the planispheric astrolabe: the plate (tympan) of the latitude, the limb of
  the mater with its hour and degree scales, the rete (ecliptic and stars),
  the rule, and the back with its altitude scale, zodiac and calendar rings
  and shadow square;
- the nocturnal, which tells the time at night from the stars turning round
  the pole;
- the planisphere (star wheel);
- the horizontal and equatorial sundials.

Independent of the interface (no Qt), tested against the classic formulas and
against the sky of the engine (tests/test_instruments.py, tests/test_workshop.py).
"""
import math
from datetime import date, datetime, timedelta

import numpy as np

OBLIQUITY = 23.4393                     # mean obliquity of the ecliptic, J2000, degrees
SIDEREAL_RATE = 1.00273790935            # sidereal hours per hour of mean time


def _side(lat):
    """+1 north of the equator, −1 south."""
    return 1.0 if lat >= 0 else -1.0


def local_sidereal_midnights(lon, std_offset, year):
    """[(month, day, LST hours)]: the local sidereal time at 00:00 standard time of
    each day of *year* (Skyfield's GMST, UT1)."""
    from engine import AstroEngine, _sky
    ts = _sky()["ts"]
    out = []
    day = date(year, 1, 1)
    while day.year == year:
        jd = AstroEngine.julian_day(datetime(day.year, day.month, day.day)) - std_offset / 24.0
        out.append((day.month, day.day, (float(ts.ut1_jd(jd).gmst) + lon / 15.0) % 24.0))
        day += timedelta(days=1)
    return out


# ── Astrolabe ─────────────────────────────────────────────────────────────────
#
# The stereographic projection of the sky from its south pole onto the plane of
# the equator, as on the astrolabes of old: the north celestial pole at the
# centre, the meridian of the south at the top under the ring, the east (Oriens)
# on the left and the west (Occasus) on the right; the rete turns clockwise as
# the sky. For the southern hemisphere, the projection from the north pole, seen
# from the south pole: the mirror image, the north at the top.
#
# Lengths are in units of the equator's radius; the tropic of Capricorn (the edge
# of the plate) is at tan(45° + ε/2) = 1.5235.

def project(dec, hour_angle, south=False):
    """
    Stereographic projection of points given by declination and hour angle
    (degrees, west positive) onto the plane of the equator (radius 1).

    Returns:
        tuple[numpy.ndarray, numpy.ndarray]: x, y (the meridian at the top)
    """
    dec = np.asarray(dec, dtype=float)
    hour_angle = np.radians(np.asarray(hour_angle, dtype=float))
    if south:
        dec = -dec
    r = np.tan(np.radians(90.0 - dec) / 2.0)
    return (-1.0 if south else 1.0) * r * np.sin(hour_angle), r * np.cos(hour_angle)


def projection_radius(dec, south=False):
    """Radius of the circle of declination *dec* (degrees)."""
    return float(np.tan(np.radians(90.0 - (-dec if south else dec)) / 2.0))


def equatorial(alt, az, lat):
    """Declination and hour angle (degrees, west positive) of points of the local sky
    given by altitude and azimuth (degrees, from the north, eastward) at *lat*."""
    alt, az, phi = np.radians(alt), np.radians(az), math.radians(lat)
    sin_dec = np.sin(alt) * math.sin(phi) + np.cos(alt) * math.cos(phi) * np.cos(az)
    dec = np.arcsin(np.clip(sin_dec, -1, 1))
    h = np.arctan2(-np.sin(az) * np.cos(alt), np.sin(alt) * math.cos(phi) - np.cos(alt) * math.sin(phi) * np.cos(az))
    return np.degrees(dec), np.degrees(h)


def hour_angle_at_altitude(alt, dec, lat):
    """Hour angle (degrees, ≥ 0: the western one; its opposite is the eastern one) at
    which a point of declination *dec* stands at altitude *alt*; NaN when never."""
    phi, d, h = math.radians(lat), np.radians(dec), np.radians(alt)
    c = (np.sin(h) - math.sin(phi) * np.sin(d)) / (math.cos(phi) * np.cos(d))
    return np.where(np.abs(c) <= 1, np.degrees(np.arccos(np.clip(c, -1, 1))), np.nan)


def _clip(x, y, limit):
    """NaN where a curve leaves the plate (beyond the tropic of Capricorn), so that it is cut."""
    outside = np.hypot(x, y) > limit * (1 + 1e-9)
    return np.where(outside, np.nan, x), np.where(outside, np.nan, y)


def plate(lat, almucantar_step=10, azimuth_step=15):
    """
    The lines of the plate of an astrolabe for latitude *lat* (degrees, |lat|
    between 10 and 80).

    Returns:
        dict: limit (radius of the tropic of Capricorn, the edge of the
        plate), tropics (Cancer, equator, Capricorn radii), horizon,
        twilight (−18°), almucantars ({altitude: (x, y)}), azimuths
        ({azimuth: (x, y)}, from the north, eastward), unequal_hours ({1..11: (x, y)}
        under the horizon), zenith (x, y), east and west (the points of the
        horizon): curves as arrays, cut at the edge.
    """
    south = lat < 0
    phi = abs(lat)
    limit = projection_radius(-OBLIQUITY)
    out = {"limit": limit, "tropics": (projection_radius(OBLIQUITY), 1.0, limit), "almucantars": {},
           "azimuths": {}, "unequal_hours": {}}
    az = np.linspace(0.0, 360.0, 1441)

    def circle(alt):
        dec, h = equatorial(np.full_like(az, alt), az, phi)
        return _clip(*project(dec, h), limit)

    out["horizon"] = circle(0.0)
    out["twilight"] = circle(-18.0)
    for alt in range(almucantar_step, 90, almucantar_step):
        out["almucantars"][alt] = circle(float(alt))
    alts = np.linspace(0.0, 89.9, 400)
    for a in range(0, 360, azimuth_step):
        dec, h = equatorial(alts, np.full_like(alts, a), phi)
        out["azimuths"][a] = _clip(*project(dec, h), limit)
    # the unequal (temporary) hours of the night: the night arc of each declination
    # divided in twelve; read with the point of the ecliptic opposite the Sun
    decs = np.linspace(-OBLIQUITY, OBLIQUITY, 201)
    h0 = hour_angle_at_altitude(0.0, decs, phi)
    for k in range(1, 12):
        h = h0 + k * (360.0 - 2.0 * h0) / 12.0
        out["unequal_hours"][k] = _clip(*project(decs, h), limit)
    zx, zy = project(phi, 0.0)
    out["zenith"] = (float(zx), float(zy))
    for key, a in (("east", 90.0), ("west", 270.0)):
        dec, h = equatorial(0.0, a, phi)
        out[key] = tuple(float(v) for v in project(dec, h))
    if south:                                            # the mirror image, read from the south pole
        for key in ("horizon", "twilight"):
            out[key] = (-out[key][0], out[key][1])
        for group in ("almucantars", "azimuths", "unequal_hours"):
            out[group] = {k: (-x, y) for k, (x, y) in out[group].items()}
        for key in ("zenith", "east", "west"):
            out[key] = (-out[key][0], out[key][1])
        # azimuths from the south pole's side: the north of the plate is the south of the sky
        out["azimuths"] = {(180 - a) % 360: xy for a, xy in out["azimuths"].items()}
    return out


def ecliptic_point(longitude, sidereal_hours=0.0, south=False):
    """Position on the rete of the point of ecliptic longitude *longitude* (degrees),
    the rete turned to the local sidereal time *sidereal_hours*; also its RA (h) and Dec."""
    lam, eps = np.radians(longitude), math.radians(OBLIQUITY)
    ra = np.degrees(np.arctan2(np.sin(lam) * math.cos(eps), np.cos(lam))) % 360.0
    dec = np.degrees(np.arcsin(np.sin(lam) * math.sin(eps)))
    x, y = project(dec, 15.0 * sidereal_hours - ra, south)
    return x, y, ra / 15.0, dec


def ecliptic_circle(south=False):
    """Centre (x, y) and radius of the ecliptic on the rete at sidereal time 0."""
    # λ = 90° at H = −90° and λ = 270° at H = +90°: a horizontal diameter
    xs = (float(ecliptic_point(90.0, 0.0, south)[0]), float(ecliptic_point(270.0, 0.0, south)[0]))
    return ((xs[0] + xs[1]) / 2.0, 0.0), abs(xs[1] - xs[0]) / 2.0


def rete(stars, south=False):
    """
    The rete, at sidereal time 0: the ecliptic, marks on it every degree, and the
    stars (name, RA hours, Dec degrees) that fall on the plate.

    Returns:
        dict: ecliptic (x, y), centre and radius of the ecliptic circle,
        ecliptic_ticks ([(longitude, x, y)] every degree), stars
        ([(name, x, y)]), limit.
    """
    lon = np.linspace(0.0, 360.0, 1441)
    ex, ey, _ra, _dec = ecliptic_point(lon, 0.0, south)
    ticks = []
    for d in range(360):
        x, y, _r, _d = ecliptic_point(float(d), 0.0, south)
        ticks.append((d, float(x), float(y)))
    limit = projection_radius(-OBLIQUITY)
    placed = []
    for name, ra_h, dec_d in stars:
        x, y = project(dec_d, -15.0 * ra_h, south)
        if math.hypot(x, y) <= limit * 0.985:
            placed.append((name, float(x), float(y)))
    centre, radius = ecliptic_circle(south)
    return {"ecliptic": (ex, ey), "centre": centre, "radius": radius, "ecliptic_ticks": ticks,
            "stars": placed, "limit": limit}


def turn(x, y, sidereal_hours, south=False):
    """Turns points of the rete (drawn at sidereal time 0) to the sidereal time: clockwise
    in the north, counter-clockwise in the south."""
    a = math.radians(15.0 * sidereal_hours) * (-1.0 if south else 1.0)
    c, s = math.cos(a), math.sin(a)
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    return x * c + y * s, -x * s + y * c


def limb_angle(solar_hours, south=False):
    """Direction (unit x, y) of the limb's mark of apparent solar time *solar_hours*:
    noon at the top, 18 h on the right (west) in the north."""
    h = math.radians(15.0 * (solar_hours - 12.0))
    return (-1.0 if south else 1.0) * math.sin(h), math.cos(h)


def limb_reading(x, y, south=False):
    """Apparent solar time (hours) read where the rule laid over the point (x, y) of the
    Sun meets the limb."""
    h = math.degrees(math.atan2((-1.0 if south else 1.0) * x, y))
    return (12.0 + h / 15.0) % 24.0


def solar_longitudes(year):
    """[(month, day, longitude)]: the Sun's apparent ecliptic longitude at 12:00 UT of each
    day of *year* (DE440), for the calendar ring of the back."""
    from engine import AstroEngine
    days = []
    day = date(year, 1, 1)
    while day.year == year:
        days.append(day)
        day += timedelta(days=1)
    tc = np.array([AstroEngine.julian_century_j2000(datetime(d.year, d.month, d.day, 12)) for d in days])
    lon, _dist = AstroEngine.sun_position(tc)
    return [(d.month, d.day, float(v) % 360.0) for d, v in zip(days, np.atleast_1d(lon))]


def back_angle(longitude):
    """Position angle (degrees, counter-clockwise from the right) of ecliptic longitude
    *longitude* on the back's zodiac ring: 0° (spring equinox) on the left, 90° (the June
    solstice) at the top."""
    return (180.0 - np.asarray(longitude, dtype=float)) % 360.0


def shadow_square(alt):
    """Reading of the shadow square (12 parts) for the altitude *alt* (degrees): ("versa",
    12 tan h) below 45°, ("recta", 12 / tan h) above; the height of an object is its
    distance × reading / 12 (versa) or × 12 / reading (recta)."""
    t = math.tan(math.radians(alt))
    return ("versa", 12.0 * t) if alt <= 45.0 else ("recta", 12.0 / t)


# ── Nocturnal ─────────────────────────────────────────────────────────────────
#
# Held at arm's length towards the visible pole, the pole star seen through the
# hole at the centre, the arm laid along the pointer stars: their hour angle is
# the arm's angle, the time follows from the date. Seen from the front, the
# pointers turn counter-clockwise round the north pole, clockwise round the south.

def nocturnal(lat, lon, std_offset, year, pointers):
    """
    The scales of a nocturnal for the place.

    Args:
        pointers: {key: right ascension (hours, of the date)} of the pointer
            stars, one tooth each on the hour disc; the first one sets the
            date ring.

    Returns:
        dict: date_ticks [(month, day, angle)], the angle (degrees from the top,
        counter-clockwise in the north, clockwise in the south) of each date;
        hour_ticks [(hour, angle)], the angle of each quarter of an hour of
        standard time from the first tooth; teeth {key: angle from the first
        tooth}; sense (+1 counter-clockwise).
    """
    keys = list(pointers)
    reference = pointers[keys[0]]
    ticks = [(m, d, ((lst - reference) * 15.0) % 360.0)
             for m, d, lst in local_sidereal_midnights(lon, std_offset, year)]
    hours = [(h / 4.0, (h / 4.0 * 15.0 * SIDEREAL_RATE) % 360.0) for h in range(96)]
    # tooth k set on the date makes the hours read the hour angle of star k
    teeth = {k: ((pointers[k] - reference) * 15.0) % 360.0 for k in keys}
    return {"date_ticks": ticks, "hour_ticks": hours, "teeth": teeth, "sense": _side(lat)}


def nocturnal_reading(arm_angle, month, day, geo, key=None):
    """Standard time (hours) read on a nocturnal whose arm is at *arm_angle* (the hour
    angle of pointer *key*, degrees), its tooth *key* set on the date (month, day)."""
    date_angle = next(a for m, d, a in geo["date_ticks"] if (m, d) == (month, day))
    tooth = geo["teeth"][key] if key is not None else 0.0
    first_tooth = date_angle - tooth
    return ((arm_angle - first_tooth) % 360.0) / (15.0 * SIDEREAL_RATE)


# ── Planisphere (star wheel) ──────────────────────────────────────────────────
#
# The sky as seen overhead, with the visible pole at the centre: an azimuthal
# equidistant projection (the distance to the centre grows as the distance to
# the pole), the classic projection of planispheres. The star disc turns under a
# fixed mask, whose window is the horizon of the latitude. Facing the south
# (north of the equator), the meridian is at the bottom and the east on the left.

def planisphere_radius(dec, lat, r_edge, dec_edge):
    """Radius of declination *dec* on the star disc, *r_edge* being that of *dec_edge*."""
    s = _side(lat)
    return r_edge * (90.0 - s * np.asarray(dec, dtype=float)) / (90.0 - s * dec_edge)


def planisphere_xy(ra_hours, dec, angle_hours, lat, r_edge, dec_edge):
    """
    Position on the planisphere of a point (RA, Dec) when the meridian (the
    bottom) shows the sidereal time *angle_hours*: angle_hours = 0 gives the
    star disc in its own frame.
    """
    r = planisphere_radius(dec, lat, r_edge, dec_edge)
    a = np.radians((np.asarray(ra_hours, dtype=float) - angle_hours) * 15.0)
    return -_side(lat) * r * np.sin(a), -r * np.cos(a)


def planisphere(lat, lon, std_offset, year, r_edge, stars, figures, margin=8.0):
    """
    The geometry of a planisphere for the place.

    Args:
        lat, lon: degrees (east positive); std_offset: the time zone's
            standard (winter) offset from UT, hours; year: the year of the
            date ring (the ring moves by a minute in four years).
        r_edge: radius (mm) of the edge of the star field.
        stars: [(name, RA h, Dec °, mag)]; figures: constellation_figures().
        margin: degrees of sky shown beyond the horizon of the south.

    Returns:
        dict: dec_edge, stars [(name, x, y, mag)], lines [((x1, y1), (x2, y2))],
        names [(key, x, y)] of the constellations, ecliptic and equator
        curves, ra_ticks [(hour, angle)], date_ticks [(month, day, angle)]
        (angles in hours of RA on the disc's own frame), horizon (x, y) of
        the window, almucantars {30: (x, y), 60: (x, y)}, cardinals
        [(azimuth, x, y)], zenith (x, y), hours [(hour, x, y on r = 1)].
    """
    s = _side(lat)
    phi = abs(lat)
    dec_edge = s * (-(90.0 - phi) - margin)
    inside = lambda dec: s * dec >= s * dec_edge                      # noqa: E731

    def xy(ra, dec):
        return planisphere_xy(ra, dec, 0.0, lat, r_edge, dec_edge)

    out = {"dec_edge": dec_edge, "stars": [], "lines": [], "names": []}
    for name, ra, dec, mag in stars:
        if inside(dec):
            x, y = xy(ra, dec)
            out["stars"].append((name, float(x), float(y), mag))
    for key, figure in figures.items():
        for line in figure["lines"]:
            for (ra1, d1), (ra2, d2) in zip(line, line[1:]):
                if inside(d1) and inside(d2):
                    out["lines"].append((tuple(map(float, xy(ra1, d1))), tuple(map(float, xy(ra2, d2)))))
        ra, dec = figure["center"]
        if inside(dec):
            out["names"].append((key, *map(float, xy(ra, dec))))
    lam = np.radians(np.linspace(0, 360, 721))
    eps = math.radians(OBLIQUITY)
    ecl_ra = np.degrees(np.arctan2(np.sin(lam) * math.cos(eps), np.cos(lam))) / 15.0 % 24.0
    ecl_dec = np.degrees(np.arcsin(np.sin(lam) * math.sin(eps)))
    ex, ey = xy(ecl_ra, ecl_dec)
    keep = inside(ecl_dec)
    out["ecliptic"] = (np.where(keep, ex, np.nan), np.where(keep, ey, np.nan))
    out["equator"] = xy(np.linspace(0, 24, 361), np.zeros(361))
    out["ra_ticks"] = [(h, float(h)) for h in range(24)]

    # the date ring: the sidereal time at 00:00 standard time of the place, each day
    out["date_ticks"] = local_sidereal_midnights(lon, std_offset, year)

    # the mask: the window of the horizon, the 30° and 60° circles, the directions
    az = np.linspace(0.0, 360.0, 721)

    def local(alt):
        dec, h = equatorial(np.full_like(az, alt), az, lat)
        return planisphere_xy(-h / 15.0, dec, 0.0, lat, r_edge, dec_edge)

    out["horizon"] = local(0.0)
    out["almucantars"] = {30: local(30.0), 60: local(60.0)}
    cards = []
    for a in range(0, 360, 45):
        dec, h = equatorial(np.array([3.0]), np.array([float(a)]), lat)
        x, y = planisphere_xy(-h / 15.0, dec, 0.0, lat, r_edge, dec_edge)
        cards.append((a, float(x[0]), float(y[0])))
    out["cardinals"] = cards
    zx, zy = planisphere_xy(0.0, lat, 0.0, lat, r_edge, dec_edge)
    out["zenith"] = (float(zx), float(zy))
    # the hour ring of the mask: standard time T sits where the date mark falls when
    # the meridian shows the sidereal time of T on that date
    out["hours"] = []
    for hour in range(24):
        a = math.radians(-hour * 15.0 * SIDEREAL_RATE)
        out["hours"].append((hour, -s * math.sin(a), -math.cos(a)))
    return out


# ── Sundials ──────────────────────────────────────────────────────────────────
#
# Both dials read the apparent solar time shifted by the longitude's offset from
# the time zone, so that their lines carry the standard (winter) time of the
# place; what remains is the equation of time (and an hour in summer time).

def sun_vector(hour_angle, dec, lat):
    """Unit vectors towards the Sun (east, north, up) for hour angles and declinations (degrees)."""
    h, d, phi = np.radians(hour_angle), np.radians(dec), math.radians(lat)
    up = np.sin(phi) * np.sin(d) + np.cos(phi) * np.cos(d) * np.cos(h)
    east = -np.cos(d) * np.sin(h)
    north = np.cos(phi) * np.sin(d) - np.sin(phi) * np.cos(d) * np.cos(h)
    return np.array([east, north, up])


def dial_hour_angle(hour, lon, std_offset):
    """Hour angle of the Sun (degrees, west positive) when a dial corrected for the
    longitude shows the standard time *hour* (apparent solar time: before the
    equation of time)."""
    return 15.0 * (hour - 12.0) + lon - 15.0 * std_offset


def dial_reading(legal_hour, dst_hours, eot_minutes):
    """What a dial corrected for the longitude shows at the legal time *legal_hour*:
    legal − summer time + equation of time (apparent − mean)."""
    return legal_hour - dst_hours + eot_minutes / 60.0


def horizontal_dial(lat, lon, std_offset, height, hours=None):
    """
    A horizontal sundial: the style (gnomon edge) points to the visible pole
    and rises at the latitude; a notch on it (the nodus, at *height* mm above
    the dial) traces the date lines.

    The origin is the foot of the style; x to the east, y to the north (mm).

    Returns:
        dict: nodus (x, y, height), style_length (from the foot to the
        nodus), hour_lines {hour: (dx, dy) unit direction from the foot},
        hour_ranges {hour: True when the Sun can be up then}, date_lines
        {declination: (x, y) arrays of the nodus' shadow over the day}.
    """
    s = _side(lat)
    phi = math.radians(abs(lat))
    style_length = height / math.sin(phi)
    nodus = (0.0, s * style_length * math.cos(phi), height)
    hours = hours if hours is not None else [h / 2 for h in range(6, 43)]   # 3:00 to 21:00
    out = {"nodus": nodus, "style_length": style_length, "hour_lines": {}, "hour_ranges": {}, "date_lines": {}}
    pole = np.array([0.0, s * math.cos(phi), math.sin(phi)])        # direction of the style
    for hour in hours:
        h = dial_hour_angle(hour, lon, std_offset)
        lit = [d for d in (0.0, s * OBLIQUITY, -s * OBLIQUITY) if sun_vector(h, d, lat)[2] > 0.01]
        out["hour_ranges"][hour] = bool(lit)
        # the shadow of the style's point p: p − (p_z / v_z) v; its direction does not
        # depend on the Sun's declination (a polar style), only on the hour angle
        v = sun_vector(h, lit[0] if lit else 0.0, lat)
        z = v[2] if abs(v[2]) > 1e-9 else 1e-9
        shadow = pole[:2] - pole[2] / z * v[:2]
        if not lit:                                     # the Sun below: the line's continuation
            shadow = -shadow
        norm = float(np.hypot(*shadow)) or 1.0
        out["hour_lines"][hour] = (float(shadow[0]) / norm, float(shadow[1]) / norm)
    hs = np.linspace(-180.0, 180.0, 1441)
    for dec in (-OBLIQUITY, -20.15, -11.47, 0.0, 11.47, 20.15, OBLIQUITY):
        e, n, z = sun_vector(hs, dec, lat)
        k = np.where(z > math.sin(math.radians(2.0)), height / np.maximum(z, 1e-9), np.nan)
        out["date_lines"][dec] = (nodus[0] - k * e, nodus[1] - k * n)
    return out


def equatorial_dial(lat, lon, std_offset, hours=None):
    """
    An equatorial sundial: the dial lies in the plane of the equator, a rod
    through its centre points to the celestial pole. The face towards the
    visible pole is lit from the spring to the autumn equinox, the other in
    the other half of the year; the hours are 15° apart on both.

    Returns:
        dict: tilt (degrees of the dial from the horizontal = 90° − |lat|),
        rod (altitude of the rod = |lat|), hour_angles {hour: angle of the
        shadow from the noon line, degrees, positive clockwise on the summer
        face}, summer {hour: can be lit}, winter {hour: can be lit}.
    """
    hours = hours if hours is not None else [h / 2 for h in range(0, 49)]
    out = {"tilt": 90.0 - abs(lat), "rod": abs(lat), "hour_angles": {}, "summer": {}, "winter": {}}
    s = _side(lat)
    for hour in hours:
        h = dial_hour_angle(hour, lon, std_offset)
        out["hour_angles"][hour] = s * h
        out["summer"][hour] = bool(sun_vector(h, s * OBLIQUITY, lat)[2] > 0)
        out["winter"][hour] = bool(sun_vector(h, -s * 1e-6, lat)[2] > 0)
    return out
