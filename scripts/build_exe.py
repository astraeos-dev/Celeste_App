"""
scripts/build_exe.py — Construit Céleste.exe pour Windows
===========================================================
1. place l'éphéméride JPL DE440 dans ~/.celeste (copiée de data/, ou
   téléchargée) pour l'essai de l'étape 4 : elle n'est pas dans
   l'application, qui la télécharge à son premier lancement ;
2. dessine l'icône (build/icons/celeste.ico) depuis assets/astraeos-icone.svg ;
3. lance PyInstaller avec celeste.spec, et vérifie que l'éphéméride n'y est pas ;
4. vérifie que l'application construite démarre (--self-test) ;
5. réunit le résultat dans dist/Celeste-<version>-Windows.zip ;
6. avec Inno Setup 6, construit le programme d'installation
   dist/Celeste-<version>-Setup.exe (installer/celeste.iss), à l'icône de
   Céleste.

Usage, sous Windows : python scripts/build_exe.py      (pip install pyinstaller)
"""
import os
import platform
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def ensure_ephemeris():
    """L'éphéméride dans ~/.celeste, où l'application construite la lit (--self-test)."""
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
    """L'éphéméride reste hors de l'application : les mises à jour en sont allégées de 32 Mo."""
    import engine
    folder = os.path.join(ROOT, "dist", "Celeste")
    found = [os.path.join(d, f) for d, _, files in os.walk(folder) for f in files
             if f == engine._EPHEMERIS_FILE]
    if found:
        sys.exit(f"éphéméride dans l'application : {found}")


def make_icons():
    """Icône Windows (.ico) rendue depuis le SVG du design system."""
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
        sys.exit(f"l'application construite ne démarre pas (code {result.returncode})")


def package():
    from config import APP_VERSION
    system = "Windows" if os.name == "nt" else platform.system()     # Linux : essai local
    base = os.path.join(ROOT, "dist", f"Celeste-{APP_VERSION}-{system}")
    archive = shutil.make_archive(base, "zip", os.path.join(ROOT, "dist"), "Celeste")
    print("archive :", archive)


def iscc():
    """Compilateur d'Inno Setup 6 : $ISCC, le PATH, puis son dossier d'installation."""
    candidates = [os.environ.get("ISCC"), shutil.which("ISCC"), shutil.which("iscc")]
    for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles")):
        if base:
            candidates.append(os.path.join(base, "Inno Setup 6", "ISCC.exe"))
    return next((c for c in candidates if c and os.path.isfile(c)), None)


def make_installer():
    """Programme d'installation Inno Setup, si le compilateur est là (Windows)."""
    from config import APP_VERSION
    compiler = iscc()
    if compiler is None:
        print("Inno Setup 6 introuvable : pas de programme d'installation")
        return None
    subprocess.check_call([compiler, f"/DAppVersion={APP_VERSION}",
                           os.path.join(ROOT, "installer", "celeste.iss")], cwd=ROOT)
    setup = os.path.join(ROOT, "dist", f"Celeste-{APP_VERSION}-Setup.exe")
    print("installation :", setup)
    return setup


def main():
    print("éphéméride :", ensure_ephemeris())
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
