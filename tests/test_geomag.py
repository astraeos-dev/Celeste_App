"""
tests/test_geomag.py — The magnetic declination (geomag.py, World Magnetic Model 2025, v4.22)

tests/data/wmm2025_test_values.txt is the file of test values NOAA's NCEI
publishes with the model (WMM2025COF.zip): 100 places, heights and dates
from 2025.0 to 2029.5, with the field computed by the model's own software.
"""
import math
import os
import sys
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import geomag  # noqa: E402

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def _test_values():
    rows = []
    with open(os.path.join(DATA, "wmm2025_test_values.txt"), encoding="ascii") as f:
        for line in f:
            if line.strip() and not line.startswith("#"):
                v = [float(x) for x in line.split()]
                rows.append({"year": v[0], "height": v[1], "lat": v[2], "lon": v[3],
                             "D": v[4], "X": v[7], "Y": v[8], "Z": v[9]})
    return rows


VALUES = _test_values()


def test_the_file_of_test_values():
    assert len(VALUES) == 100
    assert {v["year"] for v in VALUES} == {2025.0, 2025.5, 2026.0, 2026.5, 2027.0, 2027.5,
                                          2028.0, 2028.5, 2029.0, 2029.5}


@pytest.mark.parametrize("value", VALUES, ids=lambda v: f"{v['year']}_{v['lat']:+.0f}_{v['lon']:+.0f}")
def test_the_model_s_own_values(value):
    """The field within 0.01 nT and the declination within 0.005° (printed to 0.01°)."""
    north, east, down = geomag.field(value["lat"], value["lon"], value["height"], value["year"])
    assert north == pytest.approx(value["X"], abs=0.01)
    assert east == pytest.approx(value["Y"], abs=0.01)
    assert down == pytest.approx(value["Z"], abs=0.01)
    assert math.degrees(math.atan2(east, north)) == pytest.approx(value["D"], abs=0.005)


def test_declination():
    first = VALUES[0]                                  # 89° N, 121° W: the field points nearly south-west
    when = datetime(2025, 1, 1, tzinfo=timezone.utc)
    assert geomag.declination(first["lat"], first["lon"], first["height"] * 1000, when) == pytest.approx(
        first["D"], abs=0.005)
    # November 2026: Paris 2.1° east, Seattle 14.9° east, Reykjavik 11.0° west
    now = datetime(2026, 11, 13, tzinfo=timezone.utc)
    assert geomag.declination(48.85, 2.35, 35, now) == pytest.approx(2.1, abs=0.05)
    assert geomag.declination(47.61, -122.33, 50, now) == pytest.approx(14.9, abs=0.05)
    assert geomag.declination(64.15, -21.94, 0, now) == pytest.approx(-11.0, abs=0.05)


def test_decimal_year():
    assert geomag.decimal_year(datetime(2025, 1, 1)) == 2025.0
    assert geomag.decimal_year(datetime(2025, 7, 2, 12)) == pytest.approx(2025.5, abs=1e-9)
    assert geomag.decimal_year(datetime(2028, 1, 1, tzinfo=timezone.utc)) == 2028.0
