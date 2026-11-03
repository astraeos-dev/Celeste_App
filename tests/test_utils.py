"""
tests/test_utils.py — Unit Tests for Céleste Formatting Utilities
==================================================================
Verifies the Formatters class (hms, dms, lunar_phase) against
hand-calculated expected values, including carry propagation and
edge cases.

Run with: pytest tests/
"""

import sys
import os

# Make root directory importable from tests/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from utils import Formatters


# ──────────────────────────────────────────────────────────────────────
# 1. hms — Right Ascension decimal hours → H/M/S string
# ──────────────────────────────────────────────────────────────────────

class TestHms:

    def test_typical_value(self):
        """Typical RA: 5h 34m 31.1s (Betelgeuse area)."""
        assert Formatters.hms(5.5753) == "5h 34m 31.1s"

    def test_zero(self):
        """Zero hours → all fields zero."""
        assert Formatters.hms(0.0) == "0h 00m 00.0s"

    def test_exact_hours(self):
        """Exact integer hours → minutes and seconds zero."""
        assert Formatters.hms(6.0) == "6h 00m 00.0s"

    def test_half_hours(self):
        """3.5 h → 3h 30m 00.0s."""
        assert Formatters.hms(3.5) == "3h 30m 00.0s"

    def test_negative_input_uses_abs(self):
        """Negative input: abs() is applied, result equals positive counterpart."""
        assert Formatters.hms(-3.5) == Formatters.hms(3.5)

    def test_output_contains_h_m_s(self):
        """Output format must contain 'h', 'm', 's' separators."""
        result = Formatters.hms(12.345)
        assert "h" in result and "m" in result and "s" in result

    def test_minutes_zero_padded(self):
        """Minutes < 10 must be zero-padded to 2 digits."""
        # 1h 05m 00.0s
        result = Formatters.hms(1.0 + 5 / 60.0)
        assert "05m" in result

    def test_carry_seconds_into_minutes(self):
        """When rounded seconds reach 60, they carry into minutes.

        5h 45m 59.97s → seconds round to 60 → 5h 46m 00.0s
        """
        # decimal_hours = 5 + 45/60 + 59.97/3600
        h = 5 + 45 / 60.0 + 59.97 / 3600.0
        assert Formatters.hms(h) == "5h 46m 00.0s"

    def test_carry_minutes_into_hours(self):
        """Seconds carry into minutes which then carry into hours.

        5h 59m 59.97s → 6h 00m 00.0s
        """
        h = 5 + 59 / 60.0 + 59.97 / 3600.0
        assert Formatters.hms(h) == "6h 00m 00.0s"

    def test_sirius_ra(self):
        """Sirius RA ≈ 6h 45m 08.9s (from star catalog)."""
        result = Formatters.hms(6.7523)
        assert result.startswith("6h 45m")


# ──────────────────────────────────────────────────────────────────────
# 2. dms — Declination decimal degrees → D/M/S string
# ──────────────────────────────────────────────────────────────────────

class TestDms:

    def test_typical_positive(self):
        """Positive declination: 23° 26' 44\"."""
        assert Formatters.dms(23.4456) == "23° 26' 44\""

    def test_typical_negative(self):
        """Negative declination: same absolute value, prepended with '-'."""
        assert Formatters.dms(-23.4456) == "-23° 26' 44\""

    def test_zero(self):
        """Zero degrees → all fields zero, no sign."""
        assert Formatters.dms(0.0) == "0° 00' 00\""

    def test_exact_degrees(self):
        """Exact integer degrees → minutes and seconds zero."""
        assert Formatters.dms(45.0) == "45° 00' 00\""

    def test_negative_small_has_sign(self):
        """Very small negative value still carries the '-' sign."""
        result = Formatters.dms(-0.001)
        assert result.startswith("-")

    def test_positive_has_no_sign(self):
        """Positive value must not have a leading sign."""
        result = Formatters.dms(10.0)
        assert not result.startswith("-") and not result.startswith("+")

    def test_seconds_zero_padded(self):
        """Seconds < 10 must be zero-padded to 2 digits."""
        # 10° 00' 03"
        result = Formatters.dms(10.0 + 3.0 / 3600.0)
        assert "'  03\"" not in result   # should be 2-digit, not 3
        assert "03\"" in result

    def test_carry_seconds_into_minutes(self):
        """When rounded seconds reach 60, they carry into minutes.

        10° 30' 59.7s → seconds round to 60 → 10° 31' 00\"
        """
        deg = 10 + 30 / 60.0 + 59.7 / 3600.0
        assert Formatters.dms(deg) == "10° 31' 00\""

    def test_carry_minutes_into_degrees(self):
        """Seconds carry into minutes which then carry into degrees.

        10° 59' 59.7\" → 11° 00' 00\"
        """
        deg = 10 + 59 / 60.0 + 59.7 / 3600.0
        assert Formatters.dms(deg) == "11° 00' 00\""

    def test_negative_carry(self):
        """Carry also works for negative values."""
        deg = -(10 + 59 / 60.0 + 59.7 / 3600.0)
        assert Formatters.dms(deg) == "-11° 00' 00\""

    def test_sirius_dec(self):
        """Sirius Dec ≈ -16° 42' 58\" (from star catalog)."""
        result = Formatters.dms(-16.7161)
        assert result.startswith("-16°")


# ──────────────────────────────────────────────────────────────────────
# 3. lunar_phase — phase angle → textual phase name with emoji
# ──────────────────────────────────────────────────────────────────────

class TestLunarPhase:

    # ── 8 sector midpoints ──────────────────────────────────────────

    def test_new_moon_sector(self):
        """Sector 0–22.5°: New Moon."""
        result = Formatters.lunar_phase(2.0, 0.0)
        assert "New Moon" in result and "🌑" in result

    def test_waxing_crescent_sector(self):
        """Sector 22.5–67.5°: Waxing Crescent."""
        result = Formatters.lunar_phase(25.0, 45.0)
        assert "Waxing Crescent" in result and "🌒" in result

    def test_first_quarter_sector(self):
        """Sector 67.5–112.5°: First Quarter."""
        result = Formatters.lunar_phase(50.0, 90.0)
        assert "First Quarter" in result and "🌓" in result

    def test_waxing_gibbous_sector(self):
        """Sector 112.5–157.5°: Waxing Gibbous."""
        result = Formatters.lunar_phase(73.2, 135.0)
        assert "Waxing Gibbous" in result and "🌔" in result

    def test_full_moon_sector(self):
        """Sector 157.5–202.5°: Full Moon."""
        result = Formatters.lunar_phase(100.0, 180.0)
        assert "Full Moon" in result and "🌕" in result

    def test_waning_gibbous_sector(self):
        """Sector 202.5–247.5°: Waning Gibbous."""
        result = Formatters.lunar_phase(73.2, 225.0)
        assert "Waning Gibbous" in result and "🌖" in result

    def test_last_quarter_sector(self):
        """Sector 247.5–292.5°: Last Quarter."""
        result = Formatters.lunar_phase(50.0, 270.0)
        assert "Last Quarter" in result and "🌗" in result

    def test_waning_crescent_sector(self):
        """Sector 292.5–337.5°: Waning Crescent."""
        result = Formatters.lunar_phase(25.0, 315.0)
        assert "Waning Crescent" in result and "🌘" in result

    def test_new_moon_else_branch(self):
        """Sector 337.5–360° (else branch): also New Moon."""
        result = Formatters.lunar_phase(2.0, 350.0)
        assert "New Moon" in result and "🌑" in result

    # ── Sector boundaries ───────────────────────────────────────────

    def test_boundary_22_5_is_waxing_crescent(self):
        """Exactly 22.5° falls in the Waxing Crescent sector (< 67.5)."""
        result = Formatters.lunar_phase(10.0, 22.5)
        assert "Waxing Crescent" in result

    def test_boundary_22_4_is_new_moon(self):
        """Just below 22.5° is still New Moon."""
        result = Formatters.lunar_phase(1.0, 22.4)
        assert "New Moon" in result

    def test_boundary_337_5_is_new_moon(self):
        """Exactly 337.5° hits the else branch → New Moon."""
        result = Formatters.lunar_phase(2.0, 337.5)
        assert "New Moon" in result

    # ── Angle normalisation ─────────────────────────────────────────

    def test_negative_angle_normalised(self):
        """-45° normalises to 315° → Waning Crescent."""
        result = Formatters.lunar_phase(25.0, -45.0)
        assert "Waning Crescent" in result

    def test_angle_over_360_normalised(self):
        """405° normalises to 45° → Waxing Crescent."""
        result = Formatters.lunar_phase(25.0, 405.0)
        assert "Waxing Crescent" in result

    def test_angle_720_normalised(self):
        """720° normalises to 0° → New Moon."""
        result = Formatters.lunar_phase(0.5, 720.0)
        assert "New Moon" in result

    # ── Illumination formatting ─────────────────────────────────────

    def test_illumination_one_decimal(self):
        """Illumination is formatted with exactly 1 decimal place."""
        result = Formatters.lunar_phase(73.2, 135.0)
        assert result.startswith("73.2%")

    def test_illumination_full(self):
        """100% illumination formats correctly."""
        result = Formatters.lunar_phase(100.0, 180.0)
        assert result.startswith("100.0%")

    def test_illumination_zero(self):
        """0% illumination formats correctly."""
        result = Formatters.lunar_phase(0.0, 0.0)
        assert result.startswith("0.0%")

    def test_full_string_waxing_gibbous(self):
        """Complete output string for Waxing Gibbous."""
        assert Formatters.lunar_phase(73.2, 135.0) == "73.2% 🌔 Waxing Gibbous"

    def test_full_string_full_moon(self):
        """Complete output string for Full Moon."""
        assert Formatters.lunar_phase(100.0, 180.0) == "100.0% 🌕 Full Moon"


# ──────────────────────────────────────────────────────────────────────
# Angle formats chosen by the user
# ──────────────────────────────────────────────────────────────────────

class TestAngleFormats:
    @pytest.mark.parametrize("fmt, degrees, signed_dec, hours", [
        ("dms", "123° 45′ 07″", "-14° 38′ 49″", "8h 45m 12.3s"),
        ("dm",  "123° 45.12′",  "-14° 38.82′",  "8h 45.205m"),
        ("dd",  "123.75197°",   "-14.64700°",   "8.75342h"),
    ])
    def test_formats(self, fmt, degrees, signed_dec, hours):
        assert Formatters.angle(123.75197, fmt) == degrees
        assert Formatters.angle(-14.647, fmt, signed=True) == signed_dec
        assert Formatters.angle(8.753417, fmt, hours=True) == hours

    def test_plus_sign_when_signed(self):
        assert Formatters.angle(14.647, "dd", signed=True) == "+14.64700°"

    @pytest.mark.parametrize("fmt, expected", [("dms", "60° 00′ 00″"), ("dm", "60° 00.00′")])
    def test_rounding_carries_over(self, fmt, expected):
        assert Formatters.angle(59.99999999, fmt) == expected

    def test_dms_matches_the_historical_formatters(self):
        """The default format shows what hms() and dms() showed."""
        assert Formatters.angle(14.4719, "dms", hours=True) == Formatters.hms(14.4719)
        assert Formatters.angle(-14.647, "dms", signed=True) == \
            Formatters.dms(-14.647).replace("'", "′").replace('"', "″")
