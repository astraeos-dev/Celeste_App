"""
i18n.py — Internationalisation of Céleste
==========================================
Loads the translations from the JSON files of the ``locales/`` folder and
offers a minimal API to the rest of the application.

Public API
----------
- ``t(key)``            → translated string (dotted key: ``t("sun.title")``)
- ``tf(key, **values)`` → translated string with its ``{fields}`` filled
- ``switch_lang(code)`` → changes the active language and loads its file
- ``get_lang()``        → active language code (``"fr"``, ``"en"``, …)
- ``available_langs()`` → codes of the available languages
- ``lang_name(code)``   → native name of a language (``"Français"``, ``"English"``, …)
- ``resolve_lang(code, system_locale)`` → ``"auto"`` replaced by the system's
  language when it is translated, else English

Fallback: when a key is missing from the active language, the reference
language's value (``fr``) is used. When the key is found nowhere, the key
itself is returned in brackets: ``[sun.title]``.
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

# Supported languages — the native name shown in the selector.
# To add a language: create ``locales/xx.json`` and add an entry here.
_LANG_META = {
    "fr": "Français",
    "en": "English",
    "es": "Español",
    "de": "Deutsch",
}

# ── Internal state ────────────────────────────────────────────────────

_current_lang: str = _FALLBACK_LANG
_translations: dict = {}       # active language (flat dict key → value)
_fallback_cache: dict = {}     # reference language (loaded once)


# ── Loading ───────────────────────────────────────────────────────────

def _flatten(d: dict, prefix: str = "") -> dict:
    """Flattens a nested dict into dotted keys: ``{"a": {"b": "x"}}`` → ``{"a.b": "x"}``."""
    out = {}
    for k, v in d.items():
        full = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            out.update(_flatten(v, full))
        else:
            out[full] = v
    return out


def _load_json(code: str) -> dict:
    """Loads and flattens ``locales/{code}.json``; ``{}`` when missing."""
    path = os.path.join(_LOCALES_DIR, f"{code}.json")
    if not os.path.isfile(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return _flatten(json.load(f))


def _ensure_fallback():
    """Loads the reference language unless it is already cached."""
    global _fallback_cache
    if not _fallback_cache:
        _fallback_cache = _load_json(_FALLBACK_LANG)


# ── Public API ────────────────────────────────────────────────────────

def switch_lang(code: str) -> None:
    """
    Changes the active language.

    Args:
        code: ISO 639-1 code (``"fr"``, ``"en"``, ``"es"``, ``"de"``).
              When its JSON file does not exist, the reference language
              (``fr``) is used.
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
    """Code of the active language."""
    return _current_lang


def available_langs() -> list[str]:
    """
    Codes of the languages whose JSON file exists: only those both in
    ``_LANG_META`` and in the ``locales/`` folder.
    """
    langs = []
    for code in _LANG_META:
        path = os.path.join(_LOCALES_DIR, f"{code}.json")
        if os.path.isfile(path):
            langs.append(code)
    return langs


def lang_name(code: str) -> str:
    """Native name of a language (``"Français"``, ``"English"``, …)."""
    return _LANG_META.get(code, code)


def t(key: str) -> str:
    """
    Translation of *key* in the active language.

    Resolution:
    1. Active language
    2. Reference language (``fr``)
    3. ``[key]`` (the key in brackets, a missing translation)

    Args:
        key: Dotted key, e.g. ``"sun.title"`` or ``"phases.new_moon"``.

    Returns:
        The translated string, or ``[key]`` when not found.
    """
    _ensure_fallback()
    if not _translations:
        # First use before switch_lang(): load the default language
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
    Translates *key*, then fills its ``{name}`` fields with *values* (a field
    may itself be called ``key``).

    A field missing from *values* leaves the string as it is rather than
    raising: an incomplete translation does not block the interface.
    """
    text = t(key)
    try:
        return text.format(**values)
    except (KeyError, IndexError, ValueError):
        return text


def resolve_lang(code, system_locale=None) -> str:
    """
    The language code to use for the preference *code*.

    ``"auto"`` (or an empty value) means the system's language: the first two
    letters of *system_locale* (``"fr_FR"`` → ``"fr"``) when a translation
    file exists for it, else English. Any other code is returned as it is.
    """
    if code and code != "auto":
        return code
    sys_code = (system_locale or "").replace("-", "_").split("_")[0].lower()
    return sys_code if sys_code in available_langs() else _AUTO_DEFAULT_LANG


# ── Initialisation when the module loads ──────────────────────────────
switch_lang(_FALLBACK_LANG)
