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
