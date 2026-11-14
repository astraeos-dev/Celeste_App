"""
tests/test_neo.py — Near-Earth asteroids passing close to the Earth (neo.py, v4.20)

The samples are real answers of JPL's APIs, made on 13 November 2026: the
Close-Approach Data API (seven approaches, trimmed) and Horizons (2016 NV, a
geocentric ephemeris around its approach of 8 December 2026). The positions
seen from Paris are checked against Horizons' own ephemeris for that place.
"""
import json
import os
import sys
from datetime import datetime

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import neo  # noqa: E402

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
PARIS = (48.85, 2.35)


@pytest.fixture(scope="module")
def payload():
    with open(os.path.join(DATA, "cad_sample.json"), encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def approaches(payload):
    return neo.parse(payload)


@pytest.fixture(scope="module")
def ephemeris_text():
    with open(os.path.join(DATA, "horizons_2016NV.txt"), encoding="utf-8") as f:
        return f.read()


def _find(approaches, designation, year=None):
    return next(a for a in approaches if a["designation"] == designation and (year is None or a["date"].year == year))


# ── The close approaches ──────────────────────────────────────────────────────

def test_parse(approaches):
    assert len(approaches) == 7
    assert all(a["date"] <= b["date"] for a, b in zip(approaches, approaches[1:]))
    nv = _find(approaches, "2016 NV")
    # 18:43 TDB is 18:42 UT (ΔT 69 s)
    assert datetime(2026, 12, 8, 18, 41, 30) <= nv["date"] <= datetime(2026, 12, 8, 18, 42, 30)
    assert nv["distance_au"] == pytest.approx(0.0366182473671146)
    assert nv["speed"] == pytest.approx(10.416, abs=0.001) and nv["h"] == 19.86
    assert nv["name"] == "2016 NV" and nv["diameter_km"] is None and nv["sigma_minutes"] == 0.0


def test_names_and_uncertainties(approaches):
    assert _find(approaches, "506074")["name"] == "506074 Svarog"
    assert _find(approaches, "506074")["diameter_km"] == 0.665
    assert _find(approaches, "137108")["name"] == "137108 (1999 AN10)"
    assert _find(approaches, "2026 VQ5")["sigma_minutes"] == 179.0                 # "02:59"
    assert _find(approaches, "2023 VE6")["sigma_minutes"] == 5 * 1440 + 3 * 60 + 28   # "5_03:28"
    assert neo._sigma_minutes("") is None and neo._sigma_minutes("??") is None


def test_unreadable_rows_are_left_out(payload):
    damaged = dict(payload, data=[["x"] * len(payload["fields"])] + payload["data"])
    assert len(neo.parse(damaged)) == 7
    assert neo.parse({}) == []


def test_sizes(approaches):
    small, large = neo.size_m(_find(approaches, "2016 NV"))                # H 19.86
    assert small == pytest.approx(284, rel=0.01) and large == pytest.approx(634, rel=0.01)
    assert neo.size_m(_find(approaches, "506074")) == (665.0, 665.0)       # measured
    assert neo.size_m({"h": None}) is None


def test_lunar_distances(approaches):
    assert neo.lunar_distances(_find(approaches, "137108")["distance_au"]) == pytest.approx(1.014, abs=0.002)
    assert neo.lunar_distances(neo.LD_AU) == pytest.approx(1.0)


def test_notable(approaches):
    assert neo.notable(_find(approaches, "137108"))                          # 1 km, at a lunar distance
    assert neo.notable(_find(approaches, "2016 NV"))                         # H 19.9: 280 to 630 m
    assert not neo.notable(_find(approaches, "2026 VP8", 2026))              # 8 to 18 m at 3 LD
    assert neo.notable({"distance_au": 0.5 * neo.LD_AU, "h": 30.0})         # nearer than the Moon


def test_worth_an_ephemeris(approaches):
    assert neo.best_magnitude(_find(approaches, "2016 NV")) == pytest.approx(12.7, abs=0.05)
    assert neo.worth_an_ephemeris(_find(approaches, "2016 NV"))
    assert not neo.worth_an_ephemeris(_find(approaches, "2026 VP8", 2026))   # 16.7 at best
    assert not neo.worth_an_ephemeris({"distance_au": 0.01, "h": None})


# ── Horizons ──────────────────────────────────────────────────────────────────

def test_command():
    assert neo._command("99942") == "'99942;'"
    assert neo._command("2016 NV") == "'DES=2016 NV;'"


def test_parse_ephemeris(ephemeris_text):
    rows = neo.parse_ephemeris(ephemeris_text)
    assert len(rows) == 21
    first = rows[0]
    assert first["date"] == datetime(2026, 12, 8, 12, 0)
    assert first["ra"] == pytest.approx(2.807159596 / 15.0) and first["dec"] == pytest.approx(10.438658390)
    assert first["mag"] == 15.056 and first["distance_au"] == pytest.approx(0.0366599638844)
    with pytest.raises(neo.NeoError):
        neo.parse_ephemeris("No matches found.")


# Horizons for Paris itself (2.35° E, 48.85° N, airless apparent): UT hour, altitude, azimuth
HORIZONS_PARIS = ((18, 48.253, 157.141), (19, 49.999, 179.316), (20, 48.001, 201.401),
                  (21, 42.743, 220.836), (22, 35.217, 236.969))


def test_seen_from_agrees_with_horizons(ephemeris_text):
    seen = {r["date"].hour: r for r in neo.seen_from(neo.parse_ephemeris(ephemeris_text), *PARIS)
            if r["date"].day == 8}
    for hour, alt, az in HORIZONS_PARIS:
        assert seen[hour]["alt"] == pytest.approx(alt, abs=0.02), hour
        assert seen[hour]["az"] == pytest.approx(az, abs=0.02), hour
    # 5.5 million km away, the place shifts it by up to 4 arcminutes: 1 arcminute here at least
    row = seen[19]
    assert row["distance_km"] == pytest.approx(row["distance_au"] * neo.AU_KM, rel=0.002)
    assert 15 < row["rate"] < 30                                            # arcseconds a minute
    assert row["sun"] < -25


def test_windows(ephemeris_text):
    seen = neo.seen_from(neo.parse_ephemeris(ephemeris_text), *PARIS)
    found = neo.windows(seen)
    assert len(found) == 1
    window = found[0]
    assert window["start"] == datetime(2026, 12, 8, 18, 0)      # the Sun 12° down after 17:15 UT
    assert window["end"] == datetime(2026, 12, 9, 0, 0)          # then too low in the west
    assert window["best"]["alt"] >= 45                           # brightest through the least air
    assert neo.windows(seen, min_alt=60) == []


# ── Download and cache ────────────────────────────────────────────────────────

@pytest.fixture
def offline(tmp_path, monkeypatch, payload, ephemeris_text):
    monkeypatch.setattr(neo, "CACHE", str(tmp_path / "neo_approaches.json"))
    monkeypatch.setattr(neo, "EPHEMERIS_DIR", str(tmp_path / "neo"))
    calls = []

    def fake(url, params, timeout):
        calls.append((url, params))
        if url == neo.CAD_URL:
            return payload
        return {"result": ephemeris_text}
    monkeypatch.setattr(neo, "_get", fake)
    return calls


def test_refresh_downloads_then_keeps(offline):
    found, error = neo.refresh(now=datetime(2026, 11, 13))
    assert len(found) == 7 and error is None
    url, params = offline[0]
    assert params["date-min"] == "2026-11-06" and params["date-max"] == "2027-11-14"
    assert params["dist-max"] == "0.05"
    found, error = neo.refresh()
    assert len(found) == 7 and len(offline) == 1                 # kept: no second download


def test_refresh_keeps_the_list_when_offline(offline, monkeypatch, tmp_path):
    neo.refresh(now=datetime(2026, 11, 13))
    old = os.path.getmtime(neo.CACHE) - 13 * 3600
    os.utime(neo.CACHE, (old, old))

    def down(url, params, timeout):
        raise OSError("no connection")
    monkeypatch.setattr(neo, "_get", down)
    found, error = neo.refresh()
    assert len(found) == 7 and "no connection" in error


def test_ephemeris_is_asked_once_a_day(offline, approaches):
    nv = _find(approaches, "2016 NV")
    rows = neo.ephemeris(nv)
    assert len(rows) == 21
    url, params = offline[-1]
    assert url == neo.HORIZONS_URL
    assert params["COMMAND"] == "'DES=2016 NV;'" and params["CENTER"] == "'500@399'"   # no place sent
    assert params["START_TIME"] == "'2026-12-06 18:41'"
    neo.ephemeris(nv)
    assert len(offline) == 1
