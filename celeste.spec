# -*- mode: python ; coding: utf-8 -*-
"""
celeste.spec — Céleste en application autonome (PyInstaller)
=============================================================
À lancer par ``python scripts/build_exe.py``, qui prépare l'éphéméride JPL
(data/de440s.bsp) et les icônes (build/icons) avant d'appeler PyInstaller.

L'application contient l'éphéméride : elle fonctionne hors ligne dès le
premier lancement. Sous macOS, Info.plist déclare l'usage de la position
(géolocalisation par le service de localisation du système).
"""
import os
import sys

from PyInstaller.utils.hooks import collect_data_files

sys.path.insert(0, os.path.abspath("."))
from config import APP_VERSION  # noqa: E402

MACOS = sys.platform == "darwin"
ICON = os.path.join("build", "icons", "celeste.icns" if MACOS else "celeste.ico")

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

if MACOS:
    app = BUNDLE(
        coll,
        name="Celeste.app",
        icon=ICON if os.path.exists(ICON) else None,
        bundle_identifier="dev.astraeos.celeste",
        version=APP_VERSION,
        info_plist={
            "CFBundleDisplayName": "Céleste",
            "CFBundleShortVersionString": APP_VERSION,
            "NSHighResolutionCapable": True,
            "NSLocationWhenInUseUsageDescription":
                "Céleste utilise votre position pour calculer le ciel de votre lieu.",
            "NSLocationUsageDescription":
                "Céleste utilise votre position pour calculer le ciel de votre lieu.",
        },
    )
