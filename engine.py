"""
engine.py — Astronomical Calculation Engine for Céleste
=========================================================
v4.0: the positions come from the JPL DE440 ephemeris (Park et al., AJ 161,
105, 2021; file de440s.bsp, 1849–2150) through Skyfield: IAU 2006 precession,
IAU 2000A nutation, light time, aberration and light deflection; UT1 and ΔT
from the IERS (Skyfield's built-in tables) and, before 1973, the long-term
model of Stephenson, Morrison & Hohenkerk (2016).

  • sun_position(), moon_position(), planet_position() — apparent geocentric
    positions (DE440, milliarcseconds)
  • find_events()   — rises, sets, transits and twilights to the second over
    the local day (Skyfield almanac): upper limb with the standard
    refraction, topocentric Moon, twilights of the Sun's geometric centre
  • find_eclipses() — Besselian elements of the Moon's shadow (solar eclipses)
    and Danjon's rule (lunar eclipses), fed by DE440; syzygies from DE440
  • ecliptic_to_equatorial(), equatorial_to_horizontal() — true obliquity
    (IAU 2006 + nutation) and apparent sidereal time, for the interface

v4.1:
  • find_events(tz=ZoneInfo) — local day of an IANA time zone (summer time);
    elevation_m lowers the horizon
  • horizontal(), moon_phase() — topocentric positions, exact phase
  • stars_horizontal() — J2000 catalogue stars brought to the date
    (precession, nutation, aberration) for the sky map
  • coordinates() — any body in the chosen system: heliocentric, geocentric or
    topocentric; ecliptic, equatorial or horizontal; angles and x, y, z
  • observations() — visual magnitude, angle with the Sun and constellation
    of the Sun, the Moon and the planets from Mercury to Pluto
  • find_conjunctions() — conjunctions (inferior, superior), oppositions and
    greatest elongations to the minute; event_scene() for their maps
  • eclipse_map() — an eclipse projected on the ground: central line, path of
    totality or annularity and zone of partiality of a solar eclipse; where
    the Moon is up during a lunar eclipse

v4.2:
  • MINOR_PLANETS — Ceres, Pallas, Juno, Vesta (JPL Horizons tables) and the
    dwarf planets Pluto (DE440), Eris, Haumea, Makemake; H, G magnitudes
  • find_moon_events(), find_seasons() — the Moon's conjunctions with planets
    and bright stars, perigees, apogees; equinoxes, solstices, apsides
  • event_visibility(), moon_occultation() — when an event is seen from the
    observer, occultations; eclipse_local() — local circumstances

v4.3:
  • body_details() — the data window of a body: apparent diameter, phase
    angle, illuminated fraction, light time, distance to the Sun
  • Sedna among MINOR_PLANETS; MINOR_PLANET_NUMBERS, the Minor Planet
    Center's numbers (« (136199) Éris »)

v4.6:
  • COMETS — comets followed during their apparition (JPL Horizons tables of
    2025–2031, total magnitudes M1, K1), comets_at(), find_comet_events()
  • tonight(), upcoming_events() — the night seen from the observer
  • moon_calendar() — the Moon day by day over a month

v4.5:
  • find_meteor_showers() — maxima of the major meteor showers (IMO calendar),
    meteor_visibility(): the night of the maximum seen from the observer
    (radiant, hourly rate under a dark sky, moonlight)

v4.4:
  • download_ephemeris() — the ephemeris is no longer in the Windows
    installer: downloaded once into ~/.celeste, with its progress, and
    checked (size and SHA-256 of the NAIF file)

The ephemeris (32 MB) is looked for in data/ next to this module, then in
~/.celeste (or $CELESTE_DATA), where it is downloaded from the JPL/NAIF
server the first time (load_ephemeris(), download_ephemeris()).

This module is completely independent from the graphical interface (MVC model).
"""

import functools
import hashlib
import math
import os
import urllib.request
from datetime import timedelta, timezone

import numpy as np
from skyfield import almanac
from skyfield.api import Loader, Star, load_constellation_map, load_constellation_names, wgs84
from skyfield.magnitudelib import planetary_magnitude
from skyfield.vectorlib import VectorFunction
from skyfield.framelib import ecliptic_frame, ecliptic_J2000_frame, itrs, true_equator_and_equinox_of_date

# ==========================================================
# CONSTANTS
# ==========================================================

# JPL DE440, short version: 1849-12-26 → 2150-01-22
_EPHEMERIS_URL  = "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/planets/de440s.bsp"
_EPHEMERIS_FILE = "de440s.bsp"
# The NAIF file, as published (MD5 3917ee56769db332790c751e2168843d in its aa_checksums.txt)
_EPHEMERIS_SIZE   = 32726016
_EPHEMERIS_SHA256 = "c1c7feeab882263fc493a9d5a5b2ddd71b54826cdf65d8d17a76126b260a49f2"
EPHEMERIS_YEARS = (1850, 2149)            # whole years covered by the ephemeris
_DATA_DIRS = (
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"),
    os.environ.get("CELESTE_DATA") or os.path.join(os.path.expanduser("~"), ".celeste"),
)

# DE440 targets (barycentres for Mars, Jupiter and Saturn: their moons move
# them by less than a millisecond of arc)
_PLANETS = {"Mercury": "mercury", "Venus": "venus", "Mars": "mars barycenter",
            "Jupiter": "jupiter barycenter", "Saturn": "saturn barycenter",
            "Uranus": "uranus barycenter", "Neptune": "neptune barycenter",
            "Pluto": "pluto barycenter", "Earth": "earth"}

# The planets of the interface
PLANETS = ("Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune")

# Minor planets: the four first asteroids, the dwarf planets (Ceres among
# both) and Sedna, far beyond them. Pluto comes from DE440, the others from the
# tables of JPL Horizons (assets/minor_planets.npz, scripts/make_minor_planets.py).
MINOR_PLANETS = ("Ceres", "Pallas", "Juno", "Vesta", "Pluto", "Eris", "Haumea", "Makemake", "Sedna")
# Their numbers in the Minor Planet Center's catalogue: « (1) Cérès »
MINOR_PLANET_NUMBERS = {"Ceres": 1, "Pallas": 2, "Juno": 3, "Vesta": 4, "Pluto": 134340,
                        "Eris": 136199, "Haumea": 136108, "Makemake": 136472, "Sedna": 90377}
_MINOR_TABLE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "minor_planets.npz")

# Comets followed by Céleste, those that become easy to see from 2027 to 2029:
# JPL Horizons tables over the years of their apparition only, 2025 to 2031
# (assets/comets.npz, scripts/make_comets.py); outside, they are not shown.
COMETS = ("Panstarrs", "Honda", "Tsuchinshan", "Borrelly")
COMET_DESIGNATIONS = {"Panstarrs": "C/2026 O1 (PANSTARRS)", "Honda": "45P/Honda-Mrkos-Pajdušáková",
                      "Tsuchinshan": "C/2026 C1 (Tsuchinshan)", "Borrelly": "19P/Borrelly"}
_COMET_TABLE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "comets.npz")

# The Messier catalogue: 110 nebulae, clusters and galaxies (assets/messier.csv,
# from OpenNGC, CC BY-SA 4.0; scripts/make_messier.py)
_MESSIER_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "messier.csv")
MESSIER_TYPES = ("galaxy", "globular_cluster", "open_cluster", "nebula", "planetary_nebula",
                 "supernova_remnant", "star_cloud", "asterism", "double_star")


@functools.lru_cache(maxsize=1)
def messier_catalog():
    """
    The 110 Messier objects, in order.

    Returns:
        tuple[dict]: m (number), id (NGC/IC designation), type (MESSIER_TYPES),
        ra (J2000, hours), dec (J2000, °), const (IAU abbreviation), mag
        (visual), major, minor (apparent size, arcminutes, or None), name
        (English common name, or "").
    """
    import csv
    with open(_MESSIER_FILE, encoding="utf-8") as f:
        rows = list(csv.DictReader(f, delimiter=";"))
    return tuple({"m": int(r["M"]), "id": r["id"], "type": r["type"], "ra": float(r["ra"]) / 15.0,
                  "dec": float(r["dec"]), "const": r["const"], "mag": float(r["mag"]),
                  "major": float(r["major"]) if r["major"] else None,
                  "minor": float(r["minor"]) if r["minor"] else None, "name": r["name"]}
                 for r in rows)

# Eclipse projected on the ground: WGS84 ellipsoid, radii of the Sun and the Moon (km)
_WGS84_A  = 6378.137
_WGS84_B  = _WGS84_A * (1.0 - 1.0 / 298.257223563)
_WGS84_E2 = 1.0 - (_WGS84_B / _WGS84_A) ** 2
_SUN_RADIUS_KM, _MOON_RADIUS_KM = 696000.0, 1737.4

# Visual magnitudes outside Skyfield's planetary models (Mallama & Hilton 2018):
# Allen's Astrophysical Quantities (4th ed.), V(1,0) and phase coefficients
_SUN_MAGNITUDE_1AU = -26.74
_MOON_MAGNITUDE    = (0.21, 0.026, 4.0e-9)       # V(1,0), mag/°, mag/°⁴
_PLUTO_MAGNITUDE   = (-1.01, 0.041)              # V(1,0), mag/°

# Rise and set of the Sun: refraction (34′) and semi-diameter (16′)
_HORIZON_CORRECTION_SUN = 0.833  # degrees

# Refraction coefficients of Sæmundsson's formula (Meeus, chap. 16)
_REFRACTION_A = 10.3
_REFRACTION_B = 5.11

# Twilights: depth of the Sun's geometric centre below the horizon
_TWILIGHTS = ((6.0, "civ"), (12.0, "naut"), (18.0, "astro"))

# Rises and sets seen from a height: standard refraction at the horizon,
# radii of the Sun and the Moon, and dip of the horizon (1.76′ √h, h in m,
# refraction included, as in the nautical almanacs)
_HORIZON_REFRACTION = 34.0 / 60.0               # degrees
_BODY_RADIUS_KM     = {"sun": 696000.0, "moon": 1737.4}

# Radii for the apparent diameters (km): equatorial for the planets (IAU WGCCRE
# 2015, as the almanacs; Saturn without its rings), mean for the minor planets
_RADII_KM = {"sun": 696000.0, "moon": 1737.4, "Mercury": 2440.5, "Venus": 6051.8,
             "Mars": 3396.2, "Jupiter": 71492.0, "Saturn": 60268.0, "Uranus": 25559.0,
             "Neptune": 24764.0, "Pluto": 1188.3, "Ceres": 469.7, "Pallas": 256.0,
             "Juno": 127.0, "Vesta": 262.7, "Eris": 1163.0, "Haumea": 780.0, "Makemake": 715.0,
             "Sedna": 498.0}
_LIGHT_SECONDS_PER_AU = 499.004784
_HORIZON_DIP        = 1.76 / 60.0               # degrees per √metre

# Solar eclipse geometry (Besselian elements); lengths in Earth equatorial radii
_EARTH_RADIUS_KM = 6378.14
_AU_KM           = 149597870.7
_SUN_RADIUS      = _AU_KM * math.sin(math.radians(959.63 / 3600.0)) / _EARTH_RADIUS_KM
_MOON_RADIUS_PENUMBRA = 0.2725076                  # Moon radius for the penumbral cone
_MOON_RADIUS_UMBRA    = 0.2722810                  # … and for the umbral cone
_CENTRAL_LIMIT   = 0.9972     # |γ| under which the shadow axis meets the flattened Earth (Meeus, chap. 54)
_GAMMA_ACCURACY  = 0.005      # margin on γ under which a grazing eclipse is only 'possible'
_SIDEREAL_RATE   = 2.0 * math.pi * 1.00273790935 / 24.0   # Earth rotation, radians per hour

# Lunar eclipse geometry: Danjon's rule, as in NASA's Five Millennium Canon of
# Lunar Eclipses. The Earth's radius is enlarged by 1/85 for its atmosphere and
# the Moon's parallax reduced by 0.998340 for the flattening (latitude 45°).
_DANJON_ENLARGEMENT   = 1.0 + 1.0 / 85.0
_PARALLAX_FLATTENING  = 0.998340
_SUN_PARALLAX_1AU     = 8.794 / 3600.0           # degrees, at 1 AU
_SUN_SEMI_DIAMETER_1AU = 959.63 / 3600.0         # degrees, at 1 AU
_LUNAR_LATITUDE_LIMIT = 1.6       # degrees: farther from the ecliptic at full moon, the Moon misses the penumbra
_LUNAR_MAG_ACCURACY   = 0.01      # accuracy of the magnitudes (vs NASA: ≤ 0.004, 2021–2028)


# ==========================================================
# EPHEMERIS
# ==========================================================

class EphemerisUnavailable(RuntimeError):
    """The DE440 file is missing and could not be downloaded."""


class DownloadCancelled(EphemerisUnavailable):
    """The download of the DE440 file was interrupted by the user."""


_SKY = {}


def user_ephemeris_path():
    """Where the DE440 file is downloaded: ~/.celeste (or $CELESTE_DATA)."""
    return os.path.join(_DATA_DIRS[-1], _EPHEMERIS_FILE)


def ephemeris_path():
    """Path of the DE440 file: the first data directory holding it, else where it will be downloaded."""
    for directory in _DATA_DIRS:
        path = os.path.join(directory, _EPHEMERIS_FILE)
        if os.path.isfile(path):
            return path
    return user_ephemeris_path()


def download_ephemeris(path=None, progress=None, cancelled=None, timeout=30):
    """
    Downloads the DE440 file from the JPL/NAIF server into *path* (by default
    ~/.celeste), checks its size and SHA-256, and only then gives it its name:
    an interrupted download leaves nothing behind.

    Args:
        progress: called with (bytes received, total size).
        cancelled: returns True to interrupt (DownloadCancelled).

    Returns:
        str: the path of the file.
    """
    path = path or user_ephemeris_path()
    partial = path + ".part"
    digest, done = hashlib.sha256(), 0
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        request = urllib.request.Request(_EPHEMERIS_URL, headers={"User-Agent": "Celeste (Skyfield)"})
        with urllib.request.urlopen(request, timeout=timeout) as resp, open(partial, "wb") as out:
            total = int(resp.headers.get("Content-Length") or _EPHEMERIS_SIZE)
            while True:
                if cancelled is not None and cancelled():
                    raise DownloadCancelled("download cancelled")
                block = resp.read(1 << 16)
                if not block:
                    break
                out.write(block)
                digest.update(block)
                done += len(block)
                if progress is not None:
                    progress(done, total)
        if done != _EPHEMERIS_SIZE or digest.hexdigest() != _EPHEMERIS_SHA256:
            raise EphemerisUnavailable(f"{_EPHEMERIS_FILE}: corrupt download ({done} bytes)")
        os.replace(partial, path)
    except EphemerisUnavailable:
        _remove(partial)
        raise
    except Exception as exc:                                # network, disk
        _remove(partial)
        raise EphemerisUnavailable(
            f"{_EPHEMERIS_FILE}: not found in {os.path.dirname(path)} and not downloadable "
            f"from {_EPHEMERIS_URL} ({exc})") from exc
    return path


def _remove(path):
    try:
        os.remove(path)
    except OSError:
        pass


def load_ephemeris(progress=None, cancelled=None):
    """
    Skyfield timescale and DE440 bodies, loaded once (downloaded the first
    time, see download_ephemeris()). Raises EphemerisUnavailable when the
    file can be neither found nor downloaded.
    """
    if not _SKY:
        path = ephemeris_path()
        if not os.path.isfile(path):
            download_ephemeris(path, progress, cancelled)
        try:
            loader = Loader(os.path.dirname(path), verbose=False)
            eph = loader(_EPHEMERIS_URL)                    # the file is there: no download
        except Exception as exc:                            # disk, corrupt file
            raise EphemerisUnavailable(f"{path}: unreadable ({exc})") from exc
        _SKY.update(ts=loader.timescale(), eph=eph,
                    earth=eph["earth"], sun=eph["sun"], moon=eph["moon"])
    return _SKY


_sky = load_ephemeris


class _TabulatedOrbit(VectorFunction):
    """
    Heliocentric position of a minor planet (ICRF, AU) interpolated in the
    states of JPL Horizons: cubic Hermite between two states, position and
    velocity matching at both, a few km off for the main belt.
    """

    center = 10                                     # the Sun, as in DE440

    def __init__(self, name, start, positions, velocities):
        self.target = name
        self.target_name = name
        self._jd0, self._step = float(start[0]), float(start[1])
        self._p, self._v = positions, velocities

    def _at(self, t):
        x = (np.asarray(t.whole, dtype=float) - self._jd0 + np.asarray(t.tdb_fraction)) / self._step
        i = np.floor(x).astype(int)
        if np.any(i < 0) or np.any(i >= len(self._p) - 1):
            raise ValueError(f"{self.target}: date outside the years of the ephemeris")
        u = (x - i)[..., None]
        p0, p1 = self._p[i], self._p[i + 1]
        v0, v1 = self._v[i] * self._step, self._v[i + 1] * self._step
        u2, u3 = u * u, u * u * u
        position = (2*u3 - 3*u2 + 1) * p0 + (u3 - 2*u2 + u) * v0 + (3*u2 - 2*u3) * p1 + (u3 - u2) * v1
        velocity = ((6*u2 - 6*u) * p0 + (3*u2 - 4*u + 1) * v0 + (6*u - 6*u2) * p1
                    + (3*u2 - 2*u) * v1) / self._step
        return np.moveaxis(position, -1, 0), np.moveaxis(velocity, -1, 0), None, None


@functools.lru_cache(maxsize=None)
def _minor_planet(name):
    """(DE440 Sun + tabulated orbit, (H, G)) of a minor planet of the Horizons tables."""
    with np.load(_MINOR_TABLE) as table:
        orbit = _TabulatedOrbit(name, table[f"{name}_start"], table[f"{name}_position"],
                                table[f"{name}_velocity"])
        hg = tuple(float(v) for v in table[f"{name}_hg"])
    return _sky()["sun"] + orbit, hg


@functools.lru_cache(maxsize=None)
def _comet(name):
    """(DE440 Sun + tabulated orbit, (M1, K1), (first, last JD)) of a comet of the Horizons tables."""
    with np.load(_COMET_TABLE) as table:
        start = table[f"{name}_start"]
        positions = table[f"{name}_position"]
        orbit = _TabulatedOrbit(name, start, positions, table[f"{name}_velocity"])
        m1k1 = tuple(float(v) for v in table[f"{name}_m1k1"])
    first = float(start[0])
    return _sky()["sun"] + orbit, m1k1, (first, first + float(start[1]) * (len(positions) - 1))


def _fast_time(jd_ut):
    """Skyfield time of UT Julian Days with the IAU 2000B nutation (1 mas, 20 times
    faster than 2000A): enough for altitudes and the visibility of events."""
    from skyfield.nutationlib import iau2000b_radians
    time = _sky()["ts"].ut1_jd(jd_ut)
    time._nutation_angles_radians = iau2000b_radians(time)
    return time


def _hg_magnitude(h, g, r, delta, phase_deg):
    """Visual magnitude of an asteroid, IAU H, G system (Bowell et al., 1989)."""
    tan_half = np.tan(np.radians(phase_deg) / 2.0)
    phi1 = np.exp(-3.33 * tan_half ** 0.63)
    phi2 = np.exp(-1.87 * tan_half ** 1.22)
    return h + 5.0 * np.log10(r * delta) - 2.5 * np.log10((1.0 - g) * phi1 + g * phi2)

# ==========================================================
# MAIN ENGINE
# ==========================================================

class AstroEngine:
    """
    Encapsulates all astronomical calculations, independent of the interface.

    All methods are class methods or static methods: no internal state is
    preserved (the ephemeris is loaded once, on first use). The positions
    come from JPL DE440 (Skyfield); the eclipse geometry follows Meeus,
    chap. 54.
    """

    @staticmethod
    def mod360(a):
        """Returns angle normalised to [0, 360[."""
        return a % 360

    @classmethod
    def julian_day(cls, dte):
        """Calculates Julian Day (JD) for a given datetime (Meeus, chap. 7)."""
        y, m, d = dte.year, dte.month, dte.day
        h, mn, s = dte.hour, dte.minute, dte.second
        if m <= 2:
            y -= 1; m += 12
        a = math.floor(y / 100)
        b = 2 - a + math.floor(a / 4)
        frac = d + h/24.0 + mn/1440.0 + s/86400.0
        return math.floor(365.25*(y+4716)) + math.floor(30.6001*(m+1)) + frac + b - 1524.5

    @classmethod
    def julian_century_j2000(cls, dte):
        """Calculates T in Julian centuries since J2000.0."""
        return (cls.julian_day(dte) - 2451545.0) / 36525.0


    @staticmethod
    def delta_t(year):
        """
        ΔT = TT − UT in seconds, for a decimal year (Skyfield): UT1 measured
        by the IERS since 1973, then its predictions; before, the spline of
        Stephenson, Morrison & Hohenkerk (2016). About 69.1 s in 2026.
        """
        return float(_sky()["ts"].J(year).delta_t)

    # ──────────────────────────────────────────────────────────────────
    # TIME AND APPARENT POSITIONS (JPL DE440)
    # ──────────────────────────────────────────────────────────────────

    @staticmethod
    def _time_ut(t):
        """Skyfield Time of t, Julian centuries of UT since J2000.0 (number or array)."""
        return _sky()["ts"].ut1_jd(2451545.0 + 36525.0 * t)

    @staticmethod
    def _time_tt(t):
        """Skyfield Time of t, Julian centuries of TT since J2000.0 (number or array)."""
        return _sky()["ts"].tt_jd(2451545.0 + 36525.0 * t)

    @staticmethod
    def _apparent_ecliptic(target, time):
        """Apparent geocentric (longitude°, latitude°, Distance), true ecliptic and equinox of date."""
        sky = _sky()
        lat, lon, dist = sky["earth"].at(time).observe(sky[target]).apparent().ecliptic_latlon(epoch="date")
        return lon.degrees, lat.degrees, dist

    @classmethod
    def _moon(cls, time):
        lon, lat, dist = cls._apparent_ecliptic("moon", time)
        km = dist.km
        return lon, lat, km, np.degrees(np.arcsin(_EARTH_RADIUS_KM / km))

    @classmethod
    def sun_position(cls, t):
        """
        Apparent ecliptic longitude (°, true equinox of date) and distance
        (AU) of the Sun, DE440.

        Args:
            t (float | numpy.ndarray): Julian centuries of UT since J2000.0.
        """
        lon, _, dist = cls._apparent_ecliptic("sun", cls._time_ut(t))
        return lon, dist.au

    @classmethod
    def sun_position_tt(cls, t):
        """sun_position() for t in Julian centuries of TT (eclipse search)."""
        lon, _, dist = cls._apparent_ecliptic("sun", cls._time_tt(t))
        return lon, dist.au

    @classmethod
    def moon_position(cls, t):
        """
        Apparent geocentric Moon, DE440.

        Args:
            t (float | numpy.ndarray): Julian centuries of UT since J2000.0.

        Returns:
            tuple: (longitude°, latitude°, horizontal parallax°)
        """
        lon, lat, _, parallax = cls._moon(cls._time_ut(t))
        return lon, lat, parallax

    @classmethod
    def moon_position_tt(cls, t):
        """
        Apparent geocentric Moon for t in Julian centuries of TT.

        Returns:
            tuple: (longitude°, latitude°, distance_km, horizontal parallax°)
        """
        return cls._moon(cls._time_tt(t))

    @classmethod
    def equation_of_time(cls, t):
        """
        Equation of Time in minutes (apparent − mean solar time): the
        Greenwich hour angle of the apparent Sun (apparent sidereal time
        minus its right ascension, DE440) against UT1.
        """
        sky  = _sky()
        time = cls._time_ut(t)
        ra, _, _ = sky["earth"].at(time).observe(sky["sun"]).apparent().radec(epoch="date")
        ut_hours = ((time.ut1 + 0.5) % 1.0) * 24.0
        return ((time.gast - ra.hours + 12.0 - ut_hours + 12.0) % 24.0 - 12.0) * 60.0

    # ──────────────────────────────────────────────────────────────────
    # NUTATION AND OBLIQUITY (coordinate conversions of the interface)
    # ──────────────────────────────────────────────────────────────────

    @staticmethod
    def _nutation(t):
        """
        Nutation in longitude Δψ and in obliquity Δε (degrees): the four
        main terms of IAU 1980 (Meeus, chap. 22), 0.5" and 0.1".
        """
        om = math.radians(125.04452 - 1934.136261 * t)      # Moon's node
        ls = math.radians(2.0 * (280.4665 + 36000.7698 * t))   # 2 L (Sun)
        lm = math.radians(2.0 * (218.3165 + 481267.8813 * t))  # 2 L′ (Moon)
        d_psi = -17.20*math.sin(om) - 1.32*math.sin(ls) - 0.23*math.sin(lm) + 0.21*math.sin(2*om)
        d_eps =   9.20*math.cos(om) + 0.57*math.cos(ls) + 0.10*math.cos(lm) - 0.09*math.cos(2*om)
        return d_psi / 3600.0, d_eps / 3600.0

    @classmethod
    def _nutation_longitude(cls, t):
        """Nutation in longitude Δψ (degrees)."""
        return cls._nutation(t)[0]

    @classmethod
    def _obliquity(cls, t):
        """
        True obliquity of the ecliptic (radians): IAU 2006 mean obliquity
        (Capitaine et al. 2003) plus the nutation in obliquity Δε.
        """
        eps0 = 84381.406 - 46.836769*t - 0.0001831*t**2 + 0.00200340*t**3
        return math.radians(eps0 / 3600.0 + cls._nutation(t)[1])


    # ──────────────────────────────────────────────────────────────────
    # APPARENT DIAMETERS AND ECLIPSE HELPERS
    # ──────────────────────────────────────────────────────────────────

    @staticmethod
    def _sun_semi_diameter(r_au):
        """Sun apparent semi-diameter in degrees given distance in AU."""
        return 0.26667 / r_au

    @staticmethod
    def _moon_semi_diameter(dist_km):
        """Moon apparent semi-diameter in degrees given geocentric distance in km."""
        return math.degrees(math.asin(1737.4 / dist_km))

    @classmethod
    def _shadow_axis(cls, jd):
        """
        Besselian elements of the Moon's shadow at jd (TT), from the apparent
        DE440 positions of the Sun and the Moon (true equator of date).

        The fundamental plane goes through the Earth's centre, perpendicular to
        the shadow axis (the Sun–Moon line); x points east, y north, and lengths
        are in Earth equatorial radii.

        Returns:
            tuple: (x, y, a, d, l1, l2, tan_f1, tan_f2)
                x, y           : point where the shadow axis crosses the plane
                a, d           : right ascension and declination of the axis (rad)
                l1, l2         : radii of the penumbra and of the umbra in the plane
                                 (l2 < 0: the umbra goes beyond it; l2 > 0: antumbra)
                tan_f1, tan_f2 : slopes of the penumbral and umbral cones
        """
        sky   = _sky()
        earth = sky["earth"].at(sky["ts"].tt_jd(jd))
        sun, moon = (earth.observe(sky[b]).apparent().frame_xyz(true_equator_and_equinox_of_date).km
                     / _EARTH_RADIUS_KM for b in ("sun", "moon"))

        gx, gy, gz = (s - m for s, m in zip(sun, moon))
        g    = math.sqrt(gx*gx + gy*gy + gz*gz)                # Sun–Moon distance
        a, d = math.atan2(gy, gx), math.asin(gz / g)
        sin_a, cos_a, sin_d, cos_d = math.sin(a), math.cos(a), math.sin(d), math.cos(d)

        mx, my, mz = moon
        x = -mx*sin_a + my*cos_a
        y = -mx*sin_d*cos_a - my*sin_d*sin_a + mz*cos_d
        z =  mx*cos_d*cos_a + my*cos_d*sin_a + mz*sin_d

        sin_f1 = (_SUN_RADIUS + _MOON_RADIUS_PENUMBRA) / g
        sin_f2 = (_SUN_RADIUS - _MOON_RADIUS_UMBRA) / g
        tan_f1 = sin_f1 / math.sqrt(1.0 - sin_f1*sin_f1)
        tan_f2 = sin_f2 / math.sqrt(1.0 - sin_f2*sin_f2)
        l1 = (z + _MOON_RADIUS_PENUMBRA / sin_f1) * tan_f1
        l2 = (z - _MOON_RADIUS_UMBRA / sin_f2) * tan_f2
        return x, y, a, d, l1, l2, tan_f1, tan_f2

    @classmethod
    def _solar_eclipse(cls, jd_nm):
        """
        Circumstances of the solar eclipse of the new moon jd_nm, if any.

        The shadow axis is followed in the fundamental plane (_shadow_axis) to
        greatest eclipse, its closest approach to the Earth's centre, at the
        distance γ. Meeus's rules (chap. 54) are then applied to the radii of
        the shadow cones:
          • |γ| ≥ 0.9972 + l1 : the penumbra misses the Earth, no eclipse;
          • |γ| < 0.9972      : central eclipse — annular if the antumbra reaches
                                the central line at greatest eclipse, total if
                                the umbra goes beyond the fundamental plane,
                                hybrid in between (total mid-path, annular at
                                its ends);
          • otherwise         : partial, or total / annular when the umbra or
                                antumbra still grazes a polar region.

        Magnitude: Moon/Sun apparent diameter ratio on the central line at
        greatest eclipse (central eclipses), otherwise fraction of the Sun's
        diameter covered where the Earth is closest to the axis (Meeus 54).
        The central phase lasts 2·|L2| / v on the central line, L2 being the
        shadow radius there and v the speed of the shadow over the ground,
        the Earth's rotation included: at most ~7.5 min for a total eclipse,
        ~12.5 min for an annular one.

        Args:
            jd_nm (float): Julian Day of the new moon.

        Returns:
            dict | None: None without eclipse, else keys
                jd           : greatest eclipse (Julian Day)
                gamma        : signed γ, Earth radii (> 0: axis north of the centre)
                sub_type     : 'total' | 'annular' | 'hybrid' | 'partial'
                magnitude    : see above
                duration_min : central phase on the central line, None if not central
                certainty    : 'possible' when |γ| lies within _GAMMA_ACCURACY of
                               the no-eclipse limit, else 'certain'

        Reference: Meeus, chap. 54; Explanatory Supplement to the Astronomical
        Almanac (1992), chap. 8 (Besselian elements).
        """
        step = 1.0 / 24.0                                   # one hour, in days
        jd   = jd_nm
        for _ in range(5):
            x, y, a, d, l1, l2, tan_f1, tan_f2 = cls._shadow_axis(jd)
            x_m, y_m, a_m, d_m = cls._shadow_axis(jd - step)[:4]
            x_p, y_p, a_p, d_p = cls._shadow_axis(jd + step)[:4]
            vx, vy = (x_p - x_m) / 2.0, (y_p - y_m) / 2.0   # Earth radii per hour
            tau = -(x*vx + y*vy) / (vx*vx + vy*vy)          # hours to the closest approach
            if abs(tau) < 1e-3:                             # 3.6 s
                break
            jd += tau / 24.0
        gamma = (y*vx - x*vy) / math.hypot(vx, vy)

        limit = _CENTRAL_LIMIT + l1
        if abs(gamma) >= limit:
            return None
        certainty = 'certain' if abs(gamma) < limit - _GAMMA_ACCURACY else 'possible'

        if abs(gamma) < _CENTRAL_LIMIT:
            zeta = math.sqrt(1.0 - gamma*gamma)             # central line point, above the plane
            L1   = l1 - zeta*tan_f1                         # shadow radii at that point
            L2   = l2 - zeta*tan_f2
            if L2 > 0:     sub_type = 'annular'
            elif l2 < 0:   sub_type = 'total'
            else:          sub_type = 'hybrid'
            magnitude = (L1 - L2) / (L1 + L2)
            # Velocity of that point in the plane as the Earth turns (Besselian ξ', η')
            da       = (a_p - a_m + math.pi) % (2.0*math.pi) - math.pi
            mu_rate  = _SIDEREAL_RATE - da / 2.0            # hour angle of the axis, rad/h
            xi_rate  = mu_rate * (zeta*math.cos(d) - y*math.sin(d))
            eta_rate = mu_rate * x * math.sin(d) - zeta * (d_p - d_m) / 2.0
            ground_speed = math.hypot(vx - xi_rate, vy - eta_rate)
            duration = round(120.0 * abs(L2) / ground_speed, 1)
        else:
            if abs(gamma) < _CENTRAL_LIMIT + abs(l2):
                sub_type = 'total' if l2 < 0 else 'annular'
            else:
                sub_type = 'partial'
            magnitude = (limit - abs(gamma)) / (l1 + l2)
            duration  = None

        return {'jd': jd, 'gamma': gamma, 'sub_type': sub_type, 'magnitude': magnitude,
                'duration_min': duration, 'certainty': certainty}

    @classmethod
    def _shadow_offset(cls, jd):
        """
        The Moon's offset from the centre of the Earth's shadow at jd, with
        what sizes the shadow.

        The centre of the shadow is the antisolar point of the apparent Sun;
        both bodies are apparent DE440 positions.

        Returns:
            tuple: (x, y, sun_au, moon_km, moon_parallax)
                x, y          : offset in degrees, x eastward along the ecliptic,
                                y northward (latitude from the antisolar point)
                sun_au        : Sun distance, AU
                moon_km       : Moon distance, km
                moon_parallax : Moon's horizontal parallax, degrees
        """
        time = _sky()["ts"].tt_jd(jd)
        sun_lon, sun_lat, sun_d = cls._apparent_ecliptic("sun", time)
        moon_lon, moon_lat, moon_d = cls._apparent_ecliptic("moon", time)
        moon_km  = moon_d.km
        moon_par = math.degrees(math.asin(_EARTH_RADIUS_KM / moon_km))
        x = ((moon_lon - sun_lon) % 360.0 - 180.0) * math.cos(math.radians(moon_lat))
        return x, moon_lat + sun_lat, sun_d.au, moon_km, moon_par

    @classmethod
    def _lunar_eclipse(cls, jd_fm):
        """
        Circumstances of the lunar eclipse of the full moon jd_fm, if any.

        The Moon is followed relative to the centre of the Earth's shadow
        (_shadow_offset) to greatest eclipse, its closest approach, at the
        distance d. The shadow radii follow Danjon's rule, as NASA's canon:
            umbra     ρu = 1.01176 × 0.998340 × πM + πS − sS
            penumbra  ρp = 1.01176 × 0.998340 × πM + πS + sS
        (π: horizontal parallaxes of the Moon and the Sun, sS: the Sun's
        semi-diameter). With s the Moon's semi-diameter:
            umbral magnitude    = (ρu + s − d) / 2s   ≥ 1: total, > 0: partial
            penumbral magnitude = (ρp + s − d) / 2s   ≤ 0: no eclipse
        A phase lasts while the distance stays under ρp + s (penumbral), ρu + s
        (partial) or ρu − s (total), the Moon moving in a straight line around
        greatest eclipse: 2·√(R² − d²) / v.

        Args:
            jd_fm (float): Julian Day of the full moon.

        Returns:
            dict | None: None without eclipse, else keys
                jd                  : greatest eclipse (Julian Day)
                gamma               : distance of the Moon's centre from the shadow
                                      axis, Earth radii (> 0: Moon north of it)
                sub_type            : 'total' | 'partial' | 'penumbral'
                umbral_magnitude, penumbral_magnitude
                magnitude           : the umbral magnitude, or the penumbral one
                                      for a penumbral eclipse
                durations           : minutes of the 'penumbral', 'partial' and
                                      'total' phases (None for a phase that does
                                      not occur)
                duration_min        : the total phase, None if not total
                certainty           : 'possible' when the penumbral magnitude is
                                      under _LUNAR_MAG_ACCURACY, else 'certain'

        Reference: Meeus, chap. 54; F. Espenak & J. Meeus, Five Millennium
        Canon of Lunar Eclipses (NASA, 2009).
        """
        step = 1.0 / 24.0                                   # one hour, in days
        jd   = jd_fm
        for _ in range(6):
            x, y, sun_au, moon_km, moon_par = cls._shadow_offset(jd)
            x_m, y_m = cls._shadow_offset(jd - step)[:2]
            x_p, y_p = cls._shadow_offset(jd + step)[:2]
            vx, vy = (x_p - x_m) / 2.0, (y_p - y_m) / 2.0   # degrees per hour
            tau = -(x*vx + y*vy) / (vx*vx + vy*vy)          # hours to the closest approach
            if abs(tau) < 1e-3:                             # 3.6 s
                break
            jd += tau / 24.0
        speed = math.hypot(vx, vy)
        d     = abs(y*vx - x*vy) / speed

        earth = _DANJON_ENLARGEMENT * _PARALLAX_FLATTENING * moon_par
        sun_par, sun_sd = _SUN_PARALLAX_1AU / sun_au, _SUN_SEMI_DIAMETER_1AU / sun_au
        rho_u, rho_p = earth + sun_par - sun_sd, earth + sun_par + sun_sd
        s = cls._moon_semi_diameter(moon_km)
        umbral    = (rho_u + s - d) / (2.0 * s)
        penumbral = (rho_p + s - d) / (2.0 * s)
        if penumbral <= 0.0:
            return None

        def phase(radius):
            if radius <= d:
                return None
            return round(120.0 * math.sqrt(radius*radius - d*d) / speed, 1)

        durations = {'penumbral': phase(rho_p + s), 'partial': phase(rho_u + s),
                     'total': phase(rho_u - s)}
        if umbral >= 1.0:   sub_type = 'total'
        elif umbral > 0.0:  sub_type = 'partial'
        else:               sub_type = 'penumbral'
        return {
            'jd':                  jd,
            'gamma':               math.copysign(d / moon_par, y),
            'sub_type':            sub_type,
            'umbral_magnitude':    umbral,
            'penumbral_magnitude': penumbral,
            'magnitude':           penumbral if sub_type == 'penumbral' else umbral,
            'durations':           durations,
            'duration_min':        durations['total'],
            'certainty':           'possible' if penumbral < _LUNAR_MAG_ACCURACY else 'certain',
        }


    # ──────────────────────────────────────────────────────────────────
    # COORDINATE CONVERSIONS
    # ──────────────────────────────────────────────────────────────────

    @classmethod
    def ecliptic_to_equatorial(cls, l_deg, b_deg, t):
        """Ecliptic → equatorial conversion, true obliquity of date (Meeus, chap. 13)."""
        eps = cls._obliquity(t)
        l, b = math.radians(l_deg), math.radians(b_deg)
        ra  = math.atan2(math.sin(l)*math.cos(eps) - math.tan(b)*math.sin(eps), math.cos(l))
        dec = math.asin(math.sin(b)*math.cos(eps) + math.cos(b)*math.sin(eps)*math.sin(l))
        return cls.mod360(math.degrees(ra))/15.0, math.degrees(dec)

    @classmethod
    def equatorial_to_horizontal(cls, jd, lat, lon, ra_h, dec_deg):
        """Equatorial → local horizontal conversion (Meeus, chap. 13)."""
        # apparent sidereal time at Greenwich (Meeus, chap. 12)
        t      = (jd - 2451545.0) / 36525.0
        theta0 = (280.46061837 + 360.98564736629*(jd - 2451545.0)
                  + 0.000387933*t*t - t**3/38710000.0
                  + cls._nutation_longitude(t) * math.cos(cls._obliquity(t)))
        lst    = cls.mod360(theta0 + lon)
        tau    = math.radians(lst - ra_h*15.0)
        phi, delta = math.radians(lat), math.radians(dec_deg)
        h  = math.asin(math.sin(phi)*math.sin(delta) + math.cos(phi)*math.cos(delta)*math.cos(tau))
        az = cls.mod360(math.degrees(math.atan2(
            -math.sin(tau),
            math.cos(phi)*math.tan(delta) - math.sin(phi)*math.cos(tau))))
        return math.degrees(h), az

    @staticmethod
    def elevation_correction(h_true, parallax_deg):
        """
        Apparent altitude from the geocentric one: parallax in altitude
        (π cos h, Meeus chap. 40), then the refraction at the topocentric
        altitude (Sæmundsson, Meeus chap. 16).
        """
        h = h_true - math.degrees(math.asin(math.sin(math.radians(parallax_deg))
                                             * math.cos(math.radians(h_true))))
        if h < -5.0:
            return h
        return h + (1.02 / math.tan(math.radians(h + _REFRACTION_A / (h + _REFRACTION_B)))) / 60.0


    # ──────────────────────────────────────────────────────────────────
    # DAILY EVENTS
    # ──────────────────────────────────────────────────────────────────

    @staticmethod
    def _local_day(dte_ref, tz):
        """
        UT bounds of the local day of dte_ref: tz is a number of hours east
        of UT, or a tzinfo (zoneinfo), which gives the 23 or 25 hour days of
        the changes to and from summer time. Naive datetimes are UT; aware
        ones come back in UTC.
        """
        if isinstance(tz, (int, float)):
            offset = timedelta(hours=tz)
            start  = (dte_ref + offset).replace(hour=0, minute=0, second=0, microsecond=0) - offset
            return start, start + timedelta(days=1)
        aware    = dte_ref if dte_ref.tzinfo else dte_ref.replace(tzinfo=timezone.utc)
        midnight = aware.astimezone(tz).replace(hour=0, minute=0, second=0, microsecond=0)
        start, end = (m.astimezone(timezone.utc) for m in (midnight, midnight + timedelta(days=1)))
        if dte_ref.tzinfo is None:
            return start.replace(tzinfo=None), end.replace(tzinfo=None)
        return start, end

    @classmethod
    def find_events(cls, dte_ref, lat, lon, body="sun", tz=0, elevation_m=0.0):
        """
        Rises, sets, transit and twilights over the local day of dte_ref,
        to the second (Skyfield almanac, DE440).

        Rises and sets are those of the upper limb with the standard
        refraction (34′), the Moon seen from the observer (its parallax);
        from a height, the horizon is lowered by its dip (1.76′ √h). The
        transit is the upper meridian transit; the twilights begin and end
        when the Sun's geometric centre is 6, 12 or 18° below the horizon.

        Args:
            dte_ref (datetime): instant of the day, UT (naive or aware).
            lat, lon (float): degrees, east positive.
            body (str): "sun", "moon" or a planet name ("Venus"…).
            tz (float | tzinfo): local time zone, hours east of UT or a
                zoneinfo.ZoneInfo (summer time included); the day searched
                runs from local midnight to midnight.
            elevation_m (float): observer's height above the horizon, metres.

        Returns:
            dict with keys: rise, set, transit,
                            dawn_civ, dusk_civ, dawn_naut, dusk_naut,
                            dawn_astro, dusk_astro  (sun only)
            UT datetimes (tzinfo of dte_ref kept), None when it does not occur.
        """
        events = dict.fromkeys(('rise', 'set', 'transit', 'dawn_civ', 'dusk_civ',
                                'dawn_naut', 'dusk_naut', 'dawn_astro', 'dusk_astro'))
        start, end = cls._local_day(dte_ref, tz)
        t0 = cls._time_ut(cls.julian_century_j2000(start))
        t1 = cls._time_ut(cls.julian_century_j2000(end))
        sky      = _sky()
        observer = sky["earth"] + wgs84.latlon(lat, lon, elevation_m=elevation_m)
        target   = cls._target(body)
        horizon  = None                                 # Skyfield's standard horizon
        if elevation_m > 0:
            middle = cls._time_ut(cls.julian_century_j2000(start + (end - start) / 2))
            km = sky["earth"].at(middle).observe(target).distance().km
            horizon = -(_HORIZON_REFRACTION + math.degrees(math.asin(_BODY_RADIUS_KM.get(body, 0.0) / km))
                        + _HORIZON_DIP * math.sqrt(elevation_m))

        def first(times, crosses=None):
            for i in range(len(times)):
                if crosses is None or crosses[i]:
                    return cls._jd_to_datetime(times[i].ut1, start)
            return None

        events['rise']    = first(*almanac.find_risings(observer, target, t0, t1, horizon))
        events['set']     = first(*almanac.find_settings(observer, target, t0, t1, horizon))
        events['transit'] = first(almanac.find_transits(observer, target, t0, t1))
        if body == "sun":
            for depth, name in _TWILIGHTS:
                events['dawn_' + name] = first(*almanac.find_risings(
                    observer, target, t0, t1, horizon_degrees=-depth))
                events['dusk_' + name] = first(*almanac.find_settings(
                    observer, target, t0, t1, horizon_degrees=-depth))
        return events

    @classmethod
    def altitudes(cls, dtes, lat, lon, elevation_m=0.0):
        """
        Altitudes of the Sun (geometric centre) and of the Moon (seen from the
        observer, standard refraction) at the UT datetimes dtes, in one
        vectorised DE440 computation.

        Returns:
            tuple[numpy.ndarray, numpy.ndarray]: (sun, moon) altitudes, degrees
        """
        sky  = _sky()
        time = cls._time_ut(np.array([cls.julian_century_j2000(d) for d in dtes]))
        here = (sky["earth"] + wgs84.latlon(lat, lon, elevation_m=elevation_m)).at(time)
        sun_alt, _, _  = here.observe(sky["sun"]).apparent().altaz()
        moon_alt, _, _ = here.observe(sky["moon"]).apparent().altaz(temperature_C=10.0,
                                                                     pressure_mbar=1010.0)
        return sun_alt.degrees, moon_alt.degrees

    @classmethod
    def horizontal(cls, t, lat, lon, body, elevation_m=0.0, refraction=False):
        """
        Apparent altitude and azimuth (degrees) of a body seen from the
        observer (topocentric, DE440): its parallax included, which lowers the
        Moon by up to 1°.

        Args:
            t (float): Julian centuries of UT since J2000.0.
            body (str): "sun", "moon", "Venus", "Mars", "Jupiter" or "Saturn".
            refraction (bool): add the standard refraction (10 °C, 1010 hPa).
        """
        sky    = _sky()
        here   = (sky["earth"] + wgs84.latlon(lat, lon, elevation_m=elevation_m)).at(cls._time_ut(t))
        target = cls._target(body)
        air    = {"temperature_C": 10.0, "pressure_mbar": 1010.0} if refraction else {}
        alt, az, _ = here.observe(target).apparent().altaz(**air)
        return alt.degrees, az.degrees

    @classmethod
    def stars_horizontal(cls, t, lat, lon, ra_hours, dec_degrees, elevation_m=0.0,
                         pm_ra_mas=None, pm_dec_mas=None):
        """
        Altitudes and azimuths (degrees, geometric) of stars given by their
        J2000 coordinates (ICRS): precession, nutation and aberration to the
        date in one vectorised computation. Without them, a J2000 position is
        off by 50″ a year (0.37° in 2026).

        Args:
            t (float): Julian centuries of UT since J2000.0.
            ra_hours, dec_degrees (sequence): J2000 right ascensions (h) and
                declinations (°).
            pm_ra_mas, pm_dec_mas (sequence): proper motions (μα·cos δ, μδ),
                milliseconds of arc a year (none by default).

        Returns:
            tuple[numpy.ndarray, numpy.ndarray]: (altitudes, azimuths)
        """
        sky   = _sky()
        ra = np.asarray(ra_hours, dtype=float)
        motion = {} if pm_ra_mas is None else {
            "ra_mas_per_year": np.asarray(pm_ra_mas, dtype=float),
            "dec_mas_per_year": np.asarray(pm_dec_mas, dtype=float)}
        stars = Star(ra_hours=ra, dec_degrees=np.asarray(dec_degrees, dtype=float), **motion)
        here  = (sky["earth"] + wgs84.latlon(lat, lon, elevation_m=elevation_m)).at(cls._time_ut(t))
        alt, az, _ = here.observe(stars).apparent().altaz()
        return alt.degrees, az.degrees

    # The bodies of the coordinates table, in the order of the Solar System
    BODIES  = ("sun", "moon", "Mercury", "Venus", "earth", "Mars", "Ceres", "Pallas", "Juno",
               "Vesta", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto", "Haumea", "Makemake",
               "Eris", "Sedna")
    CENTERS = ("heliocentric", "geocentric", "topocentric")
    FRAMES  = ("ecliptic", "equatorial", "horizontal")

    @classmethod
    def coordinates(cls, t, body, center="geocentric", frame="equatorial",
                    lat=0.0, lon=0.0, elevation_m=0.0):
        """
        Coordinates of a body in the chosen system, as angles and as x, y, z.

        Centres, following the ephemerides (JPL Horizons, Astronomical Almanac):
          • heliocentric — geometric position from the Sun's centre, mean
            ecliptic or equator and equinox of J2000;
          • geocentric, topocentric — apparent position (light time,
            aberration, deflection) from the Earth's centre or from the
            observer, true ecliptic or equator and equinox of the date.
        Frames: "ecliptic" (λ, β), "equatorial" (α, δ) or "horizontal"
        (azimuth from the north through the east, altitude without refraction;
        not for the heliocentric centre).

        Args:
            t (float): Julian centuries of UT since J2000.0.
            body (str): one of BODIES ("sun", "moon", "earth" or a planet name).
            lat, lon, elevation_m: observer (topocentric centre, horizontal frame).

        Returns:
            dict | None: lon (°, [0, 360[: λ, α in degrees or azimuth), lat (°:
            β, δ or altitude), dist (AU), x, y, z (AU: x towards the equinox, or
            the north for the horizontal frame, z towards the pole or the
            zenith); None when the body is the centre itself.
        """
        if center not in cls.CENTERS or frame not in cls.FRAMES:
            raise ValueError(f"unknown system: {center}, {frame}")
        if frame == "horizontal" and center == "heliocentric":
            raise ValueError("no horizontal frame for heliocentric coordinates")
        sky  = _sky()
        time = cls._time_ut(t)
        target = cls._target(body)
        here = wgs84.latlon(lat, lon, elevation_m=elevation_m)
        if center == "heliocentric":
            if body == "sun":
                return None
            position = target.at(time) - sky["sun"].at(time)
            reference = ecliptic_J2000_frame if frame == "ecliptic" else None   # None: ICRS
        else:
            if body == "earth":
                return None
            origin = sky["earth"] if center == "geocentric" else sky["earth"] + here
            position = origin.at(time).observe(target).apparent()
            reference = {"ecliptic": ecliptic_frame, "horizontal": here,
                         "equatorial": true_equator_and_equinox_of_date}[frame]
        if reference is None:
            lat_, lon_, dist = position.radec()
            lon_deg = lon_.hours * 15.0
            x, y, z = position.position.au
        else:
            lat_, lon_, dist = position.frame_latlon(reference)
            lon_deg = lon_.degrees
            x, y, z = position.frame_xyz(reference).au
        return {"lon": float(lon_deg) % 360.0, "lat": float(lat_.degrees), "dist": float(dist.au),
                "x": float(x), "y": float(y), "z": float(z)}

    @classmethod
    def _target(cls, body):
        """Target of a body name: "sun", "moon", "earth", a planet, a minor planet
        or a star of MOON_STARS."""
        sky = _sky()
        if body.lower() in ("sun", "moon"):
            return sky[body.lower()]
        if body in cls.MOON_STARS:
            return cls._star_target(body)
        name = body.capitalize()
        if name in _PLANETS:
            return sky["eph"][_PLANETS[name]]
        if name in COMETS:
            return _comet(name)[0]
        return _minor_planet(name)[0]

    @staticmethod
    def comet_years():
        """(first, last) years covered by the comet tables, all comets together."""
        from datetime import datetime as _dt
        spans = [_comet(name)[2] for name in COMETS]
        to_year = lambda jd: (_dt(2000, 1, 1, 12) + timedelta(days=jd - 2451545.0)).year
        return to_year(min(a for a, _b in spans)), to_year(max(b for _a, b in spans))

    @staticmethod
    def comets_at(t):
        """The comets whose table covers the instant t (Julian centuries of UT since J2000.0)."""
        jd = 2451545.0 + 36525.0 * t
        return tuple(name for name in COMETS if _comet(name)[2][0] + 1.0 <= jd <= _comet(name)[2][1] - 1.0)

    @classmethod
    def observations(cls, t, bodies=None):
        """
        How the bodies look from the Earth's centre (DE440, apparent): visual
        magnitude, angle with the Sun (elongation) and constellation (IAU
        boundaries), computed together.

        Magnitudes: Mallama & Hilton (2018) from Mercury to Neptune (Skyfield);
        Allen's Astrophysical Quantities for the Sun, the Moon and Pluto; the
        IAU H, G system (Bowell et al., 1989) for the other minor planets.

        Args:
            t (float): Julian centuries of UT since J2000.0.
            bodies (sequence): names among BODIES (all by default).

        Returns:
            dict: {body: {"mag", "elongation" (None for the Sun), "constellation"
            (IAU abbreviation, as "Cap"), "constellation_name" (Latin name)}},
            None for the Earth.
        """
        sky    = _sky()
        time   = cls._time_ut(t)
        earth  = sky["earth"].at(time)
        sun_at = sky["sun"].at(time)
        sun    = earth.observe(sky["sun"]).apparent()
        result = {}
        for body in bodies or cls.BODIES:
            if body == "earth":
                result[body] = None
                continue
            target = cls._target(body)
            astrometric = earth.observe(target)
            apparent = astrometric.apparent()
            delta = astrometric.distance().au
            if body == "sun":
                mag, elongation = _SUN_MAGNITUDE_1AU + 5.0 * math.log10(delta), None
            else:
                elongation = float(apparent.separation_from(sun).degrees)
                if body in COMETS:
                    r = (target.at(time) - sun_at).distance().au
                    m1, k1 = _comet(body)[1]
                    mag = m1 + 5.0 * math.log10(delta) + k1 * math.log10(r)
                elif body in MINOR_PLANETS and body != "Pluto":
                    r = (target.at(time) - sun_at).distance().au
                    sun_dist = (sun_at - earth).distance().au
                    phase = math.degrees(math.acos(max(-1.0, min(1.0, (r*r + delta*delta - sun_dist*sun_dist)
                                                                 / (2.0 * r * delta)))))
                    mag = float(_hg_magnitude(*_minor_planet(body)[1], r, delta, phase))
                elif body in ("moon", "Pluto"):
                    r = (target.at(time) - sun_at).distance().au
                    phase = float(almanac.phase_angle(sky["eph"], _PLANETS.get(body, body), time).degrees)
                    if body == "moon":
                        h, k1, k4 = _MOON_MAGNITUDE
                        mag = h + 5.0 * math.log10(r * delta) + k1 * phase + k4 * phase ** 4
                    else:
                        h, k1 = _PLUTO_MAGNITUDE
                        mag = h + 5.0 * math.log10(r * delta) + k1 * phase
                else:
                    mag = float(planetary_magnitude(astrometric))
            abbreviation, name = _constellation(apparent)
            result[body] = {"mag": float(mag), "elongation": elongation,
                            "constellation": abbreviation, "constellation_name": name}
        return result

    @classmethod
    def body_details(cls, t, body):
        """
        What the data window of a body shows, seen from the Earth's centre
        (DE440, apparent): observations() (magnitude, elongation,
        constellation) and the distance in AU and km, the light time, the
        apparent diameter, the distance to the Sun, the phase angle (Sun–body–
        Earth) and the illuminated fraction of the disc.

        Args:
            t (float): Julian centuries of UT since J2000.0.
            body (str): "sun", "moon", a planet or a minor planet.

        Returns:
            dict: mag, elongation, constellation, constellation_name, dist_au,
            dist_km, light_time_s, diameter_arcsec, helio_au, phase_angle,
            illuminated (%) — None where it does not apply (the Sun).
        """
        sky = _sky()
        time = cls._time_ut(t)
        target = cls._target(body)
        astrometric = sky["earth"].at(time).observe(target)
        delta = astrometric.distance()
        seen = cls.observations(t, [body])[body]
        out = dict(seen, dist_au=float(delta.au), dist_km=float(delta.km),
                   light_time_s=float(delta.au) * _LIGHT_SECONDS_PER_AU,
                   diameter_arcsec=None, helio_au=None, phase_angle=None, illuminated=None)
        radius = _RADII_KM.get(body if body in ("sun", "moon") else body.capitalize())
        if radius:
            out["diameter_arcsec"] = 2.0 * math.degrees(math.asin(radius / float(delta.km))) * 3600.0
        if body != "sun":
            # Sun → body at the time the light left the body, and Earth → body
            emitted = time - delta.au * _LIGHT_SECONDS_PER_AU / 86400.0
            helio = (target.at(emitted) - sky["sun"].at(emitted)).position.au
            geo = astrometric.position.au
            r = float(np.linalg.norm(helio))
            cos_phase = float(np.dot(helio, geo) / (r * float(delta.au)))
            phase = math.degrees(math.acos(max(-1.0, min(1.0, cos_phase))))
            out.update(helio_au=r if body != "moon" else None, phase_angle=phase,
                       illuminated=None if body in COMETS else 50.0 * (1.0 + math.cos(math.radians(phase))))
        return out

    # ──────────────────────────────────────────────────────────────────
    # ECLIPSE PROJECTED ON THE GROUND
    # ──────────────────────────────────────────────────────────────────

    @staticmethod
    def _ellipsoid_hit(origin, direction):
        """
        First point where the lines origin + s·direction (s > 0, km, ITRS,
        arrays of shape (3, n)) meet the WGS84 ellipsoid; NaN where they miss.
        """
        k = np.array([[1.0], [1.0], [_WGS84_A / _WGS84_B]])
        o, d = origin * k, direction * k
        a = (d * d).sum(0)
        b = (o * d).sum(0)
        c = (o * o).sum(0) - _WGS84_A ** 2
        disc = b * b - a * c
        with np.errstate(invalid="ignore"):
            s = (-b - np.sqrt(disc)) / a
        s = np.where((disc >= 0) & (s > 0), s, np.nan)
        return origin + s * direction

    @staticmethod
    def _geodetic(xyz):
        """Geodetic latitudes and longitudes (degrees) of points on the WGS84 ellipsoid (km)."""
        x, y, z = xyz
        lat = np.degrees(np.arctan2(z, (1.0 - _WGS84_E2) * np.hypot(x, y)))
        return lat, np.degrees(np.arctan2(y, x))

    @staticmethod
    def _ellipsoid_points(lats, lons):
        """ITRS positions (km) and upward normals of points of the WGS84 ellipsoid."""
        phi, lam = np.radians(lats), np.radians(lons)
        n = _WGS84_A / np.sqrt(1.0 - _WGS84_E2 * np.sin(phi) ** 2)
        xyz = np.array([n * np.cos(phi) * np.cos(lam), n * np.cos(phi) * np.sin(lam),
                        n * (1.0 - _WGS84_E2) * np.sin(phi)])
        up = np.array([np.cos(phi) * np.cos(lam), np.cos(phi) * np.sin(lam), np.sin(phi)])
        return xyz, up

    @classmethod
    def _sun_moon_itrs(cls, time):
        """Apparent geocentric Sun and Moon in the Earth-fixed frame (ITRS), km, shape (3, n)."""
        sky   = _sky()
        earth = sky["earth"].at(time)
        return tuple(earth.observe(sky[b]).apparent().frame_xyz(itrs).km for b in ("sun", "moon"))

    @classmethod
    def eclipse_map(cls, greatest, kind, half_span_hours=3.5, grid_step=1.5):
        """
        An eclipse projected on the ground, around its greatest instant (DE440,
        WGS84 ellipsoid, Earth-fixed frame).

        Solar eclipse:
          • central  — central line: where the axis of the Moon's shadow meets
            the ground, minute by minute (lat, lon arrays; NaN off the Earth);
          • path     — footprints of the umbra (total) or antumbra (annular)
            on the ground, minute by minute (list of (lats, lons) polygons);
          • grid     — maximum magnitude reached at each point of a grid while
            the Sun is up (lats, lons, 2D array; 0 outside the partiality);
          • greatest — point of the central line at greatest eclipse, or the
            point of the Earth nearest the axis for a partial eclipse.
        Lunar eclipse:
          • grid     — altitude of the Moon (degrees) at greatest eclipse, and
            at the start and end of the partial phase (or of the penumbral one);
          • greatest — point where the Moon is at the zenith at greatest eclipse.

        Args:
            greatest (datetime): instant of greatest eclipse, UT.
            kind (str): "solar" or "lunar".
            half_span_hours (float): solar: the shadow is followed from
                greatest − half_span to greatest + half_span.
            grid_step (float): degrees between the grid points.

        Returns:
            dict: the elements above, with "kind".
        """
        sky = _sky()
        jd0 = cls.julian_day(greatest)
        lats = np.arange(-90.0 + grid_step / 2, 90.0, grid_step)
        lons = np.arange(-180.0 + grid_step / 2, 180.0, grid_step)
        glat, glon = np.meshgrid(lats, lons, indexing="ij")
        points, up = cls._ellipsoid_points(glat.ravel(), glon.ravel())

        if kind == "lunar":
            result = {"kind": "lunar", "lats": lats, "lons": lons}
            for key, offset in (("at_greatest", 0.0), ("at_start", -1.0), ("at_end", 1.0)):
                _sun, moon = cls._sun_moon_itrs(sky["ts"].ut1_jd(jd0 + offset * half_span_hours / 24.0))
                v = moon[:, None] - points
                alt = np.degrees(np.arcsin((v * up).sum(0) / np.linalg.norm(v, axis=0)))
                result[key] = alt.reshape(glat.shape)
            _sun, moon = cls._sun_moon_itrs(sky["ts"].ut1_jd(jd0))
            result["greatest"] = tuple(float(v) for v in cls._geodetic(moon / np.linalg.norm(moon)
                                                                     * _WGS84_A))
            return result

        # ── solar: the shadow followed minute by minute ───────────────────────
        minutes = np.arange(-60.0 * half_span_hours, 60.0 * half_span_hours + 1.0)
        sun, moon = cls._sun_moon_itrs(sky["ts"].ut1_jd(jd0 + minutes / 1440.0))
        axis = moon - sun
        axis /= np.linalg.norm(axis, axis=0)
        central = cls._ellipsoid_hit(moon, axis)
        c_lat, c_lon = cls._geodetic(central)

        # umbra / antumbra: cone through the Moon's limb and the apex of the umbra
        distance = np.linalg.norm(sun - moon, axis=0)
        apex = moon + axis * (_MOON_RADIUS_KM * distance / (_SUN_RADIUS_KM - _MOON_RADIUS_KM))
        u = np.cross(axis.T, [0.0, 0.0, 1.0]).T
        u /= np.linalg.norm(u, axis=0)
        w = np.cross(axis.T, u.T).T
        path = []
        for i in np.flatnonzero(~np.isnan(c_lat)):
            angles = np.linspace(0.0, 2.0 * np.pi, 33)
            limb = moon[:, i:i + 1] + _MOON_RADIUS_KM * (np.cos(angles) * u[:, i:i + 1]
                                                          + np.sin(angles) * w[:, i:i + 1])
            towards = apex[:, i:i + 1] - limb
            ground = cls._ellipsoid_hit(limb, towards / np.linalg.norm(towards, axis=0))
            if not np.isnan(ground).any():
                path.append(cls._geodetic(ground))

        # partiality: maximum magnitude while the Sun is up, every 4 minutes
        best = np.zeros(points.shape[1])
        for i in range(0, len(minutes), 4):
            vs, vm = sun[:, i:i + 1] - points, moon[:, i:i + 1] - points
            ds, dm = np.linalg.norm(vs, axis=0), np.linalg.norm(vm, axis=0)
            rs, rm = np.arcsin(_SUN_RADIUS_KM / ds), np.arcsin(_MOON_RADIUS_KM / dm)
            sep = np.arccos(np.clip((vs * vm).sum(0) / (ds * dm), -1.0, 1.0))
            mag = np.clip((rs + rm - sep) / (2.0 * rs), 0.0, None)
            mag[(vs * up).sum(0) <= 0.0] = 0.0                   # Sun below the horizon
            best = np.maximum(best, mag)

        middle = len(minutes) // 2
        if np.isnan(c_lat[middle]):                              # partial: nearest point to the axis
            k = int(np.argmax(best))
            greatest_point = (float(glat.ravel()[k]), float(glon.ravel()[k]))
        else:
            greatest_point = (float(c_lat[middle]), float(c_lon[middle]))
        return {"kind": "solar", "central": (c_lat, c_lon), "path": path,
                "lats": lats, "lons": lons, "grid": best.reshape(glat.shape),
                "greatest": greatest_point, "minutes": minutes}

    @classmethod
    def moon_phase(cls, t):
        """
        Illuminated fraction of the Moon (%, from the Sun–Moon–Earth angle,
        DE440) and its age (days since the last true new moon).

        Args:
            t (float): Julian centuries of UT since J2000.0.

        Returns:
            tuple[float, float]: (illumination %, age in days)
        """
        sky  = _sky()
        time = cls._time_ut(t)
        illumination = 100.0 * float(almanac.fraction_illuminated(sky["eph"], "moon", time))
        jd = float(time.tt)
        last_new_moon = max(j for j in _new_moons(int(jd // 10)) if j <= jd)
        return illumination, jd - last_new_moon

    # ──────────────────────────────────────────────────────────────────
    # PLANETS
    # ──────────────────────────────────────────────────────────────────

    @classmethod
    def planet_heliocentric(cls, t, name):
        """
        Heliocentric position of a planet (DE440).

        Args:
            t (float | numpy.ndarray): Julian centuries since J2000.0.
            name (str): "Venus", "Mars", "Jupiter", "Saturn" or "Earth".

        Returns:
            tuple: (x, y, z) in AU, mean ecliptic and equinox of J2000
            (x towards the vernal equinox); arrays when t is one.
        """
        sky  = _sky()
        time = cls._time_tt(t)
        x, y, z = (sky["eph"][_PLANETS[name]].at(time) - sky["sun"].at(time)).frame_xyz(
            ecliptic_J2000_frame).au
        return x, y, z

    @classmethod
    def planet_position(cls, t, name):
        """
        Apparent geocentric planet position (DE440), true equator and equinox
        of date: light time, aberration and light deflection included.

        Args:
            t (float | numpy.ndarray): Julian centuries of UT since J2000.0.

        Returns:
            tuple: (RA hours, Dec degrees, distance AU)
        """
        sky = _sky()
        ra, dec, dist = sky["earth"].at(cls._time_ut(t)).observe(
            cls._target(name)).apparent().radec(epoch="date")
        return ra.hours, dec.degrees, dist.au

    # ──────────────────────────────────────────────────────────────────
    # ANGULAR SEPARATION, CONJUNCTIONS, ECLIPSES
    # ──────────────────────────────────────────────────────────────────

    @staticmethod
    def angular_separation(ra1_h, dec1_deg, ra2_h, dec2_deg):
        """Angular separation between two objects (Meeus, chap. 17)."""
        ra1, ra2 = math.radians(ra1_h*15), math.radians(ra2_h*15)
        d1,  d2  = math.radians(dec1_deg), math.radians(dec2_deg)
        cos_d = math.sin(d1)*math.sin(d2) + math.cos(d1)*math.cos(d2)*math.cos(ra1-ra2)
        return math.degrees(math.acos(max(-1.0, min(1.0, cos_d))))


    @classmethod
    def _ecliptic_series(cls, jds, bodies):
        """Apparent geocentric ecliptic (of date) longitude°, latitude°, distance AU at UT Julian Days."""
        sky   = _sky()
        earth = sky["earth"].at(sky["ts"].ut1_jd(jds))
        series = {}
        for name in bodies:
            lat, lon, dist = earth.observe(cls._target(name)).apparent().ecliptic_latlon(epoch="date")
            series[name] = (lon.degrees, lat.degrees, dist.au)
        return series

    @staticmethod
    def _wrap180(angle):
        return (np.asarray(angle) + 180.0) % 360.0 - 180.0

    @staticmethod
    def _ecliptic_separation(lon1, lat1, lon2, lat2):
        """Angular distance (°) between two points given in ecliptic coordinates."""
        l1, b1, l2, b2 = (np.radians(v) for v in (lon1, lat1, lon2, lat2))
        c = np.sin(b1) * np.sin(b2) + np.cos(b1) * np.cos(b2) * np.cos(l1 - l2)
        return np.degrees(np.arccos(np.clip(c, -1.0, 1.0)))

    @classmethod
    def find_conjunctions(cls, dte_start, num_days=365, max_separation=5.0, minor_planets=True):
        """
        Conjunctions and oppositions of the planets, and greatest elongations
        of Mercury and Venus, to the minute (DE440, apparent positions).

        Definitions of the almanacs: a conjunction is the instant two bodies
        have the same geocentric ecliptic longitude (of date), an opposition
        the instant a planet is 180° from the Sun in longitude, a greatest
        elongation the maximum of the angle Sun–planet. A conjunction of
        Mercury or Venus with the Sun is inferior (the planet nearer than the
        Sun; a transit when it crosses the Sun's disc) or superior. Pairs of
        planets are kept when they pass within max_separation degrees. With
        minor_planets, the oppositions of MINOR_PLANETS are added.

        Found day by day, then refined hour by hour and interpolated.

        Returns:
            list[dict]: sorted by date, keys: date (instant, UT, tzinfo of
            dte_start), type ('conjunction' | 'opposition' |
            'greatest_elongation'), bodies ((planet, other) — "Sun" for the
            Sun), separation (°: distance between the bodies at the instant;
            elongation for an opposition or a greatest elongation), kind
            ('inferior' | 'superior' for Mercury and Venus with the Sun, else
            None), transit (bool), side ('north' | 'south': the first body
            relative to the second; 'east' | 'west' for an elongation),
            group ('planets' | 'minor'), mag (visual magnitude of the planet
            at an opposition or an elongation, else None), details (text).
        """
        jd0  = cls.julian_day(dte_start)
        days = jd0 + np.arange(num_days + 1, dtype=float)
        minors = tuple(MINOR_PLANETS) if minor_planets else ()
        bodies = ("sun",) + PLANETS + minors
        daily = cls._ecliptic_series(days, bodies)
        wrap = cls._wrap180

        # 1. day by day: brackets of the events
        candidates = []                                  # (type, a, b, first sample, last sample)
        def crossings(diff):
            near = np.abs(diff) < 90.0
            return np.flatnonzero((np.sign(diff[:-1]) != np.sign(diff[1:])) & near[:-1] & near[1:])
        for k, a in enumerate(PLANETS):
            d_sun = wrap(daily[a][0] - daily["sun"][0])
            candidates += [("conjunction", a, "sun", i, i + 1) for i in crossings(d_sun)]
            if a not in ("Mercury", "Venus"):
                candidates += [("opposition", a, "sun", i, i + 1) for i in crossings(wrap(d_sun - 180.0))]
            for b in PLANETS[k + 1:]:
                candidates += [("conjunction", a, b, i, i + 1)
                               for i in crossings(wrap(daily[a][0] - daily[b][0]))]
        for a in minors:
            candidates += [("opposition", a, "sun", i, i + 1)
                           for i in crossings(wrap(daily[a][0] - daily["sun"][0] - 180.0))]
        for a in ("Mercury", "Venus"):
            e = cls._ecliptic_separation(daily[a][0], daily[a][1], daily["sun"][0], daily["sun"][1])
            peaks = np.flatnonzero((e[1:-1] > e[:-2]) & (e[1:-1] >= e[2:])) + 1
            candidates += [("greatest_elongation", a, "sun", i - 1, i + 1) for i in peaks]
        if not candidates:
            return []

        # 2. hour by hour around each bracket, all in one computation
        windows = [days[i] + np.arange(0.0, (j - i) * 24.0 + 1.0) / 24.0 for _t, _a, _b, i, j in candidates]
        hourly = cls._ecliptic_series(np.concatenate(windows), bodies)
        results, offset = [], 0
        for (kind, a, b, _i, _j), window in zip(candidates, windows):
            n = len(window)
            la, ba, ra = (v[offset:offset + n] for v in hourly[a])
            lb, bb, rb = (v[offset:offset + n] for v in hourly[b])
            offset += n
            if kind == "greatest_elongation":
                e = cls._ecliptic_separation(la, ba, lb, bb)
                m = int(np.clip(np.argmax(e), 1, n - 2))
                y0, y1, y2 = e[m - 1], e[m], e[m + 1]
                step = 0.5 * (y0 - y2) / (y0 - 2.0 * y1 + y2) if (y0 - 2.0 * y1 + y2) else 0.0
                jd = window[m] + step / 24.0
                value = float(y1 - 0.25 * (y0 - y2) * step)
                side = "east" if wrap(la[m] - lb[m]) > 0 else "west"
                results.append(dict(jd=jd, type=kind, bodies=(a, "Sun"), separation=value,
                                    kind=None, transit=False, side=side))
                continue
            diff = wrap(la - lb - (180.0 if kind == "opposition" else 0.0))
            idx = np.flatnonzero(np.sign(diff[:-1]) != np.sign(diff[1:]))
            if not len(idx):
                continue
            h = int(idx[0])
            f = float(diff[h] / (diff[h] - diff[h + 1]))          # fraction of the hour
            at = lambda v: float(v[h] + f * (v[h + 1] - v[h]))
            jd = window[h] + f / 24.0
            separation = float(cls._ecliptic_separation(at(la), at(ba), at(lb), at(bb)))
            if kind == "opposition":
                results.append(dict(jd=jd, type=kind, bodies=(a, "Sun"), separation=separation,
                                    kind=None, transit=False, side=None))
            elif b == "sun":
                inferior = a in ("Mercury", "Venus") and at(ra) < at(rb)
                sun_radius = math.degrees(math.asin(696000.0 / (at(rb) * 149597870.7)))
                results.append(dict(jd=jd, type=kind, bodies=(a, "Sun"), separation=separation,
                                    kind=("inferior" if inferior else "superior") if a in ("Mercury", "Venus")
                                    else None, transit=inferior and separation < sun_radius,
                                    side="north" if at(ba) > at(bb) else "south"))
            elif separation <= max_separation:
                results.append(dict(jd=jd, type=kind, bodies=(a, b), separation=separation,
                                    kind=None, transit=False, side="north" if at(ba) > at(bb) else "south"))

        for r in results:
            a, b = r["bodies"]
            r["group"] = "minor" if a in minors else "planets"
            r["mag"] = (cls.observations((r["jd"] - 2451545.0) / 36525.0, [a])[a]["mag"]
                        if r["type"] != "conjunction" else None)
            r["date"] = cls._jd_to_datetime(r.pop("jd"), dte_start)
            if r["type"] == "opposition":
                r["details"] = f"{a} at opposition: {r['separation']:.1f}° from the Sun"
            elif r["type"] == "greatest_elongation":
                r["details"] = f"{a} at greatest elongation {r['side']}: {r['separation']:.1f}°"
            else:
                what = f"{r['kind']} conjunction" if r["kind"] else "conjunction"
                r["details"] = f"{a} – {b} {what}: {r['separation']:.2f}° {r['side']}"
        results.sort(key=lambda r: r["date"])
        return results

    # Bright stars the Moon passes, by their name in star_catalog ("Pleiades": Alcyone)
    MOON_STARS = {"Aldebaran": "Aldebaran", "Pleiades": "Alcyone", "Regulus": "Regulus",
                  "Spica": "Spica", "Antares": "Antares"}

    @classmethod
    def _star_target(cls, name):
        from star_catalog import CATALOG
        entry = next(c for c in CATALOG if c[6] == cls.MOON_STARS[name])
        return Star(ra_hours=entry[1], dec_degrees=entry[2], ra_mas_per_year=entry[4],
                    dec_mas_per_year=entry[5])

    @classmethod
    def _refine_extremum(cls, jds, values, i, sign):
        """Instant (JD) and value of the extremum near the sample i (parabola through 3 samples)."""
        i = int(np.clip(i, 1, len(values) - 2))
        y0, y1, y2 = values[i - 1], values[i], values[i + 1]
        den = y0 - 2.0 * y1 + y2
        step = 0.5 * (y0 - y2) / den if den else 0.0
        return jds[i] + step * (jds[1] - jds[0]), float(y1 - 0.25 * (y0 - y2) * step)

    @classmethod
    def find_moon_events(cls, dte_start, num_days=365, max_separation=5.0):
        """
        The Moon's conjunctions with the planets and the bright stars of its
        path (MOON_STARS), within max_separation degrees, and its perigees and
        apogees, to the minute (DE440, apparent geocentric positions).

        Conjunction: same ecliptic longitude of date, as find_conjunctions.
        A perigee near a full moon (within a day) is a "supermoon".

        Returns:
            list[dict]: sorted by date; keys date, type ('conjunction' |
            'perigee' | 'apogee'), bodies (("Moon", planet or star) or
            ("Moon",)), separation (°), side (the Moon 'north' | 'south' of the
            other body), distance_km (perigee, apogee), syzygy ('full' |
            'new' within a day of a perigee or an apogee, else None), group
            'moon', kind, transit, mag (None).
        """
        jd0  = cls.julian_day(dte_start)
        days = jd0 + np.arange(num_days + 2, dtype=float)
        sky  = _sky()
        others = PLANETS + tuple(cls.MOON_STARS)

        def series(jds):
            earth = sky["earth"].at(sky["ts"].ut1_jd(jds))
            out = {}
            for name in ("moon",) + others:
                target = cls._star_target(name) if name in cls.MOON_STARS else cls._target(name)
                lat, lon, dist = earth.observe(target).apparent().ecliptic_latlon(epoch="date")
                out[name] = (lon.degrees, lat.degrees, dist.km)
            return out

        daily = series(days)
        wrap = cls._wrap180
        brackets = []
        for name in others:
            diff = wrap(daily["moon"][0] - daily[name][0])
            near = np.abs(diff) < 90.0
            brackets += [(name, i) for i in np.flatnonzero(
                (np.sign(diff[:-1]) != np.sign(diff[1:])) & near[:-1] & near[1:])]
        results = []
        if brackets:
            windows = [days[i] + np.arange(25) / 24.0 for _n, i in brackets]
            hourly = series(np.concatenate(windows))
            for k, ((name, _i), window) in enumerate(zip(brackets, windows)):
                part = slice(25 * k, 25 * (k + 1))
                lm, bm = hourly["moon"][0][part], hourly["moon"][1][part]
                lo, bo = hourly[name][0][part], hourly[name][1][part]
                diff = wrap(lm - lo)
                idx = np.flatnonzero(np.sign(diff[:-1]) != np.sign(diff[1:]))
                if not len(idx):
                    continue
                h = int(idx[0])
                f = float(diff[h] / (diff[h] - diff[h + 1]))
                at = lambda v: float(v[h] + f * (v[h + 1] - v[h]))
                separation = float(cls._ecliptic_separation(at(lm), at(bm), at(lo), at(bo)))
                if separation <= max_separation:
                    results.append(dict(jd=window[h] + f / 24.0, type="conjunction", bodies=("Moon", name),
                                        separation=separation, side="north" if at(bm) > at(bo) else "south"))

        # perigees and apogees: extrema of the distance, refined hour by hour
        dist = daily["moon"][2]
        extrema = [("perigee", i) for i in np.flatnonzero((dist[1:-1] < dist[:-2]) & (dist[1:-1] <= dist[2:])) + 1]
        extrema += [("apogee", i) for i in np.flatnonzero((dist[1:-1] > dist[:-2]) & (dist[1:-1] >= dist[2:])) + 1]
        if extrema:
            hours = np.arange(-24, 25) / 24.0
            jds = np.concatenate([days[i] + hours for _k, i in extrema])
            d = sky["earth"].at(sky["ts"].ut1_jd(jds)).observe(sky["moon"]).distance().km
            for k, (kind, _i) in enumerate(extrema):
                part = d[49 * k: 49 * (k + 1)]
                window = jds[49 * k: 49 * (k + 1)]
                m = int(np.argmin(part) if kind == "perigee" else np.argmax(part))
                jd, value = cls._refine_extremum(window, part, m, 1)
                results.append(dict(jd=jd, type=kind, bodies=("Moon",), separation=None, side=None,
                                    distance_km=value))
            phases_t, phases = almanac.find_discrete(sky["ts"].ut1_jd(days[0] - 2.0), sky["ts"].ut1_jd(days[-1] + 2.0),
                                                     almanac.moon_phases(sky["eph"]))
            syzygies = [(float(tt.ut1), {0: "new", 2: "full"}[int(ph)]) for tt, ph in zip(phases_t, phases)
                        if int(ph) in (0, 2)]
            for r in results:
                if r["type"] in ("perigee", "apogee"):
                    r["syzygy"] = next((name for jd, name in syzygies if abs(jd - r["jd"]) <= 1.0), None)

        end = jd0 + num_days
        out = []
        for r in sorted(results, key=lambda r: r["jd"]):
            if not jd0 <= r["jd"] < end:
                continue
            r.setdefault("distance_km", None)
            r.setdefault("syzygy", None)
            r.update(group="moon", kind=None, transit=False, mag=None,
                     date=cls._jd_to_datetime(r.pop("jd"), dte_start))
            out.append(r)
        return out

    @classmethod
    def find_seasons(cls, dte_start, num_days=365):
        """
        Equinoxes and solstices (the Sun's apparent longitude a multiple of
        90°, Skyfield almanac) and the Earth's perihelion and aphelion (the
        extrema of its distance to the Sun, centre to centre), to the minute.

        Returns:
            list[dict]: date, type ('season' | 'perihelion' | 'aphelion'),
            kind ('march_equinox', 'june_solstice', 'september_equinox',
            'december_solstice' | None), distance_au, bodies ("Earth",),
            group 'seasons', separation, side, transit, mag (None).
        """
        sky = _sky()
        jd0 = cls.julian_day(dte_start)
        t0, t1 = sky["ts"].ut1_jd(jd0), sky["ts"].ut1_jd(jd0 + num_days)
        times, seasons = almanac.find_discrete(t0, t1, almanac.seasons(sky["eph"]))
        names = ("march_equinox", "june_solstice", "september_equinox", "december_solstice")
        results = [dict(jd=float(tt.ut1), type="season", kind=names[int(k)], distance_au=None)
                   for tt, k in zip(times, seasons)]
        days = jd0 - 1.0 + np.arange(num_days + 3, dtype=float)
        dist = sky["earth"].at(sky["ts"].ut1_jd(days)).observe(sky["sun"]).distance().au
        for kind, idx in (("perihelion", np.flatnonzero((dist[1:-1] < dist[:-2]) & (dist[1:-1] <= dist[2:])) + 1),
                          ("aphelion", np.flatnonzero((dist[1:-1] > dist[:-2]) & (dist[1:-1] >= dist[2:])) + 1)):
            for i in idx:
                hours = days[i] + np.arange(-24, 25) / 24.0
                d = sky["earth"].at(sky["ts"].ut1_jd(hours)).observe(sky["sun"]).distance().au
                m = int(np.argmin(d) if kind == "perihelion" else np.argmax(d))
                jd, value = cls._refine_extremum(hours, d, m, 1)
                if jd0 <= jd < jd0 + num_days:
                    results.append(dict(jd=jd, type=kind, kind=None, distance_au=value))
        out = []
        for r in sorted(results, key=lambda r: r["jd"]):
            r.update(bodies=("Earth",), group="seasons", separation=None, side=None, transit=False,
                     mag=None, date=cls._jd_to_datetime(r.pop("jd"), dte_start))
            out.append(r)
        return out

    _COMET_EVENT_MAG = 12.0          # comet events brighter than this (a small telescope)

    @classmethod
    def find_comet_events(cls, dte_start, num_days=365):
        """
        For each comet of COMETS within its table: its perihelion (closest to
        the Sun), its closest approach to the Earth and its greatest brightness
        (total magnitude M1, K1), to about the minute (daily samples, then a
        parabola through three); only those brighter than magnitude 12.

        Returns:
            list[dict]: date, type ('comet_perihelion' | 'comet_closest' |
            'comet_brightest'), bodies (name,), distance_au (to the Sun, to the
            Earth), mag (at that time), group 'comets', separation, side,
            transit, kind (None).
        """
        sky = _sky()
        jd0 = cls.julian_day(dte_start)
        out = []
        for name in COMETS:
            target, (m1, k1), (first, last) = _comet(name)
            lo, hi = max(jd0, first + 2.0), min(jd0 + num_days, last - 2.0)
            if hi - lo < 3.0:
                continue
            days = lo - 1.0 + np.arange(int(hi - lo) + 3, dtype=float)
            time = sky["ts"].ut1_jd(days)
            r = (target.at(time) - sky["sun"].at(time)).distance().au
            delta = sky["earth"].at(time).observe(target).distance().au
            mag = m1 + 5.0 * np.log10(delta) + k1 * np.log10(r)
            for kind, values in (("comet_perihelion", r), ("comet_closest", delta), ("comet_brightest", mag)):
                i = int(np.argmin(values))
                if i in (0, len(values) - 1):
                    continue                                    # at the edge: not a true minimum
                jd, value = cls._refine_extremum(days, values, i, 1)
                if not lo <= jd < hi:
                    continue
                k = int(round(jd - days[0]))
                if (value if kind == "comet_brightest" else mag[k]) > cls._COMET_EVENT_MAG:
                    continue                                    # too faint to be worth an event
                out.append(dict(date=cls._jd_to_datetime(jd, dte_start), type=kind, bodies=(name,),
                                distance_au=float(value) if kind != "comet_brightest" else None,
                                mag=float(value if kind == "comet_brightest" else mag[k]),
                                group="comets", separation=None, side=None, transit=False, kind=None))
        out.sort(key=lambda e: e["date"])
        return out

    # Meteor showers: the major ones of the Working List of Visual Meteor Showers
    # (International Meteor Organization, Meteor Shower Calendar 2026, Table 5).
    # code: (IAU number, first and last day of activity (month, day), solar
    # longitude of the maximum (J2000, °), radiant α, δ at the maximum (J2000, °),
    # V∞ (km/s), population index r, ZHR)
    METEOR_SHOWERS = {
        "QUA": (10, (12, 28), (1, 12), 283.15, 230.0, 49.0, 41, 2.1, 80),
        "LYR": (6, (4, 14), (4, 30), 32.32, 271.0, 34.0, 49, 2.1, 18),
        "ETA": (31, (4, 19), (5, 28), 45.5, 338.0, -1.0, 66, 2.4, 50),
        "SDA": (5, (7, 12), (8, 23), 128.0, 340.0, -16.0, 41, 2.5, 25),
        "CAP": (1, (7, 3), (8, 15), 128.0, 307.0, -10.0, 23, 2.5, 5),
        "PER": (7, (7, 17), (8, 24), 140.0, 48.0, 58.0, 59, 2.2, 100),
        "DRA": (9, (10, 6), (10, 10), 195.4, 262.0, 54.0, 20, 2.6, 5),
        "ORI": (8, (10, 2), (11, 7), 208.0, 95.0, 16.0, 66, 2.5, 20),
        "STA": (2, (9, 20), (11, 20), 223.0, 52.0, 15.0, 27, 2.3, 7),
        "NTA": (17, (10, 20), (12, 10), 230.0, 58.0, 22.0, 29, 2.3, 5),
        "LEO": (13, (11, 6), (11, 30), 235.27, 152.0, 22.0, 71, 2.5, 15),
        "GEM": (4, (12, 4), (12, 20), 262.2, 112.0, 33.0, 35, 2.6, 150),
        "URS": (15, (12, 17), (12, 26), 270.7, 217.0, 76.0, 33, 2.8, 10),
    }

    @classmethod
    def _solar_longitude(cls, jds):
        """Geocentric longitude of the Sun on the ecliptic and equinox J2000 (°), without
        aberration, as in the meteor shower calendars (20″ earlier: 8 minutes)."""
        sky = _sky()
        sun = sky["earth"].at(_fast_time(jds)).observe(sky["sun"])
        return sun.frame_latlon(ecliptic_J2000_frame)[1].degrees

    @classmethod
    def find_meteor_showers(cls, dte_start, num_days=365):
        """
        Maxima of the major meteor showers (METEOR_SHOWERS): the instant the
        Sun reaches the solar longitude of each maximum (J2000), to the
        minute, as in the calendar of the International Meteor Organization.

        Returns:
            list[dict]: date, type 'meteor_shower', kind (its IMO code),
            iau (number), zhr, velocity (km/s), r, radiant (α, δ in °),
            activity ((month, day), (month, day)), bodies ("Meteors",),
            group 'meteors', separation, side, transit, mag (None).
        """
        jd0 = cls.julian_day(dte_start)
        days = jd0 - 1.0 + np.arange(num_days + 3, dtype=float)
        lon = np.degrees(np.unwrap(np.radians(cls._solar_longitude(days))))
        out = []
        for code, (iau, first, last, peak, ra, dec, speed, r, zhr) in cls.METEOR_SHOWERS.items():
            for turn in range(int((lon[0] - peak) // 360.0), int((lon[-1] - peak) // 360.0) + 2):
                target = peak + 360.0 * turn
                k = np.flatnonzero((lon[:-1] <= target) & (lon[1:] > target))
                if not len(k):
                    continue
                i = int(k[0])
                jd = days[i] + (target - lon[i]) / (lon[i + 1] - lon[i])
                for _ in range(2):                      # Newton, at about 0.99°/day
                    rate = lon[i + 1] - lon[i]
                    jd += (((peak - cls._solar_longitude(np.array([jd]))[0]) + 180.0) % 360.0 - 180.0) / rate
                if jd0 <= jd < jd0 + num_days:
                    out.append(dict(date=cls._jd_to_datetime(jd, dte_start), type="meteor_shower",
                                    kind=code, iau=iau, zhr=zhr, velocity=speed, r=r, radiant=(ra, dec),
                                    activity=(first, last), bodies=("Meteors",), group="meteors",
                                    separation=None, side=None, transit=False, mag=None))
        out.sort(key=lambda e: e["date"])
        return out

    @classmethod
    def meteor_visibility(cls, event, lat, lon, elevation_m=0.0, tz=0):
        """
        The night of a meteor shower maximum seen from the observer: from the
        local noon before the maximum (12 h earlier) to the next noon, every
        10 minutes, the radiant 5° above the horizon while the Sun is 12°
        below it. Its best moment is the radiant's highest in the dark.

        Returns:
            dict: as event_visibility (period, best, alt, az, reason), and
            rate (meteors per hour under a dark sky at the best moment:
            ZHR × sin of the radiant's altitude, at least 1), moon_fraction (0–1) and
            moon_alt (°) at the best moment (at the maximum if invisible),
            moon ('none' | 'low' | 'medium' | 'strong'): the moonlight.
        """
        sky = _sky()
        here = sky["earth"] + wgs84.latlon(lat, lon, elevation_m=elevation_m)
        day = cls._local_day(event["date"].replace(tzinfo=None) - timedelta(hours=12), tz)[0]
        jds = cls.julian_day(day) + 0.5 + np.arange(145) / 144.0
        observer = here.at(_fast_time(jds))
        ra, dec = event["radiant"]
        radiant = Star(ra_hours=ra / 15.0, dec_degrees=dec)
        alt, az, _ = observer.observe(radiant).apparent().altaz()
        alt, az = alt.degrees, az.degrees
        sun_alt = observer.observe(sky["sun"]).apparent().altaz()[0].degrees
        moon_alt = observer.observe(sky["moon"]).apparent().altaz()[0].degrees
        dark = sun_alt < cls._DARKER_SUN
        up = alt >= cls._VISIBLE_ALTITUDE
        seen = dark & up
        vis = {"period": None, "best": None, "alt": None, "az": None, "reason": None, "rate": None}
        if seen.any():
            i = int(np.flatnonzero(seen)[np.argmax(alt[seen])])
            dark_idx = np.flatnonzero(dark)
            middle = 0.5 * (dark_idx[0] + dark_idx[-1])
            share = seen.sum() / dark.sum()
            vis.update(period="night" if share >= 0.85 else ("evening" if i <= middle else "morning"),
                       best=cls._jd_to_datetime(jds[i], event["date"]), alt=float(alt[i]),
                       az=float(az[i]), rate=max(1, round(event["zhr"] * math.sin(math.radians(alt[i])))))
            jd = jds[i]
        else:
            vis["reason"] = "no_night" if not dark.any() else ("daylight" if up.any() else "horizon")
            i = int(np.argmin(np.abs(jds - cls.julian_day(event["date"]))))
            jd = cls.julian_day(event["date"])
        fraction = float(almanac.fraction_illuminated(sky["eph"], "moon", _fast_time(jd)))
        vis.update(moon_fraction=fraction, moon_alt=float(moon_alt[i]),
                   moon=cls._moonlight(fraction, float(moon_alt[i])))
        return vis

    @staticmethod
    def _moonlight(fraction, moon_alt):
        """How much the Moon brightens the sky: 'none' when set or nearly new,
        else 'low', 'medium' or 'strong' with its illuminated fraction."""
        if moon_alt < 0.0 or fraction < 0.1:
            return "none"
        return "low" if fraction < 0.4 else ("medium" if fraction < 0.75 else "strong")

    # Visibility of the events: altitude of the body at least _VISIBLE_ALTITUDE
    # while the Sun is lower than _DARK_SUN (bright bodies) or _DARKER_SUN
    _VISIBLE_ALTITUDE, _DARK_SUN, _DARKER_SUN = 5.0, -6.0, -12.0

    @classmethod
    def event_visibility(cls, events, lat, lon, elevation_m=0.0, tz=0):
        """
        How each event can be seen from the observer, in its night: from the
        local noon before the event (12 h earlier) to the next noon, every 10
        minutes. The body (the planet, the Moon for its events) is visible when
        it stands 5° above the horizon while the Sun is 6° below it (12° for
        the faint minor planets). Adds to each event the key visibility:
        None (seasons), or a dict: period ('evening' | 'morning' | 'night' |
        None), best (UT datetime of its greatest altitude in the dark), alt,
        az (°), reason when invisible ('daylight': only up by day,
        'horizon': under the horizon at night, 'no_night': no dark night).
        Lunar conjunctions closer than 1.5° also get occultation (see
        moon_occultation); meteor showers, their night (meteor_visibility).
        """
        sky = _sky()
        here = sky["earth"] + wgs84.latlon(lat, lon, elevation_m=elevation_m)
        steps = np.arange(145) / 144.0                       # one day, every 10 minutes
        for e in events:
            if e.get("group") == "meteors":
                e["visibility"] = cls.meteor_visibility(e, lat, lon, elevation_m, tz)
        todo = [e for e in events if e.get("group") not in ("seasons", "meteors")]
        if not todo:
            return events
        starts = []
        for e in todo:
            day = cls._local_day(e["date"].replace(tzinfo=None) - timedelta(hours=12), tz)[0]
            starts.append(cls.julian_day(day) + 0.5)
        jds = np.concatenate([s + steps for s in starts])
        time = _fast_time(jds)
        observer = here.at(time)
        sun_alt = observer.observe(sky["sun"]).apparent().altaz()[0].degrees.reshape(len(todo), -1)
        bodies = {("moon" if e["bodies"][0] == "Moon" else e["bodies"][0]) for e in todo}
        alt_az = {}
        for body in bodies:
            rows = [k for k, e in enumerate(todo) if (("moon" if e["bodies"][0] == "Moon" else e["bodies"][0]) == body)]
            sub = _fast_time(np.concatenate([starts[k] + steps for k in rows]))
            alt, az, _ = here.at(sub).observe(cls._target(body)).apparent().altaz()
            for n, k in enumerate(rows):
                alt_az[k] = (alt.degrees[145 * n: 145 * (n + 1)], az.degrees[145 * n: 145 * (n + 1)])
        for k, e in enumerate(todo):
            alt, az = alt_az[k]
            dark_limit = cls._DARKER_SUN if e.get("group") in ("minor", "comets") else cls._DARK_SUN
            dark = sun_alt[k] < dark_limit
            up = alt >= cls._VISIBLE_ALTITUDE
            seen = dark & up
            vis = {"period": None, "best": None, "alt": None, "az": None, "reason": None}
            if seen.any():
                i = int(np.flatnonzero(seen)[np.argmax(alt[seen])])
                share = seen.sum() / dark.sum()
                dark_idx = np.flatnonzero(dark)
                middle = 0.5 * (dark_idx[0] + dark_idx[-1])
                vis.update(period="night" if share >= 0.85 else ("evening" if i <= middle else "morning"),
                           best=cls._jd_to_datetime(starts[k] + steps[i], e["date"]),
                           alt=float(alt[i]), az=float(az[i]))
            else:
                vis["reason"] = "no_night" if not dark.any() else ("daylight" if up.any() else "horizon")
            e["visibility"] = vis
            if e["bodies"][0] == "Moon" and e["type"] == "conjunction" and e["separation"] < 1.5:
                e["occultation"] = cls.moon_occultation(e, lat, lon, elevation_m)
        return events

    @classmethod
    def moon_calendar(cls, year, month, lat, lon, elevation_m=0.0, tz=0):
        """
        The Moon day by day over a month of the observer's calendar.

        Returns:
            list[dict]: one per local day: date (datetime.date), phase (Moon −
            Sun longitude at local noon, °: 0 new, 180 full), fraction (0–1, at
            local noon), rise, set (UT datetimes or None, find_events) and
            event (None, or the principal phase of that day: kind 'new_moon' |
            'first_quarter' | 'full_moon' | 'last_quarter', time in UT).
        """
        from datetime import date as _date, datetime as _datetime
        sky = _sky()
        first = _date(year, month, 1)
        days = []
        day = first
        while day.month == month:
            days.append(day)
            day += timedelta(days=1)
        starts = [cls._local_day(_datetime(d.year, d.month, d.day, 12), tz)[0] for d in days]
        starts = [s.replace(tzinfo=None) if s.tzinfo else s for s in starts]
        end = starts[-1] + timedelta(days=1)
        noons = np.array([cls.julian_day(s) + 0.5 for s in starts])
        noon_times = _fast_time(noons)
        phase = almanac.moon_phase(sky["eph"], noon_times).degrees
        fraction = almanac.fraction_illuminated(sky["eph"], "moon", noon_times)
        t0, t1 = sky["ts"].ut1_jd(cls.julian_day(starts[0])), sky["ts"].ut1_jd(cls.julian_day(end))
        times, kinds = almanac.find_discrete(t0, t1, almanac.moon_phases(sky["eph"]))
        names = ("new_moon", "first_quarter", "full_moon", "last_quarter")
        principal = {}
        for tt, k in zip(times, kinds):
            when = cls._jd_to_datetime(float(tt.ut1), starts[0])
            i = max(j for j, s in enumerate(starts) if s <= when)
            principal[i] = {"kind": names[int(k)], "time": when}
        out = []
        for i, d in enumerate(days):
            ev = cls.find_events(_datetime(d.year, d.month, d.day, 12), lat, lon, "moon", tz, elevation_m)
            rise, sets = ev.get("rise"), ev.get("set")
            out.append({"date": d, "phase": float(phase[i]), "fraction": float(fraction[i]),
                        "rise": rise.replace(tzinfo=None) if rise is not None and rise.tzinfo else rise,
                        "set": sets.replace(tzinfo=None) if sets is not None and sets.tzinfo else sets,
                        "event": principal.get(i)})
        return out

    @classmethod
    def deep_sky_horizontal(cls, t, lat, lon, elevation_m=0.0):
        """Altitudes and azimuths (°) of the Messier objects at t (Julian centuries of UT
        since J2000.0), brought to the date like the stars of the sky map."""
        catalog = messier_catalog()
        return cls.stars_horizontal(t, lat, lon, [o["ra"] for o in catalog], [o["dec"] for o in catalog],
                                    elevation_m)

    # « Ce soir » : the deep-sky objects worth a look, at least 30° high in the
    # dark (Sun 12° below the horizon or more), the brightest first
    _DEEP_SKY_ALTITUDE, _DEEP_SKY_COUNT = 30.0, 5

    @classmethod
    def _tonight_deep_sky(cls, jds, sun, here, lat, lon, start):
        """The brightest Messier objects of the night, each at its highest in the dark
        (10-minute samples; hour angles from the coordinates of the night's middle)."""
        dark = sun < (-18.0 if (sun < -18.0).any() else cls._DARKER_SUN)
        if not dark.any():
            return []
        catalog = messier_catalog()
        middle = _fast_time(float(jds[int(np.argmin(sun))]))
        stars = Star(ra_hours=np.array([o["ra"] for o in catalog]),
                     dec_degrees=np.array([o["dec"] for o in catalog]))
        ra, dec, _ = here.at(middle).observe(stars).apparent().radec(epoch="date")
        idx = np.flatnonzero(dark)[::2]
        times = _fast_time(jds[idx])
        lat = math.radians(lat)
        lst = (times.gast + lon / 15.0) * 15.0
        hour_angle = np.radians(lst[:, None] - ra._degrees[None, :])
        d = dec.radians[None, :]
        sin_alt = math.sin(lat) * np.sin(d) + math.cos(lat) * np.cos(d) * np.cos(hour_angle)
        alt = np.degrees(np.arcsin(np.clip(sin_alt, -1.0, 1.0)))
        az = np.degrees(np.arctan2(-np.cos(d) * np.sin(hour_angle),
                                   math.cos(lat) * np.sin(d) - math.sin(lat) * np.cos(d) * np.cos(hour_angle))) % 360.0
        best = np.argmax(alt, axis=0)
        found = []
        for k, obj in enumerate(catalog):
            i = int(best[k])
            if alt[i, k] >= cls._DEEP_SKY_ALTITUDE:
                found.append({"m": obj["m"], "alt": float(alt[i, k]), "az": float(az[i, k]),
                              "best": cls._jd_to_datetime(float(jds[idx[i]]), start),
                              "mag": obj["mag"]})
        found.sort(key=lambda o: o["mag"])
        return found[:cls._DEEP_SKY_COUNT]

    # « Ce soir » : planets seen when 5° high, the Sun 6° below the horizon
    # (12° for Uranus and Neptune, too faint in the twilight), and the comets
    # brighter than magnitude 10 (binoculars)
    _FAINT_PLANETS = ("Uranus", "Neptune")
    _BRIGHT_COMET = 10.0

    @classmethod
    def tonight(cls, dte, lat, lon, elevation_m=0.0, tz=0):
        """
        The night of dte seen from the observer: from the local noon before
        it to the next noon (dte in the morning: the night under way), every
        5 minutes, times to about the minute.

        Returns:
            dict: start, end (UT datetimes of the two noons); dark ('astro',
            'naut', 'civil' or None: the darkest twilight reached), dusk,
            dawn (UT datetimes when the Sun goes below and back above it);
            moon (fraction at the middle of the night, rise, set during the
            night — Sun 6° below — or None, up: share of that night with the
            Moon up); planets: the visible ones, with the comets brighter
            than magnitude 10 (dicts name, period 'evening' | 'morning' |
            'night', best, alt, az, mag, rise and set during the night or
            None), by best time; deep_sky: the five brightest Messier objects
            at least 30° high in the dark (dicts m, alt, az, best, mag).
        """
        sky = _sky()
        here = sky["earth"] + wgs84.latlon(lat, lon, elevation_m=elevation_m)
        local = dte.replace(tzinfo=None) - timedelta(hours=12)
        start = cls._local_day(local, tz)[0] + timedelta(hours=12)
        if start.tzinfo is not None:
            start = start.replace(tzinfo=None)
        jd0 = cls.julian_day(start)
        jds = jd0 + np.arange(289) / 288.0
        observer = here.at(_fast_time(jds))

        def when(jd):
            return None if jd is None else cls._jd_to_datetime(jd, start)

        def crossing(alt, level, rising, lo=0, hi=len(jds) - 1):
            """First crossing of *level* between the samples lo and hi."""
            above = alt >= level
            idx = np.flatnonzero(above[1:] & ~above[:-1] if rising else ~above[1:] & above[:-1])
            idx = idx[(idx >= lo) & (idx < hi)]
            if not len(idx):
                return None
            i = int(idx[0])
            f = (level - alt[i]) / (alt[i + 1] - alt[i])
            return float(jds[i] + f * (jds[i + 1] - jds[i]))

        sun = observer.observe(sky["sun"]).apparent().altaz()[0].degrees
        dark, dusk, dawn = None, None, None
        for kind, depth in (("astro", -18.0), ("naut", -12.0), ("civil", -6.0)):
            if (sun < depth).any():
                dark, dusk, dawn = kind, crossing(sun, depth, False), crossing(sun, depth, True)
                break
        middle = jds[int(np.argmin(sun))]

        # rises and sets that matter: during the night (Sun 6° below), or the whole
        # window when it never gets that dark
        night = sun < -6.0
        night_idx = np.flatnonzero(night)
        lo, hi = (int(night_idx[0]), int(night_idx[-1])) if len(night_idx) else (0, len(jds) - 1)
        moon_alt = observer.observe(sky["moon"]).apparent().altaz()[0].degrees
        moon = {"fraction": float(almanac.fraction_illuminated(sky["eph"], "moon", _fast_time(middle))),
                "rise": when(crossing(moon_alt, -0.83, True, lo, hi)),
                "set": when(crossing(moon_alt, -0.83, False, lo, hi)),
                "up": float((moon_alt[night] > 0).mean()) if night.any() else 0.0}

        planets = []
        tc_middle = (middle - 2451545.0) / 36525.0
        comets = cls.comets_at(tc_middle)
        seen = cls.observations(tc_middle, comets) if comets else {}      # () would mean all the bodies
        bright = [c for c in comets if seen[c]["mag"] <= cls._BRIGHT_COMET]
        for name in PLANETS + tuple(bright):
            alt, az, _ = observer.observe(cls._target(name)).apparent().altaz()
            alt, az = alt.degrees, az.degrees
            faint = name in cls._FAINT_PLANETS or name in COMETS
            dark_here = sun < (cls._DARKER_SUN if faint else cls._DARK_SUN)
            seen = dark_here & (alt >= cls._VISIBLE_ALTITUDE)
            if not seen.any():
                continue
            i = int(np.flatnonzero(seen)[np.argmax(alt[seen])])
            share = seen.sum() / dark_here.sum()
            dark_idx = np.flatnonzero(dark_here)
            period = "night" if share >= 0.85 else (
                "evening" if i <= 0.5 * (dark_idx[0] + dark_idx[-1]) else "morning")
            tc = (jds[i] - 2451545.0) / 36525.0
            planets.append({"name": name, "period": period, "best": when(jds[i]),
                            "alt": float(alt[i]), "az": float(az[i]),
                            "mag": cls.observations(tc, [name])[name]["mag"],
                            "rise": when(crossing(alt, -0.57, True, lo, hi)),
                            "set": when(crossing(alt, -0.57, False, lo, hi))})
        planets.sort(key=lambda p: p["best"])
        return {"start": start, "end": when(jds[-1]), "dark": dark, "dusk": when(dusk), "dawn": when(dawn),
                "moon": moon, "planets": planets,
                "deep_sky": cls._tonight_deep_sky(jds, sun, here, lat, lon, start)}

    @classmethod
    def upcoming_events(cls, dte, lat, lon, elevation_m=0.0, tz=0, num_days=30, count=3):
        """
        The next *count* events of the coming *num_days* seen from the
        observer: conjunctions, oppositions, elongations, the Moon's events,
        meteor showers and comets whose night is visible (event_visibility).
        """
        events = (cls.find_conjunctions(dte, num_days=num_days, minor_planets=False)
                  + cls.find_moon_events(dte, num_days=num_days)
                  + cls.find_meteor_showers(dte, num_days=num_days)
                  + cls.find_comet_events(dte, num_days=num_days))
        events = [e for e in events if e["type"] not in ("perigee", "apogee")]
        cls.event_visibility(events, lat, lon, elevation_m, tz)
        seen = [e for e in events if e["visibility"] and e["visibility"]["period"] is not None]
        return sorted(seen, key=lambda e: e["date"])[:count]

    @classmethod
    def moon_occultation(cls, event, lat, lon, elevation_m=0.0):
        """
        Occultation of the body of a lunar conjunction seen from the observer:
        the topocentric distance between the centres falls under the Moon's
        topocentric semi-diameter (minute by minute over ±4 h, interpolated).

        Returns:
            dict | None: None without occultation here, else start, end (UT
            datetimes of the disappearance and the reappearance, None beyond
            the ±4 h), moon_alt_start, moon_alt_end, sun_alt_start (°).
        """
        sky = _sky()
        jd = cls.julian_day(event["date"])
        jds = jd + np.arange(-240, 241) / 1440.0
        observer = (sky["earth"] + wgs84.latlon(lat, lon, elevation_m=elevation_m)).at(_fast_time(jds))
        name = event["bodies"][1]
        target = cls._star_target(name) if name in cls.MOON_STARS else cls._target(name)
        moon = observer.observe(sky["moon"]).apparent()
        other = observer.observe(target).apparent()
        radius = np.degrees(np.arcsin(_MOON_RADIUS_KM / moon.distance().km))
        inside = other.separation_from(moon).degrees - radius
        if inside.min() >= 0.0:
            return None

        def crossing(i):
            f = inside[i] / (inside[i] - inside[i + 1])
            return jds[i] + f / 1440.0
        down = np.flatnonzero((inside[:-1] >= 0) & (inside[1:] < 0))
        rise = np.flatnonzero((inside[:-1] < 0) & (inside[1:] >= 0))
        start = crossing(int(down[0])) if len(down) else None
        end = crossing(int(rise[-1])) if len(rise) else None

        def moon_alt(j):
            if j is None:
                return None
            here = (sky["earth"] + wgs84.latlon(lat, lon, elevation_m=elevation_m)).at(_fast_time(j))
            return float(here.observe(sky["moon"]).apparent().altaz()[0].degrees)
        sun_start = None
        if start is not None:
            here = (sky["earth"] + wgs84.latlon(lat, lon, elevation_m=elevation_m)).at(_fast_time(start))
            sun_start = float(here.observe(sky["sun"]).apparent().altaz()[0].degrees)
        to_dt = lambda j: None if j is None else cls._jd_to_datetime(j, event["date"])
        return {"start": to_dt(start), "end": to_dt(end), "moon_alt_start": moon_alt(start),
                "moon_alt_end": moon_alt(end), "sun_alt_start": sun_start}

    @classmethod
    def eclipse_local(cls, eclipse, lat, lon, elevation_m=0.0):
        """
        Local circumstances of an eclipse of find_eclipses() for the observer.

        Solar eclipse: the topocentric Sun and Moon (DE440, apparent) every
        20 s over ±3.5 h, the contacts interpolated where the distance of the
        centres equals the sum (first and last) or the difference (second and
        third: totality or annularity) of the semi-diameters. Magnitude: the
        fraction of the Sun's diameter covered at maximum; obscuration: of
        its area.

        Lunar eclipse: the contacts are the same for everyone (penumbral
        P1–P4, umbral U1–U4, totality U2–U3, around greatest as in
        find_eclipses); the observer sees those where the Moon is up.

        Returns:
            dict | None: None when a solar eclipse misses the place. Keys:
            contacts {name: UT datetime or None} ('c1', 'c2', 'max', 'c3',
            'c4' for the Sun; 'p1', 'u1', 'u2', 'max', 'u3', 'u4', 'p4' for the
            Moon), altitudes {name: ° of the eclipsed body}, visible (the body
            up during part of the eclipse); solar: magnitude, obscuration,
            central ('total' | 'annular' | None), duration_s.
        """
        sky = _sky()
        here = sky["earth"] + wgs84.latlon(lat, lon, elevation_m=elevation_m)
        greatest = eclipse["greatest"]
        jd_g = cls.julian_day(greatest)
        to_dt = lambda j: None if j is None else cls._jd_to_datetime(j, greatest)

        def altitude(body, jd):
            return float(here.at(sky["ts"].ut1_jd(jd)).observe(sky[body]).apparent().altaz()[0].degrees)

        if eclipse["type"] == "lunar":
            durations = eclipse.get("durations") or {}
            contacts = {"max": jd_g}
            for phase, (first, last) in (("penumbral", ("p1", "p4")), ("partial", ("u1", "u4")),
                                         ("total", ("u2", "u3"))):
                minutes = durations.get(phase)
                contacts[first] = jd_g - minutes / 2880.0 if minutes else None
                contacts[last] = jd_g + minutes / 2880.0 if minutes else None
            altitudes = {k: (altitude("moon", j) if j is not None else None) for k, j in contacts.items()}
            first, last = contacts["p1"], contacts["p4"]
            span = np.linspace(first, last, 61)
            moon = here.at(sky["ts"].ut1_jd(span)).observe(sky["moon"]).apparent().altaz()[0].degrees
            return {"contacts": {k: to_dt(j) for k, j in contacts.items()}, "altitudes": altitudes,
                    "visible": bool((moon > -0.5).any()), "all_visible": bool((moon > -0.5).all())}

        jds = jd_g + np.arange(-630, 631) * 20.0 / 86400.0
        observer = here.at(sky["ts"].ut1_jd(jds))
        sun = observer.observe(sky["sun"]).apparent()
        moon = observer.observe(sky["moon"]).apparent()
        # the Moon's radii of the shadow cones (_shadow_axis): its mean limb for
        # the partial phase, its valleys for totality, as NASA's predictions
        rs = np.degrees(np.arcsin(_SUN_RADIUS_KM / sun.distance().km))
        moon_km = moon.distance().km
        rm = np.degrees(np.arcsin(_MOON_RADIUS_PENUMBRA * _EARTH_RADIUS_KM / moon_km))
        rm_inner = np.degrees(np.arcsin(_MOON_RADIUS_UMBRA * _EARTH_RADIUS_KM / moon_km))
        sep = moon.separation_from(sun).degrees
        outer, inner = sep - (rs + rm), sep - np.abs(rs - rm_inner)
        if outer.min() >= 0.0:
            return None

        def crossings(values):
            idx = np.flatnonzero(np.sign(values[:-1]) != np.sign(values[1:]))
            return [jds[i] + values[i] / (values[i] - values[i + 1]) * (jds[1] - jds[0]) for i in idx]
        c_outer, c_inner = crossings(outer), crossings(inner)
        m = int(np.argmin(sep))
        jd_max, s_max = cls._refine_extremum(jds, sep, m, -1)
        r_s, r_m = float(rs[m]), float(rm[m])
        central = None
        if len(c_inner) >= 2:
            central = "total" if float(rm_inner[m]) > r_s else "annular"
        contacts = {"c1": c_outer[0] if c_outer and c_outer[0] < jd_max else None, "max": jd_max,
                    "c4": c_outer[-1] if c_outer and c_outer[-1] > jd_max else None,
                    "c2": c_inner[0] if central else None, "c3": c_inner[-1] if central else None}
        # overlap of the two discs, as a fraction of the Sun's
        d, a, b = max(s_max, 0.0), r_s, r_m
        if d >= a + b:
            obscured = 0.0
        elif d <= abs(a - b):
            obscured = min(1.0, (b / a) ** 2)
        else:
            alpha = math.acos((d * d + a * a - b * b) / (2 * d * a))
            beta = math.acos((d * d + b * b - a * a) / (2 * d * b))
            area = a * a * (alpha - math.sin(2 * alpha) / 2) + b * b * (beta - math.sin(2 * beta) / 2)
            obscured = area / (math.pi * a * a)
        sun_alt = sun.altaz()[0].degrees
        during = (outer < 0) & (sun_alt > -0.83)
        return {"contacts": {k: to_dt(j) for k, j in contacts.items()},
                "altitudes": {k: (altitude("sun", j) if j is not None else None) for k, j in contacts.items()},
                "magnitude": (r_s + r_m - s_max) / (2.0 * r_s), "obscuration": obscured,
                "central": central,
                "duration_s": (contacts["c3"] - contacts["c2"]) * 86400.0 if central else None,
                "visible": bool(during.any()), "all_visible": bool(during.sum() == (outer < 0).sum())}

    @classmethod
    def event_scene(cls, event, star_catalog=()):
        """
        What the map of a conjunction, an opposition or a greatest elongation
        shows: the apparent paths of its two bodies (RA, Dec of date) around
        the event, their positions at the instant, the stars of star_catalog
        in the field, and the ecliptic.

        Args:
            event (dict): from find_conjunctions().
            star_catalog: (designation, RA h, Dec °, mag, pm RA, pm Dec, name) tuples.

        Returns:
            dict: type, bodies [(name, ra h array, dec ° array, ra h, dec °)],
            days (offsets from the event), stars [(label, ra h, dec °, mag)],
            ecliptic (ra h array, dec ° array), sun_radius (°).
        """
        a, b = event["bodies"]
        slow = {"Jupiter", "Saturn", "Uranus", "Neptune"}
        span = {"opposition": 80.0, "greatest_elongation": 25.0}.get(
            event["type"], 40.0 if a in slow and b in slow else 12.0)
        step = 0.5 if span <= 12.0 else 1.0
        if a == "Moon":                                   # 13° a day: two days, hour by hour
            span, step = 1.0, 1.0 / 24.0
        days = np.arange(-span, span + step / 2, step)
        jd = cls.julian_day(event["date"])
        sky = _sky()
        time = sky["ts"].ut1_jd(jd + days)
        instant = sky["ts"].ut1_jd(jd)
        earth, earth_now = sky["earth"].at(time), sky["earth"].at(instant)
        bodies, radii = [], {}
        for name in (a, b):
            target = cls._target(name)
            ra, dec, _ = earth.observe(target).apparent().radec(epoch="date")
            ra0, dec0, dist0 = earth_now.observe(target).apparent().radec(epoch="date")
            bodies.append((name, ra.hours, dec.degrees, float(ra0.hours), float(dec0.degrees)))
            if name in ("Sun", "Moon"):
                radius = _SUN_RADIUS_KM if name == "Sun" else _MOON_RADIUS_KM
                radii[name] = math.degrees(math.asin(radius / dist0.km))
        sun_au = float(earth_now.observe(sky["sun"]).apparent().distance().au)
        stars = []
        if len(star_catalog):
            cat = list(star_catalog)
            positions = Star(ra_hours=np.array([c[1] for c in cat]), dec_degrees=np.array([c[2] for c in cat]),
                             ra_mas_per_year=np.array([c[4] for c in cat], dtype=float),
                             dec_mas_per_year=np.array([c[5] for c in cat], dtype=float))
            ra, dec, _ = earth_now.observe(positions).apparent().radec(epoch="date")
            stars = [(c[6] or c[0], float(r), float(d), c[3]) for c, r, d in zip(cat, ra.hours, dec.degrees)]
        t = (jd - 2451545.0) / 36525.0
        lon0 = float(cls._ecliptic_series(np.array([jd]), (a,))[a][0][0])
        ecl = [cls.ecliptic_to_equatorial(lon0 + d, 0.0, t) for d in np.arange(-150.0, 151.0, 1.0)]
        return {"type": event["type"], "bodies": bodies, "days": days, "stars": stars, "radii": radii,
                "fixed": [name for name in (a, b) if name in cls.MOON_STARS],
                "ecliptic": (np.array([e[0] for e in ecl]), np.array([e[1] for e in ecl])),
                "sun_radius": math.degrees(math.asin(696000.0 / (sun_au * 149597870.7)))}

    @staticmethod
    def _phases_between(jd0, jd1):
        """
        True lunar phases between two instants (TT Julian Days), DE440: the
        apparent Moon − Sun longitude difference reaching 0, 90, 180, 270°.

        Returns:
            tuple: (TT Julian Days, phase indices 0 new, 1 first quarter,
                    2 full, 3 last quarter)
        """
        sky = _sky()
        times, phases = almanac.find_discrete(sky["ts"].tt_jd(jd0), sky["ts"].tt_jd(jd1),
                                              almanac.moon_phases(sky["eph"]))
        return times.tt.tolist(), phases.tolist()

    @classmethod
    def _syzygies_from(cls, jd_start, phase, count):
        """
        TT Julian Days of `count` successive true new moons (phase=0) or full
        moons (phase=0.5), DE440, from the first one at or after jd_start (TT).
        """
        if count <= 0:
            return []
        index = round(phase * 4) % 4
        jds, phases = cls._phases_between(jd_start, jd_start + 29.9 * count + 1.0)
        return [jd for jd, i in zip(jds, phases) if i == index][:count]

    @classmethod
    def _jd_to_datetime(cls, jd, ref):
        """Datetime of jd, to the second, built on ref so that its tzinfo is kept."""
        ref = ref.replace(microsecond=0)
        return ref + timedelta(seconds=round((jd - cls.julian_day(ref)) * 86400.0))

    @classmethod
    def _delta_t_days(cls, jd):
        """ΔT at the Julian Day jd, in days."""
        return cls.delta_t(2000.0 + (jd - 2451545.0) / 365.25) / 86400.0


    @classmethod
    def _tt_to_datetime(cls, jde, ref):
        """UT datetime of the instant jde, given in dynamical time (TT)."""
        return cls._jd_to_datetime(_sky()["ts"].tt_jd(jde).ut1, ref)

    @classmethod
    def _find_syzygy(cls, dte_approx, target_phase=0):
        """
        True new moon (target_phase=0) or full moon (180) nearest to
        dte_approx, DE440 (90 and 270 give the quarters), as a datetime in
        dynamical time (TT) built on dte_approx.
        """
        jd    = cls.julian_day(dte_approx)
        index = round((target_phase % 360.0) / 90.0) % 4
        jds, phases = cls._phases_between(jd - 16.0, jd + 16.0)
        best = min((j for j, i in zip(jds, phases) if i == index), key=lambda j: abs(j - jd))
        return cls._jd_to_datetime(best, dte_approx)

    _find_syzygy_hp = _find_syzygy

    @classmethod
    def find_eclipses(cls, dte_start, num_months=12):
        """
        Searches for solar and lunar eclipses with the JPL DE440 ephemeris.

        Scans the num_months true new moons and num_months true full moons
        that follow dte_start, starting with the first ones at or after it
        (_syzygies_from), whatever the start date.

        A new moon closer than 1.58° to the ecliptic gives a solar eclipse if
        the Moon's penumbra reaches the Earth (_solar_eclipse), which also
        gives, at greatest eclipse (key greatest):
          • sub_type        : 'total' | 'annular' | 'hybrid' | 'partial'
          • magnitude       : Moon/Sun diameter ratio on the central line
                              (central eclipses), fraction of the Sun's
                              diameter covered otherwise
          • duration_min    : central phase on the central line, in minutes
                              (None for a partial eclipse)
        and diameter_ratio is the geocentric Moon/Sun apparent diameter ratio
        at new moon. A full moon gives a lunar eclipse if the Moon enters the
        Earth's penumbra (_lunar_eclipse), which gives at greatest eclipse:
          • sub_type        : 'total' | 'partial' | 'penumbral'
          • magnitude       : umbral magnitude (penumbral one for a
                              penumbral eclipse), and both as
                              umbral_magnitude, penumbral_magnitude
          • durations       : minutes of the penumbral, partial and total
                              phases (None when a phase does not occur);
                              duration_min is the total phase.

        The search runs in dynamical time (TT); date and greatest are given
        back in UT, like dte_start, with ΔT = TT − UT from delta_t().

        Args:
            dte_start (datetime): Start date (UT).
            num_months (int): Lunations to scan (default 12).

        Returns:
            list[dict]: Sorted by date (instant of new or full moon, UT);
                greatest is the instant of greatest eclipse (UT). Solar eclipse
                dicts contain: date, greatest, type='solar', certainty,
                moon_latitude, gamma, details, sub_type, diameter_ratio,
                magnitude, duration_min.
            Lunar eclipse dicts contain: date, greatest, type='lunar',
                certainty, moon_latitude, gamma, details, sub_type, magnitude,
                umbral_magnitude, penumbral_magnitude, durations, duration_min.

        Reference: Meeus, chap. 54 (eclipse rules); syzygies from DE440.
        """
        jd_start = cls.julian_day(dte_start)
        jd_start += cls._delta_t_days(jd_start)       # syzygies are in TT
        results  = []

        _EMOJI = {'total': '🌑', 'annular': '⭕', 'hybrid': '🔄', 'partial': '🌘'}

        # ── New moons: solar eclipses ──────────────────────────────────
        for jd_nm in cls._syzygies_from(jd_start, 0.0, num_months):
            t_nm = (jd_nm - 2451545.0) / 36525.0
            _, b_nm, dist_moon_nm, _ = cls.moon_position_tt(t_nm)
            if abs(b_nm) >= 1.58:
                continue
            eclipse = cls._solar_eclipse(jd_nm)
            if eclipse is None:                     # the penumbra misses the Earth
                continue

            _, r_sun_nm = cls.sun_position_tt(t_nm)
            ratio     = cls._moon_semi_diameter(dist_moon_nm) / cls._sun_semi_diameter(r_sun_nm)
            sub_type  = eclipse['sub_type']
            certainty = eclipse['certainty']
            mag       = eclipse['magnitude']
            duration  = eclipse['duration_min']

            parts = [f"Solar eclipse {sub_type} ({certainty})"]
            parts.append(f"Diameter ratio: {ratio:.4f}")
            parts.append(f"Magnitude: {mag:.3f}")
            if duration is not None:
                parts.append(f"Central phase: ~{duration} min")
            parts.append(f"Moon lat: {b_nm:+.2f}°")

            results.append({
                'date':           cls._tt_to_datetime(jd_nm, dte_start),
                'greatest':       cls._tt_to_datetime(eclipse['jd'], dte_start),
                'gamma':          eclipse['gamma'],
                'type':           'solar',
                'certainty':      certainty,
                'moon_latitude':  b_nm,
                'sub_type':       sub_type,
                'diameter_ratio': ratio,
                'magnitude':      mag,
                'duration_min':   duration,
                'details':        f"{_EMOJI.get(sub_type,'🌘')}  " + "  |  ".join(parts),
            })

        # ── Full moons: lunar eclipses ─────────────────────────────────
        for jd_fm in cls._syzygies_from(jd_start, 0.5, num_months):
            _, b_fm, _, _ = cls.moon_position_tt((jd_fm - 2451545.0) / 36525.0)
            if abs(b_fm) >= _LUNAR_LATITUDE_LIMIT:
                continue
            eclipse = cls._lunar_eclipse(jd_fm)
            if eclipse is None:                     # the Moon misses the penumbra
                continue

            sub_type, certainty = eclipse['sub_type'], eclipse['certainty']
            parts = [f"Lunar eclipse {sub_type} ({certainty})",
                     f"Umbral magnitude: {eclipse['umbral_magnitude']:.3f}",
                     f"Penumbral magnitude: {eclipse['penumbral_magnitude']:.3f}"]
            if eclipse['duration_min'] is not None:
                parts.append(f"Totality: ~{eclipse['duration_min']} min")
            parts.append(f"Moon lat: {b_fm:+.2f}°")

            results.append({
                'date':                cls._tt_to_datetime(jd_fm, dte_start),
                'greatest':            cls._tt_to_datetime(eclipse['jd'], dte_start),
                'type':                'lunar',
                'certainty':           certainty,
                'moon_latitude':       b_fm,
                'gamma':               eclipse['gamma'],
                'sub_type':            sub_type,
                'magnitude':           eclipse['magnitude'],
                'umbral_magnitude':    eclipse['umbral_magnitude'],
                'penumbral_magnitude': eclipse['penumbral_magnitude'],
                'durations':           eclipse['durations'],
                'duration_min':        eclipse['duration_min'],
                'details':             "🌕  " + "  |  ".join(parts),
            })

        results.sort(key=lambda r: r['date'])
        return results


@functools.lru_cache(maxsize=32)
def _new_moons(bucket):
    """
    TT Julian Days of the true new moons from 40 days before to 20 days after
    the start of a 10-day bucket (bucket × 10): always one before any instant
    of the bucket, for AstroEngine.moon_phase().
    """
    start = bucket * 10.0
    jds, phases = AstroEngine._phases_between(start - 40.0, start + 20.0)
    return tuple(jd for jd, i in zip(jds, phases) if i == 0)


@functools.lru_cache(maxsize=1)
def _constellations():
    """IAU constellation boundaries and Latin names (data shipped with Skyfield)."""
    return load_constellation_map(), dict(load_constellation_names())


def constellation_names():
    """{IAU abbreviation: Latin name} of the 88 constellations."""
    return _constellations()[1]


def _constellation(position):
    """IAU abbreviation and Latin name of the constellation of an apparent position."""
    find, names = _constellations()
    abbreviation = str(find(position))
    return abbreviation, names.get(abbreviation, abbreviation)
