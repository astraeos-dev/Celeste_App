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


# ── Astrolabe ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("site", [CHERBOURG, SYDNEY], ids=["north", "south"])
def test_astrolabe_puts_vega_on_its_almucantar(site):
    """The rete turned to the local sidereal time puts Vega, brought to the date, on the
    point of the plate of its altitude and azimuth (engine), within 0.1 mm on a 150 mm plate."""
    lat, lon, off = site
    south = lat < 0
    ut = datetime(2026, 11, 12, 18, 30)
    (name, ra, dec, _mag), = workshop.stars_of_date([("Vega", 18.615639, 38.78361, 0.03)], 2026)
    lst = (float(_sky()["ts"].ut1_jd(AstroEngine.julian_day(ut)).gmst) + lon / 15) % 24
    x, y = instruments.project(dec, 15.0 * (lst - ra), south)
    rx, ry = instruments.turn(*instruments.project(dec, -15.0 * ra, south), lst, south)  # the rete, turned
    assert (float(rx), float(ry)) == pytest.approx((float(x), float(y)), abs=1e-9)
    alt, az = AstroEngine.stars_horizontal(AstroEngine.julian_century_j2000(ut), lat, lon, [18.615639], [38.78361])
    d, h = instruments.equatorial(np.asarray(alt, float), np.asarray(az, float), lat)
    px, py = instruments.project(d, h, south)
    scale = 75.0 / instruments.plate(lat)["limit"]
    assert math.hypot(float(px[0]) - float(x), float(py[0]) - float(y)) * scale < 0.1


@pytest.mark.parametrize("site, ut", CASES, ids=CASE_IDS)
def test_astrolabe_reads_the_apparent_solar_time(site, ut):
    """The Sun set on its almucantar (altitude from the engine, on the side of its
    azimuth) and the rule laid over it: the limb reads the apparent solar time, UT +
    longitude + equation of time, within a minute."""
    lat, lon, _off = site
    south = lat < 0
    tc = AstroEngine.julian_century_j2000(ut)
    alt, az = AstroEngine.horizontal(tc, lat, lon, "sun")
    if float(alt) < 3:
        pytest.skip("the Sun is down or too low")
    lam, _dist = AstroEngine.sun_position(tc)
    _x, _y, _ra, dec = instruments.ecliptic_point(float(lam))
    h = float(instruments.hour_angle_at_altitude(float(alt), float(dec), lat))
    h = h if float(az) > 180 else -h                          # west in the afternoon
    x, y = instruments.project(float(dec), h, south)
    reading = instruments.limb_reading(float(x), float(y), south)
    expected = (ut.hour + ut.minute / 60 + lon / 15 + AstroEngine.equation_of_time(tc) / 60) % 24
    assert abs((reading - expected + 12) % 24 - 12) * 60 < 1.0


def test_back_calendar_follows_the_sun():
    """The calendar ring: about 0° on 20 March (the equinox of 2026), 90° on 21 June."""
    lons = {(m, d): lon for m, d, lon in instruments.solar_longitudes(2026)}
    assert len(lons) == 365
    assert lons[(3, 20)] == pytest.approx(359.5, abs=1.0) or lons[(3, 20)] < 1.0
    assert lons[(6, 21)] == pytest.approx(90.0, abs=1.0)
    assert float(instruments.back_angle(90.0)) == pytest.approx(90.0)        # June at the top
    assert float(instruments.back_angle(0.0)) == pytest.approx(180.0)        # the equinox on the left


# ── Nocturnal ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("key, star", [("great_bear", ("Dubhe", 11.062130, 61.75103)),
                                        ("little_bear", ("Kochab", 14.845092, 74.15550))])
@pytest.mark.parametrize("ut", [datetime(2026, 1, 15, 21, 0), datetime(2026, 11, 12, 3, 40),
                                datetime(2026, 7, 2, 23, 10)], ids=lambda d: d.strftime("%m-%d"))
def test_nocturnal_reads_the_standard_time(key, star, ut):
    """The arm laid along the pointer (its hour angle at that moment, Skyfield, star of the
    date), the tooth on the date: the hour disc shows the standard time within 2 minutes."""
    lat, lon, off = CHERBOURG
    stars = workshop.stars_of_date([(star[0], star[1], star[2], 2.0), ("Dubhe", 11.062130, 61.75103, 1.8)], 2026)
    pointers = {"great_bear": stars[1][1], key: stars[0][1]}
    geo = instruments.nocturnal(lat, lon, off, 2026, pointers)
    lst = (float(_sky()["ts"].ut1_jd(AstroEngine.julian_day(ut)).gmst) + lon / 15) % 24
    arm = ((lst - pointers[key]) * 15.0) % 360.0
    std = ut + timedelta(hours=off)
    reading = instruments.nocturnal_reading(arm, std.month, std.day, geo, key)
    expected = std.hour + std.minute / 60
    assert abs((reading - expected + 12) % 24 - 12) * 60 < 2.0


@pytest.mark.parametrize("kind", ["astrolabe", "nocturnal"])
@pytest.mark.parametrize("site", [CHERBOURG, SYDNEY], ids=["north", "south"])
def test_workshop_2_pdfs(tmp_path, kind, site):
    zone = ZoneInfo("Europe/Paris" if site[0] > 0 else "Australia/Sydney")
    place = workshop.Place("", site[0], site[1], zone, datetime(2026, 11, 12, 20))
    pages = workshop.instrument_pages(kind, place, options={"size": 120})
    texts = [txt.get_text() for fig in pages.figures for ax in fig.axes for txt in ax.texts]
    assert not [txt for txt in texts if txt.startswith("[")]
    assert len(pages.figures) >= (6 if kind == "astrolabe" else 3)
    assert workshop.print_instrument(kind, str(tmp_path / "x.pdf"), place, options={"size": 120}) == len(pages.figures)


# ── The planisphere in its holder (4.23) ─────────────────────────────────────

@pytest.mark.parametrize("site", [CHERBOURG, SYDNEY], ids=["north", "south"])
@pytest.mark.parametrize("paper", list(workshop.PAPERS))
def test_planisphere_holder(site, paper):
    """As the planispheres of the shops: the night's hours on the holder's rounded edge, the wheel's
    dates just past it; the window well inside, room left for the hours and the directions; the
    wheel clear of the sides, of the fold and of the glue; everything on the page."""
    import charts
    lat, lon, off = site
    r_chart, r_wheel = workshop._planisphere_sizes(paper)
    geo = instruments.planisphere(lat, lon, off, 2026, r_chart, [], charts.constellation_figures(),
                                  margin=workshop.PLANISPHERE_MARGIN)
    x, y, frame = workshop.planisphere_holder_outline(r_chart, r_wheel)
    first, last = workshop.PLANISPHERE_NIGHT
    for hours in (24 - first, last):                       # from midnight to the first and the last hour
        assert math.radians(hours * 15 * instruments.SIDEREAL_RATE) < frame["span"] - math.radians(5)
    assert np.hypot(*geo["horizon"]).max() <= r_chart - 8.0     # the window, then the S, then the hours
    assert r_wheel < frame["side"] - 2 and r_wheel < frame["fold"] - 1
    low = frame["fold"] - (frame["fold"] - frame["shoulder"]) + 2.0  # the glue strips' end, from the pole
    assert math.sqrt(r_wheel ** 2 - low ** 2) < frame["side"] - 6.0
    assert x.max() == pytest.approx(frame["side"]) and y.max() == pytest.approx(frame["pin"] + 10.0)
    assert y.min() == pytest.approx(-r_chart, abs=0.01)
    width, height = workshop.PAPERS[paper]
    zone = ZoneInfo("Europe/Paris") if lat > 0 else ZoneInfo("Australia/Sydney")
    place = workshop.Place("", lat, lon, zone, datetime(2026, 11, 12, 20))
    page = workshop.instrument_pages("planisphere", place, paper).figures[1].axes[0]
    outline = max(page.lines, key=lambda line: len(line.get_xdata()))
    assert 20 < min(outline.get_ydata()) and max(outline.get_ydata()) < height - 18
    assert 10 < min(outline.get_xdata()) and max(outline.get_xdata()) < width - 10
    texts = [txt.get_text() for txt in page.texts]
    assert "0h" in texts and f"{first}h" in texts and f"{last}h" in texts and "12h" not in texts


def test_planisphere_holder_low_latitude():
    """Near the tropics the chart stops short of the other pole."""
    place = workshop.Place("", 12.0, -61.7, ZoneInfo("America/Grenada"), datetime(2026, 11, 12, 20))
    pages = workshop.instrument_pages("planisphere", place)
    assert len(pages.figures) >= 3
