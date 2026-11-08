"""
updater.py — Updates of Céleste
================================
The latest published version (GitHub Release of astraeos-dev/Celeste_App) is
compared with APP_VERSION; when it is newer, its installer
(Celeste-<version>-Setup.exe) is downloaded, its SHA-256 checksum verified
against the one published with it (.sha256), then it runs silently: it
installs the new version over the old one (same Inno Setup AppId), keeping
settings and favourites, and reopens Céleste.

The Releases are created by the "Build — Windows application" workflow when
APP_VERSION changes on master. This module does not depend on Qt.
"""
import hashlib
import json
import os
import re
import sys
import tempfile
import urllib.request

from config import APP_VERSION

REPOSITORY = "astraeos-dev/Celeste_App"
LATEST_RELEASE_API = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
_SETUP = re.compile(r"^Celeste-(?P<version>[\d.]+)-Setup\.exe$")


class UpdateError(RuntimeError):
    """An update could not be checked, downloaded or verified."""


def parse_version(text):
    """"v4.2.1" → (4, 2, 1); "4.2" → (4, 2, 0)."""
    numbers = [int(n) for n in re.findall(r"\d+", text or "")[:3]]
    if not numbers:
        raise ValueError(f"version illisible : {text!r}")
    return tuple(numbers + [0] * (3 - len(numbers)))


def is_newer(remote, local=APP_VERSION):
    return parse_version(remote) > parse_version(local)


def _request(url):
    return urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": f"Celeste/{APP_VERSION} (+https://github.com/{REPOSITORY})"})


def latest_release(timeout=10):
    """
    The latest published Release (neither a draft nor a pre-release).

    Returns:
        dict | None: version, tag, notes, page (address of the Release),
        setup_url, setup_name, setup_size, sha256_url; None when the Release
        has no installer.
    """
    try:
        with urllib.request.urlopen(_request(LATEST_RELEASE_API), timeout=timeout) as resp:
            release = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:                                  # network, 404 without a Release, JSON
        raise UpdateError(str(exc)) from exc
    assets = {a.get("name", ""): a for a in release.get("assets", [])}
    setup = next((a for name, a in assets.items() if _SETUP.match(name)), None)
    if setup is None:
        return None
    checksum = assets.get(setup["name"] + ".sha256")
    return {
        "version": _SETUP.match(setup["name"])["version"],
        "tag": release.get("tag_name", ""),
        "notes": release.get("body") or "",
        "page": release.get("html_url", f"https://github.com/{REPOSITORY}/releases"),
        "setup_url": setup["browser_download_url"],
        "setup_name": setup["name"],
        "setup_size": int(setup.get("size") or 0),
        "sha256_url": checksum["browser_download_url"] if checksum else None,
    }


def plain_notes(markdown):
    """
    A release note (the Release's Markdown, from CHANGELOG.md) as plain text
    for the update window: headings, bold, code and links without their
    markup, "•" bullets, continuation lines joined to their bullet.
    """
    lines = []
    for raw in (markdown or "").replace("\r\n", "\n").split("\n"):
        line = re.sub(r"^#{1,6}\s*", "", raw.rstrip())
        line = re.sub(r"\*\*(.+?)\*\*|__(.+?)__", lambda m: m.group(1) or m.group(2), line)
        line = re.sub(r"`([^`]*)`", r"\1", line)
        line = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", line)
        bullet = re.match(r"^[-*+]\s+(.*)", line)
        if bullet:
            lines.append("• " + bullet.group(1))
        elif line.startswith((" ", "\t")) and line.strip() and lines and lines[-1].startswith("• "):
            lines[-1] += " " + line.strip()
        else:
            lines.append(line.strip())
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def can_self_update():
    """An application installed on Windows (PyInstaller executable) updates itself;
    from the sources, it is git pull."""
    return bool(getattr(sys, "frozen", False)) and sys.platform == "win32"


def sha256_of(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def expected_sha256(url, timeout=10):
    """Checksum published with the installer ("<hex>  <name>")."""
    try:
        with urllib.request.urlopen(_request(url), timeout=timeout) as resp:
            text = resp.read(4096).decode("ascii", "replace")
    except Exception as exc:
        raise UpdateError(str(exc)) from exc
    match = re.search(r"\b[0-9a-fA-F]{64}\b", text)
    if not match:
        raise UpdateError("unreadable SHA-256 checksum")
    return match.group(0).lower()


def download(release, progress=None, cancelled=None, timeout=30):
    """
    Downloads and verifies the installer of *release*.

    Args:
        progress: called with (bytes received, total size).
        cancelled: returns True to interrupt.

    Returns:
        str: path of the verified installer.
    """
    if not release.get("sha256_url"):
        raise UpdateError("no SHA-256 checksum published with this version")
    expected = expected_sha256(release["sha256_url"], timeout)
    folder = os.path.join(tempfile.gettempdir(), "Celeste-update")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, release["setup_name"])
    try:
        with urllib.request.urlopen(_request(release["setup_url"]), timeout=timeout) as resp, \
                open(path, "wb") as out:
            total = int(resp.headers.get("Content-Length") or release.get("setup_size") or 0)
            done = 0
            while True:
                if cancelled is not None and cancelled():
                    raise UpdateError("download interrupted")
                block = resp.read(1 << 16)
                if not block:
                    break
                out.write(block)
                done += len(block)
                if progress is not None:
                    progress(done, total)
    except UpdateError:
        _remove(path)
        raise
    except Exception as exc:
        _remove(path)
        raise UpdateError(str(exc)) from exc
    if sha256_of(path) != expected:
        _remove(path)
        raise UpdateError("different SHA-256 checksum: corrupt file")
    return path


def _remove(path):
    try:
        os.remove(path)
    except OSError:
        pass


def installer_command(setup_path, app_dir=None):
    """
    The installer in silent mode: a progress window only, Céleste closed then
    reopened ([Run] … skipifnotsilent of installer/celeste.iss), in the same
    mode as the first installation (all users when Céleste is in Program
    Files). Installation log: install.log, next to the installer
    (%TEMP%\\Celeste-update).
    """
    app_dir = os.path.normcase(os.path.abspath(app_dir or os.path.dirname(sys.executable)))
    program_files = [os.environ.get(k) for k in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432")]
    machine = any(p and app_dir.startswith(os.path.normcase(os.path.abspath(p))) for p in program_files)
    log = os.path.join(os.path.dirname(os.path.abspath(setup_path)), "install.log")
    return [setup_path, "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS",
            "/ALLUSERS" if machine else "/CURRENTUSER", f"/LOG={log}"]


def launch_installer(setup_path):
    """Runs the installer, detached from Céleste, which is about to close."""
    import subprocess
    flags = 0
    if sys.platform == "win32":
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(installer_command(setup_path), close_fds=True, creationflags=flags)
