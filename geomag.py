"""
geomag.py — The magnetic declination of a place (World Magnetic Model 2025)
===========================================================================
A compass, and the magnetometer of a phone, point to the magnetic north,
which is off the true north by the declination of the place: in November
2026, 2° east in Paris, 15° east in Seattle, 13° east in Sydney, 11° west
in Reykjavik; in Paris it grows by about 1.5° a decade. The sky map that
follows the phone (4.22) adds it to the phone's azimuth.

The World Magnetic Model 2025 of NOAA's NCEI and the British Geological
Survey (public domain): the Gauss coefficients of the Earth's main field to
degree 12 and their yearly change, assets/wmm2025.cof, valid from 2025.0 to
2030.0 (used outside with a growing error). The computation follows the
model's report (Chulliat et al., NOAA Technical Report, 2024–2025):
geodetic place to geocentric spherical coordinates, Schmidt semi-normalized
associated Legendre functions, the field's north, east and down components,
turned back to the ellipsoid. Checked against the model's 100 test values
(tests/test_geomag.py).

No Qt here.
"""
import math
import os
from datetime import datetime, timezone

_COF = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "wmm2025.cof")

_REFERENCE_RADIUS = 6371.2              # km, the model's geomagnetic reference radius
_A = 6378.137                           # km, WGS84 semi-major axis
_F = 1 / 298.257223563                  # WGS84 flattening
_E2 = _F * (2 - _F)                     # first eccentricity squared

_MODEL = {}


def _model():
    """The coefficients (read once): epoch, degree, and {(n, m): (g, h, ġ, ḣ)}."""
    if not _MODEL:
        with open(_COF, encoding="ascii") as f:
            lines = f.read().splitlines()
        epoch = float(lines[0].split()[0])
        terms = {}
        for line in lines[1:]:
            parts = line.split()
            if len(parts) != 6:                        # the closing lines of nines
                break
            n, m = int(parts[0]), int(parts[1])
            terms[n, m] = tuple(float(v) for v in parts[2:])
        _MODEL.update(epoch=epoch, degree=max(n for n, _m in terms), terms=terms)
    return _MODEL


def decimal_year(when):
    """The year of *when* (a datetime, UT when naive) with its fraction: 2025.5 is 2 July 2025."""
    if when.tzinfo is not None:
        when = when.astimezone(timezone.utc).replace(tzinfo=None)
    start = datetime(when.year, 1, 1)
    length = (datetime(when.year + 1, 1, 1) - start).total_seconds()
    return when.year + (when - start).total_seconds() / length


def _legendre(degree, x, c):
    """
    Schmidt semi-normalized associated Legendre functions P̆(n, m) of x = sin φ′
    and their derivatives along the geocentric latitude φ′ (c = cos φ′ > 0), as
    two dicts keyed (n, m); without the Condon–Shortley phase, as the model.
    """
    p, dp = {}, {}
    for m in range(degree + 1):
        # unnormalized: P(m, m) = (2m − 1)!! c^m, then up in n
        diagonal = c ** m
        for k in range(1, 2 * m, 2):
            diagonal *= k
        previous, current = 0.0, diagonal
        for n in range(m, degree + 1):
            if n == m + 1:
                previous, current = current, x * (2 * m + 1) * diagonal
            elif n > m + 1:
                previous, current = current, ((2 * n - 1) * x * current - (n + m - 1) * previous) / (n - m)
            below = previous if n > m else 0.0                     # P(n − 1, m)
            schmidt = math.sqrt((1 if m == 0 else 2) * math.factorial(n - m) / math.factorial(n + m))
            p[n, m] = schmidt * current
            dp[n, m] = -schmidt * (n * x * current - (n + m) * below) / c
    return p, dp


def field(lat, lon, height_km=0.0, year=2025.0):
    """
    The main field at a place: its north (X), east (Y) and down (Z)
    components in nanotesla, along the ellipsoid's directions.

    Args:
        lat, lon: geodetic latitude and longitude, degrees (east positive).
        height_km: height above the WGS84 ellipsoid, km.
        year: decimal year (decimal_year()).
    """
    model = _model()
    degree, dt = model["degree"], year - model["epoch"]
    phi, lam = math.radians(lat), math.radians(lon)
    # the place in geocentric spherical coordinates (radius r, latitude φ′)
    sin_phi, cos_phi = math.sin(phi), math.cos(phi)
    rc = _A / math.sqrt(1 - _E2 * sin_phi * sin_phi)
    p = (rc + height_km) * cos_phi
    z = (rc * (1 - _E2) + height_km) * sin_phi
    r = math.hypot(p, z)
    phi_c = math.asin(z / r)
    x, c = math.sin(phi_c), max(math.cos(phi_c), 1e-12)        # (the poles themselves left out)
    legendre, slope = _legendre(degree, x, c)
    north = east = down = 0.0
    for n in range(1, degree + 1):
        scale = (_REFERENCE_RADIUS / r) ** (n + 2)
        for m in range(n + 1):
            g0, h0, g_dot, h_dot = model["terms"][n, m]
            g, h = g0 + dt * g_dot, h0 + dt * h_dot
            cos_m, sin_m = math.cos(m * lam), math.sin(m * lam)
            along = g * cos_m + h * sin_m
            north -= scale * along * slope[n, m]
            east += scale * m * (g * sin_m - h * cos_m) * legendre[n, m]
            down -= scale * (n + 1) * along * legendre[n, m]
    east /= c
    # from the geocentric directions back to the ellipsoid's
    psi = phi_c - phi
    return (north * math.cos(psi) - down * math.sin(psi), east,
            north * math.sin(psi) + down * math.cos(psi))


def declination(lat, lon, elevation_m=0.0, when=None):
    """
    The magnetic declination at a place, degrees: how far east of the true
    north a compass points (negative: west). *when*: a datetime (now when
    None); *elevation_m*: the height above the ellipsoid, metres.
    """
    when = when or datetime.now(timezone.utc)
    north, east, _down = field(lat, lon, (elevation_m or 0.0) / 1000.0, decimal_year(when))
    return math.degrees(math.atan2(east, north))
