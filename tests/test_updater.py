"""
tests/test_updater.py — Updates of Céleste (updater.py), without network
"""
import hashlib
import io
import json
import os
import sys

import urllib.error

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import updater  # noqa: E402

SETUP = b"MZ" + b"\x00" * 5000          # an "installer"


class _Response(io.BytesIO):
    def __init__(self, data, length=True, url=None):
        super().__init__(data)
        self.headers = {"Content-Length": str(len(data))} if length else {}
        self.url = url

    def geturl(self):
        return self.url

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


API_SETUP = "https://api.example.test/releases/assets/1"
API_CHECKSUM = "https://api.example.test/releases/assets/2"


def _release(version="9.1", with_checksum=True):
    assets = [{"name": f"Celeste-{version}-Setup.exe", "size": len(SETUP), "url": API_SETUP,
               "browser_download_url": f"https://example.test/Celeste-{version}-Setup.exe"}]
    if with_checksum:
        assets.append({"name": f"Celeste-{version}-Setup.exe.sha256", "url": API_CHECKSUM,
                       "browser_download_url": f"https://example.test/Celeste-{version}-Setup.exe.sha256"})
    return {"tag_name": f"v{version}", "body": "## What's new\n- everything", "assets": assets,
            "html_url": f"https://github.com/astraeos-dev/Celeste_App/releases/tag/v{version}"}


@pytest.fixture
def network(monkeypatch, tmp_path):
    """Simulated answers: the Release, the installer and its checksum, through the
    API or github.com. files["fail"]: addresses that answer 504 (all with "*");
    files["requests"]: (address, Accept) of each request."""
    files = {"release": _release(), "checksum": hashlib.sha256(SETUP).hexdigest(),
             "fail": set(), "truncate": 0, "requests": [],
             "tag_page": "https://github.com/astraeos-dev/Celeste_App/releases/tag/v9.1"}

    def urlopen(request, timeout=None):
        url = request.full_url
        files["requests"].append((url, request.get_header("Accept")))
        if url in files["fail"]:
            raise urllib.error.HTTPError(url, 503, "Service Unavailable", {}, None)
        if url == updater.LATEST_RELEASE_API:
            return _Response(json.dumps(files["release"]).encode())
        if url == updater.LATEST_RELEASE_PAGE:
            assert request.get_method() == "HEAD"
            return _Response(b"", url=files["tag_page"])
        if "*" in files["fail"]:
            raise urllib.error.HTTPError(url, 504, "Gateway Timeout", {}, None)
        if url.endswith(".sha256") or url == API_CHECKSUM:
            return _Response(f"{files['checksum']}  Celeste-9.1-Setup.exe\n".encode())
        if files["truncate"]:
            files["truncate"] -= 1
            response = _Response(SETUP[:1000])
            response.headers["Content-Length"] = str(len(SETUP))
            return response
        return _Response(SETUP)
    monkeypatch.setattr(updater.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(updater.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(updater, "_RETRY_DELAY_S", 0.0)
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
        assert release["setup_api_url"] == API_SETUP and release["sha256_api_url"] == API_CHECKSUM
        assert "What's new" in release["notes"]

    def test_no_installer_in_the_release(self, network):
        network["release"]["assets"] = []
        assert updater.latest_release() is None

    def test_network_error(self, monkeypatch, tmp_path):
        def fail(*_a, **_k):
            raise OSError("no network")
        monkeypatch.setattr(updater.urllib.request, "urlopen", fail)
        monkeypatch.setattr(updater.tempfile, "gettempdir", lambda: str(tmp_path))
        monkeypatch.setattr(updater, "_RETRY_DELAY_S", 0.0)
        with pytest.raises(updater.UpdateError, match="no network"):
            updater.latest_release()

    def test_github_com_when_the_api_fails(self, network):
        """v4.7.1: the API answers 503 (GitHub incident for applications without an
        account); github.com's latest-release page redirects to the tag."""
        network["fail"] = {updater.LATEST_RELEASE_API}
        release = updater.latest_release()
        assert release["version"] == "9.1" and release["tag"] == "v9.1" and release["notes"] == ""
        assert release["page"].endswith("/releases/tag/v9.1")
        assert release["setup_url"] == ("https://github.com/astraeos-dev/Celeste_App/releases/download/"
                                        "v9.1/Celeste-9.1-Setup.exe")
        assert release["sha256_url"] == release["setup_url"] + ".sha256"
        assert release["setup_api_url"] is None
        assert open(updater.download(release), "rb").read() == SETUP
        assert "503" in open(updater.log_path(), encoding="utf-8").read()

    def test_both_routes_fail_three_times(self, network):
        network["fail"] = {updater.LATEST_RELEASE_API, updater.LATEST_RELEASE_PAGE}
        with pytest.raises(updater.UpdateError, match="github.com: HTTP Error 503"):
            updater.latest_release()
        assert len(network["requests"]) == 2 * updater._ATTEMPTS

    def test_page_without_a_version(self, network):
        network["fail"] = {updater.LATEST_RELEASE_API}
        network["tag_page"] = "https://github.com/astraeos-dev/Celeste_App/releases"
        with pytest.raises(updater.UpdateError, match="no published version"):
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
        with pytest.raises(updater.UpdateCancelled, match="interrupted"):
            updater.download(updater.latest_release(), cancelled=lambda: True)

    def test_through_the_api_first(self, network):
        updater.download(updater.latest_release())
        files = [r for r in network["requests"] if r[0] != updater.LATEST_RELEASE_API]
        assert files == [(API_CHECKSUM, "application/octet-stream"),
                         (API_SETUP, "application/octet-stream")]

    def test_github_com_when_the_api_fails(self, network):
        """v4.7.1: the API answers 503, github.com takes over; the failure is logged."""
        network["fail"] = {API_CHECKSUM, API_SETUP}
        path = updater.download(updater.latest_release())
        assert open(path, "rb").read() == SETUP
        log = open(updater.log_path(), encoding="utf-8").read()
        assert "503" in log and API_SETUP in log and "downloaded and verified" in log

    def test_three_rounds_then_the_last_error(self, network):
        network["fail"] = {"*"}
        with pytest.raises(updater.UpdateError, match="example.test: HTTP Error 504"):
            updater.download(updater.latest_release())
        tries = [r for r in network["requests"] if r[0] != updater.LATEST_RELEASE_API]
        assert len(tries) == 2 * updater._ATTEMPTS                  # API and github.com, three rounds

    def test_incomplete_download_is_retried(self, network):
        network["truncate"] = 1
        path = updater.download(updater.latest_release())
        assert open(path, "rb").read() == SETUP
        assert "incomplete download (1000 of 5002 bytes)" in open(updater.log_path(), encoding="utf-8").read()

    def test_corrupt_file_is_not_downloaded_again(self, network):
        network["checksum"] = "0" * 64
        with pytest.raises(updater.UpdateError, match="SHA-256"):
            updater.download(updater.latest_release())
        tries = [r for r in network["requests"] if r[0] == API_SETUP or r[0].endswith(".exe")]
        assert len(tries) == 1

    def test_release_of_an_older_version_without_api_addresses(self, network):
        """A release dict without the API addresses (a test, an old cache): github.com only."""
        release = dict(updater.latest_release(), setup_api_url=None, sha256_api_url=None)
        assert open(updater.download(release), "rb").read() == SETUP


class TestInstaller:
    def test_silent_and_current_user(self, tmp_path):
        command = updater.installer_command("Setup.exe", str(tmp_path / "Celeste"))
        assert command[0] == "Setup.exe" and "/SILENT" in command and "/CURRENTUSER" in command
        assert command[-1].startswith("/LOG=") and command[-1].endswith("install.log")

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


class TestPlainNotes:
    def test_changelog_section(self):
        text = "- First line\n  going on\n- **Bold**, `code` and a [link](https://x.test)"
        assert updater.plain_notes(text) == "• First line going on\n• Bold, code and a link"

    def test_notes_generated_by_github(self):
        """The notes of Releases ≤ 4.4 (generated by GitHub) stay readable."""
        text = "## What's Changed\r\n* Version 4.4 by @x in https://x.test/pull/28\r\n\r\n\r\n**Full Changelog**: v4.3.1...v4.4"
        assert updater.plain_notes(text) == ("What's Changed\n• Version 4.4 by @x in https://x.test/pull/28"
                                             "\n\nFull Changelog: v4.3.1...v4.4")

    def test_empty(self):
        assert updater.plain_notes("") == "" and updater.plain_notes(None) == ""


def test_a_beta_is_replaced_by_the_release_of_its_version():
    """4.12 beta 3 updates itself to 4.12, not to an older release; a release does not
    go back to the same version."""
    assert updater.is_newer("4.12", "4.12", beta=3)
    assert not updater.is_newer("4.11", "4.12", beta=3)
    assert updater.is_newer("4.13", "4.12", beta=3)
    assert not updater.is_newer("4.12", "4.12", beta=0)


def test_beta_build_info(tmp_path, monkeypatch):
    """scripts/build_exe.py writes the beta number that config reads (APP_RELEASE)."""
    import importlib
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
    import build_exe
    monkeypatch.setattr(build_exe, "ROOT", str(tmp_path))
    monkeypatch.setenv("CELESTE_BETA", "7")
    assert build_exe.write_build_info() == 7
    monkeypatch.syspath_prepend(str(tmp_path))
    sys.modules.pop("_build_info", None)
    import config
    try:
        importlib.reload(config)
        assert config.APP_BETA == 7 and config.APP_RELEASE == f"{config.APP_VERSION}-beta.7"
    finally:
        sys.modules.pop("_build_info", None)
        (tmp_path / "_build_info.py").unlink()
        importlib.reload(config)
    assert config.APP_BETA == 0 and config.APP_RELEASE == config.APP_VERSION


def _build_exe():
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
    import build_exe
    return build_exe


def test_sign_command():
    """The signature: SHA-256, the certificate, its password, a timestamp."""
    build_exe = _build_exe()
    command = build_exe.sign_command("dist/Celeste.exe", "signtool.exe", "cert.pfx", "secret")
    assert command[:2] == ["signtool.exe", "sign"]
    assert command[command.index("/fd") + 1] == "SHA256"
    assert command[command.index("/f") + 1] == "cert.pfx"
    assert command[command.index("/p") + 1] == "secret"
    assert command[command.index("/tr") + 1] == build_exe.TIMESTAMP_URL
    assert command[-1] == "dist/Celeste.exe"
    assert "/p" not in build_exe.sign_command("a.exe", "signtool.exe", "cert.pfx", "")
    token = build_exe.sign_command("a.exe", "signtool.exe", thumbprint="ABC123")
    assert token[token.index("/sha1") + 1] == "ABC123" and "/f" not in token


def test_unsigned_without_certificate(monkeypatch):
    """No CELESTE_SIGN_PFX: the build goes on, unsigned."""
    build_exe = _build_exe()
    monkeypatch.delenv("CELESTE_SIGN_PFX", raising=False)
    monkeypatch.delenv("CELESTE_SIGN_THUMBPRINT", raising=False)
    assert build_exe.sign("whatever.exe") is False
    monkeypatch.setenv("CELESTE_SIGN_PFX", "/no/such/cert.pfx")
    with pytest.raises(SystemExit):
        build_exe.sign("whatever.exe")
