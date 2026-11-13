"""
tests/test_transients.py — Recent novae and supernovae (transients.py, v4.21)

The samples are real rows of the two lists, copied on 13 November 2026:
David Bishop's active supernovae (rochesterastronomy.org) and Koji Mukai's
recent galactic novae (NASA Goddard).
"""
import io
import os
import sys
import zlib
from datetime import date, datetime

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import transients as tr  # noqa: E402

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
TODAY = date(2026, 11, 13)
PARIS = (48.85, 2.35)


def _read(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        return f.read()


@pytest.fixture(scope="module")
def supernovae():
    return tr.parse_supernovae(_read("snactive_sample.html"))


@pytest.fixture(scope="module")
def novae():
    return tr.parse_novae(_read("novae_sample.html"), since=date(2024, 11, 13))


def _named(objects, name):
    return next(o for o in objects if o["name"] == name)


# ── Reading the lists ─────────────────────────────────────────────────────────

def test_supernovae(supernovae):
    # the cataclysmic variable, the unclassified transient and the 18th-magnitude supernova are left out
    assert [o["name"] for o in supernovae] == ["LMC V1341", "SN 2026ahvu", "AT 2026aina", "AT 2026abbx",
                                               "SN 2026sqf", "SN 2026ahvi"]
    sn = _named(supernovae, "SN 2026ahvu")
    assert sn["kind"] == "supernova" and sn["type"] == "Ia" and sn["host"] == "NGC 1433"
    assert sn["ra"] == pytest.approx(3 + 41 / 60 + 55.511 / 3600)
    assert sn["dec"] == pytest.approx(-(47 + 13 / 60 + 39.39 / 3600))
    assert sn["mag"] == 12.3 and sn["mag_date"] == date(2026, 11, 10) and not sn["stale"]
    assert sn["discovered"] == date(2026, 11, 2) and sn["discoverer"] == "ATLAS"
    assert sn["z"] == pytest.approx(0.003589) and sn["aka"] == ["ATLAS26ncp", "GOTO26ltt"]
    sqf = _named(supernovae, "SN 2026sqf")
    assert sqf["type"] == "Ia-CSM" and sqf["peak"] == 11.2 and sqf["peak_date"] == date(2026, 7, 28)
    nova = _named(supernovae, "AT 2026aina")
    assert nova["kind"] == "nova" and nova["type"] == "EGN" and nova["host"] == "LMC" and nova["z"] is None
    assert _named(supernovae, "AT 2026abbx")["host"] is None                    # a nova of our galaxy


def test_unreadable_rows_are_left_out():
    text = _read("snactive_sample.html").replace("03:41:55.511", "3h41", 1)
    assert "SN 2026ahvu" not in [o["name"] for o in tr.parse_supernovae(text)]
    assert tr.parse_supernovae("<html>not found</html>") == []
    assert len(tr.parse_supernovae(_read("snactive_sample.html"), keep_mag=13.0)) == 4


def test_novae(novae):
    assert [o["name"] for o in novae] == ["V8056 Sgr", "TCP J17520680-2343207", "V488 Sge", "V1452 Tau"]
    v488 = _named(novae, "V488 Sge")
    assert v488["peak"] == 7.1 and v488["discovered"] == date(2026, 8, 25) and v488["mag"] is None
    assert v488["ra"] == pytest.approx(19 + 45 / 60 + 6.49 / 3600)
    assert v488["dec"] == pytest.approx(18 + 22 / 60 + 42.1 / 3600)
    assert v488["aka"] == ["Nova Sagittae 2026 PNV J19450648+1822422"]
    assert _named(novae, "V8056 Sgr")["peak"] == 9.3                           # "9.3 (V) 7.8 (unfiltered?)"
    tcp = _named(novae, "TCP J17520680-2343207")                               # no variable star name yet
    assert tcp["aka"] == ["ASASSN-26fc", "AT 2026abbx", "Nova in Saggitarius"]
    every = tr.parse_novae(_read("novae_sample.html"))
    assert _named(every, "AT 2023tow")["peak"] == pytest.approx(12.26)          # "G=12.26"


def test_merge(supernovae, novae):
    merged = tr.merge(supernovae, novae)
    assert len(merged) == len(supernovae) + len(novae) - 1
    tcp = _named(merged, "TCP J17520680-2343207")
    assert tcp["mag"] == 12.6 and tcp["mag_date"] == date(2026, 9, 8)          # the latest measure, Bishop's
    assert tcp["peak"] == 11.3 and "AT 2026abbx" in tcp["aka"]
    assert not any(o["name"] == "AT 2026abbx" for o in merged)
    assert tr.separation_arcsec(tcp, _named(supernovae, "AT 2026abbx")) < 5


def test_chosen(supernovae, novae):
    merged = tr.merge(supernovae, novae)
    shown = [o["name"] for o in tr.chosen(merged, TODAY, mag_limit=15.0, nova_days=365)]
    # LMC V1341's latest magnitude is of 2024: faded or forgotten
    assert set(shown) == {"SN 2026ahvu", "AT 2026aina", "SN 2026sqf", "SN 2026ahvi", "V8056 Sgr",
                          "TCP J17520680-2343207", "V488 Sge", "V1452 Tau"}
    assert shown[:3] == ["V488 Sge", "SN 2026ahvu", "AT 2026aina"]              # a nova at its peak + 5
    assert shown[-1] == "TCP J17520680-2343207"                                 # its measure is two months old
    bright = [o["name"] for o in tr.chosen(merged, TODAY, mag_limit=13.0, nova_days=365)]
    assert "SN 2026sqf" not in bright and "SN 2026ahvu" in bright and "V488 Sge" in bright
    recent = [o["name"] for o in tr.chosen(merged, TODAY, mag_limit=15.0, nova_days=60)]
    assert "V8056 Sgr" in recent and "V488 Sge" not in recent


def test_distance():
    assert tr.distance_mly(0.003589) == pytest.approx(50.1, abs=0.2)
    assert tr.distance_mly(None) is None and tr.distance_mly(0.0) is None


def test_tonight(supernovae):
    """From Paris, the night of 13 to 14 November 2026: SN 2026sqf (+53°) high before dawn,
    SN 2026ahvu (−47°) never above the horizon."""
    import planner
    night = planner.night_window(datetime(2026, 11, 13, 21), *PARIS, 0.0, 0,
                                 depths=((tr.DARK_SUN, "naut"),))
    objects = [_named(supernovae, "SN 2026sqf"), _named(supernovae, "SN 2026ahvu")]
    sqf, ahvu = tr.tonight(objects, night["start"], night["end"], *PARIS)
    assert ahvu is None
    assert sqf["alt"] == pytest.approx(78.0, abs=2.0) and 40 < sqf["az"] < 320
    assert night["start"] <= sqf["best"] <= night["end"] and sqf["best"].hour >= 4
    assert tr.tonight([], night["start"], night["end"], *PARIS) == []
    assert tr.tonight(objects, None, None, *PARIS) == [None, None]


# ── Download and cache ────────────────────────────────────────────────────────

@pytest.fixture
def lists(tmp_path, monkeypatch):
    monkeypatch.setattr(tr, "CACHE", str(tmp_path / "transients.json"))
    pages = {tr.SUPERNOVAE_URL: _read("snactive_sample.html"), tr.NOVAE_URL: _read("novae_sample.html")}
    calls = []

    def fake(url, timeout):
        calls.append(url)
        return pages[url]
    monkeypatch.setattr(tr, "_get", fake)
    return calls


def test_refresh_downloads_then_keeps(lists):
    objects, error = tr.refresh(today=TODAY)
    assert error is None and len(objects) == 9 and len(lists) == 2
    assert _named(objects, "SN 2026sqf")["discovered"] == date(2026, 7, 8)       # dates kept as dates
    objects, error = tr.refresh(today=TODAY)
    assert len(objects) == 9 and len(lists) == 2                                 # kept: no download


def test_refresh_keeps_the_lists_when_offline(lists, monkeypatch):
    tr.refresh(today=TODAY)
    old = os.path.getmtime(tr.CACHE) - 13 * 3600
    os.utime(tr.CACHE, (old, old))

    def down(url, timeout):
        raise OSError("no connection")
    monkeypatch.setattr(tr, "_get", down)
    objects, error = tr.refresh(today=TODAY)
    assert len(objects) == 9 and "no connection" in error


def test_get_reads_a_compressed_page(monkeypatch):
    page = "<table><tr><td>é</td></tr></table>"
    packer = zlib.compressobj(wbits=16 + zlib.MAX_WBITS)
    body = packer.compress(page.encode("utf-8")) + packer.flush()

    class Answer(io.BytesIO):
        headers = {"Content-Encoding": "gzip"}

        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False
    monkeypatch.setattr(tr.urllib.request, "urlopen", lambda request, timeout: Answer(body))
    assert tr._get("https://example.org/", 5) == page
