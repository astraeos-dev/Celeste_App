"""
android/deploy.py — pyside6-android-deploy with what Céleste's engine needs
===========================================================================
PySide6's Android tool writes a buildozer configuration whose Python packages
are only python3, shiboken6 and PySide6. This wrapper runs the tool unchanged
(same arguments: python android/deploy.py <pyside6-android-deploy options>)
after adding, to the configuration it writes:

- the engine's packages: NumPy (a python-for-android recipe) and Skyfield with
  its pure-Python dependencies (jplephem, sgp4 — built without its C++ part,
  PYTHON_SGP4_COMPILE=never —, certifi);
- the Internet permission, for the download of the JPL ephemeris at the first
  start.

CELESTE_ANDROID_REQUIREMENTS replaces the list of packages.
"""
import os
import runpy
import sys
from pathlib import Path

import PySide6

SCRIPTS = Path(PySide6.__file__).parent / "scripts"
REQUIREMENTS = os.environ.get("CELESTE_ANDROID_REQUIREMENTS", "numpy,certifi,jplephem,sgp4,skyfield")
PERMISSIONS = ("android.permission.INTERNET",)


def extended(requirements, permissions):
    """The tool's requirements and permissions (comma-separated) with Céleste's added once."""
    req = [r.strip() for r in (requirements or "").split(",") if r.strip()]
    req += [r for r in (x.strip() for x in REQUIREMENTS.split(",")) if r and r not in req]
    perms = [p.strip() for p in (permissions or "").split(",") if p.strip()]
    perms += [p for p in PERMISSIONS if p not in perms]
    return ",".join(req), ", ".join(perms)


def patch(buildozer_module):
    """BuildozerConfig writes Céleste's packages and permission too."""
    original = buildozer_module.BuildozerConfig.__init__

    def init(self, *args, **kwargs):
        original(self, *args, **kwargs)
        requirements, permissions = extended(self.get_value("app", "requirements"),
                                             self.get_value("app", "android.permissions"))
        self.set_value("app", "requirements", requirements)
        self.set_value("app", "android.permissions", permissions)
        self.update_config()
        print("[celeste] requirements:", requirements, "| permissions:", permissions, flush=True)

    buildozer_module.BuildozerConfig.__init__ = init


def main():
    os.environ.setdefault("PYTHON_SGP4_COMPILE", "never")
    sys.path.insert(0, str(SCRIPTS))
    from deploy_lib.android import buildozer
    patch(buildozer)
    script = SCRIPTS / "android_deploy.py"
    sys.argv[0] = str(script)
    runpy.run_path(str(script), run_name="__main__")


if __name__ == "__main__":
    main()
