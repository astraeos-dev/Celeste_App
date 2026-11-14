"""
tests/test_android.py — The Android build's own code (android/)

deploy.py adds the engine's packages and the Internet permission to the
configuration of pyside6-android-deploy, once each; qt_modules.py names
for that tool the Qt modules qt.py loads.
"""
import ast
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "android"))

import deploy  # noqa: E402


def _imported_qt_modules(path):
    """The Qt modules of the 'from PySide6 import Qt…' lines of a file, as the tool reads them."""
    with open(path, encoding="utf-8") as f:
        tree = ast.parse(f.read())
    return {alias.name for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module == "PySide6"
            for alias in node.names if alias.name.startswith("Qt")}


def test_the_tool_sees_the_modules_of_qt_py():
    import qt
    assert _imported_qt_modules(os.path.join(ROOT, "android", "qt_modules.py")) == set(qt._MODULES)


def test_engine_packages_and_internet():
    requirements, permissions = deploy.extended("python3,shiboken6,PySide6",
                                                "android.permission.ACCESS_FINE_LOCATION")
    assert requirements.split(",")[:3] == ["python3", "shiboken6", "PySide6"]
    for package in ("numpy", "skyfield", "jplephem", "sgp4", "certifi"):
        assert package in requirements.split(",")
    assert permissions == "android.permission.ACCESS_FINE_LOCATION, android.permission.INTERNET"


def test_data_files_kept():
    exts = deploy.with_data_extensions("py,png,jpg,kv,atlas,qml,js").split(",")
    assert exts[:7] == ["py", "png", "jpg", "kv", "atlas", "qml", "js"]
    for ext in ("json", "npz", "gz", "csv", "tsv", "ttf"):
        assert exts.count(ext) == 1
    assert deploy.with_data_extensions(",".join(exts)) == ",".join(exts)


def test_added_once():
    once = deploy.extended("python3,numpy", "android.permission.INTERNET")
    assert once[0].split(",").count("numpy") == 1
    assert deploy.extended(*once) == once
    assert deploy.extended(None, None)[1] == "android.permission.INTERNET"


def test_the_start_is_told_to_the_system_log(monkeypatch, capsys):
    """mobile.log() writes the lines the emulator check and adb look for; nothing on a desktop."""
    sys.path.insert(0, ROOT)
    import mobile
    for name in ("ANDROID_PRIVATE", "ANDROID_ARGUMENT"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(mobile.sys, "platform", "linux")
    mobile.log("ephemeris ready")
    assert capsys.readouterr().out == ""
    monkeypatch.setenv("ANDROID_PRIVATE", "/data/user/0/org.celeste.celeste/files")
    mobile.log("ephemeris ready")
    assert capsys.readouterr().out == "Céleste android: ephemeris ready\n"


def test_the_emulator_check_knows_the_start_lines():
    """android/ci_emulator.sh stops waiting on the lines main.py writes, and names a failure."""
    with open(os.path.join(ROOT, "android", "ci_emulator.sh"), encoding="utf-8") as f:
        script = f.read()
    with open(os.path.join(ROOT, "main.py"), encoding="utf-8") as f:
        source = f.read()
    for line in ("ephemeris FAILED", "the event loop ended", "android window OK"):
        assert line in source and line in script, line
    # the location granted at install: Android's question would stop the app's timers (4.22)
    assert "adb install -r -g " in script
    # the install left to settle, and one more start, only one, when the process vanished silently (4.24)
    install = script.index("adb install")
    assert "sleep 30" in script[install:script.index("monkey", install)]
    assert script.count("monkey -p") == 2 and "relaunched=1" in script
