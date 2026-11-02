"""
tests/test_config.py — Astræos design tokens
=============================================
The three themes carry the values of the design system's tokens.json, old
theme names still open the right theme, and text keeps its contrast.

Run with: pytest tests/
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import THEME_NAMES, Config, mix  # noqa: E402


def _luminance(hex_color):
    def channel(c):
        c = c / 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def _contrast(a, b):
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


@pytest.fixture(autouse=True)
def back_to_nuit():
    yield
    Config.apply_theme("nuit")


class TestThemes:
    def test_three_themes(self):
        assert THEME_NAMES == ("nuit", "jour", "observation")

    def test_tokens_of_the_design_system(self):
        """A few values copied from tokens.json."""
        Config.apply_theme("nuit")
        assert (Config.CIEL_000, Config.ENCRE, Config.OR) == ("#0b0f17", "#e8ecf2", "#f2b84b")
        Config.apply_theme("jour")
        assert (Config.CIEL_000, Config.ENCRE, Config.OR) == ("#f6f4ef", "#141a24", "#8f5c00")
        Config.apply_theme("observation")
        assert (Config.CIEL_000, Config.ENCRE, Config.LUNE) == ("#0a0000", "#ff5a46", "#e04a35")

    def test_sur_or_is_ciel_000(self):
        for theme in THEME_NAMES:
            Config.apply_theme(theme)
            assert Config.SUR_OR == Config.CIEL_000

    @pytest.mark.parametrize("old, new", [("mocha", "nuit"), ("frape", "nuit"),
                                          ("frapé", "nuit"), ("latte", "jour"),
                                          ("Observation", "observation"), ("?", "nuit"),
                                          (None, "nuit")])
    def test_old_and_unknown_names(self, old, new):
        assert Config.normalize_theme(old) == new
        Config.apply_theme(old)
        assert Config.THEME == new

    def test_token_accessor(self):
        Config.apply_theme("jour")
        assert Config.token("ciel-200") == Config.CIEL_200 == "#e3dfd5"

    @pytest.mark.parametrize("theme", THEME_NAMES)
    def test_text_contrast(self, theme):
        """Text pairs reach 4.5:1 in every theme (design system rule)."""
        Config.apply_theme(theme)
        for ink in (Config.ENCRE, Config.ENCRE_ATTENUEE):
            for ground in (Config.CIEL_000, Config.CIEL_100):
                assert _contrast(ink, ground) >= 4.5, (theme, ink, ground)
        assert _contrast(Config.SUR_OR, Config.OR) >= 4.5


class TestMix:
    def test_ends(self):
        assert mix("#000000", "#ffffff", 1.0) == "#000000"
        assert mix("#000000", "#ffffff", 0.0) == "#ffffff"

    def test_middle(self):
        assert mix("#000000", "#ffffff", 0.5) == "#808080"
