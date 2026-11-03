# -*- mode: python ; coding: utf-8 -*-
"""
celeste.spec — Céleste.exe pour Windows (PyInstaller)
=====================================================
À lancer par ``python scripts/build_exe.py``, qui prépare l'éphéméride JPL
(data/de440s.bsp) et l'icône (build/icons/celeste.ico) avant d'appeler
PyInstaller.

L'application contient l'éphéméride : elle fonctionne hors ligne dès le
premier lancement.
"""
import os

from PyInstaller.utils.hooks import collect_data_files

ICON = os.path.join("build", "icons", "celeste.ico")

datas = [
    ("fonts", "fonts"),
    ("assets", "assets"),
    ("locales", "locales"),
    ("favorites_default.json", "."),
    (os.path.join("data", "de440s.bsp"), "data"),
]
for package in ("skyfield", "timezonefinder", "timezonefinder_data", "tzdata"):
    datas += collect_data_files(package)

a = Analysis(
    ["main.py"],
    pathex=["."],
    datas=datas,
    hiddenimports=["PyQt6.QtPositioning", "PyQt6.QtSvg"],
    excludes=["tkinter", "pytest", "pandas"],          # pandas : import facultatif de Skyfield
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
