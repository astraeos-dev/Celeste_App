"""
workshop.py — The Workshop: instruments to print, cut out and assemble
======================================================================
PDF files at true scale of instruments computed for the place:

- planisphere (star wheel): the star disc with its date ring, the mask with
  the window of the horizon and the hour ring;
- equatorial sundial: the summer and winter faces, the wedge of the stand;
- horizontal sundial: the dial with its hour lines and date lines, the
  triangular gnomon with its nodus;

each followed by pages of explanations: how to assemble it, how to use it, the
astronomy behind it, a worked example for the place and the date, and the
table of the equation of time for the sundials.

The geometry is in instruments.py; the texts in locales/ ("workshop"). No Qt:
the interface only chooses the instrument and where to save.
"""
import math
import textwrap
from datetime import datetime, timedelta, timezone

import numpy as np

import instruments
from i18n import t, tf

INSTRUMENTS = ("planisphere", "equatorial_dial", "horizontal_dial")
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
                        hanging = "    " if raw[:1].isdigit() and raw[1:3] == ". " else ""
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


def instrument_pages(kind, place, paper="a4"):
    """The pages (matplotlib figures, in millimetres) of instrument *kind* (INSTRUMENTS)."""
    build = {"planisphere": _build_planisphere, "equatorial_dial": _build_equatorial_dial,
             "horizontal_dial": _build_horizontal_dial}[kind]
    return build(place, paper)


def print_instrument(kind, path, place, paper="a4"):
    """Writes the PDF of instrument *kind* at true scale; returns the number of pages."""
    pages = instrument_pages(kind, place, paper)
    pages.save(path)
    return len(pages.figures)


def preview_png(kind, place, paper="a4", page=0, dpi=60):
    """PNG bytes of one page of the instrument, for the interface's preview."""
    import io
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    pages = instrument_pages(kind, place, paper)
    fig = pages.figures[min(page, len(pages.figures) - 1)]
    FigureCanvasAgg(fig)
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=dpi, facecolor="white")
    return buffer.getvalue(), len(pages.figures)
