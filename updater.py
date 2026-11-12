"""
updater.py — Updates of Céleste
================================
The latest published version (GitHub Release of astraeos-dev/Celeste_App) is
compared with APP_VERSION; when it is newer, its installer
(Celeste-<version>-Setup.exe) is downloaded, its SHA-256 checksum verified
against the one published with it (.sha256), then it runs silently: it
installs the new version over the old one (same Inno Setup AppId), keeping
settings and favourites, and reopens Céleste.

v4.7.1: the latest version and its files are asked to the GitHub API, then to
github.com, for up to three rounds (either can answer 503 or 504 for a while,
as during GitHub incidents that touch applications without an account); each
failure goes to update.log, next to the installer.

The Releases are created by the "Build — Windows application" workflow when
APP_VERSION changes on master. This module does not depend on Qt.
"""
import hashlib
import json
import os
import re
import sys
import tempfile
import time
import urllib.parse
import urllib.request

from config import APP_BETA, APP_VERSION

REPOSITORY = "astraeos-dev/Celeste_App"
LATEST_RELEASE_API = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
LATEST_RELEASE_PAGE = f"https://github.com/{REPOSITORY}/releases/latest"
_SETUP = re.compile(r"^Celeste-(?P<version>[\d.]+)-Setup\.exe$")
_TAG_PAGE = re.compile(r"/releases/tag/(?P<tag>v?(?P<version>\d+(?:\.\d+)*))/?$")
_ASSET = "application/octet-stream"     # a Release file, through the API or github.com
_ATTEMPTS = 3                           # rounds over the sources (API, then github.com)
_RETRY_DELAY_S = 2.0                    # pause before the 2nd round; twice as long before the 3rd


class UpdateError(RuntimeError):
    """An update could not be checked, downloaded or verified."""


class UpdateCancelled(UpdateError):
    """The user interrupted the download."""


class CorruptDownload(UpdateError):
    """A complete file whose checksum differs: downloading it again would not help."""


def parse_version(text):
    """"v4.2.1" → (4, 2, 1); "4.2" → (4, 2, 0)."""
    numbers = [int(n) for n in re.findall(r"\d+", text or "")[:3]]
    if not numbers:
        raise ValueError(f"unreadable version: {text!r}")
    return tuple(numbers + [0] * (3 - len(numbers)))


def is_newer(remote, local=APP_VERSION, beta=None):
    """Whether *remote* is a newer release; a beta build is replaced by the release of its
    own version (4.12 beta 3 → 4.12)."""
    beta = APP_BETA if beta is None else beta
    if beta and parse_version(remote) == parse_version(local):
        return True
    return parse_version(remote) > parse_version(local)


def _request(url, accept="application/vnd.github+json"):
    return urllib.request.Request(url, headers={
        "Accept": accept,
        "User-Agent": f"Celeste/{APP_VERSION} (+https://github.com/{REPOSITORY})"})


def update_folder():
    """Where the installer, update.log and the installer's install.log go."""
    return os.path.join(tempfile.gettempdir(), "Celeste-update")


def log_path():
    return os.path.join(update_folder(), "update.log")


def log(message):
    """Adds a dated line to update.log, to find out why an update failed."""
    try:
        os.makedirs(update_folder(), exist_ok=True)
        with open(log_path(), "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}  Céleste {APP_VERSION}  {message}\n")
    except OSError:
        pass


def latest_release(timeout=10):
    """
    The latest published Release (neither a draft nor a pre-release), asked to
    the GitHub API, then to github.com, for up to three rounds: either can fail
    for a while for applications without an account (503, 504, timeouts).

    Returns:
        dict | None: version, tag, notes, page (address of the Release),
        setup_url, setup_name, setup_size, sha256_url (github.com links),
        setup_api_url, sha256_api_url (the same files through the API, None
        when the answer came from github.com); None when the Release has no
        installer.
    """
    def ask(url, _accept):
        return _release_from_api(timeout) if url == LATEST_RELEASE_API else _release_from_page(timeout)
    return _with_retries([(LATEST_RELEASE_API, None), (LATEST_RELEASE_PAGE, None)], ask)


def _release_from_api(timeout):
    with urllib.request.urlopen(_request(LATEST_RELEASE_API), timeout=timeout) as resp:
        release = json.loads(resp.read().decode("utf-8"))
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
        "setup_api_url": setup.get("url"),
        "sha256_api_url": checksum.get("url") if checksum else None,
    }


def _release_from_page(timeout):
    """
    Without the API: github.com/<repository>/releases/latest redirects to the
    page of the latest tag, and the files of a Release have fixed names. The
    note is not read (the page is HTML): the window shows the version only.
    """
    request = urllib.request.Request(LATEST_RELEASE_PAGE, method="HEAD", headers={
        "User-Agent": f"Celeste/{APP_VERSION} (+https://github.com/{REPOSITORY})"})
    with urllib.request.urlopen(request, timeout=timeout) as resp:
        page = resp.geturl()
    match = _TAG_PAGE.search(urllib.parse.urlsplit(page).path)
    if not match:
        raise UpdateError(f"no published version ({page})")
    name = f"Celeste-{match['version']}-Setup.exe"
    files = f"https://github.com/{REPOSITORY}/releases/download/{match['tag']}/{name}"
    return {"version": match["version"], "tag": match["tag"], "notes": "", "page": page,
            "setup_url": files, "setup_name": name, "setup_size": 0,
            "sha256_url": files + ".sha256", "setup_api_url": None, "sha256_api_url": None}


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


def expected_sha256(url, timeout=10, accept=_ASSET):
    """Checksum published with the installer ("<hex>  <name>")."""
    try:
        with urllib.request.urlopen(_request(url, accept), timeout=timeout) as resp:
            text = resp.read(4096).decode("ascii", "replace")
    except Exception as exc:
        raise UpdateError(str(exc)) from exc
    match = re.search(r"\b[0-9a-fA-F]{64}\b", text)
    if not match:
        raise UpdateError("unreadable SHA-256 checksum")
    return match.group(0).lower()


def _sources(release, kind):
    """(address, Accept) of the installer (*kind* "setup") or of its checksum
    ("sha256"): through the API first, then the github.com link."""
    urls = (release.get(f"{kind}_api_url"), release.get(f"{kind}_url"))
    return [(url, _ASSET) for url in urls if url]


def _pause(seconds, cancelled):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if cancelled is not None and cancelled():
            raise UpdateCancelled("download interrupted")
        time.sleep(0.1)


def _with_retries(sources, fetch, cancelled=None):
    """
    fetch(url, accept) on each source in turn, for up to _ATTEMPTS rounds;
    the first success wins. Each failure is logged; the last one is raised.
    A cancellation or a corrupt file stops at once.
    """
    last = UpdateError("no download address")
    for attempt in range(_ATTEMPTS):
        if attempt:
            _pause(_RETRY_DELAY_S * attempt, cancelled)
        for url, accept in sources:
            if cancelled is not None and cancelled():
                raise UpdateCancelled("download interrupted")
            try:
                return fetch(url, accept)
            except UpdateCancelled:
                log("cancelled")
                raise
            except Exception as exc:
                last = UpdateError(f"{urllib.parse.urlsplit(url).hostname}: {exc}")
                log(f"attempt {attempt + 1}, {url}: {exc}")
                if isinstance(exc, CorruptDownload):
                    raise last from exc
    raise last


def download(release, progress=None, cancelled=None, timeout=30):
    """
    Downloads and verifies the installer of *release*.

    Args:
        progress: called with (bytes received, total size).
        cancelled: returns True to interrupt.

    Returns:
        str: path of the verified installer.
    """
    checksum_sources = _sources(release, "sha256")
    if not checksum_sources:
        raise UpdateError("no SHA-256 checksum published with this version")
    log(f"downloading {release.get('setup_name')}")
    expected = _with_retries(checksum_sources,
                             lambda url, accept: expected_sha256(url, timeout, accept), cancelled)
    os.makedirs(update_folder(), exist_ok=True)
    path = os.path.join(update_folder(), release["setup_name"])

    def fetch(url, accept):
        try:
            with urllib.request.urlopen(_request(url, accept), timeout=timeout) as resp, \
                    open(path, "wb") as out:
                total = int(resp.headers.get("Content-Length") or release.get("setup_size") or 0)
                done = 0
                while True:
                    if cancelled is not None and cancelled():
                        raise UpdateCancelled("download interrupted")
                    block = resp.read(1 << 16)
                    if not block:
                        break
                    out.write(block)
                    done += len(block)
                    if progress is not None:
                        progress(done, total)
            if total and done != total:
                raise UpdateError(f"incomplete download ({done} of {total} bytes)")
            if sha256_of(path) != expected:
                raise CorruptDownload("different SHA-256 checksum: corrupt file")
            return path
        except BaseException:
            _remove(path)
            raise

    path = _with_retries(_sources(release, "setup"), fetch, cancelled)
    log(f"downloaded and verified: {path}")
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
    install_log = os.path.join(os.path.dirname(os.path.abspath(setup_path)), "install.log")
    return [setup_path, "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS",
            "/ALLUSERS" if machine else "/CURRENTUSER", f"/LOG={install_log}"]


def launch_installer(setup_path):
    """Runs the installer, detached from Céleste, which is about to close."""
    import subprocess
    flags = 0
    if sys.platform == "win32":
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(installer_command(setup_path), close_fds=True, creationflags=flags)
