"""
month_sheet.py — The sky of the month, on one page to print
===========================================================
An A4 page for the place, in the colours of the Jour theme (dark ink on
white paper):

- the sky map on the 15th at 22:00 local time, as the magazines' monthly
  charts, with the hours the same sky shows on the first and the last day;
- the Moon day by day, drawn as it is lit, and its four phases;
- the planets in the middle of the month: when to see them, how bright;
- the month's events: the planets, the Moon, eclipses, seasons, meteor
  showers, the minima of Algol seen from the place.

collect() computes (a second or two, no Qt: run in the background); draw()
lays the page out with the words the interface gives it (the events' titles,
the planets' lines, in the interface language); save() writes the PDF.
"""
import math
import textwrap
from datetime import datetime, timedelta, timezone

import numpy as np
from matplotlib.figure import Figure
from matplotlib.patches import Circle, Polygon

import astro_calendar
import charts
from config import Config
from engine import AstroEngine

PAPER_MM = (210.0, 297.0)             # A4, portrait
MAP_DAY, MAP_HOUR = 15, 22            # the map: the 15th at 22:00 local time
MAP_MAG = 5.0                         # the faintest stars of the printed map
SIDEREAL_DAY = 0.99726957             # days: the same sky comes back 3 min 56 s earlier each day
CATEGORIES = tuple(c for c in astro_calendar.CATEGORIES if c != "satellites")   # passes: 10 days ahead only
EVENT_LINES = 19                      # lines in each of the two columns of events


def _to_ut(local, zone):
    """UT (naive) of the local time *local* (naive) of *zone*."""
    return local.replace(tzinfo=zone).astimezone(timezone.utc).replace(tzinfo=None)


def _next_month(year, month):
    return (year + 1, 1) if month == 12 else (year, month + 1)


def month_span(year, month, zone=timezone.utc):
    """The local month as UT datetimes: its first midnight, the next month's."""
    return _to_ut(datetime(year, month, 1), zone), _to_ut(datetime(*_next_month(year, month), 1), zone)


def days_in_month(year, month):
    return (datetime(*_next_month(year, month), 1) - datetime(year, month, 1)).days


def collect(year, month, lat, lon, elevation_m=0.0, zone=timezone.utc):
    """
    What the page shows, computed for the place.

    Returns:
        dict: year, month, lat, lon, zone; start, end (UT, the local month);
        map_time (UT of the 15th at 22:00 local); same_sky (UT of the first
        and the last day when the sky is the map's); scene (charts.sky_scene,
        stars to MAP_MAG); night (AstroEngine.tonight of the 15th); moon_days
        (AstroEngine.moon_calendar); events (astro_calendar.collect over the
        month, the phases of the Moon included).
    """
    start, end = month_span(year, month, zone)
    map_time = _to_ut(datetime(year, month, MAP_DAY, MAP_HOUR), zone)
    same_sky = [map_time + timedelta(days=(day - MAP_DAY) * SIDEREAL_DAY)
                for day in (1, days_in_month(year, month))]
    sky = charts.sky_state(map_time, lat, lon, elevation_m)
    bright = [m for m in sky["minor_planets"] if m["mag"] <= MAP_MAG]
    scene = charts.sky_scene(AstroEngine.julian_day(map_time), lat, lon, MAP_MAG, sky["sun"], sky["moon"],
                             sky["planets"] + bright)
    return {"year": year, "month": month, "lat": lat, "lon": lon, "zone": zone,
            "start": start, "end": end, "map_time": map_time, "same_sky": same_sky, "scene": scene,
            "night": AstroEngine.tonight(map_time, lat, lon, elevation_m, zone),
            "moon_days": AstroEngine.moon_calendar(year, month, lat, lon, elevation_m, zone),
            "events": astro_calendar.collect(start, end, lat, lon, elevation_m, zone, categories=CATEGORIES)}


# ── Drawing ───────────────────────────────────────────────────────────────────

def _moon_outline(phase, radius, southern=False, samples=33):
    """
    The lit part of the Moon's disc (centred on 0, 0) for the phase angle
    *phase* (Moon − Sun, degrees: 0 new, 180 full): its limb, then the
    terminator back. Lit on the right while waxing in the northern sky; the
    southern sky sees it the other way round. None at new moon.
    """
    p = phase % 360.0
    if min(p, 360.0 - p) < 1.0:
        return None
    side = 1.0 if p < 180.0 else -1.0
    if southern:
        side = -side
    k = math.cos(math.radians(p))
    ys = np.linspace(radius, -radius, samples)
    half = np.sqrt(np.maximum(radius * radius - ys * ys, 0.0))
    limb = np.column_stack([side * half, ys])
    terminator = np.column_stack([side * k * half, ys])[::-1]
    return np.vstack([limb, terminator])


def _text(fig, x_mm, y_mm, text, size, weight=400, color=None, ha="left", va="top", **style):
    """Text at (x, y) millimetres from the page's top left corner."""
    return fig.text(x_mm / PAPER_MM[0], 1.0 - y_mm / PAPER_MM[1], text, fontsize=size, fontweight=weight,
                    color=color or Config.ENCRE, ha=ha, va=va, **style)


def _axes(fig, x_mm, y_mm, w_mm, h_mm):
    """Axes over the rectangle (x, y, width, height) in millimetres from the top left corner."""
    width, height = PAPER_MM
    return fig.add_axes((x_mm / width, 1.0 - (y_mm + h_mm) / height, w_mm / width, h_mm / height))


def _lines(fig, x_mm, y_mm, lines, width_chars, size=7.5, step_mm=3.6, color=None, gap_mm=1.2):
    """Wrapped lines from (x, y) down; returns the y under the last one."""
    for line in lines:
        for part in textwrap.wrap(line, width_chars) or [""]:
            _text(fig, x_mm, y_mm, part, size, color=color)
            y_mm += step_mm
        y_mm += gap_mm
    return y_mm


def _clip(text, chars):
    return text if len(text) <= chars else text[:chars - 1].rstrip() + "…"


def draw(fig, sheet, texts):
    """
    Lays the page out on *fig* (PAPER_MM), in the active theme's colours.

    Args:
        sheet (dict): from collect().
        texts (dict): the interface's words: kicker, title, subtitle,
            map_labels (charts.draw_sky_map's), map_caption; moon_title,
            phases (lines); planets_title, planets (lines); events_title,
            events ([(when, title)], by date), no_events; footer.
    """
    fig.clear()
    fig.set_layout_engine("none")
    fig.patch.set_facecolor(Config.CIEL_100)
    width, _height = PAPER_MM
    left, right = 12.0, width - 12.0
    muted = Config.ENCRE_ATTENUEE

    _text(fig, left, 12.0, texts["kicker"].upper(), 8, 600, muted)
    _text(fig, left, 17.0, texts["title"], 20, 600)
    _text(fig, left, 27.5, texts["subtitle"], 8.5, color=muted)

    # the sky map, and when it shows
    ax = _axes(fig, left - 2.0, 33.0, 119.0, 119.0)
    charts.draw_sky_map(fig, sheet["scene"], texts["map_labels"], ax=ax)
    _lines(fig, left, 153.5, [texts["map_caption"]], 78, size=7.5, color=muted)

    # the Moon and the planets, beside the map
    column = 136.0
    _text(fig, column, 36.0, texts["moon_title"], 11, 600)
    y = _lines(fig, column, 43.0, texts["phases"], 46, gap_mm=0.4)
    _text(fig, column, y + 4.0, texts["planets_title"], 11, 600)
    _lines(fig, column, y + 11.0, texts["planets"], 46)

    # the Moon day by day
    days = sheet["moon_days"]
    strip = _axes(fig, left, 162.0, right - left, 15.0)
    strip.set_xlim(0, right - left)
    strip.set_ylim(-9.0, 6.0)
    strip.set_aspect("equal")
    strip.axis("off")
    slot = (right - left) / 31.0
    radius = min(2.4, slot * 0.38)
    southern = sheet["lat"] < 0
    for i, day in enumerate(days):
        cx = slot * (i + 0.5)
        strip.add_patch(Circle((cx, 1.5), radius, facecolor=Config.ENCRE, edgecolor=Config.ENCRE, linewidth=0.4))
        lit = _moon_outline(day["phase"], radius, southern)
        if lit is not None:
            strip.add_patch(Polygon(lit + (cx, 1.5), closed=True, facecolor=Config.CIEL_100, linewidth=0))
        if day.get("event"):                                  # a principal phase that day
            strip.add_patch(Circle((cx, 1.5), radius + 0.8, fill=False, edgecolor=Config.OR, linewidth=0.8))
        strip.text(cx, 1.5 - radius - 1.4, str(day["date"].day), ha="center", va="top", fontsize=5.5,
                   color=muted)

    # the month's events, in two columns
    _text(fig, left, 186.0, texts["events_title"], 11, 600)
    events = texts["events"]
    if not events:
        _text(fig, left, 193.0, texts["no_events"], 7.5, color=muted)
    column_width = (right - left) / 2.0
    for n, (when, title) in enumerate(events[:2 * EVENT_LINES]):
        x = left + (n // EVENT_LINES) * column_width
        y = 193.0 + (n % EVENT_LINES) * 4.5
        _text(fig, x, y, when, 7.5, 600)
        _text(fig, x + 19.0, y, _clip(title, 56), 7.5)

    _text(fig, left, PAPER_MM[1] - 9.0, texts["footer"], 6.5, color=muted)
    return fig


def save(path, sheet, texts):
    """Writes the page as a PDF at *path*."""
    from matplotlib.backends.backend_pdf import PdfPages
    fig = Figure(figsize=(PAPER_MM[0] / 25.4, PAPER_MM[1] / 25.4))
    draw(fig, sheet, texts)
    with PdfPages(path, metadata={"Title": f"{texts['title']} — {texts['kicker']}", "Creator": "Céleste"}) as pdf:
        pdf.savefig(fig)
