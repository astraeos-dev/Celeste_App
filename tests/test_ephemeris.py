"""
tests/test_ephemeris.py — Téléchargement de l'éphéméride JPL DE440, sans réseau
================================================================================
L'éphéméride n'est pas dans le programme d'installation : Céleste la
télécharge une fois dans ~/.celeste, la vérifie (taille et SHA-256 du fichier
de la NAIF) et ne lui donne son nom qu'ensuite.
"""
import hashlib
import io
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import engine  # noqa: E402

PAYLOAD = b"DAF/SPK " + bytes(range(256)) * 40          # une « éphéméride »


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
    """Le serveur de la NAIF répond PAYLOAD, que le moteur attend."""
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
        raise OSError("pas de réseau")
    monkeypatch.setattr(engine.urllib.request, "urlopen", urlopen)
    with pytest.raises(engine.EphemerisUnavailable, match="pas de réseau") as error:
        engine.download_ephemeris(str(tmp_path / engine._EPHEMERIS_FILE))
    assert not isinstance(error.value, engine.DownloadCancelled)
    assert list(tmp_path.iterdir()) == []


def test_downloaded_into_the_user_folder(tmp_path, monkeypatch):
    """Sans éphéméride nulle part, elle est téléchargée dans ~/.celeste (ou $CELESTE_DATA)."""
    monkeypatch.setattr(engine, "_DATA_DIRS", (str(tmp_path / "data"), str(tmp_path / "user")))
    assert engine.user_ephemeris_path() == str(tmp_path / "user" / engine._EPHEMERIS_FILE)
    assert engine.ephemeris_path() == engine.user_ephemeris_path()
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / engine._EPHEMERIS_FILE).write_bytes(b"")       # une installation ≤ 4.3.1
    assert engine.ephemeris_path() == str(tmp_path / "data" / engine._EPHEMERIS_FILE)


def test_the_published_file():
    """La vraie éphéméride, si elle est là, est bien celle que le moteur attend."""
    path = engine.ephemeris_path()
    if not os.path.isfile(path):
        pytest.skip("éphéméride absente")
    assert os.path.getsize(path) == engine._EPHEMERIS_SIZE
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    assert digest.hexdigest() == engine._EPHEMERIS_SHA256


def test_not_in_the_application():
    """celeste.spec n'emporte pas l'éphéméride : les mises à jour en sont allégées."""
    with open(os.path.join(ROOT, "celeste.spec"), encoding="utf-8") as f:
        spec = f.read()
    assert "de440" not in spec and ".bsp" not in spec
