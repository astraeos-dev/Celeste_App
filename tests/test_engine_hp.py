"""
tests/test_engine_hp.py — High-precision engine unit tests
===========================================================
Tests for VSOP87 (Sun), ELP2000 (Moon) and enriched eclipse logic
(type, diameter ratio, magnitude, duration).

Run with: pytest tests/test_engine_hp.py -v
"""

import math
import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from engine import MeeusEngine


def approx(value, expected, tol):
    return abs(value - expected) <= tol


# ===========================================================================
# 1. VSOP87 — Sun high precision
# ===========================================================================

class TestSunPositionHP:
    """Tests for sun_position_hp (VSOP87 truncated)."""

    def test_longitude_in_360(self):
        """Longitude always in [0, 360[."""
        for year in range(2000, 2030, 5):
            for m in (1, 4, 7, 10):
                t = MeeusEngine.julian_century_j2000(datetime(year, m, 15))
                l, _ = MeeusEngine.sun_position_hp(t)
                assert 0 <= l < 360, f"L={l:.3f} out of range ({year}-{m})"

    def test_distance_realistic(self):
        """Earth-Sun distance in [0.980, 1.020] AU all year."""
        for m in range(1, 13):
            t = MeeusEngine.julian_century_j2000(datetime(2024, m, 15))
            _, r = MeeusEngine.sun_position_hp(t)
            assert 0.980 < r < 1.020, f"r={r:.5f} AU out of range (month {m})"

    def test_meeus_example_25a(self):
        """
        Meeus p.165: October 13, 1992.
        VSOP87 longitude expected ~199.907°, distance ~0.9976 AU.
        """
        t = MeeusEngine.julian_century_j2000(datetime(1992, 10, 13))
        l, r = MeeusEngine.sun_position_hp(t)
        assert approx(l, 199.907, 0.5), f"L={l:.3f}° (expected ~199.907°)"
        assert approx(r, 0.9976,  0.005), f"r={r:.5f} AU"

    def test_perihelion_less_than_aphelion(self):
        """Perihelion distance (Jan) < aphelion distance (Jul)."""
        t_jan = MeeusEngine.julian_century_j2000(datetime(2024, 1, 3))
        t_jul = MeeusEngine.julian_century_j2000(datetime(2024, 7, 5))
        _, r_jan = MeeusEngine.sun_position_hp(t_jan)
        _, r_jul = MeeusEngine.sun_position_hp(t_jul)
        assert r_jan < r_jul
        assert 0.981 < r_jan < 0.987, f"Perihelion r={r_jan:.5f} AU"
        assert 1.014 < r_jul < 1.020, f"Aphelion r={r_jul:.5f} AU"

    def test_coherent_with_short_series(self):
        """HP and short series must agree within 0.1° for recent dates."""
        for year in (2020, 2024, 2025):
            for m in (3, 6, 9, 12):
                t = MeeusEngine.julian_century_j2000(datetime(year, m, 21))
                l_hp, _ = MeeusEngine.sun_position_hp(t)
                l_sc, _ = MeeusEngine.sun_position(t)
                diff = abs((l_hp - l_sc + 180) % 360 - 180)
                assert diff < 0.1, f"{year}-{m}: diff HP/SC = {diff:.4f}°"

    def test_j2000_longitude(self):
        """At J2000.0, geocentric Sun longitude ~280.46°."""
        t = MeeusEngine.julian_century_j2000(datetime(2000, 1, 1, 12))
        l, _ = MeeusEngine.sun_position_hp(t)
        assert approx(l, 280.46, 1.0), f"L J2000 = {l:.3f}°"

    def test_long_term_coherence(self):
        """Over 50 years, HP and short series within 0.5°."""
        for year in range(1980, 2030, 10):
            t = MeeusEngine.julian_century_j2000(datetime(year, 6, 21))
            l_hp, _ = MeeusEngine.sun_position_hp(t)
            l_sc, _ = MeeusEngine.sun_position(t)
            diff = abs((l_hp - l_sc + 180) % 360 - 180)
            assert diff < 0.5, f"{year}: diff = {diff:.4f}°"


# ===========================================================================
# 2. ELP2000 — Moon high precision
# ===========================================================================

class TestMoonPositionELP2000:
    """Tests for moon_position_elp2000."""

    def test_returns_4_values(self):
        """Method must return (lon, lat, dist_km, parallax)."""
        t = MeeusEngine.julian_century_j2000(datetime(2024, 3, 25))
        assert len(MeeusEngine.moon_position_elp2000(t)) == 4

    def test_longitude_in_360(self):
        """Longitude always in [0, 360[."""
        for d in range(1, 29, 4):
            t = MeeusEngine.julian_century_j2000(datetime(2024, 6, d))
            lon, _, _, _ = MeeusEngine.moon_position_elp2000(t)
            assert 0 <= lon < 360

    def test_latitude_bounded(self):
        """Ecliptic latitude in [-7, 7]°."""
        for m in range(1, 13):
            t = MeeusEngine.julian_century_j2000(datetime(2024, m, 15))
            _, lat, _, _ = MeeusEngine.moon_position_elp2000(t)
            assert -7 <= lat <= 7, f"lat={lat:.3f}° out of range"

    def test_distance_realistic(self):
        """Geocentric distance between 356 000 and 407 000 km."""
        for m in range(1, 13):
            t = MeeusEngine.julian_century_j2000(datetime(2024, m, 15))
            _, _, dist, _ = MeeusEngine.moon_position_elp2000(t)
            assert 356000 <= dist <= 407000, f"dist={dist:.0f} km out of range"

    def test_parallax_realistic(self):
        """Horizontal equatorial parallax in [0.89°, 1.02°]."""
        for m in range(1, 13):
            t = MeeusEngine.julian_century_j2000(datetime(2024, m, 15))
            _, _, _, par = MeeusEngine.moon_position_elp2000(t)
            assert 0.89 <= par <= 1.02, f"parallax={par:.4f}° out of range"

    def test_meeus_example_47a(self):
        """
        Meeus p.342 — April 12, 1992:
        longitude 133.162655°, latitude -3.229126°.
        """
        t = MeeusEngine.julian_century_j2000(datetime(1992, 4, 12))
        lon, lat, dist, par = MeeusEngine.moon_position_elp2000(t)
        # Within 0.01° (36"): a wrong sign on the 1.27° evection term shifts
        # the longitude by up to 2.5°, and the eclipse times by hours.
        assert approx(lon, 133.162655, 0.01), f"lon={lon:.4f}° (ref 133.162655°)"
        assert approx(lat, -3.229126, 0.01), f"lat={lat:.4f}° (ref -3.229126°)"
        assert 356000 <= dist <= 407000

    def test_distance_example_47a(self):
        """Meeus example distance ~368409 km, tolerance ±5000 km."""
        t = MeeusEngine.julian_century_j2000(datetime(1992, 4, 12))
        _, _, dist, _ = MeeusEngine.moon_position_elp2000(t)
        assert approx(dist, 368409, 5000), f"dist={dist:.0f} km (ref ~368409)"


# ===========================================================================
# 3. Apparent diameters
# ===========================================================================

class TestApparentDiameters:

    def test_sun_at_1au(self):
        """At 1 AU, Sun semi-diameter ≈ 0.2667°."""
        dd = MeeusEngine._sun_semi_diameter(1.0)
        assert approx(dd, 0.2667, 0.002), f"dd_sun(1AU)={dd:.4f}°"

    def test_sun_larger_at_perihelion(self):
        """At perihelion (0.983 AU), Sun semi-diameter > 1 AU value."""
        assert MeeusEngine._sun_semi_diameter(0.983) > MeeusEngine._sun_semi_diameter(1.0)

    def test_moon_at_mean_distance(self):
        """At mean distance (~384 400 km), Moon semi-diameter ≈ 0.259°."""
        dd = MeeusEngine._moon_semi_diameter(384400.0)
        assert approx(dd, 0.259, 0.003), f"dd_moon(384400km)={dd:.4f}°"

    def test_moon_larger_at_perigee(self):
        """At perigee (~356 500 km), Moon semi-diameter > mean value."""
        assert MeeusEngine._moon_semi_diameter(356500) > MeeusEngine._moon_semi_diameter(384400)

    def test_diameter_ratio_physical_range(self):
        """Diameter ratio Moon/Sun must be in [0.88, 1.08] (physical)."""
        for m in range(1, 13):
            t = MeeusEngine.julian_century_j2000(datetime(2024, m, 15))
            _, _, dist, _ = MeeusEngine.moon_position_elp2000(t)
            _, r_sun      = MeeusEngine.sun_position_hp(t)
            ratio = MeeusEngine._moon_semi_diameter(dist) / MeeusEngine._sun_semi_diameter(r_sun)
            assert 0.88 <= ratio <= 1.08, f"ratio={ratio:.4f} out of range (month {m})"


# ===========================================================================
# 4. Eclipse magnitude and duration
# ===========================================================================

class TestMagnitudeAndDuration:

    def test_magnitude_central_eclipse(self):
        """Central eclipse (gamma=0) should have magnitude > 1."""
        assert MeeusEngine._eclipse_magnitude(0.005, 0.0) > 1.0

    def test_magnitude_partial_eclipse(self):
        """Large gamma → partial eclipse → magnitude < 1."""
        assert MeeusEngine._eclipse_magnitude(0.005, 0.95) < 1.0

    def test_duration_positive_for_central(self):
        """Central eclipse should have positive duration."""
        d = MeeusEngine._totality_duration(0.005, 0.0)
        assert d is not None and d > 0

    def test_duration_none_if_no_central_phase(self):
        """Large discriminant → None."""
        assert MeeusEngine._totality_duration(0.5, 0.95) is None

    def test_duration_plausible_range(self):
        """Typical eclipse duration should be in [1, 480] minutes."""
        d = MeeusEngine._totality_duration(0.005, 0.1)
        assert d is not None and 1 <= d <= 480


# ===========================================================================
# 5. find_eclipses — high precision
# ===========================================================================

class TestFindEclipsesHP:

    def test_returns_list(self):
        res = MeeusEngine.find_eclipses(datetime(2024, 1, 1), num_months=3)
        assert isinstance(res, list)

    def test_solar_structure_has_new_fields(self):
        """Solar eclipses must have sub_type, diameter_ratio, magnitude, duration_min."""
        res = MeeusEngine.find_eclipses(datetime(2024, 1, 1), num_months=12)
        solar = [r for r in res if r['type'] == 'solar']
        for r in solar:
            for key in ('sub_type', 'diameter_ratio', 'magnitude', 'duration_min'):
                assert key in r, f"Missing key: {key}"
            assert r['sub_type'] in ('total', 'annular', 'hybrid', 'partial')

    def test_sub_type_coherent_with_ratio(self):
        """sub_type must be coherent with diameter_ratio."""
        res = MeeusEngine.find_eclipses(datetime(2020, 1, 1), num_months=24)
        for r in [r for r in res if r['type'] == 'solar']:
            ratio = r['diameter_ratio']
            st    = r['sub_type']
            if ratio > 1.005:
                assert st == 'total',    f"ratio={ratio:.4f} but sub_type={st}"
            elif ratio < 0.990:
                assert st == 'annular',  f"ratio={ratio:.4f} but sub_type={st}"

    def test_2024_solar_eclipses(self):
        """2024 must have ≥ 2 solar eclipses (total + annular known)."""
        res    = MeeusEngine.find_eclipses(datetime(2024, 1, 1), num_months=12)
        solar  = [r for r in res if r['type'] == 'solar']
        assert len(solar) >= 2, f"Only {len(solar)} solar eclipse(s)"
        types  = [r['sub_type'] for r in solar]
        assert 'total' in types or 'annular' in types, f"Types found: {types}"

    def test_magnitude_positive(self):
        """Magnitude must be > 0 for all detected eclipses."""
        res = MeeusEngine.find_eclipses(datetime(2024, 1, 1), num_months=12)
        for r in res:
            if r['type'] == 'solar' and r['magnitude'] is not None:
                assert r['magnitude'] > 0

    def test_duration_only_for_central_eclipses(self):
        """Partial eclipses must have duration_min = None."""
        res = MeeusEngine.find_eclipses(datetime(2020, 1, 1), num_months=36)
        for r in [r for r in res if r['type'] == 'solar']:
            if r['sub_type'] == 'partial':
                assert r['duration_min'] is None

    def test_diameter_ratio_physical(self):
        """Diameter ratio must be in [0.88, 1.08]."""
        res = MeeusEngine.find_eclipses(datetime(2020, 1, 1), num_months=36)
        for r in [r for r in res if r['type'] == 'solar']:
            assert 0.88 <= r['diameter_ratio'] <= 1.08

    def test_results_sorted_by_date(self):
        """Results must be sorted chronologically."""
        res = MeeusEngine.find_eclipses(datetime(2024, 1, 1), num_months=12)
        for i in range(len(res)-1):
            assert res[i]['date'] <= res[i+1]['date']

    def test_moon_latitude_within_threshold(self):
        """All detected eclipses must have |moon_latitude| < 1.58°."""
        res = MeeusEngine.find_eclipses(datetime(2024, 1, 1), num_months=12)
        for r in res:
            assert abs(r['moon_latitude']) < 1.58

    def test_plausible_count(self):
        """Between 2 and 8 eclipses over 12 months."""
        res = MeeusEngine.find_eclipses(datetime(2024, 1, 1), num_months=12)
        assert 2 <= len(res) <= 8

    def test_syzygy_hp_phase_near_zero(self):
        """HP syzygy finder must find phase very close to 0°."""
        dte = datetime(2024, 4, 8)  # close to April 2024 new moon
        nl  = MeeusEngine._find_syzygy_hp(dte, target_phase=0)
        t_  = MeeusEngine.julian_century_j2000(nl)
        s_l, _     = MeeusEngine.sun_position_hp(t_)
        m_l,_,_,_  = MeeusEngine.moon_position_elp2000(t_)
        phase = MeeusEngine.mod360(m_l - s_l)
        diff  = min(abs(phase), 360 - abs(phase))
        assert diff < 5.0, f"HP syzygy phase not near 0: {diff:.2f}°"
