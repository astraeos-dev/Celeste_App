"""
scripts/build_exe.py — Builds Céleste.exe for Windows
======================================================
1. puts the JPL DE440 ephemeris in ~/.celeste (copied from data/, or
   downloaded) for the check of step 4: it is not in the application, which
   downloads it at its first launch;
2. draws the icon (build/icons/celeste.ico) from assets/astraeos-icone.svg, and
   copies it to assets/celeste.ico for the window and the taskbar;
3. runs PyInstaller with celeste.spec, and checks that the ephemeris is not in;
4. checks that the built application starts (--self-test);
5. gathers the result in dist/Celeste-<version>-Windows.zip;
6. with Inno Setup 6, builds the installer dist/Celeste-<version>-Setup.exe
   (installer/celeste.iss), with Céleste's icon.

Signature on this PC: with a code-signing certificate installed in Windows
(a USB token, or Certum SimplySign: since 2023 the keys stay on a hardware
device), CELESTE_SIGN_THUMBPRINT = its SHA-1 thumbprint; with an older .pfx
file, CELESTE_SIGN_PFX (and CELESTE_SIGN_PASSWORD). Celeste.exe and the
installer are then signed with signtool (Windows SDK) and timestamped.
Without either, the build is unsigned. The Build workflow signs the release
installer with SignPath instead (wiki: Publier une version).
"""
import os
import platform
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def ensure_ephemeris():
    """The ephemeris in ~/.celeste, where the built application reads it (--self-test)."""
    import engine
    target = engine.user_ephemeris_path()
    if not os.path.isfile(target):
        local = os.path.join(ROOT, "data", engine._EPHEMERIS_FILE)
        if os.path.isfile(local):
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copyfile(local, target)
        else:
            engine.download_ephemeris(target)
    return target


def check_no_ephemeris():
    """The ephemeris stays out of the application: updates are 32 MB lighter."""
    import engine
    folder = os.path.join(ROOT, "dist", "Celeste")
    found = [os.path.join(d, f) for d, _, files in os.walk(folder) for f in files
             if f == engine._EPHEMERIS_FILE]
    if found:
        sys.exit(f"ephemeris in the application: {found}")


def make_icons():
    """Windows icon (.ico) drawn from the design system's SVG."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PIL import Image
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QGuiApplication, QImage, QPainter
    from PyQt6.QtSvg import QSvgRenderer

    app = QGuiApplication.instance() or QGuiApplication([])  # noqa: F841 (needed to paint)
    out = os.path.join(ROOT, "build", "icons")
    os.makedirs(out, exist_ok=True)
    png = os.path.join(out, "celeste.png")
    image = QImage(1024, 1024, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    QSvgRenderer(os.path.join(ROOT, "assets", "astraeos-icone.svg")).render(painter)
    painter.end()
    image.save(png)
    icon = Image.open(png)
    sizes = [(s, s) for s in (16, 20, 24, 32, 40, 48, 64, 128, 256)]
    icon.save(os.path.join(out, "celeste.ico"), sizes=sizes)
    # the same icon inside the application: the window and the taskbar (icons.app_icon)
    shutil.copyfile(os.path.join(out, "celeste.ico"), os.path.join(ROOT, "assets", "celeste.ico"))


def executable():
    return os.path.join(ROOT, "dist", "Celeste", "Celeste.exe" if os.name == "nt" else "Celeste")


def self_test():
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    result = subprocess.run([executable(), "--self-test"], env=env, capture_output=True,
                            text=True, timeout=600)
    print(result.stdout.strip() or result.stderr.strip())
    if result.returncode != 0 or "self-test OK" not in result.stdout:
        sys.exit(f"the built application does not start (code {result.returncode})")


def write_build_info():
    """_build_info.py: the beta number of this build (CELESTE_BETA), 0 for a release."""
    beta = int(os.environ.get("CELESTE_BETA") or 0)
    with open(os.path.join(ROOT, "_build_info.py"), "w", encoding="utf-8") as f:
        f.write(f'"""Written by scripts/build_exe.py."""\nBETA = {beta}\n')
    return beta


def release_name():
    """4.12, or 4.12-beta.3 for a beta build (read after write_build_info())."""
    import importlib
    import config
    importlib.reload(config)
    return config.APP_RELEASE


def package():
    system = "Windows" if os.name == "nt" else platform.system()     # Linux: a local try
    base = os.path.join(ROOT, "dist", f"Celeste-{release_name()}-{system}")
    archive = shutil.make_archive(base, "zip", os.path.join(ROOT, "dist"), "Celeste")
    print("archive:", archive)


def iscc():
    """The Inno Setup 6 compiler: $ISCC, the PATH, then its installation folder."""
    candidates = [os.environ.get("ISCC"), shutil.which("ISCC"), shutil.which("iscc")]
    for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles")):
        if base:
            candidates.append(os.path.join(base, "Inno Setup 6", "ISCC.exe"))
    return next((c for c in candidates if c and os.path.isfile(c)), None)


TIMESTAMP_URL = "http://timestamp.digicert.com"


def signtool():
    """signtool.exe: $SIGNTOOL, the PATH, then the newest Windows SDK."""
    candidates = [os.environ.get("SIGNTOOL"), shutil.which("signtool")]
    base = os.environ.get("ProgramFiles(x86)")
    if base:
        kits = os.path.join(base, "Windows Kits", "10", "bin")
        if os.path.isdir(kits):
            for version in sorted(os.listdir(kits), reverse=True):
                candidates.append(os.path.join(kits, version, "x64", "signtool.exe"))
    return next((c for c in candidates if c and os.path.isfile(c)), None)


def sign_command(path, tool="signtool", pfx=None, password=None, thumbprint=None):
    """The signtool command that signs *path* (SHA-256, timestamped)."""
    command = [tool, "sign", "/fd", "SHA256"]
    if thumbprint:
        command += ["/sha1", thumbprint]
    else:
        command += ["/f", pfx]
        if password:
            command += ["/p", password]
    return command + ["/tr", TIMESTAMP_URL, "/td", "SHA256", "/d", "Céleste", path]


def sign(path):
    """Signs *path* when a certificate is named (CELESTE_SIGN_*); True when signed."""
    thumbprint = os.environ.get("CELESTE_SIGN_THUMBPRINT")
    pfx = os.environ.get("CELESTE_SIGN_PFX")
    if not (thumbprint or pfx):
        return False
    if pfx and not thumbprint and not os.path.isfile(pfx):
        sys.exit(f"CELESTE_SIGN_PFX: no file {pfx}")
    tool = signtool()
    if tool is None:
        sys.exit("signtool.exe not found (Windows SDK): cannot sign")
    subprocess.check_call(sign_command(path, tool, pfx, os.environ.get("CELESTE_SIGN_PASSWORD"), thumbprint))
    subprocess.check_call([tool, "verify", "/pa", path])
    print("signed:", path)
    return True


def make_installer():
    """The Inno Setup installer, when the compiler is there (Windows)."""
    version = release_name()
    compiler = iscc()
    if compiler is None:
        print("Inno Setup 6 not found: no installer")
        return None
    subprocess.check_call([compiler, f"/DAppVersion={version}",
                           os.path.join(ROOT, "installer", "celeste.iss")], cwd=ROOT)
    setup = os.path.join(ROOT, "dist", f"Celeste-{version}-Setup.exe")
    print("installer:", setup)
    sign(setup)
    return setup


def main():
    print("beta:", write_build_info() or "no (a release)")
    print("ephemeris:", ensure_ephemeris())
    make_icons()
    subprocess.check_call([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
                           "celeste.spec"], cwd=ROOT)
    check_no_ephemeris()
    if not sign(executable()):
        print("no certificate (CELESTE_SIGN_THUMBPRINT, CELESTE_SIGN_PFX): unsigned")
    self_test()
    package()
    make_installer()


if __name__ == "__main__":
    if "--self-test" in sys.argv[1:]:
        self_test()
    else:
        main()
