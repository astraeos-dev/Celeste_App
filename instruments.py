"""
instruments.py — Astronomical instruments to print and build (prototype)
========================================================================
The geometry of instruments drawn for the observer's latitude, to print at
true scale and build from cardboard. A first instrument, the planispheric
astrolabe:

- the plate (tympan), made for one latitude: the tropics and the equator, the
  horizon, the circles of altitude (almucantars), the azimuth lines, the
  astronomical twilight line;
- the rete, which turns over the plate: the ecliptic and the brightest stars.

Both are the stereographic projection of the sky from its south pole onto the
plane of the equator, as on the astrolabes of the Middle Ages, for the northern
hemisphere (the mirror one for the southern hemisphere). The geometry is
computed point by point from altitude and azimuth, so that every line follows
from one formula.

Lengths are in units of the equator's radius; print_astrolabe() scales them
to millimetres. Independent of the interface (no Qt).
"""
import math

import numpy as np

OBLIQUITY = 23.4393                     # mean obliquity of the ecliptic, J2000, degrees


def project(dec, hour_angle, south=False):
    """
    Stereographic projection of points of the sky given by declination and
    hour angle (degrees): from the south celestial pole onto the plane of the
    equator, whose radius is 1. The north pole is at the centre and the
    meridian of the south at the top, under the suspension ring, as on the
    astrolabes of old; the east is on the left and the sky turns clockwise
    (from east to west). *south*: the projection from the north pole, for
    the southern hemisphere.

    Returns:
        tuple[numpy.ndarray, numpy.ndarray]: x, y
    """
    dec = np.asarray(dec, dtype=float)
    hour_angle = np.radians(np.asarray(hour_angle, dtype=float))
    if south:
        dec = -dec
    r = np.tan(np.radians(90.0 - dec) / 2.0)
    return -r * np.sin(hour_angle), r * np.cos(hour_angle)


def equatorial(alt, az, lat):
    """Declination and hour angle (degrees) of points of the local sky given by altitude
    and azimuth (degrees, from the north, eastward) at latitude *lat*."""
    alt, az, phi = np.radians(alt), np.radians(az), math.radians(lat)
    sin_dec = np.sin(alt) * math.sin(phi) + np.cos(alt) * math.cos(phi) * np.cos(az)
    dec = np.arcsin(np.clip(sin_dec, -1, 1))
    h = np.arctan2(-np.sin(az) * np.cos(alt), np.sin(alt) * math.cos(phi) - np.cos(alt) * math.sin(phi) * np.cos(az))
    return np.degrees(dec), np.degrees(h)


def _clip(x, y, limit):
    """NaN where a curve leaves the plate (beyond the tropic of Capricorn), so that it is cut."""
    outside = np.hypot(x, y) > limit * (1 + 1e-9)
    return np.where(outside, np.nan, x), np.where(outside, np.nan, y)


def plate(lat, almucantar_step=10, azimuth_step=15):
    """
    The lines of the plate of an astrolabe for latitude *lat* (degrees,
    |lat| between 10 and 80).

    Returns:
        dict: limit (radius of the tropic of Capricorn, the edge of the
        plate), tropics and equator (radii), horizon, twilight,
        almucantars ({altitude: (x, y)}), azimuths ({azimuth: (x, y)}),
        zenith (x, y): curves as arrays, cut at the edge.
    """
    south = lat < 0
    phi = abs(lat)
    radius = lambda dec: math.tan(math.radians(90.0 - dec) / 2.0)   # noqa: E731
    limit = radius(-OBLIQUITY)
    out = {"limit": limit, "tropics": (radius(OBLIQUITY), 1.0, limit), "almucantars": {}, "azimuths": {}}
    az = np.linspace(0.0, 360.0, 721)

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
    zx, zy = project(phi, 0.0)
    out["zenith"] = (float(zx), float(zy))
    if south:                                            # the mirror image, read from the south pole
        for key in ("horizon", "twilight"):
            out[key] = (-out[key][0], out[key][1])
        for group in ("almucantars", "azimuths"):
            out[group] = {k: (-x, y) for k, (x, y) in out[group].items()}
        out["zenith"] = (-out["zenith"][0], out["zenith"][1])
    return out


def rete(stars, south=False):
    """
    The rete, at sidereal time 0: the ecliptic and the stars (name, RA hours,
    Dec degrees) that fall on the plate.

    Returns:
        dict: ecliptic (x, y), ecliptic_ticks ([(longitude, x, y)] every 30°,
        the signs), stars ([(name, x, y)]).
    """
    lam = np.radians(np.linspace(0.0, 360.0, 721))
    eps = math.radians(OBLIQUITY)
    ra = np.degrees(np.arctan2(np.sin(lam) * math.cos(eps), np.cos(lam)))
    dec = np.degrees(np.arcsin(np.sin(lam) * math.sin(eps)))
    ex, ey = project(dec, -ra, south)
    ticks = [(int(round(math.degrees(lam[i]))), float(ex[i]), float(ey[i])) for i in range(0, 720, 60)]
    limit = math.tan(math.radians(90.0 + OBLIQUITY) / 2.0)
    placed = []
    for name, ra_h, dec_d in stars:
        x, y = project(dec_d, -15.0 * ra_h, south)
        if math.hypot(x, y) <= limit:
            placed.append((name, float(x), float(y)))
    return {"ecliptic": (ex, ey), "ecliptic_ticks": ticks, "stars": placed}


def print_astrolabe(path, lat, place="", plate_mm=160.0, stars=None, labels=None):
    """
    Writes a PDF of two A4 pages at true scale: the plate for *lat*, then the
    rete (to print on a transparent sheet, or to cut out). *plate_mm*: the
    diameter of the plate (the tropic of Capricorn).
    """
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib.backends.backend_pdf import PdfPages
    from matplotlib.figure import Figure

    labels = {"plate": "Plate", "rete": "Rete", "latitude": "latitude", **(labels or {})}
    if stars is None:
        from star_catalog import CATALOG
        stars = [(c[6], c[1], c[2]) for c in CATALOG if c[6] and c[3] < 2.0]
    geometry = plate(lat)
    scale = plate_mm / 2.0 / geometry["limit"]            # millimetres per unit
    a4 = (210.0, 297.0)

    def page(title):
        fig = Figure(figsize=(a4[0] / 25.4, a4[1] / 25.4))
        size = plate_mm + 30.0
        ax = fig.add_axes(((a4[0] - size) / 2 / a4[0], (a4[1] - size) / 2 / a4[1], size / a4[0], size / a4[1]))
        ax.set_xlim(-size / 2, size / 2)
        ax.set_ylim(-size / 2, size / 2)
        ax.set_aspect("equal")
        ax.axis("off")
        fig.text(0.5, 0.95, title, ha="center", va="top", fontsize=14)
        return fig, ax

    def line(ax, xy, **style):
        ax.plot(np.asarray(xy[0]) * scale, np.asarray(xy[1]) * scale, color="black", **style)

    def ring(ax, r, **style):
        t = np.linspace(0, 2 * np.pi, 361)
        ax.plot(r * scale * np.cos(t), r * scale * np.sin(t), color="black", **style)

    with PdfPages(path) as pdf:
        fig, ax = page(f"{labels['plate']} — {place} {labels['latitude']} {lat:+.1f}°".replace("  ", " "))
        for r in geometry["tropics"]:
            ring(ax, r, linewidth=0.8)
        ax.plot([0, 0], [-geometry["limit"] * scale, geometry["limit"] * scale], color="black", linewidth=0.5)
        line(ax, geometry["horizon"], linewidth=1.2)
        line(ax, geometry["twilight"], linewidth=0.6, linestyle=(0, (4, 3)))
        for alt, xy in geometry["almucantars"].items():
            line(ax, xy, linewidth=0.4)
        for az, xy in geometry["azimuths"].items():
            line(ax, xy, linewidth=0.3)
        ax.plot(geometry["zenith"][0] * scale, geometry["zenith"][1] * scale, "+", color="black", markersize=6)
        ax.plot(0, 0, "o", color="black", markersize=3)
        pdf.savefig(fig)

        fig, ax = page(labels["rete"])
        r = rete(stars, lat < 0)
        ring(ax, geometry["limit"], linewidth=1.0)
        line(ax, r["ecliptic"], linewidth=1.0)
        for lon, x, y in r["ecliptic_ticks"]:
            ax.plot(x * scale, y * scale, "|", color="black", markersize=6)
        for name, x, y in r["stars"]:
            ax.plot(x * scale, y * scale, "^", color="black", markersize=4)
            ax.annotate(name, (x * scale, y * scale), xytext=(3, 3), textcoords="offset points", fontsize=6)
        ax.plot(0, 0, "o", color="black", markersize=3)
        pdf.savefig(fig)


# ── Planisphere (star wheel) ──────────────────────────────────────────────────
#
# The sky as seen overhead, with the visible pole at the centre: an azimuthal
# equidistant projection (the distance to the centre grows as the distance to
# the pole), the classic projection of planispheres. The star disc turns under a
# fixed mask, whose window is the horizon of the latitude. Facing the south
# (north of the equator), the meridian is at the bottom and the east on the left.

SIDEREAL_RATE = 1.00273790935            # sidereal hours per hour of mean time


def _side(lat):
    """+1 north of the equator, −1 south (the east then on the right)."""
    return 1.0 if lat >= 0 else -1.0


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
    from engine import AstroEngine, _sky
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
    ts = _sky()["ts"]
    ticks = []
    from datetime import date, timedelta
    day = date(year, 1, 1)
    while day.year == year:
        jd = AstroEngine.julian_day(datetime_from(day)) - std_offset / 24.0
        lst = (float(ts.ut1_jd(jd).gmst) + lon / 15.0) % 24.0
        ticks.append((day.month, day.day, lst))
        day += timedelta(days=1)
    out["date_ticks"] = ticks

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


def datetime_from(day):
    from datetime import datetime
    return datetime(day.year, day.month, day.day)


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
