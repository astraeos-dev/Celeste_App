"""
tests/test_workshop.py — The Workshop: planisphere and sundials (instruments.py, workshop.py)
=============================================================================================
The geometry against the classic formulas, then against the sky of the engine:
the shadow of the real Sun falls on the dial's line for the reading computed
from the legal time; the planisphere's date ring gives the sidereal time and
Vega sits in the window where the engine puts it.
"""
import math
import os
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import i18n  # noqa: E402
import instruments  # noqa: E402
import workshop  # noqa: E402
from engine import AstroEngine, _sky  # noqa: E402

CHERBOURG = (49.6333, -1.6167, 1.0)
SYDNEY = (-33.87, 151.21, 10.0)


def _sun_vector(ut, lat, lon):
    """Unit vector (east, north, up) towards the Sun, from the engine (DE440)."""
    alt, az = AstroEngine.horizontal(AstroEngine.julian_century_j2000(ut), lat, lon, "sun")
    a, h = math.radians(float(az)), math.radians(float(alt))
    return np.array([math.sin(a) * math.cos(h), math.cos(a) * math.cos(h), math.sin(h)])


def _reading(ut, std_offset, dst):
    """What a dial corrected for the longitude shows at *ut*."""
    legal = (ut.hour + ut.minute / 60 + std_offset + dst) % 24
    eot = AstroEngine.equation_of_time(AstroEngine.julian_century_j2000(ut))
    return instruments.dial_reading(legal, dst, eot)


# ── Sundials: closed formulas ─────────────────────────────────────────────────

@pytest.mark.parametrize("lat", [20.0, 45.0, 49.6333, 65.0, -33.87])
def test_horizontal_hour_lines_follow_tan_theta_sin_phi_tan_h(lat):
    """tan θ = sin φ · tan H, θ the angle of the line from the noon line, towards
    the east in the afternoon on both sides of the equator (the shadow is opposite
    the Sun, which is in the west)."""
    dial = instruments.horizontal_dial(lat, 0.0, 0.0, 30.0, hours=[8.0, 9.5, 11.0, 12.0, 13.0, 15.5, 17.0])
    for hour, (dx, dy) in dial["hour_lines"].items():
        h = math.radians(instruments.dial_hour_angle(hour, 0.0, 0.0))
        theta = math.atan2(dx, dy if lat > 0 else -dy)
        expected = math.atan(math.sin(math.radians(abs(lat))) * math.tan(h))
        assert theta == pytest.approx(expected, abs=1e-9)


def test_horizontal_noon_line_is_shifted_by_the_longitude():
    """At Cherbourg (1.62° W, UTC+1) solar noon comes at 13:06 standard time: the
    meridian is between the 13:00 and 13:30 lines, and 12:00 points west of north."""
    lat, lon, off = CHERBOURG
    noon = 12.0 + off - lon / 15.0
    dial = instruments.horizontal_dial(lat, lon, off, 30.0, hours=[12.0, noon])
    assert dial["hour_lines"][noon][0] == pytest.approx(0.0, abs=1e-9)
    assert dial["hour_lines"][12.0][0] < 0


def test_horizontal_nodus_and_equinox_line():
    """The nodus at height h stands h / tan φ north of the foot; at the equinox its
    shadow runs on the straight line y = h / (sin φ cos φ)."""
    lat, h = 49.6333, 30.0
    dial = instruments.horizontal_dial(lat, 0.0, 0.0, h)
    phi = math.radians(lat)
    assert dial["nodus"][1] == pytest.approx(h / math.tan(phi))
    assert dial["style_length"] == pytest.approx(h / math.sin(phi))
    x, y = dial["date_lines"][0.0]
    ok = np.isfinite(y)
    assert np.abs(y[ok] - h / (math.sin(phi) * math.cos(phi))).max() < 1e-9
    # the June curve is nearer the foot at noon than the December one
    jx, jy = dial["date_lines"][instruments.OBLIQUITY]
    dx, dy = dial["date_lines"][-instruments.OBLIQUITY]
    assert np.nanmin(np.abs(jy)) < np.nanmin(np.abs(dy))


def test_equatorial_dial_is_tilted_to_the_colatitude():
    dial = instruments.equatorial_dial(49.6333, -1.6167, 1.0)
    assert dial["tilt"] == pytest.approx(40.3667)
    assert dial["rod"] == pytest.approx(49.6333)
    assert dial["hour_angles"][14.0] - dial["hour_angles"][13.0] == pytest.approx(15.0)
    assert dial["summer"][6.0] and not dial["summer"][2.0]
    assert dial["winter"][12.0] and not dial["winter"][20.0]


# ── Sundials: the real Sun of the engine ──────────────────────────────────────

MOMENTS = [datetime(2026, 7, 10, 13, 0), datetime(2026, 11, 12, 8, 30),
           datetime(2026, 3, 1, 15, 0), datetime(2026, 12, 21, 11, 45)]
# by day in Sydney: 10:00 UT is 20:00 or 21:00 there, so the same moments a few hours earlier
SOUTH = [datetime(2026, 7, 10, 1, 0), datetime(2026, 11, 12, 22, 30),
         datetime(2026, 3, 1, 4, 0), datetime(2026, 12, 21, 23, 45)]
CASES = [(CHERBOURG, ut) for ut in MOMENTS] + [(SYDNEY, ut) for ut in SOUTH]
CASE_IDS = [f"{'north' if site[0] > 0 else 'south'}-{ut:%m-%d}" for site, ut in CASES]


@pytest.mark.parametrize("site, ut", CASES, ids=CASE_IDS)
def test_shadow_of_the_real_sun_falls_on_the_horizontal_line(site, ut):
    lat, lon, off = site
    zone = ZoneInfo("Europe/Paris" if lat > 0 else "Australia/Sydney")
    v = _sun_vector(ut, lat, lon)
    if v[2] < 0.05:
        pytest.skip("the Sun is down or too low")
    dst = (ut.replace(tzinfo=ZoneInfo("UTC")).astimezone(zone).dst() or timedelta(0)).total_seconds() / 3600
    reading = _reading(ut, off, dst)
    line = instruments.horizontal_dial(lat, lon, off, 30.0, hours=[reading])["hour_lines"][reading]
    phi = math.radians(abs(lat))
    pole = np.array([0.0, math.copysign(math.cos(phi), lat), math.sin(phi)])
    shadow = pole[:2] - pole[2] / v[2] * v[:2]
    shadow /= np.hypot(*shadow)
    assert np.allclose(line, shadow, atol=2e-4)       # well under a minute of time


@pytest.mark.parametrize("site, ut", CASES, ids=CASE_IDS)
def test_equatorial_dial_reads_the_suns_hour_angle(site, ut):
    lat, lon, off = site
    zone = ZoneInfo("Europe/Paris" if lat > 0 else "Australia/Sydney")
    v = _sun_vector(ut, lat, lon)
    if v[2] < 0.05:
        pytest.skip("the Sun is down or too low")
    phi = math.radians(lat)
    meridian = np.array([0.0, -math.sin(phi), math.cos(phi)])       # equator plane, towards H = 0
    sun_h = math.degrees(math.atan2(-v[0], v @ meridian))
    dst = (ut.replace(tzinfo=ZoneInfo("UTC")).astimezone(zone).dst() or timedelta(0)).total_seconds() / 3600
    reading = _reading(ut, off, dst)
    assert instruments.dial_hour_angle(reading, lon, off) == pytest.approx(sun_h, abs=0.02)


def test_equation_of_time_table():
    """Early November the Sun is about 16 min fast, mid-February 14 min slow."""
    table = {(m, d): e for m, d, e in workshop.equation_of_time_table(2026)}
    assert len(table) == 36
    assert table[(11, 1)] == pytest.approx(16.4, abs=0.3)
    assert table[(2, 11)] == pytest.approx(-14.2, abs=0.3)
    assert abs(table[(4, 11)]) < 1.5 and abs(table[(6, 11)]) < 1.5


# ── Planisphere ───────────────────────────────────────────────────────────────

def _geo(lat, lon, off, year=2026):
    import charts
    stars = [("Vega", 18.615639, 38.78361, 0.03), ("Sirius", 6.752472, -16.71611, -1.46)]
    return instruments.planisphere(lat, lon, off, year, 72.0, stars, charts.constellation_figures())


@pytest.mark.parametrize("site", [CHERBOURG, SYDNEY], ids=["north", "south"])
def test_planisphere_date_ring_gives_the_sidereal_time(site):
    """Date mark + standard time × sidereal rate = local sidereal time, within 20 s."""
    lat, lon, off = site
    geo = _geo(lat, lon, off)
    ts = _sky()["ts"]
    for month, day, lst0 in geo["date_ticks"][::37]:
        for hour in (0.0, 5.5, 21.0):
            ut = datetime(2026, month, day) + timedelta(hours=hour - off)
            lst = (float(ts.ut1_jd(AstroEngine.julian_day(ut)).gmst) + lon / 15) % 24
            got = (lst0 + hour * instruments.SIDEREAL_RATE) % 24
            assert abs((got - lst + 12) % 24 - 12) * 3600 < 20


@pytest.mark.parametrize("site", [CHERBOURG, SYDNEY], ids=["north", "south"])
def test_planisphere_shows_vega_where_the_engine_puts_it(site):
    """The disc set for a moment puts Vega on the mask's point of its altitude and
    azimuth, within 1 mm (the stars are J2000: precession moves them by 0.37°)."""
    lat, lon, off = site
    geo = _geo(lat, lon, off)
    ut = datetime(2026, 11, 12, 18, 30)
    tc = AstroEngine.julian_century_j2000(ut)
    lst = (float(_sky()["ts"].ut1_jd(AstroEngine.julian_day(ut)).gmst) + lon / 15) % 24
    vx, vy = instruments.planisphere_xy(18.615639, 38.78361, lst, lat, 72.0, geo["dec_edge"])
    alt, az = AstroEngine.stars_horizontal(tc, lat, lon, [18.615639], [38.78361])
    dec, h = instruments.equatorial(np.asarray(alt, float), np.asarray(az, float), lat)
    mx, my = instruments.planisphere_xy(-h / 15.0, dec, 0.0, lat, 72.0, geo["dec_edge"])
    assert math.hypot(float(vx) - float(mx[0]), float(vy) - float(my[0])) < 1.0


@pytest.mark.parametrize("site", [CHERBOURG, SYDNEY], ids=["north", "south"])
def test_planisphere_window(site):
    """The window holds the pole and the zenith, stays inside the star field, and
    reaches the edge's declination minus the margin at the bottom (the meridian)."""
    lat, lon, off = site
    geo = _geo(lat, lon, off)
    x, y = geo["horizon"]
    r = np.hypot(x, y)
    assert r.max() < 72.0
    phi = abs(lat)
    assert r.max() == pytest.approx(72.0 * (180 - phi) / (188 - phi), rel=1e-6)
    assert abs(x[np.argmax(r)]) < 1.0 and y[np.argmax(r)] < 0          # at the bottom
    assert geo["zenith"][1] < 0
    zr = math.hypot(*geo["zenith"])
    assert zr == pytest.approx(72.0 * (90 - abs(lat)) / (180 - abs(lat) + 8))
    north = [c for c in geo["cardinals"] if c[0] == 0][0]
    assert (north[2] > 0) == (lat > 0)                 # the visible pole's side at the top


# ── The PDF files ─────────────────────────────────────────────────────────────

def test_place_standard_offset_and_summer_time():
    when = datetime(2026, 7, 1)
    paris = workshop.Place("", 48.85, 2.35, ZoneInfo("Europe/Paris"), when)
    tokyo = workshop.Place("", 35.68, 139.69, ZoneInfo("Asia/Tokyo"), when)
    sydney = workshop.Place("", -33.87, 151.21, ZoneInfo("Australia/Sydney"), when)
    assert (paris.std_offset, paris.has_dst) == (1.0, True)
    assert (tokyo.std_offset, tokyo.has_dst) == (9.0, False)
    assert (sydney.std_offset, sydney.has_dst) == (10.0, True)
    assert paris.dst_hours(datetime(2026, 7, 1, 12)) == 1.0
    assert paris.dst_hours(datetime(2026, 1, 1, 12)) == 0.0


@pytest.mark.parametrize("lang", ["fr", "en", "es", "de"])
@pytest.mark.parametrize("kind", workshop.INSTRUMENTS)
def test_instrument_pdf_in_every_language(tmp_path, lang, kind):
    """Each instrument is printed with its explanations, no key left untranslated."""
    i18n.switch_lang(lang)
    try:
        place = workshop.Place("Cherbourg", *CHERBOURG[:2], ZoneInfo("Europe/Paris"), datetime(2026, 11, 12, 20))
        pages = workshop.instrument_pages(kind, place)
        texts = [txt.get_text() for fig in pages.figures for ax in fig.axes for txt in ax.texts]
        assert not [txt for txt in texts if "[" in txt and "workshop." in txt]
        assert len(pages.figures) >= 3
        path = tmp_path / f"{kind}.pdf"
        assert workshop.print_instrument(kind, str(path), place) == len(pages.figures)
        assert path.read_bytes()[:5] == b"%PDF-"
    finally:
        i18n.switch_lang("fr")


def test_pages_are_at_true_scale():
    place = workshop.Place("", -33.87, 151.21, ZoneInfo("Australia/Sydney"), datetime(2026, 11, 12))
    for paper, (w, h) in workshop.PAPERS.items():
        fig = workshop.instrument_pages("horizontal_dial", place, paper).figures[0]
        assert fig.get_size_inches() * 25.4 == pytest.approx((w, h))
        ax = fig.axes[0]
        assert ax.get_xlim() == (0, w) and ax.get_ylim() == (0, h)


def test_preview_png():
    place = workshop.Place("", 49.63, -1.62, ZoneInfo("Europe/Paris"), datetime(2026, 11, 12))
    png, count = workshop.preview_png("equatorial_dial", place, page=1, dpi=30)
    assert png[:8] == b"\x89PNG\r\n\x1a\n" and count >= 3
