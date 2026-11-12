"""
tests/test_satellites.py — Orbits of the bright satellites and their passes, without network
=============================================================================================
Elements of 7 November 2026: ISS (ARISS), Tiangong (AMSAT), Hubble (CelesTrak).
"""
import calendar
import io
import os
import sys
from datetime import datetime, timedelta

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import satellites  # noqa: E402
from engine import AstroEngine, _sky  # noqa: E402

ELEMENTS = {
    "ISS": ("1 25544U 98067A   26311.46585591  .00014112  00000-0  26146-3 0  9997",
            "2 25544  51.6322 311.0744 0007266 358.6454   1.4513 15.49241650593960"),
    "Tiangong": ("1 48274U 21035A   26311.08203773  .00020571  00000-0  23676-3 0  9991",
                 "2 48274  41.4679 173.7415 0004583 270.4816  89.5498 15.61485279315486"),
    "Hubble": ("1 20580U 90037B   26311.89641212  .00008265  00000+0  25055-3 0  9990",
               "2 20580  28.4716 177.2871 0001867 321.5230  38.5233 15.32215546810621"),
}
TLE_TEXT = "".join(f"{name}\n{a}\n{b}\n" for name, (a, b) in ELEMENTS.items())
CHERBOURG = (49.6333, -1.6167)


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


# ── elements: parsing, download, cache ───────────────────────────────────

def test_parse_checks_the_checksums():
    assert satellites.parse(TLE_TEXT) == {25544: ELEMENTS["ISS"], 48274: ELEMENTS["Tiangong"],
                                          20580: ELEMENTS["Hubble"]}
    line1, line2 = ELEMENTS["ISS"]
    corrupt = line1[:68] + str((int(line1[68]) + 1) % 10)
    assert satellites.parse(f"{corrupt}\n{line2}\n") == {}
    assert satellites.parse("garbage\n1 short\n2 short\n") == {}


def test_epoch_age():
    now = calendar.timegm((2026, 11, 8, 7, 0, 0))
    assert abs(satellites.epoch_age_days({"ISS": ELEMENTS["ISS"]}, now) - 0.826) < 0.001
    assert satellites.epoch_age_days({}, now) == float("inf")


def test_download_from_celestrak(monkeypatch):
    def urlopen(request, timeout=None):
        number = int(request.full_url.split("CATNR=")[1].split("&")[0])
        name = next(n for n, k in satellites.SATELLITES.items() if k == number)
        return _Response(f"{name}\n{ELEMENTS[name][0]}\n{ELEMENTS[name][1]}\n".encode())
    monkeypatch.setattr(satellites.urllib.request, "urlopen", urlopen)
    assert satellites.download() == ELEMENTS


def test_amsat_when_celestrak_refuses(monkeypatch):
    """CelesTrak rate-limits; AMSAT carries the two stations, not Hubble."""
    amsat = "".join(f"{n}\n{a}\n{b}\n" for n, (a, b) in ELEMENTS.items() if n != "Hubble")

    def urlopen(request, timeout=None):
        if "celestrak" in request.full_url:
            raise ConnectionResetError("reset by peer")
        return _Response(amsat.encode())
    monkeypatch.setattr(satellites.urllib.request, "urlopen", urlopen)
    assert set(satellites.download()) == {"ISS", "Tiangong"}


def test_nothing_downloaded(monkeypatch):
    def urlopen(request, timeout=None):
        raise OSError("offline")
    monkeypatch.setattr(satellites.urllib.request, "urlopen", urlopen)
    with pytest.raises(satellites.SatelliteError, match="offline"):
        satellites.download()


def test_refresh_keeps_recent_elements(tmp_path, monkeypatch):
    monkeypatch.setattr(satellites, "CACHE", str(tmp_path / "satellites.tle"))
    satellites.save(ELEMENTS)
    assert satellites.load() == ELEMENTS
    monkeypatch.setattr(satellites, "epoch_age_days", lambda elements, now=None: 0.5)
    monkeypatch.setattr(satellites, "download", lambda timeout=15: pytest.fail("no download"))
    assert satellites.refresh() == (ELEMENTS, None)


def test_refresh_downloads_old_elements_and_falls_back(tmp_path, monkeypatch):
    monkeypatch.setattr(satellites, "CACHE", str(tmp_path / "satellites.tle"))
    satellites.save(ELEMENTS)
    monkeypatch.setattr(satellites, "epoch_age_days", lambda elements, now=None: 5.0)
    monkeypatch.setattr(satellites, "download", lambda timeout=15: {"ISS": ELEMENTS["ISS"]})
    assert satellites.refresh() == ({"ISS": ELEMENTS["ISS"]}, None)
    assert satellites.load() == {"ISS": ELEMENTS["ISS"]}          # kept on disk

    def offline(timeout=15):
        raise satellites.SatelliteError("offline")
    monkeypatch.setattr(satellites, "download", offline)
    elements, error = satellites.refresh()
    assert elements == {"ISS": ELEMENTS["ISS"]} and "offline" in str(error)


# ── passes ───────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def passes():
    return AstroEngine.satellite_passes(ELEMENTS, datetime(2026, 11, 8, 12), *CHERBOURG, 0.0, 10)


def test_passes_are_visible_and_ordered(passes):
    assert len(passes) >= 8 and [p["start"] for p in passes] == sorted(p["start"] for p in passes)
    for p in passes:
        assert p["start"] <= p["max"] <= p["end"]
        assert timedelta(seconds=30) <= p["end"] - p["start"] <= timedelta(minutes=12)
        assert 10.0 - 0.5 <= p["max_alt"] <= 90.0 and p["max_alt"] >= max(p["start_alt"], p["end_alt"])


def test_a_pass_checked_by_hand(passes):
    """At its highest, the satellite is where SGP4 puts it, lit by the Sun, in a dark sky."""
    from skyfield.api import EarthSatellite, wgs84
    sky = _sky()
    p = max(passes, key=lambda p: p["max_alt"])
    sat = EarthSatellite(*ELEMENTS[p["name"]], p["name"], sky["ts"])
    topos = wgs84.latlon(*CHERBOURG)
    t = sky["ts"].ut1_jd(AstroEngine.julian_day(p["max"]))
    alt, az, _ = (sat - topos).at(t).altaz()
    # angle between the two directions (near the zenith the azimuth alone swings fast); the time
    # is given to the second, and the ISS crosses about 1° a second overhead
    import math
    a1, a2, daz = math.radians(alt.degrees), math.radians(p["max_alt"]), math.radians(az.degrees - p["max_az"])
    cos_sep = math.sin(a1) * math.sin(a2) + math.cos(a1) * math.cos(a2) * math.cos(daz)
    assert math.degrees(math.acos(min(1.0, cos_sep))) < 0.6
    assert sat.at(t).is_sunlit(sky["eph"])
    sun_alt = (sky["earth"] + topos).at(t).observe(sky["sun"]).apparent().altaz()[0].degrees
    assert sun_alt < -6.0


def test_iss_in_the_evening_in_mid_november(passes):
    """From Cherbourg, mid-November 2026: ISS passes after dusk, into the Earth's shadow."""
    iss = [p for p in passes if p["name"] == "ISS"]
    assert len(iss) >= 8
    assert all(16 <= p["start"].hour <= 20 for p in iss)
    assert sum(p["into_shadow"] for p in iss) >= len(iss) // 2


def test_hubble_stays_low_from_cherbourg(passes):
    """Inclined 28.5°, Hubble barely rises 10° above the horizon at latitude 49.6°."""
    assert not [p for p in passes if p["name"] == "Hubble"]


def test_from_the_tropics():
    """From Miami (25.8° N), Hubble has visible passes, well above the horizon."""
    found = AstroEngine.satellite_passes({"Hubble": ELEMENTS["Hubble"]}, datetime(2026, 11, 8), 25.76, -80.19,
                                         0.0, 10)
    assert found and max(p["max_alt"] for p in found) > 20


def test_visual_group_parsed_with_names(tmp_path, monkeypatch):
    """CelesTrak's "visual" group: the names kept, kept on disk, the three followed satellites
    not repeated."""
    text = "".join(f"{name.upper()} DEB\n{a}\n{b}\n" for name, (a, b) in ELEMENTS.items())
    found = satellites.parse_named(text)
    assert set(found) == {f"{name.upper()} DEB" for name in ELEMENTS}
    monkeypatch.setattr(satellites, "_get", lambda url, timeout: text)
    path = tmp_path / "visual.tle"
    visual, error = satellites.refresh_visual(max_age_days=-1, path=str(path))
    assert error is None and visual == found and path.exists()
    merged = satellites.with_visual({"ISS": ELEMENTS["ISS"]}, visual)
    assert "ISS" in merged and "ISS DEB" not in merged and len(merged) == len(ELEMENTS)


def test_visual_group_offline_keeps_the_old_list(tmp_path, monkeypatch):
    path = tmp_path / "visual.tle"
    path.write_text("".join(f"{n}\n{a}\n{b}\n" for n, (a, b) in ELEMENTS.items()), encoding="ascii")

    def offline(url, timeout):
        raise OSError("no network")
    monkeypatch.setattr(satellites, "_get", offline)
    visual, error = satellites.refresh_visual(max_age_days=-1, path=str(path))
    assert error is not None and set(visual) == set(ELEMENTS)
