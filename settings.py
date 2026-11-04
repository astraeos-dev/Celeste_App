"""
settings.py — Gestionnaire de préférences persistantes de Céleste
==================================================================
Charge et sauvegarde les préférences utilisateur dans ``settings.json``, rangé
dans le dossier de l'utilisateur (``~/.celeste``, ou ``$CELESTE_DATA``) et non
dans le dépôt : changer de branche ou mettre à jour Céleste n'y touche pas.
Un ``settings.json`` laissé dans le dossier de l'application par une version
précédente est repris au premier lancement.

Chaque préférence a une valeur par défaut définie dans ``_DEFAULTS``.
Au chargement, les clés manquantes sont complétées par les défauts.

API publique
------------
- ``load()``          → charge settings.json (appelé au démarrage)
- ``save()``          → écrit settings.json
- ``get(key)``        → valeur d'une préférence
- ``set(key, value)`` → modifie + sauvegarde automatiquement
- ``reset()``         → restaure tous les défauts
- ``all()``           → dict complet des préférences
"""

import json
import os

# Dossier des données de l'utilisateur, partagé avec l'éphéméride (engine.py)
USER_DIR = os.environ.get("CELESTE_DATA") or os.path.join(os.path.expanduser("~"), ".celeste")

_SETTINGS_FILE = os.path.join(USER_DIR, "settings.json")
# Emplacement des versions ≤ 4.1, dans le dossier de l'application
_LEGACY_SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")

# ── Valeurs par défaut ─────────────────────────────────────────────────────────

_DEFAULTS = {
    # Apparence
    "theme":          "nuit",       # nuit | jour | observation (thèmes Astræos)
    "lang":           "auto",       # auto (langue du système) | fr | en | es | de
    "time_format":    "24h",        # 24h | 12h

    # Lieu par défaut
    "default_place":  "Cherbourg-en-Cotentin",
    "default_lat":    49.6333,      # latitude par défaut
    "default_lon":    -1.6167,      # longitude par défaut
    "default_tz":     "auto",       # fuseau IANA (Europe/Paris…) ou auto (selon le lieu)
    "default_elevation": 0,         # altitude de l'observateur, m
    "auto_geoloc":    False,        # géoloc auto au lancement

    # Unités
    "temp_unit":      "C",          # C | F
    "dist_unit":      "km",         # km | miles

    # Affichage
    "live_interval":  2000,         # ms entre rafraîchissements temps réel
    "mag_limit":      6.0,          # magnitude limite pour les étoiles

    # Coordonnées
    "angle_format":   "dms",        # dms (dd° mm′ ss″) | dm (dd° mm,mm′) | dd (dd,ddddd°)
    "coord_cartesian": "heliocentric",   # x, y, z : heliocentric | geocentric | topocentric
    "coord_angular":   "equatorial",     # angles : ecliptic | equatorial | horizontal
    "coord_ecliptic_from": "sun",        # angles écliptiques vus du : sun | earth
    "coord_angle_format": "global",      # angles du tableau : global (paramètres) | dms | dm | dd
    # Onglet Planètes
    "planet_group":   "planets",    # astres du tableau : all | planets | minor
    "planet_visible_only": False,   # seulement les astres au-dessus de l'horizon
}

# ── État interne ───────────────────────────────────────────────────────────────

_settings: dict = {}

# ── API publique ───────────────────────────────────────────────────────────────

def load() -> dict:
    """Charge settings.json. Complète les clés manquantes avec les défauts."""
    global _settings
    _settings = dict(_DEFAULTS)
    path = _SETTINGS_FILE
    if not os.path.isfile(path) and os.path.isfile(_LEGACY_SETTINGS_FILE):
        path = _LEGACY_SETTINGS_FILE          # reprise d'une version précédente
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                user = json.load(f)
            for k, v in user.items():
                if k in _DEFAULTS:
                    _settings[k] = v
            # ancien réglage UTC±N : zone IANA fixe équivalente (UTC+2 → Etc/GMT-2)
            offset = user.get("default_utc")
            if "default_tz" not in user and isinstance(offset, int) and offset:
                _settings["default_tz"] = f"Etc/GMT{-offset:+d}"
        except (json.JSONDecodeError, OSError):
            pass
    return _settings


def save() -> None:
    """Écrit les préférences courantes dans settings.json (dossier de l'utilisateur)."""
    os.makedirs(os.path.dirname(_SETTINGS_FILE), exist_ok=True)
    with open(_SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(_settings, f, ensure_ascii=False, indent=2)


def get(key: str):
    """Retourne la valeur d'une préférence."""
    if not _settings:
        load()
    return _settings.get(key, _DEFAULTS.get(key))


def set(key: str, value) -> None:
    """Modifie une préférence et sauvegarde automatiquement."""
    if not _settings:
        load()
    if key in _DEFAULTS:
        _settings[key] = value
        save()


def reset() -> dict:
    """Restaure toutes les préférences par défaut."""
    global _settings
    _settings = dict(_DEFAULTS)
    save()
    return _settings


def all() -> dict:
    """Retourne une copie du dict complet des préférences."""
    if not _settings:
        load()
    return dict(_settings)


def defaults() -> dict:
    """Retourne les valeurs par défaut (lecture seule)."""
    return dict(_DEFAULTS)
