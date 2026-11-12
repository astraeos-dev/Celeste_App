"""
tests/test_instruments.py — Instruments to print (instruments.py, prototype)
"""
import math
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import instruments  # noqa: E402

LAT = 49.6333


@pytest.mark.parametrize("alt", [0, 20, 40, 60, 80])
def test_almucantars_are_the_classic_circles(alt):
    """Centre on the meridian at cos φ / (sin φ + sin h), radius cos h / (sin φ + sin h)
    (equator radius 1, south up)."""
    plate = instruments.plate(LAT)
    x, y = plate["horizon"] if alt == 0 else plate["almucantars"][alt]
    ok = ~np.isnan(x)
    phi, h = math.radians(LAT), math.radians(alt)
    centre = math.cos(phi) / (math.sin(phi) + math.sin(h))
    radius = math.cos(h) / (math.sin(phi) + math.sin(h))
    assert ok.sum() > 50
    assert np.abs(np.hypot(x[ok], y[ok] - centre) - radius).max() < 1e-9


def test_zenith_tropics_and_edge():
    plate = instruments.plate(LAT)
    assert plate["zenith"] == pytest.approx((0.0, math.tan(math.radians(90 - LAT) / 2)))
    cancer, equator, capricorn = plate["tropics"]
    assert equator == 1.0 and cancer == pytest.approx(0.6564, abs=1e-4) and capricorn == pytest.approx(1.5235, abs=1e-4)   # tan(45° ∓ ε/2)
    for x, y in plate["azimuths"].values():
        assert np.nanmax(np.hypot(x, y)) <= plate["limit"] + 1e-9


def test_azimuth_lines_meet_at_the_zenith():
    plate = instruments.plate(LAT)
    for x, y in plate["azimuths"].values():
        assert (x[-1], y[-1]) == pytest.approx(plate["zenith"], abs=0.01)


def test_southern_plate_is_the_mirror_image():
    north, south = instruments.plate(35.0), instruments.plate(-35.0)
    assert south["zenith"] == pytest.approx(north["zenith"])
    xn, yn = north["almucantars"][30]
    xs, ys = south["almucantars"][30]
    assert np.allclose(xs, -xn, equal_nan=True) and np.allclose(ys, yn, equal_nan=True)


def test_rete():
    """The ecliptic touches the tropic of Cancer at 90° and that of Capricorn at 270°; Sirius
    (−16.7°) is on the rete, Canopus (−52.7°) is not."""
    rete = instruments.rete([("Sirius", 6.7525, -16.716), ("Canopus", 6.3992, -52.696)])
    radius = {lon: math.hypot(x, y) for lon, x, y in rete["ecliptic_ticks"]}
    plate = instruments.plate(LAT)
    assert radius[90] == pytest.approx(plate["tropics"][0], abs=1e-6)
    assert radius[270] == pytest.approx(plate["tropics"][2], abs=1e-6)
    assert [s[0] for s in rete["stars"]] == ["Sirius"]


def test_east_on_the_left_and_the_sky_turning_clockwise():
    """As on the astrolabes of old: the rising side (Oriens) on the left, the setting one
    on the right; a star an hour later (larger hour angle) has moved clockwise. The
    southern plate is the mirror image."""
    north, south = instruments.plate(LAT), instruments.plate(-LAT)
    assert north["east"][0] < 0 < north["west"][0]
    assert south["east"][0] > 0 > south["west"][0]
    x1, y1 = instruments.project(20.0, -30.0)
    x2, y2 = instruments.project(20.0, -15.0)
    assert float(x1) * float(y2) - float(y1) * float(x2) < 0     # clockwise


def test_unequal_hours_at_the_equinox():
    """At the equator (δ = 0) the night lasts 12 hours: the unequal hours are the equal
    ones, 15° apart from the setting at H = 90°."""
    plate = instruments.plate(LAT)
    for k, (x, y) in plate["unequal_hours"].items():
        mid = len(x) // 2                                   # δ = 0 in the middle of the range
        h = 90.0 + 15.0 * k
        ex, ey = instruments.project(0.0, h)
        assert (x[mid], y[mid]) == pytest.approx((float(ex), float(ey)), abs=1e-9)


def test_ecliptic_is_a_circle():
    centre, radius = instruments.ecliptic_circle()
    lon = np.linspace(0, 360, 73)
    x, y, _ra, _dec = instruments.ecliptic_point(lon)
    assert np.abs(np.hypot(x - centre[0], y - centre[1]) - radius).max() < 1e-9


def test_limb_reading_inverts_limb_angle():
    for south in (False, True):
        for hours in (0.25, 6.0, 11.9, 12.0, 15.5, 23.75):
            assert instruments.limb_reading(*instruments.limb_angle(hours, south), south) == pytest.approx(hours)
    assert instruments.limb_angle(18.0)[0] > 0                 # 18 h on the right (west), in the north


def test_shadow_square():
    assert instruments.shadow_square(45.0) == ("versa", pytest.approx(12.0))
    kind, value = instruments.shadow_square(30.0)
    assert kind == "versa" and value == pytest.approx(12 * math.tan(math.radians(30)))
    kind, value = instruments.shadow_square(60.0)
    assert kind == "recta" and value == pytest.approx(12 / math.tan(math.radians(60)))
