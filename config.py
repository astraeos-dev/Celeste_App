"""
config.py — Configuration and Visual Themes for Céleste
======================================================
Centralizes color palettes (Catppuccin Mocha / Frappé / Latte) and global
application parameters.

Usage:
    from config import Config
    # At startup, call Config.apply_theme(prefs.get("theme")) before building the UI.
    # The interface calls it again when the theme changes, then redraws itself.
"""

# ──────────────────────────────────────────────────────────────────────────────
# THEME PRESETS  (Catppuccin family)
# ──────────────────────────────────────────────────────────────────────────────
#
# BG_*        window, tab pane, card and input field backgrounds
# FG_*        text and accent colors
# BTN_COLOR   accent color (primary button, selection, sliders)
# GRID_COLOR  borders, separators and chart grids
# TW_*        twilight bands of the trajectory chart (day → night)
# PLANET_*    planet colors in tables and the orrery
# MODE        "dark" or "light"

_THEMES = {
    "mocha": {
        "BG_MAIN":    "#1B1B25",
        "BG_PANEL":   "#222230",
        "BG_CARD":    "#292938",
        "BG_INPUT":   "#1B1B25",
        "FG_LABEL":   "#A0A0B0",
        "FG_MUTED":   "#7F849C",
        "FG_WHITE":   "#FFFFFF",
        "FG_SUN":     "#F9E2AF",
        "FG_MOON":    "#89B4FA",
        "FG_GREEN":   "#A6E3A1",
        "FG_PURPLE":  "#CBA6F7",
        "FG_RED":     "#F38BA8",
        "BTN_COLOR":  "#89B4FA",
        "GRID_COLOR": "#45475A",
        "TW_DAY":     "#33456A",
        "TW_CIVIL":   "#2C3657",
        "TW_NAUT":    "#252B46",
        "TW_ASTRO":   "#1F2238",
        "TW_NIGHT":   "#191A29",
        "PLANET_VENUS":   "#D4C060",
        "PLANET_MARS":    "#E07050",
        "PLANET_JUPITER": "#C8A870",
        "PLANET_SATURN":  "#C0C060",
        "MODE":       "dark",
    },
    "frape": {
        "BG_MAIN":    "#232634",
        "BG_PANEL":   "#292C3C",
        "BG_CARD":    "#303446",
        "BG_INPUT":   "#232634",
        "FG_LABEL":   "#A5ADCE",
        "FG_MUTED":   "#838BA7",
        "FG_WHITE":   "#C6D0F5",
        "FG_SUN":     "#EF9F76",
        "FG_MOON":    "#8CAAEE",
        "FG_GREEN":   "#A6D189",
        "FG_PURPLE":  "#CA9EE6",
        "FG_RED":     "#E78284",
        "BTN_COLOR":  "#8CAAEE",
        "GRID_COLOR": "#414559",
        "TW_DAY":     "#3E5079",
        "TW_CIVIL":   "#364266",
        "TW_NAUT":    "#2F3754",
        "TW_ASTRO":   "#292E45",
        "TW_NIGHT":   "#232636",
        "PLANET_VENUS":   "#E5C890",
        "PLANET_MARS":    "#EA999C",
        "PLANET_JUPITER": "#EF9F76",
        "PLANET_SATURN":  "#E5C890",
        "MODE":       "dark",
    },
    "latte": {
        "BG_MAIN":    "#EFF1F5",
        "BG_PANEL":   "#E6E9EF",
        "BG_CARD":    "#F7F8FA",
        "BG_INPUT":   "#FFFFFF",
        "FG_LABEL":   "#5C5F77",
        "FG_MUTED":   "#8C8FA1",
        "FG_WHITE":   "#4C4F69",
        "FG_SUN":     "#FE640B",
        "FG_MOON":    "#1E66F5",
        "FG_GREEN":   "#40A02B",
        "FG_PURPLE":  "#8839EF",
        "FG_RED":     "#D20F39",
        "BTN_COLOR":  "#1E66F5",
        "GRID_COLOR": "#ACB0BE",
        "TW_DAY":     "#F4F8FF",
        "TW_CIVIL":   "#DCE5F5",
        "TW_NAUT":    "#C6D1EA",
        "TW_ASTRO":   "#B1BEDF",
        "TW_NIGHT":   "#A0AED5",
        "PLANET_VENUS":   "#A47A00",
        "PLANET_MARS":    "#C2410C",
        "PLANET_JUPITER": "#8B5E34",
        "PLANET_SATURN":  "#7C7C00",
        "MODE":       "light",
    },
}

# Theme names shown in the settings, in display order
THEME_NAMES = ("mocha", "frape", "latte")

# The sky map stays a night sky in every theme, so it has its own palette
SKY = {
    "FIG":      "#04040E",   # around the dome (dark themes)
    "DOME":     "#06061A",   # inside the horizon circle
    "TITLE":    "#C8D4FF",
    "TICK":     "#8899BB",
    "GRID":     "#0F1E35",
    "HORIZON":  "#2A4466",
    "RING":     "#1B3050",
    "ZENITH":   "#445566",
    "STAR":     "#F5F7FF",
    "STAR_LBL": "#9AA6C8",
    "LINE":     "#3A5A8C",
    "SUN":      "#F9E2AF",
    "MOON":     "#C6D8FF",
    "VENUS":    "#D4C060",
    "MARS":     "#E07050",
    "JUPITER":  "#C8A870",
    "SATURN":   "#C0C060",
}


# ──────────────────────────────────────────────────────────────────────────────
# CONFIG CLASS
# ──────────────────────────────────────────────────────────────────────────────

class Config:
    """Color palette and global parameters for Céleste application."""

    # Name of the active theme (key of _THEMES)
    THEME = "mocha"

    # Active colors (defaults = mocha)
    BG_MAIN    = "#1B1B25"
    BG_PANEL   = "#222230"
    BG_CARD    = "#292938"
    BG_INPUT   = "#1B1B25"
    FG_LABEL   = "#A0A0B0"
    FG_MUTED   = "#7F849C"
    FG_WHITE   = "#FFFFFF"
    FG_SUN     = "#F9E2AF"
    FG_MOON    = "#89B4FA"
    FG_GREEN   = "#A6E3A1"
    FG_PURPLE  = "#CBA6F7"
    FG_RED     = "#F38BA8"
    BTN_COLOR  = "#89B4FA"
    GRID_COLOR = "#45475A"
    TW_DAY     = "#33456A"
    TW_CIVIL   = "#2C3657"
    TW_NAUT    = "#252B46"
    TW_ASTRO   = "#1F2238"
    TW_NIGHT   = "#191A29"
    PLANET_VENUS   = "#D4C060"
    PLANET_MARS    = "#E07050"
    PLANET_JUPITER = "#C8A870"
    PLANET_SATURN  = "#C0C060"
    MODE       = "dark"

    @staticmethod
    def normalize_theme(theme_name) -> str:
        """Return the key of a theme ("frapé" → "frape"), mocha if unknown."""
        key = (theme_name or "mocha").lower().replace("é", "e")
        return key if key in _THEMES else "mocha"

    @classmethod
    def apply_theme(cls, theme_name: str) -> None:
        """Apply a named theme preset to all Config color attributes."""
        key = cls.normalize_theme(theme_name)
        for attr, value in _THEMES[key].items():
            setattr(cls, attr, value)
        cls.THEME = key

    @classmethod
    def is_dark(cls) -> bool:
        """True for the dark themes (mocha, frappé)."""
        return cls.MODE == "dark"

    @classmethod
    def planet_color(cls, name: str) -> str:
        """Theme color of a planet ("Venus", "Mars", "Jupiter", "Saturn")."""
        return getattr(cls, f"PLANET_{name.upper()}", cls.FG_LABEL)
