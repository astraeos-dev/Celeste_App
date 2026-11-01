"""
main.py — Point d'entrée de l'application Céleste (PyQt6)
==========================================================
Usage :
    python main.py
    python main.py --lang fr        (auto, fr, en, es, de)
    python main.py --theme latte    (mocha, frape, latte)

Sans option, la langue et le thème viennent de settings.json ; la langue
« auto » (par défaut) suit celle du système, ou l'anglais si elle n'est pas
traduite. Les deux se changent ensuite dans l'onglet Paramètres, sans
redémarrer.
"""

import argparse
import sys

from PyQt6.QtCore import QLocale, QTimer
from PyQt6.QtWidgets import QApplication

import settings as prefs
from config import Config
from i18n import resolve_lang, switch_lang


def parse_args(argv):
    """Options de Céleste ; les options propres à Qt sont laissées à Qt."""
    parser = argparse.ArgumentParser(
        prog="main.py", description="Céleste — observatoire astronomique")
    parser.add_argument("--lang", help="langue de l'interface : auto, fr, en, es, de")
    parser.add_argument("--theme", help="thème : mocha, frape, latte")
    args, _qt_args = parser.parse_known_args(argv)
    return args


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
    window = AstroApp()
    window.show()

    # Géolocalisation au démarrage si elle est activée dans les paramètres
    if prefs.get("auto_geoloc"):
        QTimer.singleShot(800, window.geolocate)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
