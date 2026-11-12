"""
main.py — Entry point of the Céleste application (PyQt6)
=========================================================
Usage:
    python main.py
    python main.py --lang fr        (auto, fr, en, es, de)
    python main.py --theme jour     (nuit, jour, observation)

Without options, the language and the theme come from the preferences
(~/.celeste/settings.json); the "auto" language (the default) follows the
system's, or English when it is not translated. The language then changes in
the Settings tab and the theme at the bottom of the side panel, without a
restart.
"""

import argparse
import sys

from PyQt6.QtCore import QLocale, QTimer
from PyQt6.QtWidgets import QApplication

import settings as prefs
from config import Config
from i18n import resolve_lang, switch_lang, t


def parse_args(argv):
    """Options of Céleste; Qt's own options are left to Qt."""
    parser = argparse.ArgumentParser(
        prog="main.py", description="Céleste — astronomical observatory")
    parser.add_argument("--lang", help="language of the interface: auto, fr, en, es, de")
    parser.add_argument("--theme", help="theme: nuit (night), jour (day), observation")
    parser.add_argument("--self-test", action="store_true",
                        help="opens the window, calculates, then quits (checks an executable)")
    args, _qt_args = parser.parse_known_args(argv)
    return args


def ensure_ephemeris():
    """
    Loads the JPL DE440 ephemeris. At the first launch it is downloaded
    (32 MB) into ~/.celeste, in the background, with its progress; it is not
    in the installer, so that updates do not download it again. Returns
    False when it can be neither found nor downloaded (after telling the
    user) or when the download is cancelled.
    """
    import os
    import threading
    from PyQt6.QtWidgets import QMessageBox, QProgressDialog
    import engine

    def fail(exc):
        folder = os.path.dirname(engine.user_ephemeris_path())
        QMessageBox.critical(None, "Céleste", t("startup.ephemeris_error").format(error=exc, folder=folder))
        return False

    if not os.path.isfile(engine.ephemeris_path()):
        state = {"done": 0, "total": engine._EPHEMERIS_SIZE, "cancel": False, "error": None}
        dialog = QProgressDialog(t("startup.downloading"), t("update.cancel"), 0, 1000)
        dialog.setWindowTitle("Céleste")
        dialog.setMinimumDuration(0)
        dialog.canceled.connect(lambda: state.update(cancel=True))

        def fetch():
            try:
                engine.download_ephemeris(progress=lambda d, n: state.update(done=d, total=n),
                                          cancelled=lambda: state["cancel"])
            except engine.EphemerisUnavailable as exc:
                state["error"] = exc

        worker = threading.Thread(target=fetch, daemon=True)
        worker.start()
        dialog.show()
        while worker.is_alive():
            dialog.setValue(int(1000 * state["done"] / state["total"]) if state["total"] else 0)
            QApplication.processEvents()
            worker.join(0.05)
        dialog.close()
        if isinstance(state["error"], engine.DownloadCancelled):
            return False
        if state["error"] is not None:
            return fail(state["error"])
    try:
        engine.load_ephemeris()
    except engine.EphemerisUnavailable as exc:
        return fail(exc)
    return True


def main(argv=None):
    argv = list(sys.argv if argv is None else argv)
    args = parse_args(argv[1:])
    prefs.load()

    if sys.platform == "win32":
        # Céleste's icon (not Python's) in the taskbar
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("astraeos.celeste")
        except (AttributeError, OSError):
            pass

    app = QApplication(argv)
    app.setApplicationName("Céleste")
    Config.apply_theme(args.theme or prefs.get("theme"))
    switch_lang(resolve_lang(args.lang or prefs.get("lang"), QLocale.system().name()))

    from gui import AstroApp, init_style
    init_style(app)
    if not ensure_ephemeris():
        return 1
    window = AstroApp()
    window.show()
    if args.self_test:
        window._calculate_quietly()                       # stays out of the user's history
        from engine import AstroEngine
        from config import APP_VERSION
        AstroEngine.find_eclipses(window._dte, num_months=1)
        from PyQt6.QtPositioning import QGeoPositionInfoSource
        sources = ", ".join(QGeoPositionInfoSource.availableSources()) or "none"
        sizes = window.windowIcon().availableSizes()
        if not sizes or window.windowIcon().pixmap(32, 32).isNull():
            print("self-test: the window has no icon")
            return 1
        print(f"Céleste {APP_VERSION} self-test OK: {window.tz_menu.currentText()}, "
              f"{len(window.visible_stars)} stars, {len(window.minor_planets)} minor planets, "
              f"location sources: {sources}")
        return 0

    # Geolocation at startup when enabled in the settings
    if prefs.get("auto_geoloc"):
        QTimer.singleShot(800, lambda: window.geolocate(interactive=False))

    # Update: is a newer version published? (Settings › About)
    if prefs.get("update_check"):
        QTimer.singleShot(4000, lambda: window.check_updates(interactive=False))

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
