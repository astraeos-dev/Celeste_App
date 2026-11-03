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
from constellations import CONSTELLATIONS, STARS
from engine import AstroEngine, _HORIZON_CORRECTION_SUN

# Astronomical symbols (Astraeos Symboles). Matplotlib never draws emoji, so
# they go without the U+FE0E selector here.
SYMBOL = {"Sun": "☉", "Moon": "☽", "Earth": "⊕", "Venus": "♀",
          "Mars": "♂", "Jupiter": "♃", "Saturn": "♄", "vernal": "♈"}

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
    # every catalogue star brought to the date at once (precession, nutation, aberration)
    names = list(STARS)
    alts, azs = AstroEngine.stars_horizontal(
        (jd - 2451545.0) / 36525.0, lat, lon,
        [STARS[n][0] for n in names], [STARS[n][1] for n in names])
    horizontal = {n: (float(a), float(z)) for n, a, z in zip(names, alts, azs)}

    stars = []
    for name, (ra, dec, mag) in STARS.items():
        if mag > mag_limit:
            continue
        alt, az = horizontal[name]
        if alt <= 0:
            continue
        x, y = sky_xy(alt, az)
        stars.append({"kind": "star", "name": name, "alt": alt, "az": az,
                      "ra": ra, "dec": dec, "mag": mag, "x": x, "y": y})

    lines = []
    for edges in CONSTELLATIONS.values():
        for a, b in edges:
            if a not in STARS or b not in STARS:
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


def _body_label(ax, x, y, text, color, size=SIZE_LEGENDE, weight=400, dx=8, dy=6):
    ax.annotate(text, (x, y), xytext=(dx, dy), textcoords="offset points",
                fontsize=size, fontweight=weight, color=color, zorder=8)


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
        # Name the brightest stars, skipping a label that would sit on top of
        # the label of a brighter neighbour (Orion's belt, Castor and Pollux)
        labelled = []
        for s in sorted(stars, key=lambda s: s["mag"]):
            if s["mag"] >= 2.0:
                break
            if any(math.hypot(s["x"] - x, s["y"] - y) < 0.07 for x, y in labelled):
                continue
            labelled.append((s["x"], s["y"]))
            ax.annotate(s["name"], (s["x"], s["y"]), xytext=(4, 3),
                        textcoords="offset points", fontsize=SIZE_LEGENDE * 0.75,
                        color=Config.ENCRE_ATTENUEE, zorder=5)

    for p in scene["planets"]:
        if p["alt"] <= 0:
            continue
        ax.plot(p["x"], p["y"], "o", color=Config.ENCRE, markersize=4.5,
                markeredgewidth=0, zorder=6)
        _body_label(ax, p["x"], p["y"],
                    f"{SYMBOL[p['name']]} {labels['planets'].get(p['name'], p['name'])}",
                    Config.ENCRE, dx=6, dy=4)

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
_PERIOD_YEARS = {"Venus": 0.61520, "Mars": 1.88085,
                 "Jupiter": 11.8622, "Saturn": 29.4571}
_PLANET_MARKER = {"Venus": 6, "Mars": 5, "Jupiter": 9, "Saturn": 8}


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
    def body(name, period_years):
        x, y, _ = AstroEngine.planet_heliocentric(t, name)
        ox, oy, _ = AstroEngine.planet_heliocentric(               # one orbit, at once
            t + np.linspace(0.0, period_years / 100.0, samples + 1), name)
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
        (fig.add_subplot(1, 2, 1), 1.8, ("Venus", "Mars"), labels["inner"]),
        (fig.add_subplot(1, 2, 2), 10.6, ("Jupiter", "Saturn"), labels["outer"]),
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
