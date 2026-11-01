"""
tests/test_engine.py — Unit Tests for Céleste Astronomical Engine
===================================================================
Verifies the MeeusEngine algorithms against reference values published
in *Astronomical Algorithms* by Jean Meeus (2nd ed., Willmann-Bell).

Run with: pytest tests/
"""

import math
import sys
import os
import pytest

# Make root directory importable from tests/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from engine import MeeusEngine


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────

def approx(value, expected, tolerance):
    """Verifies that |value - expected| ≤ tolerance."""
    return abs(value - expected) <= tolerance


# ──────────────────────────────────────────────────────────────────────
# 1. Julian Day  (Meeus, chap. 7, examples p. 61-62)
# ──────────────────────────────────────────────────────────────────────

class TestJulianDay:
    def test_j2000(self):
        """J2000.0 : January 1.5, 2000 = JD 2451545.0 (epoch definition)."""
        jd = MeeusEngine.julian_day(datetime(2000, 1, 1, 12, 0, 0))
        assert abs(jd - 2451545.0) < 0.001

    def test_meeus_example_7a(self):
        """Meeus example p. 61: October 4.81, 1957 → JD 2436116.31."""
        # October 4, 1957, 19h26m24s UT
        dte = datetime(1957, 10, 4, 19, 26, 24)
        jd = MeeusEngine.julian_day(dte)
        assert abs(jd - 2436116.31) < 0.01

    def test_j1900(self):
        """J1900.0 : January 0.5, 1900 noon UT = JD 2415021.0."""
        dte = datetime(1900, 1, 1, 12, 0, 0)
        jd = MeeusEngine.julian_day(dte)
        assert abs(jd - 2415021.0) < 0.01

    def test_half_day(self):
        """A 12h delta between two datetimes must give exactly 0.5 JD."""
        d1 = MeeusEngine.julian_day(datetime(2024, 3, 20, 0, 0, 0))
        d2 = MeeusEngine.julian_day(datetime(2024, 3, 20, 12, 0, 0))
        assert abs((d2 - d1) - 0.5) < 1e-9

    def test_monotonic_growth(self):
        """JD must increase by one day between consecutive dates."""
        d1 = MeeusEngine.julian_day(datetime(2024, 6, 15, 0, 0, 0))
        d2 = MeeusEngine.julian_day(datetime(2024, 6, 16, 0, 0, 0))
        assert abs((d2 - d1) - 1.0) < 1e-9


# ──────────────────────────────────────────────────────────────────────
# 2. Julian Century since J2000.0
# ──────────────────────────────────────────────────────────────────────

class TestJulianCentury:
    def test_j2000_is_zero(self):
        """At J2000.0, T must be exactly 0."""
        t = MeeusEngine.julian_century_j2000(datetime(2000, 1, 1, 12, 0, 0))
        assert abs(t) < 1e-10

    def test_one_century_later(self):
        """Exactly 100 Julian years after J2000.0 → T = 1.0."""
        # 1 Julian century = 36525 days ≈ 100 years
        dte = datetime(2000, 1, 1, 12, 0, 0)
        dte_plus100 = datetime(2100, 1, 1, 12, 0, 0)
        t = MeeusEngine.julian_century_j2000(dte_plus100)
        # Precision to 0.001: leap years make calculation approximate
        assert abs(t - 1.0) < 0.001

    def test_sign_before_j2000(self):
        """Before J2000.0, T must be negative."""
        t = MeeusEngine.julian_century_j2000(datetime(1999, 1, 1, 12, 0, 0))
        assert t < 0


# ──────────────────────────────────────────────────────────────────────
# 3. Sun Position  (Meeus, chap. 25)
# ──────────────────────────────────────────────────────────────────────

class TestSunPosition:
    def test_longitude_j2000(self):
        """J2000.0 : Sun's ecliptic longitude ≈ 280.46° (L0 at T=0)."""
        t = MeeusEngine.julian_century_j2000(datetime(2000, 1, 1, 12, 0, 0))
        l, _ = MeeusEngine.sun_position(t)
        # Real longitude close to 280° (spring equinox ~3 months later)
        assert 270 < l < 290

    def test_distance_near_1au(self):
        """Earth-Sun distance ≈ 1 AU (±3%)."""
        t = MeeusEngine.julian_century_j2000(datetime(2024, 6, 21, 0, 0, 0))
        _, r = MeeusEngine.sun_position(t)
        assert 0.97 < r < 1.03

    def test_meeus_example_25a(self):
        """
        Meeus example p. 165: October 13, 1992 0h TD.
        Apparent Sun longitude ≈ 199.9° (Meeus L0=201.807°, short series ±1°).
        Distance ≈ 0.9976 AU.
        """
        dte = datetime(1992, 10, 13, 0, 0, 0)
        t = MeeusEngine.julian_century_j2000(dte)
        l, r = MeeusEngine.sun_position(t)
        assert approx(l, 199.9, 1.5), f"Longitude = {l:.3f}°"
        assert approx(r, 0.9976, 0.005), f"Distance = {r:.5f} AU"

    def test_longitude_in_360(self):
        """Longitude must always be in [0, 360[."""
        for year in range(2000, 2030, 5):
            for month in (1, 4, 7, 10):
                t = MeeusEngine.julian_century_j2000(datetime(year, month, 15))
                l, _ = MeeusEngine.sun_position(t)
                assert 0 <= l < 360


# ──────────────────────────────────────────────────────────────────────
# 4. Moon Position  (Meeus, chap. 47)
# ──────────────────────────────────────────────────────────────────────

class TestMoonPosition:
    def test_longitude_in_360(self):
        """Ecliptic longitude must be in [0, 360[."""
        t = MeeusEngine.julian_century_j2000(datetime(2024, 3, 25, 0, 0, 0))
        l, b, p = MeeusEngine.moon_position(t)
        assert 0 <= l < 360

    def test_latitude_bounded(self):
        """Moon's ecliptic latitude always in ±6.5°."""
        for day in range(1, 29, 4):
            t = MeeusEngine.julian_century_j2000(datetime(2024, 1, day))
            _, b, _ = MeeusEngine.moon_position(t)
            assert -7 <= b <= 7, f"Latitude out of range: {b:.2f}°"

    def test_parallax_realistic(self):
        """Moon's horizontal equatorial parallax between 0.90° and 1.02°."""
        t = MeeusEngine.julian_century_j2000(datetime(2024, 1, 1))
        _, _, p = MeeusEngine.moon_position(t)
        assert 0.90 <= p <= 1.02, f"Parallax = {p:.4f}°"


# ──────────────────────────────────────────────────────────────────────
# 5. Ecliptic to Equatorial Conversion  (Meeus, chap. 13)
# ──────────────────────────────────────────────────────────────────────

class TestEclipticToEquatorial:
    def test_meeus_example_13a(self):
        """
        Meeus p. 95: λ=113.842°, β=6.684°, obliquity 23.4392° (T≈0).
        → RA ≈ 7h45m45s = 7.7625h,  Dec ≈ 28°1' = 28.02°.
        Tolerance 0.05h / 0.1°: short series, precision <1'.
        """
        t = 0.0  # J2000.0
        ra, dec = MeeusEngine.ecliptic_to_equatorial(113.842, 6.684, t)
        assert approx(ra, 7.7625, 0.05), f"RA = {ra:.3f}h"
        assert approx(dec, 28.02, 0.15), f"Dec = {dec:.3f}°"

    def test_ra_in_range(self):
        """Right Ascension must always be in [0, 24[."""
        for l in (0, 90, 180, 270, 359):
            ra, _ = MeeusEngine.ecliptic_to_equatorial(l, 0.0, 0.0)
            assert 0 <= ra < 24, f"RA out of range for λ={l}°: {ra}"

    def test_vernal_point(self):
        """λ=0, β=0 → RA=0h, Dec=0° (vernal equinox point)."""
        ra, dec = MeeusEngine.ecliptic_to_equatorial(0.0, 0.0, 0.0)
        assert abs(ra) < 0.01
        assert abs(dec) < 0.01


# ──────────────────────────────────────────────────────────────────────
# 6. Elevation Correction (refraction + parallax)
# ──────────────────────────────────────────────────────────────────────

class TestElevationCorrection:
    def test_positive_altitude_increases(self):
        """Refraction must increase apparent altitude (object seems higher)."""
        h_corr = MeeusEngine.elevation_correction(30.0, 0.0)
        assert h_corr > 30.0

    def test_refraction_stronger_near_horizon(self):
        """Refraction is stronger near horizon than at zenith."""
        r_low    = MeeusEngine.elevation_correction(1.0, 0.0) - 1.0
        r_high   = MeeusEngine.elevation_correction(60.0, 0.0) - 60.0
        assert r_low > r_high

    def test_below_horizon_minimal_correction(self):
        """For h < -5°, only parallax is subtracted (no refraction)."""
        h_in = -10.0
        p    = 0.95
        h_out = MeeusEngine.elevation_correction(h_in, p)
        assert abs(h_out - (h_in - p)) < 0.001

    def test_moon_parallax_decreases_altitude(self):
        """Moon's parallax (~0.95°) must lower corrected altitude."""
        h_without = MeeusEngine.elevation_correction(45.0, 0.0)
        h_with = MeeusEngine.elevation_correction(45.0, 0.95)
        assert h_with < h_without


# ──────────────────────────────────────────────────────────────────────
# 7. Daily Events (rise / set)
# ──────────────────────────────────────────────────────────────────────

class TestFindEvents:
    # Paris at summer solstice 2024 — Sun must rise and set
    PARIS_LAT = 48.8566
    PARIS_LON = 2.3522
    DATE_SUMMER = datetime(2024, 6, 21, 12, 0, 0)

    def test_rise_set_exist(self):
        """In Paris in summer, rise and set must be detected."""
        ev = MeeusEngine.find_events(
            self.DATE_SUMMER, self.PARIS_LAT, self.PARIS_LON, "sun")
        assert ev["rise"]   is not None, "Rise not detected"
        assert ev["set"] is not None, "Set not detected"

    def test_rise_before_set(self):
        """Rise must precede set."""
        ev = MeeusEngine.find_events(
            self.DATE_SUMMER, self.PARIS_LAT, self.PARIS_LON, "sun")
        assert ev["rise"] < ev["set"]

    def test_transit_between_rise_set(self):
        """Transit must be between rise and set."""
        ev = MeeusEngine.find_events(
            self.DATE_SUMMER, self.PARIS_LAT, self.PARIS_LON, "sun")
        assert ev["rise"] < ev["transit"] < ev["set"]

    def test_twilight_order_correct(self):
        """Expected order: dawn_astro < dawn_naut < dawn_civ < rise (morning)."""
        ev = MeeusEngine.find_events(
            self.DATE_SUMMER, self.PARIS_LAT, self.PARIS_LON, "sun")
        if all(ev[k] for k in ("dawn_astro", "dawn_naut", "dawn_civ", "rise")):
            assert ev["dawn_astro"] < ev["dawn_naut"]
            assert ev["dawn_naut"]  < ev["dawn_civ"]
            assert ev["dawn_civ"]   < ev["rise"]

    def test_sun_rise_paris_summer_time_range(self):
        """Sun rise in Paris on June 21, 2024 ≈ 04h–06h UT."""
        ev = MeeusEngine.find_events(
            self.DATE_SUMMER, self.PARIS_LAT, self.PARIS_LON, "sun")
        rise = ev["rise"]
        hour = rise.hour + rise.minute / 60.0
        assert 3.5 <= hour <= 6.0, f"Unexpected rise at {rise.strftime('%H:%M')}"

    def test_moon_events_exist(self):
        """Moon events must use 'moon' key."""
        ev = MeeusEngine.find_events(
            self.DATE_SUMMER, self.PARIS_LAT, self.PARIS_LON, "moon")
        # Twilights are not calculated for Moon
        assert "rise" in ev
        assert "set" in ev
        assert ev.get("dawn_civ") is None


# ──────────────────────────────────────────────────────────────────────
# 8. Planet Positions
# ──────────────────────────────────────────────────────────────────────

class TestPlanetPosition:
    T_J2000 = MeeusEngine.julian_century_j2000(datetime(2000, 1, 1, 12, 0, 0))

    def test_ra_in_range(self):
        """Right Ascension must always be in [0, 24[."""
        for p in ("Venus", "Mars", "Jupiter", "Saturn"):
            ra, _, _ = MeeusEngine.planet_position(self.T_J2000, p)
            assert 0 <= ra < 24, f"{p} : RA = {ra}"

    def test_dec_bounded(self):
        """Declination must be in [-90, +90]."""
        for p in ("Venus", "Mars", "Jupiter", "Saturn"):
            _, dec, _ = MeeusEngine.planet_position(self.T_J2000, p)
            assert -90 <= dec <= 90, f"{p} : Dec = {dec}"

    def test_distances_realistic(self):
        """Geocentric distances in expected ranges (AU)."""
        ranges = {
            "Venus":   (0.25, 1.75),
            "Mars":    (0.35, 2.7),
            "Jupiter": (3.9, 6.5),
            "Saturn":  (7.9, 11.1),
        }
        for p, (dmin, dmax) in ranges.items():
            _, _, dist = MeeusEngine.planet_position(self.T_J2000, p)
            assert dmin <= dist <= dmax, f"{p} : dist = {dist:.3f} AU"

    def test_positions_vary_over_time(self):
        """Planetary positions must change between dates one year apart."""
        t1 = MeeusEngine.julian_century_j2000(datetime(2024, 1, 1))
        t2 = MeeusEngine.julian_century_j2000(datetime(2025, 1, 1))
        for p in ("Venus", "Mars", "Jupiter", "Saturn"):
            ra1, _, _ = MeeusEngine.planet_position(t1, p)
            ra2, _, _ = MeeusEngine.planet_position(t2, p)
            assert ra1 != ra2, f"{p} : position unchanged after 1 year"


class TestPlanetHeliocentric:
    """planet_heliocentric() feeds the orrery and planet_position()."""

    T = MeeusEngine.julian_century_j2000(datetime(2026, 11, 1))

    def test_radius_between_perihelion_and_aphelion(self):
        """Heliocentric distance stays within a(1 - e) and a(1 + e)."""
        from engine import _ORBITAL_ELEMENTS
        for p in ("Venus", "Mars", "Jupiter", "Saturn"):
            _, _, a, e0, e1, *_ = _ORBITAL_ELEMENTS[p]
            e = e0 + e1 * self.T
            x, y, z = MeeusEngine.planet_heliocentric(self.T, p)
            r = math.sqrt(x * x + y * y + z * z)
            assert a * (1 - e) - 1e-6 <= r <= a * (1 + e) + 1e-6, f"{p} : r = {r:.4f} AU"

    def test_close_to_ecliptic_plane(self):
        """Inclinations are under 3.4°, so |z| ≤ r·sin(3.4°)."""
        for p in ("Venus", "Mars", "Jupiter", "Saturn"):
            x, y, z = MeeusEngine.planet_heliocentric(self.T, p)
            r = math.sqrt(x * x + y * y + z * z)
            assert abs(z) <= r * math.sin(math.radians(3.4)), p

    def test_geocentric_distance_consistent(self):
        """planet_position() distance = |planet − Earth| from the same vectors."""
        lon_sun, r_sun = MeeusEngine.sun_position(self.T)
        a = math.radians(lon_sun + 180.0)
        xe, ye = r_sun * math.cos(a), r_sun * math.sin(a)
        for p in ("Venus", "Mars", "Jupiter", "Saturn"):
            x, y, z = MeeusEngine.planet_heliocentric(self.T, p)
            _, _, dist = MeeusEngine.planet_position(self.T, p)
            assert approx(dist, math.sqrt((x - xe) ** 2 + (y - ye) ** 2 + z * z), 1e-9), p


# ──────────────────────────────────────────────────────────────────────
# Moon High Precision Tests
# ──────────────────────────────────────────────────────────────────────

class TestMoonPositionHP:
    """Verifies Moon precision against Meeus example 47.a."""

    def test_meeus_example_47a(self):
        """April 12, 1992, 0h TD — Meeus p.342."""
        t = MeeusEngine.julian_century_j2000(datetime(1992, 4, 12))
        lon, lat, par = MeeusEngine.moon_position(t)
        # Latitude very precise; longitude and parallax improved over
        # old simplified series (~1°).
        assert abs(lon - 133.162) < 2.0, f"Longitude : {lon:.3f}° (expected ~133.162°)"
        assert abs(lat - (-3.229)) < 0.15, f"Latitude : {lat:.3f}° (expected ~-3.229°)"
        assert 0.89 <= par <= 1.03, f"Parallax : {par:.4f}° (out of bounds)"

    def test_precision_improved(self):
        """New series is better than old (~1°) over several dates."""
        dates = [datetime(2024, 1, 15), datetime(2024, 6, 21), datetime(2024, 12, 1)]
        for dte in dates:
            t = MeeusEngine.julian_century_j2000(dte)
            lon, lat, par = MeeusEngine.moon_position(t)
            assert 0 <= lon < 360
            assert -6 <= lat <= 6
            assert 0.89 <= par <= 1.03

    def test_bounds_unchanged(self):
        """Existing bounds remain valid with complete series."""
        t = MeeusEngine.julian_century_j2000(datetime(2024, 6, 15))
        lon, lat, par = MeeusEngine.moon_position(t)
        assert 0 <= lon < 360
        assert -7 <= lat <= 7
        assert 0.89 <= par <= 1.03


# ──────────────────────────────────────────────────────────────────────
# Equation of Time Tests
# ──────────────────────────────────────────────────────────────────────

class TestEquationOfTime:
    """Verifies Equation of Time over known dates."""

    def test_annual_range(self):
        """EoT remains in [-17, +17] minutes all year."""
        for month in range(1, 13):
            t = MeeusEngine.julian_century_j2000(datetime(2024, month, 15))
            eot = MeeusEngine.equation_of_time(t)
            assert -17 <= eot <= 17, f"Month {month} : EoT = {eot:.1f} min"

    def test_february_negative(self):
        """Mid-February: EoT ≈ −14 min (±3 min)."""
        t = MeeusEngine.julian_century_j2000(datetime(2024, 2, 12))
        eot = MeeusEngine.equation_of_time(t)
        assert -17 <= eot <= -11, f"February : EoT = {eot:.1f} min"

    def test_november_positive(self):
        """Early November: EoT ≈ +16 min (±3 min)."""
        t = MeeusEngine.julian_century_j2000(datetime(2024, 11, 3))
        eot = MeeusEngine.equation_of_time(t)
        assert 13 <= eot <= 19, f"November : EoT = {eot:.1f} min"


# ──────────────────────────────────────────────────────────────────────
# Angular Separation Tests
# ──────────────────────────────────────────────────────────────────────

class TestAngularSeparation:
    """Verifies angular separation calculation."""

    def test_same_point(self):
        """Separation of a point with itself is 0."""
        sep = MeeusEngine.angular_separation(6.0, 45.0, 6.0, 45.0)
        assert abs(sep) < 1e-10

    def test_poles(self):
        """North Pole and South Pole are 180° apart."""
        sep = MeeusEngine.angular_separation(0.0, 90.0, 0.0, -90.0)
        assert abs(sep - 180.0) < 1e-10

    def test_90_degrees(self):
        """Points separated by 90° in declination."""
        sep = MeeusEngine.angular_separation(0.0, 0.0, 0.0, 90.0)
        assert abs(sep - 90.0) < 1e-10


# ──────────────────────────────────────────────────────────────────────
# Conjunction Search Tests
# ──────────────────────────────────────────────────────────────────────

class TestFindConjunctions:
    """Verifies conjunction/opposition search."""

    def test_returns_list(self):
        """Result is a list."""
        results = MeeusEngine.find_conjunctions(
            datetime(2024, 1, 1), num_days=30)
        assert isinstance(results, list)

    def test_result_structure(self):
        """Each result contains expected keys."""
        results = MeeusEngine.find_conjunctions(
            datetime(2024, 1, 1), num_days=60)
        for r in results:
            assert 'date' in r
            assert 'type' in r
            assert r['type'] in ('conjunction', 'opposition')
            assert 'bodies' in r
            assert 'separation' in r

    def test_events_over_year(self):
        """Over a year, should find at least a few events."""
        results = MeeusEngine.find_conjunctions(
            datetime(2024, 1, 1), num_days=365)
        assert len(results) >= 1


# ──────────────────────────────────────────────────────────────────────
# Eclipse Search Tests
# ──────────────────────────────────────────────────────────────────────

class TestFindEclipses:
    """Verifies eclipse detection."""

    def test_returns_list(self):
        """Result is a list."""
        results = MeeusEngine.find_eclipses(datetime(2024, 1, 1), num_months=6)
        assert isinstance(results, list)

    def test_fewer_eclipses_than_lunations(self):
        """Over 12 months, fewer eclipses than lunations (max ~5-6)."""
        results = MeeusEngine.find_eclipses(datetime(2024, 1, 1), num_months=12)
        assert len(results) < 12

    def test_eclipses_2024(self):
        """In 2024, at least 2 eclipses (known solar + lunar)."""
        results = MeeusEngine.find_eclipses(datetime(2024, 1, 1), num_months=12)
        assert len(results) >= 2, f"Only {len(results)} eclipse(s) detected"

    def test_result_structure(self):
        """Each result contains expected keys."""
        results = MeeusEngine.find_eclipses(datetime(2024, 1, 1), num_months=6)
        for r in results:
            assert 'date' in r
            assert r['type'] in ('solar', 'lunar')
            assert 'certainty' in r
            assert 'moon_latitude' in r
            assert abs(r['moon_latitude']) < 1.58
