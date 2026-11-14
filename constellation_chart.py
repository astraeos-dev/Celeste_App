"""
constellation_chart.py — A chart of each constellation, as in the sky atlases (4.24)
====================================================================================
For one of the 88 constellations: its outline (the boundaries of Delporte,
1930, that the IAU adopted, brought to J2000: assets/constellation_bounds.json,
from d3-celestial, BSD 3-Clause), its figure, the stars to magnitude 6.5 with
their Bayer letters, the deep-sky objects, the outlines and the names of its
neighbours and a grid of right ascension and declination, on a stereographic
projection centred on it (the shapes are kept; east on the left, as the sky is
seen); and its facts: its area, the month it is highest at 10 pm, whether it
rises at the place, its brightest stars and its finest objects.

No Qt: ui/constellations_tab.py shows it, and prints it on an A4 page.
"""
import functools
import json
import math
import os

import numpy as np

_ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
_GREEK = set("αβγδεζηθικλμνξοπρστυφχψω")


@functools.lru_cache(maxsize=1)
def outlines():
    """{IAU abbreviation: [ring, ...]}: each ring a closed list of [RA hours, Dec degrees], J2000."""
    with open(os.path.join(_ASSETS, "constellation_bounds.json"), encoding="utf-8") as f:
        return json.load(f)


def densified(ring, step=1.0):
    """The ring's points with its edges cut every *step* degrees at most (the boundaries
    follow parallels and hour circles: long edges curve on a chart)."""
    out = []
    for (ra1, d1), (ra2, d2) in zip(ring, ring[1:]):
        dra = (ra2 - ra1 + 12.0) % 24.0 - 12.0                     # the short way round, hours
        length = max(abs(dra) * 15.0 * math.cos(math.radians((d1 + d2) / 2)), abs(d2 - d1))
        n = max(1, int(math.ceil(length / step)))
        out.extend(((ra1 + dra * k / n) % 24.0, d1 + (d2 - d1) * k / n) for k in range(n))
    out.append(tuple(ring[-1]))
    return out


def _vectors(ra_hours, dec):
    a, d = np.radians(np.asarray(ra_hours, float) * 15.0), np.radians(np.asarray(dec, float))
    return np.stack([np.cos(d) * np.cos(a), np.cos(d) * np.sin(a), np.sin(d)], axis=-1)


def center(key):
    """(RA hours, Dec degrees) of the middle of a constellation's outline."""
    points = [p for ring in outlines()[key] for p in densified(ring)]
    v = _vectors([p[0] for p in points], [p[1] for p in points]).mean(axis=0)
    return (math.degrees(math.atan2(v[1], v[0])) / 15.0) % 24.0, math.degrees(math.asin(v[2] / np.linalg.norm(v)))


def area(key):
    """The constellation's area in square degrees (the sum of its rings: Serpens has two)."""
    total = 0.0
    for ring in outlines()[key]:
        points = densified(ring, 0.25)
        lam = np.radians(np.array([p[0] for p in points]) * 15.0)
        phi = np.radians(np.array([p[1] for p in points]))
        dlam = (np.diff(lam) + np.pi) % (2 * np.pi) - np.pi
        signed = np.sum(dlam * (2 + np.sin(phi[:-1]) + np.sin(phi[1:]))) / 2.0
        # a ring around a pole closes the cap on the side it turns about
        steradians = abs(signed)
        if steradians > 2 * np.pi:
            steradians = 4 * np.pi - steradians
        total += steradians
    return total * (180.0 / math.pi) ** 2


def project(ra_hours, dec, ra0, dec0):
    """
    Stereographic projection centred on (*ra0* hours, *dec0* degrees): x to the
    west (east on the left), y to the north, in units of the sphere's radius;
    points more than 120° away come back as NaN.
    """
    a = np.radians((np.asarray(ra_hours, float) - ra0) * 15.0)
    d, d0 = np.radians(np.asarray(dec, float)), math.radians(dec0)
    cos_c = math.sin(d0) * np.sin(d) + math.cos(d0) * np.cos(d) * np.cos(a)
    k = np.where(cos_c > -0.5, 2.0 / (1.0 + np.maximum(cos_c, -0.5)), np.nan)
    return -k * np.cos(d) * np.sin(a), k * (math.cos(d0) * np.sin(d) - math.sin(d0) * np.cos(d) * np.cos(a))


def best_month(ra_hours):
    """
    The month (1–12) the point of *ra_hours* is highest at 10 pm local mean time:
    then the sidereal time of 10 pm is its right ascension (the sidereal time at
    10 pm on 1 January is 4.70 h, and it gains 3 min 56 s a day).
    """
    day = ((ra_hours - 4.70) % 24.0) / 0.065710
    return min(12, int(day / 30.44) + 1)


def visibility(key, latitude):
    """"all" (every part rises at *latitude*), "part" or "none"."""
    decs = [p[1] for ring in outlines()[key] for p in ring]
    limit = 90.0 - abs(latitude)                                  # the other pole's cap never rises
    if latitude >= 0:
        lowest, highest = min(decs), max(decs)
        return "all" if lowest > -limit else "none" if highest < -limit else "part"
    lowest, highest = -max(decs), -min(decs)
    return "all" if lowest > -limit else "none" if highest < -limit else "part"


def own_stars(key, stars):
    """The stars of *stars* ((designation, RA, Dec, mag, ..., name)) that belong to *key* by
    their Bayer or Flamsteed designation ("α Ori", "46 LMi"), the brightest first."""
    found = [s for s in stars if s[0].rsplit(" ", 1)[-1] == key and " " in s[0]]
    return sorted(found, key=lambda s: s[3])


def bayer(designation):
    """The Greek letter of a designation ("α", "π³"), or "" for another one."""
    head = designation.split(" ", 1)[0]
    return head if head and head[0] in _GREEK else ""


def chart(key, stars, figures, deep_sky, mag_limit=6.5, deep_mag=9.0):
    """
    Everything the chart of *key* draws, projected: a dict with the view's
    limits, the grid lines and their labels, the outline (own and the
    neighbours'), the figures, the stars (x, y, mag, label), the deep-sky
    objects (x, y, type, label) and the neighbours' names.

    *stars*: star_catalog.CATALOG; *figures*: charts.constellation_figures();
    *deep_sky*: planner.deep_sky_catalog().
    """
    ra0, dec0 = center(key)
    rings = {k: [densified(r) for r in rs] for k, rs in outlines().items()}
    own = []
    for ring in rings[key]:
        x, y = project([p[0] for p in ring], [p[1] for p in ring], ra0, dec0)
        own.append((x, y))
    xs = np.concatenate([x for x, _y in own])
    ys = np.concatenate([y for _x, y in own])
    half = max(xs.max() - xs.min(), ys.max() - ys.min(), math.radians(18.0)) / 2 * 1.18
    cx, cy = (xs.max() + xs.min()) / 2, (ys.max() + ys.min()) / 2
    view = (cx - half, cx + half, cy - half, cy + half)

    def inside(x, y, slack=0.0):
        return (view[0] - slack <= x) & (x <= view[1] + slack) & (view[2] - slack <= y) & (y <= view[3] + slack)

    scene = {"key": key, "center": (ra0, dec0), "view": view, "own": own, "neighbours": [], "names": [],
             "lines": [], "own_lines": [], "stars": [], "deep_sky": [], "grid": [], "grid_labels": []}
    reach = 2.2 * half
    for other, other_rings in rings.items():
        if other == key:
            continue
        seen_x, seen_y = [], []
        for ring in other_rings:
            x, y = project([p[0] for p in ring], [p[1] for p in ring], ra0, dec0)
            if np.any(inside(x, y, reach)):
                scene["neighbours"].append((x, y))
            within = inside(x, y, -0.08 * half)
            seen_x.extend(x[within])
            seen_y.extend(y[within])
        if seen_x:                       # named in the middle of the part of its outline in view
            scene["names"].append((other, float(np.mean(seen_x)), float(np.mean(seen_y))))
    for other, figure in figures.items():
        target = scene["own_lines"] if other == key else scene["lines"]
        for line in figure["lines"]:
            x, y = project([p[0] for p in line], [p[1] for p in line], ra0, dec0)
            if np.any(inside(x, y)):
                target.append((x, y))
    # the stars: their own ones named by their Greek letter, the brightest by their name too
    ra = np.array([s[1] for s in stars])
    dec = np.array([s[2] for s in stars])
    x, y = project(ra, dec, ra0, dec0)
    keep = inside(x, y) & (np.array([s[3] for s in stars]) <= mag_limit)
    for i in np.flatnonzero(keep):
        s = stars[i]
        mine = s[0].rsplit(" ", 1)[-1] == key
        label = bayer(s[0]) if mine else ""
        name = s[6] if (mine and s[3] < 2.5 and len(s) > 6) else ""
        scene["stars"].append({"x": float(x[i]), "y": float(y[i]), "mag": s[3], "label": label, "name": name,
                               "designation": s[0], "own": mine})
    worth = [o for o in deep_sky if o["m"] or o["c"] or (o["mag"] is not None and o["mag"] <= deep_mag)]
    worth.sort(key=lambda o: (0 if o["m"] else 1 if o["c"] else 2, o["mag"] if o["mag"] is not None else 99))
    dx, dy = project(np.array([o["ra"] for o in worth]) / 15.0, np.array([o["dec"] for o in worth]), ra0, dec0)
    for o, ox, oy in zip(worth, dx, dy):
        if not bool(inside(ox, oy)):
            continue
        label = f"M{o['m']}" if o["m"] else f"C{o['c']}" if o["c"] else o["id"]
        scene["deep_sky"].append({"x": float(ox), "y": float(oy), "type": o["type"], "label": label,
                                  "mag": o["mag"], "own": o["const"] == key, "named": bool(o["m"] or o["c"])})
    # the grid: hour circles and parallels, labelled where they leave the view at the bottom and on the left
    step_ra = 1.0 if abs(dec0) < 60 else 2.0
    labelled = []
    for k in range(int(24 / step_ra)):
        h = k * step_ra
        x, y = project(np.full(181, h), np.linspace(-90, 90, 181), ra0, dec0)
        visible = inside(x, y)
        if np.any(visible):
            scene["grid"].append((x, y))
            i = np.flatnonzero(visible)[np.argmin(y[visible])]
            if all(abs(x[i] - other) > 0.12 * half for other in labelled):   # near a pole they crowd
                labelled.append(float(x[i]))
                scene["grid_labels"].append(("ra", f"{h:g}h", float(x[i]), float(y[i])))
    for d in range(-80, 90, 10):
        x, y = project(np.linspace(0, 24, 721), np.full(721, float(d)), ra0, dec0)
        visible = inside(x, y)
        if np.any(visible):
            scene["grid"].append((x, y))
            i = np.flatnonzero(visible)[np.argmin(x[visible])]
            scene["grid_labels"].append(("dec", f"{d:+d}°", float(x[i]), float(y[i])))
    return scene


def facts(key, latitude, stars, deep_sky, count=6):
    """The facts of the sheet: area, best month, visibility at *latitude*, the brightest
    stars [(designation, name, mag)] and the finest deep-sky objects [(label, type, mag, name)]."""
    ra0, _dec0 = center(key)
    brightest = [(s[0], s[6] if len(s) > 6 else "", s[3]) for s in own_stars(key, stars)[:count]]
    objects = sorted((o for o in deep_sky if o["const"] == key and (o["m"] or o["c"] or (o["mag"] or 99) <= 9.0)),
                     key=lambda o: (0 if o["m"] else 1, o["mag"] if o["mag"] is not None else 99))
    finest = [(f"M{o['m']}" if o["m"] else f"C{o['c']}" if o["c"] else o["id"], o["type"], o["mag"], o["name"],
               o["m"]) for o in objects[:count]]
    return {"area": area(key), "month": best_month(ra0), "visibility": visibility(key, latitude),
            "stars": brightest, "objects": finest}


# ── Drawing ───────────────────────────────────────────────────────────────────

PRINT_COLORS = {"background": "#ffffff", "ink": "#000000", "soft": "#555555", "faint": "#9a9a9a",
                "grid": "#d8d8d8", "outline": "#000000", "deep": "#1f4e8c"}


def draw(ax, scene, names, colors=PRINT_COLORS, size=1.0):
    """
    Draws *scene* (chart()) in *ax*: the grid, the neighbours' outlines and
    figures and names (*names*: {abbreviation: name}), the outline and the figure
    of the constellation, its stars with their letters, the deep-sky objects.
    *size* scales the texts and the marks (1 on screen, more on paper).
    """
    import charts
    x0, x1, y0, y1 = scene["view"]
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_facecolor(colors["background"])
    clip = ax.patch
    def line(x, y, **style):
        artist, = ax.plot(x, y, **style)
        artist.set_clip_path(clip)
    for x, y in scene["grid"]:
        line(x, y, color=colors["grid"], linewidth=0.5 * size, zorder=1)
    for kind, text, x, y in scene["grid_labels"]:
        if kind == "ra":
            ax.annotate(text, (x, y0), xytext=(0, 3), textcoords="offset points", ha="center", va="bottom",
                        fontsize=6.5 * size, color=colors["faint"], zorder=2, annotation_clip=False)
        else:
            ax.annotate(text, (x0, y), xytext=(3, 0), textcoords="offset points", ha="left", va="center",
                        fontsize=6.5 * size, color=colors["faint"], zorder=2, annotation_clip=False)
    for x, y in scene["neighbours"]:
        line(x, y, color=colors["faint"], linewidth=0.6 * size, linestyle=(0, (4, 3)), zorder=2)
    for x, y in scene["lines"]:
        line(x, y, color=colors["grid"], linewidth=0.7 * size, zorder=2)
    span = x1 - x0
    neighbours = []
    for key, x, y in scene["names"]:
        # near a side of the chart, the name runs from its point towards the middle: not cut by the edge
        ha = "left" if x < x0 + 0.22 * span else "right" if x > x1 - 0.22 * span else "center"
        neighbours.append(ax.text(min(max(x, x0 + 0.01 * span), x1 - 0.01 * span), y, names.get(key, key).upper(),
                                  fontsize=6.5 * size, color=colors["faint"], ha=ha, va="center", zorder=3,
                                  clip_on=True))
    for x, y in scene["own"]:
        line(x, y, color=colors["outline"], linewidth=1.0 * size, linestyle=(0, (5, 3)), zorder=4)
    for x, y in scene["own_lines"]:
        line(x, y, color=colors["soft"], linewidth=1.0 * size, zorder=4)
    stars = scene["stars"]
    if stars:
        ax.scatter([s["x"] for s in stars], [s["y"] for s in stars],
                   s=[charts.star_marker_size(s["mag"]) * size * size for s in stars],
                   color=[colors["ink"] if s["own"] else colors["soft"] for s in stars],
                   linewidths=0, zorder=5).set_clip_path(clip)
    lettered = []
    for s in sorted(stars, key=lambda s: s["mag"]):
        text = s["label"] + (f"  {s['name']}" if s["name"] else "")
        if text:
            lettered.append(ax.annotate(text, (s["x"], s["y"]), xytext=(3.5 * size, 2.5 * size),
                                        textcoords="offset points", fontsize=(7.5 if s["mag"] < 3 else 6.5) * size,
                                        color=colors["ink"], zorder=6, annotation_clip=True))
    named, others = [], []
    for o in scene["deep_sky"]:
        marker = next((m for kinds, m in charts._DEEP_SKY_MARKERS.items() if o["type"] in kinds), "s")
        style = {"color": colors["deep"]} if marker == "x" else {"facecolors": "none", "edgecolors": colors["deep"]}
        ax.scatter([o["x"]], [o["y"]], s=28 * size * size, marker=marker, linewidths=0.9 * size, zorder=5,
                   **style).set_clip_path(clip)
        if o["label"]:
            (named if o.get("named") else others).append(
                ax.annotate(o["label"], (o["x"], o["y"]), xytext=(4 * size, -8 * size), textcoords="offset points",
                            fontsize=6.3 * size, color=colors["deep"], zorder=6, annotation_clip=True))
    # the order of importance: the bright stars, the Messier and Caldwell objects, the other stars,
    # the neighbours, the other objects
    bright = [text for text in lettered if text.get_fontsize() > 7.0 * size]
    ax._celeste_labels = bright + named + [text for text in lettered if text not in bright] + neighbours + others
    declutter(ax)


def declutter(ax):
    """
    The labels of *ax* (drawn by draw()) clear of one another, as they are drawn
    at the figure's present size: a label that would sit on a more important one
    goes to the other side of its point, or is hidden. To be run again when the
    chart changes size.
    """
    (x0, x1), (y0, y1) = sorted(ax.get_xlim()), sorted(ax.get_ylim())
    taken = []
    for text in getattr(ax, "_celeste_labels", ()):
        x, y = text.xy if hasattr(text, "xyann") else text.get_position()
        if not (x0 <= x <= x1 and y0 <= y <= y1):          # its point is out of view: not drawn
            text.set_visible(False)
            continue
        text.set_visible(True)
        places = [None]
        if hasattr(text, "xyann"):                         # an annotation: its point's other side too
            if not hasattr(text, "_celeste_home"):
                text._celeste_home = (tuple(text.xyann), text.get_ha())
            (dx, dy), ha = text._celeste_home
            places = [((dx, dy), ha), ((-dx, dy), "right" if ha == "left" else "left")]
        for place in places:
            _place_label(text, place)
            box = text.get_window_extent().padded(1.0)
            if not any(box.overlaps(other) for other in taken):
                taken.append(box)
                break
        else:
            text.set_visible(False)
            _place_label(text, places[0])


def _place_label(text, place):
    """An annotation's label at *place*, (offset, horizontal alignment); None: as it is."""
    if place is not None:
        text.xyann = place[0]
        text.set_ha(place[1])


# ── The sheet to print ────────────────────────────────────────────────────────

def sheet(path, key, latitude, place_text, stars, figures, deep_sky):
    """
    Writes the A4 sheet of *key* to *path* (PDF): its name, the chart, its
    facts for *latitude* (the place *place_text*), its brightest stars and its
    finest objects, in the interface's language.
    """
    from matplotlib.backends.backend_pdf import PdfPages
    fig = sheet_figure(key, latitude, place_text, stars, figures, deep_sky)
    with PdfPages(path) as pdf:
        pdf.savefig(fig)
    return path


def sheet_figure(key, latitude, place_text, stars, figures, deep_sky):
    """The figure of sheet(): the name and the facts above the chart, the brightest
    stars and the finest objects under it, side by side."""
    from matplotlib.figure import Figure

    import charts
    from i18n import t
    charts.configure_fonts()
    names = {k: t(f"constellations.{k}") for k in outlines()}
    scene = chart(key, stars, figures, deep_sky)
    info = facts(key, latitude, stars, deep_sky)
    fig = Figure(figsize=(210 / 25.4, 297 / 25.4))
    fig.text(0.07, 0.955, names[key], fontsize=20, fontweight=600, va="top")
    fig.text(0.07, 0.923, fact_line(key, info), fontsize=9, va="top", color="#333333")
    ax = fig.add_axes((0.07, 0.30, 0.86, 0.86 * 210 / 297))
    draw(ax, scene, names, PRINT_COLORS, size=1.25)
    for spine in ("left", "right", "top", "bottom"):
        ax.spines[spine].set_visible(False)
    # two columns: the stars (short lines), the objects (their names in full)
    for x, title, rows in ((0.07, t("constellation_chart.stars"), [star_line(row) for row in info["stars"]]),
                           (0.34, t("constellation_chart.objects"), [object_line(row) for row in info["objects"]])):
        if not rows:
            continue
        fig.text(x, 0.255, title, fontsize=10.5, fontweight=600, va="top")
        for i, row in enumerate(rows):
            fig.text(x + 0.01, 0.233 - 0.017 * i, row, fontsize=8.6, va="top")
    fig.text(0.5, 0.025, f"Céleste — {names[key]} — {place_text}", fontsize=6.5, ha="center", color="#555555")
    return fig


# the languages whose months take no capital in a sentence ("en janvier", but "in January", "im Januar")
_LOWER_MONTHS = {"fr", "es"}


def fact_line(key, info):
    """"Orion (Ori) · 594 square degrees · highest at 10 pm in January · entirely visible from your place"."""
    from i18n import get_lang, t, tf
    month = t(f"workshop.month_{info['month']}")
    return tf("constellation_chart.facts", key=key, area=f"{info['area']:.0f}",
              month=month.lower() if get_lang() in _LOWER_MONTHS else month,
              visibility=t(f"constellation_chart.visible_{info['visibility']}"))


def star_line(row):
    """"β Rigel 0.12": the letter (or the number) without the constellation, the name, the magnitude."""
    designation, name, mag = row
    figure = f"{mag:.2f}".replace(".", "," if _comma() else ".")
    return f"{designation.rsplit(' ', 1)[0]}{' ' + name if name else ''} {figure}"


def object_line(row):
    """"M42 · Nebula · 4.0 · Orion Nebula", the Messier objects' names in the interface's language."""
    from i18n import t
    label, kind, mag, name, messier = row
    if messier and name:
        local = t(f"messier.name_{messier}")
        name = name if local.startswith("[") else local
    text = f"{label} · {t('messier.type_' + kind)}"
    if mag is not None:
        text += " · " + f"{mag:.1f}".replace(".", "," if _comma() else ".")
    return text + (f" · {name}" if name else "")


def _comma():
    from i18n import get_lang
    return get_lang() in ("fr", "es", "de")
