"""
tests/test_ephemeris.py — Download of the JPL DE440 ephemeris, without network
==============================================================================
The ephemeris is not in the installer: Céleste downloads it once into
~/.celeste, checks it (size and SHA-256 of the NAIF file) and only then gives
it its name.
"""
import hashlib
import io
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import engine  # noqa: E402

PAYLOAD = b"DAF/SPK " + bytes(range(256)) * 40          # an "ephemeris"


class _Response(io.BytesIO):
    def __init__(self, data):
        super().__init__(data)
        self.headers = {"Content-Length": str(len(data))}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def fake_naif(monkeypatch):
    """The NAIF server answers PAYLOAD, which the engine expects."""
    requests = []

    def urlopen(request, timeout=None):
        requests.append(request)
        return _Response(PAYLOAD)

    monkeypatch.setattr(engine.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(engine, "_EPHEMERIS_SIZE", len(PAYLOAD))
    monkeypatch.setattr(engine, "_EPHEMERIS_SHA256", hashlib.sha256(PAYLOAD).hexdigest())
    return requests


def test_download_is_checked_then_named(tmp_path, fake_naif):
    target = tmp_path / "user" / engine._EPHEMERIS_FILE
    seen = []
    path = engine.download_ephemeris(str(target), progress=lambda d, n: seen.append((d, n)))
    assert path == str(target)
    assert target.read_bytes() == PAYLOAD
    assert not (tmp_path / "user" / (engine._EPHEMERIS_FILE + ".part")).exists()
    assert seen[-1] == (len(PAYLOAD), len(PAYLOAD))
    assert fake_naif[0].full_url == engine._EPHEMERIS_URL


def test_corrupt_download_leaves_nothing(tmp_path, fake_naif, monkeypatch):
    monkeypatch.setattr(engine, "_EPHEMERIS_SHA256", "0" * 64)
    with pytest.raises(engine.EphemerisUnavailable, match="corrupt"):
        engine.download_ephemeris(str(tmp_path / engine._EPHEMERIS_FILE))
    assert list(tmp_path.iterdir()) == []


def test_truncated_download_leaves_nothing(tmp_path, fake_naif, monkeypatch):
    monkeypatch.setattr(engine, "_EPHEMERIS_SIZE", len(PAYLOAD) + 1)
    with pytest.raises(engine.EphemerisUnavailable):
        engine.download_ephemeris(str(tmp_path / engine._EPHEMERIS_FILE))
    assert list(tmp_path.iterdir()) == []


def test_cancelled_download_leaves_nothing(tmp_path, fake_naif):
    with pytest.raises(engine.DownloadCancelled):
        engine.download_ephemeris(str(tmp_path / engine._EPHEMERIS_FILE), cancelled=lambda: True)
    assert list(tmp_path.iterdir()) == []


def test_network_error(tmp_path, monkeypatch):
    def urlopen(request, timeout=None):
        raise OSError("no network")
    monkeypatch.setattr(engine.urllib.request, "urlopen", urlopen)
    with pytest.raises(engine.EphemerisUnavailable, match="no network") as error:
        engine.download_ephemeris(str(tmp_path / engine._EPHEMERIS_FILE))
    assert not isinstance(error.value, engine.DownloadCancelled)
    assert list(tmp_path.iterdir()) == []


def test_downloaded_into_the_user_folder(tmp_path, monkeypatch):
    """With no ephemeris anywhere, it is downloaded into ~/.celeste (or $CELESTE_DATA)."""
    monkeypatch.setattr(engine, "_DATA_DIRS", (str(tmp_path / "data"), str(tmp_path / "user")))
    assert engine.user_ephemeris_path() == str(tmp_path / "user" / engine._EPHEMERIS_FILE)
    assert engine.ephemeris_path() == engine.user_ephemeris_path()
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / engine._EPHEMERIS_FILE).write_bytes(b"")       # an installation ≤ 4.3.1
    assert engine.ephemeris_path() == str(tmp_path / "data" / engine._EPHEMERIS_FILE)


def test_the_published_file():
    """The real ephemeris, when present, is the one the engine expects."""
    path = engine.ephemeris_path()
    if not os.path.isfile(path):
        pytest.skip("no ephemeris")
    assert os.path.getsize(path) == engine._EPHEMERIS_SIZE
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    assert digest.hexdigest() == engine._EPHEMERIS_SHA256


def test_not_in_the_application():
    """celeste.spec does not bundle the ephemeris: updates are lighter."""
    with open(os.path.join(ROOT, "celeste.spec"), encoding="utf-8") as f:
        spec = f.read()
    assert "de440" not in spec and ".bsp" not in spec
