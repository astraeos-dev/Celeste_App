"""
i18n.py — Système d'internationalisation de Céleste
=====================================================
Charge les traductions depuis des fichiers JSON dans le dossier ``locales/``
et expose une API minimaliste pour le reste de l'application.

API publique
------------
- ``t(key)``            → chaîne traduite (notation pointée : ``t("sun.title")``)
- ``tf(key, **values)`` → chaîne traduite dont les ``{champs}`` sont remplis
- ``switch_lang(code)`` → change la langue active et recharge le fichier
- ``get_lang()``        → code langue actif (``"fr"``, ``"en"``, …)
- ``available_langs()`` → liste des codes langue disponibles
- ``lang_name(code)``   → nom natif d'une langue (``"Français"``, ``"English"``, …)
- ``resolve_lang(code, system_locale)`` → ``"auto"`` remplacé par la langue
  du système si elle est traduite, sinon l'anglais

Fallback : si une clé est absente de la langue active, la valeur de la langue
de référence (``fr``) est utilisée. Si la clé est introuvable partout,
la clé elle-même est retournée entre crochets : ``[sun.title]``.
"""

import json
import os

# ── Configuration ─────────────────────────────────────────────────────

_LOCALES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "locales")
# Translation fallback language — used when a key is missing from the active locale.
# This is NOT the UI default language (the "lang" preference, "auto" by default,
# see resolve_lang). Keep as "fr": the French locale is the reference file.
_FALLBACK_LANG = "fr"

# Language chosen by "auto" when the system language has no translation.
_AUTO_DEFAULT_LANG = "en"

# Métadonnées des langues supportées — nom natif affiché dans le sélecteur.
# Pour ajouter une langue : créer ``locales/xx.json`` et ajouter une entrée ici.
_LANG_META = {
    "fr": "Français",
    "en": "English",
    "es": "Español",
    "de": "Deutsch",
}

# ── État interne ──────────────────────────────────────────────────────

_current_lang: str = _FALLBACK_LANG
_translations: dict = {}       # langue active (dict plat clé → valeur)
_fallback_cache: dict = {}     # langue de référence (chargée une seule fois)


# ── Chargement ────────────────────────────────────────────────────────

def _flatten(d: dict, prefix: str = "") -> dict:
    """Aplatit un dict imbriqué en clés pointées : ``{"a": {"b": "x"}}`` → ``{"a.b": "x"}``."""
    out = {}
    for k, v in d.items():
        full = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            out.update(_flatten(v, full))
        else:
            out[full] = v
    return out


def _load_json(code: str) -> dict:
    """Charge et aplatit ``locales/{code}.json``. Retourne ``{}`` si absent."""
    path = os.path.join(_LOCALES_DIR, f"{code}.json")
    if not os.path.isfile(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return _flatten(json.load(f))


def _ensure_fallback():
    """Charge la langue de référence si elle n'est pas déjà en cache."""
    global _fallback_cache
    if not _fallback_cache:
        _fallback_cache = _load_json(_FALLBACK_LANG)


# ── API publique ──────────────────────────────────────────────────────

def switch_lang(code: str) -> None:
    """
    Change la langue active.

    Args:
        code: Code ISO 639-1 (``"fr"``, ``"en"``, ``"es"``, ``"de"``).
              Si le fichier JSON correspondant n'existe pas, la langue
              de référence (``fr``) est utilisée.
    """
    global _current_lang, _translations
    _ensure_fallback()
    _current_lang = code
    if code == _FALLBACK_LANG:
        _translations = _fallback_cache
    else:
        loaded = _load_json(code)
        _translations = loaded if loaded else _fallback_cache


def get_lang() -> str:
    """Retourne le code de la langue active."""
    return _current_lang


def available_langs() -> list[str]:
    """
    Retourne la liste des codes langue dont le fichier JSON existe.

    Seules les langues présentes à la fois dans ``_LANG_META`` et
    dans le dossier ``locales/`` sont retournées.
    """
    langs = []
    for code in _LANG_META:
        path = os.path.join(_LOCALES_DIR, f"{code}.json")
        if os.path.isfile(path):
            langs.append(code)
    return langs


def lang_name(code: str) -> str:
    """Retourne le nom natif d'une langue (``"Français"``, ``"English"``, …)."""
    return _LANG_META.get(code, code)


def t(key: str) -> str:
    """
    Retourne la traduction de *key* dans la langue active.

    Résolution :
    1. Langue active
    2. Langue de référence (``fr``)
    3. ``[key]`` (clé entre crochets, indique une traduction manquante)

    Args:
        key: Clé en notation pointée, ex. ``"sun.title"`` ou ``"phases.new_moon"``.

    Returns:
        Chaîne traduite, ou ``[key]`` si introuvable.
    """
    _ensure_fallback()
    if not _translations:
        # Première utilisation avant switch_lang() : charger la langue par défaut
        switch_lang(_FALLBACK_LANG)
    val = _translations.get(key)
    if val is not None:
        return val
    val = _fallback_cache.get(key)
    if val is not None:
        return val
    return f"[{key}]"


def tf(key: str, /, **values) -> str:
    """
    Traduit *key* puis remplit ses champs ``{nom}`` avec *values*
    (un champ peut lui-même s'appeler ``key``).

    Un champ absent de *values* laisse la chaîne telle quelle plutôt que
    de lever une exception : une traduction incomplète ne bloque pas l'interface.
    """
    text = t(key)
    try:
        return text.format(**values)
    except (KeyError, IndexError, ValueError):
        return text


def resolve_lang(code, system_locale=None) -> str:
    """
    Retourne le code de langue à utiliser pour la préférence *code*.

    ``"auto"`` (ou une valeur vide) désigne la langue du système : les deux
    premières lettres de *system_locale* (``"fr_FR"`` → ``"fr"``) si un fichier
    de traduction existe pour elle, sinon l'anglais. Tout autre code est
    retourné tel quel.
    """
    if code and code != "auto":
        return code
    sys_code = (system_locale or "").replace("-", "_").split("_")[0].lower()
    return sys_code if sys_code in available_langs() else _AUTO_DEFAULT_LANG


# ── Initialisation au chargement du module ────────────────────────────
switch_lang(_FALLBACK_LANG)
