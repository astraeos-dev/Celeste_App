"""
charts.py — Matplotlib drawings of Céleste
==========================================
The three charts of the interface:

- the altitude of the Sun and the Moon over the local day, on a background
  shaded by the phases of the day (day, civil, nautical and astronomical
  twilights, night);
- the sky map: the dome seen from below with the zenith at the centre, the
  horizon on the circle, north up and east on the right;
- the solar system seen from the north ecliptic pole, inner and outer views.

The ``*_scene`` functions compute what to draw with the engine; the
``draw_*`` functions only draw, with the active Astræos theme (``Config``)
and the translated labels they receive. Nothing here depends on Qt, so the
tests run these functions on the Agg backend.

Astræos rules applied here: hairlines rather than shadows, ``encre`` for
values and ``encre-attenuee`` for labels, the Sun in ``or`` and the Moon in
``lune`` where the color helps reading, and the astronomical symbols (☉ ☽ ♀ ♂
♃ ♄ ⊕ ♈) always next to the body's name.
"""

import logging
import json
import math

import numpy as np
import os
from datetime import timedelta

import matplotlib
from matplotlib import font_manager
from matplotlib.colors import to_rgba
from matplotlib.patches import Circle, Patch
from matplotlib.ticker import FuncFormatter, MultipleLocator

from config import Config, FONT_SANS, mix
from constellations import CONSTELLATIONS
from star_catalog import CATALOG
from engine import EPHEMERIS_YEARS, AstroEngine, _HORIZON_CORRECTION_SUN

# Astronomical symbols (Astraeos Symboles). Matplotlib never draws emoji, so
# they go without the U+FE0E selector here.
SYMBOL = {"Sun": "☉", "Moon": "☽", "Earth": "⊕", "Mercury": "☿", "Venus": "♀",
          "Mars": "♂", "Jupiter": "♃", "Saturn": "♄", "Uranus": "♅", "Neptune": "♆",
          "Pluto": "♇", "vernal": "♈"}

# Text sizes of the design system (px) converted to points at the figures'
# 100 dpi: legende 13 px, corps 15 px, sous-titre 17 px.
_PT = 0.72
SIZE_LEGENDE = 13 * _PT
SIZE_CORPS = 15 * _PT
SIZE_SOUS_TITRE = 17 * _PT

_FONTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")

# ──────────────────────────────────────────────────────────────────────────────
# FONTS
# ──────────────────────────────────────────────────────────────────────────────


def configure_fonts(fonts_dir=_FONTS_DIR):
    """
    Register the Astræos fonts shipped in fonts/ with matplotlib and use
    IBM Plex Sans, then Astraeos Symboles for the symbols (DejaVu Sans,
    shipped with matplotlib, only when the files are missing).

    Returns:
        str: The first family of the stack.
    """
    if os.path.isdir(fonts_dir):
        for name in sorted(os.listdir(fonts_dir)):
            if name.endswith(".ttf"):
                font_manager.fontManager.addfont(os.path.join(fonts_dir, name))
    # Astraeos Symboles has a single weight: a semibold title falls back to
    # its regular symbols, which matplotlib would report each time.
    logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)
    installed = {f.name for f in font_manager.fontManager.ttflist}
    families = [f for f in FONT_SANS if f in installed]
    if FONT_SANS[0] not in families:      # files missing: matplotlib's own font
        families.append("DejaVu Sans")
    matplotlib.rcParams["font.family"] = families
    matplotlib.rcParams["axes.unicode_minus"] = True
    return families[0]


# ──────────────────────────────────────────────────────────────────────────────
# PHASES OF THE DAY
# ──────────────────────────────────────────────────────────────────────────────

# Same convention as AstroEngine.find_events, so the bands line up with the
# times listed in the Ephemeris tab: day from sunrise (geometric centre at
# −0.833°: refraction and semi-diameter), then the twilights of the geometric
# centre at −6, −12 and −18°.
DAY_PHASES = ("day", "civil", "nautical", "astronomical", "night")
_PHASE_LIMITS = (("day", -_HORIZON_CORRECTION_SUN), ("civil", -6.0),
                 ("nautical", -12.0), ("astronomical", -18.0))

# Share of lune laid over ciel-100: the more sunlight, the more lune
_PHASE_TINT = {"day": 0.26, "civil": 0.17, "nautical": 0.10,
               "astronomical": 0.05, "night": 0.0}


def _phase_of_corrected(h):
    for name, limit in _PHASE_LIMITS:
        if h >= limit:
            return name
    return "night"


def day_phase(sun_alt):
    """
    Phase of the day for a geometric Sun altitude.

    Args:
        sun_alt (float): Altitude of the Sun's centre, degrees.

    Returns:
        str: "day", "civil", "nautical", "astronomical" or "night".
    """
    return _phase_of_corrected(sun_alt)


def twilight_segments(hours, sun_alts):
    """
    Splits the sampled day into contiguous phases of the day.

    The boundaries are interpolated linearly between two samples.

    Args:
        hours (list[float]): Sample times, increasing (hours).
        sun_alts (list[float]): Geometric Sun altitude at each sample (degrees).

    Returns:
        list[tuple[float, float, str]]: (start, end, phase) covering
        hours[0] → hours[-1], with no gap and no zero-length segment.
    """
    if not hours:
        return []
    segments = []
    start = hours[0]
    current = _phase_of_corrected(sun_alts[0])
    for i in range(1, len(hours)):
        h0, h1 = hours[i - 1], hours[i]
        a0, a1 = sun_alts[i - 1], sun_alts[i]
        crossings = []
        for _, limit in _PHASE_LIMITS:
            if a0 < limit <= a1:            # rising through the limit
                crossings.append(((limit - a0) / (a1 - a0), _phase_of_corrected(limit)))
            elif a1 < limit <= a0:          # setting through the limit
                crossings.append(((a0 - limit) / (a0 - a1),
                                  _phase_of_corrected(limit - 1e-9)))
        for frac, new_phase in sorted(crossings):
            when = h0 + frac * (h1 - h0)
            if new_phase == current:
                continue
            if when > start:
                segments.append((start, when, current))
                start = when
            current = new_phase
    if hours[-1] > start or not segments:
        segments.append((start, hours[-1], current))
    return segments


def phase_color(phase):
    """Background of a phase of the day in the active theme: lune over ciel-100."""
    return mix(Config.LUNE, Config.CIEL_100, _PHASE_TINT[phase])


# ──────────────────────────────────────────────────────────────────────────────
# COMMON STYLE
# ──────────────────────────────────────────────────────────────────────────────

def _style_axes(ax):
    ax.set_facecolor(Config.CIEL_100)
    ax.tick_params(colors=Config.ENCRE_ATTENUEE, labelsize=SIZE_LEGENDE,
                   length=3, width=0.8)
    for spine in ax.spines.values():
        spine.set_color(Config.CIEL_200)
    ax.grid(color=Config.CIEL_200, linewidth=0.8)


def _tooltip(ax):
    """Hidden annotation used as a hover tooltip."""
    tip = ax.annotate(
        "", xy=(0, 0), xytext=(12, 12), textcoords="offset points",
        fontsize=SIZE_LEGENDE, color=Config.ENCRE, zorder=20, multialignment="left",
        bbox=dict(boxstyle="round,pad=0.5,rounding_size=0.3", fc=Config.CIEL_100,
                  ec=Config.CIEL_200, lw=1),
        annotation_clip=False)
    tip.set_visible(False)
    return tip


def _hour_label(x, _pos=None):
    return f"{int(round(x)) % 24:02d}h"


def _title(fig, ax, text):
    ax.set_title(text, color=Config.ENCRE, fontsize=SIZE_SOUS_TITRE,
                 fontweight=600, loc="left", pad=12)


# ──────────────────────────────────────────────────────────────────────────────
# 24 H TRAJECTORIES
# ──────────────────────────────────────────────────────────────────────────────

def sample_day(dte, lat, lon, step_min=5, elevation_m=0.0, tz=0):
    """
    Altitude of the Sun (geometric centre) and the Moon (seen from the
    observer, refraction included) over the local day of *dte*, the one of
    the events listed (AstroEngine.find_events), computed at once from the
    DE440 ephemeris.

    Args:
        dte (datetime): instant of the day, UT.
        tz (float | tzinfo): local time zone, hours east of UT or a zoneinfo.

    Returns:
        tuple[list, list, list]: (hours since local midnight, sun_altitudes,
        moon_altitudes); a day of change of summer time lasts 23 or 25 hours.
    """
    start, end = AstroEngine._local_day(dte, tz)
    span = int((end - start).total_seconds() // 60)
    minutes = range(0, span + 1, step_min)
    sun_alts, moon_alts = AstroEngine.altitudes(
        [start + timedelta(minutes=minute) for minute in minutes], lat, lon, elevation_m)
    return [minute / 60.0 for minute in minutes], sun_alts.tolist(), moon_alts.tolist()


def draw_trajectory(fig, hours, sun_alts, moon_alts, now_hour, sun_now, moon_now,
                    labels, utc_offset=0):
    """
    Draws the altitude of the Sun and the Moon over the day.

    Args:
        fig: matplotlib Figure (cleared first).
        hours, sun_alts, moon_alts: samples from ``sample_day``.
        now_hour (float): Current time, hours since local midnight.
        sun_now, moon_now (float): Current altitudes (degrees).
        labels (dict): title, xlabel (local time), ylabel, top_axis (UT),
            sun, moon and one entry per phase of DAY_PHASES.
        utc_offset (float): Offset of the time zone at local midnight, hours:
            the UT axis on top reads local time minus it (no top axis when 0).

    Returns:
        tuple: (axes, tooltip annotation)
    """
    fig.clear()
    fig.set_layout_engine("constrained")
    fig.get_layout_engine().set(w_pad=0.16, h_pad=0.12)
    fig.patch.set_facecolor(Config.CIEL_100)
    ax = fig.add_subplot(111)
    _style_axes(ax)

    for start, end, phase in twilight_segments(hours, sun_alts):
        ax.axvspan(start, end, color=phase_color(phase), lw=0, zorder=0)

    ax.axhline(0, color=Config.ENCRE_ATTENUEE, linewidth=1.0, zorder=2)
    sun_line, = ax.plot(hours, sun_alts, color=Config.OR, linewidth=2.0,
                        label=f"{SYMBOL['Sun']}  {labels['sun']}", zorder=3)
    moon_line, = ax.plot(hours, moon_alts, color=Config.LUNE, linewidth=2.0,
                         label=f"{SYMBOL['Moon']}  {labels['moon']}", zorder=3)
    ax.axvline(now_hour, color=Config.ENCRE, linewidth=1.0, alpha=0.7,
               linestyle=(0, (4, 3)), zorder=4)
    for alt, color in ((sun_now, Config.OR), (moon_now, Config.LUNE)):
        ax.plot(now_hour, alt, "o", color=color, markersize=7,
                markeredgecolor=Config.CIEL_100, markeredgewidth=1.5, zorder=5)

    ax.set_xlim(0, hours[-1] if hours else 24)          # 23 or 25 h on a change of time
    ax.xaxis.set_major_locator(MultipleLocator(3))
    ax.xaxis.set_major_formatter(FuncFormatter(_hour_label))
    values = list(sun_alts) + list(moon_alts) + [sun_now, moon_now]
    low = min(-10.0, 10 * math.floor((min(values) - 5) / 10))
    high = max(10.0, 10 * math.ceil((max(values) + 5) / 10))
    ax.set_ylim(low, high)
    _title(fig, ax, labels["title"])
    ax.set_xlabel(labels["xlabel"], color=Config.ENCRE_ATTENUEE, fontsize=SIZE_LEGENDE)
    ax.set_ylabel(labels["ylabel"], color=Config.ENCRE_ATTENUEE, fontsize=SIZE_LEGENDE)

    if utc_offset:
        top = ax.secondary_xaxis(
            "top", functions=(lambda x: x - utc_offset, lambda x: x + utc_offset))
        top.xaxis.set_major_locator(MultipleLocator(3))
        top.xaxis.set_major_formatter(FuncFormatter(_hour_label))
        top.tick_params(colors=Config.ENCRE_ATTENUEE, labelsize=SIZE_LEGENDE,
                        length=3, width=0.8)
        top.spines["top"].set_color(Config.CIEL_200)
        top.set_xlabel(labels["top_axis"], color=Config.ENCRE_ATTENUEE,
                       fontsize=SIZE_LEGENDE)

    handles = [sun_line, moon_line] + [
        Patch(facecolor=phase_color(p), edgecolor=Config.CIEL_200, label=labels[p])
        for p in DAY_PHASES]
    fig.legend(handles=handles, loc="outside lower center", ncol=len(handles),
               frameon=False, fontsize=SIZE_LEGENDE, labelcolor=Config.ENCRE_ATTENUEE,
               handlelength=1.6, columnspacing=1.6)
    return ax, _tooltip(ax)


# ──────────────────────────────────────────────────────────────────────────────
# SKY MAP
# ──────────────────────────────────────────────────────────────────────────────

def sky_xy(alt, az):
    """
    Position on the sky map: zenith at (0, 0), horizon on the unit circle,
    north up and east on the right. Below the horizon, the radius exceeds 1.
    """
    r = (90.0 - alt) / 90.0
    a = math.radians(az)
    return r * math.sin(a), r * math.cos(a)


def star_marker_size(mag):
    """Marker area (points²) of a star of magnitude *mag*: brighter is bigger."""
    diameter = max(1.6, 6.5 - 1.2 * mag)
    return diameter * diameter


def sky_scene(jd, lat, lon, mag_limit, sun, moon, planets):
    """
    Collects what the sky map shows.

    Args:
        jd (float): Julian day (UT).
        lat, lon (float): Observer, degrees.
        mag_limit (float): Faintest star magnitude shown.
        sun, moon (dict): name, alt, az, ra, dec (the Moon also illum, phase).
        planets (list[dict]): name, alt, az, ra, dec, dist for each planet.

    Returns:
        dict: stars (above the horizon and bright enough), constellation
        lines (at least one end above the horizon), sun, moon, planets;
        every object carries its map position "x", "y".
    """
    # the 513 stars of the catalogue brought to the date at once (proper motion,
    # precession, nutation, aberration); the stars of the figures by their name
    alts, azs = AstroEngine.stars_horizontal(
        (jd - 2451545.0) / 36525.0, lat, lon, [c[1] for c in CATALOG], [c[2] for c in CATALOG],
        pm_ra_mas=[c[4] for c in CATALOG], pm_dec_mas=[c[5] for c in CATALOG])
    stars, horizontal = [], {}
    for (designation, ra, dec, mag, _pm_ra, _pm_dec, name), alt, az in zip(CATALOG, alts, azs):
        alt, az = float(alt), float(az)
        if name:
            horizontal[name] = (alt, az)
        if mag > mag_limit or alt <= 0:
            continue
        x, y = sky_xy(alt, az)
        stars.append({"kind": "star", "name": name or designation, "designation": designation,
                      "alt": alt, "az": az, "ra": ra, "dec": dec, "mag": mag, "x": x, "y": y})

    lines = []
    for edges in CONSTELLATIONS.values():
        for a, b in edges:
            if a not in horizontal or b not in horizontal:
                continue
            (alt1, az1), (alt2, az2) = horizontal[a], horizontal[b]
            if max(alt1, alt2) <= 0:
                continue
            lines.append((sky_xy(alt1, az1), sky_xy(alt2, az2)))

    def placed(body, kind):
        x, y = sky_xy(body["alt"], body["az"])
        return {**body, "kind": kind, "x": x, "y": y}

    return {
        "stars": stars,
        "lines": lines,
        "sun": placed(sun, "sun"),
        "moon": placed(moon, "moon"),
        "planets": [placed(p, "planet") for p in planets],
    }


def visible_objects(scene):
    """Objects of *scene* above the horizon, as the map draws them."""
    objs = list(scene["stars"])
    objs += [p for p in scene["planets"] if p["alt"] > 0]
    for body in (scene["sun"], scene["moon"]):
        if body["alt"] > 0:
            objs.append(body)
    return objs


def hit_test(objects, x, y, radius=0.06):
    """Object of *objects* nearest to (x, y) within *radius*, or None."""
    best, best_d = None, radius
    for obj in objects:
        d = math.hypot(obj["x"] - x, obj["y"] - y)
        if d < best_d:
            best, best_d = obj, d
    return best


def _body_label(ax, x, y, text, color, size=SIZE_LEGENDE, weight=400, dx=8, dy=6,
                ha="left", va="baseline"):
    ax.annotate(text, (x, y), xytext=(dx, dy), textcoords="offset points",
                fontsize=size, fontweight=weight, color=color, zorder=8, ha=ha, va=va)


def _label_box(ax, x, y, text, size, dx, dy, ha="left"):
    """Approximate box (data units) of a label set (dx, dy) points from (x, y), bottom-aligned."""
    bbox = ax.get_window_extent()
    (x0, x1), (y0, y1) = ax.get_xlim(), ax.get_ylim()
    ux, uy = bbox.width / (x1 - x0), bbox.height / (y1 - y0)          # pixels per data unit
    px = ax.figure.dpi / 72.0                                          # pixels per point
    width, height = 0.6 * size * px * len(text) / ux, 1.25 * size * px / uy
    left = x + dx * px / ux - (width if ha == "right" else 0.0)
    bottom = y + dy * px / uy
    return left, bottom, left + width, bottom + height


def _overlaps(a, b):
    return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])


# Places tried for a planet's label: above right, below right, above left, below left
_LABEL_PLACES = ((6, 3, "left"), (6, -14, "left"), (-6, 3, "right"), (-6, -14, "right"))


def draw_sky_map(fig, scene, labels):
    """
    Draws the sky map.

    Args:
        fig: matplotlib Figure (cleared first).
        scene (dict): from ``sky_scene``.
        labels (dict): title, sun, moon, horizon, cardinals (8 labels from N
            clockwise) and planets ({"Venus": "Vénus", ...}).

    Returns:
        tuple: (axes, tooltip annotation)
    """
    fig.clear()
    fig.set_layout_engine("none")
    fig.patch.set_facecolor(Config.CIEL_100)
    ax = fig.add_axes((0.02, 0.02, 0.96, 0.89))
    ax.set_aspect("equal")
    ax.set_xlim(-1.17, 1.17)
    ax.set_ylim(-1.17, 1.17)
    ax.axis("off")

    dome = Circle((0, 0), 1.0, facecolor=Config.CIEL_000,
                  edgecolor=Config.ENCRE_ATTENUEE, linewidth=1.2, zorder=0)
    ax.add_patch(dome)
    for az in range(0, 360, 45):
        x, y = sky_xy(0, az)
        ax.plot([0, x], [0, y], color=Config.CIEL_200, linewidth=0.8, zorder=1)
    for alt in (30, 60):
        ax.add_patch(Circle((0, 0), (90 - alt) / 90, fill=False,
                            edgecolor=Config.CIEL_200, linewidth=1.0, zorder=1))
        lx, ly = sky_xy(alt, 202)
        ax.text(lx, ly, f"{alt}°", color=Config.ENCRE_ATTENUEE, fontsize=SIZE_LEGENDE * 0.85,
                ha="center", va="center", zorder=1)
    hx, hy = sky_xy(0, 202)
    ax.text(hx * 0.93, hy * 0.93, labels["horizon"], color=Config.ENCRE_ATTENUEE,
            fontsize=SIZE_LEGENDE * 0.85, ha="center", va="center", rotation=-22, zorder=1)
    ax.plot(0, 0, "+", color=Config.ENCRE_ATTENUEE, markersize=9, markeredgewidth=1.0,
            zorder=2)
    for i, card in enumerate(labels["cardinals"]):
        cx, cy = sky_xy(-8.5, i * 45)
        main = i % 2 == 0
        ax.text(cx, cy, card, ha="center", va="center",
                color=Config.ENCRE if i == 0 else Config.ENCRE_ATTENUEE,
                fontsize=SIZE_CORPS if main else SIZE_LEGENDE,
                fontweight=600 if main else 400)

    for (x1, y1), (x2, y2) in scene["lines"]:
        line, = ax.plot([x1, x2], [y1, y2], color=Config.ENCRE_ATTENUEE, linewidth=0.8,
                        alpha=0.4, zorder=2)
        line.set_clip_path(dome)

    stars = scene["stars"]
    if stars:
        bright = [s for s in stars if s["mag"] < 1.0]
        if bright:
            ax.scatter([s["x"] for s in bright], [s["y"] for s in bright],
                       s=[star_marker_size(s["mag"]) * 4.5 for s in bright],
                       color=to_rgba(Config.ENCRE, 0.10), linewidths=0, zorder=3)
        ax.scatter([s["x"] for s in stars], [s["y"] for s in stars],
                   s=[star_marker_size(s["mag"]) for s in stars],
                   color=[to_rgba(Config.ENCRE, min(1.0, max(0.45, 1.0 - s["mag"] / 7.0)))
                          for s in stars],
                   linewidths=0, zorder=4)
    # Planets first, each label at the first of four places free of the other
    # labels and bodies; then the brightest stars, skipping a label that would
    # sit on another one (Orion's belt, Castor and Pollux)
    up = [p for p in scene["planets"] if p["alt"] > 0]
    taken = [(b["x"] - 0.01, b["y"] - 0.01, b["x"] + 0.01, b["y"] + 0.01)
             for b in up + [scene["sun"], scene["moon"]] if b["alt"] > 0]
    for p in up:
        ax.plot(p["x"], p["y"], "o", color=Config.ENCRE, markersize=4.5,
                markeredgewidth=0, zorder=6)
        text = f"{SYMBOL[p['name']]} {labels['planets'].get(p['name'], p['name'])}"
        own = (p["x"] - 0.01, p["y"] - 0.01, p["x"] + 0.01, p["y"] + 0.01)
        for dx, dy, ha in _LABEL_PLACES:
            box = _label_box(ax, p["x"], p["y"], text, SIZE_LEGENDE, dx, dy, ha)
            if not any(_overlaps(box, other) for other in taken if other != own):
                break
        else:
            dx, dy, ha = _LABEL_PLACES[0]
            box = _label_box(ax, p["x"], p["y"], text, SIZE_LEGENDE, dx, dy, ha)
        taken.append(box)
        _body_label(ax, p["x"], p["y"], text, Config.ENCRE, dx=dx, dy=dy, ha=ha, va="bottom")

    if stars:
        labelled = []
        for s in sorted(stars, key=lambda s: s["mag"]):
            if s["mag"] >= 2.0:
                break
            if any(math.hypot(s["x"] - x, s["y"] - y) < 0.07 for x, y in labelled):
                continue
            box = _label_box(ax, s["x"], s["y"], s["name"], SIZE_LEGENDE * 0.75, 4, 3)
            if any(_overlaps(box, other) for other in taken):
                continue
            labelled.append((s["x"], s["y"]))
            taken.append(box)
            ax.annotate(s["name"], (s["x"], s["y"]), xytext=(4, 3),
                        textcoords="offset points", fontsize=SIZE_LEGENDE * 0.75,
                        color=Config.ENCRE_ATTENUEE, zorder=5, va="bottom")

    moon = scene["moon"]
    if moon["alt"] > 0:
        ax.plot(moon["x"], moon["y"], "o", color=Config.LUNE, markersize=10,
                markeredgewidth=0, zorder=7)
        _body_label(ax, moon["x"], moon["y"], f"{SYMBOL['Moon']} {labels['moon']}",
                    Config.LUNE, size=SIZE_CORPS, weight=600)

    sun = scene["sun"]
    if sun["alt"] > 0:
        ax.plot(sun["x"], sun["y"], "o", color=Config.OR, markersize=12,
                markeredgewidth=0, zorder=7)
        _body_label(ax, sun["x"], sun["y"], f"{SYMBOL['Sun']} {labels['sun']}",
                    Config.OR, size=SIZE_CORPS, weight=600)

    fig.text(0.03, 0.97, labels["title"], ha="left", va="top", fontsize=SIZE_SOUS_TITRE,
             fontweight=600, color=Config.ENCRE)
    return ax, _tooltip(ax)


# ──────────────────────────────────────────────────────────────────────────────
# SOLAR SYSTEM (ORRERY)
# ──────────────────────────────────────────────────────────────────────────────

# Sidereal periods (years), to trace one full orbit
_PERIOD_YEARS = {"Mercury": 0.24085, "Venus": 0.61520, "Mars": 1.88085,
                 "Jupiter": 11.8622, "Saturn": 29.4571, "Uranus": 84.0205, "Neptune": 164.79}
_PLANET_MARKER = {"Mercury": 5, "Venus": 6, "Mars": 5, "Jupiter": 9, "Saturn": 8,
                  "Uranus": 7, "Neptune": 7}


def orrery_scene(t, samples=180):
    """
    Heliocentric positions and orbits seen from the north ecliptic pole.

    Args:
        t (float): Julian centuries since J2000.0.
        samples (int): Points per orbit.

    Returns:
        dict: "earth" and "planets" ({name: ...}), each with "x", "y" (AU)
        and "orbit" (list of (x, y)).
    """
    # an orbit is traced from now, or shifted back to stay within the ephemeris
    # (Neptune takes 165 years: 2026 + 165 is past 2149)
    first, last = ((year - 2000.0) / 100.0 for year in (EPHEMERIS_YEARS[0], EPHEMERIS_YEARS[1] + 1))

    def body(name, period_years):
        x, y, _ = AstroEngine.planet_heliocentric(t, name)
        span = period_years / 100.0
        start = max(first, min(t, last - span))
        ox, oy, _ = AstroEngine.planet_heliocentric(               # one orbit, at once
            start + np.linspace(0.0, span, samples + 1), name)
        return {"x": float(x), "y": float(y), "orbit": list(zip(ox.tolist(), oy.tolist()))}

    planets = {name: body(name, period) for name, period in _PERIOD_YEARS.items()}
    return {"earth": body("Earth", 1.0), "planets": planets}


def draw_orrery(fig, scene, labels):
    """
    Draws the inner and the outer solar system side by side.

    Args:
        fig: matplotlib Figure (cleared first).
        scene (dict): from ``orrery_scene``.
        labels (dict): inner, outer (panel titles), au, sun, earth, vernal
            and planets ({"Venus": "Vénus", ...}).
    """
    fig.clear()
    fig.set_layout_engine("constrained")
    fig.get_layout_engine().set(w_pad=0.16, h_pad=0.12, wspace=0.08)
    fig.patch.set_facecolor(Config.CIEL_100)
    panels = (
        (fig.add_subplot(1, 2, 1), 1.8, ("Mercury", "Venus", "Mars"), labels["inner"]),
        (fig.add_subplot(1, 2, 2), 31.5, ("Jupiter", "Saturn", "Uranus", "Neptune"), labels["outer"]),
    )
    earth = scene["earth"]
    for ax, lim, named, title in panels:
        _style_axes(ax)
        ax.set_aspect("equal")
        ax.set_xlim(-lim, lim)
        ax.set_ylim(-lim, lim)
        _title(fig, ax, title)
        ax.set_xlabel(labels["au"], color=Config.ENCRE_ATTENUEE, fontsize=SIZE_LEGENDE)

        inner = lim < 5
        ax.plot(0, 0, "o", color=Config.OR, markersize=10 if inner else 7,
                markeredgewidth=0, zorder=5)
        if inner:
            _body_label(ax, 0, 0, f"{SYMBOL['Sun']} {labels['sun']}", Config.OR,
                        dx=8, dy=-14)
        # Direction of the vernal point (x axis of the ecliptic frame)
        ax.annotate(f"{SYMBOL['vernal']} {labels['vernal']}", xy=(lim * 0.98, 0),
                    xytext=(lim * 0.68, 0), fontsize=SIZE_LEGENDE * 0.9,
                    color=Config.ENCRE_ATTENUEE, va="center", ha="right",
                    arrowprops=dict(arrowstyle="->", color=Config.ENCRE_ATTENUEE, lw=0.8))

        bodies = [("Earth", earth, Config.LUNE, 6)]
        bodies += [(name, scene["planets"][name], Config.ENCRE, _PLANET_MARKER[name])
                   for name in _PERIOD_YEARS]
        for name, body, color, size in bodies:
            # Inner panel: Venus, Earth, Mars. Outer panel: the giants, with
            # the inner orbits faint and the Earth as a small dot.
            main = name in named or (inner and name == "Earth")
            if inner and not main:
                continue
            xs, ys = zip(*body["orbit"])
            ax.plot(xs, ys, color=color, linewidth=0.9,
                    alpha=0.45 if main else 0.2, zorder=2)
            if main or name == "Earth":
                ax.plot(body["x"], body["y"], "o", color=color,
                        markersize=size if main else 3.5,
                        markeredgecolor=Config.CIEL_100, markeredgewidth=1, zorder=6)
            if main:
                text = labels["earth"] if name == "Earth" else labels["planets"][name]
                _body_label(ax, body["x"], body["y"], f"{SYMBOL[name]} {text}", color,
                            dx=7, dy=6)


# ──────────────────────────────────────────────────────────────────────────────
# ECLIPSE PROJECTED ON THE GROUND
# ──────────────────────────────────────────────────────────────────────────────

_WORLD_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "world_land.json")
_world_rings = []


def world_rings():
    """Coastlines of the lands (Natural Earth 1:110m, public domain): list of (lons, lats)."""
    if not _world_rings:
        with open(_WORLD_FILE, encoding="utf-8") as f:
            for ring in json.load(f)["rings"]:
                lon, lat = zip(*ring)
                _world_rings.append((np.array(lon), np.array(lat)))
    return _world_rings


def _wrapped(lons, lats):
    """A small polygon (shadow footprint) across the 180° meridian, drawn on both sides of the map."""
    lons, lats = np.asarray(lons), np.asarray(lats)
    if np.ptp(lons) <= 180.0:
        return [np.column_stack((lons, lats))]
    east = np.where(lons < 0.0, lons + 360.0, lons)
    return [np.column_stack((east, lats)), np.column_stack((east - 360.0, lats))]


def _broken_line(lons, lats):
    """A line with gaps where it leaves the Earth (NaN) or crosses the 180° meridian."""
    lons, lats = np.array(lons, dtype=float), np.array(lats, dtype=float)
    jump = np.flatnonzero(np.abs(np.diff(lons)) > 180.0) + 1
    return np.insert(lons, jump, np.nan), np.insert(lats, jump, np.nan)


def draw_eclipse_map(fig, scene, labels, observer=None):
    """
    World map of an eclipse projected on the ground (equirectangular).

    Args:
        fig: matplotlib Figure (cleared first).
        scene (dict): from ``AstroEngine.eclipse_map``.
        labels (dict): title, greatest, observer; solar: central, path,
            partial; lunar: moon_up, limits.
        observer (tuple | None): (lat, lon) of the place entered.
    """
    from matplotlib.collections import PolyCollection
    from matplotlib.lines import Line2D

    fig.clear()
    fig.set_layout_engine("constrained")
    fig.patch.set_facecolor(Config.CIEL_100)
    ax = fig.add_subplot(1, 1, 1)
    _style_axes(ax)
    ax.set_facecolor(mix(Config.CIEL_000, Config.CIEL_100, 0.5))
    ax.set_xlim(-180, 180)
    ax.set_ylim(-90, 90)
    ax.set_aspect("equal")
    ax.xaxis.set_major_locator(MultipleLocator(60))
    ax.yaxis.set_major_locator(MultipleLocator(30))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _p: f"{int(v)}°"))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _p: f"{int(v)}°"))
    # Natural Earth already cuts the lands at ±180°: drawn as they are
    land = [np.column_stack((lon, lat)) for lon, lat in world_rings()]
    ax.add_collection(PolyCollection(land, facecolors=Config.CIEL_200, edgecolors=Config.ENCRE_ATTENUEE,
                                     linewidths=0.3, zorder=1))
    handles = []
    if scene["kind"] == "solar":
        levels = [0.001, 0.25, 0.5, 0.75]
        ax.contourf(scene["lons"], scene["lats"], scene["grid"], levels=levels + [2.0],
                    colors=[to_rgba(Config.OR, a) for a in (0.10, 0.18, 0.26, 0.34)], zorder=2)
        lines = ax.contour(scene["lons"], scene["lats"], scene["grid"], levels=levels,
                           colors=Config.OR, linewidths=0.7, zorder=3)
        ax.clabel(lines, fmt=lambda v: f"{v:.2f}".replace(".", labels.get("decimal", ".")).rstrip("0")
                  .rstrip(labels.get("decimal", ".")) if v > 0.01 else "0", fontsize=SIZE_LEGENDE * 0.8)
        if scene["path"]:
            path = [poly for lat, lon in scene["path"] for poly in _wrapped(lon, lat)]
            ax.add_collection(PolyCollection(path, facecolors=to_rgba(Config.OR, 0.85),
                                             edgecolors="none", zorder=4))
            handles.append(Patch(color=to_rgba(Config.OR, 0.85), label=labels["path"]))
        c_lat, c_lon = scene["central"]
        if not np.all(np.isnan(c_lat)):
            x, y = _broken_line(c_lon, c_lat)
            ax.plot(x, y, color=Config.ENCRE, linewidth=0.9, zorder=5)
            handles.append(Line2D([], [], color=Config.ENCRE, linewidth=0.9, label=labels["central"]))
        handles.append(Patch(color=to_rgba(Config.OR, 0.26), label=labels["partial"]))
    else:
        ax.contourf(scene["lons"], scene["lats"], scene["at_greatest"], levels=[0.0, 90.0],
                    colors=[to_rgba(Config.LUNE, 0.30)], zorder=2)
        for key in ("at_start", "at_end"):
            ax.contour(scene["lons"], scene["lats"], scene[key], levels=[0.0], colors=Config.LUNE,
                       linewidths=0.9, linestyles="--", zorder=3)
        handles.append(Patch(color=to_rgba(Config.LUNE, 0.30), label=labels["moon_up"]))
        handles.append(Line2D([], [], color=Config.LUNE, linewidth=0.9, linestyle="--",
                              label=labels["limits"]))
    lat, lon = scene["greatest"]
    ax.plot(lon, lat, "*", color=Config.ENCRE, markersize=11, markeredgecolor=Config.CIEL_100,
            markeredgewidth=0.6, zorder=6)
    handles.append(Line2D([], [], marker="*", linestyle="none", color=Config.ENCRE, markersize=10,
                          label=labels["greatest"]))
    if observer is not None:
        ax.plot(observer[1], observer[0], "o", color=Config.LUNE, markersize=6,
                markeredgecolor=Config.CIEL_100, markeredgewidth=1, zorder=7)
        handles.append(Line2D([], [], marker="o", linestyle="none", color=Config.LUNE, markersize=6,
                              label=labels["observer"]))
    legend = ax.legend(handles=handles, loc="lower left", fontsize=SIZE_LEGENDE * 0.85,
                       facecolor=Config.CIEL_100, edgecolor=Config.CIEL_200, labelcolor=Config.ENCRE,
                       framealpha=0.92)
    legend.set_zorder(10)
    _title(fig, ax, labels["title"])
    return ax


# ──────────────────────────────────────────────────────────────────────────────
# CONJUNCTIONS, OPPOSITIONS, ELONGATIONS
# ──────────────────────────────────────────────────────────────────────────────

def _tick_step(span_days):
    """Days between two date ticks along the paths of an event map."""
    for step in (2, 4, 5, 10, 20):
        if span_days / step <= 8:
            return step
    return 30


def draw_event_map(fig, scene, labels, date):
    """
    Star chart of a conjunction, an opposition or a greatest elongation: the
    paths of the bodies among the stars around the instant (equatorial
    coordinates of date, north up, east to the left, as seen in the sky).

    Args:
        fig: matplotlib Figure (cleared first).
        scene (dict): from ``AstroEngine.event_scene``.
        labels (dict): title, ecliptic, bodies ({"Venus": "Vénus", "Sun": "Soleil"}),
            date_format (strftime of the date ticks, "%d/%m" by default), and
            decimal (the decimal separator).
        date (datetime): instant of the event, in the time zone of the ticks.
    """
    fig.clear()
    fig.set_layout_engine("constrained")
    fig.patch.set_facecolor(Config.CIEL_100)
    ax = fig.add_subplot(1, 1, 1)
    _style_axes(ax)
    ax.set_facecolor(Config.CIEL_000)

    shown = [b for b in scene["bodies"] if not (scene["type"] == "opposition" and b[0] == "Sun")]
    ra0 = float(np.mean([b[3] for b in shown])) if len(shown) == 1 else None
    if ra0 is None:                                   # centre between the bodies, across 0h
        d = ((shown[1][3] - shown[0][3] + 12.0) % 24.0) - 12.0
        ra0 = (shown[0][3] + d / 2.0) % 24.0
    dec0 = float(np.mean([b[4] for b in shown]))
    k = math.cos(math.radians(dec0))

    def xy(ra, dec):
        return -(((np.asarray(ra) - ra0 + 12.0) % 24.0) - 12.0) * 15.0 * k, np.asarray(dec)

    xs, ys = [], []
    for b in shown:
        x, y = xy(b[1], b[2])
        xs.append(x)
        ys.append(y)
    xs, ys = np.concatenate(xs), np.concatenate(ys)
    half = max(3.0, 0.55 * max(np.ptp(xs), np.ptp(ys)) + 1.5)
    cx, cy = 0.5 * (xs.min() + xs.max()), 0.5 * (ys.min() + ys.max())
    x_lim, y_lim = (cx - half, cx + half), (cy - half, cy + half)   # x already grows westward
    ax.set_xlim(*x_lim)
    ax.set_ylim(*y_lim)
    ax.set_aspect("equal")
    ax.grid(False)

    from matplotlib.ticker import FixedLocator

    step = next(s for s in (1, 2, 5, 10, 15, 20, 30) if 2 * half / s <= 8)
    ax.yaxis.set_major_locator(MultipleLocator(step))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _p: f"{v:+.0f}°".replace("+0°", "0°")))
    # right ascension: round values, about as far apart as the declination ticks
    ra_step = next((m for m in (5, 10, 15, 20, 30, 60, 120, 180) if m >= step * 4.0 / k), 240) / 60.0
    ra_ticks = np.arange(math.floor((ra0 - 12.0) / ra_step), math.ceil((ra0 + 12.0) / ra_step) + 1) * ra_step
    tick_x = [float(xy(r % 24.0, 0.0)[0]) for r in ra_ticks]
    keep = [(x, r % 24.0) for x, r in zip(tick_x, ra_ticks) if min(x_lim) <= x <= max(x_lim)]
    ax.xaxis.set_major_locator(FixedLocator([x for x, _r in keep]))
    names = {round(x, 6): f"{int(r + 1e-9)}h{int(round((r % 1.0) * 60.0)) % 60:02d}" for x, r in keep}
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _p: names.get(round(v, 6), "")))

    # stars in the field, the brightest named
    inside = []
    for name, ra, dec, mag in scene["stars"]:
        x, y = xy(ra, dec)
        if min(x_lim) <= x <= max(x_lim) and y_lim[0] <= y <= y_lim[1]:
            inside.append((name, float(x), float(y), mag))
    if inside:
        ax.scatter([s[1] for s in inside], [s[2] for s in inside],
                   s=[star_marker_size(s[3]) for s in inside],
                   color=[to_rgba(Config.ENCRE, min(1.0, max(0.45, 1.0 - s[3] / 7.0))) for s in inside],
                   linewidths=0, zorder=2)
        for name, x, y, mag in sorted(inside, key=lambda s: s[3])[:8]:
            if mag < 3.5:
                ax.annotate(name, (x, y), xytext=(4, 3), textcoords="offset points",
                            fontsize=SIZE_LEGENDE * 0.75, color=Config.ENCRE_ATTENUEE, zorder=3)

    ex, ey = xy(*scene["ecliptic"])
    jumps = np.flatnonzero(np.abs(np.diff(ex)) > 90.0)
    ex, ey = np.insert(ex.astype(float), jumps + 1, np.nan), np.insert(ey.astype(float), jumps + 1, np.nan)
    ax.plot(ex, ey, color=Config.OR, linewidth=0.8, linestyle=(0, (5, 4)), alpha=0.6, zorder=1)
    visible = np.flatnonzero((ex > min(x_lim)) & (ex < max(x_lim)) & (ey > y_lim[0]) & (ey < y_lim[1]))
    if len(visible):
        i = visible[min(len(visible) - 1, len(visible) // 8)]
        ax.annotate(labels["ecliptic"], (ex[i], ey[i]), xytext=(0, -11), textcoords="offset points",
                    fontsize=SIZE_LEGENDE * 0.8, color=Config.OR, alpha=0.8, ha="center", zorder=1)

    days = np.asarray(scene["days"])
    tick = _tick_step(days.max())
    ticks = np.flatnonzero(np.isclose(np.mod(days, tick), 0.0) & (days != 0.0))
    fmt = labels.get("date_format", "%d/%m")
    palette = [Config.ENCRE, Config.LUNE]
    at = [xy(b[3], b[4]) for b in shown]
    highest = max(range(len(shown)), key=lambda n: float(at[n][1]))
    min_gap = 0.09 * half                             # between two date labels
    for n, (name, ra, dec, _ra_at, _dec_at) in enumerate(shown):
        color = Config.OR if name == "Sun" else palette[n % 2]
        x, y = xy(ra, dec)
        above = n == highest
        ax.plot(x, y, color=color, linewidth=1.1, alpha=0.75, zorder=4)
        ax.scatter(x[ticks], y[ticks], s=9, color=color, linewidths=0, zorder=5)
        if n == 0:                                    # dates along the first planet's path only
            placed = [(float(at[0][0]), float(at[0][1]))]
            for i in ticks:
                if any(math.hypot(x[i] - u, y[i] - v) < min_gap for u, v in placed):
                    continue
                placed.append((float(x[i]), float(y[i])))
                ax.annotate((date + timedelta(days=float(days[i]))).strftime(fmt), (x[i], y[i]),
                            xytext=(0, 6 if above else -6), textcoords="offset points", ha="center",
                            va="bottom" if above else "top", fontsize=SIZE_LEGENDE * 0.7,
                            color=mix(color, Config.CIEL_100, 0.25), zorder=5)
        px, py = (float(v) for v in at[n])
        if name == "Sun":
            ax.add_patch(Circle((px, py), scene["sun_radius"], color=Config.OR, zorder=6))
            ax.plot(px, py, "o", color=Config.OR, markersize=9, alpha=0.35, markeredgewidth=0, zorder=6)
        else:
            ax.plot(px, py, "o", color=color, markersize=6.5, markeredgecolor=Config.CIEL_000,
                    markeredgewidth=0.8, zorder=7)
        _body_label(ax, px, py, f"{SYMBOL.get(name, '')} {labels['bodies'].get(name, name)}",
                    color, size=SIZE_CORPS, weight=600, dx=9, dy=7 if above else -9,
                    va="bottom" if above else "top")
    _title(fig, ax, labels["title"])
    return ax

