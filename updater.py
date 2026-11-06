"""
updater.py — Mises à jour de Céleste
=====================================
La dernière version publiée (Release GitHub de astraeos-dev/Celeste_App) est
comparée à APP_VERSION ; si elle est plus récente, son programme
d'installation (Celeste-<version>-Setup.exe) est téléchargé, son empreinte
SHA-256 vérifiée contre celle publiée avec lui (.sha256), puis il est lancé en
mode silencieux : il installe la nouvelle version par-dessus l'ancienne (même
AppId Inno Setup), en gardant réglages et favoris, et rouvre Céleste.

Les Releases sont créées par le workflow « Build — application Windows »
quand APP_VERSION change sur master. Ce module ne dépend pas de Qt.
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
    """Vérification, téléchargement ou contrôle d'une mise à jour impossible."""


def parse_version(text):
    """« v4.2.1 » → (4, 2, 1) ; « 4.2 » → (4, 2, 0)."""
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
    La dernière Release publiée (ni brouillon ni préversion).

    Returns:
        dict | None: version, tag, notes, page (adresse de la Release),
        setup_url, setup_name, setup_size, sha256_url ; None sans programme
        d'installation dans la Release.
    """
    try:
        with urllib.request.urlopen(_request(LATEST_RELEASE_API), timeout=timeout) as resp:
            release = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:                                  # réseau, 404 sans Release, JSON
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


def can_self_update():
    """Une application installée sous Windows (exécutable PyInstaller) se met à jour seule ;
    depuis les sources, c'est git pull."""
    return bool(getattr(sys, "frozen", False)) and sys.platform == "win32"


def sha256_of(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def expected_sha256(url, timeout=10):
    """Empreinte publiée avec le programme d'installation (« <hex>  <nom> »)."""
    try:
        with urllib.request.urlopen(_request(url), timeout=timeout) as resp:
            text = resp.read(4096).decode("ascii", "replace")
    except Exception as exc:
        raise UpdateError(str(exc)) from exc
    match = re.search(r"\b[0-9a-fA-F]{64}\b", text)
    if not match:
        raise UpdateError("empreinte SHA-256 illisible")
    return match.group(0).lower()


def download(release, progress=None, cancelled=None, timeout=30):
    """
    Télécharge et vérifie le programme d'installation de *release*.

    Args:
        progress: appelée avec (octets reçus, taille totale).
        cancelled: renvoie True pour interrompre.

    Returns:
        str: chemin du programme d'installation vérifié.
    """
    if not release.get("sha256_url"):
        raise UpdateError("pas d'empreinte SHA-256 publiée avec cette version")
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
                    raise UpdateError("téléchargement interrompu")
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
        raise UpdateError("empreinte SHA-256 différente : fichier corrompu")
    return path


def _remove(path):
    try:
        os.remove(path)
    except OSError:
        pass


def installer_command(setup_path, app_dir=None):
    """
    Programme d'installation en mode silencieux : fenêtre de progression seule,
    Céleste fermé puis rouvert ([Run] … skipifnotsilent de installer/celeste.iss),
    dans le même mode qu'à la première installation (tous les utilisateurs si
    Céleste est dans Program Files).
    """
    app_dir = os.path.normcase(os.path.abspath(app_dir or os.path.dirname(sys.executable)))
    program_files = [os.environ.get(k) for k in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432")]
    machine = any(p and app_dir.startswith(os.path.normcase(os.path.abspath(p))) for p in program_files)
    return [setup_path, "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS",
            "/ALLUSERS" if machine else "/CURRENTUSER"]


def launch_installer(setup_path):
    """Lance le programme d'installation, détaché de Céleste qui va se fermer."""
    import subprocess
    flags = 0
    if sys.platform == "win32":
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(installer_command(setup_path), close_fds=True, creationflags=flags)
