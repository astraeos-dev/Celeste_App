"""
android/main.py — Céleste on Android, on the way to 5.0
=======================================================
The Android build of Céleste (docs/ANDROID.md), built by
pyside6-android-deploy in the Android workflow (.github/workflows/android.yml,
android/deploy.py):

- 4.14: PySide6 on Android, Céleste's version, the Nuit theme and the logo;
- 4.17: Céleste's engine on the phone (NumPy, Skyfield): at the first start
  the JPL ephemeris is downloaded (32 MB, with its progress) into the app's
  folder, then the Sun's and the Moon's altitudes are computed for now.

The workflow puts next to this file config.py, engine.py, icon.png and
logo.png. The full interface comes with the 5.0 alpha.

pyside6-android-deploy requires the entry point to be named main.py.
"""
import os
import platform
import sys
import threading
import traceback
from datetime import datetime, timezone

print("Céleste android: Python", platform.python_version(), "started", flush=True)

from PySide6.QtCore import QObject, QStandardPaths, Qt, QTimer, Signal, qVersion  # noqa: E402
from PySide6.QtGui import QFont, QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget  # noqa: E402

from config import APP_RELEASE, Config  # noqa: E402

SPACES = ("Ce soir", "Ciel", "Astres", "Calendrier", "Observer")
PLACE = ("Cherbourg-en-Cotentin", 49.6333, -1.6167)     # until the phone's position (5.0)


def self_test_line():
    """The line the workflow and logcat look for."""
    return (f"Céleste {APP_RELEASE} android self-test OK: Qt {qVersion()}, "
            f"Python {platform.python_version()}, {platform.machine() or 'unknown'}")


class EngineRun(QObject):
    """Céleste's engine in a thread: the ephemeris (downloaded once), then the Sun and the Moon."""

    progress = Signal(str)
    finished = Signal(bool, str)

    def __init__(self, data_dir):
        super().__init__()
        self.data_dir = data_dir

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        try:
            os.environ.setdefault("CELESTE_DATA", self.data_dir)
            import certifi                              # the CA certificates: Android's are out of reach
            os.environ.setdefault("SSL_CERT_FILE", certifi.where())
            import engine
            path = engine.ephemeris_path()
            if not os.path.isfile(path):
                self.progress.emit("Téléchargement des éphémérides JPL…")

                def progress(done, total):
                    self.progress.emit(f"Téléchargement des éphémérides JPL : "
                                       f"{done / 1e6:.0f} / {total / 1e6:.0f} Mo")
                engine.download_ephemeris(path, progress)
            engine.load_ephemeris()
            name, lat, lon = PLACE
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            sun, moon = engine.AstroEngine.altitudes([now], lat, lon)
            text = (f"{name}, maintenant ({now:%d/%m/%Y %H:%M} TU) :\n"
                    f"Soleil à {sun[0]:+.1f}° de hauteur · Lune à {moon[0]:+.1f}°")
            print(f"Céleste {APP_RELEASE} android engine OK: sun {sun[0]:+.2f}°, moon {moon[0]:+.2f}°, "
                  f"ephemeris {path}", flush=True)
            self.finished.emit(True, text)
        except Exception as exc:                        # shown in the window and in logcat
            traceback.print_exc()
            print(f"Céleste {APP_RELEASE} android engine FAILED: {exc!r}", flush=True)
            self.finished.emit(False, f"Le moteur n'a pas pu démarrer : {exc}")


def window():
    Config.apply_theme("nuit")
    root = QWidget()
    root.setObjectName("root")
    root.setStyleSheet(f"#root {{ background: {Config.CIEL_000}; }} QLabel {{ color: {Config.ENCRE}; }}")
    layout = QVBoxLayout(root)
    layout.setContentsMargins(24, 48, 24, 24)
    layout.setSpacing(16)
    logo_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.png")
    if os.path.isfile(logo_file):                   # drawn by make_images.py (Android workflow)
        logo = QLabel()
        logo.setPixmap(QPixmap(logo_file).scaledToHeight(72, Qt.TransformationMode.SmoothTransformation))
        layout.addWidget(logo)
    title = QLabel("Céleste")
    font = QFont()
    font.setPixelSize(36)
    font.setBold(True)
    title.setFont(font)
    layout.addWidget(title)
    version = QLabel(f"Version {APP_RELEASE}\nQt {qVersion()} · Python {platform.python_version()}")
    version.setStyleSheet(f"color: {Config.ENCRE_ATTENUEE}; font-size: 16px;")
    layout.addWidget(version)
    sky = QLabel("Démarrage du moteur de calcul…")
    sky.setObjectName("sky")
    sky.setWordWrap(True)
    sky.setStyleSheet(f"font-size: 18px; color: {Config.LUNE};")
    layout.addWidget(sky)
    note = QLabel("Version de test Android : l'interface complète arrive avec Céleste 5.\n\n"
                  + " · ".join(SPACES))
    note.setWordWrap(True)
    note.setAlignment(Qt.AlignmentFlag.AlignLeft)
    note.setStyleSheet("font-size: 16px;")
    layout.addWidget(note)
    layout.addStretch(1)
    root.sky = sky
    return root


def data_dir():
    """The app's own folder (Android: /data/user/0/<package>/files), for the ephemeris."""
    path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    path = os.environ.get("CELESTE_DATA") or path or os.path.join(os.path.expanduser("~"), ".celeste")
    os.makedirs(path, exist_ok=True)
    return path


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Céleste")
    w = window()
    w.show()
    print(self_test_line(), flush=True)
    run = EngineRun(data_dir())
    run.progress.connect(w.sky.setText)

    def finished(ok, text):
        w.sky.setText(text)
        if "--self-test" in sys.argv:
            app.exit(0 if ok else 1)

    run.finished.connect(finished)
    run.start()
    if "--self-test" in sys.argv:
        QTimer.singleShot(120000, lambda: app.exit(2))     # no answer in two minutes
    return app.exec()


if __name__ == "__main__":
    try:
        code = main()
    except BaseException:                  # in logcat (tag python) rather than a silent exit
        traceback.print_exc()
        sys.stdout.flush()
        raise
    sys.exit(code)
