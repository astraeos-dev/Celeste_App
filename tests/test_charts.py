"""
tests/test_charts.py — Unit Tests for the Céleste charts
=========================================================
Phases of the day behind the trajectory chart, sky map geometry and
contents, orrery positions, and a smoke test of the three drawings on the
Agg backend (no display, no Qt).

Run with: pytest tests/
"""

import math
import os
import sys
from datetime import datetime

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

matplotlib = pytest.importorskip("matplotlib")
matplotlib.use("Agg")
from matplotlib.figure import Figure  # noqa: E402

import charts  # noqa: E402
from config import Config  # noqa: E402
from engine import AstroEngine  # noqa: E402

# Cherbourg, 1 November 2026, 21:30 UT (night, Moon below the horizon)
DTE = datetime(2026, 11, 1, 21, 30, 0)
LAT, LON = 49.6333, -1.6167


@pytest.fixture(scope="module")
def day():
    return charts.sample_day(DTE, LAT, LON)


def _bodies(dte=DTE):
    jd = AstroEngine.julian_day(dte)
    t = AstroEngine.julian_century_j2000(dte)
    s_l, r = AstroEngine.sun_position(t)
    s_ra, s_dec = AstroEngine.ecliptic_to_equatorial(s_l, 0, t)
    s_alt, s_az = AstroEngine.equatorial_to_horizontal(jd, LAT, LON, s_ra, s_dec)
    m_l, m_b, m_p = AstroEngine.moon_position(t)
    m_ra, m_dec = AstroEngine.ecliptic_to_equatorial(m_l, m_b, t)
    m_alt, m_az = AstroEngine.equatorial_to_horizontal(jd, LAT, LON, m_ra, m_dec)
    sun = {"name": "Sun", "ra": s_ra, "dec": s_dec, "alt": s_alt, "az": s_az, "dist": r}
    moon = {"name": "Moon", "ra": m_ra, "dec": m_dec, "alt": m_alt, "az": m_az,
            "illum": 50.0, "phase": 270.0, "dist": 380000.0}
    planets = []
    for name in ("Venus", "Mars", "Jupiter", "Saturn"):
        ra, dec, dist = AstroEngine.planet_position(t, name)
        alt, az = AstroEngine.equatorial_to_horizontal(jd, LAT, LON, ra, dec)
        planets.append({"name": name, "ra": ra, "dec": dec, "dist": dist,
                        "alt": alt, "az": az, "elong": 0.0, "east": True})
    return jd, sun, moon, planets


# ──────────────────────────────────────────────────────────────────────
# 1. Phases of the day
# ──────────────────────────────────────────────────────────────────────

class TestDayPhase:
    def test_thresholds(self):
        """Same convention as find_events: day from −0.833°, twilights of the geometric centre."""
        assert charts.day_phase(10) == "day"
        assert charts.day_phase(-0.8) == "day"
        assert charts.day_phase(-1.0) == "civil"
        assert charts.day_phase(-5.9) == "civil"
        assert charts.day_phase(-6.5) == "nautical"
        assert charts.day_phase(-13.0) == "astronomical"
        assert charts.day_phase(-19.0) == "night"


class TestTwilightSegments:
    def test_empty(self):
        assert charts.twilight_segments([], []) == []

    def test_constant_altitude_is_one_segment(self):
        """Polar day or night: a single segment over the whole day."""
        hours = [h / 4 for h in range(97)]
        assert charts.twilight_segments(hours, [30.0] * 97) == [(0.0, 24.0, "day")]
        assert charts.twilight_segments(hours, [-40.0] * 97) == [(0.0, 24.0, "night")]

    def test_segments_are_contiguous(self, day):
        hours, sun_alts, _ = day
        segs = charts.twilight_segments(hours, sun_alts)
        assert segs[0][0] == hours[0] and segs[-1][1] == hours[-1]
        for (_, end, _), (start, _, _) in zip(segs, segs[1:]):
            assert end == start
        assert all(end > start for start, end, _ in segs)
        assert all(phase in charts.DAY_PHASES for _, _, phase in segs)

    def test_winter_day_sequence(self, day):
        """Cherbourg in November: night → twilights → day → twilights → night."""
        hours, sun_alts, _ = day
        phases = [p for _, _, p in charts.twilight_segments(hours, sun_alts)]
        assert phases == ["night", "astronomical", "nautical", "civil", "day",
                          "civil", "nautical", "astronomical", "night"]

    def test_boundaries_match_daily_events(self, day):
        """Band edges fall within 2 minutes of the times of the Ephemeris tab."""
        hours, sun_alts, _ = day
        segs = charts.twilight_segments(hours, sun_alts)
        events = AstroEngine.find_events(DTE, LAT, LON, "sun")

        def hour(dt):
            return dt.hour + dt.minute / 60 + dt.second / 3600

        starts = {p: s for s, _, p in segs[:5]}          # morning
        ends = {p: e for _, e, p in segs[4:]}            # evening
        assert abs(starts["day"] - hour(events["rise"])) < 2 / 60
        assert abs(ends["day"] - hour(events["set"])) < 2 / 60
        assert abs(starts["civil"] - hour(events["dawn_civ"])) < 2 / 60
        assert abs(ends["civil"] - hour(events["dusk_civ"])) < 2 / 60

    def test_phase_colors_follow_theme(self):
        """Night is the card surface; the more sunlight, the more lune over it."""
        for theme in ("jour", "nuit"):
            Config.apply_theme(theme)
            assert charts.phase_color("night") == Config.CIEL_100
            assert len({charts.phase_color(p) for p in charts.DAY_PHASES}) == 5
        assert charts.phase_color("day") != charts.phase_color("civil")


# ──────────────────────────────────────────────────────────────────────
# 2. Sky map
# ──────────────────────────────────────────────────────────────────────

class TestSkyGeometry:
    def test_zenith_at_centre(self):
        x, y = charts.sky_xy(90, 123)
        assert abs(x) < 1e-12 and abs(y) < 1e-12

    def test_cardinal_points_on_horizon(self):
        """North up, east on the right, horizon on the unit circle."""
        assert all(abs(a - b) < 1e-12 for a, b in zip(charts.sky_xy(0, 0), (0, 1)))
        assert all(abs(a - b) < 1e-12 for a, b in zip(charts.sky_xy(0, 90), (1, 0)))
        assert all(abs(a - b) < 1e-12 for a, b in zip(charts.sky_xy(0, 180), (0, -1)))

    def test_below_horizon_outside_circle(self):
        assert math.hypot(*charts.sky_xy(-10, 45)) > 1

    def test_star_size_decreases_with_magnitude(self):
        sizes = [charts.star_marker_size(m) for m in (-1.5, 0, 1, 2, 3, 6)]
        assert sizes == sorted(sizes, reverse=True)
        assert charts.star_marker_size(10) == charts.star_marker_size(20) > 0


class TestSkyScene:
    def test_stars_above_horizon_and_bright_enough(self):
        jd, sun, moon, planets = _bodies()
        scene = charts.sky_scene(jd, LAT, LON, 2.0, sun, moon, planets)
        assert scene["stars"]
        assert all(s["alt"] > 0 and s["mag"] <= 2.0 for s in scene["stars"])
        assert all(math.hypot(s["x"], s["y"]) < 1 for s in scene["stars"])

    def test_magnitude_limit_filters_stars(self):
        jd, sun, moon, planets = _bodies()
        bright = charts.sky_scene(jd, LAT, LON, 1.0, sun, moon, planets)
        faint = charts.sky_scene(jd, LAT, LON, 6.0, sun, moon, planets)
        assert len(bright["stars"]) < len(faint["stars"])

    def test_constellation_lines_and_bodies(self):
        jd, sun, moon, planets = _bodies()
        scene = charts.sky_scene(jd, LAT, LON, 6.0, sun, moon, planets)
        assert scene["lines"]
        assert scene["sun"]["kind"] == "sun" and scene["moon"]["kind"] == "moon"
        assert len(scene["planets"]) == 4

    def test_visible_objects_exclude_bodies_below_horizon(self):
        jd, sun, moon, planets = _bodies()
        scene = charts.sky_scene(jd, LAT, LON, 6.0, sun, moon, planets)
        objs = charts.visible_objects(scene)
        assert all(o["alt"] > 0 for o in objs)
        assert scene["sun"] not in objs          # the Sun is down at 21:30 UT

    def test_hit_test(self):
        objs = [{"x": 0.0, "y": 0.0, "name": "a"}, {"x": 0.5, "y": 0.5, "name": "b"}]
        assert charts.hit_test(objs, 0.01, 0.01)["name"] == "a"
        assert charts.hit_test(objs, 0.48, 0.49)["name"] == "b"
        assert charts.hit_test(objs, 0.25, 0.25) is None


# ──────────────────────────────────────────────────────────────────────
# 3. Orrery
# ──────────────────────────────────────────────────────────────────────

def _distance_to_polyline(point, polyline):
    """Distance from a point to the nearest segment of a polyline (plane)."""
    px, py = point
    best = float("inf")
    for (ax, ay), (bx, by) in zip(polyline, polyline[1:]):
        dx, dy = bx - ax, by - ay
        k = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / ((dx * dx + dy * dy) or 1.0)))
        best = min(best, math.hypot(px - ax - k * dx, py - ay - k * dy))
    return best


class TestOrreryScene:
    def test_orbits_close_and_contain_the_planet(self):
        scene = charts.orrery_scene(AstroEngine.julian_century_j2000(DTE), samples=90)
        for name, body in scene["planets"].items():
            orbit = body["orbit"]
            assert len(orbit) == 91
            first, last = orbit[0], orbit[-1]
            # DE440 orbits are perturbed (Jupiter–Saturn): closed to 1 % of the radius
            gap = math.hypot(first[0] - last[0], first[1] - last[1])
            assert gap < 0.01 * math.hypot(*first), name
            # the planet is on its orbit (from now, or shifted within the ephemeris
            # for Uranus and Neptune): within 1 % of the radius of a sampled segment
            radius = math.hypot(body["x"], body["y"])
            assert _distance_to_polyline((body["x"], body["y"]), orbit) < 0.01 * radius, name

    def test_seven_planets_and_long_orbits_within_the_ephemeris(self):
        """Neptune (165 years) is traced within 1850–2149 instead of up to 2191."""
        scene = charts.orrery_scene(AstroEngine.julian_century_j2000(DTE), samples=90)
        assert list(scene["planets"]) == list(PLANET_LABELS)

    def test_earth_one_au_from_the_sun(self):
        scene = charts.orrery_scene(AstroEngine.julian_century_j2000(DTE), samples=12)
        earth = scene["earth"]
        assert 0.98 < math.hypot(earth["x"], earth["y"]) < 1.02


# ──────────────────────────────────────────────────────────────────────
# 4. Drawings (smoke tests on Agg)
# ──────────────────────────────────────────────────────────────────────

LABELS_TRAJ = {"title": "T", "xlabel": "Local", "ylabel": "Alt", "top_axis": "UT",
               "sun": "Sun", "moon": "Moon", "day": "Day", "civil": "Civil",
               "nautical": "Nautical", "astronomical": "Astro", "night": "Night"}
PLANET_LABELS = {p: p for p in ("Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune")}


@pytest.mark.parametrize("theme", ["nuit", "jour", "observation"])
def test_draw_all_charts(theme, day):
    Config.apply_theme(theme)
    try:
        hours, sun_alts, moon_alts = day
        fig = Figure(figsize=(8, 5))
        ax, tip = charts.draw_trajectory(fig, hours, sun_alts, moon_alts, 21.5,
                                         -45.0, -8.0, LABELS_TRAJ, utc_offset=1)
        assert len(ax.lines) >= 2 and not tip.get_visible()
        fig.canvas.draw()

        jd, sun, moon, planets = _bodies()
        scene = charts.sky_scene(jd, LAT, LON, 6.0, sun, moon, planets)
        fig = Figure(figsize=(6, 6))
        ax, tip = charts.draw_sky_map(fig, scene, {
            "title": "Sky", "sun": "Sun", "moon": "Moon", "horizon": "Horizon",
            "cardinals": ["N", "NE", "E", "SE", "S", "SW", "W", "NW"],
            "planets": PLANET_LABELS})
        assert not tip.get_visible()
        fig.canvas.draw()

        fig = Figure(figsize=(8, 4))
        charts.draw_orrery(fig, charts.orrery_scene(0.27, samples=30), {
            "inner": "Inner", "outer": "Outer", "au": "AU", "sun": "Sun",
            "earth": "Earth", "vernal": "vernal point", "planets": PLANET_LABELS})
        assert len(fig.axes) == 2
        fig.canvas.draw()
    finally:
        Config.apply_theme("nuit")


def test_configure_fonts_uses_the_astraeos_fonts():
    """IBM Plex Sans for the text, Astraeos Symboles for ☉ ☽ ♀ ♂ ♃ ♄."""
    from matplotlib import font_manager
    assert charts.configure_fonts() == "IBM Plex Sans"
    assert matplotlib.rcParams["font.family"][:2] == ["IBM Plex Sans", "Astraeos Symboles"]
    path = font_manager.findfont(font_manager.FontProperties(family="Astraeos Symboles"),
                                 fallback_to_default=False)
    assert path.endswith("AstraeosSymboles-Regular.ttf")


def test_symbols_are_in_the_symbol_font():
    """Every symbol drawn on the charts exists in Astraeos Symboles."""
    from fontTools.ttLib import TTFont
    font = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "fonts", "AstraeosSymboles-Regular.ttf")
    cmap = TTFont(font).getBestCmap()
    assert all(ord(s) in cmap for s in charts.SYMBOL.values())


# ──────────────────────────────────────────────────────────────────────
# Trajectory over the local day
# ──────────────────────────────────────────────────────────────────────

class TestLocalDay:
    def test_starts_at_local_midnight(self):
        """Kolkata (UTC+5:30): 24 h from local midnight, the Sun highest near local noon."""
        from zoneinfo import ZoneInfo
        hours, sun, _ = charts.sample_day(datetime(2026, 11, 2, 6), 22.5726, 88.3639,
                                          tz=ZoneInfo("Asia/Kolkata"))
        assert hours[0] == 0 and hours[-1] == 24
        noon = hours[sun.index(max(sun))]
        assert abs(noon - (11 + 20 / 60)) < 0.1          # transit 11:20 local (USNO)

    def test_day_of_the_change_of_time_lasts_25_hours(self):
        from zoneinfo import ZoneInfo
        hours, _, _ = charts.sample_day(datetime(2026, 10, 25, 12), 48.8566, 2.3522,
                                        tz=ZoneInfo("Europe/Paris"))
        assert hours[-1] == 25

    def test_ut_by_default(self):
        """Without a time zone, the day is the UT day, as before."""
        hours, _, _ = charts.sample_day(DTE, LAT, LON)
        assert hours[0] == 0 and hours[-1] == 24


def test_draw_event_map():
    """Map of a conjunction with the Sun and of an opposition (the Sun left out)."""
    from star_catalog import CATALOG
    events = AstroEngine.find_conjunctions(datetime(2026, 1, 1), num_days=15)
    for event in [e for e in events if e["type"] in ("conjunction", "opposition")][:3]:
        scene = AstroEngine.event_scene(event, CATALOG)
        fig = Figure(figsize=(7, 6))
        ax = charts.draw_event_map(fig, scene, {"title": "Event", "ecliptic": "Ecliptic",
                                                "bodies": {"Sun": "Sun"}}, event["date"])
        paths = len(scene["bodies"]) - (event["type"] == "opposition")
        assert len([line for line in ax.lines if len(line.get_xdata()) == len(scene["days"])]) == paths
        lo, hi = ax.get_xlim()
        assert lo < hi                                   # x grows westward: east on the left
        fig.canvas.draw()
