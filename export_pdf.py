"""
export_pdf.py — Ephemeris PDF report — printable dot-matrix IBM/DOS style
=========================================================================
Generates an A4 report in Courier font (monospace), ASCII box-drawing
characters (+-|), white background — suitable for any printer.

Content:
  • Header   : title, UT date, local time, location, coordinates
  • SUN      : RA, Dec, Altitude, Azimuth, Equation of Time, Distance
  • MOON     : RA, Dec, Altitude, Azimuth, Phase, Illumination
  • EVENTS   : sunrise/sunset/twilights + moonrise/moonset
  • Footer   : signature, algorithms, timestamp

Usage:
    from export_pdf import generate_report_pdf, build_data_from_app
    data = build_data_from_app(app)          # from gui.py AstroApp instance
    path = generate_report_pdf(data)         # auto-named PDF
    path = generate_report_pdf(data, "/path/report.pdf")

Data dict structure:
    {
        'date'       : datetime   — UT calculation datetime
        'lat'        : float      — latitude (decimal degrees)
        'lon'        : float      — longitude (decimal degrees)
        'location'   : str        — place name
        'utc_offset' : int        — UTC offset hours
        'sun'        : {
            'ra': str, 'dec': str, 'alt': float, 'az': float,
            'eot': float, 'dist': str, 'status': str
        },
        'moon'       : {
            'ra': str, 'dec': str, 'alt': float, 'az': float,
            'illum': float, 'phase': str, 'status': str
        },
        'events'     : {
            'sun' : {rise, set, transit, dawn_civ, dusk_civ,
                     dawn_naut, dusk_naut, dawn_astro, dusk_astro},
            'moon': {rise, transit, set}
        },
    }

Dependencies: reportlab
"""

import os
from datetime import datetime, timedelta, timezone

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib import colors

# ===========================================================================
# PALETTE — white background, printable
# ===========================================================================

_BG         = colors.white
_FG_BLACK   = colors.black
_FG_NAVY    = colors.Color(0.00, 0.20, 0.60)
_FG_GRAY    = colors.Color(0.45, 0.45, 0.45)
_FG_LGRAY   = colors.Color(0.70, 0.70, 0.70)
_FG_DKGRAY  = colors.Color(0.25, 0.25, 0.25)

# ===========================================================================
# TYPOGRAPHY
# ===========================================================================

_FONT      = "Courier"
_FONT_BOLD = "Courier-Bold"
_FS        = 8.0
_FS_TITLE  = 9.0
_LH        = 3.90 * mm
_ML        = 12 * mm
_MT        = 14 * mm
_MB        = 12 * mm
_COLS      = 110 # do not change this value without adjusting the rest of the layout and fonts!

# ===========================================================================
# ASCII BOX PRIMITIVES
# ===========================================================================

_H = "-"; _V = "|"; _C = "+"


def _hline(w=_COLS):
    return _C + _H*(w-2) + _C


def _hline_t(title, w=_COLS):
    t = f"[ {title} ]"[:w-2]
    pl = (w-2-len(t))//2; pr = w-2-len(t)-pl
    return _C + _H*pl + t + _H*pr + _C


def _vrow(content, w=_COLS):
    return _V + content[:w-2].ljust(w-2) + _V


def _blank(w=_COLS):
    return _vrow("", w)


# ===========================================================================
# RENDERER
# ===========================================================================

class _PDF:
    """Low-level renderer: Y cursor, colors, auto page break."""

    def __init__(self, path):
        self.path = path
        self.c    = rl_canvas.Canvas(path, pagesize=A4)
        self.pw, self.ph = A4
        self.x0   = _ML
        self.ytop = self.ph - _MT
        self.ymin = _MB + _LH * 2
        self.y    = self.ytop
        self._bg()
        self.c.setFont(_FONT, _FS)
        self.cw = self.c.stringWidth("X", _FONT, _FS)

    def _bg(self):
        self.c.setFillColor(_BG)
        self.c.rect(0, 0, self.pw, self.ph, fill=1, stroke=0)

    def nl(self, n=1):
        self.y -= _LH * n
        if self.y < self.ymin:
            self.c.showPage(); self._bg()
            self.c.setFont(_FONT, _FS); self.y = self.ytop

    def line(self, text, color=_FG_LGRAY, bold=False):
        self.c.setFont(_FONT_BOLD if bold else _FONT, _FS)
        self.c.setFillColor(color)
        self.c.drawString(self.x0, self.y, text)
        self.nl()

    def center(self, text, color=_FG_BLACK, bold=False, fs=None):
        fs = fs or _FS
        self.c.setFont(_FONT_BOLD if bold else _FONT, fs)
        self.c.setFillColor(color)
        inner = _COLS - 14
        self.c.drawString(self.x0, self.y, _V + text[:inner].center(inner) + _V)
        self.nl()

    def blank(self):
        self.line(_blank())

    def drow(self, label, value, lw=30, cv=_FG_NAVY, bold_val=False):
        """Data row: label in dark gray, value in cv."""
        label = str(label)[:lw].ljust(lw); value = str(value)
        inner = _COLS - 2; pfx = f" {label}: "
        vw    = max(0, inner - len(pfx) - 1)
        value = value[:vw].ljust(vw)
        cx    = self.x0
        self.c.setFont(_FONT, _FS)
        self.c.setFillColor(_FG_LGRAY);  self.c.drawString(cx, self.y, _V);  cx += self.cw
        self.c.setFillColor(_FG_DKGRAY); self.c.drawString(cx, self.y, pfx); cx += self.cw*len(pfx)
        self.c.setFont(_FONT_BOLD if bold_val else _FONT, _FS)
        self.c.setFillColor(cv);         self.c.drawString(cx, self.y, value); cx += self.cw*vw
        self.c.setFont(_FONT, _FS)
        self.c.setFillColor(_FG_LGRAY);  self.c.drawString(cx, self.y, _V)
        self.nl()

    def trow(self, l1, v1, l2, v2, lw=16, vw=14, c1=_FG_NAVY, c2=_FG_NAVY,
             bold1=False, bold2=False):
        """Two-column data row."""
        l1=str(l1)[:lw].ljust(lw); v1=str(v1)[:vw].ljust(vw)
        l2=str(l2)[:lw].ljust(lw); v2=str(v2)[:vw].ljust(vw)
        half = (_COLS-2)//2
        seg1 = f" {l1}: "; seg2 = f"  {l2}: "
        gap  = max(0, half - len(seg1) - vw)
        cx   = self.x0
        self.c.setFont(_FONT, _FS)
        self.c.setFillColor(_FG_LGRAY);  self.c.drawString(cx, self.y, _V);        cx += self.cw
        self.c.setFillColor(_FG_DKGRAY); self.c.drawString(cx, self.y, seg1);      cx += self.cw*len(seg1)
        self.c.setFont(_FONT_BOLD if bold1 else _FONT, _FS)
        self.c.setFillColor(c1);         self.c.drawString(cx, self.y, v1);        cx += self.cw*vw
        self.c.setFont(_FONT, _FS)
        self.c.setFillColor(_BG);        self.c.drawString(cx, self.y, " "*gap);   cx += self.cw*gap
        self.c.setFillColor(_FG_DKGRAY); self.c.drawString(cx, self.y, seg2);      cx += self.cw*len(seg2)
        self.c.setFont(_FONT_BOLD if bold2 else _FONT, _FS)
        self.c.setFillColor(c2);         self.c.drawString(cx, self.y, v2);        cx += self.cw*vw
        self.c.setFont(_FONT, _FS)
        end_x = self.x0 + self.cw*(_COLS-1)
        fill  = max(0, int((end_x-cx)/self.cw))
        self.c.setFillColor(_BG);        self.c.drawString(cx, self.y, " "*fill);  cx += self.cw*fill
        self.c.setFillColor(_FG_LGRAY);  self.c.drawString(cx, self.y, _V)
        self.nl()

    def erow(self, label, value, cv=_FG_BLACK, bold_v=False, bold_l=False):
        """Event row."""
        lw = 34; label = str(label)[:lw].ljust(lw); value = str(value)
        cx = self.x0
        self.c.setFont(_FONT, _FS)
        self.c.setFillColor(_FG_LGRAY); self.c.drawString(cx, self.y, _V); cx += self.cw
        self.c.setFont(_FONT_BOLD if bold_l else _FONT, _FS)
        self.c.setFillColor(_FG_DKGRAY)
        lbl = f"  {label}  "
        self.c.drawString(cx, self.y, lbl); cx += self.cw*len(lbl)
        self.c.setFont(_FONT_BOLD if bold_v else _FONT, _FS)
        self.c.setFillColor(cv); self.c.drawString(cx, self.y, value); cx += self.cw*len(value)
        self.c.setFont(_FONT, _FS)
        end_x = self.x0 + self.cw*(_COLS-1)
        fill  = max(0, int((end_x-cx)/self.cw))
        self.c.setFillColor(_BG); self.c.drawString(cx, self.y, " "*fill); cx += self.cw*fill
        self.c.setFillColor(_FG_LGRAY); self.c.drawString(cx, self.y, _V)
        self.nl()

    def stitle(self, text):
        """Sub-section title row."""
        inner = _COLS-2; txt = f"  {text}".ljust(inner)
        cx = self.x0
        self.c.setFillColor(_FG_LGRAY); self.c.setFont(_FONT, _FS)
        self.c.drawString(cx, self.y, _V); cx += self.cw
        self.c.setFillColor(_FG_BLACK); self.c.setFont(_FONT_BOLD, _FS)
        self.c.drawString(cx, self.y, txt); cx += self.cw*inner
        self.c.setFillColor(_FG_LGRAY); self.c.setFont(_FONT, _FS)
        self.c.drawString(cx, self.y, _V)
        self.nl()

    def save(self):
        self.c.save()


# ===========================================================================
# MAIN GENERATOR
# ===========================================================================

def generate_report_pdf(data: dict, output_path: str = None) -> str:
    """
    Generates ephemeris report PDF (white background, Courier font, printable).

    Args:
        data (dict)         : Data dict (see module docstring).
        output_path (str)   : Target path. None → celeste_YYYYMMDD_HHMMSS.pdf

    Returns:
        str: Absolute path of generated PDF.
    """
    if output_path is None:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            f"celeste_{ts}.pdf")

    p          = _PDF(output_path)
    dte        = data['date']
    lat        = data['lat']
    lon        = data['lon']
    location   = data.get('location', '---')
    utc_off    = data.get('utc_offset', 0)
    sun        = data['sun']
    moon       = data['moon']
    evts_sun   = data['events'].get('sun',  {})
    evts_moon  = data['events'].get('moon', {})
    dte_loc    = dte + timedelta(hours=utc_off)
    off_str    = f"UTC{'+' if utc_off >= 0 else ''}{utc_off}"

    # ── HEADER ────────────────────────────────────────────────────────
    p.line(_hline())
    p.blank()
    p.center("C E L E S T E   --   A S T R O N O M I C A L   O B S E R V A T O R Y",
             color=_FG_BLACK, bold=True, fs=_FS_TITLE)
    p.center("EPHEMERIS REPORT  --  v3.3  --  VSOP87 + ELP2000-82B",
             color=_FG_DKGRAY)
    p.blank()
    p.line(_hline())
    p.nl(0.3)

    # ── SESSION ───────────────────────────────────────────────────────
    p.line(_hline_t("SESSION"))
    p.drow("Date (UT)",     dte.strftime("%A %d %B %Y").upper(), lw=28, cv=_FG_BLACK, bold_val=True)
    p.drow("Time (UT)",     dte.strftime("%H:%M:%S"),             lw=28, cv=_FG_BLACK, bold_val=True)
    p.drow("Local time",    f"{dte_loc.strftime('%H:%M:%S')}  ({off_str})", lw=28, cv=_FG_BLACK)
    p.drow("Location",      location,                              lw=28, cv=_FG_BLACK)
    p.drow("Latitude",      f"{abs(lat):08.4f}  {'N' if lat>=0 else 'S'}", lw=28, cv=_FG_NAVY)
    p.drow("Longitude",     f"{abs(lon):09.4f}  {'E' if lon>=0 else 'W'}", lw=28, cv=_FG_NAVY)
    p.line(_hline())
    p.nl(0.3)

    # ── SUN ───────────────────────────────────────────────────────────
    s_status = sun.get('status','---')
    p.line(_hline_t(f"SUN  [{s_status}]"))
    p.blank()
    p.drow("Right Ascension (RA)",  sun.get('ra','---'), cv=_FG_NAVY)
    p.drow("Declination     (Dec)", sun.get('dec','---'), cv=_FG_NAVY)
    p.blank()
    s_alt = sun.get('alt', 0)
    p.trow("Altitude",    f"{s_alt:+.2f} deg",    "Azimuth",  f"{sun.get('az',0):.2f} deg",
           c1=_FG_BLACK, c2=_FG_BLACK, bold1=(s_alt>0))
    p.trow("Eq. of Time", f"{sun.get('eot',0):+.1f} min", "Distance", sun.get('dist','1.0000 AU'),
           c1=_FG_DKGRAY, c2=_FG_DKGRAY)
    p.blank(); p.line(_hline()); p.nl(0.3)

    # ── MOON ──────────────────────────────────────────────────────────
    m_status = moon.get('status','---')
    p.line(_hline_t(f"MOON  [{m_status}]"))
    p.blank()
    p.drow("Right Ascension (RA)",  moon.get('ra','---'), cv=_FG_NAVY)
    p.drow("Declination     (Dec)", moon.get('dec','---'), cv=_FG_NAVY)
    p.blank()
    m_alt = moon.get('alt', 0)
    p.trow("Altitude",     f"{m_alt:+.2f} deg",        "Azimuth", f"{moon.get('az',0):.2f} deg",
           c1=_FG_BLACK, c2=_FG_BLACK, bold1=(m_alt>0))
    p.trow("Illumination", f"{moon.get('illum',0):.1f} %", "Phase", moon.get('phase','---'),
           c1=_FG_DKGRAY, c2=_FG_DKGRAY)
    p.blank(); p.line(_hline()); p.nl(0.3)

    # ── EVENTS ────────────────────────────────────────────────────────
    p.line(_hline_t(f"DAILY EVENTS  ({off_str})"))
    p.blank()

    p.stitle("SUN")
    p.line(_hline_t("", _COLS).replace("[","-").replace("]","-"),
           color=_FG_LGRAY)  # light separator

    _SUN_EVENTS = [
        ("Astronomical Dawn  ( -18 deg )", 'dawn_astro', _FG_GRAY,   False, False),
        ("Nautical Dawn      ( -12 deg )", 'dawn_naut',  _FG_GRAY,   False, False),
        ("Civil Dawn         (  -6 deg )", 'dawn_civ',   _FG_DKGRAY, False, False),
        (">>> SUNRISE        (   0 deg )", 'rise',        _FG_BLACK,  True,  True ),
        ("    SOLAR TRANSIT              ", 'transit',    _FG_BLACK,  True,  False),
        (">>> SUNSET         (   0 deg )", 'set',         _FG_BLACK,  True,  True ),
        ("Civil Dusk         (  -6 deg )", 'dusk_civ',   _FG_DKGRAY, False, False),
        ("Nautical Dusk      ( -12 deg )", 'dusk_naut',  _FG_GRAY,   False, False),
        ("Astronomical Dusk  ( -18 deg )", 'dusk_astro', _FG_GRAY,   False, False),
    ]
    for lbl, key, cv, bv, bl in _SUN_EVENTS:
        p.erow(lbl, evts_sun.get(key,'--:--'), cv=cv, bold_v=bv, bold_l=bl)

    p.blank()
    p.stitle("MOON")
    p.line(_hline(), color=_FG_LGRAY)

    _MOON_EVENTS = [
        (">>> MOONRISE", 'rise',    _FG_BLACK, True,  True ),
        ("    TRANSIT",  'transit', _FG_BLACK, True,  False),
        (">>> MOONSET",  'set',     _FG_BLACK, True,  True ),
    ]
    for lbl, key, cv, bv, bl in _MOON_EVENTS:
        p.erow(lbl, evts_moon.get(key,'--:--'), cv=cv, bold_v=bv, bold_l=bl)

    p.blank(); p.line(_hline()); p.nl(0.3)

    # ── FOOTER ────────────────────────────────────────────────────────
    gen_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    p.line(_hline())
    p.center(f"Generated {gen_ts} UT  |  Celeste v3.3", color=_FG_GRAY)
    p.center("Jean Meeus — Astronomical Algorithms, 2nd ed.", color=_FG_GRAY)
    p.center("VSOP87 (Sun ~1\")  |  ELP2000-82B (Moon ~10\")", color=_FG_GRAY)
    p.blank()
    p.center("*** END OF REPORT ***", color=_FG_BLACK, bold=True)
    p.line(_hline())

    p.save()
    return os.path.abspath(output_path)


# ===========================================================================
# GUI HELPER — builds data dict from AstroApp instance
# ===========================================================================

def build_data_from_app(app) -> dict:
    """
    Builds the data dict for generate_report_pdf() from a running AstroApp.

    Reads the window's public state: ``current_inputs()`` (UT date, latitude,
    longitude), ``location_name``, ``utc_offset``, ``sun_data``, ``moon_data``
    and the daily events of the last calculation (``sun_events``,
    ``moon_events``). Call ``app.calculate()`` first so they match the inputs.

    Args:
        app: AstroApp instance (gui.py).

    Returns:
        dict: Ready to pass to generate_report_pdf().

    Raises:
        ValueError: If the coordinates typed in the window are invalid.
    """
    from utils import Formatters
    from engine import AstroEngine

    dte, lat, lon = app.current_inputs()
    location = getattr(app, "location_name", "") or "---"

    sd = app.sun_data
    md = app.moon_data
    se = app.sun_events
    me = app.moon_events

    def fmt_evt(dt):
        if dt is None: return "--:--"
        return (dt + timedelta(hours=app.utc_offset)).strftime("%H:%M")

    s_alt = sd.get('alt', -90)
    if   s_alt > 0:   s_status = "VISIBLE"
    elif s_alt > -6:  s_status = "CIVIL TWIL."
    elif s_alt > -12: s_status = "NAUT. TWIL."
    elif s_alt > -18: s_status = "ASTRO TWIL."
    else:             s_status = "PITCH DARK"

    m_status = "VISIBLE" if md.get('alt',-90) > 0 else "BELOW HORIZON"

    t_       = AstroEngine.julian_century_j2000(dte)
    eot      = AstroEngine.equation_of_time(t_)
    _, r_sun = AstroEngine.sun_position(t_)

    return {
        'date'      : dte,
        'lat'       : lat,
        'lon'       : lon,
        'location'  : location,
        'utc_offset': app.utc_offset,
        'sun'       : {
            'ra'    : Formatters.hms(sd.get('ra',0)),
            'dec'   : Formatters.dms(sd.get('dec',0)),
            'alt'   : round(sd.get('alt',0), 2),
            'az'    : round(sd.get('az',0),  2),
            'eot'   : round(eot, 1),
            'dist'  : f"{r_sun:.4f} AU",
            'status': s_status,
        },
        'moon'      : {
            'ra'    : Formatters.hms(md.get('ra',0)),
            'dec'   : Formatters.dms(md.get('dec',0)),
            'alt'   : round(md.get('alt',0),   2),
            'az'    : round(md.get('az',0),    2),
            'illum' : round(md.get('illum',0), 1),
            # Plain English name: Courier has no glyph for the phase emoji
            'phase' : Formatters.PHASES[Formatters.phase_index(md.get('phase',0))][2],
            'status': m_status,
        },
        'events'    : {
            'sun' : {k: fmt_evt(v) for k, v in se.items()},
            'moon': {k: fmt_evt(v) for k, v in me.items()},
        },
    }
