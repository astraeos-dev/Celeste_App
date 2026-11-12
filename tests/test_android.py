"""
tests/test_android.py — The Android build's own code (android/)

deploy.py adds the engine's packages and the Internet permission to the
configuration of pyside6-android-deploy, once each.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "android"))

import deploy  # noqa: E402


def test_engine_packages_and_internet():
    requirements, permissions = deploy.extended("python3,shiboken6,PySide6",
                                                "android.permission.ACCESS_FINE_LOCATION")
    assert requirements.split(",")[:3] == ["python3", "shiboken6", "PySide6"]
    for package in ("numpy", "skyfield", "jplephem", "sgp4", "certifi"):
        assert package in requirements.split(",")
    assert permissions == "android.permission.ACCESS_FINE_LOCATION, android.permission.INTERNET"


def test_added_once():
    once = deploy.extended("python3,numpy", "android.permission.INTERNET")
    assert once[0].split(",").count("numpy") == 1
    assert deploy.extended(*once) == once
    assert deploy.extended(None, None)[1] == "android.permission.INTERNET"
