"""
tests/test_variables.py — The minima of Algol (variables.py, v4.18)

The ephemeris was fitted to the CCD minima of the BAV's Lichtenknecker
Database (2006–2017). It is checked against those minima, against the
BAV/Kreiner elements of 2017 and the predictions the BAV published for 2017
and 2019 (BAV Rundbrief 2016-2 and 2019-1); the light time against the
Earth's orbit; the visibility against the place.
"""
import os
import sys
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import variables  # noqa: E402
from engine import AstroEngine  # noqa: E402

ALGOL = variables.ALGOL
# Observed primary minima, HJD (CCD), Lichtenknecker Database of the BAV
OBSERVED = (2455800.48358, 2456976.0904, 2457021.9674, 2457059.2430, 2457698.6591, 2458065.6732)
CHERBOURG = (49.6333, -1.6167)


def _predicted_hjd(hjd):
    """The ephemeris' heliocentric minimum nearest to *hjd*."""
    cycle = round((hjd - ALGOL["epoch"]) / ALGOL["period"])
    return ALGOL["epoch"] + cycle * ALGOL["period"]


def _hjd(date):
    jd = AstroEngine.julian_day(date)
    return jd + float(variables.light_time_days(jd))


@pytest.mark.parametrize("hjd", OBSERVED)
def test_fits_the_observed_minima(hjd):
    assert abs(hjd - _predicted_hjd(hjd)) * 1440 < 10


def test_agrees_with_the_bav_kreiner_elements():
    """HJD 2452500.1750 + 2.8673390 E: within 10 minutes from 2025 to 2027."""
    for date in variables.minima(datetime(2025, 1, 1), datetime(2028, 1, 1))[::20]:
        hjd = _hjd(date)
        cycle = round((hjd - 2452500.1750) / 2.8673390)
        assert abs(2452500.1750 + cycle * 2.8673390 - hjd) * 1440 < 10, date


def test_published_predictions():
    """BAV/Kreiner for 11 January 2017: JD 2457764.61 (3:38 CET); the Kosmos Himmelsjahr for
    1 June 2019: 20:28 CEST. The first within a quarter of an hour, the second within the
    stated uncertainty."""
    assert abs(_predicted_hjd(2457764.61) - 2457764.61) * 1440 < 15
    (minimum,) = variables.minima(datetime(2019, 6, 1, 12), datetime(2019, 6, 2))
    assert abs((minimum - datetime(2019, 6, 1, 18, 28)).total_seconds()) / 60 < variables.UNCERTAINTY_MIN


def test_light_time_follows_the_earth():
    """At most 8.3 minutes; the Earth on Algol's side in mid-November (the Sun opposite),
    on the far side in mid-May."""
    jds = AstroEngine.julian_day(datetime(2026, 1, 1)) + np.arange(0, 366, 2)
    minutes = variables.light_time_days(jds) * 1440
    assert np.abs(minutes).max() < 8.4
    assert variables.light_time_days(AstroEngine.julian_day(datetime(2026, 11, 17))) * 1440 > 7.3
    assert variables.light_time_days(AstroEngine.julian_day(datetime(2026, 5, 17))) * 1440 < -7.3


def test_a_minimum_every_period():
    dates = variables.minima(datetime(2026, 1, 1), datetime(2027, 1, 1))
    assert len(dates) in (127, 128)
    gaps = np.diff([AstroEngine.julian_day(d) for d in dates])
    assert np.allclose(gaps, ALGOL["period"], atol=1 / 1440)          # within a minute (the light time)
    assert all(datetime(2026, 1, 1) <= d < datetime(2027, 1, 1) for d in dates)


def test_aware_dates_stay_aware():
    start = datetime(2026, 11, 1, tzinfo=timezone.utc)
    dates = variables.minima(start, start + timedelta(days=10))
    assert len(dates) in (3, 4) and all(d.tzinfo is not None for d in dates)


def test_visible_from_cherbourg():
    seen = variables.visible_minima(datetime(2026, 1, 1), datetime(2027, 1, 1), *CHERBOURG)
    assert 20 <= len(seen) <= 50
    assert all(m["alt"] >= variables.VISIBLE_ALT and m["sun"] <= variables.DARK_SUN for m in seen)
    near = next(m for m in seen if m["date"].date() == datetime(2026, 11, 10).date())
    assert near["alt"] > 75 and near["date"].hour == 0                  # 00:1x UT, near the zenith


def test_hardly_seen_from_sydney():
    """Algol culminates 15° high at 34° south: a minimum or two a year at best."""
    seen = variables.visible_minima(datetime(2026, 1, 1), datetime(2027, 1, 1), -33.87, 151.21)
    assert len(seen) <= 6 and all(m["alt"] >= variables.VISIBLE_ALT for m in seen)
