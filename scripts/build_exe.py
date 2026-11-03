"""
scripts/build_exe.py — Construit Céleste en application autonome
==================================================================
1. place l'éphéméride JPL DE440 dans data/ (copiée de ~/.celeste, ou
   téléchargée la première fois) : l'application fonctionne hors ligne ;
2. dessine les icônes (build/icons/celeste.ico et .icns) depuis
   assets/astraeos-icone.svg ;
3. lance PyInstaller avec celeste.spec ;
4. vérifie que l'application construite démarre (--self-test) ;
5. réunit le résultat dans dist/Celeste-<version>-<système>.zip.

Usage : python scripts/build_exe.py            (pip install pyinstaller)
"""
import os
import platform
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def ensure_ephemeris():
    import engine
    target = os.path.join(ROOT, "data", engine._EPHEMERIS_FILE)
    if os.path.isfile(target):
        return target
    engine.load_ephemeris()                       # téléchargée dans ~/.celeste au besoin
    os.makedirs(os.path.dirname(target), exist_ok=True)
    shutil.copyfile(engine.ephemeris_path(), target)
    return target


def make_icons():
    """Icônes Windows (.ico) et macOS (.icns) rendues depuis le SVG du design system."""
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
    icon.save(os.path.join(out, "celeste.icns"))


def executable():
    dist = os.path.join(ROOT, "dist")
    if sys.platform == "darwin":
        return os.path.join(dist, "Celeste.app", "Contents", "MacOS", "Celeste")
    return os.path.join(dist, "Celeste", "Celeste.exe" if os.name == "nt" else "Celeste")


def self_test():
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    result = subprocess.run([executable(), "--self-test"], env=env, capture_output=True,
                            text=True, timeout=600)
    print(result.stdout.strip() or result.stderr.strip())
    if result.returncode != 0 or "self-test OK" not in result.stdout:
        sys.exit(f"l'application construite ne démarre pas (code {result.returncode})")


def package():
    from config import APP_VERSION
    system = {"darwin": "macOS", "win32": "Windows"}.get(sys.platform, platform.system())
    base = os.path.join(ROOT, "dist", f"Celeste-{APP_VERSION}-{system}")
    folder = "Celeste.app" if sys.platform == "darwin" else "Celeste"
    archive = shutil.make_archive(base, "zip", os.path.join(ROOT, "dist"), folder)
    print("archive :", archive)


def main():
    print("éphéméride :", ensure_ephemeris())
    make_icons()
    subprocess.check_call([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
                           "celeste.spec"], cwd=ROOT)
    self_test()
    package()


if __name__ == "__main__":
    if "--self-test" in sys.argv[1:]:
        self_test()
    else:
        main()
