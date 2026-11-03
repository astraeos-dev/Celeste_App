"""
main.py — Point d'entrée de l'application Céleste (PyQt6)
==========================================================
Usage :
    python main.py
    python main.py --lang fr        (auto, fr, en, es, de)
    python main.py --theme jour     (nuit, jour, observation)

Sans option, la langue et le thème viennent des préférences (~/.celeste/settings.json) ; la langue
« auto » (par défaut) suit celle du système, ou l'anglais si elle n'est pas
traduite. La langue se change ensuite dans l'onglet Paramètres et le thème
en bas de la barre latérale, sans redémarrer.
"""

import argparse
import sys

from PyQt6.QtCore import QLocale, QTimer
from PyQt6.QtWidgets import QApplication

import settings as prefs
from config import Config
from i18n import resolve_lang, switch_lang, t


def parse_args(argv):
    """Options de Céleste ; les options propres à Qt sont laissées à Qt."""
    parser = argparse.ArgumentParser(
        prog="main.py", description="Céleste — observatoire astronomique")
    parser.add_argument("--lang", help="langue de l'interface : auto, fr, en, es, de")
    parser.add_argument("--theme", help="thème : nuit, jour, observation")
    args, _qt_args = parser.parse_known_args(argv)
    return args


def ensure_ephemeris():
    """
    Loads the JPL DE440 ephemeris, downloading it (32 MB) at the first launch.
    Returns False, after telling the user, when it can be neither found nor
    downloaded.
    """
    import os
    from PyQt6.QtWidgets import QMessageBox, QProgressDialog
    import engine

    dialog = None
    if not os.path.isfile(engine.ephemeris_path()):
        dialog = QProgressDialog(t("startup.downloading"), None, 0, 0)
        dialog.setWindowTitle("Céleste")
        dialog.show()
        QApplication.processEvents()
    try:
        engine.load_ephemeris()
    except engine.EphemerisUnavailable as exc:
        QMessageBox.critical(None, "Céleste", t("startup.ephemeris_error").format(error=exc))
        return False
    finally:
        if dialog is not None:
            dialog.close()
    return True


def main(argv=None):
    argv = list(sys.argv if argv is None else argv)
    args = parse_args(argv[1:])
    prefs.load()

    if sys.platform == "win32":
        # Icône de Céleste (et non de Python) dans la barre des tâches
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

    # Géolocalisation au démarrage si elle est activée dans les paramètres
    if prefs.get("auto_geoloc"):
        QTimer.singleShot(800, window.geolocate)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
