"""
android/qt_modules.py — Céleste's Qt modules, written out for the Android tool
==============================================================================
pyside6-android-deploy learns which Qt modules an app uses by reading the
import lines of its Python files ("from PySide6 import QtCore"…). From those
modules it takes, for the APK, Qt's Java libraries (Qt6Android.jar, which the
app's activity is built on), its plugins (the Android platform plugin, the
image formats) and its permissions.

Céleste imports Qt by name in qt.py (PySide6, or PyQt6 on a desktop without
it), which the tool cannot read: with no module found, the APK of the full app
had no Qt6Android.jar and did not compile (5.0 alpha). The Android workflow
puts this file next to qt.py; it is never imported. Its modules are qt.py's
(tests/test_android.py).
"""
from PySide6 import QtCore, QtGui, QtNetwork, QtPositioning, QtSvg, QtWidgets  # noqa: F401
