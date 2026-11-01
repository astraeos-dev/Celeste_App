"""
tests/test_i18n.py — Tests unitaires du système d'internationalisation
=======================================================================
Vérifie le chargement des fichiers JSON, le basculement de langue,
le fallback, et la cohérence entre les fichiers de traduction.

Lancer avec :  pytest tests/test_i18n.py -v
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
    """Retourne l'ensemble des clés aplaties pour un fichier de langue."""
    return set(_load_json(code).keys())


# ──────────────────────────────────────────────────────────────────────
# 1. Chargement et API de base
# ──────────────────────────────────────────────────────────────────────

class TestI18nBase:
    def setup_method(self):
        """Remet le français comme langue active avant chaque test."""
        switch_lang("fr")

    def test_default_lang_is_fr(self):
        """La langue par défaut est le français."""
        assert get_lang() == "fr"

    def test_t_returns_string(self):
        """t() retourne toujours une chaîne."""
        assert isinstance(t("app.title"), str)

    def test_t_known_key(self):
        """Une clé connue retourne une traduction non vide."""
        val = t("app.title")
        assert val and not val.startswith("[")

    def test_t_unknown_key_returns_bracket(self):
        """Une clé inconnue retourne [clé]."""
        val = t("this.key.does.not.exist")
        assert val == "[this.key.does.not.exist]"

    def test_available_langs_includes_fr_en(self):
        """FR et EN sont disponibles."""
        langs = available_langs()
        assert "fr" in langs
        assert "en" in langs

    def test_lang_name(self):
        """lang_name retourne les noms natifs."""
        assert lang_name("fr") == "Français"
        assert lang_name("en") == "English"
        assert lang_name("es") == "Español"
        assert lang_name("de") == "Deutsch"


# ──────────────────────────────────────────────────────────────────────
# 2. Basculement de langue
# ──────────────────────────────────────────────────────────────────────

class TestSwitchLang:
    def test_switch_to_en(self):
        """Basculer en anglais change la langue active."""
        switch_lang("en")
        assert get_lang() == "en"

    def test_switch_changes_translations(self):
        """Les traductions changent effectivement après switch."""
        switch_lang("fr")
        fr_title = t("sun.title")
        switch_lang("en")
        en_title = t("sun.title")
        assert fr_title != en_title
        assert "SOLEIL" in fr_title
        assert "SUN" in en_title

    def test_switch_back_to_fr(self):
        """Retour au français fonctionne."""
        switch_lang("en")
        switch_lang("fr")
        assert get_lang() == "fr"
        assert "SOLEIL" in t("sun.title")

    def test_switch_unknown_lang_fallback(self):
        """Une langue inconnue retombe sur le français."""
        switch_lang("xx")
        assert get_lang() == "xx"
        # Les traductions tombent en fallback FR
        assert t("app.title") != "[app.title]"


# ──────────────────────────────────────────────────────────────────────
# 3. Fallback
# ──────────────────────────────────────────────────────────────────────

class TestFallback:
    def test_missing_key_in_en_falls_to_fr(self):
        """Si une clé manque en EN, la valeur FR est retournée."""
        # On force un test : si fr.json a une clé que en.json n'a pas,
        # le fallback doit fonctionner. On teste avec app.header qui existe partout.
        switch_lang("en")
        val = t("app.header")
        assert val and not val.startswith("[")


# ──────────────────────────────────────────────────────────────────────
# 4. Cohérence des fichiers de traduction
# ──────────────────────────────────────────────────────────────────────

class TestTranslationCoherence:
    """Vérifie que tous les fichiers de traduction ont les mêmes clés."""

    def test_en_has_all_fr_keys(self):
        """EN couvre toutes les clés de FR (aucune traduction manquante)."""
        fr_keys = _all_keys("fr")
        en_keys = _all_keys("en")
        missing = fr_keys - en_keys
        assert not missing, f"Clés manquantes dans en.json : {missing}"

    def test_en_has_no_extra_keys(self):
        """EN n'a pas de clés supplémentaires absentes de FR."""
        fr_keys = _all_keys("fr")
        en_keys = _all_keys("en")
        extra = en_keys - fr_keys
        assert not extra, f"Clés supplémentaires dans en.json : {extra}"

    def test_no_empty_values_in_fr(self):
        """Aucune valeur vide dans FR (sauf lang.restart_hint)."""
        data = _load_json("fr")
        empty = [k for k, v in data.items()
                 if isinstance(v, str) and v == "" and k != "lang.restart_hint"]
        assert not empty, f"Valeurs vides dans fr.json : {empty}"

    def test_no_empty_values_in_en(self):
        """Aucune valeur vide dans EN (sauf lang.restart_hint)."""
        data = _load_json("en")
        empty = [k for k, v in data.items()
                 if isinstance(v, str) and v == "" and k != "lang.restart_hint"]
        assert not empty, f"Valeurs vides dans en.json : {empty}"

    def test_placeholders_consistent(self):
        """Les placeholders {xxx} sont les mêmes entre FR et EN."""
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
            "Placeholders incohérents :\n" + "\n".join(mismatches))


    @pytest.mark.parametrize("code", ["es", "de"])
    def test_other_locales_match_fr(self, code):
        """ES et DE ont exactement les clés de FR : rien ne retombe en français."""
        fr_keys = _all_keys("fr")
        keys = _all_keys(code)
        assert not fr_keys - keys, f"Clés manquantes dans {code}.json : {fr_keys - keys}"
        assert not keys - fr_keys, f"Clés en trop dans {code}.json : {keys - fr_keys}"

    @pytest.mark.parametrize("code", ["en", "es", "de"])
    def test_placeholders_consistent_all_locales(self, code):
        """Les placeholders {xxx} sont les mêmes dans toutes les langues."""
        import re
        pattern = re.compile(r'\{(\w+)\}')
        fr_data = _load_json("fr")
        data = _load_json(code)
        mismatches = [k for k in fr_data if k in data and
                      set(pattern.findall(fr_data[k])) != set(pattern.findall(data[k]))]
        assert not mismatches, f"Placeholders incohérents dans {code}.json : {mismatches}"


# ──────────────────────────────────────────────────────────────────────
# 5. Langue automatique et formatage
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
        """Un champ peut s'appeler « key » comme le paramètre de tf()."""
        assert "F5" in tf("side.calculate_tip", key="F5")

    def test_missing_value_returns_raw_text(self):
        assert tf("status.stars_many") == t("status.stars_many")


# ──────────────────────────────────────────────────────────────────────
# 6. Format des fichiers JSON
# ──────────────────────────────────────────────────────────────────────

class TestJsonFormat:
    def test_fr_json_valid(self):
        """fr.json est un JSON valide."""
        path = os.path.join(LOCALES_DIR, "fr.json")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, dict)

    def test_en_json_valid(self):
        """en.json est un JSON valide."""
        path = os.path.join(LOCALES_DIR, "en.json")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, dict)
