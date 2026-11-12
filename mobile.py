"""
mobile.py — Céleste on a phone (Android)
========================================
What changes when Céleste runs on Android (docs/ANDROID.md), set up by
main.py before anything else is imported:

- the user folder (settings, favourites, history, log, the JPL ephemeris) is
  the app's private storage, given by python-for-android in ANDROID_PRIVATE;
- HTTPS (the ephemeris download, the forecast) uses certifi's CA
  certificates and Android's own: Python on Android finds none by itself;
- the automatic update (a Windows installer) is not offered.

Everything here does nothing on a desktop.
"""
import os
import sys

ANDROID_CA_DIR = "/system/etc/security/cacerts"        # Android's CA certificates (hashed PEM)


def is_android():
    """True on Android (CPython's own Android build, or python-for-android's)."""
    return (sys.platform == "android" or "ANDROID_ARGUMENT" in os.environ
            or "ANDROID_PRIVATE" in os.environ)


def data_dir():
    """The user folder on Android: <app private storage>/celeste."""
    base = os.environ.get("ANDROID_PRIVATE") or os.path.expanduser("~")
    return os.path.join(base, "celeste")


def use_certificates():
    """
    Every default HTTPS context of Python (urllib) loads certifi's file and
    Android's own certificates when they are there. Returns False without any.
    """
    import ssl
    try:
        import certifi
        cafile = certifi.where()
    except ImportError:
        cafile = None
    cafile = cafile if cafile and os.path.isfile(cafile) else None
    capath = ANDROID_CA_DIR if os.path.isdir(ANDROID_CA_DIR) else None
    print(f"Céleste android: CA certificates {cafile or '-'} · {capath or '-'}", flush=True)
    if cafile is None and capath is None:
        return False

    def context(*_args, **_kwargs):
        return ssl.create_default_context(cafile=cafile, capath=capath)

    ssl._create_default_https_context = context
    return True


def setup():
    """
    On Android, before the settings are imported: the user folder and the
    HTTPS certificates. Returns True on Android.
    """
    if not is_android():
        return False
    os.environ.setdefault("CELESTE_DATA", data_dir())
    os.makedirs(os.environ["CELESTE_DATA"], exist_ok=True)
    use_certificates()
    return True
