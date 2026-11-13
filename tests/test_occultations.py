"""
tests/test_occultations.py — Stars hidden by asteroids (occultations.py, v4.20)

The sample holds seven real events of the IOTA predictions for 2026
(asteroidoccultation.com, 2026-iota.zip), copied verbatim. The reading of the
Besselian elements (X east, Y north, UT) is checked against JPL Horizons;
the band on the ground against the shadow's axis and its edges carried to the
WGS84 ellipsoid in three dimensions.
"""
import io
import math
import os
import sys
import zipfile
from datetime import datetime, timedelta

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import occultations as occ  # noqa: E402
from engine import AstroEngine, _WGS84_A  # noqa: E402

SAMPLE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "occelmnt_sample.xml")
PARIS, LYON, MUNICH = (48.85, 2.35), (45.76, 4.84), (48.14, 11.58)


@pytest.fixture(scope="module")
def events():
    with open(SAMPLE, encoding="utf-8") as f:
        return occ.parse(f.read())


def _event(events, name):
    return next(e for e in events if e["name"] == name)


def _zip(text):
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("2026-iota-all.xml", text)
    return data.getvalue()


# ── Reading the predictions ───────────────────────────────────────────────────

def test_parse(events):
    assert len(events) == 7
    titania = _event(events, "Titania")
    assert titania["number"] == "593"
    assert abs((titania["middle"] - datetime(2026, 1, 1, 0, 28, 56)).total_seconds()) < 1
    assert titania["elements"][:4] == (-0.0617697, -0.3221017, 13.7466999, -2.6525074)
    assert titania["diameter_km"] == 79.0 and titania["star_mag"] == 9.73 and titania["mag"] == 14.49
    assert titania["star"] == "UCAC4 474-050539"
    assert (titania["ra"], titania["dec"]) == (14.01445828, 4.5677527)
    assert titania["substar"] == (102.3014, 4.5678) and titania["subsolar"] == (173.61, -23.02)
    assert titania["max_duration"] == 3.18
    assert titania["orbit"].startswith("JPL#68")


def test_unreadable_events_are_left_out(events):
    with open(SAMPLE, encoding="utf-8") as f:
        text = f.read()
    damaged = text.replace("<Object>593,Titania,14.49,79.000", "<Object>593,Titania,14.49,x", 1)
    assert len(occ.parse(damaged)) == 6
    assert occ.parse("<html>not found</html>") == []


def test_read_zip():
    with open(SAMPLE, encoding="utf-8") as f:
        text = f.read()
    assert len(occ.read_zip(_zip(text))) == 7
    with pytest.raises(occ.OccultationError):
        occ.read_zip(b"<html>404</html>")


def test_mag_drop():
    # Titania (14.49) in front of a 9.73 star: the light falls almost to the asteroid's alone
    assert occ.mag_drop(9.73, 14.49) == pytest.approx(4.76, abs=0.02)
    assert occ.mag_drop(10.0, 10.0) == pytest.approx(2.5 * math.log10(2.0), abs=1e-9)
    assert occ.mag_drop(None, 12.0) is None


# ── The elements, against JPL Horizons ────────────────────────────────────────

def test_elements_read_as_horizons_sees_the_asteroid(events):
    """
    593 Titania, airless apparent geocentric RA, Dec and distance from JPL
    Horizons (orbit JPL#74) at 00:28 and 00:29 UT on 1 January 2026, carried
    onto the fundamental plane of the star's apparent place of date: within
    0.02 Earth radii of the elements at their middle (the IOTA file used
    orbit JPL#68), and moving as they do. Read in TT instead of UT, X would be
    0.26 Earth radii off.
    """
    titania = _event(events, "Titania")
    rows = ((210.216593824, 4.567482208, 2.50028529219166), (210.216818481, 4.567438972, 2.50027853642608))
    km_per_au = 149597870.7
    alpha_s, delta_s = math.radians(titania["ra"] * 15.0), math.radians(titania["dec"])

    def plane(ra, dec, dist):
        a, d = math.radians(ra), math.radians(dec)
        r = dist * km_per_au / occ.EARTH_KM
        x = r * math.cos(d) * math.sin(a - alpha_s)
        y = r * (math.sin(d) * math.cos(delta_s) - math.cos(d) * math.sin(delta_s) * math.cos(a - alpha_s))
        return x, y

    (x0, y0), (x1, y1) = plane(*rows[0]), plane(*rows[1])
    frac = (titania["middle"] - datetime(2026, 1, 1, 0, 28)).total_seconds() / 60.0
    x, y = x0 + frac * (x1 - x0), y0 + frac * (y1 - y0)
    ex, ey, dx, dy = titania["elements"][:4]
    assert abs(x - ex) < 0.02 and abs(y - ey) < 0.02
    assert (x1 - x0) * 60 == pytest.approx(dx, rel=0.01)
    assert (y1 - y0) * 60 == pytest.approx(dy, rel=0.01)
    assert abs(dx * 69.2 / 3600.0) > 10 * 0.02                    # TT would be far off


# ── The band on the ground, in three dimensions ──────────────────────────────

def _frame(event, tau):
    """The star's direction and the plane's east and north axes, Earth-fixed, at *tau*."""
    lam = math.radians(event["substar"][0]) - occ._SIDEREAL * tau
    d = math.radians(event["dec"])
    star = np.array([math.cos(d) * math.cos(lam), math.cos(d) * math.sin(lam), math.sin(d)])
    east = np.array([-math.sin(lam), math.cos(lam), 0.0])
    north = np.array([-math.sin(d) * math.cos(lam), -math.sin(d) * math.sin(lam), math.cos(d)])
    return star, east, north


def _ground_point(event, tau, x, y):
    """Where the line parallel to the star through (x, y) on the plane meets the ground."""
    star, east, north = _frame(event, tau)
    origin = (x * east + y * north + 3.0 * star) * _WGS84_A
    lat, lon = AstroEngine._geodetic(AstroEngine._ellipsoid_hit(origin[:, None], -star[:, None]))
    return float(lat[0]), float(lon[0])


def _across(event, tau, lat, lon):
    """The unit vector across the band on the plane, at the place (lat, lon), at *tau*."""
    pc, ps = occ._place(lat, lon)
    _x, _y, x1, y1, _a, _b = occ._shadow(event["elements"], tau)
    _xi, _eta, xi1, eta1, _c, _d = occ._observer(pc, ps, math.radians(event["dec"]),
                                                 float(occ._hour_angle(lon, event["substar"][0], tau)))
    vx, vy = x1 - xi1, y1 - eta1
    return -vy / math.hypot(vx, vy), vx / math.hypot(vx, vy)


@pytest.mark.parametrize("tau", (-0.01, 0.0, 0.01))
def test_on_the_centre_line(events, tau):
    for event in events:
        x, y, *_ = occ._shadow(event["elements"], tau)
        lat, lon = _ground_point(event, tau, x, y)
        if math.isnan(lat):
            continue
        seen = occ.pass_at(event, lat, lon)
        assert seen["distance_km"] < 0.05, event["name"]
        assert abs((seen["date"] - (event["middle"] + timedelta(hours=tau))).total_seconds()) < 1, event["name"]
        assert seen["inside"] and seen["edge_km"] == 0.0 and seen["direction"] is None


def test_band_edges_and_distances(events):
    """Places carried to the ground from the plane at 0.9, 1.1 and 3 radii across the band."""
    for event in events:
        x, y, *_ = occ._shadow(event["elements"], 0.0)
        lat, lon = _ground_point(event, 0.0, x, y)
        if math.isnan(lat):
            continue
        px, py = _across(event, 0.0, lat, lon)
        radius = event["diameter_km"] / 2.0 / occ.EARTH_KM
        for k in (0.9, 1.1, 3.0, -3.0):
            here = _ground_point(event, 0.0, x + k * radius * px, y + k * radius * py)
            if math.isnan(here[0]):
                continue
            seen = occ.pass_at(event, *here)
            assert seen["distance_km"] == pytest.approx(abs(k) * seen["half_width_km"], rel=0.02), event["name"]
            assert seen["inside"] == (abs(k) < 1.0), event["name"]
            if abs(k) == 3.0:
                assert seen["half_width_km"] >= event["diameter_km"] / 2.0 * 0.99   # wider on the ground


def test_direction_points_to_the_centre_line(events):
    for event in events:
        x, y, *_ = occ._shadow(event["elements"], 0.0)
        lat, lon = _ground_point(event, 0.0, x, y)
        if math.isnan(lat):
            continue
        px, py = _across(event, 0.0, lat, lon)
        radius = event["diameter_km"] / 2.0 / occ.EARTH_KM
        here = _ground_point(event, 0.0, x + 3.0 * radius * px, y + 3.0 * radius * py)
        if math.isnan(here[0]):
            continue
        seen = occ.pass_at(event, *here)
        # walk the distance towards the direction given: the centre line, within a few per cent
        az, dist = math.radians(seen["direction"]), seen["distance_km"] / 6371.0
        phi1, lam1 = math.radians(here[0]), math.radians(here[1])
        phi2 = math.asin(math.sin(phi1) * math.cos(dist) + math.cos(phi1) * math.sin(dist) * math.cos(az))
        lam2 = lam1 + math.atan2(math.sin(az) * math.sin(dist) * math.cos(phi1),
                                 math.cos(dist) - math.sin(phi1) * math.sin(phi2))
        there = occ.pass_at(event, math.degrees(phi2), math.degrees(lam2))
        assert there["distance_km"] < 0.05 * seen["distance_km"], event["name"]


def test_duration_on_the_centre_line(events):
    """Across the centre of the band, the star is hidden for the time Occult gives
    (its own figure, at the Earth's centre: within the Earth's turning)."""
    for event in events:
        x, y, *_ = occ._shadow(event["elements"], 0.0)
        lat, lon = _ground_point(event, 0.0, x, y)
        if math.isnan(lat):
            continue
        speed = math.hypot(*event["elements"][2:4])
        tolerance = 0.27 / (speed - 0.27)             # the ground turns at most 0.26 Earth radii an hour
        assert occ.pass_at(event, lat, lon)["duration"] == pytest.approx(event["max_duration"],
                                                                          rel=tolerance + 0.01), event["name"]


# ── From the place ────────────────────────────────────────────────────────────

def test_near_finds_the_bands_over_the_place(events):
    found = occ.near(events, *PARIS)
    li = next(s for s in found if s["event"]["name"] == "Li")
    assert li["inside"] and li["duration"] > 0
    assert li["date"].date() == datetime(2026, 6, 6).date()
    assert li["alt"] == pytest.approx(20.5, abs=1.0) and li["sun"] < -12
    herrick = next(s for s in occ.near(events, *MUNICH) if s["event"]["name"] == "Herrick")
    assert herrick["inside"] and 4 < herrick["duration"] < 8
    imatra = next(s for s in occ.near(events, *LYON) if s["event"]["name"] == "Imatra")
    assert imatra["inside"]
    assert all(found[i]["date"] <= found[i + 1]["date"] for i in range(len(found) - 1))


def test_near_filters(events):
    def names(**kw):
        return [s["event"]["name"] for s in occ.near(events, *PARIS, **kw)]
    assert "Li" in names()
    assert "Li" not in names(min_alt=25.0)                         # the star at 20° only
    assert "Li" not in names(dark_sun=-20.0)                        # the Sun at −18°
    assert "Li" not in names(start=datetime(2026, 6, 7))
    assert "Li" not in names(end=datetime(2026, 6, 6))
    assert "Li" in names(start=datetime(2026, 6, 6), end=datetime(2026, 6, 7))
    edge = occ.pass_at(_event(events, "Phaethon"), *MUNICH)["edge_km"]
    assert edge > 0
    found = [s["event"]["name"] for s in occ.near(events, *MUNICH, max_km=edge + 1, dark_sun=-10)]
    assert "Phaethon" in found
    found = [s["event"]["name"] for s in occ.near(events, *MUNICH, max_km=edge - 1, dark_sun=-10)]
    assert "Phaethon" not in found


def test_daylight_and_horizon_are_left_out(events):
    """Titania's band crosses Asia in the morning: from Paris the star is below the horizon."""
    titania = _event(events, "Titania")
    seen = occ.pass_at(titania, *PARIS)
    assert seen["alt"] < 0 or seen["sun"] > -12
    assert all(s["event"]["name"] != "Titania" for s in occ.near(events, *PARIS, max_km=20000))


# ── Download and cache ────────────────────────────────────────────────────────

@pytest.fixture
def cache(tmp_path, monkeypatch):
    monkeypatch.setattr(occ, "CACHE_DIR", str(tmp_path))
    with open(SAMPLE, encoding="utf-8") as f:
        data = _zip(f.read())
    calls = []

    def fake(year, timeout):
        calls.append(year)
        if year != 2026:
            raise OSError("HTTP Error 404: Not Found")
        return data
    monkeypatch.setattr(occ, "_download", fake)
    return calls


def test_refresh_downloads_then_keeps(cache, tmp_path):
    events, missing = occ.refresh([2026, 2027])
    assert len(events) == 7 and set(missing) == {2027}
    assert "404" in missing[2027]
    assert os.path.isfile(tmp_path / "2026-iota.zip")
    assert cache == [2026, 2027]
    events, missing = occ.refresh([2026])
    assert len(events) == 7 and not missing and cache == [2026, 2027]      # kept: no download
    assert all(events[i]["middle"] <= events[i + 1]["middle"] for i in range(len(events) - 1))


def test_refresh_keeps_an_old_file_when_offline(cache, tmp_path, monkeypatch):
    occ.refresh([2026])
    old = os.path.getmtime(tmp_path / "2026-iota.zip") - 40 * 86400
    os.utime(tmp_path / "2026-iota.zip", (old, old))

    def offline(year, timeout):
        raise OSError("no connection")
    monkeypatch.setattr(occ, "_download", offline)
    events, missing = occ.refresh([2026])
    assert len(events) == 7 and not missing


def test_years_between():
    assert occ.years_between(datetime(2026, 11, 13), datetime(2027, 2, 13)) == [2026, 2027]
    assert occ.years_between(datetime(2026, 1, 1), datetime(2026, 12, 31)) == [2026]
