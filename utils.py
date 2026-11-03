"""
utils.py — Formatting Utilities for Céleste
============================================
Converts raw numeric values (decimal degrees, decimal hours,
phase angles) into readable character strings for the graphical interface.
"""

# ==========================================================
# 2. DATA FORMATTING
# ==========================================================
class Formatters:
    """Utility functions for text formatting of astronomical coordinates."""

    @staticmethod
    def utc_offset(hours):
        """« UTC+1 », « UTC+5:30 », « UTC−3:30 » for an offset in hours."""
        minutes = round(hours * 60)
        h, m = divmod(abs(minutes), 60)
        return f"UTC{'+' if minutes >= 0 else '−'}{h}" + (f":{m:02d}" if m else "")

    # Angle formats offered: degrees-minutes-seconds, degrees and decimal
    # minutes, decimal degrees (in hours for a right ascension)
    ANGLE_FORMATS = ("dms", "dm", "dd")

    @staticmethod
    def angle(value, fmt="dms", signed=False, hours=False):
        """
        Formats an angle given in degrees, or in hours for a right ascension.

        Args:
            value (float): Angle (degrees, or hours if *hours*).
            fmt (str): "dms" → 123° 45′ 07″ (8h 45m 12.3s),
                       "dm"  → 123° 45.12′ (8h 45.205m),
                       "dd"  → 123.45197° (8.75342h).
            signed (bool): Always write the sign (latitudes, declinations).
            hours (bool): Units h, m, s instead of °, ′, ″.

        Returns:
            str: The formatted angle, "-" for a negative one (ASCII minus).
        """
        sign = "-" if value < 0 else ("+" if signed else "")
        value = abs(value)
        u1, u2, u3 = ("h", "m", "s") if hours else ("°", "′", "″")
        if fmt == "dd":
            return f"{sign}{value:.5f}{u1}"
        whole = int(value)
        if fmt == "dm":
            digits = 3 if hours else 2
            minutes = round((value - whole) * 60.0, digits)
            if minutes >= 60.0:
                whole, minutes = whole + 1, 0.0
            return f"{sign}{whole}{u1} {minutes:0{3 + digits}.{digits}f}{u2}"
        minutes = int((value - whole) * 60.0)
        digits = 1 if hours else 0
        seconds = round(((value - whole) * 60.0 - minutes) * 60.0, digits)
        if seconds >= 60.0:
            minutes, seconds = minutes + 1, 0.0
        if minutes >= 60:
            whole, minutes = whole + 1, 0
        sec = f"{seconds:04.1f}" if hours else f"{int(seconds):02d}"
        return f"{sign}{whole}{u1} {minutes:02d}{u2} {sec}{u3}"

    @staticmethod
    def hms(decimal_hours):
        """
        Converts Right Ascension from decimal hours to Hours/Minutes/Seconds format.

        Args:
            decimal_hours (float): Right Ascension in decimal hours (absolute value used).

        Returns:
            str: Formatted string, ex. "5h 34m 32.0s".
        """
        decimal_hours = abs(decimal_hours)
        h = int(decimal_hours)
        m = int((decimal_hours - h) * 60)
        s = round((decimal_hours - h - m / 60.0) * 3600.0, 1)
        if s >= 60:
            s = 0.0
            m += 1
        if m >= 60:
            m = 0
            h += 1
        return f"{h}h {m:02d}m {s:04.1f}s"

    @staticmethod
    def dms(decimal_degrees):
        """
        Converts Declination from decimal degrees to Degrees/Minutes/Seconds format.

        Args:
            decimal_degrees (float): Declination in decimal degrees (can be negative).

        Returns:
            str: Formatted string, ex. "-23° 26' 44\"".
        """
        sign = "-" if decimal_degrees < 0 else ""
        decimal_degrees = abs(decimal_degrees)
        d = int(decimal_degrees)
        m = int((decimal_degrees - d) * 60)
        s = round((decimal_degrees - d - m / 60.0) * 3600.0, 0)
        if s >= 60:
            s = 0
            m += 1
        if m >= 60:
            m = 0
            d += 1
        return f"{sign}{d}° {m:02d}' {int(s):02d}\""

    # Eight phase sectors of 45°, centred on the principal phases:
    # (translation key in the "phases" section of the locales, emoji, English name)
    PHASES = (
        ("new_moon",        "🌑", "New Moon"),
        ("waxing_crescent", "🌒", "Waxing Crescent"),
        ("first_quarter",   "🌓", "First Quarter"),
        ("waxing_gibbous",  "🌔", "Waxing Gibbous"),
        ("full_moon",       "🌕", "Full Moon"),
        ("waning_gibbous",  "🌖", "Waning Gibbous"),
        ("last_quarter",    "🌗", "Last Quarter"),
        ("waning_crescent", "🌘", "Waning Crescent"),
    )

    @staticmethod
    def phase_index(phase_angle):
        """
        Index in ``PHASES`` of the sector containing *phase_angle*.

        Args:
            phase_angle (float): Moon longitude − Sun longitude, in degrees (any range).

        Returns:
            int: 0 (new moon) to 7 (waning crescent).
        """
        return int(((phase_angle % 360) + 22.5) // 45) % 8

    @staticmethod
    def lunar_phase(illumination, phase_angle):
        """
        Returns a textual description of lunar phase with emoji.

        The phase is determined by the phase angle (difference between
        Moon's ecliptic longitude and Sun's ecliptic longitude),
        divided into 8 sectors of 45°.

        Args:
            illumination (float): Percentage of visible face illumination [0, 100].
            phase_angle (float): Phase angle in degrees (Moon longitude − Sun longitude).

        Returns:
            str: Formatted string, ex. "73.2% 🌔 Waxing Gibbous".
        """
        _, emoji, name = Formatters.PHASES[Formatters.phase_index(phase_angle)]
        return f"{illumination:.1f}% {emoji} {name}"
