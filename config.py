"""
config.py — Astræos design tokens for Céleste
=============================================
The colors of the three Astræos themes, copied from the design system's
tokens.json, and the spacing, radii and text styles the interface uses.

- Nuit (default): screens, evening use.
- Jour: daytime use and printed documents.
- Observation: everything red on black, to read the screen in the dark
  without losing the eye's adaptation.

Roles (README of the design system):
    ciel-000        page background
    ciel-100        cards, panels, windows, input fields
    ciel-200        hairlines, borders, gauge tracks (never text)
    encre           text and values
    encre-attenuee  labels, units, captions
    or              identity: the logo's star, the primary action, focus.
                    One gold area per screen.
    sur-or          text and icons on a gold fill (= ciel-000)
    lune            information: links, secondary data
    signal-ok, signal-alerte   states only, always with a word or an icon

Usage:
    from config import Config
    Config.apply_theme(prefs.get("theme"))   # before building the interface
    Config.ENCRE, Config.token("ciel-200")
"""

# Version of Céleste: the only place to change it (window, settings, executable,
# installer, GitHub requests). Raise it for each release, then push the tag
# v<version>: the build workflow checks that both agree.
APP_VERSION = "4.21"

# A beta build (scripts/build_exe.py with CELESTE_BETA=<n>, the Beta workflow) writes
# _build_info.py: the version is then "4.12 beta <n>", published as a pre-release that
# only its testers install; the release of the same version replaces it.
try:
    from _build_info import BETA as APP_BETA
except ImportError:
    APP_BETA = 0
APP_RELEASE = f"{APP_VERSION}-beta.{APP_BETA}" if APP_BETA else APP_VERSION   # files, tags, installer

# ──────────────────────────────────────────────────────────────────────────────
# COLOR TOKENS (tokens.json of the Astræos design system)
# ──────────────────────────────────────────────────────────────────────────────

THEME_NAMES = ("nuit", "jour", "observation")

_THEMES = {
    "nuit": {
        "ciel-000":       "#0b0f17",
        "ciel-100":       "#131a26",
        "ciel-200":       "#1f2a3b",
        "encre":          "#e8ecf2",
        "encre-attenuee": "#9aa6b8",
        "or":             "#f2b84b",
        "lune":           "#8fb8e8",
        "signal-ok":      "#5cc98a",
        "signal-alerte":  "#ff6b5e",
    },
    "jour": {
        "ciel-000":       "#f6f4ef",
        "ciel-100":       "#ffffff",
        "ciel-200":       "#e3dfd5",
        "encre":          "#141a24",
        "encre-attenuee": "#5a6372",
        "or":             "#8f5c00",
        "lune":           "#2f5d8f",
        "signal-ok":      "#1f7a48",
        "signal-alerte":  "#b3261e",
    },
    "observation": {
        "ciel-000":       "#0a0000",
        "ciel-100":       "#160303",
        "ciel-200":       "#2a0707",
        "encre":          "#ff5a46",
        "encre-attenuee": "#da4733",
        "or":             "#ff8a5c",
        "lune":           "#e04a35",
        "signal-ok":      "#e8604a",
        "signal-alerte":  "#ffa090",
    },
}
for _palette in _THEMES.values():
    _palette["sur-or"] = _palette["ciel-000"]          # alias, as in tokens.json

# Theme names of earlier versions of Céleste (Catppuccin)
_ALIASES = {"mocha": "nuit", "frape": "nuit", "frappe": "nuit", "latte": "jour",
            "night": "nuit", "day": "jour"}

# ──────────────────────────────────────────────────────────────────────────────
# SPACING, RADII, TYPE
# ──────────────────────────────────────────────────────────────────────────────

SPACE = {"espace-1": 4, "espace-2": 8, "espace-4": 16, "espace-6": 24}     # px
RADIUS = {"rayon-s": 4, "rayon-m": 10, "rayon-plein": 999}                   # px

# Families: Plex first, Astraeos Symboles after it for the astronomical symbols
FONT_SANS = ("IBM Plex Sans", "Astraeos Symboles")
FONT_MONO = ("IBM Plex Mono", "Astraeos Symboles")
FONT_SYMBOLS = ("Astraeos Symboles",)

# Text styles: name → (family, size px, line height px, weight)
TEXT_STYLES = {
    "affiche":    ("sans", 40, 44, 600),
    "titre":      ("sans", 24, 30, 600),
    "sous-titre": ("sans", 17, 24, 600),
    "corps":      ("sans", 15, 22, 400),
    "legende":    ("sans", 13, 18, 400),
    "donnee":     ("mono", 15, 22, 500),
    "cadran":     ("mono", 32, 36, 500),
}


def mix(color_a, color_b, weight_a):
    """
    Mix of two hex colors, *weight_a* of the first (0–1), like the design
    system's color-mix() for hover and pressed states.
    """
    a = [int(color_a[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(color_b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x * weight_a + y * (1 - weight_a)):02x}"
                         for x, y in zip(a, b))


# ──────────────────────────────────────────────────────────────────────────────
# CONFIG CLASS
# ──────────────────────────────────────────────────────────────────────────────

class Config:
    """Active Astræos theme: one attribute per color token."""

    THEME          = "nuit"
    CIEL_000       = "#0b0f17"
    CIEL_100       = "#131a26"
    CIEL_200       = "#1f2a3b"
    ENCRE          = "#e8ecf2"
    ENCRE_ATTENUEE = "#9aa6b8"
    OR             = "#f2b84b"
    SUR_OR         = "#0b0f17"
    LUNE           = "#8fb8e8"
    SIGNAL_OK      = "#5cc98a"
    SIGNAL_ALERTE  = "#ff6b5e"

    @staticmethod
    def normalize_theme(theme_name) -> str:
        """Key of a theme; old names are mapped ("latte" → "jour"), unknown → "nuit"."""
        key = (theme_name or "nuit").strip().lower().replace("é", "e")
        key = _ALIASES.get(key, key)
        return key if key in _THEMES else "nuit"

    @classmethod
    def apply_theme(cls, theme_name) -> None:
        """Make *theme_name* the active theme."""
        key = cls.normalize_theme(theme_name)
        for token, value in _THEMES[key].items():
            setattr(cls, token.upper().replace("-", "_"), value)
        cls.THEME = key

    @classmethod
    def token(cls, name) -> str:
        """Value of a color token ("ciel-200", "encre-attenuee"…) in the active theme."""
        return _THEMES[cls.THEME][name]

    @classmethod
    def is_dark(cls) -> bool:
        """True for Nuit and Observation."""
        return cls.THEME != "jour"
