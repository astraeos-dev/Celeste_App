"""
android/main.py — The first Android build of Céleste (4.14)
===========================================================
The smallest app that settles the Android tools before the interface moves
(docs/ANDROID.md): PySide6 on Android, built by pyside6-android-deploy in the
Android workflow (.github/workflows/android.yml), with Céleste's version and
the colours of the Nuit theme from config.py (copied next to this file by the
workflow). The engine (NumPy, Skyfield) and the full interface come with the
5.0 alpha.

pyside6-android-deploy requires the entry point to be named main.py.
"""
import platform
import sys

print("Céleste android: Python", platform.python_version(), "started", flush=True)

from PySide6.QtCore import Qt, qVersion
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

from config import APP_RELEASE, Config

SPACES = ("Ce soir", "Ciel", "Astres", "Calendrier", "Observer")


def self_test_line():
    """The line the workflow and logcat look for."""
    return (f"Céleste {APP_RELEASE} android self-test OK: Qt {qVersion()}, "
            f"Python {platform.python_version()}, {platform.machine() or 'unknown'}")


def window():
    Config.apply_theme("nuit")
    root = QWidget()
    root.setObjectName("root")
    root.setStyleSheet(f"#root {{ background: {Config.CIEL_000}; }} QLabel {{ color: {Config.ENCRE}; }}")
    layout = QVBoxLayout(root)
    layout.setContentsMargins(24, 48, 24, 24)
    layout.setSpacing(16)
    title = QLabel("Céleste")
    font = QFont()
    font.setPixelSize(36)
    font.setBold(True)
    title.setFont(font)
    layout.addWidget(title)
    star = QLabel("★")
    star.setStyleSheet(f"color: {Config.OR}; font-size: 28px;")
    layout.addWidget(star)
    version = QLabel(f"Version {APP_RELEASE}\nQt {qVersion()} · Python {platform.python_version()}")
    version.setStyleSheet(f"color: {Config.ENCRE_ATTENUEE}; font-size: 16px;")
    layout.addWidget(version)
    note = QLabel("Première version Android : l'interface complète arrive avec Céleste 5.\n\n"
                  + " · ".join(SPACES))
    note.setWordWrap(True)
    note.setAlignment(Qt.AlignmentFlag.AlignLeft)
    note.setStyleSheet("font-size: 18px;")
    layout.addWidget(note)
    layout.addStretch(1)
    return root


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Céleste")
    w = window()
    w.show()
    print(self_test_line(), flush=True)
    if "--self-test" in sys.argv:
        return 0
    return app.exec()


if __name__ == "__main__":
    try:
        code = main()
    except BaseException:                  # in logcat (tag python) rather than a silent exit
        import traceback
        traceback.print_exc()
        sys.stdout.flush()
        raise
    sys.exit(code)
