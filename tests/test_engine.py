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
    """Conjunctions, oppositions and greatest elongations, to the minute."""

    @pytest.fixture(scope="class")
    @classmethod
    def year_2026(cls):
        return AstroEngine.find_conjunctions(datetime(2026, 1, 1), num_days=365)

    @staticmethod
    def _find(events, kind, bodies, month):
        return next(e for e in events if e["type"] == kind and e["bodies"] == bodies
                    and e["date"].month == month)

    def test_returns_list(self):
        """Result is a list."""
        results = AstroEngine.find_conjunctions(
            datetime(2024, 1, 1), num_days=30)
        assert isinstance(results, list)

    def test_result_structure(self, year_2026):
        """Each result contains the expected keys, sorted by date."""
        for r in year_2026:
            assert set(r) >= {"date", "type", "bodies", "separation", "kind", "transit", "side", "details"}
            assert r["type"] in ("conjunction", "opposition", "greatest_elongation")
        assert [r["date"] for r in year_2026] == sorted(r["date"] for r in year_2026)

    @pytest.mark.parametrize("kind, bodies, instant", [
        # JPL Horizons: crossing of the observer ecliptic longitudes (quantity 31), minute sampling
        ("conjunction", ("Venus", "Sun"), datetime(2026, 1, 6, 16, 36, 0)),
        ("opposition", ("Jupiter", "Sun"), datetime(2026, 1, 10, 8, 42, 10)),
        ("conjunction", ("Mercury", "Sun"), datetime(2026, 3, 7, 11, 1, 43)),
        ("conjunction", ("Venus", "Saturn"), datetime(2026, 3, 8, 13, 39, 38)),
        ("conjunction", ("Mercury", "Sun"), datetime(2026, 5, 14, 14, 24, 22)),
        ("opposition", ("Saturn", "Sun"), datetime(2026, 10, 4, 12, 29, 12)),
        ("conjunction", ("Venus", "Sun"), datetime(2026, 10, 24, 3, 44, 7)),
        ("conjunction", ("Mars", "Jupiter"), datetime(2026, 11, 16, 6, 23, 38)),
    ])
    def test_instants_match_horizons(self, year_2026, kind, bodies, instant):
        event = self._find(year_2026, kind, bodies, instant.month)
        assert abs((event["date"] - instant).total_seconds()) < 30

    def test_inferior_and_superior_conjunctions(self, year_2026):
        """Venus behind the Sun in January 2026, between the Earth and the Sun in October."""
        superior = self._find(year_2026, "conjunction", ("Venus", "Sun"), 1)
        inferior = self._find(year_2026, "conjunction", ("Venus", "Sun"), 10)
        assert superior["kind"] == "superior" and inferior["kind"] == "inferior"
        assert inferior["side"] == "south" and inferior["separation"] == pytest.approx(6.51, abs=0.02)
        assert not superior["transit"] and not inferior["transit"]
        assert self._find(year_2026, "conjunction", ("Jupiter", "Sun"), 7)["kind"] is None

    def test_planet_north_of_the_other(self, year_2026):
        """Mars passes 1.2° north of Jupiter on 16 November 2026."""
        event = self._find(year_2026, "conjunction", ("Mars", "Jupiter"), 11)
        assert event["side"] == "north" and event["separation"] == pytest.approx(1.195, abs=0.01)

    @pytest.mark.parametrize("start, planet, instant", [
        (datetime(2019, 11, 1), "Mercury", datetime(2019, 11, 11, 15, 21, 42)),   # Horizons
        (datetime(2012, 6, 1), "Venus", datetime(2012, 6, 6, 1, 9)),               # USNO
    ])
    def test_transits(self, start, planet, instant):
        event = next(e for e in AstroEngine.find_conjunctions(start, num_days=30)
                     if e["bodies"] == (planet, "Sun") and e["type"] == "conjunction")
        assert event["kind"] == "inferior" and event["transit"]
        assert abs((event["date"] - instant).total_seconds()) < 60

    @pytest.mark.parametrize("planet, month, instant, elongation, side", [
        # Horizons, minute sampling: maximum of the angle Sun–planet
        ("Mercury", 2, datetime(2026, 2, 19, 17, 41), 18.1227, "east"),
        ("Venus", 8, datetime(2026, 8, 15, 6, 34), 45.8923, "east"),
        ("Mercury", 4, datetime(2026, 4, 3, 22, 33), 27.819, "west"),
    ])
    def test_greatest_elongations(self, year_2026, planet, month, instant, elongation, side):
        event = self._find(year_2026, "greatest_elongation", (planet, "Sun"), month)
        assert event["side"] == side
        assert event["separation"] == pytest.approx(elongation, abs=0.002)
        assert abs((event["date"] - instant).total_seconds()) < 300     # a very flat maximum

    def test_no_opposition_of_inner_planets(self, year_2026):
        assert not [e for e in year_2026 if e["type"] == "opposition"
                    and e["bodies"][0] in ("Mercury", "Venus")]
        assert not [e for e in year_2026 if e["type"] == "greatest_elongation"
                    and e["bodies"][0] not in ("Mercury", "Venus")]

    def test_scene_of_an_event(self, year_2026):
        """The map of an event: both paths around the instant, the stars of the field."""
        from star_catalog import CATALOG
        event = self._find(year_2026, "conjunction", ("Mars", "Jupiter"), 11)
        scene = AstroEngine.event_scene(event, CATALOG)
        (a, ra_a, dec_a, ra0_a, dec0_a), (b, ra_b, dec_b, ra0_b, dec0_b) = scene["bodies"]
        assert (a, b) == ("Mars", "Jupiter") and len(ra_a) == len(scene["days"])
        ra1, dec1, ra2, dec2 = map(math.radians, (ra0_a * 15, dec0_a, ra0_b * 15, dec0_b))
        distance = math.degrees(math.acos(math.sin(dec1) * math.sin(dec2)
                                          + math.cos(dec1) * math.cos(dec2) * math.cos(ra1 - ra2)))
        assert distance == pytest.approx(event["separation"], abs=0.001)
        assert dec0_a > dec0_b                                 # Mars to the north
        assert len(scene["stars"]) == len(CATALOG)
        assert 0.26 < scene["sun_radius"] < 0.28


class TestMinorPlanets:
    """Minor planets: JPL Horizons tables (asteroids, dwarf planets) and DE440 (Pluto)."""

    # JPL Horizons, astrometric RA/Dec (ICRF, quantity 1) and visual magnitude (quantity 9), UT
    @pytest.mark.parametrize("body, when, ra, dec, mag", [
        ("Ceres", datetime(1900, 3, 1), 297.672747950, -23.928223019, 9.199),
        ("Ceres", datetime(2026, 11, 3, 12), 114.662060988, 24.112152375, 8.197),
        ("Vesta", datetime(2026, 11, 3, 12), None, None, None),
        ("Sedna", datetime(1900, 3, 1), 11.767674867, -4.116757931, 22.791),
        ("Sedna", datetime(2026, 11, 3, 12), 62.095219201, 8.776505972, 20.727),
        ("Eris", datetime(2026, 11, 3, 12), None, None, None),
    ])
    def test_positions_and_magnitudes_match_horizons(self, body, when, ra, dec, mag):
        from engine import _sky
        t = AstroEngine.julian_century_j2000(when)
        astrometric = _sky()["earth"].at(AstroEngine._time_ut(t)).observe(AstroEngine._target(body))
        ra_, dec_, _ = astrometric.radec()
        if ra is None:                                   # the table covers it: a finite position
            assert math.isfinite(ra_.hours) and math.isfinite(dec_.degrees)
            return
        assert abs(((ra_._degrees - ra + 180) % 360 - 180) * math.cos(math.radians(dec)) * 3600) < 0.01
        assert abs(dec_.degrees - dec) * 3600 < 0.01
        assert AstroEngine.observations(t, [body])[body]["mag"] == pytest.approx(mag, abs=0.02)

    def test_vesta_and_eris_magnitudes(self):
        """Horizons, 3 November 2026 12h UT: Vesta 6.74, Eris 18.57, Haumea 17.25."""
        t = AstroEngine.julian_century_j2000(datetime(2026, 11, 3, 12))
        seen = AstroEngine.observations(t, ["Vesta", "Eris", "Haumea"])
        assert seen["Vesta"]["mag"] == pytest.approx(6.74, abs=0.02)
        assert seen["Eris"]["mag"] == pytest.approx(18.57, abs=0.02)
        assert seen["Haumea"]["mag"] == pytest.approx(17.25, abs=0.02)

    def test_rise_and_set_of_a_minor_planet(self):
        events = AstroEngine.find_events(datetime(2026, 11, 1, 21), 49.6, -1.6, "Vesta", 0, 0.0)
        assert events["rise"] is not None and events["set"] is not None

    def test_outside_the_tables(self):
        with pytest.raises(ValueError):
            AstroEngine.planet_position(AstroEngine.julian_century_j2000(datetime(1849, 1, 1)), "Ceres")

    def test_oppositions_of_minor_planets(self):
        """Vesta at opposition on 13 October 2026, magnitude 6.4; none for Ceres in 2026."""
        events = [e for e in AstroEngine.find_conjunctions(datetime(2026, 1, 1), 365)
                  if e["group"] == "minor"]
        vesta = next(e for e in events if e["bodies"] == ("Vesta", "Sun"))
        assert vesta["type"] == "opposition" and vesta["date"].strftime("%d/%m") == "13/10"
        assert vesta["mag"] == pytest.approx(6.4, abs=0.1)
        assert not [e for e in events if e["bodies"][0] == "Ceres"]


class TestBodyDetails:
    """Data window: JPL Horizons, 3 November 2026 12h UT (quantities 10, 13, 24)."""

    @pytest.mark.parametrize("body, illuminated, diameter, phase", [
        ("Venus", 3.96154, 58.44, 157.0335),
        ("Jupiter", 99.17030, 36.09617, 10.4511),
        ("moon", 32.26228, 1894.896, 110.7764),
    ])
    def test_matches_horizons(self, body, illuminated, diameter, phase):
        t = AstroEngine.julian_century_j2000(datetime(2026, 11, 3, 12))
        d = AstroEngine.body_details(t, body)
        assert d["illuminated"] == pytest.approx(illuminated, abs=0.01)
        assert d["diameter_arcsec"] == pytest.approx(diameter, rel=1e-3)
        assert d["phase_angle"] == pytest.approx(phase, abs=0.01)

    def test_sun(self):
        d = AstroEngine.body_details(AstroEngine.julian_century_j2000(datetime(2026, 11, 3, 12)), "sun")
        assert d["phase_angle"] is None and 480 < d["light_time_s"] < 510
        assert 1890 < d["diameter_arcsec"] < 1960


class TestMoonAndSeasons:
    @pytest.fixture(scope="class")
    @classmethod
    def moon_2026(cls):
        return AstroEngine.find_moon_events(datetime(2026, 1, 1), num_days=365)

    @pytest.mark.parametrize("other, instant", [
        # JPL Horizons: crossing of the ecliptic longitudes (quantity 31), minute sampling
        ("Jupiter", datetime(2026, 1, 3, 22, 54, 25)),
        ("Saturn", datetime(2026, 2, 19, 20, 48, 6)),
        ("Venus", datetime(2026, 9, 14, 11, 32, 41)),
    ])
    def test_moon_conjunctions_match_horizons(self, moon_2026, other, instant):
        event = next(e for e in moon_2026 if e["bodies"] == ("Moon", other)
                     and abs((e["date"] - instant).total_seconds()) < 86400)
        assert abs((event["date"] - instant).total_seconds()) < 30

    def test_moon_and_bright_stars(self, moon_2026):
        stars = {e["bodies"][1] for e in moon_2026 if e["bodies"][1:] and e["bodies"][1] in AstroEngine.MOON_STARS}
        assert stars <= set(AstroEngine.MOON_STARS) and len(stars) >= 4   # Aldebaran: > 5° in 2026
        assert all(e["separation"] <= 5.0 for e in moon_2026 if e["type"] == "conjunction")

    def test_perigee_matches_horizons(self, moon_2026):
        """Horizons: least distance 360 361 km on 1 January 2026 at 21:51 UT."""
        perigee = moon_2026[0]
        assert perigee["type"] == "perigee"
        assert abs((perigee["date"] - datetime(2026, 1, 1, 21, 51)).total_seconds()) < 300
        assert perigee["distance_km"] == pytest.approx(360361, abs=5)
        assert sum(e["type"] == "apogee" for e in moon_2026) in (13, 14)

    def test_supermoon(self):
        """24 December 2026: perigee (356 648 km) within a day of the full moon; not in November."""
        events = AstroEngine.find_moon_events(datetime(2026, 11, 20), num_days=40)
        november, december = [e for e in events if e["type"] == "perigee"]
        assert november["syzygy"] is None and december["syzygy"] == "full"

    @pytest.mark.parametrize("kind, instant", [
        # USNO, Earth's seasons and apsides 2026 (UT, to the minute)
        ("perihelion", datetime(2026, 1, 3, 17, 16)),
        ("march_equinox", datetime(2026, 3, 20, 14, 46)),
        ("june_solstice", datetime(2026, 6, 21, 8, 24)),
        ("aphelion", datetime(2026, 7, 6, 17, 31)),
        ("september_equinox", datetime(2026, 9, 23, 0, 5)),
        ("december_solstice", datetime(2026, 12, 21, 20, 50)),
    ])
    def test_seasons_match_usno(self, kind, instant):
        events = AstroEngine.find_seasons(datetime(2026, 1, 1), num_days=365)
        event = next(e for e in events if kind in (e["type"], e["kind"]))
        assert abs((event["date"] - instant).total_seconds()) <= 60


class TestLocalVisibility:
    PARIS = (48.8566, 2.3522, 35.0)

    @pytest.fixture(scope="class")
    @classmethod
    def year_2026(cls):
        from zoneinfo import ZoneInfo
        events = AstroEngine.find_conjunctions(datetime(2026, 1, 1), num_days=365)
        events += AstroEngine.find_moon_events(datetime(2026, 1, 1), num_days=365)
        return AstroEngine.event_visibility(events, *cls.PARIS, ZoneInfo("Europe/Paris"))

    def test_opposition_visible_all_night(self, year_2026):
        """Jupiter at opposition, 10 January 2026: up all night, 63° high to the south at midnight."""
        jupiter = next(e for e in year_2026 if e["type"] == "opposition" and e["bodies"][0] == "Jupiter")
        vis = jupiter["visibility"]
        assert vis["period"] == "night" and vis["alt"] == pytest.approx(63, abs=1.5)
        assert 170 < vis["az"] < 190

    def test_superior_conjunction_not_observable(self, year_2026):
        venus = next(e for e in year_2026 if e["bodies"] == ("Venus", "Sun") and e["kind"] == "superior")
        assert venus["visibility"]["period"] is None and venus["visibility"]["reason"] == "daylight"

    def test_greatest_elongations_evening_and_morning(self, year_2026):
        east = next(e for e in year_2026 if e["type"] == "greatest_elongation" and e["side"] == "east")
        west = next(e for e in year_2026 if e["type"] == "greatest_elongation" and e["side"] == "west")
        assert east["visibility"]["period"] == "evening"
        assert west["visibility"]["period"] in ("morning", None)

    def test_no_dark_night_in_the_arctic_summer(self):
        events = [e for e in AstroEngine.find_conjunctions(datetime(2026, 6, 1), num_days=20)
                  if e["bodies"] == ("Venus", "Jupiter")]
        AstroEngine.event_visibility(events, 69.65, 18.96, 0.0, 1)        # Tromsø, 9 June
        assert events[0]["visibility"]["reason"] == "no_night"

    def test_occultation_of_regulus_from_paris(self, year_2026):
        """29 March 2026: the Moon hides Regulus seen from Paris, at dusk."""
        event = next(e for e in year_2026 if e["bodies"] == ("Moon", "Regulus")
                     and e["date"].strftime("%d/%m") == "29/03")
        occ = event["occultation"]
        assert occ["start"] < event["date"] < occ["end"] + timedelta(hours=1)
        assert 30 < occ["moon_alt_start"] < 45 and occ["sun_alt_start"] < 0
        # at the disappearance, the star is on the Moon's limb
        from engine import _sky
        from skyfield.api import wgs84
        sky = _sky()
        here = (sky["earth"] + wgs84.latlon(48.8566, 2.3522, elevation_m=35.0)).at(
            sky["ts"].ut1_jd(AstroEngine.julian_day(occ["start"])))
        moon = here.observe(sky["moon"]).apparent()
        star = here.observe(AstroEngine._target("Regulus")).apparent()
        limb = math.degrees(math.asin(1737.4 / moon.distance().km))
        assert abs(star.separation_from(moon).degrees - limb) * 3600 < 2.0


class TestTonight:
    """The night of 1 November 2026 at Cherbourg (UT; the zone only cuts the local day)."""
    LAT, LON = 49.6333, -1.6167

    @pytest.fixture(scope="class")
    @classmethod
    def night(cls):
        from zoneinfo import ZoneInfo
        return AstroEngine.tonight(datetime(2026, 11, 1, 21, 30), cls.LAT, cls.LON, 0.0,
                                   ZoneInfo("Europe/Paris"))

    def test_dark_night_matches_the_twilights(self, night):
        from zoneinfo import ZoneInfo
        zone = ZoneInfo("Europe/Paris")
        today = AstroEngine.find_events(datetime(2026, 11, 1, 12), self.LAT, self.LON, "sun", zone)
        tomorrow = AstroEngine.find_events(datetime(2026, 11, 2, 12), self.LAT, self.LON, "sun", zone)
        assert night["dark"] == "astro"
        assert abs(night["dusk"] - today["dusk_astro"].replace(tzinfo=None)) < timedelta(minutes=1)
        assert abs(night["dawn"] - tomorrow["dawn_astro"].replace(tzinfo=None)) < timedelta(minutes=1)

    def test_moon(self, night):
        """Last quarter: rises at 23:42 local time, does not set before dawn."""
        moon = night["moon"]
        assert abs(moon["fraction"] - 0.49) < 0.02 and moon["set"] is None
        assert abs(moon["rise"] - datetime(2026, 11, 1, 22, 42)) < timedelta(minutes=2)
        assert 0.4 < moon["up"] < 0.7

    def test_planets(self, night):
        planets = {p["name"]: p for p in night["planets"]}
        assert set(planets) == {"Saturn", "Neptune", "Uranus", "Mars", "Jupiter"}
        assert planets["Saturn"]["period"] == "evening" and planets["Jupiter"]["period"] == "morning"
        assert planets["Jupiter"]["rise"] is not None and planets["Jupiter"]["set"] is None
        assert abs(planets["Jupiter"]["mag"] + 2.0) < 0.2
        assert [p["best"] for p in night["planets"]] == sorted(p["best"] for p in night["planets"])

    def test_the_night_under_way(self, night):
        """At 3 a.m., "tonight" is the night already begun."""
        from zoneinfo import ZoneInfo
        later = AstroEngine.tonight(datetime(2026, 11, 2, 3, 0), self.LAT, self.LON, 0.0,
                                    ZoneInfo("Europe/Paris"))
        assert later["dusk"] == night["dusk"] and later["start"] == night["start"]

    def test_white_night(self):
        """Tromsø at the summer solstice: no darkness, no planet."""
        from zoneinfo import ZoneInfo
        night = AstroEngine.tonight(datetime(2026, 6, 21, 12), 69.65, 18.96, 0.0, ZoneInfo("Europe/Oslo"))
        assert night["dark"] is None and night["dusk"] is None and night["planets"] == []

    def test_upcoming_events(self):
        from zoneinfo import ZoneInfo
        events = AstroEngine.upcoming_events(datetime(2026, 11, 1, 21, 30), self.LAT, self.LON, 0.0,
                                             ZoneInfo("Europe/Paris"))
        assert len(events) == 3 and [e["date"] for e in events] == sorted(e["date"] for e in events)
        assert all(e["visibility"]["period"] for e in events)
        assert events[0]["bodies"] == ("Moon", "Mars")


class TestMoonCalendar:
    """November 2026 at Cherbourg (Europe/Paris): principal phases of the USNO, in UT."""

    @pytest.fixture(scope="class")
    @classmethod
    def november(cls):
        from zoneinfo import ZoneInfo
        return AstroEngine.moon_calendar(2026, 11, 49.6333, -1.6167, 0.0, ZoneInfo("Europe/Paris"))

    def test_one_row_per_day(self, november):
        assert len(november) == 30 and november[0]["date"].day == 1 and november[-1]["date"].day == 30

    @pytest.mark.parametrize("day, kind, hour, minute", [
        (1, "last_quarter", 20, 28), (9, "new_moon", 7, 2), (17, "first_quarter", 11, 48),
        (24, "full_moon", 14, 53),
    ])
    def test_principal_phases(self, november, day, kind, hour, minute):
        event = november[day - 1]["event"]
        assert event["kind"] == kind
        assert abs(event["time"] - datetime(2026, 11, day, hour, minute)) <= timedelta(minutes=1)
        assert sum(1 for d in november if d["event"]) == 4

    def test_fraction_and_phase(self, november):
        assert november[8]["fraction"] < 0.01 and november[23]["fraction"] > 0.99
        assert abs(november[16]["phase"] - 90.0) < 5.0          # first quarter, at noon

    def test_rises_and_sets(self, november):
        """The Moon rises about 50 minutes later each day, and skips a day once a month."""
        assert november[1]["rise"] is None and november[2]["rise"] is not None
        moon = AstroEngine.find_events(datetime(2026, 11, 1, 12), 49.6333, -1.6167, "moon", 1)
        assert abs(november[0]["rise"] - moon["rise"]) < timedelta(seconds=2)

    def test_local_days_of_the_zone(self):
        """In Tokyo, the full Moon of 24 November 14:53 UT falls on the 24th at 23:53 local time."""
        from zoneinfo import ZoneInfo
        tokyo = AstroEngine.moon_calendar(2026, 11, 35.68, 139.69, 0.0, ZoneInfo("Asia/Tokyo"))
        assert tokyo[23]["event"]["kind"] == "full_moon"


class TestDeepSky:
    """The Messier catalogue (assets/messier.csv, OpenNGC + SEDS) and the night's best objects."""

    def test_catalogue(self):
        from engine import MESSIER_TYPES, messier_catalog
        catalog = messier_catalog()
        assert [o["m"] for o in catalog] == list(range(1, 111))
        assert all(o["type"] in MESSIER_TYPES and -2 < o["mag"] <= 11.0 for o in catalog)   # M91: 11.0
        m31 = catalog[30]
        assert m31["id"] == "NGC 224" and m31["const"] == "And" and m31["name"] == "Andromeda Galaxy"
        assert abs(m31["ra"] - 0.7123) < 0.001 and abs(m31["dec"] - 41.269) < 0.001 and m31["mag"] == 3.4
        assert catalog[101]["id"] == "NGC 5866"                 # M102, the Spindle Galaxy
        assert catalog[21]["mag"] == 5.1                        # M22, magnitude from SEDS

    def test_upper_culmination_of_m31(self):
        """From Cherbourg, M31 culminates at 90° − (φ − δ of the date) ≈ 81.8°."""
        from zoneinfo import ZoneInfo
        night = AstroEngine.tonight(datetime(2026, 11, 1, 21, 30), 49.6333, -1.6167, 0.0, ZoneInfo("Europe/Paris"))
        m31 = next(o for o in night["deep_sky"] if o["m"] == 31)
        assert abs(m31["alt"] - 81.8) < 0.3 and abs(m31["az"] - 180.0) < 10.0
        alt, _az = AstroEngine.deep_sky_horizontal(AstroEngine.julian_century_j2000(m31["best"]), 49.6333, -1.6167)
        assert abs(float(alt[30]) - m31["alt"]) < 0.3            # hour angles vs full reduction

    def test_the_brightest_first(self):
        from zoneinfo import ZoneInfo
        night = AstroEngine.tonight(datetime(2026, 11, 1, 21, 30), 49.6333, -1.6167, 0.0, ZoneInfo("Europe/Paris"))
        assert [o["m"] for o in night["deep_sky"]] == [45, 44, 31, 42, 39]
        assert all(o["alt"] >= 30.0 for o in night["deep_sky"])

    def test_white_night(self):
        from zoneinfo import ZoneInfo
        night = AstroEngine.tonight(datetime(2026, 6, 21, 12), 69.65, 18.96, 0.0, ZoneInfo("Europe/Oslo"))
        assert night["deep_sky"] == []


class TestComets:
    """Comets of the Horizons tables, against JPL Horizons (astrometric RA/Dec, T-mag)."""

    @pytest.mark.parametrize("name, when, ra, dec, mag", [
        ("Panstarrs", datetime(2027, 7, 18, 10), 164.142840347, -28.917184962, 9.131),     # perihelion
        ("Honda", datetime(2027, 8, 30, 23), 127.706470800, 17.673400452, 8.247),          # perihelion
        ("Tsuchinshan", datetime(2028, 11, 10, 4), 307.159489161, -76.723977498, 6.637),   # brightest
        ("Borrelly", datetime(2028, 12, 7, 5), 37.809650992, -4.834328672, 9.627),
        ("Tsuchinshan", datetime(2026, 11, 7), 189.445907295, 0.308347604, 17.874),       # far away
    ])
    def test_position_and_magnitude(self, name, when, ra, dec, mag):
        from engine import _sky
        sky = _sky()
        t = sky["ts"].ut1_jd(AstroEngine.julian_day(when))
        got_ra, got_dec, _ = sky["earth"].at(t).observe(AstroEngine._target(name)).radec()
        assert abs((got_ra._degrees - ra) * math.cos(math.radians(dec))) * 3600 < 0.05
        assert abs(got_dec.degrees - dec) * 3600 < 0.05
        tc = (AstroEngine.julian_day(when) - 2451545.0) / 36525.0
        assert abs(AstroEngine.observations(tc, [name])[name]["mag"] - mag) < 0.01

    def test_only_within_their_tables(self):
        from engine import COMETS
        assert AstroEngine.comets_at(AstroEngine.julian_century_j2000(datetime(2028, 1, 1))) == COMETS
        for year in (2024, 2035):
            assert AstroEngine.comets_at(AstroEngine.julian_century_j2000(datetime(year, 6, 1))) == ()

    def test_events(self):
        events = AstroEngine.find_comet_events(datetime(2026, 11, 7), 3 * 365)
        found = {(e["bodies"][0], e["type"]): e for e in events}
        brightest = found[("Tsuchinshan", "comet_brightest")]
        assert abs(brightest["date"] - datetime(2028, 11, 10, 12)) < timedelta(days=1)
        assert abs(brightest["mag"] - 6.6) < 0.1
        perihelion = found[("Honda", "comet_perihelion")]
        assert perihelion["date"].strftime("%d/%m/%Y") == "30/08/2027"
        assert abs(perihelion["distance_au"] - 0.559) < 0.002
        assert all(e["mag"] <= 12.0 and e["group"] == "comets" for e in events)

    def test_tonight_includes_a_bright_comet(self):
        """25 August 2027 at Cherbourg: 45P (magnitude 8) low in the east before dawn."""
        from zoneinfo import ZoneInfo
        night = AstroEngine.tonight(datetime(2027, 8, 25, 3), 49.6333, -1.6167, 0.0, ZoneInfo("Europe/Paris"))
        honda = next(p for p in night["planets"] if p["name"] == "Honda")
        assert honda["period"] == "morning" and 10 < honda["alt"] < 20 and honda["mag"] < 8.5
        assert not any(p["name"] in ("Borrelly", "Tsuchinshan") for p in night["planets"])   # faint

    def test_data_window(self):
        d = AstroEngine.body_details(AstroEngine.julian_century_j2000(datetime(2027, 8, 30, 23)), "Honda")
        assert d["illuminated"] is None and d["diameter_arcsec"] is None
        assert abs(d["helio_au"] - 0.559) < 0.002 and abs(d["dist_au"] - 1.053) < 0.002


class TestMeteorShowers:
    """Maxima of the meteor showers: the IMO Meteor Shower Calendar 2026 (λ☉ J2000, times in UT)."""

    @pytest.fixture(scope="class")
    @classmethod
    def year_2026(cls):
        return {e["kind"]: e for e in AstroEngine.find_meteor_showers(datetime(2026, 1, 1), 365)}

    @pytest.mark.parametrize("code, expected, minutes", [
        ("QUA", datetime(2026, 1, 3, 21, 0), 60),          # "close to 21h UT"
        ("LYR", datetime(2026, 4, 22, 19, 40), 10),        # 19h 40m UT
        ("PER", datetime(2026, 8, 13, 3, 0), 60),          # 02h to 04h UT
        ("DRA", datetime(2026, 10, 9, 1, 0), 30),          # 01h UT
        ("LEO", datetime(2026, 11, 17, 23, 45), 10),       # 23h 45m UT
        ("GEM", datetime(2026, 12, 14, 14, 0), 30),        # 14h UT
        ("URS", datetime(2026, 12, 22, 22, 0), 30),        # 22h UT
    ])
    def test_times_of_the_imo_calendar(self, year_2026, code, expected, minutes):
        assert abs(year_2026[code]["date"] - expected) <= timedelta(minutes=minutes)

    def test_dates_of_the_imo_calendar(self, year_2026):
        """Table 5: dates of the maxima, accurate for 2026."""
        dates = {"ETA": "06/05", "SDA": "31/07", "CAP": "31/07", "ORI": "21/10", "STA": "05/11",
                 "NTA": "12/11"}
        for code, day in dates.items():
            assert year_2026[code]["date"].strftime("%d/%m") == day, code
        assert len(year_2026) == len(AstroEngine.METEOR_SHOWERS)

    def test_over_the_new_year(self):
        """From 1 November: the Quadrantids and the Lyrids of the next year, in order."""
        events = AstroEngine.find_meteor_showers(datetime(2026, 11, 1), 365)
        assert len(events) == 13 and [e["date"] for e in events] == sorted(e["date"] for e in events)
        assert all(datetime(2026, 11, 1) <= e["date"] < datetime(2027, 11, 1) for e in events)
        qua = next(e for e in events if e["kind"] == "QUA")
        assert qua["date"].year == 2027 and qua["date"].strftime("%d/%m") == "04/01"
        assert events[0]["kind"] == "STA" and events[0]["group"] == "meteors"

    def test_perseids_from_cherbourg(self, year_2026):
        """2026: new Moon (total solar eclipse of 12 August), radiant high before dawn."""
        event = dict(year_2026["PER"])
        vis = AstroEngine.meteor_visibility(event, 49.64, -1.62, 0.0, 1)
        assert vis["period"] is not None and vis["alt"] > 55
        assert vis["moon"] == "none" and vis["moon_fraction"] < 0.02
        assert vis["rate"] == round(100 * math.sin(math.radians(vis["alt"])))
        assert vis["best"].date() == datetime(2026, 8, 13).date() and vis["best"].hour < 4

    def test_moonlight(self, year_2026):
        """The Quadrantids at full Moon, the Geminids with the Moon set (IMO, 2026)."""
        qua = AstroEngine.meteor_visibility(year_2026["QUA"], 49.64, -1.62, 0.0, 1)
        gem = AstroEngine.meteor_visibility(year_2026["GEM"], 49.64, -1.62, 0.0, 1)
        assert qua["moon"] == "strong" and qua["moon_fraction"] > 0.95
        assert gem["moon"] == "none" and gem["moon_alt"] < 0

    def test_from_the_south(self, year_2026):
        """Santiago: the η-Aquariids are higher than in Cherbourg, the Ursids never rise."""
        north = AstroEngine.meteor_visibility(year_2026["ETA"], 49.64, -1.62, 0.0, 1)
        south = AstroEngine.meteor_visibility(year_2026["ETA"], -33.45, -70.67, 500.0, -4)
        assert north["period"] == "morning" and north["alt"] < 20
        assert south["alt"] > north["alt"] + 20
        assert AstroEngine.meteor_visibility(year_2026["URS"], -33.45, -70.67, 500.0, -3)["reason"] == "horizon"

    def test_no_dark_night(self, year_2026):
        """Tromsø in mid-August: the Sun never 12° below the horizon."""
        vis = AstroEngine.meteor_visibility(year_2026["PER"], 69.65, 18.96, 0.0, 2)
        assert vis["period"] is None and vis["reason"] == "no_night" and vis["rate"] is None

    def test_with_the_other_events(self, year_2026):
        """event_visibility gives meteor showers their own night."""
        events = [dict(year_2026["GEM"])] + AstroEngine.find_seasons(datetime(2026, 12, 1), 30)
        AstroEngine.event_visibility(events, 49.64, -1.62, 0.0, 1)
        assert events[0]["visibility"]["rate"] > 100
        assert all(e.get("visibility") is None for e in events[1:])


class TestLocalEclipses:
    @pytest.fixture(scope="class")
    @classmethod
    def eclipses(cls):
        return AstroEngine.find_eclipses(datetime(2026, 1, 1), num_months=12)

    @pytest.mark.parametrize("lat, lon, seconds, maximum", [
        # NASA, path of the total eclipse of 12 August 2026: central line and duration
        (73 + 41.0 / 60, -(27 + 47.3 / 60), 135.4, "17:30"),
        (67 + 12.6 / 60, -(26 + 1.9 / 60), 138.1, "17:42"),
    ])
    def test_totality_on_the_central_line(self, eclipses, lat, lon, seconds, maximum):
        solar = next(e for e in eclipses if e["type"] == "solar" and e["greatest"].month == 8)
        local = AstroEngine.eclipse_local(solar, lat, lon)
        assert local["central"] == "total"
        assert local["duration_s"] == pytest.approx(seconds, abs=0.5)
        assert local["contacts"]["max"].strftime("%H:%M") == maximum

    def test_partial_in_paris_ends_at_sunset(self, eclipses):
        solar = next(e for e in eclipses if e["type"] == "solar" and e["greatest"].month == 8)
        local = AstroEngine.eclipse_local(solar, 48.8566, 2.3522)
        assert local["central"] is None and local["visible"]
        assert local["magnitude"] == pytest.approx(0.93, abs=0.01)
        assert local["obscuration"] == pytest.approx(0.92, abs=0.01)
        assert local["altitudes"]["c4"] < 0 < local["altitudes"]["c1"]

    def test_dallas_2024(self):
        """NASA: 3 min 51 s of totality in Dallas on 8 April 2024."""
        solar = next(e for e in AstroEngine.find_eclipses(datetime(2024, 3, 1), 3) if e["type"] == "solar")
        local = AstroEngine.eclipse_local(solar, 32.7767, -96.7970)
        assert local["duration_s"] == pytest.approx(231, abs=2)

    def test_no_eclipse_far_away(self, eclipses):
        solar = next(e for e in eclipses if e["type"] == "solar" and e["greatest"].month == 8)
        assert AstroEngine.eclipse_local(solar, -33.87, 151.21) is None        # Sydney

    def test_lunar_eclipse_contacts(self, eclipses):
        """3 March 2026 (NASA: U1 09:50, U2 11:04, U3 12:03, U4 13:17): set in Paris, up in Hawaii."""
        lunar = next(e for e in eclipses if e["type"] == "lunar" and e["greatest"].month == 3)
        paris = AstroEngine.eclipse_local(lunar, 48.8566, 2.3522)
        assert not paris["visible"]
        hawaii = AstroEngine.eclipse_local(lunar, 21.31, -157.86)
        assert hawaii["visible"]
        c = hawaii["contacts"]
        for key, expected in (("u1", "09:50"), ("u2", "11:04"), ("u3", "12:03"), ("u4", "13:17")):
            assert abs((c[key] - c[key].replace(hour=int(expected[:2]), minute=int(expected[3:]),
                                                 second=0)).total_seconds()) < 60, key


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
    """The engine's docstring describes the version the interface shows (its x.y:
    a corrective x.y.z release does not change the engine)."""
    import engine
    from config import APP_VERSION
    assert "v" + ".".join(APP_VERSION.split(".")[:2]) + ":" in engine.__doc__


# ──────────────────────────────────────────────────────────────────────
# Coordinates in the chosen system (JPL Horizons, 2 November 2026 12h UT)
# ──────────────────────────────────────────────────────────────────────

class TestCoordinateSystems:
    T = AstroEngine.julian_century_j2000(datetime(2026, 11, 2, 12))
    PARIS = (48.8566, 2.3522)

    def test_heliocentric_vectors(self):
        """Geometric heliocentric vectors, ecliptic J2000 (Horizons VECTORS, no correction)."""
        refs = {"Mars": (-0.3081280212458685, 1.565401835532534, 0.04036036724601148),
                "Jupiter": (-3.674476851412720, 3.842965080361585, 0.06624793661325734)}
        for body, ref in refs.items():
            c = AstroEngine.coordinates(self.T, body, "heliocentric", "ecliptic")
            for got, exp in zip((c["x"], c["y"], c["z"]), ref):
                assert abs(got - exp) < 2e-6, body          # Jupiter: barycentre vs centre, 160 km

    def test_geocentric_ecliptic_of_date(self):
        """Apparent geocentric ecliptic longitude and latitude of date (Horizons quantity 31)."""
        for body, (lon, lat) in {"Mars": (139.3734896, 1.6319487),
                                 "Jupiter": (144.5028828, 0.6951914)}.items():
            c = AstroEngine.coordinates(self.T, body, "geocentric", "ecliptic")
            assert abs(c["lon"] - lon) * 3600 < 1 and abs(c["lat"] - lat) * 3600 < 1, body

    def test_geocentric_equatorial_is_planet_position(self):
        c = AstroEngine.coordinates(self.T, "Venus", "geocentric", "equatorial")
        ra, dec, dist = AstroEngine.planet_position(self.T, "Venus")
        assert approx(c["lon"], ra * 15.0, 1e-9) and approx(c["lat"], dec, 1e-9)
        assert approx(c["dist"], dist, 1e-12)

    def test_topocentric_horizontal_is_horizontal(self):
        c = AstroEngine.coordinates(self.T, "moon", "topocentric", "horizontal", *self.PARIS)
        alt, az = AstroEngine.horizontal(self.T, *self.PARIS, "moon")
        assert approx(c["lat"], alt, 1e-9) and approx(c["lon"], az, 1e-9)

    def test_parallax_separates_geocentric_and_topocentric_moon(self):
        """Seen from Paris, the Moon is ~0.94° lower than from the Earth's centre."""
        geo = AstroEngine.coordinates(self.T, "moon", "geocentric", "horizontal", *self.PARIS)
        topo = AstroEngine.coordinates(self.T, "moon", "topocentric", "horizontal", *self.PARIS)
        assert 0.8 < geo["lat"] - topo["lat"] < 1.0

    @pytest.mark.parametrize("center, frame", [("heliocentric", "ecliptic"), ("geocentric", "equatorial"),
                                               ("topocentric", "horizontal"), ("topocentric", "ecliptic")])
    def test_cartesian_matches_the_angles(self, center, frame):
        c = AstroEngine.coordinates(self.T, "Mars", center, frame, *self.PARIS)
        lon, lat = math.radians(c["lon"]), math.radians(c["lat"])
        expected = (c["dist"] * math.cos(lat) * math.cos(lon), c["dist"] * math.cos(lat) * math.sin(lon),
                    c["dist"] * math.sin(lat))
        for got, exp in zip((c["x"], c["y"], c["z"]), expected):
            assert abs(got - exp) < 1e-9

    def test_centre_has_no_coordinates(self):
        assert AstroEngine.coordinates(self.T, "sun", "heliocentric", "ecliptic") is None
        assert AstroEngine.coordinates(self.T, "earth", "geocentric", "equatorial") is None
        assert AstroEngine.coordinates(self.T, "earth", "heliocentric", "ecliptic")["dist"] == \
            pytest.approx(0.9923, abs=1e-3)

    def test_no_horizontal_frame_from_the_sun(self):
        with pytest.raises(ValueError):
            AstroEngine.coordinates(self.T, "Mars", "heliocentric", "horizontal")


# ──────────────────────────────────────────────────────────────────────
# Magnitude, angle with the Sun, constellation (JPL Horizons, 2 Nov 2026 12h UT)
# ──────────────────────────────────────────────────────────────────────

class TestObservations:
    # Horizons quantities 9 (APmag), 23 (S-O-T elongation) and 29 (constellation)
    HORIZONS = {
        "sun":     (-26.759, None,     "Lib"),
        "moon":    (-9.870,  81.7051,  "Leo"),
        "Mercury": (4.581,   4.9327,   "Lib"),
        "Venus":   (-4.277,  15.2075,  "Vir"),
        "Mars":    (0.867,   80.7079,  "Leo"),
        "Jupiter": (-2.011,  75.5758,  "Leo"),
        "Saturn":  (0.469,   149.0110, "Cet"),
        "Uranus":  (5.609,   155.4561, "Tau"),
        "Neptune": (7.695,   141.9531, "Psc"),
        "Pluto":   (14.590,  83.0822,  "Cap"),
    }
    # Mercury, 165° from full phase behind the Sun: the magnitude models part (0.12)
    MAG_TOLERANCE = {"Mercury": 0.15}

    def test_against_horizons(self):
        seen = AstroEngine.observations(AstroEngine.julian_century_j2000(datetime(2026, 11, 2, 12)))
        assert seen["earth"] is None
        for body, (mag, elongation, constellation) in self.HORIZONS.items():
            o = seen[body]
            assert abs(o["mag"] - mag) < self.MAG_TOLERANCE.get(body, 0.05), f"{body}: {o['mag']:.3f}"
            if elongation is None:
                assert o["elongation"] is None
            else:
                assert abs(o["elongation"] - elongation) < 0.01, body
            assert o["constellation"] == constellation, body
        assert seen["Pluto"]["constellation_name"] == "Capricornus"

    def test_every_body_of_the_table(self):
        t = AstroEngine.julian_century_j2000(datetime(2026, 11, 2, 12))
        for body in AstroEngine.BODIES:
            c = AstroEngine.coordinates(t, body, "heliocentric", "ecliptic")
            assert (c is None) == (body == "sun"), body
        assert 29.0 < AstroEngine.coordinates(t, "Pluto", "heliocentric", "ecliptic")["dist"] < 50.0


class TestStarCatalog:
    def test_every_star_of_the_figures_is_in_the_catalogue(self):
        """The constellation lines need the position of each of their stars."""
        from constellations import CONSTELLATIONS
        from star_catalog import CATALOG
        names = {c[6] for c in CATALOG if c[6]}
        for edges in CONSTELLATIONS.values():
            for a, b in edges:
                assert a in names and b in names, (a, b)

    def test_proper_motion_moves_arcturus(self):
        """Arcturus, −1.09″ and −2.00″ a year: 1′ from its J2000 place in 2026."""
        from star_catalog import CATALOG
        ra, dec, pm_ra, pm_dec = next((c[1], c[2], c[4], c[5]) for c in CATALOG if c[6] == "Arcturus")
        t = AstroEngine.julian_century_j2000(datetime(2026, 11, 2, 22))
        fixed = AstroEngine.stars_horizontal(t, 48.8566, 2.3522, [ra], [dec])
        moving = AstroEngine.stars_horizontal(t, 48.8566, 2.3522, [ra], [dec],
                                              pm_ra_mas=[pm_ra], pm_dec_mas=[pm_dec])
        shift = AstroEngine.angular_separation(fixed[1][0] / 15, fixed[0][0], moving[1][0] / 15, moving[0][0])
        assert 0.8 < shift * 60 < 1.2                       # arcminutes



# ──────────────────────────────────────────────────────────────────────
# Eclipses projected on the ground (NASA's greatest eclipse points)
# ──────────────────────────────────────────────────────────────────────

class TestEclipseMap:
    # Greatest eclipse (NASA, Espenak): latitude, longitude
    NASA_GREATEST = {
        datetime(2026, 8, 12): (65.17, -25.21),        # total, Iceland
        datetime(2027, 2, 6): (-31.32, -48.50),        # annular, South Atlantic
        datetime(2027, 8, 2): (25.52, 33.20),          # total, Egypt
    }

    @pytest.fixture(scope="class")
    @classmethod
    def solar(cls):
        found = AstroEngine.find_eclipses(datetime(2026, 7, 1), 14)
        return {e["greatest"].replace(hour=0, minute=0, second=0): e for e in found if e["type"] == "solar"}

    def test_greatest_point_matches_nasa(self, solar):
        for day, (lat, lon) in self.NASA_GREATEST.items():
            scene = AstroEngine.eclipse_map(solar[day]["greatest"], "solar")
            got_lat, got_lon = scene["greatest"]
            assert abs(got_lat - lat) < 0.15 and abs(got_lon - lon) < 0.15, (day, scene["greatest"])

    def test_sun_and_moon_aligned_on_the_central_line(self, solar):
        """From the greatest point, at greatest eclipse, the Moon's centre is on the Sun's."""
        from engine import _sky
        from skyfield.api import wgs84
        e = solar[datetime(2027, 8, 2)]
        lat, lon = AstroEngine.eclipse_map(e["greatest"], "solar")["greatest"]
        sky = _sky()
        here = (sky["earth"] + wgs84.latlon(lat, lon)).at(sky["ts"].ut1_jd(AstroEngine.julian_day(e["greatest"])))
        sun, moon = (here.observe(sky[b]).apparent() for b in ("sun", "moon"))
        assert sun.separation_from(moon).arcseconds() < 2.0

    def test_width_of_the_path_of_totality(self, solar):
        """2 August 2027: path 258 km wide at greatest eclipse (NASA)."""
        e = solar[datetime(2027, 8, 2)]
        scene = AstroEngine.eclipse_map(e["greatest"], "solar")
        middle = len(scene["path"]) // 2
        lats, lons = scene["path"][middle]
        pts = [(math.radians(a), math.radians(b)) for a, b in zip(lats, lons)]
        diameter = max(6371.0 * math.acos(min(1.0, math.sin(a1) * math.sin(a2)
                                              + math.cos(a1) * math.cos(a2) * math.cos(b1 - b2)))
                       for a1, b1 in pts for a2, b2 in pts)
        assert 230 < diameter < 290, diameter

    def test_partial_magnitude_matches_a_direct_computation(self, solar):
        """12 August 2026 seen from Cherbourg: grid value vs a direct topocentric computation."""
        from engine import _sky
        from skyfield.api import wgs84
        import numpy as np
        e = solar[datetime(2026, 8, 12)]
        scene = AstroEngine.eclipse_map(e["greatest"], "solar", grid_step=0.5)
        lat, lon = 49.6333, -1.6167
        i = int(np.argmin(np.abs(scene["lats"] - lat)))
        j = int(np.argmin(np.abs(scene["lons"] - lon)))
        sky = _sky()
        here = sky["earth"] + wgs84.latlon(lat, lon)
        jd = AstroEngine.julian_day(e["greatest"]) + np.arange(-180, 181) / 1440.0
        at = here.at(sky["ts"].ut1_jd(jd))
        sun, moon = at.observe(sky["sun"]).apparent(), at.observe(sky["moon"]).apparent()
        rs = np.arcsin(696000.0 / sun.distance().km)
        rm = np.arcsin(1737.4 / moon.distance().km)
        sep = sun.separation_from(moon).radians
        up = sun.altaz()[0].degrees > 0
        direct = float(np.max(np.where(up, np.clip((rs + rm - sep) / (2 * rs), 0, None), 0)))
        assert 0.5 < direct < 1.0
        assert abs(scene["grid"][i, j] - direct) < 0.05

    def test_lunar_eclipse_where_the_moon_is_up(self):
        lunar = next(e for e in AstroEngine.find_eclipses(datetime(2027, 1, 1), 3) if e["type"] == "lunar")
        scene = AstroEngine.eclipse_map(lunar["greatest"], "lunar", half_span_hours=1.0)
        lat, lon = scene["greatest"]
        assert scene["at_greatest"].max() > 85.0                 # the Moon at the zenith somewhere
        import numpy as np
        i = int(np.argmin(np.abs(scene["lats"] - lat)))
        j = int(np.argmin(np.abs(scene["lons"] - lon)))
        assert scene["at_greatest"][i, j] > 85.0


# ──────────────────────────────────────────────────────────────────────
# Jupiter's moons and Saturn's rings (v4.8), against JPL Horizons
# ──────────────────────────────────────────────────────────────────────

class TestGalileanMoons:
    """Reference: geocentric apparent positions of Jupiter and its moons (Horizons),
    turned into radii of Jupiter along (x, west +) and across (y, north +) its equator."""

    @staticmethod
    def _at(*date):
        return AstroEngine.galilean_moons(AstroEngine.julian_century_j2000(datetime(*date)))

    @pytest.mark.parametrize("date, expected", [
        ((2026, 1, 30, 4, 0), [(-3.260, 0.123), (8.401, -0.036), (14.752, -0.063), (24.620, -0.258)]),
        ((2026, 6, 30, 20, 0), [(5.767, 0.018), (-7.546, -0.066), (9.818, 0.217), (26.159, -0.098)]),
        ((2026, 11, 17, 20, 0), [(4.778, -0.015), (9.017, 0.019), (-10.139, 0.018), (-10.600, -0.113)]),
    ])
    def test_positions(self, date, expected):
        moons = self._at(*date)
        assert [m["name"] for m in moons] == ["Io", "Europa", "Ganymede", "Callisto"]
        for moon, (x, y), tolerance in zip(moons, expected, (0.03, 0.05, 0.09, 0.15)):
            assert abs(moon["x"] - x) < tolerance, moon["name"]
            assert abs(moon["y"] - y) < 0.18, moon["name"]          # the tilt of the orbits is left out
            assert moon["state"] == "free"

    @pytest.mark.parametrize("moon, date, state", [
        (0, (2026, 1, 16, 18, 0), "transit"), (0, (2026, 2, 16, 16, 0), "occulted"),
        (0, (2026, 3, 8, 5, 0), "eclipsed"),
        (1, (2026, 1, 11, 19, 0), "transit"), (1, (2026, 2, 25, 3, 0), "occulted"),
        (1, (2026, 2, 18, 3, 0), "eclipsed"),
        (2, (2026, 1, 21, 10, 0), "transit"), (2, (2026, 3, 30, 9, 0), "occulted"),
        (2, (2026, 2, 22, 19, 0), "eclipsed"),
        (3, (2026, 1, 10, 8, 0), "transit"), (3, (2026, 4, 11, 22, 0), "occulted"),
        (3, (2026, 1, 1, 21, 0), "eclipsed"),
    ])
    def test_in_front_behind_and_in_the_shadow(self, moon, date, state):
        """Horizons' visibility codes t (transit), O (occulted) and u (umbral eclipse)."""
        assert self._at(*date)[moon]["state"] == state

    def test_eclipsed_away_from_the_disc(self):
        """Before opposition the shadow lies west of Jupiter: Io vanishes 1.35 radius from the centre."""
        io = self._at(2026, 3, 8, 5, 0)[0]
        assert io["state"] == "eclipsed" and 1.2 < abs(io["x"]) < 1.5

    def test_shadow_on_the_disc(self):
        """Near opposition (10 January 2026) a moon in transit carries its shadow with it."""
        io = self._at(2026, 1, 16, 18, 0)[0]
        assert io["state"] == "transit" and io["shadow"] is True
        assert self._at(2026, 1, 30, 4, 0)[0]["shadow"] is False

    def test_orbits_keep_their_size(self):
        """In 40 days each moon reaches its greatest elongation: 5.9, 9.4, 15.0 and 26.4 radii
        (semi-major axes of 421 800, 671 100, 1 070 400 and 1 882 700 km)."""
        reach = [0.0] * 4
        for hour in range(0, 24 * 40, 3):
            for i, moon in enumerate(AstroEngine.galilean_moons(
                    AstroEngine.julian_century_j2000(datetime(2026, 1, 1) + timedelta(hours=hour)))):
                reach[i] = max(reach[i], abs(moon["x"]))
        for found, km in zip(reach, (421800, 671100, 1070400, 1882700)):
            assert abs(found - km / 71492.0) < 0.25


class TestSaturnRings:
    """Reference: Horizons' sub-observer latitude (planetodetic), brought back to the ring plane."""

    @staticmethod
    def _centric(planetodetic):
        return math.degrees(math.atan(math.tan(math.radians(planetodetic)) * (54364.0 / 60268.0) ** 2))

    @pytest.mark.parametrize("date, horizons", [
        ((2020, 1, 1), 28.187555), ((2025, 3, 15), 0.610845), ((2026, 11, 5), -7.943098),
        ((2030, 3, 19), -26.870039), ((2032, 5, 17), -31.983054),
    ])
    def test_tilt(self, date, horizons):
        rings = AstroEngine.saturn_rings(AstroEngine.julian_century_j2000(datetime(*date)))
        assert abs(rings["tilt"] - self._centric(horizons)) < 0.001

    def test_size(self):
        """5 November 2026: Saturn's disc is 19.36″ (Horizons), ring A reaches 136 775 / 60 268 of it."""
        rings = AstroEngine.saturn_rings(AstroEngine.julian_century_j2000(datetime(2026, 11, 5)))
        assert abs(rings["major_arcsec"] - 19.36456 * 136775.0 / 60268.0) < 0.01
        assert abs(rings["minor_arcsec"] - rings["major_arcsec"] * math.sin(math.radians(6.4771))) < 0.01
        assert rings["lit"] is True and rings["sun_tilt"] < 0          # the south face, sunlit

    def test_edge_on_in_march_2025(self):
        """The Earth crossed the ring plane on 23 March 2025; the Sun was still north of it:
        for a few weeks the face seen was the unlit one."""
        before = AstroEngine.saturn_rings(AstroEngine.julian_century_j2000(datetime(2025, 3, 15)))
        after = AstroEngine.saturn_rings(AstroEngine.julian_century_j2000(datetime(2025, 3, 25)))
        assert before["tilt"] > 0 > after["tilt"] and abs(after["tilt"]) < 0.1
        assert before["lit"] is True and after["lit"] is False and after["sun_tilt"] > 0
        assert after["minor_arcsec"] < 0.1

    def test_widest_in_2032(self):
        rings = AstroEngine.saturn_rings(AstroEngine.julian_century_j2000(datetime(2032, 5, 17)))
        assert 26.9 < abs(rings["tilt"]) < 27.0


class TestNextRise:
    """The rise that follows an instant, where find_events() gives the first of the local day."""
    LAT, LON = 49.6333, -1.6167

    def test_jupiter_rises_twice_on_1_november_2026(self):
        day = AstroEngine.find_events(datetime(2026, 11, 1, 21, 30), self.LAT, self.LON, "Jupiter")
        assert day["rise"].strftime("%H:%M") == "00:00"                  # already past at 21:30
        rise = AstroEngine.next_rise(datetime(2026, 11, 1, 21, 30), self.LAT, self.LON, "Jupiter")
        assert rise.strftime("%d %H:%M") == "01 23:57"

    def test_same_as_the_day_s_rise_when_it_is_still_to_come(self):
        day = AstroEngine.find_events(datetime(2026, 11, 1, 3, 0), self.LAT, self.LON, "sun")
        rise = AstroEngine.next_rise(datetime(2026, 11, 1, 3, 0), self.LAT, self.LON, "sun")
        assert abs((rise - day["rise"]).total_seconds()) < 1

    def test_no_rise_in_the_polar_night(self):
        assert AstroEngine.next_rise(datetime(2026, 12, 21, 12, 0), 78.22, 15.65, "sun") is None
