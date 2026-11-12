"""
settings.py — Persistent preferences of Céleste
================================================
Loads and saves the user's preferences in ``settings.json``, kept in the
user's folder (``~/.celeste``, or ``$CELESTE_DATA``) and not in the
repository: switching branches or updating Céleste leaves it alone. A
``settings.json`` left in the application folder by an earlier version is
taken over at the first launch.

Each preference has a default value in ``_DEFAULTS``. On loading, the missing
keys are filled with the defaults.

Public API
----------
- ``load()``          → loads settings.json (called at startup)
- ``save()``          → writes settings.json
- ``get(key)``        → value of a preference
- ``set(key, value)`` → changes it and saves at once
- ``reset()``         → restores all the defaults
- ``all()``           → full dict of the preferences
"""

import json
import os

# Folder of the user's data, shared with the ephemeris (engine.py)
USER_DIR = os.environ.get("CELESTE_DATA") or os.path.join(os.path.expanduser("~"), ".celeste")

_SETTINGS_FILE = os.path.join(USER_DIR, "settings.json")
# Where versions 4.1 and earlier kept it, in the application folder
_LEGACY_SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")

# ── Default values ─────────────────────────────────────────────────────────────

_DEFAULTS = {
    # Appearance
    "theme":          "nuit",       # nuit | jour | observation (Astræos themes)
    "lang":           "auto",       # auto (system language) | fr | en | es | de
    "time_format":    "24h",        # 24h | 12h

    # Default place
    "default_place":  "Cherbourg-en-Cotentin",
    "default_lat":    49.6333,      # default latitude
    "default_lon":    -1.6167,      # default longitude
    "default_tz":     "auto",       # IANA time zone (Europe/Paris…) or auto (from the place)
    "default_elevation": 0,         # observer's elevation, m
    "auto_geoloc":    False,        # geolocation at launch

    # Units
    "temp_unit":      "C",          # C | F
    "dist_unit":      "km",         # km | miles

    # Display
    "live_interval":  2000,         # ms between real-time refreshes
    "mag_limit":      6.0,          # limiting magnitude of the stars
    "show_messier":   True,         # sky map: the Messier objects

    # Coordinates
    "angle_format":   "dms",        # dms (dd° mm′ ss″) | dm (dd° mm,mm′) | dd (dd,ddddd°)
    "coord_cartesian": "heliocentric",   # x, y, z : heliocentric | geocentric | topocentric
    "coord_angular":   "equatorial",     # angles : ecliptic | equatorial | horizontal
    "coord_ecliptic_from": "sun",        # ecliptic angles seen from: sun | earth
    "coord_angle_format": "global",      # angles of the table: global (settings) | dms | dm | dd
    # Planets tab
    "planet_group":   "planets",    # bodies of the table: all | planets | minor | comets
    "planet_visible_only": False,   # only the bodies above the horizon
    # Observing site and night planner (planner.py)
    "env_temperature": 10.0,        # °C, for the refraction
    "env_pressure":   1010.0,       # hPa; 0: no refraction
    "horizon_points": [],           # horizon mask: [[azimuth, altitude], ...] degrees
    "bortle":         0,            # light pollution of the place, Bortle class 1–9; 0: not given
    "weather_forecast": False,      # quality of the night: the clouds forecast by Open-Meteo
    "journal_instrument": "",       # observation log: the instrument of the last entry
    "planner_constraints": {},      # the user's values of planner.DEFAULTS
    "planner_bucket": [],           # targets always shown
    "planner_done":   [],           # targets never shown
    "planner_custom": [],           # the user's own targets (planner.custom_target keywords)
    "planner_mpc":    True,         # every comet of the Minor Planet Center, not only Céleste's
    "satellites_visual": False,     # passes of the ~150 naked-eye satellites too (CelesTrak "visual")
    "plan_split": [40, 60],         # Targets tab: share of the height for the tables and the chart
    "plan_map_east_right": False,   # the map of the night with the east on the right (as uptonight)
    # Updates (updater.py)
    "update_check":   True,         # look for a new version at startup
    "update_skipped": "",           # version the user chose to skip
}

# ── Internal state ─────────────────────────────────────────────────────────────

_settings: dict = {}

# ── Public API ─────────────────────────────────────────────────────────────────

def load() -> dict:
    """Loads settings.json, filling the missing keys with the defaults."""
    global _settings
    _settings = dict(_DEFAULTS)
    path = _SETTINGS_FILE
    if not os.path.isfile(path) and os.path.isfile(_LEGACY_SETTINGS_FILE):
        path = _LEGACY_SETTINGS_FILE          # taken over from an earlier version
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                user = json.load(f)
            for k, v in user.items():
                if k in _DEFAULTS:
                    _settings[k] = v
            # old UTC±N setting: the equivalent fixed IANA zone (UTC+2 → Etc/GMT-2)
            offset = user.get("default_utc")
            if "default_tz" not in user and isinstance(offset, int) and offset:
                _settings["default_tz"] = f"Etc/GMT{-offset:+d}"
        except (json.JSONDecodeError, OSError):
            pass
    return _settings


def save() -> None:
    """Writes the current preferences to settings.json (the user's folder)."""
    os.makedirs(os.path.dirname(_SETTINGS_FILE), exist_ok=True)
    with open(_SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(_settings, f, ensure_ascii=False, indent=2)


def get(key: str):
    """Value of a preference."""
    if not _settings:
        load()
    return _settings.get(key, _DEFAULTS.get(key))


def set(key: str, value) -> None:
    """Changes a preference and saves at once."""
    if not _settings:
        load()
    if key in _DEFAULTS:
        _settings[key] = value
        save()


def reset() -> dict:
    """Restores all the default preferences."""
    global _settings
    _settings = dict(_DEFAULTS)
    save()
    return _settings


def all() -> dict:
    """A copy of the full dict of the preferences."""
    if not _settings:
        load()
    return dict(_settings)


def defaults() -> dict:
    """The default values (a copy)."""
    return dict(_DEFAULTS)
