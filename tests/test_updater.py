"""
tests/test_updater.py — Mises à jour de Céleste (updater.py), sans réseau
"""
import hashlib
import io
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import updater  # noqa: E402

SETUP = b"MZ" + b"\x00" * 5000          # un « programme d'installation »


class _Response(io.BytesIO):
    def __init__(self, data, length=True):
        super().__init__(data)
        self.headers = {"Content-Length": str(len(data))} if length else {}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _release(version="9.1", with_checksum=True):
    assets = [{"name": f"Celeste-{version}-Setup.exe", "size": len(SETUP),
               "browser_download_url": f"https://example.test/Celeste-{version}-Setup.exe"}]
    if with_checksum:
        assets.append({"name": f"Celeste-{version}-Setup.exe.sha256",
                       "browser_download_url": f"https://example.test/Celeste-{version}-Setup.exe.sha256"})
    return {"tag_name": f"v{version}", "body": "## Nouveautés\n- tout", "assets": assets,
            "html_url": f"https://github.com/astraeos-dev/Celeste_App/releases/tag/v{version}"}


@pytest.fixture
def network(monkeypatch, tmp_path):
    """Réponses simulées : la Release, l'installateur et son empreinte."""
    files = {"release": _release(), "checksum": hashlib.sha256(SETUP).hexdigest()}

    def urlopen(request, timeout=None):
        url = request.full_url
        if url == updater.LATEST_RELEASE_API:
            return _Response(json.dumps(files["release"]).encode())
        if url.endswith(".sha256"):
            return _Response(f"{files['checksum']}  Celeste-9.1-Setup.exe\n".encode())
        return _Response(SETUP)
    monkeypatch.setattr(updater.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(updater.tempfile, "gettempdir", lambda: str(tmp_path))
    return files


class TestVersions:
    def test_parse(self):
        assert updater.parse_version("v4.2.1") == (4, 2, 1)
        assert updater.parse_version("4.3") == (4, 3, 0)

    def test_newer(self):
        assert updater.is_newer("4.10", "4.9")
        assert updater.is_newer("4.2.1", "4.2")
        assert not updater.is_newer("4.2", "4.2.0")
        assert not updater.is_newer("4.1", "4.2")


class TestLatestRelease:
    def test_reads_the_installer_and_its_checksum(self, network):
        release = updater.latest_release()
        assert release["version"] == "9.1" and release["tag"] == "v9.1"
        assert release["setup_url"].endswith("Celeste-9.1-Setup.exe")
        assert release["sha256_url"].endswith(".sha256")
        assert "Nouveautés" in release["notes"]

    def test_no_installer_in_the_release(self, network):
        network["release"]["assets"] = []
        assert updater.latest_release() is None

    def test_network_error(self, monkeypatch):
        def fail(*_a, **_k):
            raise OSError("pas de réseau")
        monkeypatch.setattr(updater.urllib.request, "urlopen", fail)
        with pytest.raises(updater.UpdateError):
            updater.latest_release()


class TestDownload:
    def test_download_and_check(self, network):
        seen = []
        path = updater.download(updater.latest_release(), progress=lambda d, n: seen.append((d, n)))
        assert open(path, "rb").read() == SETUP
        assert seen[-1] == (len(SETUP), len(SETUP))

    def test_corrupted_download_is_removed(self, network):
        network["checksum"] = "0" * 64
        release = updater.latest_release()
        with pytest.raises(updater.UpdateError, match="SHA-256"):
            updater.download(release)
        assert not os.path.exists(os.path.join(updater.tempfile.gettempdir(), "Celeste-update",
                                               "Celeste-9.1-Setup.exe"))

    def test_refused_without_checksum(self, network):
        network["release"] = _release(with_checksum=False)
        with pytest.raises(updater.UpdateError, match="SHA-256"):
            updater.download(updater.latest_release())

    def test_cancelled(self, network):
        with pytest.raises(updater.UpdateError, match="interrompu"):
            updater.download(updater.latest_release(), cancelled=lambda: True)


class TestInstaller:
    def test_silent_and_current_user(self, tmp_path):
        command = updater.installer_command("Setup.exe", str(tmp_path / "Celeste"))
        assert command[0] == "Setup.exe" and "/SILENT" in command and "/CURRENTUSER" in command

    def test_all_users_under_program_files(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ProgramFiles", str(tmp_path / "Program Files"))
        command = updater.installer_command("Setup.exe", str(tmp_path / "Program Files" / "Celeste"))
        assert "/ALLUSERS" in command

    def test_only_an_installed_windows_application_updates_itself(self, monkeypatch):
        monkeypatch.setattr(updater.sys, "frozen", False, raising=False)
        assert not updater.can_self_update()
        monkeypatch.setattr(updater.sys, "frozen", True, raising=False)
        monkeypatch.setattr(updater.sys, "platform", "win32")
        assert updater.can_self_update()

    def test_installer_relaunches_celeste_after_a_silent_update(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        script = open(os.path.join(root, "installer", "celeste.iss"), encoding="utf-8-sig").read()
        assert "skipifnotsilent" in script and "commandline" in script
