"""
qt.py — The Qt binding of Céleste
=================================
Céleste runs on PySide6 (Qt for Python, the binding whose official tool builds
Android apps: docs/ANDROID.md), and still on PyQt6 when PySide6 is missing or
when CELESTE_QT=pyqt6. Every module imports Qt from here:

    from qt.QtWidgets import QLabel
    from qt import Signal

``qt.QtCore``, ``qt.QtGui``… are the binding's own modules, so the classes are
the same objects either way. ``API`` names the binding in use ("PySide6" or
"PyQt6"); matplotlib's Qt backend follows it (QT_API).
"""
import importlib
import os
import sys

_BINDINGS = ("PyQt6",) if os.environ.get("CELESTE_QT", "").lower() == "pyqt6" else ("PySide6", "PyQt6")
API = None
for _name in _BINDINGS:
    try:
        importlib.import_module(_name + ".QtCore")
    except ImportError:
        continue
    API = _name
    break
if API is None:
    raise ImportError("Céleste needs PySide6 (pip install PySide6) or PyQt6")

os.environ.setdefault("QT_API", API.lower())          # matplotlib's backend_qtagg

# QtSensors: the sky map that follows a phone (ui/phone.py); a desktop build
# leaves it out, and the map's follow button then stays hidden
_MODULES = ("QtCore", "QtGui", "QtWidgets", "QtSvg", "QtNetwork", "QtPositioning", "QtSensors")
for _module in _MODULES:
    try:
        _loaded = importlib.import_module(f"{API}.{_module}")
    except ImportError:                                 # a module left out of a small build
        continue
    globals()[_module] = _loaded
    sys.modules[f"{__name__}.{_module}"] = _loaded

if API == "PySide6":
    Signal, Slot = QtCore.Signal, QtCore.Slot           # noqa: F821 (set just above)
    QT_VERSION = QtCore.qVersion()                      # noqa: F821
else:
    Signal, Slot = QtCore.pyqtSignal, QtCore.pyqtSlot   # noqa: F821
    QT_VERSION = QtCore.QT_VERSION_STR                  # noqa: F821
