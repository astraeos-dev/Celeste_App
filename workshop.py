"""
workshop.py — The Workshop: instruments to print, cut out and assemble
======================================================================
PDF files at true scale of instruments computed for the place:

- planisphere (star wheel): the star disc with its date ring, the mask with
  the window of the horizon and the hour ring;
- equatorial sundial: the summer and winter faces, the wedge of the stand;
- horizontal sundial: the dial with its hour lines and date lines, the
  triangular gnomon with its nodus;
- planispheric astrolabe: the front (mater, limb, plate of the latitude), the
  rete and the rule on a transparent sheet, the back (altitude scale, zodiac,
  calendar of the year, shadow square), the alidade;
- nocturnal: the date disc and its handle, the hour disc with its teeth, the arm;

each followed by pages of explanations: how to assemble it, how to use it, the
astronomy behind it, worked examples for the place and the date, and the
table of the equation of time where the time must be corrected.

The geometry is in instruments.py; the texts in locales/ ("workshop"). No Qt:
the interface only chooses the instrument, the place, the options and where to save.
"""
import math
import textwrap
from datetime import datetime, timedelta, timezone

import numpy as np

import instruments
from i18n import t, tf

INSTRUMENTS = ("planisphere", "equatorial_dial", "horizontal_dial", "astrolabe", "nocturnal")
ASTROLABE_SIZES = (120, 150)
PAPERS = {"a4": (210.0, 297.0), "letter": (215.9, 279.4)}
_INK, _GREY, _LIGHT = "#000000", "#555555", "#999999"


# ── The place ─────────────────────────────────────────────────────────────────

class Place:
    """Where and when the instrument is made for: name, lat, lon (degrees, east
    positive), zone (tzinfo), when (UT datetime of the worked example)."""

    def __init__(self, name, lat, lon, zone, when):
        self.name, self.lat, self.lon, self.zone, self.when = name, lat, lon, zone, when.replace(tzinfo=None)
        self.std_offset, self.has_dst = self._standard_offset()

    def _standard_offset(self):
        """The zone's standard (winter) offset from UT in hours, and whether it has summer time."""
        offsets = []
        for month in (1, 7):
            moment = datetime(self.when.year, month, 15, 12, tzinfo=timezone.utc).astimezone(self.zone)
            offsets.append((moment.utcoffset() - (moment.dst() or timedelta(0))).total_seconds() / 3600.0)
            if moment.dst():
                offsets.append(None)
        return offsets[0], None in offsets

    def local(self, ut):
        return ut.replace(tzinfo=timezone.utc).astimezone(self.zone).replace(tzinfo=None)

    def utc(self, local):
        return local.replace(tzinfo=self.zone).astimezone(timezone.utc).replace(tzinfo=None)

    def dst_hours(self, ut):
        dst = ut.replace(tzinfo=timezone.utc).astimezone(self.zone).dst()
        return (dst or timedelta(0)).total_seconds() / 3600.0

    def describe(self):
        ns = t("skymap.cardinal_n") if self.lat >= 0 else t("skymap.cardinal_s")
        ew = t("skymap.cardinal_e") if self.lon >= 0 else t("skymap.cardinal_w")
        coords = f"{_num(abs(self.lat), 2)}° {ns}, {_num(abs(self.lon), 2)}° {ew}"
        return f"{self.name} · {coords}" if self.name else coords


def _num(value, decimals=0):
    text = f"{value:.{decimals}f}"
    return text.replace(".", t("workshop.decimal")) if decimals else text


def _offset_text(hours):
    sign = "+" if hours >= 0 else "−"
    h, m = divmod(round(abs(hours) * 60), 60)
    return f"UTC{sign}{h}" + (f":{m:02d}" if m else "")


def _hm(hours):
    """"14 h 05" style clock text of a number of hours."""
    total = round(hours * 60) % (24 * 60)
    return tf("workshop.clock", h=total // 60, m=f"{total % 60:02d}")


# ── Pages ─────────────────────────────────────────────────────────────────────

class _Pages:
    """A PDF of pages in millimetres, with a ruler and a footer on each."""

    def __init__(self, paper, footer):
        import charts
        charts.configure_fonts()
        self.width, self.height = PAPERS[paper]
        self.footer = footer
        self.figures = []

    def new(self, title, ruler=True):
        from matplotlib.figure import Figure
        fig = Figure(figsize=(self.width / 25.4, self.height / 25.4))
        ax = fig.add_axes((0, 0, 1, 1))
        ax.set_xlim(0, self.width)
        ax.set_ylim(0, self.height)
        ax.set_aspect("equal")
        ax.axis("off")
        ax.text(self.width / 2, self.height - 12, title, ha="center", va="top", fontsize=13, fontweight=600)
        ax.text(self.width / 2, 7, self.footer, ha="center", va="bottom", fontsize=6.5, color=_GREY)
        if ruler:
            self._ruler(ax)
        self.figures.append(fig)
        return fig, ax

    def _ruler(self, ax):
        x0, y0 = 14.0, 16.0
        ax.plot([x0, x0 + 100], [y0, y0], color=_INK, linewidth=0.6)
        for mm in range(0, 101, 5):
            ax.plot([x0 + mm, x0 + mm], [y0, y0 + (3 if mm % 10 == 0 else 1.5)], color=_INK, linewidth=0.4)
        ax.text(x0 + 102, y0, t("workshop.ruler"), va="center", fontsize=6, color=_GREY)

    def text_pages(self, title, sections):
        """Pages of explanations: [(heading, [paragraph, ...])]; long lines wrapped."""
        fig, ax = self.new(title, ruler=False)
        y = self.height - 26
        width = int((self.width - 36) / 1.62)                # characters of about 9 pt per line
        for heading, paragraphs in sections:
            needed = 9 + sum(len(textwrap.wrap(p, width)) * 4.3 + 2 for p in paragraphs[:1])
            if y - needed < 18:
                fig, ax = self.new(title, ruler=False)
                y = self.height - 26
            if heading:
                ax.text(18, y, heading, fontsize=10.5, fontweight=600, va="top")
                y -= 7
            for paragraph in paragraphs:
                lines = []
                for raw in paragraph.split("\n"):
                    if raw.startswith("|"):
                        lines.append(raw)
                    else:
                        numbered = raw[:1].isdigit() and raw[1:3] == ". "
                        hanging = "    " if numbered or raw.startswith("• ") else ""
                        lines += textwrap.wrap(raw, width, subsequent_indent=hanging) or [""]
                for line in lines:
                    if y < 18:
                        fig, ax = self.new(title, ruler=False)
                        y = self.height - 26
                    mono = line.startswith("|")
                    ax.text(18, y, line.lstrip("|"), fontsize=8.6 if not mono else 8, va="top",
                            family="monospace" if mono else None)
                    y -= 4.3
                y -= 2.2
            y -= 2.5
        return fig

    def save(self, path):
        from matplotlib.backends.backend_pdf import PdfPages
        with PdfPages(path) as pdf:
            for fig in self.figures:
                pdf.savefig(fig)


def _circle(ax, cx, cy, r, **style):
    a = np.linspace(0, 2 * np.pi, 721)
    ax.plot(cx + r * np.cos(a), cy + r * np.sin(a), **{"color": _INK, "linewidth": 0.5, **style})


def _cut(ax, x, y):
    """A cut line: thicker than the drawn lines."""
    ax.plot(x, y, color=_INK, linewidth=1.0)


# ── Planisphere ───────────────────────────────────────────────────────────────

def _bright_stars():
    from star_catalog import CATALOG
    return [(c[6] or c[0], c[1], c[2], c[3]) for c in CATALOG if c[3] <= 4.5]


def _build_planisphere(place, paper):
    import charts
    width, height = PAPERS[paper]
    cx, cy, r_edge = width / 2, height / 2 + 6, 72.0
    geo = instruments.planisphere(place.lat, place.lon, place.std_offset, place.when.year, r_edge,
                                  _bright_stars(), charts.constellation_figures())
    pages = _Pages(paper, f"Céleste — {t('workshop.planisphere')} — {place.describe()}")
    s = 1.0 if place.lat >= 0 else -1.0

    # 1. the star disc
    fig, ax = pages.new(t("workshop.planisphere_disc"))
    _circle(ax, cx, cy, r_edge, linewidth=0.4, color=_GREY)
    _circle(ax, cx, cy, r_edge + 5.5, linewidth=0.4, color=_GREY)
    for (x1, y1), (x2, y2) in geo["lines"]:
        ax.plot([cx + x1, cx + x2], [cy + y1, cy + y2], color=_LIGHT, linewidth=0.35)
    for name, x, y, mag in geo["stars"]:
        size = max(0.25, (4.8 - mag) * 0.85)
        ax.plot(cx + x, cy + y, "o", color=_INK, markersize=size, markeredgewidth=0)
        if mag < 1.6 and not name[0].isdigit() and " " not in name[:2]:
            ax.text(cx + x + 1.2, cy + y + 0.6, name, fontsize=4.6, color=_GREY)
    for key, x, y in geo["names"]:
        ax.text(cx + x, cy + y, t(f"constellations.{key}").upper(), fontsize=4.0, color=_GREY,
                ha="center", va="center")
    ex, ey = geo["ecliptic"]
    ax.plot(cx + ex, cy + ey, color=_GREY, linewidth=0.5, linestyle=(0, (4, 2)))
    qx, qy = geo["equator"]
    ax.plot(cx + qx, cy + qy, color=_GREY, linewidth=0.4, linestyle=(0, (1, 1.5)))
    # right ascension ring
    for hour, _a in geo["ra_ticks"]:
        for minute in range(0, 60, 10):
            ra = hour + minute / 60
            a = math.radians(ra * 15)
            inner = r_edge + (0 if minute == 0 else 2.5)
            p = [(-s * r * math.sin(a), -r * math.cos(a)) for r in (inner, r_edge + 5.5)]
            ax.plot([cx + p[0][0], cx + p[1][0]], [cy + p[0][1], cy + p[1][1]], color=_INK, linewidth=0.3)
        a = math.radians((hour + 0.5) * 15)
        ax.text(cx - s * (r_edge + 2.8) * math.sin(a), cy - (r_edge + 2.8) * math.cos(a), f"{hour}h",
                fontsize=4.4, ha="center", va="center", rotation=math.degrees(-s * a) + 180)
    # date ring
    r0, r1 = r_edge + 5.5, r_edge + 19.0
    _circle(ax, cx, cy, r0 + 6.5, linewidth=0.3)
    for month, day, lst in geo["date_ticks"]:
        a = math.radians(lst * 15)
        length = 6.5 if day == 1 else 3.5 if day % 5 == 0 else 1.8
        p = [(-s * r * math.sin(a), -r * math.cos(a)) for r in (r0, r0 + length)]
        ax.plot([cx + p[0][0], cx + p[1][0]], [cy + p[0][1], cy + p[1][1]], color=_INK,
                linewidth=0.5 if day == 1 else 0.3)
        if day % 5 == 0 and day < 31:
            q = (-s * (r0 + 5.0) * math.sin(a), -(r0 + 5.0) * math.cos(a))
            ax.text(cx + q[0], cy + q[1], str(day), fontsize=3.6, ha="center", va="center",
                    rotation=math.degrees(-s * a) + 180)
        if day == 15:
            q = (-s * (r0 + 10.0) * math.sin(a), -(r0 + 10.0) * math.cos(a))
            ax.text(cx + q[0], cy + q[1], t(f"workshop.month_{month}"), fontsize=6.2, ha="center",
                    va="center", rotation=math.degrees(-s * a) + 180, fontweight=600)
    _cut(ax, cx + r1 * np.cos(np.linspace(0, 2 * np.pi, 721)), cy + r1 * np.sin(np.linspace(0, 2 * np.pi, 721)))
    _circle(ax, cx, cy, 1.0, linewidth=0.6)
    ax.text(cx, cy - r1 - 4, t("workshop.planisphere_disc_hint"), fontsize=6.5, ha="center", va="top", color=_GREY)

    # 2. the mask
    fig, ax = pages.new(t("workshop.planisphere_mask"))
    r_mask = r_edge + 5.5
    _cut(ax, cx + r_mask * np.cos(np.linspace(0, 2 * np.pi, 721)), cy + r_mask * np.sin(np.linspace(0, 2 * np.pi, 721)))
    hx, hy = geo["horizon"]
    _cut(ax, cx + hx, cy + hy)
    ax.fill(cx + hx, cy + hy, color="#f2f2f2", zorder=0)
    for alt, (x, y) in geo["almucantars"].items():
        ax.plot(cx + x, cy + y, color=_LIGHT, linewidth=0.4, linestyle=(0, (3, 2)))
    for az, x, y in geo["cardinals"]:
        key = ("n", "ne", "e", "se", "s", "sw", "w", "nw")[az // 45]
        ax.text(cx + x * 0.93, cy + y * 0.93, t(f"skymap.cardinal_{key}"), fontsize=7 if az % 90 == 0 else 5,
                fontweight=600 if az % 90 == 0 else 400, ha="center", va="center")
    zx, zy = geo["zenith"]
    ax.plot(cx + zx, cy + zy, "+", color=_INK, markersize=6, markeredgewidth=0.6)
    for hour, ux, uy in geo["hours"]:
        p = [(ux * r, uy * r) for r in (r_mask - 3.2, r_mask)]
        ax.plot([cx + p[0][0], cx + p[1][0]], [cy + p[0][1], cy + p[1][1]], color=_INK, linewidth=0.6)
        a = math.atan2(ux, -uy)
        ax.text(cx + ux * (r_mask - 6), cy + uy * (r_mask - 6), str(hour), fontsize=6, ha="center", va="center",
                rotation=-math.degrees(a) + 180, fontweight=600 if hour % 6 == 0 else 400)
        for quarter in (0.25, 0.5, 0.75):
            b = math.radians(-(hour + quarter) * 15 * instruments.SIDEREAL_RATE)
            vx, vy = -s * math.sin(b), -math.cos(b)
            ax.plot([cx + vx * (r_mask - (1.8 if quarter == 0.5 else 1.0)), cx + vx * r_mask],
                    [cy + vy * (r_mask - (1.8 if quarter == 0.5 else 1.0)), cy + vy * r_mask],
                    color=_INK, linewidth=0.3)
    _circle(ax, cx, cy, 1.0, linewidth=0.6)
    top = cy + r_mask - 14
    for i, line in enumerate((place.describe(),
                              tf("workshop.planisphere_mask_time", zone=_offset_text(place.std_offset)),
                              t("workshop.planisphere_mask_summer") if place.has_dst else "")):
        ax.text(cx, top - 4 * i, line, fontsize=6, ha="center", va="top", color=_GREY)
    ax.text(cx, cy - r_mask - 4, t("workshop.planisphere_mask_hint"), fontsize=6.5, ha="center", va="top",
            color=_GREY)

    # 3. explanations
    pages.text_pages(t("workshop.planisphere"), _planisphere_texts(place, geo))
    return pages


def _planisphere_texts(place, geo):
    from engine import AstroEngine
    from star_catalog import CATALOG
    evening = place.utc(datetime(place.local(place.when).year, place.local(place.when).month,
                                 place.local(place.when).day, 22, 0))
    dst = place.dst_hours(evening)
    named = [c for c in CATALOG if c[6] and c[3] < 1.6]
    tc = AstroEngine.julian_century_j2000(evening)
    alts, azs = AstroEngine.stars_horizontal(tc, place.lat, place.lon, [c[1] for c in named], [c[2] for c in named])
    up = sorted(((float(a), float(z), c[6]) for c, a, z in zip(named, alts, azs) if a > 10), reverse=True)[:5]
    winds = ("n", "ne", "e", "se", "s", "sw", "w", "nw")
    stars = "; ".join(tf("workshop.star_at", name=name, alt=_num(alt), dir=t(f"skymap.cardinal_{winds[int(round(az / 45)) % 8]}"))
                      for alt, az, name in up) or t("workshop.none")
    local = place.local(evening)
    dial = 22 - dst
    return [
        (t("workshop.what_title"), [t("workshop.planisphere_what")]),
        (t("workshop.assembly_title"), [t("workshop.planisphere_assembly")]),
        (t("workshop.use_title"), [t("workshop.planisphere_use"), t("workshop.planisphere_use_2")]),
        (t("workshop.summer_title"), [t("workshop.planisphere_summer") if place.has_dst else t("workshop.no_summer")]),
        (t("workshop.example_title"), [tf("workshop.planisphere_example", date=local.strftime("%d/%m/%Y"),
                                          hour=_hm(dial), legal="22:00", stars=stars)]),
        (t("workshop.astro_title"), [tf("workshop.planisphere_astro", lat=_num(abs(place.lat), 1),
                                        edge=_num(abs(geo["dec_edge"]), 0), lon=_num(place.lon, 2),
                                        zone=_offset_text(place.std_offset),
                                        shift=_num(abs(place.lon / 15.0 - place.std_offset) * 60, 0),
                                        year=place.when.year),
                                     t("workshop.planisphere_astro_2")]),
    ]


# ── Sundials ──────────────────────────────────────────────────────────────────

def equation_of_time_table(year):
    """[(month, day, minutes)] on the 1st, 11th and 21st of each month: apparent − mean solar time."""
    from engine import AstroEngine
    rows = []
    for month in range(1, 13):
        for day in (1, 11, 21):
            rows.append((month, day, AstroEngine.equation_of_time(
                AstroEngine.julian_century_j2000(datetime(year, month, day, 12)))))
    return rows


def _corrections(place):
    """Lines of the table: what to add to the dial's reading to get the legal time."""
    lines = []
    table = equation_of_time_table(place.when.year)
    for month in range(1, 13):
        cells = []
        for m, day, eot in table:
            if m == month:
                minutes = -eot
                cells.append(f"{day:>2} : {'+' if minutes >= 0 else '−'}{abs(minutes):4.1f}".replace(".", t("workshop.decimal")))
        lines.append("|" + f"{t(f'workshop.month_{month}'):<10}" + "   ".join(cells))
    return "\n".join(lines)


def _sundial_example(place):
    """(local date, legal time text, dial reading text) at 15:00 legal on the example's day."""
    from engine import AstroEngine
    local_day = place.local(place.when)
    ut = place.utc(datetime(local_day.year, local_day.month, local_day.day, 15, 0))
    eot = AstroEngine.equation_of_time(AstroEngine.julian_century_j2000(ut))
    reading = instruments.dial_reading(15.0, place.dst_hours(ut), eot)
    return local_day.strftime("%d/%m/%Y"), "15:00", _hm(reading), eot, place.dst_hours(ut)


def _build_equatorial_dial(place, paper):
    width, height = PAPERS[paper]
    geo = instruments.equatorial_dial(place.lat, place.lon, place.std_offset)
    pages = _Pages(paper, f"Céleste — {t('workshop.equatorial_dial')} — {place.describe()}")
    fig, ax = pages.new(t("workshop.equatorial_faces"))
    r = 52.0
    for (cx, cy), face, mirror in (((width / 2, height - 79), "summer", 1.0), ((width / 2, 96), "winter", -1.0)):
        _cut(ax, cx + r * np.cos(np.linspace(0, 2 * np.pi, 721)), cy + r * np.sin(np.linspace(0, 2 * np.pi, 721)))
        _circle(ax, cx, cy, 2.2, linewidth=0.6)
        _circle(ax, cx, cy, r - 7, linewidth=0.3, color=_GREY)
        for hour, angle in geo["hour_angles"].items():
            if not geo[face][hour]:
                continue
            a = math.radians(angle)
            vx, vy = -mirror * math.sin(a), -math.cos(a)
            whole = hour == int(hour)
            ax.plot([cx + vx * (8 if whole else r - 12), cx + vx * (r - 7)],
                    [cy + vy * (8 if whole else r - 12), cy + vy * (r - 7)],
                    color=_INK, linewidth=0.6 if whole else 0.3)
            if whole:
                ax.text(cx + vx * (r - 3.5), cy + vy * (r - 3.5), str(int(hour)), fontsize=7, ha="center",
                        va="center", fontweight=600 if hour == 12 else 400)
        ax.text(cx, cy + 0.6 * r, t(f"workshop.equatorial_{face}"), fontsize=7.5, ha="center", fontweight=600)
        ax.text(cx, cy + 0.6 * r - 5, t(f"workshop.equatorial_{face}_dates"), fontsize=6, ha="center", color=_GREY)
        ax.text(cx, cy + r + 2.5, t("workshop.equatorial_top"), fontsize=6, ha="center", va="bottom", color=_GREY)
        ax.plot([cx - 4, cx + 4], [cy + r - 1.5, cy + r - 1.5], color=_INK, linewidth=1.2)
    # 2. the wedge of the stand
    fig, ax = pages.new(t("workshop.equatorial_stand"))
    tilt = math.radians(geo["tilt"])
    for k, x0 in enumerate((22.0, 22.0)):
        y0 = height - 112 - k * 112
        h = min(70.0, 120.0 * math.tan(tilt))           # the slanted edge about as long as the dial
        b = h / math.tan(tilt)
        xs = [x0, x0 + b, x0 + b, x0]
        ys = [y0, y0, y0 + h, y0]
        _cut(ax, xs, ys)
        ax.plot([x0, x0 + b], [y0 - 8, y0 - 8], color=_INK, linewidth=0.4, linestyle=(0, (2, 2)))
        _cut(ax, [x0, x0, x0 + b, x0 + b], [y0, y0 - 8, y0 - 8, y0])
        a = np.linspace(0, tilt, 30)
        ax.plot(x0 + 14 * np.cos(a), y0 + 14 * np.sin(a), color=_INK, linewidth=0.4)
        ax.text(x0 + 17, y0 + 3, f"{_num(geo['tilt'], 1)}°", fontsize=7)
        ax.text(x0 + b + 3, y0 + h / 2, t("workshop.equatorial_wedge"), fontsize=6.5, va="center", color=_GREY)
        ax.text(x0 + b / 2, y0 - 4, t("workshop.fold_glue"), fontsize=5.5, ha="center", va="center", color=_GREY)
    date, legal, reading, eot, dst = _sundial_example(place)
    pages.text_pages(t("workshop.equatorial_dial"), [
        (t("workshop.what_title"), [t("workshop.equatorial_what")]),
        (t("workshop.assembly_title"), [tf("workshop.equatorial_assembly", rod=_num(geo["rod"], 1),
                                           tilt=_num(geo["tilt"], 1))]),
        (t("workshop.orientation_title"), [t("workshop.sundial_orientation")]),
        (t("workshop.use_title"), [t("workshop.equatorial_use")]),
        (t("workshop.correction_title"), [t("workshop.sundial_corrections"), _corrections(place)]),
        (t("workshop.example_title"), [tf("workshop.sundial_example", date=date, legal=legal, reading=reading,
                                          eot=_num(eot, 1), dst=_num(dst, 0))]),
        (t("workshop.astro_title"), [tf("workshop.equatorial_astro", lat=_num(abs(place.lat), 1)),
                                     tf("workshop.sundial_longitude", lon=_num(place.lon, 2),
                                        zone=_offset_text(place.std_offset),
                                        shift=_num((place.lon / 15.0 - place.std_offset) * 60, 0))]),
    ])
    return pages


def _dial_size(place, reach):
    """Height (mm) of the nodus that puts the noon shadow of the winter solstice *reach* mm
    from the foot of the gnomon (the Sun kept 8° high at least, near the polar circles)."""
    phi = math.radians(abs(place.lat))
    noon = math.radians(max(90.0 - abs(place.lat) - instruments.OBLIQUITY, 8.0))
    return max(8.0, min(45.0, reach / (1.0 / math.tan(phi) + 1.0 / math.tan(noon))))


def _build_horizontal_dial(place, paper):
    width, height = PAPERS[paper]
    s = 1.0 if place.lat >= 0 else -1.0
    w, h_plate = 180.0, 220.0
    x0, y0 = (width - w) / 2, 34.0
    foot = (width / 2, y0 + (55.0 if s > 0 else h_plate - 55.0))
    reach = (y0 + h_plate - 12 - foot[1]) if s > 0 else (foot[1] - y0 - 12)
    nodus_h = _dial_size(place, reach)
    geo = instruments.horizontal_dial(place.lat, place.lon, place.std_offset, nodus_h)
    pages = _Pages(paper, f"Céleste — {t('workshop.horizontal_dial')} — {place.describe()}")
    fig, ax = pages.new(t("workshop.horizontal_plate"))
    _cut(ax, [x0, x0 + w, x0 + w, x0, x0], [y0, y0, y0 + h_plate, y0 + h_plate, y0])
    inner = (x0 + 8, x0 + w - 8, y0 + 8, y0 + h_plate - 8)
    ax.plot([inner[0], inner[1], inner[1], inner[0], inner[0]], [inner[2], inner[2], inner[3], inner[3], inner[2]],
            color=_GREY, linewidth=0.3)

    def to_edge(dx, dy):
        """Distance from the foot to the inner frame along (dx, dy)."""
        ts = []
        for edge, d, origin in ((inner[0], dx, foot[0]), (inner[1], dx, foot[0]),
                                (inner[2], dy, foot[1]), (inner[3], dy, foot[1])):
            if abs(d) > 1e-9:
                k = (edge - origin) / d
                if k > 0:
                    ts.append(k)
        return min(ts)

    for hour, (dx, dy) in geo["hour_lines"].items():
        if not geo["hour_ranges"][hour]:
            continue
        k = to_edge(dx, dy)
        whole = hour == int(hour)
        start = min(10.0, k) if whole else k - 7
        ax.plot([foot[0] + dx * start, foot[0] + dx * k], [foot[1] + dy * start, foot[1] + dy * k],
                color=_INK, linewidth=0.6 if whole else 0.3)
        if whole:
            ax.text(foot[0] + dx * (k + 4), foot[1] + dy * (k + 4), str(int(hour)), fontsize=7.5, ha="center",
                    va="center", fontweight=600 if hour == 12 else 400)
    labels = {instruments.OBLIQUITY: "workshop.date_june", 0.0: "workshop.date_equinox",
              -instruments.OBLIQUITY: "workshop.date_december"}
    for dec, (x, y) in geo["date_lines"].items():
        px, py = foot[0] + x, foot[1] + y
        keep = (px > inner[0]) & (px < inner[1]) & (py > inner[2]) & (py < inner[3])
        px, py = np.where(keep, px, np.nan), np.where(keep, py, np.nan)
        main = dec in labels
        ax.plot(px, py, color=_GREY if main else _LIGHT, linewidth=0.5 if main else 0.3,
                linestyle="-" if main else (0, (2, 2)))
        if main and np.isfinite(px).any():
            i = int(np.nanargmax(np.where(np.isfinite(px), px, -np.inf)))
            ax.text(px[i] - 1, py[i] + 1.5, t(labels[dec]), fontsize=5, ha="right", color=_GREY)
    ax.plot(*foot, "o", color=_INK, markersize=3)
    ax.text(foot[0] + 3, foot[1] - 3 * s, t("workshop.horizontal_foot"), fontsize=6, va="center", color=_GREY)
    nodus_x, nodus_y = foot[0] + geo["nodus"][0], foot[1] + geo["nodus"][1]
    ax.plot([foot[0], nodus_x], [foot[1], nodus_y], color=_INK, linewidth=1.4)
    ax.text(nodus_x + 2, nodus_y, t("workshop.horizontal_gnomon_here"), fontsize=5.5, color=_GREY, va="center")
    north_y = y0 + h_plate + 13 if s > 0 else y0 - 13
    ax.annotate(t("skymap.cardinal_n"), (x0 + w - 6, north_y + 4 * s), xytext=(x0 + w - 6, north_y - 4 * s),
                ha="center", va="center", fontsize=8, fontweight=600,
                arrowprops={"arrowstyle": "->", "linewidth": 0.6})

    # 2. the gnomon
    fig, ax = pages.new(t("workshop.horizontal_gnomon"))
    phi = math.radians(abs(place.lat))
    base = geo["nodus"][1] * s
    gx, gy = 40.0, height - 140.0
    _cut(ax, [gx, gx + base, gx + base, gx], [gy, gy, gy + nodus_h, gy])
    _cut(ax, [gx, gx, gx + base, gx + base], [gy, gy - 10, gy - 10, gy])
    ax.plot([gx, gx + base], [gy, gy], color=_INK, linewidth=0.4, linestyle=(0, (2, 2)))
    a = np.linspace(0, phi, 30)
    ax.plot(gx + 12 * np.cos(a), gy + 12 * np.sin(a), color=_INK, linewidth=0.4)
    ax.text(gx + 15, gy + 2.5, f"{_num(abs(place.lat), 1)}°", fontsize=7)
    ax.plot(gx + base, gy + nodus_h, "o", color=_INK, markersize=2.5)
    ax.text(gx + base + 3, gy + nodus_h, t("workshop.horizontal_nodus"), fontsize=6.5, va="center")
    ax.text(gx - 2, gy - 3, t("workshop.horizontal_foot"), fontsize=6, ha="right", color=_GREY)
    ax.text(gx + base / 2, gy - 5, t("workshop.fold_glue"), fontsize=5.5, ha="center", va="center", color=_GREY)
    ax.text(gx, gy - 22, tf("workshop.horizontal_gnomon_sizes", height=_num(nodus_h, 1), base=_num(base, 1),
                            style=_num(geo["style_length"], 1)), fontsize=7, va="top")
    date, legal, reading, eot, dst = _sundial_example(place)
    pages.text_pages(t("workshop.horizontal_dial"), [
        (t("workshop.what_title"), [t("workshop.horizontal_what")]),
        (t("workshop.assembly_title"), [t("workshop.horizontal_assembly")]),
        (t("workshop.orientation_title"), [t("workshop.sundial_orientation"), t("workshop.horizontal_level")]),
        (t("workshop.use_title"), [t("workshop.horizontal_use")]),
        (t("workshop.correction_title"), [t("workshop.sundial_corrections"), _corrections(place)]),
        (t("workshop.example_title"), [tf("workshop.sundial_example", date=date, legal=legal, reading=reading,
                                          eot=_num(eot, 1), dst=_num(dst, 0))]),
        (t("workshop.astro_title"), [tf("workshop.horizontal_astro", lat=_num(abs(place.lat), 1)),
                                     tf("workshop.sundial_longitude", lon=_num(place.lon, 2),
                                        zone=_offset_text(place.std_offset),
                                        shift=_num((place.lon / 15.0 - place.std_offset) * 60, 0))]),
    ])
    return pages


# ── Stars of the date ─────────────────────────────────────────────────────────

def stars_of_date(stars, year):
    """[(name, RA h, Dec °, mag)] brought from J2000 to the middle of *year* (precession,
    nutation: Skyfield), for instruments whose scales are set by the stars."""
    from skyfield.api import Star
    from engine import _sky
    sky = _sky()
    ra = np.array([s[1] for s in stars])
    dec = np.array([s[2] for s in stars])
    when = sky["ts"].utc(year, 7, 1)
    r, d, _ = sky["earth"].at(when).observe(Star(ra_hours=ra, dec_degrees=dec)).apparent().radec(epoch="date")
    return [(s[0], float(a), float(b), s[3]) for s, a, b in zip(stars, np.atleast_1d(r.hours),
                                                                 np.atleast_1d(d.degrees))]


_SIGNS = 12
_ASTROLABE_STARS = ("Aldebaran", "Capella", "Rigel", "Betelgeuse", "Sirius", "Procyon", "Pollux", "Castor",
                    "Regulus", "Denebola", "Dubhe", "Alkaid", "Spica", "Arcturus", "Alphecca", "Antares",
                    "Rasalhague", "Vega", "Altair", "Deneb", "Enif", "Markab", "Alpheratz", "Mirach",
                    "Hamal", "Algol", "Mirfak", "Fomalhaut", "Achernar", "Canopus", "Acrux", "Hadar",
                    "Rigil Kentaurus", "Shaula", "Peacock", "Alnilam", "Adhara", "Alphard", "Kochab",
                    "Polaris", "Diphda", "Menkar", "Bellatrix", "Elnath")


def _astrolabe_stars(year, south):
    from star_catalog import CATALOG
    chosen = [(c[6], c[1], c[2], c[3]) for c in CATALOG if c[6] in _ASTROLABE_STARS]
    return stars_of_date(chosen, year)


def _ticks(ax, cx, cy, angles_deg, r0, r1, **style):
    """Radial ticks between radii r0 and r1 at position angles (counter-clockwise from the right)."""
    a = np.radians(np.asarray(angles_deg, dtype=float))
    xs = np.stack([cx + r0 * np.cos(a), cx + r1 * np.cos(a), np.full_like(a, np.nan)], axis=1).ravel()
    ys = np.stack([cy + r0 * np.sin(a), cy + r1 * np.sin(a), np.full_like(a, np.nan)], axis=1).ravel()
    ax.plot(xs, ys, **{"color": _INK, "linewidth": 0.3, **style})


def _radial_text(ax, cx, cy, angle_deg, r, text, size, upright=True, **style):
    """Text at position angle *angle_deg* (counter-clockwise from the right), along the circle."""
    a = math.radians(angle_deg)
    rotation = angle_deg - 90.0
    if upright and 90.0 < angle_deg % 360.0 < 270.0:
        rotation += 180.0
    ax.text(cx + r * math.cos(a), cy + r * math.sin(a), text, fontsize=size, ha="center", va="center",
            rotation=rotation, rotation_mode="anchor", **style)


def _ring_tab(ax, cx, cy, r_out, half=8.0):
    """The edge of the mater with its throne: a tab with the hole of the ring, at the top."""
    side = math.acos(half / r_out)
    edge = np.linspace(math.pi - side, 2 * math.pi + side, 1200)
    top = cy + r_out + 3.0
    cap = np.linspace(0, math.pi, 90)
    xs = np.concatenate([cx + r_out * np.cos(edge), [cx + half], cx + half * np.cos(cap), [cx - half],
                         [cx + r_out * math.cos(math.pi - side)]])
    ys = np.concatenate([cy + r_out * np.sin(edge), [top], top + half * np.sin(cap), [top],
                         [cy + r_out * math.sin(math.pi - side)]])
    _cut(ax, xs, ys)
    _circle(ax, cx, top + 2.5, 2.5, linewidth=0.8)


def _astrolabe_geometry(place, size):
    s = 1.0 if place.lat >= 0 else -1.0
    plate = instruments.plate(place.lat, almucantar_step=5, azimuth_step=15)
    scale = size / 2.0 / plate["limit"]
    return s, plate, scale


def _build_astrolabe(place, paper, options):
    width, height = PAPERS[paper]
    size = float(options.get("size", 150))
    south = place.lat < 0
    s, plate, k = _astrolabe_geometry(place, size)
    r_plate = size / 2.0
    r_hours, r_out = r_plate + 7.0, r_plate + 14.0
    cx, cy = width / 2, (height - 24) / 2 + 4
    pages = _Pages(paper, f"Céleste — {t('workshop.astrolabe')} — {place.describe()}")

    # 1. the mater's face: limb and plate
    fig, ax = pages.new(t("workshop.astrolabe_front"))
    _ring_tab(ax, cx, cy, r_out)
    _circle(ax, cx, cy, r_plate, linewidth=0.7)
    _circle(ax, cx, cy, r_hours, linewidth=0.4)
    # degree scale (inner ring), counted clockwise from the top in the north
    for d in range(360):
        pa = 90.0 - s * d
        length = 3.2 if d % 10 == 0 else 2.2 if d % 5 == 0 else 1.2
        _ticks(ax, cx, cy, [pa], r_plate, r_plate + length, linewidth=0.35 if d % 5 == 0 else 0.25)
        if d % 30 == 0:
            _radial_text(ax, cx, cy, pa, r_plate + 5.0, str(d), 4.6, color=_GREY)
    # hour scale (outer ring): apparent solar time, noon at the top
    for q in range(24 * 12):
        hours = q / 12.0
        ux, uy = instruments.limb_angle(hours, south)
        pa = math.degrees(math.atan2(uy, ux))
        length = 2.6 if q % 12 == 0 else 1.6 if q % 3 == 0 else 0.9
        _ticks(ax, cx, cy, [pa], r_hours, r_hours + length, linewidth=0.45 if q % 12 == 0 else 0.25)
        if q % 12 == 0:
            _radial_text(ax, cx, cy, pa, r_hours + 4.6, str(q // 12), 6.5, fontweight=600 if q % 72 == 0 else 400)
    # the plate
    def line(xy, **style):
        ax.plot(cx + np.asarray(xy[0]) * k, cy + np.asarray(xy[1]) * k, **{"color": _INK, **style})

    for r in plate["tropics"][:2]:
        _circle(ax, cx, cy, r * k, linewidth=0.35)
    ax.plot([cx, cx], [cy - r_plate, cy + r_plate], color=_INK, linewidth=0.35)
    ax.plot([cx - r_plate, cx + r_plate], [cy, cy], color=_LIGHT, linewidth=0.3)
    for kk, xy in plate["unequal_hours"].items():
        line(xy, linewidth=0.3, color=_GREY, linestyle=(0, (2, 1.2)))
        x, y = np.asarray(xy[0]) * k, np.asarray(xy[1]) * k
        ok = np.where(np.isfinite(x))[0]
        if len(ok):
            i = ok[len(ok) // 2]
            ax.text(cx + x[i], cy + y[i], str(12 - kk), fontsize=4.2, color=_GREY, ha="center", va="center",
                    bbox={"facecolor": "white", "edgecolor": "none", "pad": 0.2})
    line(plate["twilight"], linewidth=0.45, linestyle=(0, (4, 2)), color=_GREY)
    for alt, xy in plate["almucantars"].items():
        line(xy, linewidth=0.45 if alt % 10 == 0 else 0.22)
    for az, xy in plate["azimuths"].items():
        line(xy, linewidth=0.25)
    line(plate["horizon"], linewidth=1.0)
    # labels: altitudes along the meridian (towards the equator), azimuths by the horizon
    for alt in range(10, 90, 10):
        dec, h = instruments.equatorial(float(alt), 180.0, abs(place.lat))
        x, y = instruments.project(dec, h)
        if math.hypot(float(x), float(y)) < plate["limit"]:
            ax.text(cx + 1.0, cy + float(y) * k + 0.6, str(alt), fontsize=4.2, color=_INK, va="bottom")
    for az in range(0, 360, 30):
        dec, h = instruments.equatorial(5.0, float(az), abs(place.lat))
        x, y = instruments.project(dec, h)
        x = float(x) * (-1 if south else 1)
        if math.hypot(x, float(y)) < plate["limit"] * 0.97:
            label = (az if not south else (180 - az) % 360)
            ax.text(cx + x * k, cy + float(y) * k, f"{label}°", fontsize=3.8, color=_GREY, ha="center",
                    va="center", bbox={"facecolor": "white", "edgecolor": "none", "pad": 0.1})
    ex, ey = plate["east"]
    wx, wy = plate["west"]
    ax.text(cx + ex * k - 1.5 * (1 if not south else -1), cy + ey * k + 1.5, t("workshop.astrolabe_east"),
            fontsize=5.5, ha="right" if not south else "left", fontweight=600)
    ax.text(cx + wx * k + 1.5 * (1 if not south else -1), cy + wy * k + 1.5, t("workshop.astrolabe_west"),
            fontsize=5.5, ha="left" if not south else "right", fontweight=600)
    zx, zy = plate["zenith"]
    ax.plot(cx + zx * k, cy + zy * k, "+", color=_INK, markersize=5, markeredgewidth=0.6)
    _circle(ax, cx, cy, 1.2, linewidth=0.6)
    ax.text(cx, cy - r_plate * 0.86, tf("workshop.astrolabe_plate_for", lat=_num(abs(place.lat), 1),
                                         ns=t("skymap.cardinal_n") if not south else t("skymap.cardinal_s")),
            fontsize=5.2, ha="center", color=_GREY, bbox={"facecolor": "white", "edgecolor": "none", "pad": 0.4})
    ax.text(cx, cy - r_out - 5, t("workshop.astrolabe_front_hint"), fontsize=6.3, ha="center", va="top",
            color=_GREY)

    # 2. the rete and the rule, to print on a transparent sheet
    fig, ax = pages.new(t("workshop.astrolabe_rete"))
    rcx, rcy = cx, height - 30 - r_plate
    rete = instruments.rete([(n, ra, dec) for n, ra, dec, _m in _astrolabe_stars(place.when.year, south)], south)
    _circle(ax, rcx, rcy, r_plate, linewidth=0.8)
    _circle(ax, rcx, rcy, r_plate - 3.0, linewidth=0.3)
    (ecx, ecy), er = rete["centre"], rete["radius"]
    band = 6.0
    _circle(ax, rcx + ecx * k, rcy + ecy * k, er * k, linewidth=0.7)
    _circle(ax, rcx + ecx * k, rcy + ecy * k, er * k - band, linewidth=0.5)
    for lon, x, y in rete["ecliptic_ticks"]:
        pa = math.degrees(math.atan2(y - ecy, x - ecx))
        length = band if lon % 30 == 0 else 2.6 if lon % 10 == 0 else 1.8 if lon % 5 == 0 else 1.0
        _ticks(ax, rcx + ecx * k, rcy + ecy * k, [pa], er * k - length, er * k,
               linewidth=0.5 if lon % 30 == 0 else 0.25)
        if lon % 30 == 15:
            _radial_text(ax, rcx + ecx * k, rcy + ecy * k, pa, er * k - 4.0,
                         t(f"workshop.sign_{lon // 30}"), 4.4, fontweight=600)
    for name, x, y in rete["stars"]:
        px, py = rcx + x * k, rcy + y * k
        d = math.hypot(px - rcx, py - rcy) or 1.0
        ux, uy = (px - rcx) / d, (py - rcy) / d
        tri = [(px, py), (px + ux * 3.2 - uy * 1.0, py + uy * 3.2 + ux * 1.0),
               (px + ux * 3.2 + uy * 1.0, py + uy * 3.2 - ux * 1.0)]
        ax.fill([p[0] for p in tri], [p[1] for p in tri], color=_INK, linewidth=0)
        ax.text(px + ux * 4.0, py + uy * 4.0, name, fontsize=4.3, ha="left" if ux >= 0 else "right",
                va="center")
    _circle(ax, rcx, rcy, 1.2, linewidth=0.6)
    ax.plot([rcx, rcx], [rcy + r_plate - 3, rcy + r_plate], color=_INK, linewidth=0.8)
    # the rule: a strip whose middle line passes through the centre, with the declination scale
    ry = 52.0
    half = r_out
    ax.plot([cx - half, cx + half, cx + half, cx - half, cx - half], [ry - 5, ry - 5, ry + 5, ry + 5, ry - 5],
            color=_INK, linewidth=0.9)
    ax.plot([cx - half + 3, cx + half - 3], [ry, ry], color=_INK, linewidth=0.4)
    _circle(ax, cx, ry, 1.2, linewidth=0.6)
    for dec in range(-20, 25, 5):
        r = instruments.projection_radius(dec, south) * k
        for sign in (-1, 1):
            ax.plot([cx + sign * r, cx + sign * r], [ry, ry + (2.4 if dec % 10 == 0 else 1.4)], color=_INK,
                    linewidth=0.3)
        if dec % 10 == 0:
            ax.text(cx + r, ry + 3.2, f"{dec:+d}°".replace("+0", "0"), fontsize=4, ha="center", va="bottom")
    for dec in (instruments.OBLIQUITY, -instruments.OBLIQUITY):
        r = instruments.projection_radius(dec, south) * k
        ax.plot([cx + r, cx + r], [ry - 2.4, ry], color=_INK, linewidth=0.5)
        ax.plot([cx - r, cx - r], [ry - 2.4, ry], color=_INK, linewidth=0.5)
    ax.text(cx, ry - 7.5, t("workshop.astrolabe_rule"), fontsize=6.5, ha="center", va="top", color=_GREY)
    ax.text(cx, rcy - r_plate - 4, t("workshop.astrolabe_rete_hint"), fontsize=6.3, ha="center", va="top",
            color=_GREY)

    # 3. the back of the mater
    fig, ax = pages.new(t("workshop.astrolabe_back"))
    _ring_tab(ax, cx, cy, r_out)
    r_alt, r_zod, r_cal = r_out - 7.0, r_out - 14.0, r_out - 25.0
    for r in (r_alt, r_zod, r_cal):
        _circle(ax, cx, cy, r, linewidth=0.4)
    for d in range(360):
        alt = d % 90 if (d // 90) % 2 == 0 else 90 - d % 90
        length = 3.0 if d % 10 == 0 else 2.0 if d % 5 == 0 else 1.0
        _ticks(ax, cx, cy, [d], r_out - length, r_out, linewidth=0.35 if d % 5 == 0 else 0.22)
        if d % 10 == 0 and alt not in (0,):
            _radial_text(ax, cx, cy, d, r_alt + 2.2, str(alt), 4.2)
    for pa in (0, 180):
        _radial_text(ax, cx, cy, pa, r_alt + 2.2, "0", 4.2)
    for lon in range(360):
        pa = float(instruments.back_angle(lon))
        length = 7.0 if lon % 30 == 0 else 2.5 if lon % 10 == 0 else 1.8 if lon % 5 == 0 else 1.0
        _ticks(ax, cx, cy, [pa], r_alt - length, r_alt, linewidth=0.45 if lon % 30 == 0 else 0.22)
        if lon % 30 == 15:
            _radial_text(ax, cx, cy, pa, r_zod + 2.4, t(f"workshop.sign_{lon // 30}"), 4.6, fontweight=600)
        elif lon % 10 == 0 and lon % 30:
            _radial_text(ax, cx, cy, pa, r_alt - 4.0, str(lon % 30), 3.6, color=_GREY)
    for month, day, lon in instruments.solar_longitudes(place.when.year):
        pa = float(instruments.back_angle(lon))
        length = 11.0 if day == 1 else 3.2 if day % 10 == 0 else 2.2 if day % 5 == 0 else 1.2
        _ticks(ax, cx, cy, [pa], r_zod - length, r_zod, linewidth=0.45 if day == 1 else 0.22)
        if day in (10, 20):
            _radial_text(ax, cx, cy, pa, r_zod - 4.6, str(day), 3.6, color=_GREY)
        if day == 15:
            _radial_text(ax, cx, cy, pa, r_cal + 3.0, t(f"workshop.month_{month}"), 5.0, fontweight=600)
    # the shadow square, in the lower half
    a = (r_cal - 3.0) / math.sqrt(2.0)
    ax.plot([cx - a, cx + a, cx + a, cx - a, cx - a], [cy, cy, cy - a, cy - a, cy], color=_INK, linewidth=0.5)
    ax.plot([cx, cx], [cy, cy - a], color=_INK, linewidth=0.5)
    for i in range(1, 12):
        f = a * i / 12.0
        for sign in (-1, 1):
            ax.plot([cx + sign * a - sign * 1.6, cx + sign * a], [cy - f, cy - f], color=_INK, linewidth=0.3)
            ax.plot([cx + sign * f, cx + sign * f], [cy - a, cy - a + 1.6], color=_INK, linewidth=0.3)
            if i % 3 == 0:
                ax.text(cx + sign * (a - 3.2), cy - f, str(i), fontsize=3.8, ha="center", va="center")
                ax.text(cx + sign * f, cy - a + 3.0, str(i), fontsize=3.8, ha="center", va="center")
    for sign in (-1, 1):                     # versa on the vertical sides, recta on the bottom one
        ax.text(cx + sign * (a - 8.0), cy - a / 2, t("workshop.astrolabe_umbra_versa"), fontsize=4.4,
                ha="center", va="center", color=_GREY, rotation=90)
        ax.text(cx + sign * a / 2, cy - a + 7.0, t("workshop.astrolabe_umbra_recta"), fontsize=4.4,
                ha="center", va="center", color=_GREY)
    ax.plot([cx - r_cal, cx + r_cal], [cy, cy], color=_INK, linewidth=0.35)
    ax.plot([cx, cx], [cy, cy + r_cal], color=_INK, linewidth=0.35)
    _circle(ax, cx, cy, 1.2, linewidth=0.6)
    ax.text(cx, cy + r_cal * 0.45, place.describe(), fontsize=5.5, ha="center", color=_GREY)
    ax.text(cx, cy + r_cal * 0.45 - 4, tf("workshop.astrolabe_calendar_year", year=place.when.year), fontsize=5,
            ha="center", color=_GREY)
    ax.text(cx, cy - r_out - 5, t("workshop.astrolabe_back_hint"), fontsize=6.3, ha="center", va="top",
            color=_GREY)

    # 4. the alidade
    fig, ax = pages.new(t("workshop.astrolabe_alidade"))
    ax_, half, w, vane = width / 2 - 30, r_out - 1.0, 12.0, 16.0          # upright, along the page
    ay = (height + 10) / 2
    _cut(ax, [ax_ - w / 2, ax_ + w / 2, ax_ + w / 2, ax_ - w / 2, ax_ - w / 2],
         [ay - half, ay - half, ay + half, ay + half, ay - half])
    for sign in (-1, 1):
        y0 = ay + sign * half
        _cut(ax, [ax_ - w / 2, ax_ - w / 2, ax_ + w / 2, ax_ + w / 2], [y0, y0 + sign * vane, y0 + sign * vane, y0])
        ax.plot([ax_ - w / 2, ax_ + w / 2], [y0, y0], color=_INK, linewidth=0.5, linestyle=(0, (2, 1.5)))
        _circle(ax, ax_, y0 + sign * vane * 0.55, 0.6, linewidth=0.6)
        ax.text(ax_ + w / 2 + 2, y0 + sign * vane * 0.55, t("workshop.astrolabe_vane"), fontsize=5.5, va="center")
    ax.plot([ax_, ax_], [ay - half + 4, ay + half - 4], color=_INK, linewidth=0.4)
    _circle(ax, ax_, ay, 1.2, linewidth=0.6)
    hint = textwrap.wrap(t("workshop.astrolabe_alidade_hint"), 38)
    for i, line in enumerate(hint):
        ax.text(ax_ + w / 2 + 12, ay + 6 - 4.2 * i, line, fontsize=6.5, va="top", color=_GREY)

    pages.text_pages(t("workshop.astrolabe"), _astrolabe_texts(place, plate, rete))
    return pages


def _astrolabe_texts(place, plate, rete):
    from engine import AstroEngine
    south = place.lat < 0
    day = place.local(place.when)
    eot_corr = lambda ut: AstroEngine.equation_of_time(AstroEngine.julian_century_j2000(ut))  # noqa: E731
    shift = place.std_offset * 60.0 - place.lon * 4.0             # minutes from local mean to zone time

    def apparent(ut):
        return (ut.hour + ut.minute / 60.0 + place.lon / 15.0 + eot_corr(ut) / 60.0) % 24.0

    sections = [
        (t("workshop.what_title"), [t("workshop.astrolabe_what")]),
        (t("workshop.assembly_title"), [t("workshop.astrolabe_assembly")]),
        (t("workshop.astrolabe_parts_title"), [t("workshop.astrolabe_parts")]),
        (t("workshop.astrolabe_measure_title"), [t("workshop.astrolabe_measure")]),
        (t("workshop.use_title"), [t("workshop.astrolabe_use"), t("workshop.astrolabe_use_2")]),
        (t("workshop.astrolabe_time_title"), [tf("workshop.astrolabe_time", shift=_num(shift, 0),
                                                   zone=_offset_text(place.std_offset)), _corrections(place)]),
    ]
    # example by day: the Sun at 10:00 legal time (else noon)
    for hour in (10, 12, 13):
        ut = place.utc(datetime(day.year, day.month, day.day, hour, 0))
        tc = AstroEngine.julian_century_j2000(ut)
        alt, az = AstroEngine.horizontal(tc, place.lat, place.lon, "sun")
        if float(alt) > 8:
            break
    lon_sun, _d = AstroEngine.sun_position(tc)
    sign = int(float(lon_sun) // 30)
    side = t("workshop.astrolabe_side_east") if float(az) < 180 else t("workshop.astrolabe_side_west")
    reading = apparent(ut)
    sections.append((t("workshop.example_title"), [
        tf("workshop.astrolabe_example_day", date=day.strftime("%d/%m/%Y"), legal=f"{hour:02d}:00",
           alt=_num(float(alt), 0), side=side, lon=_num(float(lon_sun) % 30, 0),
           sign=t(f"workshop.sign_{sign}"), reading=_hm(reading), eot=_num(eot_corr(ut), 1),
           dst=_num(place.dst_hours(ut), 0), shift=_num(shift, 0))]))
    # example by night: a bright star of the rete at 22:00 legal time
    ut = place.utc(datetime(day.year, day.month, day.day, 22, 0))
    tc = AstroEngine.julian_century_j2000(ut)
    names = [n for n, _x, _y in rete["stars"]]
    from star_catalog import CATALOG
    cat = {c[6]: c for c in CATALOG if c[6] in names}
    best = None
    if cat:
        keys = list(cat)
        alts, azs = AstroEngine.stars_horizontal(tc, place.lat, place.lon, [cat[n][1] for n in keys],
                                                 [cat[n][2] for n in keys])
        for name, a, z in zip(keys, alts, azs):
            off_meridian = min(abs(float(z) - 180.0), abs(float(z)), abs(float(z) - 360.0))
            if 20 < float(a) < 70 and off_meridian > 35:
                if best is None or cat[name][3] < cat[best[0]][3]:
                    best = (name, float(a), float(z))
    if best:
        name, a, z = best
        sections.append(("", [tf("workshop.astrolabe_example_night", date=day.strftime("%d/%m/%Y"), star=name,
                                 alt=_num(a, 0),
                                 side=t("workshop.astrolabe_side_east") if z < 180 else
                                 t("workshop.astrolabe_side_west"),
                                 reading=_hm(apparent(ut)), legal="22:00")]))
    sections.append((t("workshop.astro_title"), [
        tf("workshop.astrolabe_astro", lat=_num(abs(place.lat), 1)), t("workshop.astrolabe_astro_2")]))
    del south
    return sections


# ── Nocturnal ─────────────────────────────────────────────────────────────────

_POINTERS_NORTH = (("great_bear", "Dubhe"), ("little_bear", "Kochab"))
_POINTERS_SOUTH = (("cross", "Acrux"),)


def _nocturnal_pointers(place):
    from star_catalog import CATALOG
    pairs = _POINTERS_NORTH if place.lat >= 0 else _POINTERS_SOUTH
    by_name = {c[6]: c for c in CATALOG if c[6]}
    stars = stars_of_date([(n, by_name[n][1], by_name[n][2], by_name[n][3]) for _k, n in pairs], place.when.year)
    return {k: (name, ra, dec) for (k, _n), (name, ra, dec, _m) in zip(pairs, stars)}


def _build_nocturnal(place, paper, options):
    width, height = PAPERS[paper]
    pointers = _nocturnal_pointers(place)
    geo = instruments.nocturnal(place.lat, place.lon, place.std_offset, place.when.year,
                                {k: v[1] for k, v in pointers.items()})
    sense = geo["sense"]
    pages = _Pages(paper, f"Céleste — {t('workshop.nocturnal')} — {place.describe()}")

    def pa(angle):                                    # angle from the top, in the instrument's sense
        return 90.0 + sense * angle

    # 1. the date disc with its handle
    fig, ax = pages.new(t("workshop.nocturnal_dates"))
    cx, cy, r_out, r_in = width / 2, height / 2 + 30, 66.0, 50.0
    b = np.linspace(math.radians(-80), math.radians(260), 900)
    xs = np.concatenate([cx + r_out * np.cos(b), [cx - 12, cx - 12, cx + 12, cx + 12]])
    ys = np.concatenate([cy + r_out * np.sin(b), [cy - r_out * 0.98, cy - r_out - 55, cy - r_out - 55,
                                                   cy - r_out * 0.98]])
    _cut(ax, xs, ys)
    _circle(ax, cx, cy, r_in, linewidth=0.5)
    _circle(ax, cx, cy, r_in + 9, linewidth=0.3)
    for month, day, angle in geo["date_ticks"]:
        length = 9.0 if day == 1 else 4.0 if day % 5 == 0 else 2.2
        _ticks(ax, cx, cy, [pa(angle)], r_in, r_in + length, linewidth=0.45 if day == 1 else 0.25)
        if day in (10, 20):
            _radial_text(ax, cx, cy, pa(angle), r_in + 5.6, str(day), 3.8, color=_GREY)
        if day == 15:
            _radial_text(ax, cx, cy, pa(angle), r_in + 12.0, t(f"workshop.month_{month}"), 6.0, fontweight=600)
    _circle(ax, cx, cy, 2.5, linewidth=0.8)
    ax.text(cx, cy - r_out - 30, t("workshop.nocturnal_handle"), fontsize=6, ha="center", rotation=90,
            color=_GREY)
    ax.text(cx, cy + r_out + 3, t("workshop.nocturnal_top"), fontsize=6, ha="center", va="bottom", color=_GREY)
    ax.text(cx, 30, t("workshop.nocturnal_dates_hint"), fontsize=6.3, ha="center", va="bottom", color=_GREY)

    # 2. the hour disc with its teeth, and the arm
    fig, ax = pages.new(t("workshop.nocturnal_hours"))
    cx, cy, r = width / 2, height - 80, 46.0
    tooth_angles = list(geo["teeth"].items())
    edge = np.linspace(0, 2 * np.pi, 1441)
    radius = np.full_like(edge, r)
    for _key, angle in tooth_angles:
        centre = math.radians(pa(angle))
        dist = np.angle(np.exp(1j * (edge - centre)))
        radius = np.maximum(radius, np.where(np.abs(dist) < math.radians(4.0),
                                             r + 9.0 * (1 - np.abs(dist) / math.radians(4.0)), r))
    _cut(ax, cx + radius * np.cos(edge), cy + radius * np.sin(edge))
    for key, angle in tooth_angles:
        _radial_text(ax, cx, cy, pa(angle), r - 3.5, t(f"workshop.nocturnal_tooth_{key}"), 4.6, fontweight=600)
    for hour, angle in geo["hour_ticks"]:
        whole = hour == int(hour)
        _ticks(ax, cx, cy, [pa(angle)], r - (6.0 if whole else 2.2), r - (0.0 if whole else 0.0),
               linewidth=0.5 if whole else 0.25)
        if whole:
            _radial_text(ax, cx, cy, pa(angle), r - 10.0, str(int(hour)), 6.0 if int(hour) % 6 == 0 else 5.0,
                         fontweight=600 if int(hour) % 6 == 0 else 400)
    _circle(ax, cx, cy, 2.5, linewidth=0.8)
    ax.text(cx, cy - 16, tf("workshop.nocturnal_hours_zone", zone=_offset_text(place.std_offset)), fontsize=5.2,
            ha="center", color=_GREY)
    # the arm
    ay, length, w = 70.0, 115.0, 10.0
    x0 = cx - 15
    xs = [x0 - 8, x0 + length - 12, x0 + length, x0 + length - 12, x0 - 8, x0 - 8]
    ys = [ay - w / 2, ay - w / 2, ay, ay + w / 2, ay + w / 2, ay - w / 2]
    _cut(ax, xs, ys)
    ax.plot([x0, x0 + length], [ay, ay], color=_INK, linewidth=0.4)
    _circle(ax, x0, ay, 2.5, linewidth=0.8)
    ax.text(x0 + length / 2, ay + w / 2 + 2, t("workshop.nocturnal_arm"), fontsize=6, ha="center", va="bottom",
            color=_GREY)
    ax.text(cx, 30, t("workshop.nocturnal_hours_hint"), fontsize=6.3, ha="center", va="bottom", color=_GREY)

    pages.text_pages(t("workshop.nocturnal"), _nocturnal_texts(place, pointers, geo))
    return pages


def _nocturnal_texts(place, pointers, geo):
    from engine import AstroEngine, _sky
    day = place.local(place.when)
    ut = place.utc(datetime(day.year, day.month, day.day, 22, 0))
    key = next(iter(pointers))
    name, ra, _dec = pointers[key]
    lst = (float(_sky()["ts"].ut1_jd(AstroEngine.julian_day(ut)).gmst) + place.lon / 15.0) % 24.0
    h = ((lst - ra) * 15.0) % 360.0
    clock = (12.0 - h / 30.0 * geo["sense"]) % 12.0
    std = (22.0 - place.dst_hours(ut)) % 24.0
    north = place.lat >= 0
    return [
        (t("workshop.what_title"), [t("workshop.nocturnal_what" if north else "workshop.nocturnal_what_south")]),
        (t("workshop.assembly_title"), [t("workshop.nocturnal_assembly")]),
        (t("workshop.use_title"), [t("workshop.nocturnal_use" if north else "workshop.nocturnal_use_south")]),
        (t("workshop.summer_title"), [t("workshop.nocturnal_summer") if place.has_dst else t("workshop.no_summer")]),
        (t("workshop.example_title"), [tf("workshop.nocturnal_example", date=day.strftime("%d/%m/%Y"), legal="22:00",
                                          star=name, clock=str(int(round(clock)) % 12 or 12), hour=_hm(std))]),
        (t("workshop.astro_title"), [tf("workshop.nocturnal_astro", lon=_num(place.lon, 2),
                                        zone=_offset_text(place.std_offset), year=place.when.year),
                                     t("workshop.nocturnal_astro_2" if north else "workshop.nocturnal_astro_south")]),
    ]


_CACHE = {}


def _key(kind, place, paper, options):
    zone = getattr(place.zone, "key", str(place.zone))
    return (kind, place.name, round(place.lat, 5), round(place.lon, 5), zone, place.when.date(),
            place.when.hour, paper, tuple(sorted((options or {}).items())), t("workshop.title"))


def instrument_pages(kind, place, paper="a4", options=None):
    """The pages (matplotlib figures, in millimetres) of instrument *kind* (INSTRUMENTS);
    *options*: {"size": plate diameter in mm} for the astrolabe. The last ones are kept,
    so that the interface's preview turns pages without drawing them again."""
    key = _key(kind, place, paper, options)
    if key in _CACHE:
        return _CACHE[key]
    builders = {"planisphere": _build_planisphere, "equatorial_dial": _build_equatorial_dial,
                "horizontal_dial": _build_horizontal_dial}
    if kind in builders:
        pages = builders[kind](place, paper)
    else:
        pages = {"astrolabe": _build_astrolabe, "nocturnal": _build_nocturnal}[kind](place, paper, options or {})
    if len(_CACHE) >= 3:
        _CACHE.pop(next(iter(_CACHE)))
    _CACHE[key] = pages
    return pages


def print_instrument(kind, path, place, paper="a4", options=None):
    """Writes the PDF of instrument *kind* at true scale; returns the number of pages."""
    pages = instrument_pages(kind, place, paper, options)
    pages.save(path)
    return len(pages.figures)


def preview_png(kind, place, paper="a4", page=0, dpi=60, options=None):
    """PNG bytes of one page of the instrument, for the interface's preview."""
    import io
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    pages = instrument_pages(kind, place, paper, options)
    fig = pages.figures[min(page, len(pages.figures) - 1)]
    FigureCanvasAgg(fig)
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=dpi, facecolor="white")
    return buffer.getvalue(), len(pages.figures)
