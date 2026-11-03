"""
tests/test_engine.py — Unit Tests for Céleste Astronomical Engine
===================================================================
Verifies the AstroEngine algorithms against reference values published
in *Astronomical Algorithms* by Jean Meeus (2nd ed., Willmann-Bell).

Run with: pytest tests/
"""

import math
import sys
import os
import pytest

# Make root directory importable from tests/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
from engine import AstroEngine


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
        jd = AstroEngine.julian_day(datetime(2000, 1, 1, 12, 0, 0))
        assert abs(jd - 2451545.0) < 0.001

    def test_reference_1957_10_04(self):
        """Meeus example p. 61: October 4.81, 1957 → JD 2436116.31."""
        # October 4, 1957, 19h26m24s UT
        dte = datetime(1957, 10, 4, 19, 26, 24)
        jd = AstroEngine.julian_day(dte)
        assert abs(jd - 2436116.31) < 0.01

    def test_j1900(self):
        """J1900.0 : January 0.5, 1900 noon UT = JD 2415021.0."""
        dte = datetime(1900, 1, 1, 12, 0, 0)
        jd = AstroEngine.julian_day(dte)
        assert abs(jd - 2415021.0) < 0.01

    def test_half_day(self):
        """A 12h delta between two datetimes must give exactly 0.5 JD."""
        d1 = AstroEngine.julian_day(datetime(2024, 3, 20, 0, 0, 0))
        d2 = AstroEngine.julian_day(datetime(2024, 3, 20, 12, 0, 0))
        assert abs((d2 - d1) - 0.5) < 1e-9

    def test_monotonic_growth(self):
        """JD must increase by one day between consecutive dates."""
        d1 = AstroEngine.julian_day(datetime(2024, 6, 15, 0, 0, 0))
        d2 = AstroEngine.julian_day(datetime(2024, 6, 16, 0, 0, 0))
        assert abs((d2 - d1) - 1.0) < 1e-9


# ──────────────────────────────────────────────────────────────────────
# 2. Julian Century since J2000.0
# ──────────────────────────────────────────────────────────────────────

class TestJulianCentury:
    def test_j2000_is_zero(self):
        """At J2000.0, T must be exactly 0."""
        t = AstroEngine.julian_century_j2000(datetime(2000, 1, 1, 12, 0, 0))
        assert abs(t) < 1e-10

    def test_one_century_later(self):
        """Exactly 100 Julian years after J2000.0 → T = 1.0."""
        # 1 Julian century = 36525 days ≈ 100 years
        dte = datetime(2000, 1, 1, 12, 0, 0)
        dte_plus100 = datetime(2100, 1, 1, 12, 0, 0)
        t = AstroEngine.julian_century_j2000(dte_plus100)
        # Precision to 0.001: leap years make calculation approximate
        assert abs(t - 1.0) < 0.001

    def test_sign_before_j2000(self):
        """Before J2000.0, T must be negative."""
        t = AstroEngine.julian_century_j2000(datetime(1999, 1, 1, 12, 0, 0))
        assert t < 0


# ──────────────────────────────────────────────────────────────────────
# 3. Sun Position  (Meeus, chap. 25)
# ──────────────────────────────────────────────────────────────────────

class TestSunPosition:
    def test_longitude_j2000(self):
        """J2000.0 : Sun's ecliptic longitude ≈ 280.46° (L0 at T=0)."""
        t = AstroEngine.julian_century_j2000(datetime(2000, 1, 1, 12, 0, 0))
        l, _ = AstroEngine.sun_position(t)
        # Real longitude close to 280° (spring equinox ~3 months later)
        assert 270 < l < 290

    def test_distance_near_1au(self):
        """Earth-Sun distance ≈ 1 AU (±3%)."""
        t = AstroEngine.julian_century_j2000(datetime(2024, 6, 21, 0, 0, 0))
        _, r = AstroEngine.sun_position(t)
        assert 0.97 < r < 1.03

    def test_reference_1992_10_13(self):
        """
        Meeus example p. 165: October 13, 1992 0h TD.
        Apparent Sun longitude ≈ 199.9° (Meeus L0=201.807°, short series ±1°).
        Distance ≈ 0.9976 AU.
        """
        dte = datetime(1992, 10, 13, 0, 0, 0)
        t = AstroEngine.julian_century_j2000(dte)
        l, r = AstroEngine.sun_position(t)
        assert approx(l, 199.9, 1.5), f"Longitude = {l:.3f}°"
        assert approx(r, 0.9976, 0.005), f"Distance = {r:.5f} AU"

    def test_longitude_in_360(self):
        """Longitude must always be in [0, 360[."""
        for year in range(2000, 2030, 5):
            for month in (1, 4, 7, 10):
                t = AstroEngine.julian_century_j2000(datetime(year, month, 15))
                l, _ = AstroEngine.sun_position(t)
                assert 0 <= l < 360


# ──────────────────────────────────────────────────────────────────────
# 4. Moon Position  (Meeus, chap. 47)
# ──────────────────────────────────────────────────────────────────────

class TestMoonPosition:
    def test_longitude_in_360(self):
        """Ecliptic longitude must be in [0, 360[."""
        t = AstroEngine.julian_century_j2000(datetime(2024, 3, 25, 0, 0, 0))
        l, b, p = AstroEngine.moon_position(t)
        assert 0 <= l < 360

    def test_latitude_bounded(self):
        """Moon's ecliptic latitude always in ±6.5°."""
        for day in range(1, 29, 4):
            t = AstroEngine.julian_century_j2000(datetime(2024, 1, day))
            _, b, _ = AstroEngine.moon_position(t)
            assert -7 <= b <= 7, f"Latitude out of range: {b:.2f}°"

    def test_parallax_realistic(self):
        """Moon's horizontal equatorial parallax between 0.90° and 1.02°."""
        t = AstroEngine.julian_century_j2000(datetime(2024, 1, 1))
        _, _, p = AstroEngine.moon_position(t)
        assert 0.90 <= p <= 1.02, f"Parallax = {p:.4f}°"


# ──────────────────────────────────────────────────────────────────────
# 5. Ecliptic to Equatorial Conversion  (Meeus, chap. 13)
# ──────────────────────────────────────────────────────────────────────

class TestEclipticToEquatorial:
    def test_reference_pollux(self):
        """
        Meeus p. 95: λ=113.842°, β=6.684°, obliquity 23.4392° (T≈0).
        → RA ≈ 7h45m45s = 7.7625h,  Dec ≈ 28°1' = 28.02°.
        Tolerance 0.05h / 0.1°: short series, precision <1'.
        """
        t = 0.0  # J2000.0
        ra, dec = AstroEngine.ecliptic_to_equatorial(113.842, 6.684, t)
        assert approx(ra, 7.7625, 0.05), f"RA = {ra:.3f}h"
        assert approx(dec, 28.02, 0.15), f"Dec = {dec:.3f}°"

    def test_ra_in_range(self):
        """Right Ascension must always be in [0, 24[."""
        for l in (0, 90, 180, 270, 359):
            ra, _ = AstroEngine.ecliptic_to_equatorial(l, 0.0, 0.0)
            assert 0 <= ra < 24, f"RA out of range for λ={l}°: {ra}"

    def test_vernal_point(self):
        """λ=0, β=0 → RA=0h, Dec=0° (vernal equinox point)."""
        ra, dec = AstroEngine.ecliptic_to_equatorial(0.0, 0.0, 0.0)
        assert abs(ra) < 0.01
        assert abs(dec) < 0.01


# ──────────────────────────────────────────────────────────────────────
# 6. Elevation Correction (refraction + parallax)
# ──────────────────────────────────────────────────────────────────────

class TestElevationCorrection:
    def test_positive_altitude_increases(self):
        """Refraction must increase apparent altitude (object seems higher)."""
        h_corr = AstroEngine.elevation_correction(30.0, 0.0)
        assert h_corr > 30.0

    def test_refraction_stronger_near_horizon(self):
        """Refraction is stronger near horizon than at zenith."""
        r_low    = AstroEngine.elevation_correction(1.0, 0.0) - 1.0
        r_high   = AstroEngine.elevation_correction(60.0, 0.0) - 60.0
        assert r_low > r_high

    def test_below_horizon_minimal_correction(self):
        """For h < -5°, only the parallax in altitude (π cos h) is subtracted."""
        h_in = -10.0
        p    = 0.95
        h_out = AstroEngine.elevation_correction(h_in, p)
        expected = h_in - math.degrees(math.asin(math.sin(math.radians(p)) * math.cos(math.radians(h_in))))
        assert abs(h_out - expected) < 0.001

    def test_no_parallax_at_zenith(self):
        """The parallax in altitude vanishes at the zenith (π cos 90° = 0)."""
        assert abs(AstroEngine.elevation_correction(90.0, 0.95) - 90.0) < 0.01

    def test_moon_parallax_decreases_altitude(self):
        """Moon's parallax (~0.95°) must lower corrected altitude."""
        h_without = AstroEngine.elevation_correction(45.0, 0.0)
        h_with = AstroEngine.elevation_correction(45.0, 0.95)
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
        ev = AstroEngine.find_events(
            self.DATE_SUMMER, self.PARIS_LAT, self.PARIS_LON, "sun")
        assert ev["rise"]   is not None, "Rise not detected"
        assert ev["set"] is not None, "Set not detected"

    def test_rise_before_set(self):
        """Rise must precede set."""
        ev = AstroEngine.find_events(
            self.DATE_SUMMER, self.PARIS_LAT, self.PARIS_LON, "sun")
        assert ev["rise"] < ev["set"]

    def test_transit_between_rise_set(self):
        """Transit must be between rise and set."""
        ev = AstroEngine.find_events(
            self.DATE_SUMMER, self.PARIS_LAT, self.PARIS_LON, "sun")
        assert ev["rise"] < ev["transit"] < ev["set"]

    def test_twilight_order_correct(self):
        """Expected order: dawn_astro < dawn_naut < dawn_civ < rise (morning)."""
        ev = AstroEngine.find_events(
            self.DATE_SUMMER, self.PARIS_LAT, self.PARIS_LON, "sun")
        if all(ev[k] for k in ("dawn_astro", "dawn_naut", "dawn_civ", "rise")):
            assert ev["dawn_astro"] < ev["dawn_naut"]
            assert ev["dawn_naut"]  < ev["dawn_civ"]
            assert ev["dawn_civ"]   < ev["rise"]

    def test_sun_rise_paris_summer_time_range(self):
        """Sun rise in Paris on June 21, 2024 ≈ 04h–06h UT."""
        ev = AstroEngine.find_events(
            self.DATE_SUMMER, self.PARIS_LAT, self.PARIS_LON, "sun")
        rise = ev["rise"]
        hour = rise.hour + rise.minute / 60.0
        assert 3.5 <= hour <= 6.0, f"Unexpected rise at {rise.strftime('%H:%M')}"

    def test_moon_events_exist(self):
        """Moon events must use 'moon' key."""
        ev = AstroEngine.find_events(
            self.DATE_SUMMER, self.PARIS_LAT, self.PARIS_LON, "moon")
        # Twilights are not calculated for Moon
        assert "rise" in ev
        assert "set" in ev
        assert ev.get("dawn_civ") is None


# ──────────────────────────────────────────────────────────────────────
# 8. Planet Positions
# ──────────────────────────────────────────────────────────────────────

class TestPlanetPosition:
    T_J2000 = AstroEngine.julian_century_j2000(datetime(2000, 1, 1, 12, 0, 0))

    def test_ra_in_range(self):
        """Right Ascension must always be in [0, 24[."""
        for p in ("Venus", "Mars", "Jupiter", "Saturn"):
            ra, _, _ = AstroEngine.planet_position(self.T_J2000, p)
            assert 0 <= ra < 24, f"{p} : RA = {ra}"

    def test_dec_bounded(self):
        """Declination must be in [-90, +90]."""
        for p in ("Venus", "Mars", "Jupiter", "Saturn"):
            _, dec, _ = AstroEngine.planet_position(self.T_J2000, p)
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
            _, _, dist = AstroEngine.planet_position(self.T_J2000, p)
            assert dmin <= dist <= dmax, f"{p} : dist = {dist:.3f} AU"

    def test_positions_vary_over_time(self):
        """Planetary positions must change between dates one year apart."""
        t1 = AstroEngine.julian_century_j2000(datetime(2024, 1, 1))
        t2 = AstroEngine.julian_century_j2000(datetime(2025, 1, 1))
        for p in ("Venus", "Mars", "Jupiter", "Saturn"):
            ra1, _, _ = AstroEngine.planet_position(t1, p)
            ra2, _, _ = AstroEngine.planet_position(t2, p)
            assert ra1 != ra2, f"{p} : position unchanged after 1 year"


class TestPlanetHeliocentric:
    """planet_heliocentric() feeds the orrery and planet_position()."""

    T = AstroEngine.julian_century_j2000(datetime(2026, 11, 1))

    def test_radius_between_perihelion_and_aphelion(self):
        """Heliocentric distance stays between perihelion and aphelion (AU)."""
        limits = {"Venus": (0.718, 0.729), "Mars": (1.381, 1.667), "Jupiter": (4.95, 5.46),
                  "Saturn": (9.02, 10.12), "Earth": (0.983, 1.017)}
        for p, (q, big_q) in limits.items():
            x, y, z = AstroEngine.planet_heliocentric(self.T, p)
            r = math.sqrt(x * x + y * y + z * z)
            assert q <= r <= big_q, f"{p} : r = {r:.4f} AU"

    def test_close_to_ecliptic_plane(self):
        """Inclinations are under 3.4°, so |z| ≤ r·sin(3.4°)."""
        for p in ("Venus", "Mars", "Jupiter", "Saturn"):
            x, y, z = AstroEngine.planet_heliocentric(self.T, p)
            r = math.sqrt(x * x + y * y + z * z)
            assert abs(z) <= r * math.sin(math.radians(3.4)), p

    # JPL Horizons, 2026-11-01 0h TT: apparent RA (°), Dec (°), distance (AU)
    HORIZONS = {
        "Venus":   (202.52107, -14.66185, 0.27977162),
        "Mars":    (141.56935,  16.76526, 1.43251662),
        "Jupiter": (146.86244,  14.06424, 5.49965645),
        "Saturn":  (  9.58801,   1.21125, 8.54788487),
    }

    def test_matches_jpl_horizons(self):
        """planet_position() (DE440, UT) within 1.2" and 1500 km of JPL Horizons."""
        ut = datetime(2026, 11, 1) - timedelta(seconds=AstroEngine.delta_t(2026.83))
        t = AstroEngine.julian_century_j2000(ut)
        for p, (ra, dec, dist) in self.HORIZONS.items():
            r, d, di = AstroEngine.planet_position(t, p)
            sep = AstroEngine.angular_separation(r, d, ra / 15.0, dec) * 3600.0
            assert sep < 1.2, f"{p} : {sep:.2f}\""
            assert approx(di, dist, 1e-5), f"{p} : dist = {di:.7f} AU"


# ──────────────────────────────────────────────────────────────────────
# Moon High Precision Tests
# ──────────────────────────────────────────────────────────────────────

class TestMoonPositionHP:
    """moon_position() takes UT: the date of Meeus example 47.a, minus ΔT."""

    def test_example_47a_in_ut(self):
        """
        April 12, 1992, 0h TT, given in UT: JPL Horizons gives the apparent
        λ = 133.16671°, β = −3.22920°, distance 368437.7 km (Meeus's
        truncated series: 133.16727° with nutation, 368409.7 km).
        """
        ut = datetime(1992, 4, 12) - timedelta(seconds=AstroEngine.delta_t(1992.28))
        lon, lat, par = AstroEngine.moon_position(AstroEngine.julian_century_j2000(ut))
        assert abs(lon - 133.16671) < 3e-4, f"Longitude : {lon:.6f}°"
        assert abs(lat - (-3.22920)) < 3e-4, f"Latitude : {lat:.6f}°"
        assert abs(par - 0.991920) < 1e-5, f"Parallax : {par:.6f}°"

    def test_precision_improved(self):
        """New series is better than old (~1°) over several dates."""
        dates = [datetime(2024, 1, 15), datetime(2024, 6, 21), datetime(2024, 12, 1)]
        for dte in dates:
            t = AstroEngine.julian_century_j2000(dte)
            lon, lat, par = AstroEngine.moon_position(t)
            assert 0 <= lon < 360
            assert -6 <= lat <= 6
            assert 0.89 <= par <= 1.03

    def test_bounds_unchanged(self):
        """Existing bounds remain valid with complete series."""
        t = AstroEngine.julian_century_j2000(datetime(2024, 6, 15))
        lon, lat, par = AstroEngine.moon_position(t)
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
            t = AstroEngine.julian_century_j2000(datetime(2024, month, 15))
            eot = AstroEngine.equation_of_time(t)
            assert -17 <= eot <= 17, f"Month {month} : EoT = {eot:.1f} min"

    def test_february_negative(self):
        """Mid-February: EoT ≈ −14 min (±3 min)."""
        t = AstroEngine.julian_century_j2000(datetime(2024, 2, 12))
        eot = AstroEngine.equation_of_time(t)
        assert -17 <= eot <= -11, f"February : EoT = {eot:.1f} min"

    def test_november_positive(self):
        """Early November: EoT ≈ +16 min (±3 min)."""
        t = AstroEngine.julian_century_j2000(datetime(2024, 11, 3))
        eot = AstroEngine.equation_of_time(t)
        assert 13 <= eot <= 19, f"November : EoT = {eot:.1f} min"


# ──────────────────────────────────────────────────────────────────────
# Angular Separation Tests
# ──────────────────────────────────────────────────────────────────────

class TestAngularSeparation:
    """Verifies angular separation calculation."""

    def test_same_point(self):
        """Separation of a point with itself is 0."""
        sep = AstroEngine.angular_separation(6.0, 45.0, 6.0, 45.0)
        assert abs(sep) < 1e-10

    def test_poles(self):
        """North Pole and South Pole are 180° apart."""
        sep = AstroEngine.angular_separation(0.0, 90.0, 0.0, -90.0)
        assert abs(sep - 180.0) < 1e-10

    def test_90_degrees(self):
        """Points separated by 90° in declination."""
        sep = AstroEngine.angular_separation(0.0, 0.0, 0.0, 90.0)
        assert abs(sep - 90.0) < 1e-10


# ──────────────────────────────────────────────────────────────────────
# Conjunction Search Tests
# ──────────────────────────────────────────────────────────────────────

class TestFindConjunctions:
    """Verifies conjunction/opposition search."""

    def test_returns_list(self):
        """Result is a list."""
        results = AstroEngine.find_conjunctions(
            datetime(2024, 1, 1), num_days=30)
        assert isinstance(results, list)

    def test_result_structure(self):
        """Each result contains expected keys."""
        results = AstroEngine.find_conjunctions(
            datetime(2024, 1, 1), num_days=60)
        for r in results:
            assert 'date' in r
            assert 'type' in r
            assert r['type'] in ('conjunction', 'opposition')
            assert 'bodies' in r
            assert 'separation' in r

    def test_events_over_year(self):
        """Over a year, should find at least a few events."""
        results = AstroEngine.find_conjunctions(
            datetime(2024, 1, 1), num_days=365)
        assert len(results) >= 1


# ──────────────────────────────────────────────────────────────────────
# Eclipse Search Tests
# ──────────────────────────────────────────────────────────────────────

class TestFindEclipses:
    """Verifies eclipse detection."""

    def test_returns_list(self):
        """Result is a list."""
        results = AstroEngine.find_eclipses(datetime(2024, 1, 1), num_months=6)
        assert isinstance(results, list)

    def test_fewer_eclipses_than_lunations(self):
        """Over 12 months, fewer eclipses than lunations (max ~5-6)."""
        results = AstroEngine.find_eclipses(datetime(2024, 1, 1), num_months=12)
        assert len(results) < 12

    def test_eclipses_2024(self):
        """In 2024, at least 2 eclipses (known solar + lunar)."""
        results = AstroEngine.find_eclipses(datetime(2024, 1, 1), num_months=12)
        assert len(results) >= 2, f"Only {len(results)} eclipse(s) detected"

    def test_result_structure(self):
        """Each result contains expected keys."""
        results = AstroEngine.find_eclipses(datetime(2024, 1, 1), num_months=6)
        for r in results:
            assert 'date' in r
            assert r['type'] in ('solar', 'lunar')
            assert 'certainty' in r
            assert 'moon_latitude' in r
            assert abs(r['moon_latitude']) < 1.58


# ──────────────────────────────────────────────────────────────────────
# Rises, sets and twilights against the USNO (aa.usno.navy.mil/api/rstt)
# ──────────────────────────────────────────────────────────────────────

class TestFindEventsUSNO:
    """
    find_events() over the local day, against the times of the US Naval
    Observatory (rounded to the minute, local time): within 45 s.
    """

    CASES = (
        # (date, lat, lon, utc_offset, body, {event: "HH:MM" local})
        ((2026, 11, 2), 48.8566, 2.3522, 1, "sun",
         {"dawn_civ": "07:06", "rise": "07:39", "transit": "12:34", "set": "17:29", "dusk_civ": "18:02"}),
        ((2026, 11, 2), 48.8566, 2.3522, 1, "moon", {"transit": "07:16", "set": "14:45"}),
        ((2026, 11, 2), 34.0522, -118.2437, -8, "sun",
         {"dawn_civ": "05:48", "rise": "06:14", "transit": "11:37", "set": "16:59", "dusk_civ": "17:25"}),
        ((2026, 11, 2), 34.0522, -118.2437, -8, "moon", {"transit": "06:35", "set": "13:27"}),
        ((2026, 6, 21), 48.8566, 2.3522, 2, "sun",
         {"dawn_civ": "05:04", "rise": "05:47", "transit": "13:52", "set": "21:58", "dusk_civ": "22:41"}),
        ((2026, 6, 21), 48.8566, 2.3522, 2, "moon", {"set": "01:23", "rise": "13:30", "transit": "19:41"}),
    )

    @pytest.mark.parametrize("ymd, lat, lon, tz, body, expected", CASES)
    def test_against_usno(self, ymd, lat, lon, tz, body, expected):
        local_noon = datetime(*ymd, 12)
        events = AstroEngine.find_events(local_noon - timedelta(hours=tz), lat, lon, body, tz=tz)
        for name, hhmm in expected.items():
            ref = datetime(*ymd, *map(int, hhmm.split(":")))
            got = events[name] + timedelta(hours=tz)
            assert abs((got - ref).total_seconds()) <= 45, f"{body} {name}: {got:%H:%M:%S} (USNO {hhmm})"

    def test_no_astronomical_night_in_june_in_paris(self):
        """At 48.9° N on 21 June, the Sun never gets 18° below the horizon."""
        events = AstroEngine.find_events(datetime(2026, 6, 21, 10), 48.8566, 2.3522, "sun", tz=2)
        assert events["dawn_astro"] is None and events["dusk_astro"] is None

    def test_local_day_far_from_greenwich(self):
        """Los Angeles (UTC−8): the sunset at 16:59 local is 00:59 UT the next day."""
        events = AstroEngine.find_events(datetime(2026, 11, 2, 20), 34.0522, -118.2437, "sun",
                                         tz=-8)
        assert events["set"].date() == datetime(2026, 11, 3).date()


# ──────────────────────────────────────────────────────────────────────
# IANA time zones, observer height, topocentric positions, Moon phase
# ──────────────────────────────────────────────────────────────────────

class TestZonesAndObserver:
    """References: USNO (rises and sets), JPL Horizons (positions, illumination)."""

    PARIS = (48.8566, 2.3522)

    @pytest.mark.parametrize("ymd, expected", [
        # summer time ends at 3 h on 25 October (25-hour day), begins on 29 March
        ((2026, 10, 25), {"dawn_civ": "06:54", "rise": "07:26", "transit": "12:35",
                          "set": "17:42", "dusk_civ": "18:15"}),
        ((2026, 3, 29), {"dawn_civ": "07:03", "rise": "07:35", "transit": "13:55",
                         "set": "20:17", "dusk_civ": "20:49"}),
    ])
    def test_summer_time_changes(self, ymd, expected):
        from zoneinfo import ZoneInfo
        paris = ZoneInfo("Europe/Paris")
        events = AstroEngine.find_events(datetime(*ymd, 12), *self.PARIS, "sun", tz=paris)
        for name, hhmm in expected.items():
            got = events[name].replace(tzinfo=ZoneInfo("UTC")).astimezone(paris)
            ref = datetime(*ymd, *map(int, hhmm.split(":")), tzinfo=paris)
            assert abs((got - ref).total_seconds()) <= 45, f"{name}: {got:%H:%M:%S} (USNO {hhmm})"

    def test_half_hour_zone(self):
        """Kolkata, UTC+5:30 (USNO, 2 November 2026)."""
        from zoneinfo import ZoneInfo
        events = AstroEngine.find_events(datetime(2026, 11, 2, 6), 22.5726, 88.3639, "sun",
                                         tz=ZoneInfo("Asia/Kolkata"))
        for name, hhmm in {"dawn_civ": "05:18", "rise": "05:41", "transit": "11:20",
                           "set": "16:59", "dusk_civ": "17:22"}.items():
            got = events[name] + timedelta(hours=5.5)
            ref = datetime(2026, 11, 2, *map(int, hhmm.split(":")))
            assert abs((got - ref).total_seconds()) <= 45, f"{name}: {got:%H:%M:%S} (USNO {hhmm})"

    def test_local_day_of_a_summer_time_change_lasts_25_hours(self):
        from zoneinfo import ZoneInfo
        start, end = AstroEngine._local_day(datetime(2026, 10, 25, 12), ZoneInfo("Europe/Paris"))
        assert (end - start) == timedelta(hours=25)
        assert start == datetime(2026, 10, 24, 22)           # local midnight, summer time

    def test_height_lowers_the_horizon(self):
        """From 1000 m (dip 0.93°), the Sun rises ~6 min earlier and sets ~6 min later."""
        low  = AstroEngine.find_events(datetime(2026, 11, 2, 12), *self.PARIS, "sun", tz=1)
        high = AstroEngine.find_events(datetime(2026, 11, 2, 12), *self.PARIS, "sun", tz=1,
                                       elevation_m=1000)
        assert 4 * 60 < (low["rise"] - high["rise"]).total_seconds() < 8 * 60
        assert 4 * 60 < (high["set"] - low["set"]).total_seconds() < 8 * 60
        assert high["dawn_civ"] == low["dawn_civ"]           # twilights: geometric centre

    def test_topocentric_positions_match_horizons(self):
        """Paris, 2 November 2026 12h UT: airless apparent azimuth and altitude (JPL Horizons)."""
        t = AstroEngine.julian_century_j2000(datetime(2026, 11, 2, 12))
        for body, (az, alt) in {"sun": (186.955686, 26.045381), "moon": (275.664805, 15.575444)}.items():
            h, a = AstroEngine.horizontal(t, *self.PARIS, body)
            assert abs(h - alt) < 1 / 3600 and abs(a - az) * math.cos(math.radians(alt)) < 1 / 3600, body

    def test_moon_phase_matches_horizons(self):
        """Geocentric illuminated fraction 42.90961 % (JPL Horizons); new moon of 10 October."""
        illum, age = AstroEngine.moon_phase(AstroEngine.julian_century_j2000(datetime(2026, 11, 2, 12)))
        assert abs(illum - 42.90961) < 0.02
        assert 22.5 < age < 23.0


# ──────────────────────────────────────────────────────────────────────
# Catalogue stars brought to the date (sky map)
# ──────────────────────────────────────────────────────────────────────

class TestStarsOfTheDate:
    """J2000 star positions precessed to the date, checked by Meeus's rigorous precession (chap. 21)."""

    ALDEBARAN = (4.5988, 16.5093)                    # J2000, constellations.py
    WHEN, PARIS = datetime(2026, 11, 2, 22), (48.8566, 2.3522)

    @staticmethod
    def _precess_meeus(ra_h, dec_deg, t):
        """Equatorial precession J2000 → date (Meeus 21.2 and 21.3), without nutation nor aberration."""
        arcsec = lambda x: math.radians(x / 3600.0)
        zeta  = arcsec(2306.2181 * t + 0.30188 * t * t + 0.017998 * t ** 3)
        z     = arcsec(2306.2181 * t + 1.09468 * t * t + 0.018203 * t ** 3)
        theta = arcsec(2004.3109 * t - 0.42665 * t * t - 0.041833 * t ** 3)
        a0, d0 = math.radians(ra_h * 15.0), math.radians(dec_deg)
        A = math.cos(d0) * math.sin(a0 + zeta)
        B = math.cos(theta) * math.cos(d0) * math.cos(a0 + zeta) - math.sin(theta) * math.sin(d0)
        C = math.sin(theta) * math.cos(d0) * math.cos(a0 + zeta) + math.cos(theta) * math.sin(d0)
        return (math.degrees(math.atan2(A, B) + z) % 360.0) / 15.0, math.degrees(math.asin(C))

    def _separation_arcsec(self, alt1, az1, alt2, az2):
        return AstroEngine.angular_separation(az1 / 15.0, alt1, az2 / 15.0, alt2) * 3600.0

    def test_matches_rigorous_precession(self):
        """Within 1′ of Meeus's precession (the rest: nutation and aberration, ~40″ at most)."""
        t = AstroEngine.julian_century_j2000(self.WHEN)
        jd = AstroEngine.julian_day(self.WHEN)
        alt, az = AstroEngine.stars_horizontal(t, *self.PARIS, [self.ALDEBARAN[0]], [self.ALDEBARAN[1]])
        ra, dec = self._precess_meeus(*self.ALDEBARAN, t)
        ref_alt, ref_az = AstroEngine.equatorial_to_horizontal(jd, *self.PARIS, ra, dec)
        assert self._separation_arcsec(alt[0], az[0], ref_alt, ref_az) < 60.0

    def test_j2000_position_is_a_third_of_a_degree_off(self):
        """The bug fixed: the J2000 coordinates used as such are ~0.37° off in 2026."""
        t = AstroEngine.julian_century_j2000(self.WHEN)
        jd = AstroEngine.julian_day(self.WHEN)
        alt, az = AstroEngine.stars_horizontal(t, *self.PARIS, [self.ALDEBARAN[0]], [self.ALDEBARAN[1]])
        old_alt, old_az = AstroEngine.equatorial_to_horizontal(jd, *self.PARIS, *self.ALDEBARAN)
        assert self._separation_arcsec(alt[0], az[0], old_alt, old_az) > 0.3 * 3600

    def test_whole_catalogue_at_once(self):
        from constellations import STARS
        t = AstroEngine.julian_century_j2000(self.WHEN)
        alts, azs = AstroEngine.stars_horizontal(t, *self.PARIS, [s[0] for s in STARS.values()],
                                                 [s[1] for s in STARS.values()])
        assert len(alts) == len(azs) == len(STARS)
        assert all(-90 <= a <= 90 for a in alts) and all(0 <= z < 360 for z in azs)


def test_version_is_single_sourced():
    """The engine's docstring describes the version the interface and the PDF show."""
    import engine
    from config import APP_VERSION
    assert f"v{APP_VERSION}" in engine.__doc__
