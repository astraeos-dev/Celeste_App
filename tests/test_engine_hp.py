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

from datetime import date, datetime, timedelta, timezone
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
        # Reproduced to the last digit. A wrong sign on the 1.27° evection term
        # once put the longitude 1.7° off here, and terms counted twice the
        # latitude 0.006° off.
        assert approx(lon, 133.162655, 1e-4), f"lon={lon:.6f}° (ref 133.162655°)"
        assert approx(lat, -3.229126, 1e-4), f"lat={lat:.6f}° (ref -3.229126°)"
        assert approx(par, 0.991990, 1e-5), f"parallax={par:.6f}° (ref 0.991990°)"

    def test_distance_example_47a(self):
        """Meeus example distance: 368409.7 km."""
        t = MeeusEngine.julian_century_j2000(datetime(1992, 4, 12))
        _, _, dist, _ = MeeusEngine.moon_position_elp2000(t)
        # Misaligned Table 47.A coefficients once put it 9 km off, and
        # terms counted twice 16 km off.
        assert approx(dist, 368409.7, 0.5), f"dist={dist:.1f} km (ref 368409.7)"

    def test_same_series_as_moon_position(self):
        """moon_position() is moon_position_elp2000() without the distance."""
        for m in range(1, 13):
            t = MeeusEngine.julian_century_j2000(datetime(2024, m, 15))
            lon, lat, _, par = MeeusEngine.moon_position_elp2000(t)
            assert MeeusEngine.moon_position(t) == (lon, lat, par)


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
# 4. Solar eclipse circumstances (shadow geometry)
# ===========================================================================

# NASA, Five Millennium Canon of Solar Eclipses (Espenak & Meeus), at
# greatest eclipse: date, type, γ, magnitude, central phase duration (s)
NASA_CENTRAL = [
    ((2009, 7, 22),  'total',    0.0698, 1.0799, 399),
    ((2010, 1, 15),  'annular',  0.4002, 0.9190, 668),
    ((2017, 8, 21),  'total',    0.4367, 1.0306, 160),
    ((2021, 12, 4),  'total',   -0.9526, 1.0367, 114),
    ((2023, 4, 20),  'hybrid',  -0.3952, 1.0132,  76),
    ((2024, 4, 8),   'total',    0.3431, 1.0566, 268),
    ((2024, 10, 2),  'annular', -0.3509, 0.9326, 445),
    ((2027, 2, 6),   'annular', -0.2951, 0.9281, 471),
    ((2027, 8, 2),   'total',    0.1421, 1.0790, 383),
]
NASA_PARTIAL = [            # date, γ, magnitude
    ((2022, 4, 30), -1.1901, 0.6396),
    ((2025, 3, 29),  1.0405, 0.9376),
]


def _solar_eclipse_near(year, month, day):
    """_solar_eclipse() for the true new moon nearest to the given date."""
    nm = MeeusEngine._find_syzygy_hp(datetime(year, month, day), target_phase=0)
    return MeeusEngine._solar_eclipse(MeeusEngine.julian_day(nm))


class TestSolarEclipseCircumstances:
    """_solar_eclipse() against published values."""

    @pytest.mark.parametrize("ymd, sub_type, gamma, mag, seconds", NASA_CENTRAL)
    def test_central_eclipse(self, ymd, sub_type, gamma, mag, seconds):
        ec = _solar_eclipse_near(*ymd)
        assert ec is not None, "eclipse not found"
        assert ec['sub_type'] == sub_type
        assert ec['certainty'] == 'certain'
        assert approx(ec['gamma'], gamma, 0.003), f"γ = {ec['gamma']:+.4f} (NASA {gamma:+.4f})"
        assert approx(ec['magnitude'], mag, 0.001), f"magnitude {ec['magnitude']:.4f} (NASA {mag})"
        # 5 %, or the 0.1 min rounding for the shortest ones
        assert approx(ec['duration_min'] * 60, seconds, max(0.05 * seconds, 6)), \
            f"central phase {ec['duration_min']} min (NASA {seconds} s)"

    @pytest.mark.parametrize("ymd, gamma, mag", NASA_PARTIAL)
    def test_partial_eclipse(self, ymd, gamma, mag):
        ec = _solar_eclipse_near(*ymd)
        assert ec is not None, "eclipse not found"
        assert ec['sub_type'] == 'partial'
        assert ec['duration_min'] is None
        assert approx(ec['gamma'], gamma, 0.003), f"γ = {ec['gamma']:+.4f} (NASA {gamma:+.4f})"
        assert approx(ec['magnitude'], mag, 0.005), f"magnitude {ec['magnitude']:.4f} (NASA {mag})"

    def test_greatest_eclipse_time(self):
        """2027-08-02: greatest eclipse at 10:07:50 TD (the engine ignores ΔT ≈ 70 s)."""
        ec = _solar_eclipse_near(2027, 8, 2)
        nasa = MeeusEngine.julian_day(datetime(2027, 8, 2, 10, 7, 50))
        assert abs(ec['jd'] - nasa) * 1440 < 1, "greatest eclipse more than 1 min off"

    def test_no_eclipse_far_from_node(self):
        """New moon of 2026-11-09: Moon ~4.9° south of the ecliptic."""
        assert _solar_eclipse_near(2026, 11, 9) is None

    def test_central_phase_within_physical_limits(self):
        """
        Every central eclipse of 2001–2030 lasts less than 15 min: at most
        ~7.5 min when total, ~12.5 min when annular. The formula used before
        (a lunar-eclipse formula) gave 170–200 min.
        """
        res = MeeusEngine.find_eclipses(datetime(2001, 1, 1), num_months=371)
        central = [r for r in res if r['type'] == 'solar' and r['duration_min'] is not None]
        assert len(central) >= 40, f"only {len(central)} central eclipses in 30 years"
        for r in central:
            d, st = r['duration_min'], r['sub_type']
            assert 0 < d < 15, f"{r['date']:%Y-%m-%d} {st}: {d} min"
            limit = 7.6 if st == 'total' else 12.6
            assert d < limit, f"{r['date']:%Y-%m-%d} {st}: {d} min"


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
        assert _phase_offset(nl, 0) < 0.01, f"HP syzygy phase not near 0: {_phase_offset(nl, 0):.4f}°"


def _phase_offset(dte, target):
    """|Moon − Sun longitude − target| at dte (VSOP87 + ELP2000), degrees."""
    t = MeeusEngine.julian_century_j2000(dte)
    s_l, _ = MeeusEngine.sun_position_hp(t)
    m_l, _, _, _ = MeeusEngine.moon_position_elp2000(t)
    return abs((m_l - s_l - target + 180.0) % 360.0 - 180.0)


# ===========================================================================
# 6. New and full moons, whatever the date a search starts from
# ===========================================================================

class TestSyzygies:
    """
    The syzygy finders used to scan only ±48 h around their first guess:
    from a date far from a new moon they returned the edge of that window.
    """

    START = datetime(2026, 11, 1, 21, 0)   # 7.4 days before the next new moon

    @pytest.mark.parametrize("finder", ["_find_syzygy", "_find_syzygy_hp"])
    def test_new_moon_far_from_the_guess(self, finder):
        """New moon of 2026-11-09 07:02 UT (both series)."""
        nm = getattr(MeeusEngine, finder)(self.START, target_phase=0)
        assert abs(nm - datetime(2026, 11, 9, 7, 2)) < timedelta(minutes=5), nm

    @pytest.mark.parametrize("finder", ["_find_syzygy", "_find_syzygy_hp"])
    def test_full_moon_far_from_the_guess(self, finder):
        """Nearest full moon: 2026-10-26 04:12 UT, 6.7 days earlier (both series)."""
        fm = getattr(MeeusEngine, finder)(self.START, target_phase=180)
        assert abs(fm - datetime(2026, 10, 26, 4, 12)) < timedelta(minutes=5), fm

    def test_first_syzygies_at_or_after_start(self):
        """_syzygies_from() starts with the first new / full moon at or after the start."""
        jd_start = MeeusEngine.julian_day(self.START)
        new_moons  = MeeusEngine._syzygies_from(jd_start, 0.0, 13)
        full_moons = MeeusEngine._syzygies_from(jd_start, 0.5, 13)
        assert MeeusEngine._jd_to_datetime(new_moons[0], self.START).date() == date(2026, 11, 9)
        assert MeeusEngine._jd_to_datetime(full_moons[0], self.START).date() == date(2026, 11, 24)
        for jds in (new_moons, full_moons):
            gaps = [b - a for a, b in zip(jds, jds[1:])]
            assert all(29.2 < g < 29.9 for g in gaps), gaps   # one lunation apart

    def test_start_between_mean_and_true_new_moon(self):
        """
        The mean new moon of February 2027 falls at 08:16, the true one at
        ~15:58: a search starting in between keeps that eclipse, one starting
        after it does not.
        """
        before = MeeusEngine.find_eclipses(datetime(2027, 2, 6, 15, 0), num_months=1)
        after  = MeeusEngine.find_eclipses(datetime(2027, 2, 6, 17, 0), num_months=1)
        assert [r['date'].date() for r in before if r['type'] == 'solar'] == [date(2027, 2, 6)]
        assert not [r for r in after if r['type'] == 'solar']


# ===========================================================================
# 7. Regression: 12-month search from 2026-11-01
# ===========================================================================

NOV_2026 = datetime(2026, 11, 1, 21, 0)


@pytest.fixture(scope="module")
def eclipses():
    """find_eclipses() over 12 lunations from 2026-11-01 21:00 UT."""
    return MeeusEngine.find_eclipses(NOV_2026, num_months=12)


class TestEclipseSearchFromNovember2026:
    """
    find_eclipses() guessed the i-th new moon at dte_start + i × 29.53 days.
    From 2026-11-01 21:00 UT it reported an annular eclipse on 2026-11-03,
    eclipses on 2027-04-15 and 2027-04-30 that do not exist, missed those
    of February and August 2027, and gave central phases of 170–200 min.
    """

    START = NOV_2026

    @staticmethod
    def _solar_near(eclipses, when):
        """Solar eclipses within a few hours of `when`."""
        return [r for r in eclipses
                if r['type'] == 'solar' and abs(r['date'] - when) < timedelta(hours=3)]

    def test_annular_eclipse_of_6_february_2027(self, eclipses):
        """New moon 2027-02-06 15:56 UT, annular eclipse (magnitude 0.928)."""
        found = self._solar_near(eclipses, datetime(2027, 2, 6, 15, 56))
        assert len(found) == 1, [r['details'] for r in eclipses]
        assert found[0]['sub_type'] == 'annular'
        assert approx(found[0]['magnitude'], 0.928, 0.005)

    def test_total_eclipse_of_2_august_2027(self, eclipses):
        """New moon 2027-08-02 10:05 UT, total eclipse (magnitude 1.079)."""
        found = self._solar_near(eclipses, datetime(2027, 8, 2, 10, 5))
        assert len(found) == 1, [r['details'] for r in eclipses]
        assert found[0]['sub_type'] == 'total'
        assert approx(found[0]['magnitude'], 1.079, 0.005)

    def test_no_solar_eclipse_in_november_2026(self, eclipses):
        assert not [r for r in eclipses
                    if r['type'] == 'solar' and (r['date'].year, r['date'].month) == (2026, 11)]

    def test_exactly_the_eclipses_of_the_period(self, eclipses):
        """2 solar and 3 (penumbral) lunar eclipses from November 2026 to October 2027."""
        solar = [r['date'].date() for r in eclipses if r['type'] == 'solar']
        lunar = [r['date'].date() for r in eclipses if r['type'] == 'lunar']
        assert solar == [date(2027, 2, 6), date(2027, 8, 2)]
        assert lunar == [date(2027, 2, 20), date(2027, 7, 18), date(2027, 8, 17)]

    def test_dates_are_true_syzygies(self, eclipses):
        """Each date is a new moon (solar) or full moon (lunar), not a window edge."""
        for r in eclipses:
            target = 0 if r['type'] == 'solar' else 180
            assert _phase_offset(r['date'], target) < 0.01, r['details']

    def test_nothing_before_start(self, eclipses):
        assert all(r['date'] >= self.START for r in eclipses)

    def test_central_durations_below_15_min(self, eclipses):
        durations = {r['date'].date(): r['duration_min'] for r in eclipses
                     if r['type'] == 'solar'}
        assert all(d is not None and 0 < d < 15 for d in durations.values()), durations
        # NASA: 7 min 51 s and 6 min 23 s
        assert approx(durations[date(2027, 2, 6)], 7.85, 0.3)
        assert approx(durations[date(2027, 8, 2)], 6.38, 0.3)

    def test_timezone_kept(self, eclipses):
        """An aware start date gives aware dates, at the same instants."""
        aware = MeeusEngine.find_eclipses(self.START.replace(tzinfo=timezone.utc), num_months=12)
        assert [r['date'] for r in aware] == [r['date'].replace(tzinfo=timezone.utc)
                                              for r in eclipses]
