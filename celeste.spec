# -*- mode: python ; coding: utf-8 -*-
"""
celeste.spec — Céleste.exe for Windows (PyInstaller)
====================================================
Run by ``python scripts/build_exe.py``, which draws the icon
(build/icons/celeste.ico) before calling PyInstaller.

The JPL ephemeris (32 MB) is not in the application: it is downloaded once
and for all into ~/.celeste at the first launch, and updates do not download
it again.
"""
import os

from PyInstaller.utils.hooks import collect_data_files

ICON = os.path.join("build", "icons", "celeste.ico")

datas = [
    ("fonts", "fonts"),
    ("assets", "assets"),
    ("locales", "locales"),
    ("favorites_default.json", "."),
]
for package in ("skyfield", "timezonefinder", "timezonefinder_data", "tzdata"):
    datas += collect_data_files(package)
# Qt's own texts in the four languages (standard buttons, dialogs): ui.common.install_qt_translation
import PySide6  # noqa: E402
_translations = os.path.join(os.path.dirname(PySide6.__file__), "Qt", "translations")
for _lang in ("fr", "es", "de"):
    _qm = os.path.join(_translations, f"qtbase_{_lang}.qm")
    if os.path.isfile(_qm):
        datas.append((_qm, os.path.join("PySide6", "Qt", "translations")))

a = Analysis(
    ["main.py"],
    pathex=["."],
    datas=datas,
    # qt.py imports the binding's modules by name: PyInstaller does not see them
    hiddenimports=["qt", "PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets", "PySide6.QtSvg",
                   "PySide6.QtNetwork", "PySide6.QtPositioning",
                   "matplotlib.backends.backend_qtagg", "matplotlib.backends.backend_pdf"],
    excludes=["tkinter", "pytest", "pandas", "PyQt6"],    # pandas: an optional import of Skyfield
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="Celeste",
    console=False,
    icon=ICON if os.path.exists(ICON) else None,
)
coll = COLLECT(exe, a.binaries, a.datas, name="Celeste")
