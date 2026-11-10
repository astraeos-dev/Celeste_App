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

a = Analysis(
    ["main.py"],
    pathex=["."],
    datas=datas,
    hiddenimports=["PyQt6.QtPositioning", "PyQt6.QtSvg"],
    excludes=["tkinter", "pytest", "pandas"],          # pandas: an optional import of Skyfield
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
