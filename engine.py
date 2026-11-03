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

The ephemeris (32 MB) is looked for in data/ next to this module, then in
~/.celeste (or $CELESTE_DATA), where it is downloaded from the JPL/NAIF
server the first time (load_ephemeris()).

This module is completely independent from the graphical interface (MVC model).
"""

import functools
import math
import os
from datetime import timedelta, timezone

import numpy as np
from skyfield import almanac
from skyfield.api import Loader, Star, load_constellation_map, load_constellation_names, wgs84
from skyfield.magnitudelib import planetary_magnitude
from skyfield.framelib import ecliptic_frame, ecliptic_J2000_frame, true_equator_and_equinox_of_date

# ==========================================================
# CONSTANTS
# ==========================================================

# JPL DE440, short version: 1849-12-26 → 2150-01-22
_EPHEMERIS_URL  = "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/planets/de440s.bsp"
_EPHEMERIS_FILE = "de440s.bsp"
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


_SKY = {}


def ephemeris_path():
    """Path of the DE440 file: the first data directory holding it, else where it will be downloaded."""
    for directory in _DATA_DIRS:
        path = os.path.join(directory, _EPHEMERIS_FILE)
        if os.path.isfile(path):
            return path
    return os.path.join(_DATA_DIRS[-1], _EPHEMERIS_FILE)


def load_ephemeris():
    """
    Skyfield timescale and DE440 bodies, loaded once (downloaded the first
    time). Raises EphemerisUnavailable when the file can be neither found
    nor downloaded.
    """
    if not _SKY:
        directory = os.path.dirname(ephemeris_path())
        try:
            os.makedirs(directory, exist_ok=True)
            loader = Loader(directory, verbose=False)
            eph = loader(_EPHEMERIS_URL)
        except Exception as exc:                            # network, disk, corrupt file
            raise EphemerisUnavailable(
                f"{_EPHEMERIS_FILE}: not found in {directory} and not downloadable "
                f"from {_EPHEMERIS_URL} ({exc})") from exc
        _SKY.update(ts=loader.timescale(), eph=eph,
                    earth=eph["earth"], sun=eph["sun"], moon=eph["moon"])
    return _SKY


_sky = load_ephemeris

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
            body (str): "sun" or "moon".
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
        target   = sky[body]
        horizon  = None                                 # Skyfield's standard horizon
        if elevation_m > 0:
            middle = cls._time_ut(cls.julian_century_j2000(start + (end - start) / 2))
            km = sky["earth"].at(middle).observe(target).distance().km
            horizon = -(_HORIZON_REFRACTION + math.degrees(math.asin(_BODY_RADIUS_KM[body] / km))
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
        target = sky[body] if body in ("sun", "moon") else sky["eph"][_PLANETS[body]]
        air    = {"temperature_C": 10.0, "pressure_mbar": 1010.0} if refraction else {}
        alt, az, _ = here.observe(target).apparent().altaz(**air)
        return alt.degrees, az.degrees

    @classmethod
    def stars_horizontal(cls, t, lat, lon, ra_hours, dec_degrees, elevation_m=0.0):
        """
        Altitudes and azimuths (degrees, geometric) of stars given by their
        J2000 coordinates (ICRS): precession, nutation and aberration to the
        date in one vectorised computation. Without them, a J2000 position is
        off by 50″ a year (0.37° in 2026).

        Args:
            t (float): Julian centuries of UT since J2000.0.
            ra_hours, dec_degrees (sequence): J2000 right ascensions (h) and
                declinations (°).

        Returns:
            tuple[numpy.ndarray, numpy.ndarray]: (altitudes, azimuths)
        """
        sky   = _sky()
        stars = Star(ra_hours=np.asarray(ra_hours, dtype=float),
                     dec_degrees=np.asarray(dec_degrees, dtype=float))
        here  = (sky["earth"] + wgs84.latlon(lat, lon, elevation_m=elevation_m)).at(cls._time_ut(t))
        alt, az, _ = here.observe(stars).apparent().altaz()
        return alt.degrees, az.degrees

    # The bodies of the coordinates table, in the order of the Solar System
    BODIES  = ("sun", "moon", "Mercury", "Venus", "earth", "Mars", "Jupiter", "Saturn",
               "Uranus", "Neptune", "Pluto")
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

    @staticmethod
    def _target(body):
        """DE440 target of a body name: "sun", "moon", "earth" or a planet."""
        sky = _sky()
        return sky[body] if body in ("sun", "moon") else sky["eph"][_PLANETS[body.capitalize()]]

    @classmethod
    def observations(cls, t, bodies=None):
        """
        How the bodies look from the Earth's centre (DE440, apparent): visual
        magnitude, angle with the Sun (elongation) and constellation (IAU
        boundaries), computed together.

        Magnitudes: Mallama & Hilton (2018) from Mercury to Neptune (Skyfield);
        Allen's Astrophysical Quantities for the Sun, the Moon and Pluto.

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
                if body in ("moon", "Pluto"):
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
            sky["eph"][_PLANETS[name]]).apparent().radec(epoch="date")
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
    def find_conjunctions(cls, dte_start, num_days=365):
        """
        Searches for planetary conjunctions and oppositions, from one apparent
        DE440 position a day (computed at once for the whole period).

        Returns:
            list[dict]: sorted by date, keys: date, type, bodies, separation, details
        """
        planets = ["Venus", "Mars", "Jupiter", "Saturn"]
        pairs   = [(a, b) for i, a in enumerate(planets) for b in planets[i+1:]]
        days    = [dte_start + timedelta(days=day) for day in range(num_days)]
        if not days:
            return []
        sky   = _sky()
        earth = sky["earth"].at(cls._time_ut(np.array([cls.julian_century_j2000(d) for d in days])))

        def track(target):
            ra, dec, _ = earth.observe(target).apparent().radec(epoch="date")
            return list(zip(ra.hours.tolist(), dec.degrees.tolist()))

        sun    = track(sky["sun"])
        tracks = {p: track(sky["eph"][_PLANETS[p]]) for p in planets}
        results = []
        prev_seps, prev_elongs = {}, {}

        for day, dte in enumerate(days):
            s_ra, s_dec = sun[day]
            positions = {p: tracks[p][day] for p in planets}

            for a, b in pairs:
                sep = cls.angular_separation(*positions[a], *positions[b])
                key = (a, b)
                if key in prev_seps and len(prev_seps[key]) >= 2:
                    p2, p1 = prev_seps[key]
                    if p1 < p2 and p1 < sep and p1 < 5.0:
                        results.append({'date': dte-timedelta(days=1), 'type': 'conjunction',
                                        'bodies': (a,b), 'separation': p1,
                                        'details': f"{a} – {b} : {p1:.1f}°"})
                prev_seps[key] = (prev_seps.get(key, (sep,))[-1], sep)

            for pname in planets:
                elong = cls.angular_separation(*positions[pname], s_ra, s_dec)
                key   = pname
                if key in prev_elongs and len(prev_elongs[key]) >= 2:
                    p2, p1 = prev_elongs[key]
                    if p1 < p2 and p1 < elong and p1 < 5.0:
                        results.append({'date': dte-timedelta(days=1), 'type': 'conjunction',
                                        'bodies': (pname,'Sun'), 'separation': p1,
                                        'details': f"{pname} in solar conjunction: {p1:.1f}°"})
                    if (pname in ("Mars","Jupiter","Saturn")
                            and p1 > p2 and p1 > elong and p1 > 175.0):
                        results.append({'date': dte-timedelta(days=1), 'type': 'opposition',
                                        'bodies': (pname,'Sun'), 'separation': p1,
                                        'details': f"{pname} in opposition: {p1:.1f}°"})
                prev_elongs[key] = (prev_elongs.get(key, (elong,))[-1], elong)

        results.sort(key=lambda r: r['date'])
        return results

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


def _constellation(position):
    """IAU abbreviation and Latin name of the constellation of an apparent position."""
    find, names = _constellations()
    abbreviation = str(find(position))
    return abbreviation, names.get(abbreviation, abbreviation)
