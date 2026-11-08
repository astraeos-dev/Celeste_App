"""
scripts/build_exe.py — Builds Céleste.exe for Windows
======================================================
1. puts the JPL DE440 ephemeris in ~/.celeste (copied from data/, or
   downloaded) for the check of step 4: it is not in the application, which
   downloads it at its first launch;
2. draws the icon (build/icons/celeste.ico) from assets/astraeos-icone.svg;
3. runs PyInstaller with celeste.spec, and checks that the ephemeris is not in;
4. checks that the built application starts (--self-test);
5. gathers the result in dist/Celeste-<version>-Windows.zip;
6. with Inno Setup 6, builds the installer dist/Celeste-<version>-Setup.exe
   (installer/celeste.iss), with Céleste's icon.

Usage, on Windows: python scripts/build_exe.py      (pip install pyinstaller)
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
    icon.save(os.path.join(out, "celeste.ico"), sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])


def executable():
    return os.path.join(ROOT, "dist", "Celeste", "Celeste.exe" if os.name == "nt" else "Celeste")


def self_test():
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    result = subprocess.run([executable(), "--self-test"], env=env, capture_output=True,
                            text=True, timeout=600)
    print(result.stdout.strip() or result.stderr.strip())
    if result.returncode != 0 or "self-test OK" not in result.stdout:
        sys.exit(f"the built application does not start (code {result.returncode})")


def package():
    from config import APP_VERSION
    system = "Windows" if os.name == "nt" else platform.system()     # Linux: a local try
    base = os.path.join(ROOT, "dist", f"Celeste-{APP_VERSION}-{system}")
    archive = shutil.make_archive(base, "zip", os.path.join(ROOT, "dist"), "Celeste")
    print("archive:", archive)


def iscc():
    """The Inno Setup 6 compiler: $ISCC, the PATH, then its installation folder."""
    candidates = [os.environ.get("ISCC"), shutil.which("ISCC"), shutil.which("iscc")]
    for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles")):
        if base:
            candidates.append(os.path.join(base, "Inno Setup 6", "ISCC.exe"))
    return next((c for c in candidates if c and os.path.isfile(c)), None)


def make_installer():
    """The Inno Setup installer, when the compiler is there (Windows)."""
    from config import APP_VERSION
    compiler = iscc()
    if compiler is None:
        print("Inno Setup 6 not found: no installer")
        return None
    subprocess.check_call([compiler, f"/DAppVersion={APP_VERSION}",
                           os.path.join(ROOT, "installer", "celeste.iss")], cwd=ROOT)
    setup = os.path.join(ROOT, "dist", f"Celeste-{APP_VERSION}-Setup.exe")
    print("installer:", setup)
    return setup


def main():
    print("ephemeris:", ensure_ephemeris())
    make_icons()
    subprocess.check_call([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
                           "celeste.spec"], cwd=ROOT)
    check_no_ephemeris()
    self_test()
    package()
    make_installer()


if __name__ == "__main__":
    if "--self-test" in sys.argv[1:]:
        self_test()
    else:
        main()
