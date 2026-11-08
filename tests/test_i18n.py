"""
tests/test_i18n.py — Unit tests of the internationalisation system
===================================================================
Checks the loading of the JSON files, the language switch, the fallback, and
the consistency between the translation files.

Run with:  pytest tests/test_i18n.py -v
"""

import sys
import os
import json
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from i18n import (t, tf, switch_lang, get_lang, available_langs, lang_name,
                  resolve_lang, _load_json)


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────

LOCALES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "locales")


def _all_keys(code):
    """The set of flattened keys of a language file."""
    return set(_load_json(code).keys())


# ──────────────────────────────────────────────────────────────────────
# 1. Loading and basic API
# ──────────────────────────────────────────────────────────────────────

class TestI18nBase:
    def setup_method(self):
        """French back as the active language before each test."""
        switch_lang("fr")

    def test_default_lang_is_fr(self):
        """The default language is French."""
        assert get_lang() == "fr"

    def test_t_returns_string(self):
        """t() always returns a string."""
        assert isinstance(t("app.title"), str)

    def test_t_known_key(self):
        """A known key returns a non-empty translation."""
        val = t("app.title")
        assert val and not val.startswith("[")

    def test_t_unknown_key_returns_bracket(self):
        """An unknown key returns [key]."""
        val = t("this.key.does.not.exist")
        assert val == "[this.key.does.not.exist]"

    def test_available_langs_includes_fr_en(self):
        """FR and EN are available."""
        langs = available_langs()
        assert "fr" in langs
        assert "en" in langs

    def test_lang_name(self):
        """lang_name returns the native names."""
        assert lang_name("fr") == "Français"
        assert lang_name("en") == "English"
        assert lang_name("es") == "Español"
        assert lang_name("de") == "Deutsch"


# ──────────────────────────────────────────────────────────────────────
# 2. Language switch
# ──────────────────────────────────────────────────────────────────────

class TestSwitchLang:
    def test_switch_to_en(self):
        """Switching to English changes the active language."""
        switch_lang("en")
        assert get_lang() == "en"

    def test_switch_changes_translations(self):
        """The translations do change after a switch."""
        switch_lang("fr")
        fr_title = t("sun.title")
        switch_lang("en")
        en_title = t("sun.title")
        assert fr_title != en_title
        assert "Soleil" in fr_title
        assert "Sun" in en_title

    def test_switch_back_to_fr(self):
        """Switching back to French works."""
        switch_lang("en")
        switch_lang("fr")
        assert get_lang() == "fr"
        assert "Soleil" in t("sun.title")

    def test_switch_unknown_lang_fallback(self):
        """An unknown language falls back to French."""
        switch_lang("xx")
        assert get_lang() == "xx"
        # The translations fall back to FR
        assert t("app.title") != "[app.title]"


# ──────────────────────────────────────────────────────────────────────
# 3. Fallback
# ──────────────────────────────────────────────────────────────────────

class TestFallback:
    def test_missing_key_in_en_falls_to_fr(self):
        """When a key is missing in EN, the FR value is returned."""
        # If fr.json has a key that en.json lacks, the fallback must work.
        # Tested with app.header, which exists everywhere.
        switch_lang("en")
        val = t("app.header")
        assert val and not val.startswith("[")


# ──────────────────────────────────────────────────────────────────────
# 4. Consistency of the translation files
# ──────────────────────────────────────────────────────────────────────

class TestTranslationCoherence:
    """All the translation files have the same keys."""

    def test_en_has_all_fr_keys(self):
        """EN covers all the keys of FR (no missing translation)."""
        fr_keys = _all_keys("fr")
        en_keys = _all_keys("en")
        missing = fr_keys - en_keys
        assert not missing, f"Missing keys in en.json: {missing}"

    def test_en_has_no_extra_keys(self):
        """EN has no extra keys absent from FR."""
        fr_keys = _all_keys("fr")
        en_keys = _all_keys("en")
        extra = en_keys - fr_keys
        assert not extra, f"Extra keys in en.json: {extra}"

    def test_no_empty_values_in_fr(self):
        """No empty value in FR (except lang.restart_hint)."""
        data = _load_json("fr")
        empty = [k for k, v in data.items()
                 if isinstance(v, str) and v == "" and k != "lang.restart_hint"]
        assert not empty, f"Empty values in fr.json: {empty}"

    def test_no_empty_values_in_en(self):
        """No empty value in EN (except lang.restart_hint)."""
        data = _load_json("en")
        empty = [k for k, v in data.items()
                 if isinstance(v, str) and v == "" and k != "lang.restart_hint"]
        assert not empty, f"Empty values in en.json: {empty}"

    def test_placeholders_consistent(self):
        """The {xxx} placeholders are the same in FR and EN."""
        import re
        fr_data = _load_json("fr")
        en_data = _load_json("en")
        pattern = re.compile(r'\{(\w+)\}')

        mismatches = []
        for key in fr_data:
            if key not in en_data:
                continue
            fr_ph = set(pattern.findall(str(fr_data[key])))
            en_ph = set(pattern.findall(str(en_data[key])))
            if fr_ph != en_ph:
                mismatches.append(f"{key}: FR={fr_ph} EN={en_ph}")

        assert not mismatches, (
            "Inconsistent placeholders:\n" + "\n".join(mismatches))


    @pytest.mark.parametrize("code", ["es", "de"])
    def test_other_locales_match_fr(self, code):
        """ES and DE have exactly the keys of FR: nothing falls back to French."""
        fr_keys = _all_keys("fr")
        keys = _all_keys(code)
        assert not fr_keys - keys, f"Missing keys in {code}.json: {fr_keys - keys}"
        assert not keys - fr_keys, f"Extra keys in {code}.json: {keys - fr_keys}"

    @pytest.mark.parametrize("code", ["en", "es", "de"])
    def test_placeholders_consistent_all_locales(self, code):
        """The {xxx} placeholders are the same in every language."""
        import re
        pattern = re.compile(r'\{(\w+)\}')
        fr_data = _load_json("fr")
        data = _load_json(code)
        mismatches = [k for k in fr_data if k in data and
                      set(pattern.findall(fr_data[k])) != set(pattern.findall(data[k]))]
        assert not mismatches, f"Inconsistent placeholders in {code}.json: {mismatches}"


# ──────────────────────────────────────────────────────────────────────
# 5. Automatic language and formatting
# ──────────────────────────────────────────────────────────────────────

class TestResolveLang:
    def test_explicit_code_is_kept(self):
        assert resolve_lang("de", "fr_FR") == "de"

    def test_auto_follows_system_language(self):
        assert resolve_lang("auto", "fr_FR") == "fr"
        assert resolve_lang("auto", "es-ES") == "es"
        assert resolve_lang("", "de_DE.UTF-8") == "de"

    def test_auto_falls_back_to_english(self):
        assert resolve_lang("auto", "ja_JP") == "en"
        assert resolve_lang("auto", None) == "en"


class TestTf:
    def setup_method(self):
        switch_lang("fr")

    def test_fills_placeholders(self):
        assert tf("status.stars_many", n=12) == "12 étoiles visibles"

    def test_placeholder_named_key(self):
        """A field can be named "key", like the parameter of tf()."""
        assert "F5" in tf("side.calculate_tip", key="F5")

    def test_missing_value_returns_raw_text(self):
        assert tf("status.stars_many") == t("status.stars_many")


# ──────────────────────────────────────────────────────────────────────
# 6. Format of the JSON files
# ──────────────────────────────────────────────────────────────────────

class TestJsonFormat:
    def test_fr_json_valid(self):
        """fr.json is valid JSON."""
        path = os.path.join(LOCALES_DIR, "fr.json")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, dict)

    def test_en_json_valid(self):
        """en.json is valid JSON."""
        path = os.path.join(LOCALES_DIR, "en.json")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, dict)
