"""
settings.py — Gestionnaire de préférences persistantes de Céleste
==================================================================
Charge et sauvegarde les préférences utilisateur dans ``settings.json``.

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

_SETTINGS_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "settings.json"
)

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
    "default_utc":    0,            # offset UTC (-12 → +14)
    "auto_geoloc":    False,        # géoloc auto au lancement

    # Unités
    "temp_unit":      "C",          # C | F
    "dist_unit":      "km",         # km | miles

    # Affichage
    "live_interval":  2000,         # ms entre rafraîchissements temps réel
    "mag_limit":      6.0,          # magnitude limite pour les étoiles
}

# ── État interne ───────────────────────────────────────────────────────────────

_settings: dict = {}

# ── API publique ───────────────────────────────────────────────────────────────

def load() -> dict:
    """Charge settings.json. Complète les clés manquantes avec les défauts."""
    global _settings
    _settings = dict(_DEFAULTS)
    if os.path.isfile(_SETTINGS_FILE):
        try:
            with open(_SETTINGS_FILE, "r", encoding="utf-8") as f:
                user = json.load(f)
            for k, v in user.items():
                if k in _DEFAULTS:
                    _settings[k] = v
        except (json.JSONDecodeError, OSError):
            pass
    return _settings


def save() -> None:
    """Écrit les préférences courantes dans settings.json."""
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
