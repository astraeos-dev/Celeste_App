"""
gui.py — Graphical interface of Céleste (PyQt6), Astræos design
=================================================================
v3.3 — Interface following the Astræos design system:
  ★ Three themes: Nuit (night, the default), Jour (day), Observation (red on
    black, to keep night vision), chosen in the side panel
  ★ IBM Plex Sans for the text, IBM Plex Mono for the data, astronomical
    symbols (☉ ☽ ♀ ♂ ♃ ♄ ☌ ☍) always next to the name of the body
  ★ No emoji: Material Design line icons
  ★ Components of the design system, under English names here: Bouton
    (_button), BoutonIcone (_icon_button), ChampSaisie (InputField),
    CarteDonnee (DataCard), PastilleEtat (_badge), Jauge, Onglets,
    SelecteurTheme (ThemeSelector); a single gold area per screen (the
    Calculate button), hairlines rather than shadows
  ★ Names kept from the design system (tokens.json): the colour tokens
    (ciel, encre, or, lune…), the text styles (corps, legende, donnee,
    cadran…), the variants (principal, secondaire, discret), the tones
    (neutre, alerte, attenuee) and the themes (nuit, jour, observation)
  ★ Translated texts (fr, en, es, de); numbers in the language's style
  ★ Shortcuts: F5 calculate, Ctrl+L real time, Ctrl+H history

Layout:
  - Side panel     : date, place, time zone, favourites, actions, theme
  - Main area      : tabs Ephemeris / Trajectories / Sky map / Planets /
                     Solar System / Coordinates / Events / Settings
  - Status bar     : place, visible bodies, UT and local time

The calculations come from engine.py, the charts from charts.py, the colours
from config.py (Astræos tokens), the icons and the logo from icons.py.
"""

import json
import math
import os
import time
import re
import sys
import urllib.request
import functools
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

from PyQt6.QtCore import (
    QDate, QDateTime, QEvent, QLocale, QPoint, QPointF, QRectF, QRegularExpression, QSize,
    QStringListModel, Qt, QTime, QTimer, QTimeZone, QUrl,
)
from PyQt6.QtGui import (
    QBrush, QColor, QCursor, QDesktopServices, QFont, QFontDatabase, QKeySequence,
    QPainter, QPainterPath, QPalette, QPen, QPixmap, QRegularExpressionValidator, QShortcut,
)
from PyQt6.QtPositioning import QGeoPositionInfo, QGeoPositionInfoSource
from PyQt6.QtWidgets import (
    QAbstractItemView, QApplication, QButtonGroup, QCheckBox, QComboBox, QCompleter,
    QDateEdit, QDateTimeEdit, QDialog, QDialogButtonBox, QFileDialog, QFrame, QGridLayout, QProgressDialog,
    QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit, QMainWindow, QMenu,
    QMessageBox, QProgressBar, QPushButton, QScrollArea, QSizePolicy, QSlider, QSplitter, QToolTip,
    QStatusBar, QTabWidget, QTableWidget, QTableWidgetItem, QToolButton,
    QVBoxLayout, QWidget,
)

import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

import astro_calendar  # noqa: E402
import charts  # noqa: E402
import history  # noqa: E402
import icons  # noqa: E402
import mpc  # noqa: E402
import planner  # noqa: E402
import places  # noqa: E402
import satellites  # noqa: E402
import settings as prefs  # noqa: E402
import updater  # noqa: E402
from config import APP_BETA, APP_VERSION, FONT_MONO, FONT_SANS, THEME_NAMES, Config, mix  # noqa: E402
from engine import (  # noqa: E402
    COMET_DESIGNATIONS, COMET_SHORT, COMETS, EPHEMERIS_YEARS, GALILEAN_MOONS, MINOR_PLANET_NUMBERS, MINOR_PLANETS, MOON_PLANETS,
    PLANETS,
    AstroEngine,
    constellation_names, messier_catalog,
)
from i18n import (  # noqa: E402
    available_langs, get_lang, lang_name, resolve_lang, switch_lang, t, tf,
)
from utils import Formatters  # noqa: E402

# ── Constants ─────────────────────────────────────────────────────────────────


# The user's favourites, outside the repository; at the first launch, those of an
# earlier version (application folder) or the starting list
_FAVORITES_FILE = os.path.join(prefs.USER_DIR, "favorites.json")
_LEGACY_FAVORITES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "favorites.json")
_DEFAULT_FAVORITES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                       "favorites_default.json")
_FONTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")

_AUTO_ZONE = "auto"           # time zone from the place (timezonefinder)
_GEOLOC_TIMEOUT_MS = 15000    # wait for the device's location service
_HISTORY_DELAY_MS = 3000      # a calculation enters the history once the user has stayed on it

_ALL_POSITIONING_METHODS = QGeoPositionInfoSource.PositioningMethod.AllPositioningMethods

# Links: website, source code, support; requests on GitHub (forms of .github/ISSUE_TEMPLATE)
_URL_SITE = "https://astraeos-dev.github.io/personnal-site/"
_URL_REPO = "https://github.com/astraeos-dev/Celeste_App"
_URL_COFFEE = "https://buymeacoffee.com/gregorychau"

# Location settings of the system, opened when access is denied
_LOCATION_SETTINGS = {
    "win32": "ms-settings:privacy-location",
    "darwin": "x-apple.systempreferences:com.apple.preference.security?Privacy_LocationServices",
}
_PLANETS = PLANETS        # Mercury to Neptune (engine.PLANETS)
_QT_DATETIME_FORMAT = "dd/MM/yyyy HH:mm:ss"

# Decimal degrees, with a point or a comma (49.6333 or 49,6333)
_COORD_REGEX = r"^\s*[+\-−]?\d{0,3}(?:[.,]\d{0,8})?\s*$"

# Greek letters of the star designations, spelled out for the search ("α CMa": "alpha cma")
_GREEK = dict(zip("αβγδεζηθικλμνξοπρστυφχψω", (
    "alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta", "theta", "iota", "kappa", "lambda",
    "mu", "nu", "xi", "omicron", "pi", "rho", "sigma", "tau", "upsilon", "phi", "chi", "psi", "omega")))

# Astronomical symbols, followed by U+FE0E (text presentation, never emoji)
_VS15 = "︎"
SYMBOL = {name: glyph + _VS15 for name, glyph in charts.SYMBOL.items()}
SYMBOL.update({"star": "★" + _VS15, "conjunction": "☌" + _VS15,
               "opposition": "☍" + _VS15, "meteors": "☄" + _VS15, "dot": "●"})

# Fallback fonts when the files of fonts/ are missing. No emoji font: placed
# in a stack, it would also draw the digits and the spaces.
_FALLBACK_SANS = ("Segoe UI", "Inter", "Helvetica Neue", "Noto Sans", "Ubuntu",
                  "Cantarell", "DejaVu Sans", "Arial")
_FALLBACK_MONO = ("Cascadia Mono", "Consolas", "JetBrains Mono", "Menlo",
                  "DejaVu Sans Mono", "Liberation Mono", "Courier New")
_fonts = {"sans": FONT_SANS, "mono": FONT_MONO}


# ── Small helpers ─────────────────────────────────────────────────────────────

def _utc_now():
    """The present instant in universal time, without time zone or microseconds."""
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


def _utc_zone():
    return QTimeZone.utc() if hasattr(QTimeZone, "utc") else QTimeZone(b"UTC")


def _pref_float(key, fallback):
    """Numeric preference; *fallback* only when it is missing (0.0 is valid)."""
    value = prefs.get(key)
    try:
        return float(value) if value is not None else fallback
    except (TypeError, ValueError):
        return fallback


def _parse_coord(text, limit):
    """Decimal degrees typed (point or comma); ValueError beyond ±limit."""
    value = float(text.strip().replace(",", ".").replace("−", "-"))
    if math.isnan(value) or not -limit <= value <= limit:
        raise ValueError(text)
    return value


def _locale():
    return QLocale(get_lang())


def _num(value, decimals=0, signed=False):
    """A number in the active language's style ("12,4" in French)."""
    text = _locale().toString(float(value), "f", decimals)
    text = text.replace("-", "−")
    if signed and value >= 0:
        text = "+" + text
    return text


def _deg(value, decimals=2, signed=False):
    return f"{_num(value, decimals, signed)}°"


def _angle_format():
    """The chosen angle format: "dms", "dm" or "dd" (Formatters.ANGLE_FORMATS)."""
    fmt = prefs.get("angle_format")
    return fmt if fmt in Formatters.ANGLE_FORMATS else "dms"


def _localized(text):
    """Decimal separator of the language and a true minus sign."""
    text = text.replace(".", _locale().decimalPoint())
    return "−" + text[1:] if text.startswith("-") else text


def _ra(hours, fmt=None):
    """Right ascension "14h 28m 19,0s", "14h 28,317m" or "14,47194h"
    (*fmt*: a forced format, else the one of the settings)."""
    return _localized(Formatters.angle(hours % 24.0, fmt or _angle_format(), hours=True))


def _dec(degrees, fmt=None):
    """Signed angle (declination, latitude, altitude): "−14° 38′ 49″", "+14° 38,82′"…"""
    return _localized(Formatters.angle(degrees, fmt or _angle_format(), signed=True))


def _az(degrees, fmt=None):
    """Angle from 0 to 360° (azimuth, longitude) in the chosen format."""
    return _localized(Formatters.angle(degrees % 360.0, fmt or _angle_format()))


def _fmt_offset(offset):
    return Formatters.utc_offset(offset)


def _zone_names():
    """IANA time zones offered (zoneinfo base), UTC first."""
    hidden = ("posix/", "right/", "SystemV/")
    return ["UTC"] + sorted(z for z in available_timezones()
                            if z != "UTC" and not z.startswith(hidden))


@functools.lru_cache(maxsize=1)
def _tz_finder():
    from timezonefinder import TimezoneFinder
    return TimezoneFinder()


@functools.lru_cache(maxsize=256)
def _zone_at(lat, lon):
    """IANA time zone of a place (timezonefinder, offline); "UTC" when unknown."""
    try:
        return _tz_finder().timezone_at(lat=lat, lng=lon) or "UTC"
    except Exception:  # timezonefinder missing or failing: universal time
        return "UTC"


def _zone(name, lat=None, lon=None):
    """tzinfo of a time zone; "auto" is the place's (lat, lon)."""
    name = name or _AUTO_ZONE
    if name == _AUTO_ZONE:
        name = _zone_at(round(lat, 3), round(lon, 3)) if lat is not None else "UTC"
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def _elev_text(metres):
    return str(int(round(metres)))


# Services giving the approximate position of the IP address, over HTTPS first
_IP_SERVICES = (
    ("https://ipwho.is/", lambda d: d.get("success") and (
        d["latitude"], d["longitude"], d.get("city"), d.get("country"), (d.get("timezone") or {}).get("id"))),
    ("https://ipapi.co/json/", lambda d: "latitude" in d and not d.get("error") and (
        d["latitude"], d["longitude"], d.get("city"), d.get("country_name"), d.get("timezone"))),
    ("http://ip-api.com/json/?fields=status,country,city,lat,lon,timezone", lambda d: d.get("status") == "success"
     and (d["lat"], d["lon"], d.get("city"), d.get("country"), d.get("timezone"))),
)


def _ip_location(services=_IP_SERVICES, timeout=4):
    """(lat, lon, city, country, IANA zone) of the IP address from the first service that
    answers; None when none does (offline, blocked)."""
    for url, parse in services:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": f"Celeste/{APP_VERSION}"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            found = parse(data)
        except Exception:  # network, delay, JSON, missing field: the next service
            continue
        if found:
            lat, lon, city, country, zone = found
            return float(lat), float(lon), city or "", country or "", zone
    return None


def _satellite_name(name, short=False):
    """The name of a satellite: translated for the ISS, Tiangong and Hubble, as CelesTrak
    gives it for the others ("SL-16 R/B" stays "SL-16 R/B")."""
    if name in satellites.SATELLITES:
        return t(f"satellites.{'short' if short else 'name'}_{name}")
    return name


def _version_text():
    """4.12, or "4.12 bêta 3" for a beta build."""
    return tf("app.beta", version=APP_VERSION, n=APP_BETA) if APP_BETA else APP_VERSION


def _place_name(lat, lon):
    """Name of the town of a point (OpenStreetMap Nominatim); without an answer, the
    nearest city of the offline list (within 25 km), else ""."""
    name = _nominatim_name(lat, lon)
    if name:
        return name
    near = places.nearest(lat, lon)
    return near["name"] if near else ""


def _nominatim_name(lat, lon):
    """Name of the town of a point (OpenStreetMap Nominatim); "" without an answer."""
    url = ("https://nominatim.openstreetmap.org/reverse?format=jsonv2&zoom=10"
           f"&lat={lat:.5f}&lon={lon:.5f}&accept-language={get_lang()}")
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": f"Celeste/{APP_VERSION} (+https://github.com/astraeos-dev/Celeste_App)"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:  # network, delay, JSON: the coordinates are enough
        return ""
    address = data.get("address") or {}
    for key in ("city", "town", "village", "municipality", "hamlet"):
        if address.get(key):
            return address[key]
    return data.get("name") or ""


def _fmt_lat(lat):
    return f"{_num(abs(lat), 4)}° {t('coords.north') if lat >= 0 else t('coords.south')}"


def _fmt_lon(lon):
    return f"{_num(abs(lon), 4)}° {t('coords.east') if lon >= 0 else t('coords.west')}"


def _default_favorites(lang=None):
    """
    The preloaded places (favorites_default.json), named in the interface
    language: a place's key is its French name, and "names" gives the others
    where they differ. A language without its own name gets the English one.
    """
    lang = lang or get_lang()
    try:
        with open(_DEFAULT_FAVORITES_FILE, "r", encoding="utf-8") as f:
            preloaded = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    favorites = {}
    for key, place in preloaded.items():
        names = place.get("names", {})
        name = key if lang == "fr" else names.get(lang, names.get("en", key))
        favorites[name] = {k: v for k, v in place.items() if k != "names"}
    return favorites


def _typed_number(text):
    """A number typed in the active language's style: "1 010", "2,5", "−3" (ValueError otherwise)."""
    return float(re.sub(r"[\s\u00a0\u202f]", "", text).replace(",", ".").replace("−", "-"))


def _coord_text(value):
    """A coordinate shown in a field (decimal comma in French)."""
    return _num(value, 4)


def _clean_place(name):
    """A place name without the 📍 pin of the old default value."""
    return (name or "").replace("\U0001f4cd", "").strip()


def _planet_name(name, symbol=False, numbered=False):
    """Name of a planet; *numbered*: with the number of a minor planet, "(1) Ceres";
    a comet: its designation, the same in every language (full with *numbered*)."""
    if name in COMET_DESIGNATIONS:
        text = COMET_DESIGNATIONS[name] if numbered else COMET_SHORT.get(name, COMET_DESIGNATIONS[name])
        return f"{SYMBOL[name]} {text}" if symbol else text
    text = t(f"planets.{name.lower()}")
    if numbered and name in MINOR_PLANET_NUMBERS:
        text = f"({MINOR_PLANET_NUMBERS[name]}) {text}"
    return f"{SYMBOL[name]} {text}" if symbol else text


_TONIGHT_CACHE = {}


def _tonight_and_upcoming(key, dte, lat, lon, elev, zone):
    """"Tonight" and the next three visible events (0.3 s), kept for the night and
    the place *key*: a change of theme or language does not compute them again."""
    key = (*key, satellites.cache_stamp())                      # new orbits: new passes
    if key not in _TONIGHT_CACHE:
        if len(_TONIGHT_CACHE) >= 8:
            _TONIGHT_CACHE.pop(next(iter(_TONIGHT_CACHE)))
        night = AstroEngine.tonight(dte, lat, lon, elev, zone)
        elements = satellites.load()                     # no network here: the orbits on disk
        if elements and satellites.epoch_age_days(elements) <= satellites.STALE_DAYS:
            night["satellites"] = AstroEngine.satellite_passes(elements, night["start"], lat, lon, elev, 1)
        _TONIGHT_CACHE[key] = (night, AstroEngine.upcoming_events(dte, lat, lon, elev, zone))
    return _TONIGHT_CACHE[key]


def _messier_label(obj, named=True):
    """"M31 Andromeda Galaxy" (the common name in the active language, if it has
    one), or "M13" with *named* False; another deep-sky object of the planner:
    "C14 Double Cluster", "NGC 7000 North America Nebula"."""
    if not obj.get("m"):
        text = planner.label(obj)
        return f"{text} {obj['name']}" if named and obj.get("name") and obj["name"] != text else text
    if named and obj.get("name"):
        name = t(f"messier.name_{obj['m']}")
        return f"M{obj['m']} {name}"
    return f"M{obj['m']}"


def _plural_key(base, n):
    """Key "_one" or "_many"; in French, 0 is singular."""
    one = n == 1 or (n == 0 and get_lang() == "fr")
    return f"{base}_{'one' if one else 'many'}"


def _ics_text(text):
    """Text of an iCalendar property: \\ ; , and line breaks escaped."""
    return (text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
            .replace("\n", "\\n"))


def _ics_fold(line):
    """An iCalendar line folded at 75 octets (RFC 5545, 3.1)."""
    out, current = [], ""
    for char in line:
        if len((current + char).encode("utf-8")) > (75 if not out else 74):
            out.append(current)
            current = ""
        current += char
    out.append(current)
    return "\r\n ".join(out)


def _ics_calendar(items, stamp):
    """
    iCalendar calendar of the events *items*: (start, end, title, description),
    times in UT (naive or with a time zone); *stamp*: time of the export.
    """
    def utc(dt):
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt.strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", f"PRODID:-//Astraeos//Celeste {APP_VERSION}//FR",
             "CALSCALE:GREGORIAN", "METHOD:PUBLISH"]
    for n, (start, end, summary, description) in enumerate(items):
        lines += ["BEGIN:VEVENT", f"UID:{utc(start)}-{n}@celeste.astraeos", f"DTSTAMP:{utc(stamp)}",
                  f"DTSTART:{utc(start)}", f"DTEND:{utc(end)}", f"SUMMARY:{_ics_text(summary)}",
                  f"DESCRIPTION:{_ics_text(description)}", "TRANSP:TRANSPARENT", "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return "".join(_ics_fold(line) + "\r\n" for line in lines)


# Groups of bodies of the Planets tab, in their order: a new group (deep sky…)
# is added here with its names, and a planets.group_<key> key in the
# translations
_BODY_GROUPS = (("planets", PLANETS), ("minor", MINOR_PLANETS), ("comets", COMETS))
_SORT_ROLE = Qt.ItemDataRole.UserRole          # numeric sort value of a cell
_NAME_ROLE = Qt.ItemDataRole.UserRole + 1      # name of the body of a row


class _SortItem(QTableWidgetItem):
    """A cell sorted by its numeric value (_SORT_ROLE), not by its text."""

    def __lt__(self, other):
        mine, theirs = self.data(_SORT_ROLE), other.data(_SORT_ROLE)
        if mine is None or theirs is None:
            return (mine is None) < (theirs is None)            # "—" last
        return mine < theirs


_BACKGROUND = set()          # timers of the running background tasks (kept alive)


def _run_in_background(func, on_done, on_error):
    """Runs func() in a separate thread (network); then on_done(result) or
    on_error(exception), in the interface's thread."""
    from concurrent.futures import ThreadPoolExecutor
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(func)
    timer = QTimer()
    timer.setInterval(150)

    def poll():
        if not future.done():
            return
        timer.stop()
        _BACKGROUND.discard(timer)
        executor.shutdown(wait=False)
        error = future.exception()
        if error is not None:
            on_error(error)
        else:
            on_done(future.result())
    timer.timeout.connect(poll)
    _BACKGROUND.add(timer)
    timer.start()


def _issue_url(template):
    """A new request on GitHub, form *template* (bug, feature, body) filled with
    the version of Céleste and the system."""
    import platform
    from urllib.parse import urlencode
    query = {"template": f"{template}.yml", "version": APP_VERSION,
             "system": f"{platform.system()} {platform.release()}".strip()}
    return f"{_URL_REPO}/issues/new?{urlencode(query)}"


def _open_url(url):
    QDesktopServices.openUrl(QUrl(url))


def _duration(minutes):
    """Duration "58 min" or "3 h 27"."""
    minutes = int(round(minutes))
    if minutes < 60:
        return tf("units.minutes", value=minutes)
    return tf("units.duration", h=minutes // 60, m=f"{minutes % 60:02d}")


def _rgba(color, alpha):
    """QSS colour with transparency (alpha from 0 to 1)."""
    c = QColor(color)
    return f"rgba({c.red()}, {c.green()}, {c.blue()}, {round(alpha * 255)})"


def _repolish(widget):
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def _set_prop(widget, name, value):
    """A property read by the style sheet; re-polished only when it changes."""
    if widget.property(name) != value:
        widget.setProperty(name, value)
        _repolish(widget)


def _set_invalid(widget, invalid):
    _set_prop(widget, "invalid", bool(invalid))


def _label(text="", style="corps", tone=None, strong=False, wrap=False, name=None):
    """QLabel in an Astræos text style (corps, legende, donnee, cadran…)."""
    lbl = QLabel(text)
    lbl.setProperty("textStyle", style)
    if tone:
        lbl.setProperty("tone", tone)
    if strong:
        lbl.setProperty("strong", True)
    if wrap:
        lbl.setWordWrap(True)
    if name:
        lbl.setObjectName(name)
    return lbl


def _card():
    frame = QFrame()
    frame.setObjectName("card")
    return frame


def _icon(key, color=None, size=20, checked=False):
    color = color or Config.ENCRE_ATTENUEE
    return icons.icon(key, color, size,
                      checked_color=Config.CIEL_000 if checked else None,
                      disabled_color=mix(color, Config.CIEL_100, 0.45))


def _button(text, icon_key=None, variant="secondaire", compact=False, checkable=False):
    """
    Astræos Bouton: "principal" (gold fill, once per screen), "secondaire"
    (outline), "discret" or "danger"; normal (40 px) or compact.
    """
    btn = QPushButton(text)
    btn.setProperty("variant", variant)
    if compact:
        btn.setProperty("density", "compact")
    btn.setFixedHeight(32 if compact else 40)
    btn.setCheckable(checkable)
    btn.setFocusPolicy(Qt.FocusPolicy.TabFocus)     # focus ring from the keyboard only
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    if icon_key:
        if variant == "principal":
            color = Config.SUR_OR
        elif variant == "danger":
            color = Config.SIGNAL_ALERTE
        else:
            color = Config.ENCRE
        size = 16 if compact else 20
        btn.setIcon(_icon(icon_key, color, size, checked=checkable))
        btn.setIconSize(QSize(size, size))
    return btn


def _icon_button(icon_key, label, variant="discret", compact=False, checkable=False):
    """Astræos BoutonIcone: round, an icon only, named by *label* (tooltip)."""
    btn = QToolButton()
    btn.setObjectName("iconButton")
    btn.setProperty("variant", variant)
    if compact:
        btn.setProperty("density", "compact")
    size = 32 if compact else 40
    icon_size = 16 if compact else 20
    btn.setFixedSize(size, size)
    btn.setIcon(_icon(icon_key, Config.ENCRE, icon_size, checked=checkable))
    btn.setIconSize(QSize(icon_size, icon_size))
    btn.setToolTip(label)
    btn.setAccessibleName(label)
    btn.setCheckable(checkable)
    btn.setFocusPolicy(Qt.FocusPolicy.TabFocus)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    return btn


def _set_badge(label, text, tone):
    """Astræos PastilleEtat: a dot and one or two words; tone "neutre", "info", "ok" or "alerte"."""
    label.setText(f"{SYMBOL['dot']}  {text}")
    label.setFixedHeight(24)
    _set_prop(label, "badge", tone)


def _badge(text="", tone="neutre"):
    lbl = QLabel()
    _set_badge(lbl, text, tone)
    return lbl


def _scroll_page():
    """(QScrollArea, inner page, vertical layout of the page)."""
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    page = QWidget()
    page.setObjectName("page")
    layout = QVBoxLayout(page)
    layout.setContentsMargins(0, 16, 8, 16)
    layout.setSpacing(16)
    scroll.setWidget(page)
    return scroll, page, layout


# ── Astræos components ────────────────────────────────────────────────────────

class InputField(QWidget):
    """
    Astræos ChampSaisie: a label always visible above, a 40 px box (encre-attenuee
    outline, encre on hover, gold ring on focus), the unit on the right, help
    or error below. *widget*: QLineEdit (the default), QComboBox or
    QDateTimeEdit.
    """

    def __init__(self, label, widget=None, unit=None, numeric=False, hint=None):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        self.label = _label(label, "label")
        lay.addWidget(self.label)

        self.box = QFrame()
        self.box.setObjectName("fieldBox")
        self.box.setFixedHeight(40)
        row = QHBoxLayout(self.box)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        self.input = widget if widget is not None else QLineEdit()
        if numeric:
            self.input.setProperty("numeric", True)
        row.addWidget(self.input, stretch=1)
        if unit:
            row.addWidget(_label(unit, "corps", tone="attenuee", name="fieldUnit"))
            self.input.setAccessibleName(f"{label} ({unit})")
        else:
            self.input.setAccessibleName(label)
        lay.addWidget(self.box)

        self.error = _label("", "legende", tone="alerte", strong=True, wrap=True)
        self.error.hide()
        lay.addWidget(self.error)
        self.hint = None
        if hint:
            self.hint = _label(hint, "legende", wrap=True)
            lay.addWidget(self.hint)

        self.input.installEventFilter(self)
        self.box.installEventFilter(self)

    def eventFilter(self, obj, event):
        kind = event.type()
        if kind in (QEvent.Type.FocusIn, QEvent.Type.FocusOut):
            # "focused", not "focus": Qt's own read-only property of that name
            # cannot be set, and the gold ring never showed
            _set_prop(self.box, "focused", kind == QEvent.Type.FocusIn)
        elif obj is self.box and kind in (QEvent.Type.Enter, QEvent.Type.Leave):
            _set_prop(self.box, "hover", kind == QEvent.Type.Enter)
        return False

    def set_error(self, message):
        """Shows *message* (what is wrong and how to fix it), or nothing with None."""
        _set_prop(self.box, "error", bool(message))
        self.error.setText(message or "")
        self.error.setVisible(bool(message))
        if self.hint is not None:
            self.hint.setVisible(not message)

    def set_inactive(self, off):
        _set_prop(self.box, "inactive", bool(off))


class DataCard(QFrame):
    """
    Astræos CarteDonnee, normal density: symbol and label, the value in the
    cadran style (Plex Mono 32 px) with its unit, a context line.
    """

    def __init__(self, label, symbol=None, accent=None):
        super().__init__()
        self.setObjectName("card")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(8)
        head = QHBoxLayout()
        head.setSpacing(8)
        if symbol:
            head.addWidget(_label(symbol, "symbol", tone=accent or "attenuee"))
        head.addWidget(_label(label, "legende"), stretch=1)
        lay.addLayout(head)
        measure = QHBoxLayout()
        measure.setSpacing(4)
        self.value = _label("—", "cadran")
        self.unit = _label("", "corps", tone="attenuee")
        measure.addWidget(self.value, alignment=Qt.AlignmentFlag.AlignBaseline)
        measure.addWidget(self.unit, alignment=Qt.AlignmentFlag.AlignBaseline)
        measure.addStretch()
        lay.addLayout(measure)
        self.detail = _label("", "legende", wrap=True)
        lay.addWidget(self.detail)
        lay.addStretch()

    def set_value(self, value, unit="", detail=""):
        self.value.setText(value)
        self.unit.setText(unit)
        self.unit.setVisible(bool(unit))
        self.detail.setText(detail)


class MoonPhase(QWidget):
    """The Moon's disc lit by the phase angle, drawn in the LUNE colour token."""

    def __init__(self, diameter=56):
        super().__init__()
        self.setFixedSize(diameter, diameter)
        self._phase = 0.0
        self._mirror = False

    def set_phase(self, phase_angle, southern=False):
        """*phase_angle*: longitude Moon − Sun (0 new moon, 180 full moon)."""
        self._phase = phase_angle % 360.0
        self._mirror = southern
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = min(self.width(), self.height()) / 2.0 - 1.5
        c = QPointF(self.width() / 2.0, self.height() / 2.0)
        disc = QRectF(c.x() - r, c.y() - r, 2 * r, 2 * r)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(Config.CIEL_200))
        p.drawEllipse(disc)

        waxing = self._phase < 180.0
        phi = self._phase if waxing else 360.0 - self._phase      # 0 … 180
        e = r * math.cos(math.radians(phi))                       # semi-axis of the terminator
        lit = QPainterPath()
        lit.moveTo(c.x(), c.y() - r)
        lit.arcTo(disc, 90, -180)                                 # right edge, lit
        ell = QRectF(c.x() - abs(e), c.y() - r, 2 * abs(e), 2 * r)
        lit.arcTo(ell, -90, 180 if e > 0 else -180)               # terminator
        lit.closeSubpath()
        if waxing == self._mirror:                                # waning: on the left
            p.translate(2 * c.x(), 0)
            p.scale(-1, 1)
        p.setBrush(QColor(Config.LUNE))
        p.drawPath(lit)
        p.resetTransform()
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(Config.LUNE), 1.2))
        p.drawEllipse(disc)
        p.end()


class JupiterMoons(QWidget):
    """
    Jupiter and its four Galilean moons along its equator, to scale, as an
    almanac draws them: north up and east to the left, as binoculars show them
    north of the equator; turned upside down with *southern*. A moon behind
    the disc is not drawn; one in Jupiter's shadow is a hollow dot.
    """
    SPAN = 28.0                     # radii of Jupiter on each side (Callisto reaches 26.6)

    def __init__(self, moons, southern=False):
        super().__init__()
        self.moons = moons
        self.southern = southern
        self.setMinimumSize(336, 56)
        self.setFixedHeight(56)

    def positions(self):
        """{name: (x, y) in pixels} of the moons drawn, and the scale (pixels per radius)."""
        scale = (self.width() - 16) / (2 * self.SPAN)
        turn = -1.0 if self.southern else 1.0
        cx, cy = self.width() / 2.0, 22.0
        return {m["name"]: (cx + turn * m["x"] * scale, cy - turn * m["y"] * scale)
                for m in self.moons if m["state"] != "occulted"}, scale

    def paintEvent(self, _event):
        points, scale = self.positions()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx, cy = self.width() / 2.0, 22.0
        p.setPen(QPen(QColor(Config.CIEL_200), 1))
        p.drawLine(QPointF(8, cy), QPointF(self.width() - 8, cy))
        p.setPen(QPen(QColor(Config.ENCRE), 1.2))
        p.setBrush(QColor(Config.CIEL_100))
        p.drawEllipse(QPointF(cx, cy), scale, scale * 0.935)
        font = QFont(self.font())
        font.setPixelSize(11)
        p.setFont(font)
        for i, moon in enumerate(self.moons):
            if moon["name"] not in points:
                continue
            x, y = points[moon["name"]]
            p.setPen(QPen(QColor(Config.LUNE), 1.2))
            p.setBrush(QColor(Config.CIEL_100 if moon["state"] == "eclipsed" else Config.LUNE))
            p.drawEllipse(QPointF(x, y), 2.5, 2.5)
            p.setPen(QColor(Config.ENCRE_ATTENUEE))
            p.drawText(QRectF(x - 12, cy + 8 + 12 * (i % 2), 24, 12), int(Qt.AlignmentFlag.AlignCenter),
                       ("I", "II", "III", "IV")[i])
        p.setPen(QColor(Config.ENCRE_ATTENUEE))
        west, east = t("skymap.cardinal_w"), t("skymap.cardinal_e")
        left, right = (west, east) if self.southern else (east, west)
        p.drawText(QRectF(0, 0, 24, 12), int(Qt.AlignmentFlag.AlignLeft), left)
        p.drawText(QRectF(self.width() - 24, 0, 24, 12), int(Qt.AlignmentFlag.AlignRight), right)
        p.end()


class _DayCell(QFrame):
    """A day of the astronomical calendar: its number and its first events, clickable."""

    def __init__(self, on_click):
        super().__init__()
        self.setObjectName("calendarDay")
        self.on_click = on_click
        self.day = None
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumSize(40, 92)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 4, 6, 4)
        lay.setSpacing(1)
        self.number = _label("", "legende", strong=True)
        lay.addWidget(self.number)
        self.lines = _label("", "legende")
        self.lines.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.lines.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        lay.addWidget(self.lines, stretch=1)

    def show_day(self, day, number, lines, tip, in_month, chosen):
        self.day = day
        self.number.setText(number)
        self.lines.setText("\n".join(lines))
        self.setToolTip(tip)
        border = Config.OR if chosen else Config.CIEL_200
        self.setStyleSheet(f"QFrame#calendarDay {{ border: {2 if chosen else 1}px solid {border}; border-radius: 6px;"
                           f" background: {Config.CIEL_100 if in_month else Config.CIEL_000}; }}")
        self.number.setEnabled(in_month)
        self.lines.setEnabled(in_month)

    def mousePressEvent(self, event):
        if self.day is not None:
            self.on_click(self.day)
        super().mousePressEvent(event)


class PlanetMoons(QWidget):
    """
    A planet and its moons as seen in a telescope: north up and east to the left (the
    reverse with *southern*); the distances from the planet are compressed (square
    root) so that Mimas and Iapetus fit in the same drawing. A moon behind the disc
    is not drawn.
    """

    def __init__(self, moons, radius_arcsec, southern=False):
        super().__init__()
        self.moons = moons
        self.radius = max(radius_arcsec, 0.05)
        self.southern = southern
        self.setMinimumSize(336, 150)
        self.setFixedHeight(150)

    def positions(self):
        """{name: (x, y) pixels} of the moons drawn, and the planet's radius in pixels."""
        far = max([m["separation"] for m in self.moons] + [self.radius * 2])
        room = self.width() / 2.0 - 44
        planet = max(4.0, room * math.sqrt(self.radius / far))
        turn = -1.0 if self.southern else 1.0
        cx, cy = self.width() / 2.0, self.height() / 2.0
        out = {}
        for m in self.moons:
            if m["state"] == "occulted":
                continue
            sep = m["separation"]
            k = room * math.sqrt(sep / far) / sep if sep > 0 else 0.0
            y = cy - turn * m["north"] * k
            out[m["name"]] = (cx - turn * m["east"] * k, max(18.0, min(self.height() - 18.0, y)))
        return out, planet

    def paintEvent(self, _event):
        points, planet = self.positions()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx, cy = self.width() / 2.0, self.height() / 2.0
        p.setPen(QPen(QColor(Config.ENCRE), 1.2))
        p.setBrush(QColor(Config.CIEL_100))
        p.drawEllipse(QPointF(cx, cy), planet, planet)
        font = QFont(self.font())
        font.setPixelSize(11)
        p.setFont(font)
        drawn = sorted((m for m in self.moons if m["name"] in points), key=lambda m: points[m["name"]][0])
        for n, moon in enumerate(drawn):                 # names above and below in turn: no overlap
            x, y = points[moon["name"]]
            p.setPen(QPen(QColor(Config.LUNE), 1.2))
            p.setBrush(QColor(Config.LUNE))
            size = max(1.6, 3.6 - 0.25 * (moon["mag"] - 8))
            p.drawEllipse(QPointF(x, y), size, size)
            p.setPen(QColor(Config.ENCRE_ATTENUEE))
            label_y = y - 17 if n % 2 == 0 else y + 5
            p.drawText(QRectF(x - 45, label_y, 90, 12), int(Qt.AlignmentFlag.AlignCenter), t(f"moons.{moon['name']}"))
        p.setPen(QColor(Config.ENCRE_ATTENUEE))
        west, east = t("skymap.cardinal_w"), t("skymap.cardinal_e")
        north, south = t("skymap.cardinal_n"), t("skymap.cardinal_s")
        left, right = (west, east) if self.southern else (east, west)
        top = south if self.southern else north
        p.drawText(QRectF(0, cy - 6, 24, 12), int(Qt.AlignmentFlag.AlignLeft), left)
        p.drawText(QRectF(self.width() - 24, cy - 6, 24, 12), int(Qt.AlignmentFlag.AlignRight), right)
        p.drawText(QRectF(cx - 12, 0, 24, 12), int(Qt.AlignmentFlag.AlignCenter), top)
        p.end()


class SaturnRings(QWidget):
    """
    Saturn and its rings at their tilt of the moment (*tilt* in degrees,
    positive when the north face is seen): the globe, the outer edge of ring A,
    the Cassini division and the inner edge of ring B; north up, the reverse
    with *southern*.
    """
    RINGS = (136775.0 / 60268.0, 119875.0 / 60268.0, 92000.0 / 60268.0)   # in radii of Saturn

    def __init__(self, tilt, southern=False):
        super().__init__()
        self.tilt = -tilt if southern else tilt
        self.setMinimumSize(200, 76)
        self.setFixedHeight(76)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx, cy, radius = self.width() / 2.0, self.height() / 2.0, 24.0
        opening = math.sin(math.radians(self.tilt))
        pens = (QPen(QColor(Config.ENCRE), 1.2), QPen(QColor(Config.ENCRE_ATTENUEE), 1),
                QPen(QColor(Config.ENCRE), 1.2))

        def ring(k, start, span):
            a = self.RINGS[k] * radius
            b = max(abs(a * opening), 0.3)
            p.setPen(pens[k])
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawArc(QRectF(cx - a, cy - b, 2 * a, 2 * b), start * 16, span * 16)

        # the far half of the rings, the globe over it, then the near half over the globe
        far = 0 if opening >= 0 else 180                  # seen from the north: the far half is the upper one
        for k in range(3):
            ring(k, far, 180)
        p.setPen(QPen(QColor(Config.ENCRE), 1.2))
        p.setBrush(QColor(Config.CIEL_100))
        p.drawEllipse(QPointF(cx, cy), radius, radius * 0.902)
        for k in range(3):
            ring(k, far + 180, 180)
        p.end()


class ThemeSelector(QFrame):
    """Astræos SelecteurTheme: Nuit, Jour, Observation, the active option in an encre fill;
    *options* (key, label, tooltip) for another exclusive choice."""

    def __init__(self, current, on_change, options=None, legend=None):
        super().__init__()
        self.setObjectName("themeSelector")
        self.setAccessibleName(legend or t("theme.legend"))
        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(4)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons = {}
        if options is None:
            options = [(key, t(f"theme.{key}"), t(f"theme.{key}_tip")) for key in THEME_NAMES]
        for key, text, tip in options:
            btn = QPushButton(text)
            btn.setObjectName("themeOption")
            btn.setCheckable(True)
            btn.setFixedHeight(32)
            btn.setToolTip(tip)
            btn.setFocusPolicy(Qt.FocusPolicy.TabFocus)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setChecked(key == current)
            self.group.addButton(btn)
            lay.addWidget(btn, stretch=1)
            self.buttons[key] = btn
            btn.clicked.connect(lambda _checked, k=key: on_change(k))


# ── Application style ─────────────────────────────────────────────────────────

def _register_fonts():
    """Registers the fonts of fonts/; False when IBM Plex could not be loaded."""
    if os.path.isdir(_FONTS_DIR):
        for name in sorted(os.listdir(_FONTS_DIR)):
            if name.endswith(".ttf"):
                QFontDatabase.addApplicationFont(os.path.join(_FONTS_DIR, name))
    families = set(QFontDatabase.families())
    if FONT_SANS[0] in families and FONT_MONO[0] in families:
        _fonts.update(sans=FONT_SANS, mono=FONT_MONO)
        return True
    sans = next((f for f in _FALLBACK_SANS if f in families),
                QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont).family())
    mono = next((f for f in _FALLBACK_MONO if f in families),
                QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont).family())
    _fonts.update(sans=(sans,), mono=(mono,))
    return False


def init_style(app):
    """
    Astræos fonts, Fusion style, palette and style sheet of the application.
    To call once, after QApplication is created.
    """
    _register_fonts()
    font = QFont()
    font.setFamilies(list(_fonts["sans"]))
    font.setPixelSize(15)                       # "corps" style
    app.setFont(font)
    app.setStyle("Fusion")
    app.setWindowIcon(icons.app_icon())
    charts.configure_fonts()
    apply_theme(app)


def apply_theme(app):
    """Palette and style sheet of the active theme (``Config``)."""
    app.setPalette(_build_palette())
    app.setStyleSheet(build_stylesheet())


def _build_palette():
    C, role = Config, QPalette.ColorRole
    palette = QPalette()
    for r, color in (
        (role.Window, C.CIEL_000), (role.WindowText, C.ENCRE),
        (role.Base, C.CIEL_100), (role.AlternateBase, C.CIEL_000),
        (role.ToolTipBase, C.CIEL_100), (role.ToolTipText, C.ENCRE),
        (role.PlaceholderText, C.ENCRE_ATTENUEE), (role.Text, C.ENCRE),
        (role.Button, C.CIEL_100), (role.ButtonText, C.ENCRE),
        (role.BrightText, C.SIGNAL_ALERTE), (role.Highlight, C.CIEL_200),
        (role.HighlightedText, C.ENCRE), (role.Link, C.LUNE),
        (role.Light, C.CIEL_100), (role.Midlight, C.CIEL_100),
        (role.Mid, C.CIEL_200), (role.Dark, C.CIEL_000), (role.Shadow, C.CIEL_000),
    ):
        palette.setColor(r, QColor(color))
    off = mix(C.ENCRE, C.CIEL_100, 0.45)
    for r in (role.Text, role.ButtonText, role.WindowText):
        palette.setColor(QPalette.ColorGroup.Disabled, r, QColor(off))
    return palette


def _qss_family(families):
    return ", ".join(f'"{f}"' for f in families)


def build_stylesheet():
    """Qt style sheet of the active theme, after the Astræos components."""
    C = Config
    sans, mono = _qss_family(_fonts["sans"]), _qss_family(_fonts["mono"])
    or_hover, or_press = mix(C.OR, C.ENCRE, 0.85), mix(C.OR, C.ENCRE, 0.72)
    off = mix(C.ENCRE, C.CIEL_100, 0.45)                       # 45 % opacity
    pressed_hover = mix(C.ENCRE, C.CIEL_000, 0.85)
    pills = "\n".join(
        f'QLabel[badge="{tone}"] {{ color: {color}; border: 1px solid {_rgba(color, 0.45)}; }}'
        for tone, color in (("neutre", C.ENCRE_ATTENUEE), ("info", C.LUNE),
                           ("ok", C.SIGNAL_OK), ("alerte", C.SIGNAL_ALERTE)))
    return f"""
QWidget {{ color: {C.ENCRE}; font-family: {sans}; }}
QMainWindow, QDialog, QWidget#central, QWidget#page {{ background: {C.CIEL_000}; }}
QFrame#sidebar {{ background: {C.CIEL_100}; border: none; border-right: 1px solid {C.CIEL_200}; }}
QWidget#qt_scrollarea_viewport {{ background: transparent; }}
QScrollArea {{ background: transparent; border: none; }}
QLabel {{ background: transparent; }}
QToolTip {{
    background: {C.CIEL_100}; color: {C.ENCRE}; border: 1px solid {C.CIEL_200};
    border-radius: 4px; padding: 4px 8px; font-size: 13px;
}}

QFrame#card {{ background: {C.CIEL_100}; border: 1px solid {C.CIEL_200}; border-radius: 10px; }}

QLabel[textStyle="affiche"] {{ font-size: 40px; font-weight: 600; }}
QLabel[textStyle="titre"] {{ font-size: 24px; font-weight: 600; }}
QLabel[textStyle="sous-titre"] {{ font-size: 17px; font-weight: 600; }}
QLabel[textStyle="corps"] {{ font-size: 15px; }}
QLabel[textStyle="legende"] {{ font-size: 13px; color: {C.ENCRE_ATTENUEE}; }}
QLabel[textStyle="label"] {{ font-size: 13px; font-weight: 600; }}
QLabel[textStyle="section"] {{ font-size: 13px; font-weight: 600; color: {C.ENCRE_ATTENUEE}; }}
QLabel[textStyle="donnee"] {{ font-family: {mono}; font-size: 15px; font-weight: 500; }}
QLabel[textStyle="cadran"] {{ font-family: {mono}; font-size: 32px; font-weight: 500; }}
QLabel[textStyle="symbol"] {{ font-family: "Astraeos Symboles"; font-size: 20px; }}
QLabel[strong="true"] {{ font-weight: 600; }}
QLabel[tone="attenuee"] {{ color: {C.ENCRE_ATTENUEE}; }}
QLabel[tone="or"] {{ color: {C.OR}; }}
QLabel[tone="lune"] {{ color: {C.LUNE}; }}
QLabel[tone="alerte"] {{ color: {C.SIGNAL_ALERTE}; }}

QLabel[badge="neutre"], QLabel[badge="info"], QLabel[badge="ok"], QLabel[badge="alerte"] {{
    font-size: 13px; font-weight: 600; border-radius: 12px; padding: 0px 8px;
}}
{pills}

QPushButton {{
    background: transparent; color: {C.ENCRE}; border: 1px solid {C.ENCRE_ATTENUEE};
    border-radius: 10px; padding: 0px 16px; font-size: 15px; font-weight: 600;
}}
QPushButton:hover {{ background: {C.CIEL_200}; border-color: {C.ENCRE}; }}
QPushButton:focus {{ border: 2px solid {C.OR}; padding: 0px 15px; }}
QPushButton:checked {{ background: {C.ENCRE}; border-color: {C.ENCRE}; color: {C.CIEL_000}; }}
QPushButton:checked:hover {{ background: {pressed_hover}; }}
QPushButton:disabled {{ color: {off}; border-color: {off}; }}
QPushButton[variant="principal"] {{ background: {C.OR}; color: {C.SUR_OR}; border-color: {C.OR}; }}
QPushButton[variant="principal"]:hover {{ background: {or_hover}; border-color: {or_hover}; }}
QPushButton[variant="principal"]:pressed {{ background: {or_press}; border-color: {or_press}; }}
QPushButton[variant="principal"]:focus {{ border: 2px solid {C.ENCRE}; }}
QPushButton[variant="discret"] {{ border-color: transparent; }}
QPushButton[variant="discret"]:hover {{ background: {C.CIEL_200}; border-color: {C.CIEL_200}; }}
QPushButton[variant="danger"] {{ color: {C.SIGNAL_ALERTE}; border-color: {C.SIGNAL_ALERTE}; }}
QPushButton[variant="danger"]:hover {{ background: {C.SIGNAL_ALERTE}; color: {C.CIEL_000}; }}
QPushButton[density="compact"] {{ border-radius: 4px; padding: 0px 12px; font-size: 13px; }}

QToolButton#iconButton {{ background: transparent; border: 1px solid transparent; border-radius: 20px; }}
QToolButton#iconButton[density="compact"] {{ border-radius: 16px; }}
QToolButton#iconButton[variant="secondaire"] {{ border-color: {C.ENCRE_ATTENUEE}; }}
QToolButton#iconButton:hover {{ background: {C.CIEL_200}; }}
QToolButton#iconButton:focus {{ border: 2px solid {C.OR}; }}
QToolButton#iconButton:checked {{ background: {C.ENCRE}; border-color: {C.ENCRE}; }}

QPushButton#themeOption {{
    background: transparent; border: none; border-radius: 4px; padding: 0px 10px;
    color: {C.ENCRE_ATTENUEE}; font-size: 13px; font-weight: 400;
}}
QPushButton#themeOption:hover {{ background: {C.CIEL_200}; color: {C.ENCRE}; }}
QPushButton#themeOption:checked {{ background: {C.ENCRE}; color: {C.CIEL_000}; font-weight: 600; }}
QPushButton#themeOption:focus {{ border: 2px solid {C.OR}; }}
QFrame#themeSelector {{ background: {C.CIEL_100}; border: 1px solid {C.CIEL_200}; border-radius: 10px; }}

QLineEdit, QComboBox, QDateTimeEdit {{
    background: {C.CIEL_100}; border: 1px solid {C.ENCRE_ATTENUEE}; border-radius: 4px;
    padding: 6px 12px; font-size: 15px;
    selection-background-color: {C.CIEL_200}; selection-color: {C.ENCRE};
}}
QLineEdit:focus, QComboBox:focus, QDateTimeEdit:focus {{ border: 2px solid {C.OR}; }}
QFrame#fieldBox {{ background: {C.CIEL_100}; border: 1px solid {C.ENCRE_ATTENUEE}; border-radius: 4px; }}
QFrame#fieldBox[hover="true"] {{ border-color: {C.ENCRE}; }}
QFrame#fieldBox[focused="true"] {{ border: 2px solid {C.OR}; }}
QFrame#fieldBox[error="true"] {{ border-color: {C.SIGNAL_ALERTE}; }}
QFrame#fieldBox[inactive="true"] {{ border-color: {off}; }}
QFrame#fieldBox QLineEdit, QFrame#fieldBox QComboBox, QFrame#fieldBox QDateTimeEdit {{
    background: transparent; border: none; padding: 0px 12px;
}}
QLineEdit[numeric="true"], QDateTimeEdit {{ font-family: {mono}; font-weight: 500; }}
QDateTimeEdit[readOnly="true"] {{ color: {C.ENCRE_ATTENUEE}; }}
QLabel#fieldUnit {{ padding-right: 12px; }}
/* Drop-down lists in list mode: height fitted to the content, a scroll bar
   only when the list is long (Qt's "menu" mode hid choices behind scroll
   arrows). */
QComboBox {{ combobox-popup: 0; }}
QComboBox QAbstractItemView {{
    background: {C.CIEL_100}; border: 1px solid {C.CIEL_200}; outline: 0;
    selection-background-color: {C.CIEL_200}; selection-color: {C.ENCRE};
}}
QComboBox QAbstractItemView::item {{ min-height: 30px; padding: 0 10px; }}
QComboBox QAbstractItemView::item:disabled {{ color: {C.ENCRE_ATTENUEE}; }}
QComboBox:disabled {{ color: {C.ENCRE_ATTENUEE}; }}

QTabWidget::pane {{ border: none; border-top: 1px solid {C.CIEL_200}; top: -1px; background: {C.CIEL_000}; }}
QTabBar::tab {{
    background: transparent; color: {C.ENCRE_ATTENUEE}; font-size: 14px; font-weight: 600;
    padding: 9px 8px; margin-right: 2px; border: none; border-bottom: 2px solid transparent;
}}
QTabBar::tab:hover {{ color: {C.ENCRE}; border-bottom-color: {C.ENCRE_ATTENUEE}; }}
QTabBar::tab:selected {{ color: {C.ENCRE}; border-bottom-color: {C.ENCRE}; }}

QTableWidget {{
    background: {C.CIEL_100}; border: 1px solid {C.CIEL_200}; border-radius: 10px;
    gridline-color: {C.CIEL_200}; font-size: 15px;
}}
QTableWidget::item {{ padding: 0px 12px; border-bottom: 1px solid {C.CIEL_200}; }}
QHeaderView::section {{
    background: {C.CIEL_100}; color: {C.ENCRE_ATTENUEE}; border: none;
    border-bottom: 1px solid {C.CIEL_200}; padding: 8px 12px; font-size: 13px; font-weight: 600;
}}
QTableCornerButton::section {{ background: {C.CIEL_100}; border: none; }}

QProgressBar {{ background: {C.CIEL_200}; border: none; border-radius: 4px; min-height: 8px; max-height: 8px; }}
QProgressBar::chunk {{ background: {C.LUNE}; border-radius: 4px; }}

QSlider::groove:horizontal {{ background: {C.CIEL_200}; height: 8px; border-radius: 4px; }}
QSlider::sub-page:horizontal {{ background: {C.LUNE}; border-radius: 4px; }}
QSlider::handle:horizontal {{
    background: {C.ENCRE}; width: 16px; height: 16px; margin: -4px 0; border-radius: 8px;
}}

QCheckBox {{ spacing: 8px; font-size: 15px; }}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {C.CIEL_200}; border-radius: 3px; min-height: 28px; }}
QScrollBar::handle:horizontal {{ background: {C.CIEL_200}; border-radius: 3px; min-width: 28px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QStatusBar {{
    background: {C.CIEL_000}; color: {C.ENCRE_ATTENUEE}; border-top: 1px solid {C.CIEL_200};
    font-size: 13px;
}}
QStatusBar::item {{ border: none; }}
QStatusBar QLabel {{ color: {C.ENCRE_ATTENUEE}; padding: 0 8px; font-size: 13px; }}

QCalendarWidget QWidget#qt_calendar_navigationbar {{ background: {C.CIEL_100}; }}
QCalendarWidget QToolButton {{ background: transparent; border: none; padding: 4px 8px; color: {C.ENCRE}; }}
QCalendarWidget QAbstractItemView {{
    background: {C.CIEL_100}; selection-background-color: {C.ENCRE}; selection-color: {C.CIEL_000};
}}
QMenu {{ background: {C.CIEL_100}; border: 1px solid {C.CIEL_200}; padding: 4px 0px; font-size: 15px; }}
QMenu::item {{ padding: 6px 16px; }}
QMenu::item:selected {{ background: {C.CIEL_200}; }}
QMenu::item:disabled {{ color: {C.ENCRE_ATTENUEE}; }}
QMenu::separator {{ height: 1px; background: {C.CIEL_200}; margin: 4px 0px; }}
"""


# ── Tooltips of the charts ────────────────────────────────────────────────────

class _TooltipLayer:
    """
    A matplotlib tooltip redrawn by blitting: hovering over it does not
    redraw the whole figure, only the tooltip.
    """

    def __init__(self, canvas):
        self.canvas = canvas
        self.artist = None
        self._background = None
        canvas.mpl_connect("draw_event", self._on_draw)

    def attach(self, artist):
        """A new tooltip, after a full redraw of the figure."""
        artist.set_animated(True)
        self.artist = artist
        self._background = None

    def _on_draw(self, _event):
        figure = self.canvas.figure
        self._background = self.canvas.copy_from_bbox(figure.bbox)
        if self.artist is not None and self.artist.get_visible():
            figure.draw_artist(self.artist)

    def hide(self):
        if self.artist is not None and self.artist.get_visible():
            self.artist.set_visible(False)
            self.refresh()

    def refresh(self):
        if self.artist is None:
            return
        if self._background is None:
            self.canvas.draw_idle()
            return
        self.canvas.restore_region(self._background)
        if self.artist.get_visible():
            self.canvas.figure.draw_artist(self.artist)
        self.canvas.blit(self.canvas.figure.bbox)


# ── Main class ────────────────────────────────────────────────────────────────

class OsmMap(QWidget):
    """
    A slippy map of OpenStreetMap tiles (Web Mercator): the wheel zooms around the
    pointer, a drag moves the map, a click puts the point (*on_pick(lat, lon)*). The
    tiles are kept in ~/.celeste/tiles for a week, as the tile usage policy of the
    OpenStreetMap Foundation asks; the attribution is drawn in a corner. Offline, the
    coastlines and the cities of Céleste's own lists stand in for the tiles.
    """
    URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
    CACHE = os.path.join(prefs.USER_DIR, "tiles")
    MAX_AGE_S = 7 * 86400
    TILE = 256
    fetch = True                           # False in the tests: no network

    def __init__(self, lat, lon, zoom, on_pick):
        super().__init__()
        self.lat, self.lon, self.zoom = lat, lon, zoom
        self.on_pick = on_pick
        self.marker = None
        self.tiles = {}                    # (z, x, y): QPixmap
        self.pending = set()
        self.failed = 0
        self._press = None
        self._net = None
        self.setMinimumHeight(380)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    # ── Web Mercator ──
    def _world(self, lat, lon, zoom=None):
        n = self.TILE * 2 ** (self.zoom if zoom is None else zoom)
        lat = max(-85.05, min(85.05, lat))
        x = (lon + 180.0) / 360.0 * n
        y = (1.0 - math.log(math.tan(math.radians(lat)) + 1.0 / math.cos(math.radians(lat))) / math.pi) / 2.0 * n
        return x, y

    def _latlon(self, x, y):
        n = self.TILE * 2 ** self.zoom
        lon = x / n * 360.0 - 180.0
        lat = math.degrees(math.atan(math.sinh(math.pi * (1.0 - 2.0 * y / n))))
        return lat, ((lon + 180.0) % 360.0) - 180.0

    def _origin(self):
        cx, cy = self._world(self.lat, self.lon)
        return cx - self.width() / 2.0, cy - self.height() / 2.0

    def to_screen(self, lat, lon):
        x, y = self._world(lat, lon)
        ox, oy = self._origin()
        return x - ox, y - oy

    def to_latlon(self, px, py):
        ox, oy = self._origin()
        return self._latlon(ox + px, oy + py)

    # ── tiles ──
    def _path(self, z, x, y):
        return os.path.join(self.CACHE, str(z), str(x), f"{y}.png")

    def _tile(self, z, x, y):
        key = (z, x, y)
        if key in self.tiles:
            return self.tiles[key]
        path = self._path(z, x, y)
        try:
            fresh = time.time() - os.path.getmtime(path) < self.MAX_AGE_S
        except OSError:
            fresh = None
        if fresh is not None:
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                self.tiles[key] = pixmap
                if fresh:
                    return pixmap
        if self.fetch and key not in self.pending and self.failed < 8:
            self._request(key)
        return self.tiles.get(key)

    def _request(self, key):
        from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest
        if self._net is None:
            self._net = QNetworkAccessManager(self)
        z, x, y = key
        request = QNetworkRequest(QUrl(self.URL.format(z=z, x=x, y=y)))
        request.setRawHeader(b"User-Agent", f"Celeste/{APP_VERSION} (+{_URL_REPO})".encode())
        self.pending.add(key)
        reply = self._net.get(request)
        reply.finished.connect(lambda r=reply, k=key: self._received(r, k))

    def _received(self, reply, key):
        self.pending.discard(key)
        data = bytes(reply.readAll())
        ok = reply.error() == reply.NetworkError.NoError and data[:8] == b"\x89PNG\r\n\x1a\n"
        reply.deleteLater()
        if not ok:
            self.failed += 1
            self.update()
            return
        self.failed = 0
        path = self._path(*key)
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as f:
                f.write(data)
        except OSError:
            pass
        pixmap = QPixmap()
        pixmap.loadFromData(data, "PNG")
        self.tiles[key] = pixmap
        self.update()

    # ── drawing ──
    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(Config.CIEL_000))
        ox, oy = self._origin()
        n = 2 ** self.zoom
        missing = False
        tx0, ty0 = int(ox // self.TILE), int(oy // self.TILE)
        tx1, ty1 = int((ox + self.width()) // self.TILE), int((oy + self.height()) // self.TILE)
        tiles = []
        for ty in range(max(ty0, 0), min(ty1, n - 1) + 1):
            for tx in range(tx0, tx1 + 1):
                pixmap = self._tile(self.zoom, tx % n, ty)
                tiles.append((tx, ty, pixmap))
                missing |= pixmap is None
        if missing:                                     # offline (or loading): Céleste's own map
            self._draw_offline(p)
        for tx, ty, pixmap in tiles:
            if pixmap is not None:
                p.drawPixmap(QPointF(tx * self.TILE - ox, ty * self.TILE - oy), pixmap)
        if self.marker:
            x, y = self.to_screen(*self.marker)
            p.setPen(QPen(QColor(Config.CIEL_000), 2))
            p.setBrush(QColor(Config.OR))
            p.drawEllipse(QPointF(x, y - 14), 8, 8)
            path = QPainterPath()
            path.moveTo(x, y)
            path.lineTo(x - 7, y - 10)
            path.lineTo(x + 7, y - 10)
            path.closeSubpath()
            p.drawPath(path)
        text = t("picker.osm_credit")
        font = QFont(self.font())
        font.setPixelSize(11)
        p.setFont(font)
        width = p.fontMetrics().horizontalAdvance(text) + 12
        box = QRectF(self.width() - width, self.height() - 18, width, 18)
        p.fillRect(box, QColor(255, 255, 255, 200))
        p.setPen(QColor("#333333"))
        p.drawText(box, int(Qt.AlignmentFlag.AlignCenter), text)
        if missing and self.failed >= 8:
            p.setPen(QColor(Config.ENCRE_ATTENUEE))
            p.drawText(QRectF(8, 8, self.width() - 16, 18), int(Qt.AlignmentFlag.AlignLeft), t("picker.offline"))
        p.end()

    def _draw_offline(self, p):
        ox, oy = self._origin()
        p.setPen(QPen(QColor(Config.ENCRE_ATTENUEE), 0.8))
        p.setBrush(QColor(Config.CIEL_200))
        n = self.TILE * 2 ** self.zoom
        for lons, lats in charts.world_rings():
            for shift in (-n, 0.0, n):
                pts = [QPointF(*(lambda xy: (xy[0] - ox + shift, xy[1] - oy))(self._world(la, lo)))
                       for lo, la in zip(lons, lats)]
                if not any(-50 < q.x() < self.width() + 50 and -50 < q.y() < self.height() + 50 for q in pts):
                    continue
                path = QPainterPath()
                path.moveTo(pts[0])
                for q in pts[1:]:
                    path.lineTo(q)
                p.drawPath(path)
        lat0, lon0 = self.to_latlon(0, self.height())
        lat1, lon1 = self.to_latlon(self.width(), 0)
        font = QFont(self.font())
        font.setPixelSize(11)
        p.setFont(font)
        for n_city, city in enumerate(places.in_box(lat0, lat1, lon0, lon1, limit=400)):
            x, y = self.to_screen(city["lat"], city["lon"])
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(Config.ENCRE_ATTENUEE))
            p.drawEllipse(QPointF(x, y), 2, 2)
            if n_city < 25:
                p.setPen(QColor(Config.ENCRE))
                p.drawText(QPointF(x + 4, y + 4), city["name"])

    # ── interaction ──
    def set_view(self, lat, lon, zoom=None):
        self.lat, self.lon = lat, lon
        if zoom is not None:
            self.zoom = max(2, min(18, int(zoom)))
        self.update()

    def zoom_by(self, step, at=None):
        zoom = max(2, min(18, self.zoom + step))
        if zoom == self.zoom:
            return
        if at is not None:                               # keep the point under the pointer in place
            lat, lon = self.to_latlon(*at)
            self.zoom = zoom
            x, y = self._world(lat, lon)
            cx, cy = x - at[0] + self.width() / 2.0, y - at[1] + self.height() / 2.0
            self.lat, self.lon = self._latlon(cx, cy)
        else:
            self.zoom = zoom
        self.update()

    def wheelEvent(self, event):
        pos = event.position()
        self.zoom_by(1 if event.angleDelta().y() > 0 else -1, (pos.x(), pos.y()))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position()
            self._press = (pos.x(), pos.y(), False)
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        if self._press is None:
            return
        x0, y0, dragged = self._press
        pos = event.position()
        if not dragged and abs(pos.x() - x0) + abs(pos.y() - y0) < 5:
            return
        cx, cy = self._world(self.lat, self.lon)
        self.lat, self.lon = self._latlon(cx - (pos.x() - x0), cy - (pos.y() - y0))
        self._press = (pos.x(), pos.y(), True)
        self.update()

    def mouseReleaseEvent(self, event):
        press, self._press = self._press, None
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        if press is None or press[2]:
            return
        pos = event.position()
        self.on_pick(*self.to_latlon(pos.x(), pos.y()))


class PlacePicker(QDialog):
    """
    The place chosen on an OpenStreetMap map: the wheel zooms, a drag moves the
    map, a click puts the point; a city's name takes the map there. For a computer
    whose location service cannot be allowed (or gives nothing), and more precise
    than the position of the IP.
    """

    def __init__(self, parent, lat, lon):
        super().__init__(parent)
        self.setWindowTitle(t("picker.title"))
        self.setMinimumSize(760, 600)
        self.chosen = None                    # (lat, lon)
        self.name = ""
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 24, 24, 16)
        lay.setSpacing(12)
        lay.addWidget(_label(t("picker.hint"), "legende", wrap=True))
        self.search = QLineEdit()
        self.search.setPlaceholderText(t("picker.search_placeholder"))
        self.search.setClearButtonEnabled(True)
        self.search.returnPressed.connect(self._find)
        lay.addWidget(InputField(t("side.place"), self.search))
        self.map = OsmMap(lat, lon, 10, self.choose)
        lay.addWidget(self.map, stretch=1)
        self.status = _label(t("picker.none"), "corps", wrap=True)
        lay.addWidget(self.status)
        row = QHBoxLayout()
        zoom_in = _icon_button("zoom_in", t("picker.zoom_in"), compact=True)
        zoom_out = _icon_button("zoom_out", t("picker.zoom_out"), compact=True)
        zoom_in.clicked.connect(lambda _c=False: self.map.zoom_by(1))
        zoom_out.clicked.connect(lambda _c=False: self.map.zoom_by(-1))
        row.addWidget(zoom_in)
        row.addWidget(zoom_out)
        row.addStretch()
        cancel = _button(t("picker.cancel"))
        cancel.clicked.connect(self.reject)
        self.use = _button(t("picker.use"), "place", "principal")
        self.use.setEnabled(False)
        self.use.clicked.connect(self.accept)
        row.addWidget(cancel)
        row.addWidget(self.use)
        lay.addLayout(row)

    def choose(self, lat, lon, name=None):
        self.chosen = (lat, lon)
        self.map.marker = (lat, lon)
        near = places.nearest(lat, lon, max_km=30.0)
        self.name = name if name is not None else (near["name"] if near else "")
        where = f"{_fmt_lat(lat)}, {_fmt_lon(lon)}"
        if near:
            km = places.distance_km(lat, lon, near["lat"], near["lon"])
            self.status.setText(tf("picker.near", point=where, city=places.label(near), km=_num(km, 1)))
        else:
            self.status.setText(tf("picker.point", point=where))
        self.use.setEnabled(True)
        self.map.update()

    def _find(self):
        found = places.search(self.search.text(), limit=1)
        if not found:
            self.status.setText(tf("side.place_unknown", name=self.search.text().strip()))
            return
        city = found[0]
        self.map.set_view(city["lat"], city["lon"], 13)
        self.choose(city["lat"], city["lon"], city["name"])


class AstroApp(QMainWindow):
    """Main window of Céleste."""

    def __init__(self):
        super().__init__()
        self.resize(1400, 880)
        self.setMinimumSize(1180, 720)
        self.setWindowIcon(icons.app_icon())

        # State
        self.live_mode           = False
        self.tz_name             = prefs.get("default_tz") or _AUTO_ZONE
        self._zone               = _zone(self.tz_name, _pref_float("default_lat", 49.6333),
                                         _pref_float("default_lon", -1.6167))
        self.location_name       = _clean_place(prefs.get("default_place"))
        self.favorites           = self._load_favorites()
        self.sun_data            = {}
        self.moon_data           = {}
        self.sun_events          = {}
        self.planet_events     = {}
        self.moon_events         = {}
        self.planets             = []
        self.minor_planets       = []
        self.visible_stars       = []
        self.visible_planets_map = []
        self.hours               = []
        self._day_start          = None      # local midnight of the computed day, in UT
        self._geo_source         = None      # request to the location service under way
        self.sun_altitudes       = []
        self.moon_altitudes      = []
        self.last_cache_key      = ""
        self._dte = self._lat = self._lon = None
        self._sky_scene          = None
        self._sky_objects        = []
        self._sky_hover          = None
        self._dirty              = set()
        self._last_search        = None
        self.history             = history.load()
        self._sky_found          = None      # the object found by name on the sky map (its reference)
        self._plan               = None      # the night planner's last result
        self._plan_key           = None      # (night, place, settings) it was computed for
        self._plan_busy          = False
        self._mpc_comets         = None      # comet elements of the Minor Planet Center, once loaded
        self._deep_sky_all       = []        # the 110 Messier objects at the computed instant
        self._history_pending    = None      # the calculation shown, not yet in the history
        self._history_quiet      = False     # a calculation the user did not ask for (start, rebuild)

        # Timers: real time, delayed recalculation after typing, history
        self._live_timer = QTimer(self)
        self._live_timer.timeout.connect(self._live_tick)
        self._recalc_timer = QTimer(self)
        self._recalc_timer.setSingleShot(True)
        self._recalc_timer.timeout.connect(self.calculate)
        self._history_timer = QTimer(self)
        self._history_timer.setSingleShot(True)
        self._history_timer.timeout.connect(self._commit_history)

        # Shortcuts, attached to the window: they survive the rebuilds
        for keys, slot in ((("F5", "Ctrl+Return"), self.calculate),
                           (("Ctrl+L",), lambda: self.btn_live.toggle()),
                           (("Ctrl+H",), lambda: self._show_history_menu())):
            for key in keys:
                QShortcut(QKeySequence(key), self).activated.connect(slot)

        self._build_ui()
        self._calculate_quietly()

    # ──────────────────────────────────────────────────────────────────────────
    # BUILDING THE INTERFACE
    # ──────────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        """Builds (or rebuilds) the whole window in the active language and theme."""
        self.setWindowTitle(t("app.title"))
        central = QWidget()
        central.setObjectName("central")
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._scrolling_sidebar(self._build_sidebar()))

        main = QWidget()
        main.setObjectName("central")
        main_l = QVBoxLayout(main)
        main_l.setContentsMargins(16, 8, 16, 0)
        self.tabs = QTabWidget()
        self.tabs.tabBar().setDrawBase(False)
        self.tabs.tabBar().setExpanding(False)
        main_l.addWidget(self.tabs)
        root.addWidget(main, stretch=1)

        self._chart_tabs = {}
        self._chart_hints = {}
        self._build_ephemeris_tab()
        self._build_trajectories_tab()
        self._build_skymap_tab()
        self._build_planets_tab()
        self._build_solar_system_tab()
        self._build_coordinates_tab()
        self._build_events_tab()
        self._build_planner_tab()
        self._build_settings_tab()
        self.tabs.currentChanged.connect(self._on_tab_changed)

        self.setCentralWidget(central)
        self._build_status_bar()
        # Otherwise the date field gets the focus with its day selected
        self.tabs.setFocus()

    # ── Side panel ────────────────────────────────────────────────────────────

    def _build_sidebar(self):
        side = QFrame()
        side.setObjectName("sidebar")
        lay = QVBoxLayout(side)
        lay.setContentsMargins(24, 24, 24, 16)
        lay.setSpacing(12)

        # Header: the Astræos symbol, then the application's name
        head = QHBoxLayout()
        head.setSpacing(12)
        mark = QLabel()
        mark.setPixmap(icons.symbol_pixmap(32, Config.ENCRE, Config.OR))
        mark.setAccessibleName("Astræos")
        head.addWidget(mark, alignment=Qt.AlignmentFlag.AlignTop)
        titles = QVBoxLayout()
        titles.setSpacing(0)
        titles.addWidget(_label(t("app.header"), "titre"))
        titles.addWidget(_label(t("app.subtitle"), "legende"))
        head.addLayout(titles, stretch=1)
        lay.addLayout(head)

        # Date and time (UT)
        self.dt_edit = QDateTimeEdit()
        if hasattr(self.dt_edit, "setTimeZone"):
            self.dt_edit.setTimeZone(_utc_zone())
        else:
            self.dt_edit.setTimeSpec(Qt.TimeSpec.UTC)
        self.dt_edit.setDisplayFormat(_QT_DATETIME_FORMAT)
        # dates covered by the JPL DE440 ephemeris
        self.dt_edit.setMinimumDate(QDate(EPHEMERIS_YEARS[0], 1, 1))
        self.dt_edit.setMaximumDate(QDate(EPHEMERIS_YEARS[1], 12, 31))
        self.dt_edit.setCalendarPopup(True)
        self.dt_edit.setToolTip(t("side.datetime_tip"))
        self._set_datetime(_utc_now())
        self.dt_edit.dateTimeChanged.connect(lambda _dt: self._schedule_recalc())
        self.field_date = InputField(t("side.datetime"), self.dt_edit)
        self.btn_now = _icon_button("now", t("side.now_tip"))
        self.btn_now.clicked.connect(self.set_now)
        lay.addLayout(self._with_button(self.field_date, self.btn_now))

        # Place: a city searched by its name (GeoNames, offline), or its coordinates
        self.entry_place = QLineEdit()
        self.entry_place.setPlaceholderText(t("side.place_placeholder"))
        self.entry_place.setToolTip(t("side.place_tip"))
        self.entry_place.setClearButtonEnabled(True)
        self._place_model = QStringListModel(self)
        self._place_found = {}
        self._place_completer = QCompleter(self._place_model, self)
        self._place_completer.setCompletionMode(QCompleter.CompletionMode.UnfilteredPopupCompletion)
        self._place_completer.setMaxVisibleItems(10)
        self._place_completer.activated.connect(self._on_place_chosen)
        self.entry_place.setCompleter(self._place_completer)
        self.entry_place.textEdited.connect(self._on_place_typed)
        self.entry_place.returnPressed.connect(self._on_place_return)
        lay.addWidget(InputField(t("side.place"), self.entry_place))

        validator = QRegularExpressionValidator(QRegularExpression(_COORD_REGEX))
        self.entry_lat = QLineEdit(_coord_text(_pref_float("default_lat", 49.6333)))
        self.entry_lon = QLineEdit(_coord_text(_pref_float("default_lon", -1.6167)))
        self.field_lat = InputField(t("side.latitude"), self.entry_lat, unit="°",
                                     numeric=True)
        self.field_lon = InputField(t("side.longitude"), self.entry_lon, unit="°",
                                     numeric=True)
        for edit, key in ((self.entry_lat, "latitude"), (self.entry_lon, "longitude")):
            edit.setValidator(validator)
            edit.setToolTip(t(f"side.{key}_tip"))
            edit.returnPressed.connect(self.calculate)
            edit.textEdited.connect(self._on_coords_edited)
        btn_map = _icon_button("map", t("side.map_tip"))
        btn_map.clicked.connect(lambda _checked=False: self.choose_on_map())
        lay.addLayout(self._with_button(self.field_lat, btn_map))
        btn_geo = _icon_button("geolocate", t("side.geoloc_tip"))
        btn_geo.clicked.connect(lambda _checked=False: self.geolocate())
        lay.addLayout(self._with_button(self.field_lon, btn_geo))

        self.entry_elev = QLineEdit(_elev_text(_pref_float("default_elevation", 0.0)))
        self.entry_elev.setValidator(QRegularExpressionValidator(QRegularExpression(r"^-?\d{0,4}$")))
        self.entry_elev.setToolTip(t("side.elevation_tip"))
        self.entry_elev.returnPressed.connect(self.calculate)
        lay.addWidget(InputField(t("side.elevation"), self.entry_elev, unit="m", numeric=True))

        # IANA time zone (summer time included), typed or chosen; "Automatic" follows the place
        self.tz_menu = QComboBox()
        self.tz_menu.setEditable(True)
        self.tz_menu.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.tz_menu.setMaxVisibleItems(14)
        self.tz_menu.addItem(t("side.timezone_auto"), _AUTO_ZONE)
        for name in _zone_names():
            self.tz_menu.addItem(name, name)
        completer = self.tz_menu.completer()
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self._select_zone(self.tz_name)
        self.tz_menu.setToolTip(t("side.timezone_tip"))
        self.tz_menu.currentIndexChanged.connect(self._on_zone_change)
        lay.addWidget(InputField(t("side.timezone"), self.tz_menu))

        self.combo_fav = QComboBox()
        self.combo_fav.setPlaceholderText(t("side.favorites_placeholder"))
        self.combo_fav.setMinimumContentsLength(6)
        self._refresh_favorites_combo()
        self.combo_fav.activated.connect(self._apply_favorite)
        fav_add = _icon_button("favorite_add", t("side.fav_save_tip"))
        fav_add.clicked.connect(self.save_location)
        fav_del = _icon_button("delete", t("side.fav_delete_tip"))
        fav_del.clicked.connect(self.delete_location)
        lay.addLayout(self._with_button(InputField(t("side.favorites"), self.combo_fav),
                                        fav_add, fav_del))

        # Actions: Calculate is the only gold area of the screen
        lay.addSpacing(4)
        self.btn_calc = _button(t("side.calculate"), "calculate", "principal")
        self.btn_calc.setToolTip(tf("side.calculate_tip", key="F5"))
        self.btn_calc.clicked.connect(self.calculate)
        lay.addWidget(self.btn_calc)
        self.btn_live = _button(t("side.live"), "live", "secondaire", checkable=True)
        self.btn_live.setToolTip(tf("side.live_tip", key="Ctrl+L"))
        self.btn_live.toggled.connect(self.toggle_live)
        lay.addWidget(self.btn_live)
        self.btn_history = _button(t("side.history"), "history", "discret")
        self.btn_history.setToolTip(tf("side.history_tip", key="Ctrl+H"))
        self.btn_history.clicked.connect(self._show_history_menu)
        lay.addWidget(self.btn_history)
        self.btn_workshop = _button(t("workshop.open"), "workshop", "discret")
        self.btn_workshop.setToolTip(t("workshop.open_tip"))
        self.btn_workshop.clicked.connect(lambda _checked=False: self.show_workshop())
        lay.addWidget(self.btn_workshop)

        lay.addStretch()
        self.theme_selector = ThemeSelector(Config.THEME, self._on_theme_selected)
        lay.addWidget(self.theme_selector)
        lay.addWidget(_label(tf("app.version", version=_version_text()), "legende"))
        return side

    @staticmethod
    def _scrolling_sidebar(side):
        """The side panel, which scrolls when the window is lower than it
        (screens 768 pixels high)."""
        side.setMinimumWidth(280)          # otherwise its natural width (337) would overflow 312
        scroll = QScrollArea()
        scroll.setObjectName("sidebarScroll")
        scroll.setWidget(side)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        bar = scroll.verticalScrollBar()

        def fit(_low=0, high=0):            # the scroll bar adds to the 312 pixels
            scroll.setFixedWidth(312 + (bar.sizeHint().width() if high > 0 else 0))
        bar.rangeChanged.connect(fit)
        fit()
        return scroll

    @staticmethod
    def _with_button(field, *buttons):
        """A field and round buttons aligned on its input box."""
        row = QHBoxLayout()
        row.setSpacing(4)
        row.addWidget(field, stretch=1)
        for btn in buttons:
            row.addWidget(btn, alignment=Qt.AlignmentFlag.AlignBottom)
        return row

    # ── Tab 1: ephemeris ──────────────────────────────────────────────────────

    def _build_ephemeris_tab(self):
        scroll, _page, lay = _scroll_page()

        # The values read at a glance
        cards = QHBoxLayout()
        cards.setSpacing(16)
        self.card_sun_alt = DataCard(t("cards.sun_alt"), SYMBOL["Sun"], "or")
        self.card_sun_rise = DataCard(t("cards.sun_rise"), SYMBOL["Sun"], "or")
        self.card_moon_alt = DataCard(t("cards.moon_alt"), SYMBOL["Moon"], "lune")
        self.card_moon_illum = DataCard(t("cards.moon_illum"), SYMBOL["Moon"], "lune")
        for card in (self.card_sun_alt, self.card_sun_rise, self.card_moon_alt,
                     self.card_moon_illum):
            cards.addWidget(card, stretch=1)
        lay.addLayout(cards)

        # Tonight: the night, the Moon, the visible planets and the next events
        card = _card()
        card.setObjectName("card")
        outer = QVBoxLayout(card)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(6)
        head = QHBoxLayout()
        head.setSpacing(8)
        head.addWidget(_label(SYMBOL["star"], "symbol", tone="or"))
        head.addWidget(_label(t("tonight.title"), "sous-titre"))
        head.addStretch()
        outer.addLayout(head)
        self._tonight_box = QVBoxLayout()
        self._tonight_box.setSpacing(6)
        outer.addLayout(self._tonight_box)
        self._tonight_key = None
        lay.addWidget(card)

        row = QHBoxLayout()
        row.setSpacing(16)

        # Sun
        card, body, self._lbl_sun_state = self._body_card(SYMBOL["Sun"], "or", t("sun.title"))
        self.sun_labels = {}
        r = self._section_rows(body, 0, t("sun.section_position"), [
            ("ra", "sun.ra"), ("dec", "sun.dec"), ("alt", "sun.alt"),
            ("az", "sun.az"), ("eot", "sun.eot"), ("dist", "sun.dist"),
        ], self.sun_labels)
        self._sun_events_title = _label("", "section")
        self._section_rows(body, r, self._sun_events_title, [
            ("dawn_astro", "sun.dawn_astro"), ("dawn_naut", "sun.dawn_naut"),
            ("dawn_civ", "sun.dawn_civil"), ("rise", "sun.rise", True),
            ("transit", "sun.transit"), ("set", "sun.set", True),
            ("dusk_civ", "sun.dusk_civil"), ("dusk_naut", "sun.dusk_naut"),
            ("dusk_astro", "sun.dusk_astro"), ("day_length", "sun.day_length"),
        ], self.sun_labels)
        row.addWidget(card, stretch=1)

        # Moon
        card, body, self._lbl_moon_state = self._body_card(SYMBOL["Moon"], "lune", t("moon.title"))
        btn_calendar = _button(t("calendar.button"), "calendar", "secondaire", compact=True)
        btn_calendar.setToolTip(t("calendar.button_tip"))
        btn_calendar.clicked.connect(lambda _=False: self._show_moon_calendar())
        card.layout().itemAt(0).layout().insertWidget(3, btn_calendar)
        self.moon_labels = {}
        r = self._section_rows(body, 0, t("moon.section_position"), [
            ("ra", "moon.ra"), ("dec", "moon.dec"), ("alt", "moon.alt"),
            ("az", "moon.az"), ("dist", "moon.dist"),
        ], self.moon_labels)

        body.setRowMinimumHeight(r, 16)
        body.addWidget(_label(t("moon.section_phase"), "section"), r + 1, 0, 1, 2)
        r += 1
        phase_row = QHBoxLayout()
        phase_row.setSpacing(16)
        self._phase_disc = MoonPhase(56)
        phase_row.addWidget(self._phase_disc)
        phase_text = QVBoxLayout()
        phase_text.setSpacing(8)
        self._lbl_phase_name = _label("—", "sous-titre")
        phase_text.addWidget(self._lbl_phase_name)
        self._illum_bar = QProgressBar()
        self._illum_bar.setRange(0, 1000)
        self._illum_bar.setTextVisible(False)
        self._illum_bar.setAccessibleName(t("moon.illum"))
        phase_text.addWidget(self._illum_bar)
        phase_row.addLayout(phase_text, stretch=1)
        body.addLayout(phase_row, r + 1, 0, 1, 2)
        r = self._section_rows(body, r + 2, None, [
            ("illum", "moon.illum"), ("age", "moon.age"),
        ], self.moon_labels)

        self._moon_events_title = _label("", "section")
        self._section_rows(body, r, self._moon_events_title, [
            ("rise", "moon.rise", True), ("transit", "moon.transit"),
            ("set", "moon.set", True),
        ], self.moon_labels)
        row.addWidget(card, stretch=1)

        lay.addLayout(row)
        lay.addStretch()
        self.tabs.addTab(scroll, t("tabs.ephemeris"))

    def _body_card(self, symbol, accent, title):
        """Card of a body: (card, data grid, state badge)."""
        card = _card()
        outer = QVBoxLayout(card)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(12)
        head = QHBoxLayout()
        head.setSpacing(8)
        head.addWidget(_label(symbol, "symbol", tone=accent))
        head.addWidget(_label(title, "sous-titre"))
        head.addStretch()
        badge = _badge()
        head.addWidget(badge)
        outer.addLayout(head)
        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(6)
        grid.setColumnStretch(0, 1)
        outer.addLayout(grid)
        outer.addStretch()
        return card, grid, badge

    @staticmethod
    def _section_rows(grid, row, title, fields, labels):
        """
        Adds a heading (text, QLabel or None), then a "label … value" line per
        field (compact DataCard); returns the next row.
        Field: (key, translation key[, emphasised]).
        """
        if title is not None:
            if isinstance(title, str):
                title = _label(title, "section")
            if row:
                grid.setRowMinimumHeight(row, 16)
                row += 1
            grid.addWidget(title, row, 0, 1, 2)
            row += 1
        for key, text_key, *opt in fields:
            strong = bool(opt and opt[0])
            name = _label(t(text_key), "corps" if strong else "legende", strong=strong)
            grid.addWidget(name, row, 0)
            value = _label("—", "donnee", strong=strong)
            value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            grid.addWidget(value, row, 1)
            labels[key] = value
            row += 1
        return row

    # ── Tabs 2 and 3: charts ──────────────────────────────────────────────────

    def _chart_page(self, name, toolbar=None, hint=None):
        """Tab page: a matplotlib chart in a card."""
        page = QWidget()
        page.setObjectName("page")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 16, 0, 16)
        lay.setSpacing(8)
        if toolbar is not None:
            lay.addLayout(toolbar)
        card = _card()
        card_l = QVBoxLayout(card)
        card_l.setContentsMargins(8, 8, 8, 8)
        figure = Figure(facecolor=Config.CIEL_100)
        canvas = FigureCanvasQTAgg(figure)
        canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        card_l.addWidget(canvas)
        lay.addWidget(card, stretch=1)
        if hint:
            self._chart_hints[name] = _label(hint, "legende", wrap=True)
            lay.addWidget(self._chart_hints[name])
        self._chart_tabs[page] = name
        return page, figure, canvas

    def _build_trajectories_tab(self):
        page, self.fig_traj, self.canvas_traj = self._chart_page(
            "traj", hint=t("chart.hint"))
        self._traj_ax = None
        self._traj_tip = _TooltipLayer(self.canvas_traj)
        self.canvas_traj.mpl_connect("motion_notify_event", self._on_traj_hover)
        self.canvas_traj.mpl_connect("figure_leave_event",
                                     lambda _e: self._traj_tip.hide())
        self.tabs.addTab(page, t("tabs.trajectory"))

    def _build_skymap_tab(self):
        bar = QHBoxLayout()
        bar.setSpacing(12)
        bar.addWidget(_label(t("skymap.mag_limit"), "label"))
        self._mag_slider = QSlider(Qt.Orientation.Horizontal)
        self._mag_slider.setRange(10, 70)          # magnitude × 10
        self._mag_slider.setFixedWidth(240)
        self._mag_slider.setValue(int(round(self._mag_limit() * 10)))
        self._mag_slider.setToolTip(t("skymap.mag_tip"))
        self._mag_lbl = _label(_num(self._mag_limit(), 1), "donnee")
        self._mag_lbl.setMinimumWidth(36)
        self._mag_slider.valueChanged.connect(self._on_mag_changed)
        bar.addWidget(self._mag_slider)
        bar.addWidget(self._mag_lbl)
        bar.addSpacing(24)
        self._messier_box = QCheckBox(t("skymap.messier"))
        self._messier_box.setToolTip(t("skymap.messier_tip"))
        self._messier_box.setChecked(bool(prefs.get("show_messier")))
        self._messier_box.toggled.connect(self._on_messier_toggled)
        bar.addWidget(self._messier_box)
        bar.addStretch()
        # find a star, a planet, a Messier object or a constellation by its name
        self._find_entry = QLineEdit()
        self._find_entry.setPlaceholderText(t("skymap.find_placeholder"))
        self._find_entry.setToolTip(t("skymap.find_tip"))
        self._find_entry.setAccessibleName(t("skymap.find_tip"))
        self._find_entry.setClearButtonEnabled(True)
        self._find_entry.setFixedWidth(220)
        self._find_model = QStringListModel(self)
        self._find_matches = {}
        self._find_completer = QCompleter(self._find_model, self)
        self._find_completer.setCompletionMode(QCompleter.CompletionMode.UnfilteredPopupCompletion)
        self._find_completer.setMaxVisibleItems(10)
        self._find_completer.activated.connect(self._on_find_chosen)
        self._find_entry.setCompleter(self._find_completer)
        self._find_entry.textEdited.connect(self._on_find_typed)
        self._find_entry.returnPressed.connect(self._on_find_return)
        self._find_entry.textChanged.connect(lambda text: text or self._clear_found())
        if self._sky_found is not None:                   # rebuilt: the object found stays circled
            self._find_entry.blockSignals(True)
            self._find_entry.setText(self._target_label(self._sky_found))
            self._find_entry.blockSignals(False)
        bar.addWidget(self._find_entry)

        page, self.fig_sky, self.canvas_sky = self._chart_page(
            "sky", toolbar=bar, hint=t("skymap.hint"))
        self._sky_ax = None
        self._sky_tip = _TooltipLayer(self.canvas_sky)
        self.canvas_sky.mpl_connect("motion_notify_event", self._on_sky_hover)
        self.canvas_sky.mpl_connect("button_press_event", self._on_sky_click)
        self.canvas_sky.mpl_connect("figure_leave_event", self._on_sky_leave)
        self.tabs.addTab(page, t("tabs.skymap"))

    # ── Tab 4: planets ────────────────────────────────────────────────────────

    def _build_planets_tab(self):
        page = QWidget()
        page.setObjectName("page")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 16, 0, 16)
        lay.setSpacing(16)

        # all the bodies, or a group; only those above the horizon
        self._planet_group = prefs.get("planet_group") or "planets"
        if self._planet_group not in ("all",) + tuple(k for k, _names in _BODY_GROUPS):
            self._planet_group = "planets"
        options = [("all", t("planets.group_all"), t("planets.group_all_tip"))]
        options += [(key, t(f"planets.group_{key}"), t(f"planets.group_{key}_tip"))
                    for key, _names in _BODY_GROUPS]
        self._planet_selector = ThemeSelector(self._planet_group, self._on_planet_group, options,
                                               t("planets.group_legend"))
        self._planet_selector.setMaximumWidth(620)
        self._planet_visible = QCheckBox(t("planets.visible_only"))
        self._planet_visible.setToolTip(t("planets.visible_only_tip"))
        self._planet_visible.setChecked(bool(prefs.get("planet_visible_only")))
        self._planet_visible.toggled.connect(self._on_planet_visible)
        bar = QHBoxLayout()
        bar.setSpacing(24)
        bar.addWidget(self._planet_selector, stretch=1)
        bar.addWidget(self._planet_visible)
        bar.addStretch()
        lay.addLayout(bar)

        # visibility reads from the name's colour (bright above the horizon)
        columns = ["col_planet", "col_ra", "col_dec", "col_alt", "col_az", "col_dist",
                   "col_elong", "col_mag", "col_rise", "col_transit", "col_set"]
        bodies = tuple(name for _key, names in _BODY_GROUPS for name in names)
        table = QTableWidget(len(bodies), len(columns))
        table.setHorizontalHeaderLabels([t(f"planets.{c}") for c in columns])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        table.setShowGrid(False)
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        table.verticalHeader().setDefaultSectionSize(40)
        table.setStyleSheet("QTableWidget::item { padding: 0 2px; }")
        mono = QFont()
        mono.setFamilies(list(_fonts["mono"]))
        mono.setPixelSize(13)
        mono.setWeight(QFont.Weight.Medium)
        self._planet_items = {}
        for r, name in enumerate(bodies):
            items = {}
            for c, col in enumerate(columns):
                item = _SortItem("—")
                item.setData(_NAME_ROLE, name)
                item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                if col == "col_planet":
                    item.setText(_planet_name(name, symbol=True))
                    bold = QFont()
                    bold.setFamilies(list(_fonts["sans"]))
                    bold.setPixelSize(15)
                    bold.setWeight(QFont.Weight.DemiBold)
                    item.setFont(bold)
                else:
                    item.setFont(mono)
                table.setItem(r, c, item)
                items[col] = item
            items["col_planet"].setData(_SORT_ROLE, r)                # order of the Solar System
            self._planet_items[name] = items
        self.planet_table = table
        # a click on a body opens its data window
        table.cellClicked.connect(
            lambda row, _col: self._show_body_detail(table.item(row, 0).data(_NAME_ROLE)))
        table.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
        table.setToolTip(t("detail.click_tip"))
        # the last column stretches: never a horizontal scroll for a few pixels
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._planet_alt = {}
        self._planet_empty = _label("", "legende", tone="attenuee", wrap=True)
        self._planet_empty.hide()
        # click on a header: ascending then descending; "Planet": natural order.
        # The sorted column has a gold header (Qt's arrow would widen every column)
        table.setSortingEnabled(True)
        header.setSortIndicatorShown(False)
        table.sortItems(0, Qt.SortOrder.AscendingOrder)
        header.sortIndicatorChanged.connect(self._on_planet_sort)
        self._show_planet_group()
        lay.addWidget(table, stretch=100)                 # scrolls when the window is too low
        lay.addWidget(self._planet_empty)
        lay.addStretch(1)
        self.tabs.addTab(page, t("tabs.planets"))

    # ── Tab 5: Solar System ───────────────────────────────────────────────────

    def _build_solar_system_tab(self):
        """The Solar System seen from above, in its own tab since v4.9 (issue #35)."""
        page = QWidget()
        page.setObjectName("page")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 16, 0, 16)
        lay.setSpacing(16)
        card = _card()
        card_l = QVBoxLayout(card)
        card_l.setContentsMargins(8, 8, 8, 8)
        # animation: the orrery moves on from the chosen date
        bar = QHBoxLayout()
        bar.setContentsMargins(8, 4, 8, 0)
        bar.setSpacing(4)
        back = _icon_button("step_back", t("planets.orrery_back"), compact=True)
        back.clicked.connect(lambda: self._orrery_step(-1))
        self._orrery_play = _icon_button("play", t("planets.orrery_play"), compact=True)
        self._orrery_play.clicked.connect(self._toggle_orrery)
        forward = _icon_button("step_forward", t("planets.orrery_forward"), compact=True)
        forward.clicked.connect(lambda: self._orrery_step(+1))
        self._orrery_speed = QComboBox()
        for key, days in (("day", 1.0), ("week", 7.0), ("month", 30.0), ("year", 365.25)):
            self._orrery_speed.addItem(t(f"planets.orrery_speed_{key}"), days)
        self._orrery_speed.setCurrentIndex(1)
        self._orrery_speed.setToolTip(t("planets.orrery_speed_tip"))
        self._orrery_date = _label("", "donnee")
        reset = _button(t("planets.orrery_reset"), "reset", "discret", compact=True)
        reset.setToolTip(t("planets.orrery_reset_tip"))
        reset.clicked.connect(self._reset_orrery)
        for widget in (back, self._orrery_play, forward, self._orrery_speed):
            bar.addWidget(widget)
        bar.addSpacing(12)
        bar.addWidget(self._orrery_date)
        bar.addStretch()
        bar.addWidget(reset)
        card_l.addLayout(bar)
        if getattr(self, "_orrery_timer", None) is None:
            self._orrery_timer = QTimer(self)
            self._orrery_timer.setInterval(80)
            self._orrery_timer.timeout.connect(lambda: self._orrery_step(+1))
            self._orrery_offset = 0.0                     # days from the chosen date
        self._orrery_timer.stop()
        self.fig_orrery = Figure(facecolor=Config.CIEL_100)
        self.canvas_orrery = FigureCanvasQTAgg(self.fig_orrery)
        card_l.addWidget(self.canvas_orrery)
        lay.addWidget(card, stretch=1)
        self._chart_tabs[page] = "orrery"
        self.tabs.addTab(page, t("tabs.solar_system"))

    # ── Updates ───────────────────────────────────────────────────────────────

    def check_updates(self, interactive=True):
        """
        Looks for a newer version (GitHub Release). *interactive* (button):
        the answer always shows; at startup, only when there is a new version
        the user did not choose to skip.
        """
        if getattr(self, "_update_busy", False):
            return
        self._update_busy = True
        self._update_interactive = interactive
        self._update_info.setText(t("update.checking"))
        _run_in_background(updater.latest_release, self._on_release, self._on_update_error)

    def _on_release(self, release):
        self._update_busy = False
        interactive = self._update_interactive
        if release is None or not updater.is_newer(release["version"]):
            self._update_info.setText(tf("update.up_to_date", version=_version_text()))
            if interactive:
                self.statusBar().showMessage(tf("update.up_to_date", version=_version_text()), 8000)
            return
        self._update_info.setText(tf("update.available", version=release["version"],
                                       current=_version_text()))
        if interactive or prefs.get("update_skipped") != release["version"]:
            self._show_update_dialog(release)

    def _on_update_error(self, error):
        self._update_busy = False
        self._update_info.setText(tf("update.error", detail=error))
        if self._update_interactive:
            QMessageBox.warning(self, t("update.title"), tf("update.error", detail=error))

    def _show_update_dialog(self, release):
        """Window (non-modal): the new version, its notes, and what to do."""
        box = QMessageBox(QMessageBox.Icon.Information, t("update.title"),
                          tf("update.available", version=release["version"], current=_version_text()),
                          parent=self)
        box.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)           # once closed, it does not stay in memory
        notes = updater.plain_notes(release.get("notes", ""))
        if len(notes) > 800:
            notes = notes[:800].rsplit("\n", 1)[0] + "\n…"
        info = notes or ""
        if not updater.can_self_update():
            info = (info + "\n\n" if info else "") + t("update.from_source")
        box.setInformativeText(info)
        install = None
        if updater.can_self_update():
            install = box.addButton(t("update.install"), QMessageBox.ButtonRole.AcceptRole)
        page = box.addButton(t("update.open_page"), QMessageBox.ButtonRole.ActionRole)
        skip = box.addButton(t("update.skip"), QMessageBox.ButtonRole.DestructiveRole)
        box.addButton(t("update.later"), QMessageBox.ButtonRole.RejectRole)

        def done(_result):
            clicked = box.clickedButton()
            if install is not None and clicked is install:
                self._install_update(release)
            elif clicked is page:
                _open_url(release["page"])
            elif clicked is skip:
                prefs.set("update_skipped", release["version"])
        box.finished.connect(done)
        self._update_dialog = box
        box.open()

    def _install_update(self, release):
        """Downloads and checks the installer, runs it, then closes Céleste."""
        state = {"done": 0, "total": release.get("setup_size") or 0, "cancel": False,
                 "closing": False}
        progress = QProgressDialog(tf("update.downloading", version=release["version"]),
                                   t("update.cancel"), 0, 1000, self)
        progress.setWindowTitle(t("update.title"))
        progress.setMinimumDuration(0)
        # close() emits canceled too: only the Cancel button (or the window's ×)
        # before the end of the download is the user's cancellation
        progress.canceled.connect(lambda: state["closing"] or state.update(cancel=True))
        ticker = QTimer(progress)
        ticker.timeout.connect(lambda: progress.setValue(
            int(1000 * state["done"] / state["total"]) if state["total"] else 0))
        ticker.start(200)
        self._update_progress = progress

        def fetch():
            return updater.download(release, progress=lambda d, n: state.update(done=d, total=n),
                                    cancelled=lambda: state["cancel"])

        def finish():
            state["closing"] = True
            ticker.stop()
            progress.close()

        def downloaded(path):
            finish()
            self.statusBar().showMessage(tf("update.installing", version=release["version"]))
            updater.launch_installer(path)
            QTimer.singleShot(300, QApplication.instance().quit)

        def failed(error):
            cancelled = state["cancel"]
            finish()
            if not cancelled:
                self._show_update_failure(release, error)
        _run_in_background(fetch, downloaded, failed)

    def _show_update_failure(self, release, error):
        """Window (non-modal): why the download failed, the release page to
        install by hand, and the log."""
        box = QMessageBox(QMessageBox.Icon.Warning, t("update.title"),
                          tf("update.error", detail=error), parent=self)
        box.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        box.setInformativeText(tf("update.failed_hint", path=updater.log_path()))
        page = box.addButton(t("update.open_page"), QMessageBox.ButtonRole.ActionRole)
        box.addButton(QMessageBox.StandardButton.Close)

        def done(_result):
            if box.clickedButton() is page:
                _open_url(release["page"])
        box.finished.connect(done)
        self._update_failure = box
        box.open()

    def _on_planet_group(self, key):
        self._planet_group = key
        prefs.set("planet_group", key)
        self._show_planet_group()

    def _on_planet_visible(self, checked):
        prefs.set("planet_visible_only", bool(checked))
        self._show_planet_group()

    def _on_planet_sort(self, column, order):
        table = self.planet_table
        for c in range(table.columnCount()):
            item = table.horizontalHeaderItem(c)
            sorted_here = c == column and c != 0
            item.setForeground(QBrush(QColor(Config.OR)) if sorted_here else QBrush())
            item.setToolTip(t("planets.sorted_" + ("ascending" if order == Qt.SortOrder.AscendingOrder
                                                    else "descending")) if sorted_here else "")
        self._show_planet_group()


    def _show_planet_group(self):
        """Shows only the bodies of the chosen group, and only those above the
        horizon when "Visible only" is checked."""
        group = dict(_BODY_GROUPS).get(self._planet_group)
        visible_only = self._planet_visible.isChecked()
        table = self.planet_table
        shown = 0
        for r in range(table.rowCount()):
            name = table.item(r, 0).data(_NAME_ROLE)
            hide = bool((group is not None and name not in group) or (
                visible_only and float(self._planet_alt.get(name, 0.0)) <= 0.0)
                or (name in COMETS and name not in getattr(self, "_comets_now", ())))
            table.setRowHidden(r, hide)
            shown += not hide
        table.resizeColumnsToContents()
        self._planet_empty.setVisible(shown == 0)
        if self._planet_group == "comets":
            first, last = AstroEngine.comet_years()
            self._planet_empty.setText(tf("planets.no_comet", first=first, last=last,
                                          comets=", ".join(COMET_SHORT.get(c, c) for c in COMETS)))
        else:
            self._planet_empty.setText(t("planets.none_visible"))
        header = table.horizontalHeader()
        # as tall as its rows, less when the window is low: it then scrolls
        table.setMaximumHeight(40 * max(1, shown) + header.sizeHint().height() + 4)
        table.setMinimumHeight(min(table.maximumHeight(), 40 * 4 + header.sizeHint().height() + 4))

    # ── Coordinates tab ───────────────────────────────────────────────────────
    #    x, y, z and distance from the "cartesian" origin; two angles in the
    #    "angular" frame; magnitude, angle with the Sun, constellation.

    _COORD_CHOICES = (
        ("cartesian", AstroEngine.CENTERS, "coord_cartesian"),
        ("angular", AstroEngine.FRAMES, "coord_angular"),
        ("ecliptic_from", ("sun", "earth"), "coord_ecliptic_from"),
        ("angle", ("global",) + Formatters.ANGLE_FORMATS, "coord_angle_format"),
    )
    _COORD_COLUMNS = ("col_body", "col_x", "col_y", "col_z", "col_dist", "col_mag",
                      "col_sun_angle", "col_constellation", "angle1", "angle2")

    def _build_coordinates_tab(self):
        # eighteen bodies: the page scrolls when the window is too low
        page, _inner, lay = _scroll_page()

        row = QHBoxLayout()
        row.setSpacing(12)
        self.coord_menus = {}
        for key, options, pref in self._COORD_CHOICES:
            menu = QComboBox()
            for option in options:
                menu.addItem(t(f"coordinates.{key}_{option}"), option)
            menu.setCurrentIndex(max(0, menu.findData(prefs.get(pref))))
            menu.currentIndexChanged.connect(lambda _i, k=key: self._on_coord_choice(k))
            self.coord_menus[key] = menu
            row.addWidget(InputField(t(f"coordinates.{key}"), menu), stretch=1)
        lay.addLayout(row)

        table = QTableWidget(len(AstroEngine.BODIES), len(self._COORD_COLUMNS))
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        table.setShowGrid(False)
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        table.verticalHeader().setDefaultSectionSize(36)
        table.setStyleSheet("QTableWidget::item { padding: 0 2px; }")
        mono = QFont()
        mono.setFamilies(list(_fonts["mono"]))
        mono.setPixelSize(13)
        mono.setWeight(QFont.Weight.Medium)
        for r, body in enumerate(AstroEngine.BODIES):
            for c, col in enumerate(self._COORD_COLUMNS):
                item = QTableWidgetItem("—")
                item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                if col not in ("col_body", "col_constellation"):
                    item.setFont(mono)
                table.setItem(r, c, item)
        table.setFixedHeight(36 * table.rowCount() + header.sizeHint().height() + 4)
        self.coord_table = table
        table.cellClicked.connect(lambda row, _col: self._show_body_detail(AstroEngine.BODIES[row]))
        table.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
        table.setToolTip(t("detail.click_tip"))
        lay.addWidget(table)
        self._coord_note = _label("", "legende", wrap=True)
        lay.addWidget(self._coord_note)
        propose = _button(t("links.body_more"), variant="discret", compact=True)
        propose.setToolTip(t("links.body_tip"))
        propose.clicked.connect(lambda _checked=False: _open_url(_issue_url("body")))
        self._propose_body = propose
        row = QHBoxLayout()
        row.addWidget(propose)
        row.addStretch()
        lay.addLayout(row)
        lay.addStretch(1)
        self._coord_page = page
        self._sync_coord_menus()
        self.tabs.addTab(page, t("tabs.coordinates"))

    def _coord_choice(self, key):
        return self.coord_menus[key].currentData()

    def _sync_coord_menus(self):
        """The Sun / Earth choice only applies to ecliptic coordinates."""
        self.coord_menus["ecliptic_from"].setEnabled(self._coord_choice("angular") == "ecliptic")

    def _on_coord_choice(self, key):
        pref = dict((k, p) for k, _o, p in self._COORD_CHOICES)[key]
        prefs.set(pref, self._coord_choice(key))
        self._sync_coord_menus()
        self._refresh_coordinates()

    def _coord_angle_format(self):
        """Angle format of the table: its own, or the settings' ("global")."""
        fmt = self._coord_choice("angle")
        return fmt if fmt in Formatters.ANGLE_FORMATS else _angle_format()

    @staticmethod
    def _body_label(body):
        if body in ("sun", "moon"):
            return f"{charts.SYMBOL[body.capitalize()]} {t(f'chart.{body}')}"
        if body == "earth":
            return f"{charts.SYMBOL['Earth']} {t('coordinates.earth')}"
        symbol = charts.SYMBOL.get(body)
        name = t(f"planets.{body.lower()}")
        return f"{symbol} {name}" if symbol else name

    def _refresh_coordinates(self):
        """Table of the coordinates, computed when its tab is shown."""
        if self._lat is None or self.tabs.currentWidget() is not getattr(self, "_coord_page", None):
            return
        cartesian, angular, from_body = (self._coord_choice(k)
                                         for k in ("cartesian", "angular", "ecliptic_from"))
        # (origin, frame) of the angles: equatorial and horizontal seen from the place,
        # ecliptic seen from the Sun or the Earth
        if angular == "ecliptic":
            angle_system = ("heliocentric" if from_body == "sun" else "geocentric", "ecliptic")
        else:
            angle_system = ("topocentric", angular)
        angle_heads = {"ecliptic": ("col_lon", "col_lat"), "equatorial": ("col_ra", "col_dec"),
                       "horizontal": ("col_az", "col_alt")}[angular]
        heads = [t(f"coordinates.{c}") for c in self._COORD_COLUMNS[:-2]]
        self.coord_table.setHorizontalHeaderLabels(heads + [t(f"coordinates.{c}") for c in angle_heads])

        tc, elev = AstroEngine.julian_century_j2000(self._dte), self._elevation()
        fmt = self._coord_angle_format()
        seen = AstroEngine.observations(tc)
        for r, body in enumerate(AstroEngine.BODIES):
            xyz = AstroEngine.coordinates(tc, body, cartesian, "ecliptic", self._lat, self._lon, elev)
            ang = AstroEngine.coordinates(tc, body, *angle_system, self._lat, self._lon, elev)
            obs = seen[body]
            cells = [self._body_label(body)]
            cells += (["—"] * 4 if xyz is None else
                      [_num(xyz[k], 7) for k in ("x", "y", "z")] + [_num(xyz["dist"], 7)])
            if obs is None:
                cells += ["—"] * 3
            else:
                cells += [_num(obs["mag"], 2, signed=True),
                          "—" if obs["elongation"] is None else _deg(obs["elongation"], 1),
                          obs["constellation"]]
            if ang is None:
                cells += ["—", "—"]
            elif angular == "equatorial":
                cells += [_ra(ang["lon"] / 15.0, fmt), _dec(ang["lat"], fmt)]
            else:
                cells += [_az(ang["lon"], fmt), _dec(ang["lat"], fmt)]
            for c, text in enumerate(cells):
                self.coord_table.item(r, c).setText(text)
            self.coord_table.item(r, 7).setToolTip(t(f"constellations.{obs['constellation']}") if obs else "")
        self._coord_note.setText(" ".join((
            t(f"coordinates.note_cartesian_{cartesian}"),
            t(f"coordinates.note_angular_{angular if angular != 'ecliptic' else 'ecliptic_' + from_body}"),
            t("coordinates.note_observation"))))

    # ── Tab 7: events ─────────────────────────────────────────────────────────

    def _build_events_tab(self):
        page = QWidget()
        page.setObjectName("page")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 16, 0, 0)
        lay.setSpacing(16)

        bar = QHBoxLayout()
        bar.setSpacing(8)
        btn_cal = _button(t("astro_calendar.button"), "calendar", "secondaire")
        btn_cal.setToolTip(t("astro_calendar.button_tip"))
        btn_cal.clicked.connect(lambda _c=False: self.show_calendar())
        bar.addWidget(btn_cal)
        btn_ecl = _button(t("events.search_eclipses"), "search")
        btn_ecl.clicked.connect(self._search_eclipses_gui)
        btn_conj = _button(t("events.search_conjunctions"), "search")
        btn_conj.clicked.connect(self._search_conjunctions_gui)
        btn_sat = _button(t("satellites.search"), "search")
        btn_sat.setToolTip(t("satellites.search_tip"))
        btn_sat.clicked.connect(self._search_satellites_gui)
        bar.addWidget(btn_ecl)
        bar.addWidget(btn_conj)
        bar.addWidget(btn_sat)
        bar.addStretch()
        self._btn_ics = _button(t("events.export_ics"), "export")
        self._btn_ics.setToolTip(t("events.export_tip"))
        self._btn_ics.setEnabled(False)
        self._btn_ics.clicked.connect(self._export_ics)
        bar.addWidget(self._btn_ics)
        lay.addLayout(bar)
        options = QHBoxLayout()
        self._sat_visual = QCheckBox(t("satellites.visual"))
        self._sat_visual.setToolTip(t("satellites.visual_tip"))
        self._sat_visual.setChecked(bool(prefs.get("satellites_visual")))
        self._sat_visual.toggled.connect(lambda v: prefs.set("satellites_visual", bool(v)))
        options.addStretch()
        options.addWidget(self._sat_visual)
        lay.addLayout(options)

        # filters of the year's events
        self._evt_filter_bar = QWidget()
        row = QHBoxLayout(self._evt_filter_bar)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(20)
        self._evt_filters = {}
        for key in self._EVENT_GROUPS + ("visible",):
            box = QCheckBox(t(f"events.filter_{key}"))
            box.setChecked(key != "visible")
            box.toggled.connect(self._render_events)
            self._evt_filters[key] = box
            row.addWidget(box)
        row.addStretch()
        self._evt_filter_bar.hide()
        lay.addWidget(self._evt_filter_bar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        inner.setObjectName("page")
        self._evt_layout = QVBoxLayout(inner)
        self._evt_layout.setContentsMargins(0, 0, 8, 16)
        self._evt_layout.setSpacing(8)
        scroll.setWidget(inner)
        lay.addWidget(scroll, stretch=1)
        self._show_events_placeholder()
        self.tabs.addTab(page, t("tabs.events"))

    # ── Tab 8: settings ───────────────────────────────────────────────────────

    # ── Tab 8: night planner (targets of the night, after uptonight) ──────────

    _PLAN_TYPES = ("galaxy", "nebula", "planetary_nebula", "open_cluster", "globular_cluster",
                   "supernova_remnant", "galaxy_group", "star_cloud", "dark_nebula", "asterism", "double_star")

    _PLAN_LIMITS = {"altitude_min": (0, 90), "altitude_max": (0, 90), "airmass_max": (1, 40),
                    "fraction_min": (0, 100), "size_min": (0, 10000), "size_max": (0, 10000),
                    "moon_separation_min": (0, 180), "magnitude_max": (-30, 30),
                    "max_targets": (1, 1000), "comet_magnitude_max": (-30, 30)}

    def _plan_constraints(self):
        return {**planner.DEFAULTS, **(prefs.get("planner_constraints") or {})}

    def _build_planner_tab(self):
        page = QWidget()
        page.setObjectName("page")
        outer = QHBoxLayout(page)
        outer.setContentsMargins(0, 16, 0, 16)
        outer.setSpacing(16)
        c = self._plan_constraints()

        # left: the constraints
        side, _inner, form = _scroll_page()
        form.setContentsMargins(0, 0, 12, 0)
        form.setSpacing(12)
        side.setFixedWidth(320)
        side.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._plan_catalog = QComboBox()
        for key in planner.CATALOGS:
            self._plan_catalog.addItem(t(f"planner.catalog_{key}"), key)
        self._plan_catalog.setCurrentIndex(max(0, self._plan_catalog.findData(c["catalog"])))
        form.addWidget(InputField(t("planner.catalog"), self._plan_catalog))
        self._plan_fields = {}

        def number_row(keys):
            row = QHBoxLayout()
            row.setSpacing(8)
            for key, unit, decimals in keys:
                edit = QLineEdit("" if c[key] is None else _num(c[key], decimals))
                field = InputField(t(f"planner.{key}"), edit, unit=unit, numeric=True)
                field.setToolTip(t(f"planner.{key}_tip"))
                self._plan_fields[key] = (edit, field)
                row.addWidget(field, stretch=1)
            form.addLayout(row)

        number_row((("altitude_min", "°", 0), ("altitude_max", "°", 0)))
        number_row((("airmass_max", "", 1), ("fraction_min", "%", 0)))
        number_row((("size_min", "′", 0), ("size_max", "′", 0)))
        number_row((("moon_separation_min", "°", 0), ("magnitude_max", "", 1)))
        number_row((("max_targets", "", 0), ("comet_magnitude_max", "", 1)))
        self._plan_fields["fraction_min"][0].setText(_num(100 * c["fraction_min"], 0))
        self._plan_moon_lit = QCheckBox(t("planner.moon_from_illumination"))
        self._plan_moon_lit.setToolTip(t("planner.moon_from_illumination_tip"))
        self._plan_moon_lit.setChecked(bool(c["moon_separation_from_illumination"]))
        form.addWidget(self._plan_moon_lit)
        self._plan_mpc = QCheckBox(t("planner.mpc"))
        self._plan_mpc.setToolTip(t("planner.mpc_tip"))
        self._plan_mpc.setChecked(bool(prefs.get("planner_mpc")))
        form.addWidget(self._plan_mpc)
        types_head = QHBoxLayout()
        types_head.setSpacing(4)
        types_head.addWidget(_label(t("planner.types"), "label"), stretch=1)
        for key, on in (("types_all", True), ("types_none", False)):
            btn = _button(t(f"planner.{key}"), None, "discret", compact=True)
            btn.setToolTip(t(f"planner.{key}_tip"))
            btn.clicked.connect(lambda _c=False, v=on: [b.setChecked(v) for b in self._plan_types.values()])
            types_head.addWidget(btn)
        form.addLayout(types_head)
        self._plan_types = {}
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(4)
        chosen = set(c["types"] or ())
        for i, key in enumerate(self._PLAN_TYPES):
            box = QCheckBox(t(f"messier.type_{key}"))
            box.setChecked(not chosen or key in chosen)
            self._plan_types[key] = box
            grid.addWidget(box, i, 0)
        form.addLayout(grid)
        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        btn_custom = _button(t("planner.custom_btn"), "favorite_add", "secondaire", compact=True)
        btn_custom.setToolTip(t("planner.custom_tip"))
        btn_custom.clicked.connect(self._edit_custom_targets)
        btn_lists = _button(t("planner.lists_btn"), "history", "secondaire", compact=True)
        btn_lists.setToolTip(t("planner.lists_tip"))
        btn_lists.clicked.connect(self._edit_plan_lists)
        buttons.addWidget(btn_custom)
        buttons.addWidget(btn_lists)
        buttons.addStretch()
        form.addLayout(buttons)
        form.addStretch()
        outer.addWidget(side)

        # right: the night, the tables, the chart
        right = QVBoxLayout()
        right.setSpacing(12)
        bar = QHBoxLayout()
        bar.setSpacing(8)
        self._btn_plan = _button(t("planner.compute"), "search")
        self._btn_plan.setToolTip(t("planner.compute_tip"))
        self._btn_plan.clicked.connect(lambda _checked=False: self._compute_plan(force=True))
        bar.addWidget(self._btn_plan)
        self._plan_status = _label("", "legende", wrap=True)
        bar.addWidget(self._plan_status, stretch=1)
        self._btn_plan_export = _button(t("planner.export"), "export")
        self._btn_plan_export.setToolTip(t("planner.export_tip"))
        self._btn_plan_export.setEnabled(False)
        self._btn_plan_export.clicked.connect(self._export_plan)
        bar.addWidget(self._btn_plan_export)
        right.addLayout(bar)
        self._plan_summary = _label(t("planner.placeholder"), "corps", wrap=True)
        right.addWidget(self._plan_summary)

        self._plan_tabs = QTabWidget()
        self._plan_tables = {}
        for key, columns in (("deep_sky", ("col_target", "col_fraction", "col_best", "col_alt_max",
                                           "col_time_max", "col_transit", "col_type", "col_const", "col_mag",
                                           "col_size")),
                             ("bodies", ("col_body", "col_mag", "col_alt_max", "col_time_max", "col_transit",
                                         "col_best", "col_fraction")),
                             ("comets", ("col_comet", "col_mag", "col_earth", "col_sun", "col_alt_max",
                                         "col_time_max", "col_rise", "col_set"))):
            table = self._plan_table(columns)
            self._plan_tables[key] = table
            self._plan_tabs.addTab(table, t(f"planner.tab_{key}"))
        self._plan_tables["deep_sky"].itemSelectionChanged.connect(self._draw_plan_chart)
        self._plan_tables["bodies"].itemSelectionChanged.connect(self._draw_plan_chart)
        self._plan_tabs.currentChanged.connect(lambda _i: self._draw_plan_chart())
        table = self._plan_tables["deep_sky"]
        table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        table.customContextMenuRequested.connect(self._plan_context_menu)
        table.cellDoubleClicked.connect(lambda row, _col: self._show_plan_target_on_map(row))
        table.setToolTip(t("planner.table_tip"))

        card = _card()
        card_l = QVBoxLayout(card)
        card_l.setContentsMargins(8, 8, 8, 8)
        views = QHBoxLayout()
        views.setSpacing(6)
        self._plan_view_buttons = {}
        group = QButtonGroup(card)
        group.setExclusive(True)
        for key in ("altitude", "map"):
            btn = _button(t(f"planner.view_{key}"), None, "secondaire", compact=True, checkable=True)
            btn.setToolTip(t(f"planner.view_{key}_tip"))
            group.addButton(btn)
            views.addWidget(btn)
            self._plan_view_buttons[key] = btn
            btn.toggled.connect(lambda on, _k=key: on and self._draw_plan_chart())
        self._plan_view_buttons["altitude"].setChecked(True)
        self._plan_slider = QSlider(Qt.Orientation.Horizontal)
        self._plan_slider.setToolTip(t("planner.time_tip"))
        self._plan_slider.valueChanged.connect(lambda _v: self._draw_plan_chart())
        self._plan_time = _label("", "legende")
        views.addSpacing(12)
        views.addWidget(self._plan_time)
        views.addWidget(self._plan_slider, stretch=1)
        self._plan_enlarge = _button(t("planner.sky_enlarge"), None, "discret", compact=True)
        self._plan_enlarge.setToolTip(t("planner.sky_enlarge_tip"))
        self._plan_enlarge.clicked.connect(lambda _c=False: self.show_night_sky())
        views.addWidget(self._plan_enlarge)
        card_l.addLayout(views)
        self.fig_plan = Figure(facecolor=Config.CIEL_100)
        self.canvas_plan = FigureCanvasQTAgg(self.fig_plan)
        self.canvas_plan.setMinimumHeight(260)
        self.canvas_plan.mpl_connect("motion_notify_event", self._on_plan_hover)
        self._plan_points = []
        card_l.addWidget(self.canvas_plan)
        # the tables and the chart share the height; the user moves the line between them
        split = QSplitter(Qt.Orientation.Vertical)
        split.setChildrenCollapsible(False)
        split.addWidget(self._plan_tabs)
        split.addWidget(card)
        sizes = prefs.get("plan_split") or [40, 60]
        split.setSizes([int(v * 10) for v in sizes])
        split.splitterMoved.connect(lambda _p, _i: prefs.set("plan_split", [int(v / 10) or 1 for v in split.sizes()]))
        split.setToolTip(t("planner.split_tip"))
        self._plan_split = split
        right.addWidget(split, stretch=1)
        outer.addLayout(right, stretch=1)
        self.tabs.addTab(page, t("tabs.planner"))
        self._planner_page = page
        if self._plan is not None:                        # rebuilt (language, theme): shown again
            self._show_plan()

    def _plan_table(self, columns):
        table = QTableWidget(0, len(columns))
        table.setHorizontalHeaderLabels([t(f"planner.{c}") for c in columns])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        table.setShowGrid(False)
        table.setWordWrap(False)
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        table.verticalHeader().setDefaultSectionSize(32)
        table.setProperty("columns", list(columns))
        return table

    # the constraints typed

    def _read_plan_constraints(self):
        """The constraints of the form, checked; None (and the fields flagged) when one is wrong."""
        c = self._plan_constraints()
        c["catalog"] = self._plan_catalog.currentData()
        ok = True
        for key, (edit, field) in self._plan_fields.items():
            text = edit.text().strip()
            if key == "magnitude_max" and not text:
                c[key] = None
                field.set_error(None)
                continue
            limits = self._PLAN_LIMITS[key]
            try:
                value = _typed_number(text)
                if not limits[0] <= value <= limits[1]:
                    raise ValueError
            except ValueError:
                field.set_error(tf("planner.range_error", low=_num(limits[0]), high=_num(limits[1])))
                ok = False
                continue
            field.set_error(None)
            c[key] = value / 100.0 if key == "fraction_min" else (int(value) if key == "max_targets" else value)
        if ok and c["altitude_min"] >= c["altitude_max"]:
            self._plan_fields["altitude_max"][1].set_error(t("planner.order_error"))
            ok = False
        if ok and c["size_min"] > c["size_max"]:
            self._plan_fields["size_max"][1].set_error(t("planner.order_error"))
            ok = False
        c["moon_separation_from_illumination"] = self._plan_moon_lit.isChecked()
        types = [k for k, box in self._plan_types.items() if box.isChecked()]
        c["types"] = () if len(types) == len(self._plan_types) else tuple(types)
        return c if ok else None

    def _plan_inputs(self):
        """Everything the plan depends on, and the key of the cache."""
        environment = {"temperature": _pref_float("env_temperature", 10.0),
                       "pressure": _pref_float("env_pressure", 1010.0)}
        horizon = [tuple(p) for p in prefs.get("horizon_points") or []]
        custom = list(prefs.get("planner_custom") or [])
        bucket, done = list(prefs.get("planner_bucket") or []), list(prefs.get("planner_done") or [])
        return environment, horizon, custom, bucket, done

    def _compute_plan(self, force=False):
        """Computes the plan of the night of the date and place typed (in the background)."""
        if self._dte is None or self._plan_busy:
            return
        c = self._read_plan_constraints()
        if c is None:
            self._plan_status.setText(t("planner.invalid"))
            return
        prefs.set("planner_constraints", {k: (list(v) if isinstance(v, tuple) else v) for k, v in c.items()})
        use_mpc = self._plan_mpc.isChecked()
        prefs.set("planner_mpc", use_mpc)
        environment, horizon, custom, bucket, done = self._plan_inputs()
        night = planner.night_window(self._dte, self._lat, self._lon, self._elevation(), self._zone)
        key = (night["start"], round(self._lat, 4), round(self._lon, 4), self._elevation(),
               json.dumps([c, environment, horizon, custom, bucket, done, use_mpc], default=str, sort_keys=True))
        if not force and key == self._plan_key:
            return
        self._plan_busy = True
        self._btn_plan.setEnabled(False)
        self._plan_status.setText(t("planner.computing"))
        dte, lat, lon, elev, zone = self._dte, self._lat, self._lon, self._elevation(), self._zone
        need_mpc = use_mpc and self._mpc_comets is None

        def work():
            comets, error = (mpc.refresh() if need_mpc else (self._mpc_comets, None))
            result = planner.plan(dte, lat, lon, elev, zone, c, horizon, environment, custom, bucket, done,
                                  comets if use_mpc else None)
            return result, comets, error

        def done_(answer):
            result, comets, error = answer
            self._plan_busy = False
            self._btn_plan.setEnabled(True)
            if use_mpc and comets:
                self._mpc_comets = comets
            self._plan, self._plan_key = result, key
            self._show_plan()
            if use_mpc and not comets:
                self._plan_status.setText(tf("planner.mpc_error", detail=error or ""))

        def failed(exc):
            self._plan_busy = False
            self._btn_plan.setEnabled(True)
            self._plan_status.setText(tf("planner.error", detail=str(exc)))
        _run_in_background(work, done_, failed)

    # showing the plan

    def _hm(self, dt):
        return "—" if dt is None else self._format_event(dt)

    def _plan_cell(self, table, row, col, text, sort=None, data=None):
        item = _SortItem(text)
        item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        if sort is not None:
            item.setData(_SORT_ROLE, sort)
        if data is not None:
            item.setData(_NAME_ROLE, data)
        table.setItem(row, col, item)
        return item

    def _show_plan(self):
        """Fills the summary, the three tables and the chart from self._plan."""
        result = self._plan
        window = result["window"]
        for table in self._plan_tables.values():
            table.setSortingEnabled(False)
            table.clearSelection()
            table.setRowCount(0)
        self._btn_plan_export.setEnabled(window["kind"] is not None)
        if window["kind"] is None:
            self._plan_summary.setText(t("planner.no_night"))
            self._plan_status.setText("")
            self._draw_plan_chart()
            return
        moon = result["moon"]
        self._plan_summary.setText(tf(
            "planner.summary", kind=t(f"planner.night_{window['kind']}"), start=self._hm(window["start"]),
            end=self._hm(window["end"]), moon=_num(moon["illumination"], 0),
            separation=_num(moon["separation_min"], 0)))
        self._plan_status.setText(tf("planner.found", n=len(result["deep_sky"]),
                                     total=_num(result["deep_sky_considered"]),
                                     catalog=t(f"planner.catalog_{result['constraints']['catalog']}")))
        table = self._plan_tables["deep_sky"]
        table.setRowCount(len(result["deep_sky"]))
        for r, o in enumerate(result["deep_sky"]):
            name = _messier_label(o)                       # the common name in the interface language
            if o.get("bucket"):
                name = f"{SYMBOL['star']} {name}"
            item = self._plan_cell(table, r, 0, name, r, o["label"])
            item.setToolTip(o["id"])
            self._plan_cell(table, r, 1, f"{_num(100 * o['fraction'], 0)} %", o["fraction"])
            best = "—" if not o["best"] else f"{self._hm(o['best'][0])}–{self._hm(o['best'][1])}"
            self._plan_cell(table, r, 2, best, o["best"][0].timestamp() if o["best"] else None)
            self._plan_cell(table, r, 3, _deg(o["alt_max"], 0), o["alt_max"])
            self._plan_cell(table, r, 4, self._hm(o["time_max"]), o["time_max"].timestamp())
            self._plan_cell(table, r, 5, self._hm(o["transit"]), o["transit"].timestamp())
            self._plan_cell(table, r, 6, t(f"messier.type_{o['type']}"))
            self._plan_cell(table, r, 7, o["const"])
            self._plan_cell(table, r, 8, "—" if o["mag"] is None else _num(o["mag"], 1), o["mag"])
            size = "—" if o["major"] is None else f"{_num(o['major'], 0)}′"
            self._plan_cell(table, r, 9, size, o["major"])
        table = self._plan_tables["bodies"]
        table.setRowCount(len(result["bodies"]))
        for r, b in enumerate(result["bodies"]):
            name = (f"{SYMBOL['Moon']} {t('chart.moon')}" if b["name"] == "moon"
                    else _planet_name(b["name"], symbol=True))
            self._plan_cell(table, r, 0, name, r, b["name"])
            self._plan_cell(table, r, 1, "—" if b["mag"] is None else _num(b["mag"], 1), b["mag"])
            self._plan_cell(table, r, 2, _deg(b["alt_max"], 0), b["alt_max"])
            self._plan_cell(table, r, 3, self._hm(b["time_max"]), b["time_max"].timestamp())
            self._plan_cell(table, r, 4, self._hm(b["transit"]), b["transit"].timestamp())
            best = "—" if not b["best"] else f"{self._hm(b['best'][0])}–{self._hm(b['best'][1])}"
            self._plan_cell(table, r, 5, best)
            self._plan_cell(table, r, 6, f"{_num(100 * b['fraction'], 0)} %", b["fraction"])
        table = self._plan_tables["comets"]
        table.setRowCount(len(result["comets"]))
        for r, k in enumerate(result["comets"]):
            name = _planet_name(k["table"], numbered=True) if k["table"] else k["name"]
            self._plan_cell(table, r, 0, f"{SYMBOL['meteors']} {name}", r, name)
            self._plan_cell(table, r, 1, _num(k["mag"], 1), k["mag"])
            self._plan_cell(table, r, 2, tf("units.au", value=_num(k["earth_au"], 2)), k["earth_au"])
            self._plan_cell(table, r, 3, tf("units.au", value=_num(k["sun_au"], 2)), k["sun_au"])
            self._plan_cell(table, r, 4, _deg(k["alt_max"], 0), k["alt_max"])
            self._plan_cell(table, r, 5, self._hm(k["time_max"]), k["time_max"].timestamp())
            self._plan_cell(table, r, 6, self._hm(k["rise"]))
            self._plan_cell(table, r, 7, self._hm(k["set"]))
        for key, table in self._plan_tables.items():
            self._plan_tabs.setTabText(list(self._plan_tables).index(key),
                                       tf(f"planner.tab_{key}_n", n=table.rowCount()))
            table.setSortingEnabled(True)
            table.sortItems(0, Qt.SortOrder.AscendingOrder)
        self._draw_plan_chart()

    def _plan_chosen(self):
        """(tab key, items of the targets chosen in the table: the first five without a choice)."""
        result = self._plan
        key = "bodies" if self._plan_tabs.currentIndex() == 1 else "deep_sky"
        table = self._plan_tables[key]
        rows = sorted({i.row() for i in table.selectedItems()}) or list(range(min(5, table.rowCount())))
        names = [table.item(r, 0).data(_NAME_ROLE) for r in rows[:8]]
        items = {o["label"]: o for o in result["deep_sky"]} if key == "deep_sky" else \
            {b["name"]: b for b in result["bodies"]}
        chosen = []
        for name in names:
            item = items.get(name)
            if item is not None:
                title = (t("chart.moon") if name == "moon" else _planet_name(name)) if key == "bodies" else name
                chosen.append((title, item))
        return key, chosen

    def _plan_map_mode(self):
        return hasattr(self, "_plan_view_buttons") and self._plan_view_buttons["map"].isChecked()

    def _plan_times(self):
        return [self._local(x).strftime("%H:%M") for x in self._plan["times"]]

    _SHAPES = {"galaxy": "circle", "galaxy_group": "circle", "nebula": "diamond", "planetary_nebula": "diamond",
               "supernova_remnant": "diamond", "dark_nebula": "diamond"}

    def _night_sky_data(self, everything=False):
        """
        What the map of the night shows (the Targets tab, its large window and its web
        page): the deep-sky targets numbered as in the table (*everything*: the first 20,
        the chosen ones shown; otherwise the chosen ones), the planets, the comets, the
        Moon, with their colours and markers, the header and the legend, as uptonight.
        """
        result = self._plan
        key, chosen = self._plan_chosen()
        chosen_names = {title for title, _item in chosen}
        times = self._plan_times()
        tracks = []

        def start(alts):
            return next((i for i, a in enumerate(alts) if a is not None and a > 0), 0)

        table = self._plan_tables["deep_sky"]
        order = [table.item(r, 0).data(_NAME_ROLE) for r in range(table.rowCount())]
        by_label = {o["label"]: o for o in result["deep_sky"]}
        if everything:
            names = order[:20] + [n for n in chosen_names if key == "deep_sky" and n in by_label and n not in order[:20]]
        else:
            names = [title for title, _item in chosen] if key == "deep_sky" else []
        for n, name in enumerate(names):
            o = by_label.get(name)
            if o is None:
                continue
            number = order.index(name) + 1 if name in order else n + 1
            details = [t(f"messier.type_{o['type']}")]
            if o.get("major"):
                details.append(f"{_num(o['major'], 0)}′")
            details.append(f"{_num(100 * o['fraction'], 0)} %")
            if o.get("mag") is not None:
                details.append(f"mag {_num(o['mag'], 1)}")
            row = order.index(name) if name in order else None
            title = table.item(row, 0).text() if row is not None else o["label"]     # the name in the language
            tracks.append({"name": o["label"], "legend": f"{number} : {title} ({', '.join(details)})",
                           "kind": "deep_sky", "shape": self._SHAPES.get(o["type"], "square"), "number": number,
                           "alt": [float(v) for v in o["altitudes"]], "az": [float(v) for v in o["azimuths"]],
                           "on": True,
                           "start": start(o["altitudes"])})
        for b in result["bodies"]:
            if b["name"] == "moon":
                continue
            title = _planet_name(b["name"])
            if not everything and not (key == "bodies" and title in chosen_names):
                continue
            mag = "" if b.get("mag") is None else f" (mag {_num(b['mag'], 1)})"
            tracks.append({"name": title, "legend": title + mag, "kind": "body", "shape": "big", "number": None,
                           "alt": [float(v) for v in b["altitudes"]], "az": [float(v) for v in b["azimuths"]],
                           "on": True, "start": start(b["altitudes"])})
        if everything:
            for k in result["comets"][:6]:
                title = _planet_name(k["table"], numbered=True) if k["table"] else k["name"]
                tracks.append({"name": title, "legend": f"{title} (mag {_num(k['mag'], 1)})", "kind": "comet",
                               "shape": "x", "number": None,
                               "alt": [float(v) for v in k["altitudes"]], "az": [float(v) for v in k["azimuths"]],
                               "on": True, "start": start(k["altitudes"])})
        moon = next((b for b in result["bodies"] if b["name"] == "moon"), None)
        if moon is not None:
            tracks.append({"name": t("chart.moon"), "legend": t("chart.moon"), "kind": "moon", "shape": "circle",
                           "number": None, "alt": [float(v) for v in moon["altitudes"]],
                           "az": [float(v) for v in moon["azimuths"]], "on": True, "start": 0})
        window, ev, c = result["window"], result.get("events", {}), result["constraints"]

        def hm(dt):
            return "—" if dt is None else self._local(dt).strftime("%H:%M")

        def dhm(dt):
            return "—" if dt is None else self._local(dt).strftime("%d/%m %H:%M")
        length = (window["end"] - window["start"]).total_seconds() / 3600
        title = tf("planner.sky_title", kind=t(f"planner.night_{window['kind']}").split(" (")[0],
                   start=dhm(window["start"]), end=dhm(window["end"]),
                   length=f"{int(length)} h {int(round(length % 1 * 60)):02d}")
        info = [tf("planner.sky_sun", set=hm(ev.get("sunset")), rise=hm(ev.get("sunrise"))),
                tf("planner.sky_moon", rise=dhm(ev.get("moonrise")), set=dhm(ev.get("moonset"))),
                tf("planner.sky_illumination", value=_num(result["moon"]["illumination"], 0)),
                tf("planner.sky_altitude", low=_num(c["altitude_min"], 0), high=_num(c["altitude_max"], 0)),
                tf("planner.sky_airmass", value=_num(c["airmass_max"], 1)),
                tf("planner.sky_size", low=_num(c["size_min"], 0), high=_num(c["size_max"], 0)),
                tf("planner.sky_fraction", value=_num(100 * c["fraction_min"], 0)),
                tf("planner.sky_separation", value=_num(result["moon"]["separation_min"], 0))]
        where = self.location_name or f"{_fmt_lat(self._lat)}, {_fmt_lon(self._lon)}"
        labels = {"north": t("skymap.cardinal_n"), "east": t("skymap.cardinal_e"), "south": t("skymap.cardinal_s"),
                  "west": t("skymap.cardinal_w"), "empty": t("planner.chart_empty")}
        info.insert(0, tf("planner.sky_place", place=where, zone=_fmt_offset(self._offset_at(result["times"][0]))))
        return {"title": title, "info": info, "markers": [t(f"planner.sky_marker_{k}") for k in
                                          ("big", "diamond", "circle", "square", "x")],
                "times": times, "tracks": tracks, "horizon": [list(p) for p in result["horizon"]],
                "limits": [c["altitude_min"], c["altitude_max"]], "labels": labels,
                "east_right": bool(prefs.get("plan_map_east_right"))}

    def _draw_plan_tracks(self):
        """The paths across the sky of the chosen targets (the map of the night, compact)."""
        result = self._plan
        times = self._plan_times() if result is not None else []
        self._plan_slider.blockSignals(True)
        self._plan_slider.setRange(0, max(0, len(times) - 1))
        self._plan_slider.blockSignals(False)
        if result is None or not times:
            self._plan_sky = None
            self.fig_plan.clear()
            self.canvas_plan.draw_idle()
            return
        self._plan_sky = self._night_sky_data()
        now = self._plan_slider.value()
        self._plan_time.setText(times[now])
        self._plan_points = charts.draw_night_sky(self.fig_plan, self._plan_sky, now,
                                                  self._plan_sky["east_right"], compact=True)
        self.canvas_plan.draw_idle()

    def _night_sky_tip(self, event, points, data, canvas):
        """The tooltip over a map of the night: the target, the hour, its altitude and azimuth."""
        if event.xdata is None or not points or data is None:
            QToolTip.hideText()
            return
        best = min(points, key=lambda p: (p[1] - event.xdata) ** 2 + (p[2] - event.ydata) ** 2)
        if (best[1] - event.xdata) ** 2 + (best[2] - event.ydata) ** 2 > 0.035 ** 2:
            QToolTip.hideText()
            return
        name, _x, _y, i = best
        track = next(tr for tr in data["tracks"] if tr["name"] == name)
        QToolTip.showText(QCursor.pos(), tf("planner.map_tip", name=name, time=data["times"][i],
                                            alt=_deg(track["alt"][i], 0), az=_deg(track["az"][i], 0)), canvas)

    def _on_plan_hover(self, event):
        if self._plan_map_mode() and self._plan is not None:
            self._night_sky_tip(event, self._plan_points, getattr(self, "_plan_sky", None), self.canvas_plan)

    def show_night_sky(self):
        """The large map of the night, after uptonight's plots, in Céleste's colours: every
        target of the table, the planets, the comets and the Moon, the header and the
        numbered legend. A slider through the night, the details under the pointer, a
        click on a line of the legend shows or hides its target (the pointer over it
        brings its path out), the east on either side, and the image to save."""
        if self._plan is None or not self._plan["times"]:
            return None
        data = self._night_sky_data(everything=True)
        dlg = QDialog(self)
        dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dlg.setWindowTitle(data["title"])
        dlg.resize(1280, 860)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(16, 16, 16, 12)
        figure = Figure(facecolor=Config.CIEL_100)
        canvas = FigureCanvasQTAgg(figure)
        lay.addWidget(canvas, stretch=1)
        bar = QHBoxLayout()
        time_label = _label("", "corps", strong=True)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(0, len(data["times"]) - 1)
        slider.setValue(len(data["times"]) // 2)
        slider.setToolTip(t("planner.time_tip"))
        east = QCheckBox(t("planner.sky_east_right"))
        east.setChecked(data["east_right"])
        east.setToolTip(t("planner.sky_east_tip"))
        show_all = _button(t("planner.sky_show_all"), None, "discret", compact=True)
        hide_all = _button(t("planner.sky_hide_all"), None, "discret", compact=True)
        png = _button(t("planner.sky_save_png"), "export", "principal", compact=True)
        close = _button(t("detail.close"), compact=True)
        close.clicked.connect(dlg.reject)
        for widget in (time_label,):
            bar.addWidget(widget)
        bar.addWidget(slider, stretch=1)
        for widget in (east, show_all, hide_all, png, close):
            bar.addWidget(widget)
        lay.addLayout(bar)
        state = {"points": [], "highlight": None}

        def draw():
            time_label.setText(data["times"][slider.value()])
            state["points"] = charts.draw_night_sky(figure, data, slider.value(), east.isChecked(),
                                                    highlight=state["highlight"])
            canvas.draw_idle()

        def legend_row(event):
            """The track under the pointer in the legend, or None."""
            legend = getattr(figure, "night_legend", None)
            if not legend or event.inaxes is not legend[0] or event.ydata is None:
                return None
            _ax, rows, step = legend
            near = min(rows, key=lambda r: abs(r[0] - event.ydata))
            return near[1] if abs(near[0] - event.ydata) <= step / 2 else None

        def moved(event):
            row = legend_row(event)
            if row != state["highlight"]:
                state["highlight"] = row if row is None or data["tracks"][row].get("on", True) else None
                draw()
            if row is None:
                self._night_sky_tip(event, state["points"], data, canvas)

        def clicked(event):
            row = legend_row(event)
            if row is not None:
                track = data["tracks"][row]
                track["on"] = not track.get("on", True)
                state["highlight"] = row if track["on"] else None
                draw()

        def show(on):
            for track in data["tracks"]:
                track["on"] = on
            draw()

        def turn_east(on):
            prefs.set("plan_map_east_right", bool(on))
            data["east_right"] = bool(on)
            draw()
            self._draw_plan_chart()

        def save():
            day = self._local(self._plan["window"]["start"]).strftime("%Y-%m-%d")
            path, _f = QFileDialog.getSaveFileName(
                dlg, t("planner.export"), os.path.join(os.path.expanduser("~"), f"celeste-nuit-{day}.png"),
                "PNG (*.png)")
            if not path:
                return
            if not path.lower().endswith(".png"):
                path += ".png"
            try:
                figure.savefig(path, dpi=150, facecolor=figure.get_facecolor())
            except OSError as exc:
                QMessageBox.critical(dlg, t("errors.error_title"), str(exc))
                return
            self.statusBar().showMessage(tf("planner.exported", path=path), 6000)

        slider.valueChanged.connect(lambda _v: draw())
        east.toggled.connect(turn_east)
        show_all.clicked.connect(lambda _c=False: show(True))
        hide_all.clicked.connect(lambda _c=False: show(False))
        png.clicked.connect(lambda _c=False: save())
        canvas.mpl_connect("motion_notify_event", moved)
        canvas.mpl_connect("button_press_event", clicked)
        dlg.night_sky = {"figure": figure, "canvas": canvas, "slider": slider, "east": east, "data": data,
                         "state": state, "save": save, "moved": moved, "clicked": clicked, "show": show}
        self._night_sky_dialog = dlg
        dlg.show()
        draw()
        return dlg

    def _draw_plan_chart(self):
        """Altitude through the night of the targets chosen in the table (the first five without a choice),
        or their paths across the sky."""
        if not hasattr(self, "fig_plan"):
            return
        map_mode = self._plan_map_mode()
        self._plan_slider.setVisible(map_mode)
        self._plan_time.setVisible(map_mode)
        self._plan_enlarge.setVisible(map_mode)
        if map_mode:
            self._draw_plan_tracks()
            return
        result = self._plan
        labels = {"title": t("planner.chart_title"), "xlabel": t("planner.chart_x"),
                  "ylabel": t("chart.altitude"), "moon": t("chart.moon"), "empty": t("planner.chart_empty")}
        if result is None or not result["times"]:
            charts.draw_night_plan(self.fig_plan, [], [], None, (30, 80), labels)
            self.canvas_plan.draw_idle()
            return
        _key, chosen = self._plan_chosen()
        series = [(title, item["altitudes"]) for title, item in chosen]
        start = self._local(result["times"][0])
        hours = [start.hour + start.minute / 60 + (self._local(x) - start).total_seconds() / 3600
                 for x in result["times"]]
        moon = next((b["altitudes"] for b in result["bodies"] if b["name"] == "moon"), None)
        c = result["constraints"]
        labels["title"] = tf("planner.chart_title_date", date=self._local(result["times"][0]).strftime("%d/%m/%Y"))
        labels["xlabel"] = tf("chart.hour_local", offset=_fmt_offset(self._offset_at(result["times"][0])))
        charts.draw_night_plan(self.fig_plan, hours, series, moon, (c["altitude_min"], c["altitude_max"]), labels)
        self.canvas_plan.draw_idle()

    def _offset_at(self, dt):
        local = self._local(dt)
        return (local - dt).total_seconds() / 3600.0

    # lists and targets of the user's

    def _plan_selected(self):
        table = self._plan_tables["deep_sky"]
        return [table.item(r, 0).data(_NAME_ROLE) for r in sorted({i.row() for i in table.selectedItems()})]

    def _plan_context_menu(self, pos):
        table = self._plan_tables["deep_sky"]
        item = table.itemAt(pos)
        if item is None:
            return
        if item.row() not in {i.row() for i in table.selectedItems()}:
            table.selectRow(item.row())
        labels = self._plan_selected()
        bucket, done = list(prefs.get("planner_bucket") or []), list(prefs.get("planner_done") or [])
        menu = QMenu(self)
        menu.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        if len(labels) == 1:
            menu.addAction(t("planner.show_on_map")).triggered.connect(
                lambda: self._show_plan_target_on_map(table.currentRow()))
        if any(lb not in bucket for lb in labels):
            menu.addAction(t("planner.add_bucket")).triggered.connect(lambda: self._plan_list_add("planner_bucket", labels))
        else:
            menu.addAction(t("planner.remove_bucket")).triggered.connect(lambda: self._plan_list_remove("planner_bucket", labels))
        menu.addAction(t("planner.add_done")).triggered.connect(lambda: self._plan_list_add("planner_done", labels))
        self._plan_menu = menu
        menu.popup(table.viewport().mapToGlobal(pos))

    def _plan_list_add(self, key, labels):
        values = list(prefs.get(key) or [])
        values += [lb for lb in labels if lb not in values]
        prefs.set(key, values)
        other = "planner_done" if key == "planner_bucket" else "planner_bucket"
        prefs.set(other, [v for v in prefs.get(other) or [] if v not in labels])
        self._compute_plan(force=True)

    def _plan_list_remove(self, key, labels):
        prefs.set(key, [v for v in prefs.get(key) or [] if v not in labels])
        self._compute_plan(force=True)

    def _show_plan_target_on_map(self, row):
        """The target of a row circled on the sky map."""
        table = self._plan_tables["deep_sky"]
        if self._plan is None or row < 0 or table.item(row, 0) is None:
            return
        name = table.item(row, 0).data(_NAME_ROLE)
        target = next((o for o in self._plan["deep_sky"] if o["label"] == name), None)
        if target is None:
            return
        ref = ("messier", target["m"]) if target.get("m") else ("deep", target["label"])
        self.tabs.setCurrentIndex(2)
        self._find_on_sky(ref)

    def _list_dialog(self, title, hint):
        dlg = QDialog(self)
        dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dlg.setWindowTitle(title)
        dlg.setMinimumWidth(520)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(24, 24, 24, 16)
        lay.setSpacing(12)
        lay.addWidget(_label(title, "sous-titre"))
        lay.addWidget(_label(hint, "legende", wrap=True))
        return dlg, lay

    def _edit_plan_lists(self):
        """Window: the bucket list and the done list, one name per line."""
        dlg, lay = self._list_dialog(t("planner.lists_title"), t("planner.lists_hint"))
        from PyQt6.QtWidgets import QPlainTextEdit
        edits = {}
        row = QHBoxLayout()
        row.setSpacing(16)
        for key in ("planner_bucket", "planner_done"):
            col = QVBoxLayout()
            col.addWidget(_label(t(f"planner.{key}"), "label"))
            edit = QPlainTextEdit("\n".join(prefs.get(key) or []))
            edit.setMinimumHeight(200)
            col.addWidget(edit)
            edits[key] = edit
            row.addLayout(col)
        lay.addLayout(row)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        lay.addWidget(buttons)

        def save():
            for key, edit in edits.items():
                prefs.set(key, [ln.strip() for ln in edit.toPlainText().splitlines() if ln.strip()])
            dlg.accept()
            self._compute_plan(force=True)
        buttons.accepted.connect(save)
        buttons.rejected.connect(dlg.reject)
        self._lists_dialog = dlg
        dlg.open()

    def _edit_custom_targets(self):
        """Window: the user's own targets, one per line: name; RA; Dec; type; size; magnitude."""
        dlg, lay = self._list_dialog(t("planner.custom_title"), t("planner.custom_hint"))
        from PyQt6.QtWidgets import QPlainTextEdit
        lines = []
        for c in prefs.get("planner_custom") or []:
            lines.append("; ".join([c["name"], _ra(c["ra"] / 15.0, "dms"), _dec(c["dec"], "dms"), c.get("type", ""),
                                    "" if c.get("size") is None else _num(c["size"], 0),
                                    "" if c.get("mag") is None else _num(c["mag"], 1)]))
        edit = QPlainTextEdit("\n".join(lines))
        edit.setPlaceholderText("Mon objet; 0h 42m 44s; +41° 16′ 09″; galaxy; 190; 3,4")
        edit.setMinimumHeight(180)
        lay.addWidget(edit)
        error = _label("", "legende", tone="alerte", wrap=True)
        lay.addWidget(error)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        lay.addWidget(buttons)

        def save():
            try:
                targets = [self._parse_custom(line) for line in edit.toPlainText().splitlines() if line.strip()]
            except ValueError as exc:
                error.setText(str(exc))
                return
            prefs.set("planner_custom", targets)
            dlg.accept()
            self._compute_plan(force=True)
        buttons.accepted.connect(save)
        buttons.rejected.connect(dlg.reject)
        self._custom_dialog = dlg
        dlg.open()

    @staticmethod
    def _parse_angle(text, hours):
        """"0h 42m 44s", "00:42:44", "10.68" (degrees, or hours with an h) → degrees."""
        raw = text.strip().replace(",", ".").replace("−", "-")
        sign = -1.0 if raw.startswith("-") else 1.0
        numbers = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", raw)]
        if not numbers:
            raise ValueError(text)
        value = sum(n / 60 ** i for i, n in enumerate(numbers[:3]))
        in_hours = hours and (len(numbers) > 1 or "h" in raw.lower())
        return sign * value * (15.0 if in_hours else 1.0)

    def _parse_custom(self, line):
        parts = [p.strip() for p in line.split(";")]
        if len(parts) < 3 or not parts[0]:
            raise ValueError(tf("planner.custom_error", line=line))
        try:
            ra = self._parse_angle(parts[1], True)
            dec = self._parse_angle(parts[2], False)
            size = float(parts[4].replace(",", ".")) if len(parts) > 4 and parts[4] else None
            mag = float(parts[5].replace(",", ".").replace("−", "-")) if len(parts) > 5 and parts[5] else None
        except ValueError:
            raise ValueError(tf("planner.custom_error", line=line)) from None
        if not (0 <= ra < 360 and -90 <= dec <= 90):
            raise ValueError(tf("planner.custom_error", line=line))
        kind = parts[3] if len(parts) > 3 and parts[3] in planner.DEEP_SKY_TYPES else "nebula"
        return {"name": parts[0], "ra": round(ra, 5), "dec": round(dec, 5), "type": kind, "size": size, "mag": mag}

    def _export_plan(self):
        """Saves the plan: a text report, JSON or the chart (PNG)."""
        if self._plan is None:
            return
        name = f"celeste-plan-{self._local(self._plan['window']['start']).strftime('%Y-%m-%d')}"
        path, chosen = QFileDialog.getSaveFileName(
            self, t("planner.export"), os.path.join(os.path.expanduser("~"), name + ".txt"),
            f"{t('planner.export_txt')} (*.txt);;JSON (*.json);;PNG (*.png)")
        if not path:
            return
        try:
            if path.lower().endswith(".png") or "png" in chosen.lower():
                self.fig_plan.savefig(path if path.lower().endswith(".png") else path + ".png", dpi=150,
                                      facecolor=self.fig_plan.get_facecolor())
            elif path.lower().endswith(".json") or "json" in chosen.lower():
                with open(path, "w", encoding="utf-8") as f:
                    f.write(planner.report_json(self._plan, self.location_name or ""))
            else:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(self._plan_report_text())
        except OSError as exc:
            QMessageBox.critical(self, t("errors.error_title"), str(exc))
            return
        self.statusBar().showMessage(tf("planner.exported", path=path), 6000)

    def _plan_report_text(self):
        """The plan as text, in the interface language (uptonight's txt report)."""
        r = self._plan
        c = r["constraints"]
        place = self.location_name or f"{_fmt_lat(self._lat)}, {_fmt_lon(self._lon)}"
        out = [tf("planner.report_title", place=place), self._plan_summary.text(), "",
               tf("planner.report_constraints", alt_min=_num(c["altitude_min"]), alt_max=_num(c["altitude_max"]),
                  airmass=_num(c["airmass_max"], 1), size_min=_num(c["size_min"]), size_max=_num(c["size_max"]),
                  fraction=_num(100 * c["fraction_min"]), catalog=t(f"planner.catalog_{c['catalog']}")), ""]
        for key in ("deep_sky", "bodies", "comets"):
            table = self._plan_tables[key]
            out.append(tf(f"planner.tab_{key}_n", n=table.rowCount()))
            heads = [table.horizontalHeaderItem(i).text() for i in range(table.columnCount())]
            rows = [[table.item(r, i).text() if table.item(r, i) else "" for i in range(table.columnCount())]
                    for r in range(table.rowCount())]
            widths = [max([len(h)] + [len(row[i]) for row in rows]) for i, h in enumerate(heads)]
            out.append("  ".join(h.ljust(w) for h, w in zip(heads, widths)).rstrip())
            out += ["  ".join(v.ljust(w) for v, w in zip(row, widths)).rstrip() for row in rows]
            out.append("")
        return "\n".join(out)

    # the observing site (settings)

    @staticmethod
    def _horizon_text(points):
        return ", ".join(f"{_num(a, 0)} {_num(h, 0)}" for a, h in points)

    def _save_horizon(self):
        """"0 10, 90 15, 180 5" → [[0, 10], [90, 15], [180, 5]] (azimuth, altitude)."""
        text = self._horizon_edit.text().strip()
        points = []
        try:
            for part in [p for p in re.split(r"[;,]\s*(?=\d)|\s*[;]\s*|,\s+", text) if p.strip()]:
                numbers = [float(x.replace(",", ".")) for x in re.findall(r"-?\d+(?:[.,]\d+)?", part)]
                if len(numbers) != 2 or not (0 <= numbers[0] <= 360 and 0 <= numbers[1] < 90):
                    raise ValueError(part)
                points.append([numbers[0], numbers[1]])
        except ValueError:
            self._horizon_field.set_error(t("observatory.horizon_error"))
            return
        self._horizon_field.set_error(None)
        prefs.set("horizon_points", sorted(points))
        self._horizon_edit.setText(self._horizon_text(sorted(points)))
        if self._dte is not None:
            self._calculate_quietly()

    def _save_environment(self):
        values = {}
        for key, edit, field, low, high in (("env_temperature", self._env_temp, self._env_temp_field, -60, 60),
                                            ("env_pressure", self._env_pressure, self._env_pressure_field, 0, 1100)):
            try:
                value = _typed_number(edit.text())
                if not low <= value <= high:
                    raise ValueError
            except ValueError:
                field.set_error(tf("planner.range_error", low=_num(low), high=_num(high)))
                continue
            field.set_error(None)
            values[key] = value
        for key, value in values.items():
            prefs.set(key, value)

    def _build_settings_tab(self):
        scroll, _page, lay = _scroll_page()

        def section(title):
            card = _card()
            box = QVBoxLayout(card)
            box.setContentsMargins(16, 16, 16, 16)
            box.setSpacing(12)
            box.addWidget(_label(title, "sous-titre"))
            lay.addWidget(card)
            return box

        # Language and display
        box = section(t("settings.display_section"))
        self._lang_combo = QComboBox()
        auto_lang = resolve_lang("auto", QLocale.system().name())
        self._lang_combo.addItem(
            f"{t('settings.lang_auto')} ({lang_name(auto_lang)})", "auto")
        for code in available_langs():
            self._lang_combo.addItem(lang_name(code), code)
        self._lang_combo.setCurrentIndex(
            max(0, self._lang_combo.findData(prefs.get("lang") or "auto")))
        self._lang_combo.currentIndexChanged.connect(self._on_lang_change)
        self._timefmt_combo = QComboBox()
        for key in ("24h", "12h"):
            self._timefmt_combo.addItem(t(f"settings.time_{key}"), key)
        self._timefmt_combo.setCurrentIndex(
            max(0, self._timefmt_combo.findData(prefs.get("time_format") or "24h")))
        self._timefmt_combo.currentIndexChanged.connect(self._on_timefmt_change)
        self._anglefmt_combo = QComboBox()
        for key in Formatters.ANGLE_FORMATS:
            self._anglefmt_combo.addItem(t(f"coordinates.angle_{key}"), key)
        self._anglefmt_combo.setCurrentIndex(max(0, self._anglefmt_combo.findData(_angle_format())))
        self._anglefmt_combo.setToolTip(t("settings.angle_format_tip"))
        self._anglefmt_combo.currentIndexChanged.connect(self._on_anglefmt_change)
        row = QHBoxLayout()
        row.setSpacing(16)
        row.addWidget(InputField(t("settings.language"), self._lang_combo), stretch=1)
        row.addWidget(InputField(t("settings.time_format"), self._timefmt_combo), stretch=1)
        row.addWidget(InputField(t("settings.angle_format"), self._anglefmt_combo), stretch=1)
        box.addLayout(row)
        box.addWidget(_label(t("settings.theme_hint"), "legende", wrap=True))

        # Starting place
        box = section(t("settings.default_place_section"))
        self._place_entry = QLineEdit(_clean_place(prefs.get("default_place")))
        box.addWidget(InputField(t("settings.default_place_name"), self._place_entry))
        coords = QVBoxLayout()
        coords.setSpacing(4)
        coords.addWidget(_label(t("settings.default_place_coords"), "label"))
        self._default_coords_lbl = _label("", "donnee")
        coords.addWidget(self._default_coords_lbl)
        box.addLayout(coords)
        self._update_default_place_label()
        buttons = QHBoxLayout()
        btn_use = _button(t("settings.use_current"), "place")
        btn_use.setToolTip(t("settings.use_current_tip"))
        btn_use.clicked.connect(self._save_default_place)
        buttons.addWidget(btn_use)
        buttons.addStretch()
        box.addLayout(buttons)
        self._autogeo_cb = QCheckBox(t("settings.auto_geoloc"))
        self._autogeo_cb.setChecked(bool(prefs.get("auto_geoloc")))
        self._autogeo_cb.toggled.connect(lambda v: prefs.set("auto_geoloc", bool(v)))
        box.addWidget(self._autogeo_cb)

        # Real time
        box = section(t("settings.live_section"))
        box.addWidget(_label(t("settings.live_interval"), "label"))
        iv = QHBoxLayout()
        iv.setSpacing(12)
        self._iv_slider = QSlider(Qt.Orientation.Horizontal)
        self._iv_slider.setRange(1, 20)            # steps of 500 ms
        self._iv_slider.setValue(int((prefs.get("live_interval") or 2000) / 500))
        self._iv_lbl = _label("", "donnee")
        self._iv_lbl.setMinimumWidth(80)
        self._iv_slider.valueChanged.connect(self._on_interval_changed)
        iv.addWidget(self._iv_slider, stretch=1)
        iv.addWidget(self._iv_lbl)
        self._iv_lbl.setText(tf("units.ms", value=_num(self._iv_slider.value() * 500)))
        box.addLayout(iv)

        # Observing site: refraction and horizon mask (night planner, sky map)
        box = section(t("observatory.section"))
        box.addWidget(_label(t("observatory.hint"), "legende", wrap=True))
        row = QHBoxLayout()
        row.setSpacing(16)
        self._env_temp = QLineEdit(_num(_pref_float("env_temperature", 10.0), 1))
        self._env_pressure = QLineEdit(_num(_pref_float("env_pressure", 1010.0), 0))
        for edit in (self._env_temp, self._env_pressure):
            edit.editingFinished.connect(self._save_environment)
        self._env_temp_field = InputField(t("observatory.temperature"), self._env_temp, unit="°C", numeric=True)
        self._env_pressure_field = InputField(t("observatory.pressure"), self._env_pressure, unit="hPa",
                                              numeric=True, hint=t("observatory.pressure_hint"))
        row.addWidget(self._env_temp_field, stretch=1, alignment=Qt.AlignmentFlag.AlignTop)
        row.addWidget(self._env_pressure_field, stretch=1, alignment=Qt.AlignmentFlag.AlignTop)
        box.addLayout(row)
        self._horizon_edit = QLineEdit(self._horizon_text(prefs.get("horizon_points") or []))
        self._horizon_edit.setPlaceholderText(t("observatory.horizon_placeholder"))
        self._horizon_edit.editingFinished.connect(self._save_horizon)
        self._horizon_field = InputField(t("observatory.horizon"), self._horizon_edit,
                                         hint=t("observatory.horizon_hint"))
        box.addWidget(self._horizon_field)

        # Reset (irreversible: danger button and confirmation)
        box = section(t("settings.reset_section"))
        box.addWidget(_label(t("settings.reset_hint"), "legende", wrap=True))
        buttons = QHBoxLayout()
        btn_reset = _button(t("settings.reset_btn"), variant="danger")
        btn_reset.clicked.connect(self._reset_settings)
        buttons.addWidget(btn_reset)
        buttons.addStretch()
        box.addLayout(buttons)

        # About: updates, links
        box = section(t("settings.about_section"))
        box.addWidget(_label(tf("settings.about", version=APP_VERSION), "corps", wrap=True))
        box.addWidget(_label(t("settings.credits"), "legende", wrap=True))
        row = QHBoxLayout()
        row.setSpacing(12)
        self._btn_update = _button(t("update.check_now"), "now", "secondaire", compact=True)
        self._btn_update.setToolTip(t("update.check_now_tip"))
        self._btn_update.clicked.connect(lambda _checked=False: self.check_updates())
        row.addWidget(self._btn_update)
        self._update_auto = QCheckBox(t("update.auto"))
        self._update_auto.setChecked(bool(prefs.get("update_check")))
        self._update_auto.toggled.connect(lambda on: prefs.set("update_check", bool(on)))
        row.addWidget(self._update_auto)
        row.addStretch()
        box.addLayout(row)
        self._update_info = _label(tf("update.current", version=APP_VERSION), "legende", wrap=True)
        box.addWidget(self._update_info)
        self._link_buttons = {}
        for links in ((("site", _URL_SITE), ("source", _URL_REPO), ("coffee", _URL_COFFEE)),
                      (("bug", _issue_url("bug")), ("feature", _issue_url("feature")),
                       ("body", _issue_url("body")))):
            row = QHBoxLayout()
            row.setSpacing(8)
            for key, url in links:
                btn = _button(t(f"links.{key}"), variant="secondaire", compact=True)
                btn.setToolTip(t(f"links.{key}_tip"))
                btn.clicked.connect(lambda _checked=False, u=url: _open_url(u))
                self._link_buttons[key] = btn
                row.addWidget(btn)
            row.addStretch()
            box.addLayout(row)

        lay.addStretch()
        # nine tabs: the settings show as an icon, named in its tooltip and for screen readers
        index = self.tabs.addTab(scroll, _icon("settings", Config.ENCRE_ATTENUEE, 18), "")
        self.tabs.setTabToolTip(index, t("tabs.settings"))
        self.tabs.tabBar().setAccessibleTabName(index, t("tabs.settings")) \
            if hasattr(self.tabs.tabBar(), "setAccessibleTabName") else None
        self._settings_page = scroll

    # ── Status bar ────────────────────────────────────────────────────────────

    def _build_status_bar(self):
        bar = QStatusBar()
        bar.setSizeGripEnabled(False)
        self.setStatusBar(bar)
        self._lbl_pos = QLabel("—")
        self._lbl_stars = QLabel("")
        self._lbl_live = _badge(t("status.live_on"), "info")
        self._lbl_live.setVisible(False)
        self._lbl_time = QLabel("")
        bar.addWidget(self._lbl_pos)
        bar.addWidget(self._lbl_stars)
        bar.addPermanentWidget(self._lbl_live)
        bar.addPermanentWidget(self._lbl_time)
        self._apply_live_ui()

    # ──────────────────────────────────────────────────────────────────────────
    # REBUILD (LANGUAGE / THEME)
    # ──────────────────────────────────────────────────────────────────────────

    def _snapshot(self):
        return {
            "dte": self._edit_datetime(),
            "lat": self._input_coord(self.entry_lat),
            "lon": self._input_coord(self.entry_lon),
            "elev": self.entry_elev.text(),
            "tab": self.tabs.currentIndex(),
            "fav": self.combo_fav.currentIndex(),
        }

    @staticmethod
    def _input_coord(edit):
        """A typed coordinate (number), or the text as it is when invalid."""
        try:
            return float(edit.text().strip().replace(",", ".").replace("−", "-"))
        except ValueError:
            return edit.text()

    def _rebuild(self, keep_place=True):
        """Rebuilds the window (new language or theme), keeping the date, the
        tab, the real-time mode and, with *keep_place*, the place."""
        state = self._snapshot()
        apply_theme(QApplication.instance())
        named_by_favorite = state["fav"] >= 0 and self.location_name == self.combo_fav.currentText()
        self.favorites = self._load_favorites()          # preloaded places: in the new language
        self._build_ui()
        self._set_datetime(state["dte"])
        if keep_place:
            for edit, value in ((self.entry_lat, state["lat"]), (self.entry_lon, state["lon"])):
                edit.setText(_coord_text(value) if isinstance(value, float) else value)
            self.entry_elev.setText(state["elev"])
            self.combo_fav.setCurrentIndex(state["fav"])
            if named_by_favorite and self.combo_fav.currentIndex() >= 0:
                self.location_name = self.combo_fav.currentText()
        self._dirty = set()
        self.tabs.setCurrentIndex(state["tab"])
        self.btn_live.blockSignals(True)
        self.btn_live.setChecked(self.live_mode)
        self.btn_live.blockSignals(False)
        self._apply_live_ui()
        self.last_cache_key = ""
        self._calculate_quietly()
        if self._last_search == "eclipses":
            self._search_eclipses_gui()
        elif self._last_search == "conjunctions":
            self._search_conjunctions_gui()
        elif self._last_search == "satellites":
            self._search_satellites_gui()

    # ──────────────────────────────────────────────────────────────────────────
    # SETTINGS HANDLERS
    # ──────────────────────────────────────────────────────────────────────────

    def _on_theme_selected(self, key):
        if not key or key == Config.THEME:
            return
        prefs.set("theme", key)
        Config.apply_theme(key)
        QTimer.singleShot(0, self._rebuild)

    def _on_lang_change(self, index):
        code = self._lang_combo.itemData(index)
        if not code:
            return
        prefs.set("lang", code)
        switch_lang(resolve_lang(code, QLocale.system().name()))
        QTimer.singleShot(0, self._rebuild)

    def _on_timefmt_change(self, index):
        prefs.set("time_format", self._timefmt_combo.itemData(index))
        self.calculate()

    def _on_anglefmt_change(self, index):
        """Angle format of the whole software (and of the coordinates table when it follows)."""
        prefs.set("angle_format", self._anglefmt_combo.itemData(index))
        self.calculate()

    def _on_messier_toggled(self, checked):
        prefs.set("show_messier", bool(checked))
        if self._dte is not None:
            self.calculate()

    def _mag_limit(self):
        return _pref_float("mag_limit", 6.0)

    def _on_mag_changed(self, value):
        mag = value / 10.0
        prefs.set("mag_limit", mag)
        self._mag_lbl.setText(_num(mag, 1))
        self._schedule_recalc(120)

    def _on_interval_changed(self, value):
        interval = value * 500
        prefs.set("live_interval", interval)
        self._iv_lbl.setText(tf("units.ms", value=_num(interval)))
        if self.live_mode:
            self._live_timer.setInterval(interval)

    def _update_default_place_label(self):
        lat = _pref_float("default_lat", 0.0)
        lon = _pref_float("default_lon", 0.0)
        zone = prefs.get("default_tz") or _AUTO_ZONE
        text = f"{_fmt_lat(lat)}, {_fmt_lon(lon)} · "
        text += t("side.timezone_auto") if zone == _AUTO_ZONE else zone
        elevation = _pref_float("default_elevation", 0.0)
        if elevation:
            text += f" · {_elev_text(elevation)} m"
        self._default_coords_lbl.setText(text)

    def _save_default_place(self):
        """The typed place becomes the starting place (name, coordinates, time zone)."""
        try:
            _dte, lat, lon = self.current_inputs()
        except ValueError:
            self._warn_invalid_coords()
            return
        name = (self._place_entry.text().strip() or self.location_name
                or f"{lat:.4f}, {lon:.4f}")
        prefs.set("default_place", name)
        prefs.set("default_lat", round(lat, 4))
        prefs.set("default_lon", round(lon, 4))
        prefs.set("default_tz", self.tz_name)
        prefs.set("default_elevation", self._elevation())
        self._place_entry.setText(name)
        self._update_default_place_label()
        self.statusBar().showMessage(tf("settings.default_saved", name=name), 6000)

    def _reset_settings(self):
        answer = QMessageBox.question(
            self, t("settings.reset_title"), t("settings.reset_confirm"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return
        prefs.reset()
        Config.apply_theme(prefs.get("theme"))
        switch_lang(resolve_lang(prefs.get("lang"), QLocale.system().name()))
        self.tz_name = prefs.get("default_tz") or _AUTO_ZONE
        self.location_name = _clean_place(prefs.get("default_place"))
        if self.live_mode:
            self._live_timer.setInterval(int(prefs.get("live_interval") or 2000))
        self._rebuild(keep_place=False)
        self.statusBar().showMessage(t("settings.reset_done"), 6000)

    # ──────────────────────────────────────────────────────────────────────────
    # FAVOURITES
    # ──────────────────────────────────────────────────────────────────────────

    def _load_favorites(self):
        """The user's favourites; until one is saved, the preloaded places."""
        for path in (_FAVORITES_FILE, _LEGACY_FAVORITES_FILE):
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        return json.load(f)
                except (OSError, json.JSONDecodeError):
                    continue
        return _default_favorites()

    def _save_favorites(self):
        try:
            os.makedirs(os.path.dirname(_FAVORITES_FILE), exist_ok=True)
            with open(_FAVORITES_FILE, "w", encoding="utf-8") as f:
                json.dump(self.favorites, f, ensure_ascii=False, indent=2)
        except OSError as exc:
            QMessageBox.critical(self, t("errors.error_title"), str(exc))

    def _refresh_favorites_combo(self, select=None):
        self.combo_fav.blockSignals(True)
        self.combo_fav.clear()
        self.combo_fav.addItems(list(self.favorites))
        self.combo_fav.setCurrentIndex(self.combo_fav.findText(select) if select else -1)
        self.combo_fav.blockSignals(False)

    def _apply_favorite(self, index):
        name = self.combo_fav.itemText(index)
        loc = self.favorites.get(name)
        if not loc:
            return
        self.entry_lat.setText(_coord_text(float(loc["lat"])))
        self.entry_lon.setText(_coord_text(float(loc["lon"])))
        self.entry_elev.setText(_elev_text(float(loc.get("elev", 0))))
        self.location_name = name
        self.calculate()

    def _on_place_typed(self, text):
        """City suggestions at each letter (two at least)."""
        found = places.search(text) if len(text.strip()) >= 2 else []
        self._place_found = {}
        for place in found:
            self._place_found.setdefault(places.label(place), place)
        self._place_model.setStringList(list(self._place_found))
        if self._place_found:
            self._place_completer.complete()

    def _on_place_chosen(self, text):
        place = self._place_found.get(text)
        if place:
            self._apply_place(place)

    def _on_place_return(self):
        """Return without choosing: the first suggestion."""
        text = self.entry_place.text()
        if not text.strip() or text in self._place_found:
            return                                        # empty, or already handled by the choice
        found = places.search(text, limit=1)
        if found:
            self._apply_place(found[0])
        else:
            self.statusBar().showMessage(tf("side.place_unknown", name=text.strip()), 5000)

    def _apply_place(self, place):
        """A city chosen: coordinates, elevation and name, then calculation."""
        self._place_completer.popup().hide()
        self.entry_lat.setText(_coord_text(place["lat"]))
        self.entry_lon.setText(_coord_text(place["lon"]))
        self.entry_elev.setText(_elev_text(place["elevation"]))
        self.location_name = place["name"]
        self.combo_fav.setCurrentIndex(-1)
        QTimer.singleShot(0, self.entry_place.clear)
        self.calculate()

    def _on_coords_edited(self, _text):
        """Coordinates typed by hand: no longer a named place."""
        self.location_name = ""
        self.combo_fav.setCurrentIndex(-1)

    def save_location(self):
        try:
            _dte, lat, lon = self.current_inputs()
        except ValueError:
            self._warn_invalid_coords()
            return
        name, ok = QInputDialog.getText(self, t("favs.save_title"),
                                        t("favs.save_prompt"), text=self.location_name)
        name = name.strip()
        if not ok or not name:
            return
        self.favorites[name] = {"lat": round(lat, 4), "lon": round(lon, 4),
                                "elev": int(round(self._elevation()))}
        self._save_favorites()
        self._refresh_favorites_combo(select=name)
        self.location_name = name
        self._update_status()
        self.statusBar().showMessage(tf("favs.saved", name=name), 5000)

    def delete_location(self):
        name = self.combo_fav.currentText() if self.combo_fav.currentIndex() >= 0 else ""
        if name not in self.favorites:
            self.statusBar().showMessage(t("favs.none_selected"), 4000)
            return
        answer = QMessageBox.question(
            self, t("favs.delete_title"), tf("favs.delete_confirm", name=name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return
        del self.favorites[name]
        self._save_favorites()
        self._refresh_favorites_combo()
        self.statusBar().showMessage(tf("favs.deleted", name=name), 5000)

    # ──────────────────────────────────────────────────────────────────────────
    # DATE, TIME ZONE, TIME FORMAT
    # ──────────────────────────────────────────────────────────────────────────

    def _set_datetime(self, dte):
        """Shows *dte* (UT, without time zone) without triggering a recalculation."""
        qdt = QDateTime(QDate(dte.year, dte.month, dte.day),
                        QTime(dte.hour, dte.minute, dte.second), _utc_zone())
        self.dt_edit.blockSignals(True)
        self.dt_edit.setDateTime(qdt)
        self.dt_edit.blockSignals(False)

    def _edit_datetime(self):
        """Date and time typed, in UT (datetime without time zone)."""
        qdt = self.dt_edit.dateTime().toUTC()
        d, tm = qdt.date(), qdt.time()
        return datetime(d.year(), d.month(), d.day(), tm.hour(), tm.minute(), tm.second())

    def current_inputs(self):
        """The typed (UT date, latitude, longitude); ValueError when invalid."""
        lat = _parse_coord(self.entry_lat.text(), 90.0)
        lon = _parse_coord(self.entry_lon.text(), 180.0)
        return self._edit_datetime(), lat, lon

    def set_now(self):
        self._set_datetime(_utc_now())
        self.calculate()

    def _schedule_recalc(self, delay=350):
        if not self.live_mode:
            self._recalc_timer.start(delay)

    def _on_zone_change(self, index):
        self.tz_name = self.tz_menu.itemData(index) or _AUTO_ZONE
        self.calculate()

    def _select_zone(self, name):
        """Shows the time zone *name* in the selector, without recalculating."""
        idx = self.tz_menu.findData(name)
        if idx < 0:
            self.tz_menu.addItem(name, name)
            idx = self.tz_menu.count() - 1
        self.tz_menu.blockSignals(True)
        self.tz_menu.setCurrentIndex(idx)
        self.tz_menu.blockSignals(False)

    def _elevation(self):
        """Observer's elevation typed, in metres (0 when empty or invalid)."""
        try:
            return max(-500.0, min(9000.0, float(self.entry_elev.text().strip() or 0)))
        except ValueError:
            return 0.0

    def _local(self, dt):
        """Local time (without time zone) of the UT instant *dt*: the place's zone, summer time included."""
        return dt.replace(tzinfo=timezone.utc).astimezone(self._zone).replace(tzinfo=None)

    @property
    def utc_offset(self):
        """Offset of the time zone at the computed instant, in hours (summer time included)."""
        dte = getattr(self, "_dte", None) or _utc_now()
        return dte.replace(tzinfo=timezone.utc).astimezone(self._zone).utcoffset().total_seconds() / 3600

    def _midnight_offset(self):
        """Offset of the time zone at the local midnight of the computed day, in hours."""
        start = self._day_start or self._dte
        return (self._local(start) - start).total_seconds() / 3600

    def _zone_text(self):
        """"Europe/Paris · UTC+1": the time zone and its offset at the computed instant."""
        return f"{getattr(self._zone, 'key', 'UTC')} · {_fmt_offset(self.utc_offset)}"

    def _fmt_clock(self, dt):
        if prefs.get("time_format") == "12h":
            return dt.strftime("%I:%M %p").lstrip("0")
        return dt.strftime("%H:%M")

    def _format_event(self, dt):
        if dt is None:
            return "--:--"
        # rounded to the nearest minute, as in the almanacs (the engine gives the second)
        return self._fmt_clock(self._local(dt + timedelta(seconds=30)))

    # ──────────────────────────────────────────────────────────────────────────
    # GEOLOCATION / REAL TIME
    # ──────────────────────────────────────────────────────────────────────────

    def geolocate(self, interactive=True):
        """
        Position of the device from the system's location service (GPS, Wi-Fi:
        QtPositioning); when it is missing, denied or silent, its last known
        position, else the approximate position of the IP address. *interactive*
        (button): a window then says why the service did not answer and opens
        its settings; at startup, the status bar.
        """
        if self._geo_source is not None:                     # a request is under way
            return
        self._geo_interactive = interactive
        source = QGeoPositionInfoSource.createDefaultSource(self)
        if source is None:
            self._geolocate_by_ip("no_source")
            return
        if hasattr(source, "setPreferredPositioningMethods"):           # GPS, Wi-Fi, network
            source.setPreferredPositioningMethods(_ALL_POSITIONING_METHODS)
        self._geo_source = source
        source.positionUpdated.connect(self._on_device_position)
        source.errorOccurred.connect(self._on_device_position_error)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        self.statusBar().showMessage(t("errors.geoloc_waiting"))
        source.requestUpdate(_GEOLOC_TIMEOUT_MS)

    def _end_device_request(self):
        source, self._geo_source = self._geo_source, None
        if source is not None:
            source.positionUpdated.disconnect(self._on_device_position)
            source.errorOccurred.disconnect(self._on_device_position_error)
            source.deleteLater()
            QApplication.restoreOverrideCursor()

    def _on_device_position(self, info):
        self._end_device_request()
        coord = info.coordinate()
        if not coord.isValid():
            self._geolocate_by_ip("invalid")
            return
        lat, lon = coord.latitude(), coord.longitude()
        name = _place_name(lat, lon)
        self._set_place(lat, lon, name, _zone_at(round(lat, 3), round(lon, 3)))
        accuracy = info.attribute(QGeoPositionInfo.Attribute.HorizontalAccuracy)
        precision = f" (±{_num(accuracy)} m)" if accuracy == accuracy and accuracy > 0 else ""
        self.statusBar().showMessage(
            tf("errors.geoloc_device", place=name or f"{_fmt_lat(lat)}, {_fmt_lon(lon)}",
               precision=precision), 8000)

    def _on_device_position_error(self, error):
        source = self._geo_source
        last = source.lastKnownPosition() if hasattr(source, "lastKnownPosition") else None
        self._end_device_request()
        if last is not None and last.isValid() and last.coordinate().isValid():
            self._on_device_position(last)                    # last known position
            return
        code = getattr(error, "value", error)
        reason = {0: "access", 1: "closed", 4: "timeout"}.get(code, "unknown")
        self._geolocate_by_ip(reason)

    def choose_on_map(self):
        """The place picked on a map (PlacePicker): coordinates, name, time zone, elevation of
        the nearest city, then calculation."""
        try:
            _dte, lat, lon = self.current_inputs()
        except ValueError:
            lat, lon = 48.0, 2.0
        picker = PlacePicker(self, lat, lon)
        self._place_picker = picker
        if picker.exec() != QDialog.DialogCode.Accepted or picker.chosen is None:
            return None
        lat, lon = picker.chosen
        near = places.nearest(lat, lon, max_km=10.0)
        if near:
            self.entry_elev.setText(_elev_text(near["elevation"]))
        self._set_place(lat, lon, picker.name, _zone_at(round(lat, 3), round(lon, 3)))
        return lat, lon

    def _set_place(self, lat, lon, name, zone=None):
        """Place found by geolocation: coordinates, name, time zone, then calculation."""
        self.entry_lat.setText(_coord_text(lat))
        self.entry_lon.setText(_coord_text(lon))
        if zone and self.tz_name != _AUTO_ZONE and self.tz_menu.findData(zone) >= 0:
            self.tz_name = zone
            self._select_zone(zone)
        self.location_name = name
        self.combo_fav.setCurrentIndex(-1)
        self.calculate()

    def _geolocate_by_ip(self, reason=None):
        """Fallback: position of the IP address, often the internet provider's;
        *reason*: why the device's service did not answer. Without an answer, the map."""
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            found = _ip_location()
        finally:
            QApplication.restoreOverrideCursor()
        if found is None:
            self._explain_geolocation(reason or "unknown", None, None)
            return
        lat, lon, city, country, zone = found
        self._set_place(lat, lon, city, zone)
        self.statusBar().showMessage(tf("errors.geoloc_ip", city=city or "?", country=country or "?"), 12000)
        if reason and getattr(self, "_geo_interactive", False):
            self._explain_geolocation(reason, city or "?", country or "?")

    def _explain_geolocation(self, reason, city, country):
        """Window (non-modal): position of the IP (or none), why, the map to pick the place
        on, and the system settings to open."""
        text = (tf("errors.geoloc_ip_short", city=city, country=country) if city is not None
                else t("errors.geoloc_no_answer"))
        box = QMessageBox(QMessageBox.Icon.Information, t("errors.geoloc_title"), text, parent=self)
        box.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        box.setInformativeText(t(f"errors.geoloc_reason_{reason}"))
        on_map = box.addButton(t("errors.geoloc_choose_map"), QMessageBox.ButtonRole.AcceptRole)
        url = _LOCATION_SETTINGS.get(sys.platform)
        settings = None
        if url and reason in ("access", "closed", "no_source", "timeout"):
            settings = box.addButton(t("errors.geoloc_open_settings"), QMessageBox.ButtonRole.ActionRole)
        box.addButton(QMessageBox.StandardButton.Close)
        box.setDefaultButton(on_map)

        def done(_result):
            if box.clickedButton() is on_map:
                QTimer.singleShot(0, self.choose_on_map)
            elif settings is not None and box.clickedButton() is settings:
                QDesktopServices.openUrl(QUrl(url))
        box.finished.connect(done)
        self._geo_dialog = box
        box.open()

    def toggle_live(self, checked):
        self.live_mode = bool(checked)
        self._apply_live_ui()
        if self.live_mode:
            self._live_timer.start(int(prefs.get("live_interval") or 2000))
            self._live_tick()
        else:
            self._live_timer.stop()

    def _apply_live_ui(self):
        """Real time: the button stays pressed (encre fill), the date freezes."""
        on = self.live_mode
        self.dt_edit.setReadOnly(on)
        _repolish(self.dt_edit)
        self.field_date.set_inactive(on)
        self.btn_now.setEnabled(not on)
        self._lbl_live.setVisible(on)

    def _live_tick(self):
        self._set_datetime(_utc_now())
        self.calculate()

    # ──────────────────────────────────────────────────────────────────────────
    # MAIN CALCULATION
    # ──────────────────────────────────────────────────────────────────────────

    def _warn_invalid_coords(self):
        QMessageBox.warning(self, t("errors.error_title"), t("status.invalid_coords"))

    def _check_inputs(self):
        """Flags invalid coordinates under their field; True when all is valid."""
        ok = True
        for edit, field, limit, key in ((self.entry_lat, self.field_lat, 90.0, "side.lat_error"),
                                        (self.entry_lon, self.field_lon, 180.0, "side.lon_error")):
            try:
                _parse_coord(edit.text(), limit)
                _set_invalid(edit, False)
                field.set_error(None)
            except ValueError:
                _set_invalid(edit, True)
                field.set_error(t(key))
                ok = False
        return ok

    def calculate(self):
        """Computes everything for the typed date and place, then updates the display."""
        self._recalc_timer.stop()
        if not self._check_inputs():
            self.statusBar().showMessage(t("status.invalid_coords"), 6000)
            return
        dte, lat, lon = self.current_inputs()
        self._dte, self._lat, self._lon = dte, lat, lon
        self._zone = _zone(self.tz_name, lat, lon)
        elev = self._elevation()

        jd = AstroEngine.julian_day(dte)
        tc = AstroEngine.julian_century_j2000(dte)

        s_l, r_sun  = AstroEngine.sun_position(tc)
        s_ra, s_dec = AstroEngine.ecliptic_to_equatorial(s_l, 0, tc)
        s_alt, s_az = AstroEngine.horizontal(tc, lat, lon, "sun", elev)

        m_l, m_b, m_p = AstroEngine.moon_position(tc)
        m_ra, m_dec   = AstroEngine.ecliptic_to_equatorial(m_l, m_b, tc)
        m_alt_c, m_az = AstroEngine.horizontal(tc, lat, lon, "moon", elev, refraction=True)

        phase = AstroEngine.mod360(m_l - s_l)
        illum, age = AstroEngine.moon_phase(tc)

        self.sun_data  = {"name": "Sun", "ra": s_ra, "dec": s_dec, "alt": s_alt,
                          "az": s_az, "dist": r_sun,
                          "eot": AstroEngine.equation_of_time(tc)}
        self.moon_data = {"name": "Moon", "ra": m_ra, "dec": m_dec, "alt": m_alt_c,
                          "az": m_az, "illum": illum, "phase": phase,
                          "dist": 6378.14 / math.sin(math.radians(m_p)),
                          "age": age}

        # Events of the day and 24 h curves: only when the date or the place changes
        key = (f"{self._local(dte):%Y-%m-%d}_{lat:.4f}_{lon:.4f}_"
               f"{getattr(self._zone, 'key', 'UTC')}_{elev:g}")
        if key != self.last_cache_key:
            self.sun_events  = AstroEngine.find_events(dte, lat, lon, "sun", self._zone, elev)
            self.moon_events = AstroEngine.find_events(dte, lat, lon, "moon", self._zone, elev)
            self.planet_events = {name: AstroEngine.find_events(dte, lat, lon, name, self._zone, elev)
                                  for name in _PLANETS + MINOR_PLANETS + AstroEngine.comets_at(tc)}
            self.hours, self.sun_altitudes, self.moon_altitudes = \
                charts.sample_day(dte, lat, lon, elevation_m=elev, tz=self._zone)
            self._day_start = AstroEngine._local_day(dte, self._zone)[0]
            self.last_cache_key = key

        self.planets, self.minor_planets = [], []
        self._comets_now = AstroEngine.comets_at(tc)                  # within their tables (2025–2031)
        bodies = _PLANETS + MINOR_PLANETS + self._comets_now
        magnitudes = AstroEngine.observations(tc, bodies)
        for name in bodies:
            ra, dec, dist = AstroEngine.planet_position(tc, name)
            alt, az = AstroEngine.horizontal(tc, lat, lon, name, elev)
            minor = name not in _PLANETS
            (self.minor_planets if minor else self.planets).append({
                "name": name, "ra": ra, "dec": dec, "dist": dist, "alt": alt, "az": az,
                "elong": AstroEngine.angular_separation(ra, dec, s_ra, s_dec),
                "east": (ra - s_ra) % 24 < 12, "mag": magnitudes[name]["mag"], "minor": minor,
                "comet": name in COMETS,
            })

        # on the map, the minor planets and comets bright enough for the chosen limit
        bright = [m for m in self.minor_planets if m["mag"] <= self._mag_limit()]
        alts, azs = AstroEngine.deep_sky_horizontal(tc, lat, lon, elev)
        self._deep_sky_all = [{**obj, "alt": float(alt), "az": float(az)}
                              for obj, alt, az in zip(messier_catalog(), alts, azs)]
        deep_sky = [o for o in self._deep_sky_all if o["alt"] > 0] if prefs.get("show_messier") else []
        self._sky_scene = charts.sky_scene(jd, lat, lon, self._mag_limit(), self.sun_data, self.moon_data,
                                           self.planets + bright, deep_sky,
                                           [tuple(p) for p in prefs.get("horizon_points") or []])
        self._refresh_sky_objects()
        self.visible_stars = [s["name"] for s in self._sky_scene["stars"]]
        self.visible_planets_map = [p["name"] for p in self.planets if p["alt"] > 0]

        self._update_data_cards()
        self._update_tonight(dte, lat, lon, elev)
        self._update_sun_card()
        self._update_moon_card()
        self._update_planet_table()
        self._refresh_coordinates()
        self._update_status()
        self._dirty = {"traj", "sky", "orrery"}
        self._draw_visible_chart()
        self._note_calculation(dte, lat, lon, elev)

    # ── History of the calculations ───────────────────────────────────────────

    def _calculate_quietly(self):
        """A calculation the user did not ask for (start, new language or theme):
        it stays out of the history."""
        self._history_quiet = True
        try:
            self.calculate()
        finally:
            self._history_quiet = False

    def _note_calculation(self, dte, lat, lon, elev):
        """
        The calculation shown enters the history once the user has stayed on it
        for a few seconds: not each step through the dates, not each tick of
        the real-time mode.
        """
        if self._history_quiet or self.live_mode:
            return
        self._history_pending = history.entry(dte, lat, lon, elev, self.location_name, self.tz_name)
        self._history_timer.start(_HISTORY_DELAY_MS)

    def _commit_history(self):
        self._history_timer.stop()
        item, self._history_pending = self._history_pending, None
        if item is not None:
            self.history = history.add(self.history, item)
            history.save(self.history)

    def _history_label(self, item):
        """"01/11/2026 21:30 UT · Cherbourg-en-Cotentin" (or the coordinates of an unnamed place)."""
        place = item["name"] or f"{_fmt_lat(item['lat'])}, {_fmt_lon(item['lon'])}"
        return f"{history.when(item):%d/%m/%Y %H:%M} {t('chart.ut')} · {place}"

    # ── Workshop ──────────────────────────────────────────────────────────

    def show_workshop(self):
        """Window of the Workshop: an instrument, its place, date and options, a preview
        page by page, and the PDF to save. The place starts as the side panel's."""
        import workshop
        dlg = QDialog(self)
        dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dlg.setWindowTitle(t("workshop.title"))
        dlg.setMinimumSize(980, 700)
        outer = QHBoxLayout(dlg)
        outer.setContentsMargins(24, 24, 24, 16)
        outer.setSpacing(24)

        # left: the choices, in a column that scrolls when the window is low
        form = QWidget()
        left = QVBoxLayout(form)
        left.setContentsMargins(0, 0, 8, 0)
        left.setSpacing(12)
        left.addWidget(_label(t("workshop.title"), "sous-titre"))
        intro = _label("", "legende", wrap=True)
        left.addWidget(intro)
        kinds = QComboBox()
        for kind in workshop.INSTRUMENTS:
            kinds.addItem(t(f"workshop.{kind}"), kind)
        left.addWidget(InputField(t("workshop.instrument"), kinds))
        description = _label("", "corps", wrap=True)
        left.addWidget(description)

        left.addWidget(_label(t("workshop.where_title"), "label", strong=True))
        place_edit = QLineEdit()
        place_edit.setPlaceholderText(t("side.place_placeholder"))
        place_edit.setClearButtonEnabled(True)
        model = QStringListModel(dlg)
        completer = QCompleter(model, dlg)
        completer.setCompletionMode(QCompleter.CompletionMode.UnfilteredPopupCompletion)
        completer.setMaxVisibleItems(10)
        place_edit.setCompleter(completer)
        left.addWidget(InputField(t("side.place"), place_edit))
        validator = QRegularExpressionValidator(QRegularExpression(_COORD_REGEX))
        lat_edit, lon_edit = QLineEdit(self.entry_lat.text()), QLineEdit(self.entry_lon.text())
        lat_field = InputField(t("side.latitude"), lat_edit, unit="°", numeric=True)
        lon_field = InputField(t("side.longitude"), lon_edit, unit="°", numeric=True)
        for edit in (lat_edit, lon_edit):
            edit.setValidator(validator)
        coords = QHBoxLayout()
        coords.setSpacing(12)
        coords.addWidget(lat_field)
        coords.addWidget(lon_field)
        left.addLayout(coords)
        zone_menu = QComboBox()
        zone_menu.setEditable(True)
        zone_menu.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        zone_menu.setMaxVisibleItems(14)
        zone_menu.addItem(t("side.timezone_auto"), _AUTO_ZONE)
        for name in _zone_names():
            zone_menu.addItem(name, name)
        zc = zone_menu.completer()
        zc.setFilterMode(Qt.MatchFlag.MatchContains)
        zc.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        zone_menu.setCurrentIndex(max(0, zone_menu.findData(self.tz_name)))
        left.addWidget(InputField(t("side.timezone"), zone_menu))
        date_edit = QDateEdit()
        date_edit.setCalendarPopup(True)
        date_edit.setDisplayFormat("dd/MM/yyyy")
        date_edit.setMinimumDate(QDate(EPHEMERIS_YEARS[0], 1, 1))
        date_edit.setMaximumDate(QDate(EPHEMERIS_YEARS[1], 12, 31))
        local = self._local(self._edit_datetime())
        date_edit.setDate(QDate(local.year, local.month, local.day))
        left.addWidget(InputField(t("workshop.date"), date_edit, hint=t("workshop.date_hint")))
        from_panel = _button(t("workshop.from_panel"), "place", "discret", compact=True)
        left.addWidget(from_panel)

        left.addWidget(_label(t("workshop.options_title"), "label", strong=True))
        size = QComboBox()
        for mm in workshop.ASTROLABE_SIZES:
            size.addItem(tf("workshop.size_mm", size=mm), mm)
        size.setCurrentIndex(len(workshop.ASTROLABE_SIZES) - 1)
        size_field = InputField(t("workshop.size"), size)
        left.addWidget(size_field)
        paper = QComboBox()
        for key in workshop.PAPERS:
            paper.addItem(t(f"workshop.paper_{key}"), key)
        left.addWidget(InputField(t("workshop.paper"), paper))
        problem = _label("", "legende", tone="alerte", strong=True, wrap=True)
        problem.hide()
        left.addWidget(problem)
        left.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(form)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        column = QVBoxLayout()
        column.setSpacing(8)
        column.addWidget(scroll, stretch=1)
        save = _button(t("workshop.save"), "export", "principal")
        column.addWidget(save)
        close = _button(t("detail.close"))
        close.clicked.connect(dlg.reject)
        column.addWidget(close)
        outer.addLayout(column, stretch=2)

        right = QVBoxLayout()
        right.setSpacing(8)
        preview = QLabel()
        preview.setObjectName("workshopPreview")
        preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview.setMinimumSize(440, 600)
        preview.setStyleSheet("background: white; border-radius: 4px;")
        right.addWidget(preview, stretch=1)
        nav = QHBoxLayout()
        previous = _icon_button("previous", t("workshop.previous_page"), compact=True)
        following = _icon_button("next", t("workshop.next_page"), compact=True)
        page_label = _label("", "legende")
        nav.addStretch()
        nav.addWidget(previous)
        nav.addWidget(page_label)
        nav.addWidget(following)
        nav.addStretch()
        right.addLayout(nav)
        outer.addLayout(right, stretch=3)

        state = {"page": 0, "pages": 1, "place": None, "name": self.entry_place.text().strip()
                 or getattr(self, "location_name", "") or "", "found": {}}
        timer = QTimer(dlg)
        timer.setSingleShot(True)

        def current_place():
            """The place of the fields; an error text instead when they are not usable."""
            try:
                lat = _parse_coord(lat_edit.text(), 90.0)
                lon = _parse_coord(lon_edit.text(), 180.0)
            except ValueError:
                return t("status.invalid_coords")
            if not 10.0 <= abs(lat) <= 80.0:
                return t("workshop.latitude_range")
            zone = _zone(zone_menu.currentData() or _AUTO_ZONE, lat, lon)
            day = date_edit.date()
            noon = datetime(day.year(), day.month(), day.day(), 20, 0, tzinfo=zone)
            when = noon.astimezone(timezone.utc).replace(tzinfo=None)
            return workshop.Place(state["name"], lat, lon, zone, when)

        def options():
            return {"size": size.currentData()} if kinds.currentData() == "astrolabe" else {}

        def refresh():
            kind = kinds.currentData()
            description.setText(t(f"workshop.desc_{kind}"))
            size_field.setVisible(kind == "astrolabe")
            place = current_place()
            if isinstance(place, str):
                problem.setText(place)
                problem.show()
                save.setEnabled(False)
                state["place"] = None
                return
            problem.hide()
            save.setEnabled(True)
            state["place"] = place
            intro.setText(tf("workshop.intro", place=place.describe()))
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            try:
                png, count = workshop.preview_png(kind, place, paper.currentData(), state["page"], dpi=72,
                                                  options=options())
            finally:
                QApplication.restoreOverrideCursor()
            state["pages"] = count
            state["page"] = min(state["page"], count - 1)
            pixmap = QPixmap()
            pixmap.loadFromData(png, "PNG")
            preview.setPixmap(pixmap.scaled(preview.size() - QSize(16, 16), Qt.AspectRatioMode.KeepAspectRatio,
                                            Qt.TransformationMode.SmoothTransformation))
            page_label.setText(tf("workshop.page", page=state["page"] + 1, pages=count))
            previous.setEnabled(state["page"] > 0)
            following.setEnabled(state["page"] < count - 1)

        def later():
            timer.start(450)

        def turn(step):
            state["page"] = max(0, min(state["pages"] - 1, state["page"] + step))
            refresh()

        def choose():
            state["page"] = 0
            refresh()

        def typed_coords():
            state["name"] = ""                          # coordinates typed: no more the city's name
            later()

        def typed_place(text):
            found = places.search(text) if len(text.strip()) >= 2 else []
            state["found"] = {}
            for p in found:
                state["found"].setdefault(places.label(p), p)
            model.setStringList(list(state["found"]))
            if state["found"]:
                completer.complete()

        def apply_city(p):
            completer.popup().hide()
            lat_edit.setText(_coord_text(p["lat"]))
            lon_edit.setText(_coord_text(p["lon"]))
            state["name"] = p["name"]
            choose()

        def chosen(text):
            p = state["found"].get(text)
            if p:
                apply_city(p)

        def returned():
            text = place_edit.text()
            if not text.strip() or text in state["found"]:
                return
            found = places.search(text, limit=1)
            if found:
                apply_city(found[0])

        def back_to_panel():
            lat_edit.setText(self.entry_lat.text())
            lon_edit.setText(self.entry_lon.text())
            zone_menu.setCurrentIndex(max(0, zone_menu.findData(self.tz_name)))
            loc = self._local(self._edit_datetime())
            date_edit.setDate(QDate(loc.year, loc.month, loc.day))
            state["name"] = getattr(self, "location_name", "") or ""
            place_edit.clear()
            choose()

        def save_pdf():
            place = state["place"]
            if place is None:
                return
            kind = kinds.currentData()
            default = os.path.join(os.path.expanduser("~"), f"{t(f'workshop.{kind}')}.pdf")
            path, _filter = QFileDialog.getSaveFileName(dlg, t("workshop.save_title"), default,
                                                        t("workshop.pdf_filter"))
            if not path:
                return
            if not path.lower().endswith(".pdf"):
                path += ".pdf"
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            try:
                count = workshop.print_instrument(kind, path, place, paper.currentData(), options())
            except OSError as exc:
                QApplication.restoreOverrideCursor()
                QMessageBox.warning(dlg, t("errors.error_title"), tf("workshop.save_error", error=exc))
                return
            QApplication.restoreOverrideCursor()
            self.statusBar().showMessage(tf("workshop.saved", path=path, pages=count), 12000)

        timer.timeout.connect(choose)
        kinds.currentIndexChanged.connect(lambda _i: choose())
        paper.currentIndexChanged.connect(lambda _i: refresh())
        size.currentIndexChanged.connect(lambda _i: refresh())
        zone_menu.currentIndexChanged.connect(lambda _i: later())
        date_edit.dateChanged.connect(lambda _d: later())
        lat_edit.textEdited.connect(lambda _t: typed_coords())
        lon_edit.textEdited.connect(lambda _t: typed_coords())
        place_edit.textEdited.connect(typed_place)
        completer.activated.connect(chosen)
        place_edit.returnPressed.connect(returned)
        from_panel.clicked.connect(lambda _checked=False: back_to_panel())
        previous.clicked.connect(lambda _checked=False: turn(-1))
        following.clicked.connect(lambda _checked=False: turn(1))
        save.clicked.connect(lambda _checked=False: save_pdf())
        dlg.workshop_fields = {"kinds": kinds, "place": place_edit, "lat": lat_edit, "lon": lon_edit,
                               "zone": zone_menu, "date": date_edit, "size": size, "paper": paper,
                               "save": save, "problem": problem, "preview": preview, "timer": timer}
        self._workshop_dialog = dlg
        dlg.show()
        refresh()
        return dlg

    def _show_history_menu(self):
        """Menu under the History button: the last calculations, the most recent first."""
        self._commit_history()                            # the calculation shown comes first
        menu = QMenu(self)
        menu.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        for item in self.history:
            action = menu.addAction(self._history_label(item))
            action.triggered.connect(lambda _checked=False, it=item: self._restore_calculation(it))
        if self.history:
            menu.addSeparator()
            menu.addAction(t("history.clear")).triggered.connect(self._clear_history)
        else:
            menu.addAction(t("history.empty")).setEnabled(False)
        self._history_menu = menu
        menu.popup(self.btn_history.mapToGlobal(QPoint(0, self.btn_history.height())))

    def _restore_calculation(self, item):
        """Brings a calculation of the history back: date, place, elevation and time zone."""
        if self.live_mode:
            self.btn_live.setChecked(False)
        self._set_datetime(history.when(item))
        self.entry_lat.setText(_coord_text(item["lat"]))
        self.entry_lon.setText(_coord_text(item["lon"]))
        self.entry_elev.setText(_elev_text(item["elev"]))
        self.location_name = item["name"]
        favorite = self.favorites.get(item["name"])
        same_place = bool(favorite) and (round(float(favorite["lat"]), 4), round(float(favorite["lon"]), 4)) \
            == (item["lat"], item["lon"])
        self.combo_fav.setCurrentIndex(self.combo_fav.findText(item["name"]) if same_place else -1)
        self.tz_name = item["tz"]
        self._select_zone(self.tz_name)
        self.calculate()
        self._commit_history()                            # back to the top of the list at once

    def _clear_history(self):
        self._history_timer.stop()
        self._history_pending = None
        self.history = []
        history.save(self.history)
        self.statusBar().showMessage(t("history.cleared"), 5000)

    def closeEvent(self, event):
        self._commit_history()                            # a calculation made just before closing
        super().closeEvent(event)

    # ──────────────────────────────────────────────────────────────────────────
    # UPDATING THE CARDS
    # ──────────────────────────────────────────────────────────────────────────

    def _events_title(self):
        return tf("common.events_title", offset=_fmt_offset(self.utc_offset))

    def _day_length(self):
        rise, sunset = self.sun_events.get("rise"), self.sun_events.get("set")
        if rise is None or sunset is None:
            return "—"
        minutes = round((sunset - rise).total_seconds() / 60) % 1440
        return tf("units.duration", h=minutes // 60, m=f"{minutes % 60:02d}")

    def _sun_phase(self):
        return charts.day_phase(self.sun_data["alt"])

    def _update_data_cards(self):
        sd, md = self.sun_data, self.moon_data
        self.card_sun_alt.set_value(
            _num(sd["alt"], 1, signed=True), "°",
            f"{tf('cards.azimuth', value=_deg(sd['az'], 1))} · {t('sun.state_' + self._sun_phase())}")
        rise, sunset = self.sun_events.get("rise"), self.sun_events.get("set")
        self.card_sun_rise.set_value(
            self._format_event(rise), "",
            tf("cards.set_at", time=self._format_event(sunset)))
        self.card_moon_alt.set_value(
            _num(md["alt"], 1, signed=True), "°",
            f"{tf('cards.rise_at', time=self._format_event(self.moon_events.get('rise')))} · "
            f"{tf('cards.set_at', time=self._format_event(self.moon_events.get('set')))}")
        key = Formatters.PHASES[Formatters.phase_index(md["phase"])][0]
        self.card_moon_illum.set_value(_num(md["illum"], 0), "%", t(f"phases.{key}"))

    def _update_sun_card(self):
        sd, lb, ev = self.sun_data, self.sun_labels, self.sun_events
        lb["ra"].setText(_ra(sd["ra"]))
        lb["dec"].setText(_dec(sd["dec"]))
        lb["alt"].setText(_dec(sd["alt"]))
        lb["az"].setText(_az(sd["az"]))
        lb["eot"].setText(tf("units.minutes", value=_num(sd["eot"], 1, signed=True)))
        lb["dist"].setText(tf("units.au", value=_num(sd["dist"], 4)))
        for key in ("dawn_astro", "dawn_naut", "dawn_civ", "rise", "transit",
                    "set", "dusk_civ", "dusk_naut", "dusk_astro"):
            lb[key].setText(self._format_event(ev.get(key)))
        lb["day_length"].setText(self._day_length())
        self._sun_events_title.setText(self._events_title())
        phase = self._sun_phase()
        _set_badge(self._lbl_sun_state, t(f"sun.state_{phase}"),
                      "info" if phase == "day" else "neutre")

    def _update_tonight(self, dte, lat, lon, elev):
        """The "Tonight" summary, computed again when the night, the place or the time zone change."""
        start = AstroEngine._local_day(dte - timedelta(hours=12), self._zone)[0]
        key = (f"{start:%Y-%m-%d %H}", round(lat, 4), round(lon, 4),
               getattr(self._zone, "key", "UTC"), elev)
        if key == self._tonight_key:
            return
        self._tonight_key = key
        self._tonight, self._upcoming = _tonight_and_upcoming(key, dte, lat, lon, elev, self._zone)
        while self._tonight_box.count():
            item = self._tonight_box.takeAt(0)
            if item.widget():
                item.widget().hide()                  # deleteLater() only acts on the next turn
                item.widget().deleteLater()
        for text, tone in self._tonight_lines():
            self._tonight_box.addWidget(_label(text, "corps" if tone is None else "legende",
                                               tone=tone or None, wrap=True))

    def _tonight_lines(self):
        """[(text, tone)] of the summary: the night, the Moon, a line per visible planet, what comes next."""
        n, clock = self._tonight, self._clock
        lines = []
        if n["dark"] is None:
            lines.append((t("tonight.no_night"), None))
        else:
            lines.append((tf(f"tonight.dark_{n['dark']}", start=clock(n["dusk"]), end=clock(n["dawn"])), None))
        moon = n["moon"]
        rise, sets = moon["rise"], moon["set"]
        if rise and sets:
            when = (tf("tonight.moon_rises_sets", rise=clock(rise), set=clock(sets)) if rise < sets
                    else tf("tonight.moon_sets_rises", rise=clock(rise), set=clock(sets)))
        elif rise:
            when = tf("tonight.moon_rises", time=clock(rise))
        elif sets:
            when = tf("tonight.moon_sets", time=clock(sets))
        else:
            when = t("tonight.moon_up" if moon["up"] > 0.5 else "tonight.moon_down")
        lines.append((f"{SYMBOL['Moon']} " + tf("tonight.moon", pct=_num(100.0 * moon["fraction"]), when=when),
                      None))
        if not n["planets"]:
            lines.append((t("tonight.no_planet"), "attenuee"))
        for planet in n["planets"]:
            seen = self._visibility_text(planet)
            text = f"{_planet_name(planet['name'], symbol=True)} · {seen[:1].lower()}{seen[1:]}"
            mag = tf("events.magnitude", value=_num(planet["mag"], 1))
            text += f" · {mag[:1].lower()}{mag[1:]}"
            if planet["rise"]:
                text += " · " + tf("tonight.rises", time=clock(planet["rise"]))
            if planet["set"]:
                text += " · " + tf("tonight.sets", time=clock(planet["set"]))
            lines.append((text, None))
        if n.get("satellites"):
            items = [tf("tonight.satellite_item", name=_satellite_name(p["name"], short=True),
                        start=clock(p["start"]), end=clock(p["end"]), alt=_num(p["max_alt"]),
                        dir=self._wind(p["max_az"])) for p in n["satellites"][:4]]
            lines.append((tf("tonight.satellites", passes=" · ".join(items)), None))
        if n.get("deep_sky"):
            catalog = messier_catalog()
            items = [tf("tonight.deep_sky_item", name=_messier_label(catalog[o["m"] - 1]), alt=_num(o["alt"]),
                        time=clock(o["best"])) for o in n["deep_sky"]]
            lines.append((tf("tonight.deep_sky", objects=" · ".join(items)), None))
        if self._upcoming:
            items = []
            for ev in self._upcoming:
                best = self._local(ev["visibility"]["best"])
                items.append(tf("tonight.event", date=f"{best:%d/%m}", title=self._event_title(ev, symbol=False),
                                when=t(f"tonight.period_{ev['visibility']['period']}")))
            lines.append((tf("tonight.upcoming", events=" · ".join(items)), "attenuee"))
        else:
            lines.append((t("tonight.no_upcoming"), "attenuee"))
        return lines

    # ── Lunar calendar ────────────────────────────────────────────────────────

    def _show_moon_calendar(self, year=None, month=None):
        """Window (non-modal): the Moon day by day over a month, seen from here."""
        if not self._check_inputs():
            self._warn_invalid_coords()
            return
        local = self._local(self._dte or _utc_now())
        dlg = getattr(self, "_calendar_dialog", None)
        if dlg is None:
            dlg = QDialog(self)
            dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
            dlg.setWindowTitle(t("calendar.window_title"))
            dlg.resize(980, 720)
            lay = QVBoxLayout(dlg)
            lay.setContentsMargins(24, 24, 24, 16)
            lay.setSpacing(12)
            head = QHBoxLayout()
            prev = _icon_button("previous", t("calendar.previous"))
            nxt = _icon_button("next", t("calendar.next"))
            prev.clicked.connect(lambda: self._fill_moon_calendar(-1))
            nxt.clicked.connect(lambda: self._fill_moon_calendar(+1))
            dlg._title = _label("", "sous-titre")
            head.addWidget(prev)
            head.addWidget(dlg._title)
            head.addWidget(nxt)
            head.addStretch()
            lay.addLayout(head)
            dlg._grid = QGridLayout()
            dlg._grid.setSpacing(6)
            lay.addLayout(dlg._grid, stretch=1)
            dlg._note = _label("", "legende", tone="attenuee", wrap=True)
            lay.addWidget(dlg._note)
            buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
            buttons.rejected.connect(dlg.reject)
            lay.addWidget(buttons)
            dlg.destroyed.connect(lambda *_: setattr(self, "_calendar_dialog", None))
            self._calendar_dialog = dlg
        dlg._month = (year or local.year, month or local.month)
        self._fill_moon_calendar(0)
        dlg.show()
        dlg.raise_()

    def _fill_moon_calendar(self, step):
        """Fills the grid of the month shown, moved by *step* months."""
        dlg = self._calendar_dialog
        year, month = dlg._month
        month += step
        year, month = year + (month - 1) // 12, (month - 1) % 12 + 1
        dlg._month = (year, month)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            days = AstroEngine.moon_calendar(year, month, self._lat, self._lon, self._elevation(), self._zone)
        finally:
            QApplication.restoreOverrideCursor()
        grid = dlg._grid
        while grid.count():
            item = grid.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()
        loc = _locale()
        name = loc.standaloneMonthName(month, QLocale.FormatType.LongFormat)
        dlg._title.setText(f"{name[:1].upper()}{name[1:]} {year}")
        first = loc.firstDayOfWeek().value                # 1 Monday … 7 Sunday
        for col in range(7):
            day = (first - 1 + col) % 7 + 1
            head = _label(loc.standaloneDayName(day, QLocale.FormatType.ShortFormat), "legende",
                          tone="attenuee")
            head.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(head, 0, col)
        offset = (days[0]["date"].isoweekday() - first) % 7
        today = self._local(self._dte).date() if self._dte else None
        southern = (self._lat or 0) < 0
        for i, d in enumerate(days):
            cell = _card()
            cell.setProperty("calendarDay", True)
            box = QVBoxLayout(cell)
            box.setContentsMargins(8, 6, 8, 6)
            box.setSpacing(2)
            top = QHBoxLayout()
            top.addWidget(_label(str(d["date"].day), "corps", tone="or" if d["date"] == today else None,
                                 strong=True))
            top.addStretch()
            disc = MoonPhase(26)
            disc.set_phase(d["phase"], southern=southern)
            top.addWidget(disc)
            box.addLayout(top)
            box.addWidget(_label(f"{_num(100.0 * d['fraction'])} %", "legende"))
            rise = self._clock(d["rise"]) if d["rise"] else "—"
            sets = self._clock(d["set"]) if d["set"] else "—"
            times = _label(f"↑ {rise}   ↓ {sets}", "legende", tone="attenuee")
            times.setToolTip(t("calendar.rise_set_tip"))
            box.addWidget(times)
            if d["event"]:
                ev = d["event"]
                box.addWidget(_label(f"{t('phases.' + ev['kind'])} {self._clock(ev['time'])}", "legende",
                                     tone="lune", strong=True))
            box.addStretch()
            grid.addWidget(cell, 1 + (offset + i) // 7, (offset + i) % 7)
        for row in range(1, 7):
            grid.setRowStretch(row, 1)
        for col in range(7):
            grid.setColumnStretch(col, 1)
            grid.setColumnMinimumWidth(col, 110)
        dlg._note.setText(tf("calendar.note", zone=getattr(self._zone, "key", "UTC"),
                             place=self.location_name or f"{_fmt_lat(self._lat)}, {_fmt_lon(self._lon)}"))

    def _update_moon_card(self):
        md, lb, ev = self.moon_data, self.moon_labels, self.moon_events
        lb["ra"].setText(_ra(md["ra"]))
        lb["dec"].setText(_dec(md["dec"]))
        lb["alt"].setText(_dec(md["alt"]))
        lb["az"].setText(_az(md["az"]))
        lb["dist"].setText(tf("units.km", value=_num(md["dist"])))
        key = Formatters.PHASES[Formatters.phase_index(md["phase"])][0]
        self._phase_disc.set_phase(md["phase"], southern=(self._lat or 0) < 0)
        self._lbl_phase_name.setText(t(f"phases.{key}"))
        self._illum_bar.setValue(int(round(md["illum"] * 10)))
        lb["illum"].setText(f"{_num(md['illum'], 1)} %")
        lb["age"].setText(tf("units.days", value=_num(md["age"], 1)))
        for key in ("rise", "transit", "set"):
            lb[key].setText(self._format_event(ev.get(key)))
        self._moon_events_title.setText(self._events_title())
        if md["alt"] > 0:
            _set_badge(self._lbl_moon_state, t("common.above_horizon"), "info")
        else:
            _set_badge(self._lbl_moon_state, t("common.below_horizon"), "neutre")

    def _update_planet_table(self):
        table = self.planet_table
        table.setSortingEnabled(False)                   # no sorting during the update
        for p in self.planets + self.minor_planets:
            items = self._planet_items[p["name"]]
            self._planet_alt[p["name"]] = float(p["alt"])
            for col, value in (("col_ra", p["ra"]), ("col_dec", p["dec"]), ("col_alt", p["alt"]),
                               ("col_az", p["az"]), ("col_dist", p["dist"]), ("col_elong", p["elong"]),
                               ("col_mag", p["mag"])):
                items[col].setData(_SORT_ROLE, float(value))
            items["col_mag"].setText(_num(p["mag"], 1))
            side = t("coords.east") if p["east"] else t("coords.west")
            items["col_ra"].setText(_ra(p["ra"]))
            items["col_dec"].setText(_dec(p["dec"]))
            items["col_alt"].setText(_dec(p["alt"]))
            items["col_az"].setText(_az(p["az"]))
            items["col_dist"].setText(_num(p["dist"], 4))                 # AU in the header
            items["col_elong"].setText(f"{_deg(p['elong'], 1)} {side}")
            events = self.planet_events.get(p["name"], {})
            for key in ("rise", "transit", "set"):
                items[f"col_{key}"].setText(self._format_event(events.get(key)))
                when = events.get(key)
                items[f"col_{key}"].setData(_SORT_ROLE, when.timestamp() if when is not None
                                            and when.tzinfo else (when - datetime(1970, 1, 1)).total_seconds()
                                            if when is not None else None)
            up = p["alt"] > 0
            name = items["col_planet"]
            name.setForeground(QBrush(QColor(Config.ENCRE if up else Config.ENCRE_ATTENUEE)))
            state = t("common.visible" if up else "common.below_horizon")
            name.setToolTip(f"{_planet_name(p['name'], numbered=True)} · {state}" if p.get("minor") else state)
        table.setSortingEnabled(True)
        table.horizontalHeader().setSortIndicatorShown(False)     # setSortingEnabled turns it back on
        self._show_planet_group()

    def _update_status(self):
        if self._lat is None:
            return
        coords = f"{_fmt_lat(self._lat)}, {_fmt_lon(self._lon)}"
        self._lbl_pos.setText(f"{self.location_name} · {coords}"
                              if self.location_name else coords)
        n, n_pl = len(self.visible_stars), len(self.visible_planets_map)
        self._lbl_stars.setText(
            f"{SYMBOL['star']} {tf(_plural_key('status.stars', n), n=n)}   ·   "
            f"{tf(_plural_key('status.planets', n_pl), n=n_pl)}")
        local = self._local(self._dte)
        self._lbl_time.setText(
            f"{tf('status.ut', time=self._dte.strftime('%d/%m/%Y %H:%M:%S'))}   ·   "
            f"{tf('status.local', time=self._fmt_clock(local), offset=self._zone_text())}")

    # ──────────────────────────────────────────────────────────────────────────
    # CHARTS
    # ──────────────────────────────────────────────────────────────────────────

    def _on_tab_changed(self, _index):
        timer = getattr(self, "_orrery_timer", None)
        if timer is not None and timer.isActive() and self._chart_tabs.get(self.tabs.currentWidget()) != "orrery":
            self._toggle_orrery()                         # a hidden animation does not run
        self._draw_visible_chart()
        self._refresh_coordinates()
        if self.tabs.currentWidget() is getattr(self, "_planner_page", None):
            self._compute_plan()                          # only when the night or the place changed

    def _draw_visible_chart(self):
        """Draws the chart of the shown tab when it is out of date: in real time,
        hidden charts are not redrawn."""
        name = self._chart_tabs.get(self.tabs.currentWidget())
        if name not in self._dirty or self._dte is None:
            return
        self._dirty.discard(name)
        {"traj": self._draw_trajectory, "sky": self._draw_sky_map,
         "orrery": self._draw_orrery}[name]()

    def _draw_trajectory(self):
        if not self.hours:
            return
        dte, start = self._dte, self._day_start
        offset = self._midnight_offset()
        labels = {
            "title": tf("chart.trajectory_title", date=self._local(start).strftime("%d/%m/%Y")),
            "xlabel": tf("chart.hour_local", offset=_fmt_offset(offset)),
            "ylabel": t("chart.altitude"),
            "top_axis": t("chart.hour_ut"),
            "sun": t("chart.sun"),
            "moon": t("chart.moon"),
        }
        labels.update({p: t(f"chart.phase_{p}") for p in charts.DAY_PHASES})
        now_h = (dte - start).total_seconds() / 3600       # since local midnight
        self._traj_ax, tip = charts.draw_trajectory(
            self.fig_traj, self.hours, self.sun_altitudes, self.moon_altitudes,
            now_h, self.sun_data["alt"], self.moon_data["alt"], labels, offset)
        self._traj_tip.attach(tip)
        self.canvas_traj.draw_idle()

    def _draw_sky_map(self):
        dte = self._dte
        labels = {
            "title": tf("skymap.title", datetime=dte.strftime("%d/%m/%Y %H:%M")),
            "sun": t("chart.sun"),
            "moon": t("chart.moon"),
            "horizon": t("skymap.horizon"),
            "cardinals": [t(f"skymap.cardinal_{c}")
                          for c in ("n", "ne", "e", "se", "s", "sw", "w", "nw")],
            "planets": {n: _planet_name(n) for n in _PLANETS + MINOR_PLANETS + COMETS},
        }
        found = self._resolve_target(self._sky_found)
        highlight = None
        if found is not None and found["alt"] > 0:
            highlight = {"x": found["x"], "y": found["y"], "label": self._target_label(self._sky_found),
                         "wide": found["kind"] == "figure"}
        self._sky_ax, tip = charts.draw_sky_map(self.fig_sky, self._sky_scene, labels, highlight)
        self._show_find_result()
        self._sky_tip.attach(tip)
        self._sky_hover = None
        self.canvas_sky.draw_idle()

    # ── Search by name on the sky map ─────────────────────────────────────────
    #    A reference names an object from one calculation to the next: ("sun",),
    #    ("moon",), ("planet", name), ("star", designation), ("messier", number),
    #    ("figure", constellation).

    @staticmethod
    def _find_key(text):
        """Search key of a name: no accents or case, Greek letters spelled out
        ("α¹ Cen": "alpha1 cen"), "M 31" and "Messier 31" as "m31"."""
        key = places.normalize("".join(_GREEK.get(ch, ch) for ch in text))
        return re.sub(r"\b(?:messier|m) (?=\d)", "m", key)

    @staticmethod
    def _star_label(star):
        return star["name"] if star["name"] == star["designation"] else f"{star['name']} ({star['designation']})"

    def _target_label(self, ref):
        kind = ref[0]
        if kind in ("sun", "moon"):
            return t(f"chart.{kind}")
        if kind == "planet":
            return _planet_name(ref[1])
        if kind == "figure":
            return t(f"constellations.{ref[1]}")
        if kind == "messier":
            return _messier_label(next(o for o in messier_catalog() if o["m"] == ref[1]))
        if kind == "deep":
            return _messier_label(self._deep_object(ref[1]))
        return self._star_label(next(s for s in self._sky_scene["catalog"] if s["designation"] == ref[1]))

    def _deep_object(self, label):
        """A deep-sky object of the planner's catalogues or of the user's targets, by its label."""
        custom = [planner.custom_target(**c) for c in prefs.get("planner_custom") or []]
        for obj in list(planner.deep_sky_catalog()) + custom:
            if planner.label(obj) == label or obj["id"] == label:
                return obj
        return None

    def _sky_targets(self):
        """Everything the search knows, [(label, search key, reference)]: the Sun, the
        Moon, the planets, minor planets and comets, the Messier objects, the
        constellations and the stars of the catalogue (their keys computed once)."""
        targets = [(self._target_label(ref), None, ref) for ref in [("sun",), ("moon",)]
                   + [("planet", p["name"]) for p in self.planets + self.minor_planets]]
        targets += [(_messier_label(o), None, ("messier", o["m"])) for o in self._deep_sky_all]
        targets += [(t(f"constellations.{key}"), None, ("figure", key)) for key in self._sky_scene["figures"]]
        targets = [(label, self._find_key(label), ref) for label, _key, ref in targets]
        if AstroApp._STAR_TARGETS is None:
            stars = [(self._star_label(s), ("star", s["designation"])) for s in self._sky_scene["catalog"]]
            AstroApp._STAR_TARGETS = [(label, self._find_key(label), ref) for label, ref in stars]
        return targets + AstroApp._STAR_TARGETS

    _STAR_TARGETS = None            # the stars do not change: their labels and keys are built once

    def _find_targets(self, text, limit=10):
        """The targets whose name matches *text*: the exact name (or its first
        word, "m3") first, then names starting with it, then a word starting
        with it, then any place in the name."""
        query = self._find_key(text)
        if not query or self._sky_scene is None:
            return []
        ranked = []
        for index, (label, key, ref) in enumerate(self._sky_targets()):
            words = key.split()
            if key == query or words[0] == query:
                rank = 0
            elif key.startswith(query):
                rank = 1
            elif any(word.startswith(query) for word in words) or f" {query}" in f" {key}":
                rank = 2
            elif query in key:
                rank = 3
            else:
                continue
            ranked.append((rank, index, label, ref))
        return [(label, ref) for _rank, _index, label, ref in sorted(ranked)[:limit]]

    def _resolve_target(self, ref):
        """The object behind a reference as the sky map describes it (altitude,
        azimuth, map position); None without a reference, or for a comet that
        has left its table."""
        if ref is None or self._sky_scene is None:
            return None
        scene, kind = self._sky_scene, ref[0]
        if kind in ("sun", "moon"):
            return scene[kind]
        if kind == "star":
            return next((s for s in scene["catalog"] if s["designation"] == ref[1]), None)
        if kind == "planet":
            obj = self._body_object(ref[1])
        elif kind == "messier":
            obj = next(({**o, "kind": "deep_sky"} for o in self._deep_sky_all if o["m"] == ref[1]), None)
        elif kind == "deep":
            found = self._deep_object(ref[1])
            if found is None:
                return None
            tc = AstroEngine.julian_century_j2000(self._dte)
            alt, az = AstroEngine.stars_horizontal(tc, self._lat, self._lon, [found["ra"] / 15.0], [found["dec"]],
                                                   self._elevation())
            obj = {**found, "kind": "deep_sky", "alt": float(alt[0]), "az": float(az[0])}
        else:
            alt, az = scene["figures"][ref[1]]
            obj = {"kind": "figure", "name": ref[1], "alt": alt, "az": az}
        if obj is None:
            return None
        x, y = charts.sky_xy(obj["alt"], obj["az"])
        return {**obj, "x": x, "y": y}

    def _refresh_sky_objects(self):
        """What the pointer finds on the map: the objects drawn and, when it is
        too faint to be drawn, the object found by name."""
        self._sky_objects = charts.visible_objects(self._sky_scene)
        found = self._resolve_target(self._sky_found)
        if found is None or found["kind"] == "figure" or found["alt"] <= 0:
            return
        same = (lambda o: o.get("id") == found.get("id")) if found["kind"] == "deep_sky" else \
            (lambda o: o.get("name") == found.get("name"))
        if not any(o["kind"] == found["kind"] and same(o) for o in self._sky_objects):
            self._sky_objects.append(found)

    def _on_find_typed(self, text):
        """Suggestions at each letter."""
        self._find_matches = dict(self._find_targets(text))
        self._find_model.setStringList(list(self._find_matches))
        if self._find_matches:
            self._find_completer.complete()

    def _on_find_chosen(self, label):
        ref = self._find_matches.get(label)
        if ref is not None:
            self._find_on_sky(ref)

    def _on_find_return(self):
        """Return without choosing: the first suggestion."""
        text = self._find_entry.text().strip()
        if not text:
            return
        ref = self._find_matches.get(text)
        if ref is None:
            found = self._find_targets(text, limit=1)
            ref = found[0][1] if found else None
        if ref is None:
            message = tf("skymap.not_found", name=text)
            self._chart_hints["sky"].setText(message)
            self.statusBar().showMessage(message, 6000)
            return
        self._find_on_sky(ref)

    def _find_on_sky(self, ref):
        """Circles the object on the map and says where it is."""
        self._find_completer.popup().hide()
        self._sky_found = ref
        self._find_entry.blockSignals(True)
        self._find_entry.setText(self._target_label(ref))
        self._find_entry.blockSignals(False)
        self._refresh_sky_objects()
        self._dirty.add("sky")
        self._draw_visible_chart()
        self._show_find_result()                          # also when another tab is shown
        self.statusBar().showMessage(self._chart_hints["sky"].text(), 6000)

    def _clear_found(self):
        if self._sky_found is None:
            self._chart_hints["sky"].setText(t("skymap.hint"))
            return
        self._sky_found = None
        self._refresh_sky_objects()
        self._dirty.add("sky")
        self._draw_visible_chart()
        self._show_find_result()

    def _show_find_result(self):
        """Under the map: where the object found is, or that it is below the horizon."""
        hint = self._chart_hints["sky"]
        found = self._resolve_target(self._sky_found)
        if found is None:
            hint.setText(t("skymap.hint"))
            return
        name = self._target_label(self._sky_found)
        if found["alt"] > 0:
            hint.setText(tf("skymap.found", name=name, alt=_deg(found["alt"], 1),
                            dir=self._wind(found["az"]), az=_deg(found["az"], 1)))
            return
        rise = None
        if found["kind"] in ("sun", "moon", "planet"):
            body = found["kind"] if found["kind"] != "planet" else found["name"]
            rise = AstroEngine.next_rise(self._dte, self._lat, self._lon, body, self._elevation())
        if rise is not None:
            hint.setText(tf("skymap.found_below_rise", name=name, alt=_deg(found["alt"], 1, signed=True),
                            time=self._format_event(rise)))
        else:
            hint.setText(tf("skymap.found_below", name=name, alt=_deg(found["alt"], 1, signed=True)))

    def _draw_orrery(self):
        labels = {
            "inner": t("planets.orrery_inner"),
            "outer": t("planets.orrery_outer"),
            "au": t("planets.orrery_au"),
            "sun": t("chart.sun"),
            "earth": t("planets.orrery_earth"),
            "vernal": t("planets.orrery_vernal"),
            "planets": {n: _planet_name(n) for n in _PLANETS},
        }
        charts.draw_orrery(self.fig_orrery, charts.orrery_scene(self._orrery_tc()), labels)
        self.canvas_orrery.draw_idle()
        self._show_orrery_date()

    # ── Animated orrery ──────────────────────────────────────────────────────

    def _orrery_tc(self):
        """Julian centuries of the orrery: the chosen date, plus the animation's offset,
        bounded by the years of the ephemeris."""
        first, last = (AstroEngine.julian_day(datetime(y, m, d)) for y, m, d in
                       ((EPHEMERIS_YEARS[0], 1, 2), (EPHEMERIS_YEARS[1], 12, 30)))
        jd = AstroEngine.julian_day(self._dte) + self._orrery_offset
        if not first <= jd <= last:
            jd = min(max(jd, first), last)
            self._orrery_offset = jd - AstroEngine.julian_day(self._dte)
            self._orrery_timer.stop()
            self._orrery_play.setIcon(_icon("play", Config.ENCRE, 16))
        return (jd - 2451545.0) / 36525.0

    def _show_orrery_date(self):
        when = self._dte + timedelta(seconds=round(self._orrery_offset * 86400.0))
        self._orrery_date.setText(when.strftime("%d/%m/%Y"))
        self._orrery_date.setProperty("tone", "or" if abs(self._orrery_offset) >= 0.5 else None)
        self._orrery_date.style().polish(self._orrery_date)

    def _orrery_step(self, sign):
        """A frame: the orrery moves forward (or back) by the chosen step."""
        if self._dte is None:
            return
        self._orrery_offset += sign * self._orrery_speed.currentData()
        scene = charts.orrery_scene(self._orrery_tc())
        if charts.move_orrery(self.fig_orrery, scene):
            self.canvas_orrery.draw_idle()
            self._show_orrery_date()
        else:
            self._draw_orrery()

    def _toggle_orrery(self):
        running = not self._orrery_timer.isActive()
        if running:
            self._orrery_timer.start()
        else:
            self._orrery_timer.stop()
        self._orrery_play.setIcon(_icon("pause" if running else "play", Config.ENCRE, 16))
        self._orrery_play.setToolTip(t("planets.orrery_pause" if running else "planets.orrery_play"))

    def _reset_orrery(self):
        """Back to the date chosen in the side panel."""
        if self._orrery_timer.isActive():
            self._toggle_orrery()
        self._orrery_offset = 0.0
        if self._dte is not None:
            self._draw_orrery()

    # ── Hover and click ──────────────────────────────────────────────────────

    def _on_traj_hover(self, event):
        tip = self._traj_tip.artist
        if tip is None:
            return
        if event.inaxes is not self._traj_ax or event.xdata is None or not self.hours:
            self._traj_tip.hide()
            return
        step = self.hours[1] - self.hours[0]
        i = max(0, min(len(self.hours) - 1, int(round(event.xdata / step))))
        hour = self.hours[i]                                  # since local midnight
        base, offset = datetime(2000, 1, 1), self._midnight_offset()
        ut = self._fmt_clock(base + timedelta(hours=hour - offset))
        first = f"{ut} {t('chart.ut')}"
        if offset:
            local = self._fmt_clock(base + timedelta(hours=hour))
            first = f"{local} {t('chart.local')}  ·  {first}"
        tip.set_text(f"{first}\n"
                     f"{charts.SYMBOL['Sun']} {t('chart.sun')}  {_deg(self.sun_altitudes[i], 1, True)}\n"
                     f"{charts.SYMBOL['Moon']} {t('chart.moon')}  {_deg(self.moon_altitudes[i], 1, True)}")
        tip.xy = (hour, event.ydata)
        right = hour > 16
        tip.set_position((-14 if right else 14, 12))
        tip.set_horizontalalignment("right" if right else "left")
        tip.set_visible(True)
        self._traj_tip.refresh()

    def _sky_object_at(self, event):
        if event.inaxes is not self._sky_ax or event.xdata is None:
            return None
        return charts.hit_test(self._sky_objects, event.xdata, event.ydata)

    def _on_sky_leave(self, _event):
        self.canvas_sky.unsetCursor()
        self._sky_hover = None
        self._sky_tip.hide()

    def _on_sky_hover(self, event):
        tip = self._sky_tip.artist
        if tip is None:
            return
        obj = self._sky_object_at(event)
        if obj is None:
            self._on_sky_leave(event)
            return
        self.canvas_sky.setCursor(Qt.CursorShape.PointingHandCursor)
        if obj is self._sky_hover:
            return
        self._sky_hover = obj
        title, _rows = self._object_details(obj, symbols=False)
        line = (f"{t('detail.alt')} {_deg(obj['alt'], 1)}  ·  "
                f"{t('detail.az')} {_deg(obj['az'], 1)}")
        if obj["kind"] in ("star", "deep_sky"):
            line += f"  ·  {t('detail.mag')} {_num(obj['mag'], 2 if obj['kind'] == 'star' else 1)}"
        tip.set_text(f"{title}\n{line}")
        tip.xy = (obj["x"], obj["y"])
        right = obj["x"] > 0.35
        tip.set_position((-14 if right else 14, 12))
        tip.set_horizontalalignment("right" if right else "left")
        tip.set_visible(True)
        self._sky_tip.refresh()

    def _on_sky_click(self, event):
        if getattr(event, "button", None) != 1:
            return
        obj = self._sky_object_at(event)
        if obj is not None:
            self._sky_tip.hide()
            self._show_object_detail(obj)

    def _object_details(self, obj, symbols=True, full=False):
        """
        Title and lines (label, value) of the card of a body. *symbols*:
        symbols followed by U+FE0E (Qt); without, for matplotlib. *full*: the
        data window of the Sun, the Moon or a planet, with apparent diameter,
        phase, distances, light time, rise and set.
        """
        sym = SYMBOL if symbols else charts.SYMBOL
        kind = obj["kind"]
        rows = []
        if kind == "star":
            title = obj["name"]
            rows.append((t("detail.type"), t("detail.type_star")))
            designation = obj.get("designation", "")
            if designation and designation != obj["name"]:
                rows.append((t("detail.designation"), designation))
            abbreviation = designation.split()[-1] if designation and not designation.startswith("HR") else ""
            if abbreviation in constellation_names():
                rows.append((t("detail.constellation"), f"{t('constellations.' + abbreviation)} ({abbreviation})"))
            rows.append((t("detail.mag"), _num(obj["mag"], 2)))
        elif kind == "planet":
            title = f"{sym[obj['name']]} {_planet_name(obj['name'], numbered=full)}"
            side = t("coords.east") if obj.get("east") else t("coords.west")
            rows.append((t("detail.type"), t("detail.type_comet" if obj.get("comet") else
                                             "detail.type_minor_planet" if obj.get("minor")
                                             else "detail.type_planet")))
            if obj.get("mag") is not None:
                rows.append((t("detail.mag"), _num(obj["mag"], 1)))
            rows.append((t("detail.distance"), tf("units.au", value=_num(obj["dist"], 4))))
            rows.append((t("detail.elongation"), f"{_deg(obj['elong'], 1)} {side}"))
        elif kind == "deep_sky":
            title = _messier_label(obj)
            rows.append((t("detail.type"), t(f"messier.type_{obj['type']}")))
            rows.append((t("detail.designation"), obj["id"]))
            if obj["const"] in constellation_names():
                rows.append((t("detail.constellation"), f"{t('constellations.' + obj['const'])} ({obj['const']})"))
            rows.append((t("detail.mag"), _num(obj["mag"], 1)))
            if obj.get("major"):
                size = f"{_num(obj['major'], 0)}′"
                if obj.get("minor"):
                    size += f" × {_num(obj['minor'], 0)}′"
                rows.append((t("detail.size"), size))
        elif kind == "sun":
            title = f"{sym['Sun']} {t('chart.sun')}"
            rows.append((t("detail.type"), t("detail.type_sun")))
            rows.append((t("detail.distance"), tf("units.au", value=_num(obj["dist"], 4))))
        else:
            title = f"{sym['Moon']} {t('chart.moon')}"
            key = Formatters.PHASES[Formatters.phase_index(obj["phase"])][0]
            rows.append((t("detail.type"), t("detail.type_moon")))
            rows.append((t("detail.phase"), t(f"phases.{key}")))
            rows.append((t("detail.illumination"), f"{_num(obj['illum'], 1)} %"))
            rows.append((t("detail.distance"), tf("units.km", value=_num(obj["dist"]))))
        rows += [
            (t("detail.ra"), _ra(obj["ra"])),
            (t("detail.dec"), _dec(obj["dec"])),
            (t("detail.alt"), _dec(obj["alt"])),
            (t("detail.az"), _az(obj["az"])),
        ]
        return title, rows

    @staticmethod
    def _light_time(seconds):
        """"8 min 15 s", "1 h 15 min"."""
        seconds = int(round(seconds))
        if seconds < 60:
            return f"{seconds} s"
        if seconds < 3600:
            return f"{seconds // 60} min {seconds % 60:02d} s"
        return f"{seconds // 3600} h {seconds % 3600 // 60:02d} min"

    @staticmethod
    def _diameter(arcsec):
        """"31′ 34″", "58,4″"."""
        if arcsec >= 60.0:
            minutes, seconds = divmod(int(round(arcsec)), 60)
            return f"{minutes}′ {seconds:02d}″"
        return f"{_num(arcsec, 1 if arcsec >= 1 else 2)}″"

    def _data_rows(self, obj):
        """Lines of the data window of a Solar System body."""
        body = {"sun": "sun", "moon": "moon"}.get(obj["kind"], obj.get("name"))
        d = AstroEngine.body_details(AstroEngine.julian_century_j2000(self._dte), body)
        rows = [] if obj.get("mag") is not None else [(t("detail.mag"), _num(d["mag"], 2))]
        if d.get("constellation"):
            rows.append((t("detail.constellation"), f"{t('constellations.' + d['constellation'])} ({d['constellation']})"))
        if d["diameter_arcsec"]:
            rows.append((t("detail.diameter"), self._diameter(d["diameter_arcsec"])))
        if d["illuminated"] is not None and obj["kind"] != "moon":
            rows.append((t("detail.illumination"), f"{_num(d['illuminated'], 1)} %"))
        if d["phase_angle"] is not None:
            rows.append((t("detail.phase_angle"), _deg(d["phase_angle"], 1)))
        rows.append((t("detail.light_time"), self._light_time(d["light_time_s"])))
        if d["helio_au"] is not None:
            rows.append((t("detail.helio"), tf("units.au", value=_num(d["helio_au"], 4))))
        events = {"sun": self.sun_events, "moon": self.moon_events}.get(
            obj["kind"], self.planet_events.get(obj.get("name"), {})) or {}
        for key in ("rise", "transit", "set"):
            if key in events:
                rows.append((t(f"detail.{key}"), self._format_event(events.get(key))))
        return rows

    def _body_object(self, name):
        """The body *name* as the sky map describes it: Sun, Moon or planet."""
        if name == "sun":
            return {**self.sun_data, "kind": "sun"}
        if name == "moon":
            return {**self.moon_data, "kind": "moon"}
        planet = next((p for p in self.planets + self.minor_planets if p["name"] == name), None)
        return {**planet, "kind": "planet"} if planet else None

    def _show_body_detail(self, name):
        """Data window of a body chosen in a table (non-modal)."""
        obj = self._body_object(name)
        if obj is None:
            return
        dlg = self._build_detail_dialog(obj)
        self._detail_dialog = dlg
        dlg.open()

    def _build_detail_dialog(self, obj):
        title, rows = self._object_details(obj, full=True)
        if obj["kind"] in ("sun", "moon", "planet") and self._dte is not None:
            rows += self._data_rows(obj)
        dlg = QDialog(self)
        dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dlg.setWindowTitle(tf("detail.title", name=title))
        dlg.setMinimumWidth(380)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(24, 24, 24, 16)
        lay.setSpacing(16)
        lay.addWidget(_label(title, "sous-titre"))
        card = _card()
        grid = QGridLayout(card)
        grid.setContentsMargins(16, 12, 16, 12)
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(6)
        for r, (key, value) in enumerate(rows):
            grid.addWidget(_label(key, "legende"), r, 0)
            val = _label(value, "donnee")
            val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            grid.addWidget(val, r, 1)
        lay.addWidget(card)
        extra = self._companions_card(obj)
        if extra is not None:
            lay.addWidget(extra)
        buttons = QDialogButtonBox()
        close = _button(t("detail.close"))
        buttons.addButton(close, QDialogButtonBox.ButtonRole.RejectRole)
        buttons.rejected.connect(dlg.reject)
        lay.addWidget(buttons)
        return dlg

    def _companions_card(self, obj):
        """Second card of the data window: Jupiter's moons, Saturn's rings, the moons of Mars,
        Saturn, Uranus, Neptune and Pluto; None for the others."""
        if not obj or obj.get("name") not in MOON_PLANETS or self._dte is None:
            return None
        if obj["name"] != "Jupiter":
            return self._moons_card(obj["name"])
        tc = AstroEngine.julian_century_j2000(self._dte)
        southern = self._lat is not None and self._lat < 0
        card = _card()
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(8)
        grid = QGridLayout()
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(6)
        if obj["name"] == "Jupiter":
            moons = AstroEngine.galilean_moons(tc)
            radius = AstroEngine.body_details(tc, "Jupiter")["diameter_arcsec"] / 2.0
            lay.addWidget(_label(t("jupiter.title"), "label"))
            self._moons_drawing = JupiterMoons(moons, southern)
            lay.addWidget(self._moons_drawing)
            rows = [(f"{numeral}  {t('jupiter.' + moon['name'])}", self._moon_text(moon, radius))
                    for numeral, moon in zip(("I", "II", "III", "IV"), moons)]
            note = t("jupiter.note_south" if southern else "jupiter.note_north")
        else:
            rings = AstroEngine.saturn_rings(tc)
            lay.addWidget(_label(t("saturn.title"), "label"))
            self._rings_drawing = SaturnRings(rings["tilt"], southern)
            lay.addWidget(self._rings_drawing)
            face = t("saturn.north_face" if rings["tilt"] >= 0 else "saturn.south_face")
            if not rings["lit"]:
                face = f"{face}, {t('saturn.unlit')}"
            rows = [(t("saturn.tilt"), f"{_deg(abs(rings['tilt']), 1)} · {face}"),
                    (t("saturn.size"), f"{self._diameter(rings['major_arcsec'])} × "
                                       f"{self._diameter(rings['minor_arcsec'])}")]
            note = t("saturn.note_south" if southern else "saturn.note_north")
        for r, (key, value) in enumerate(rows):
            grid.addWidget(_label(key, "legende"), r, 0)
            val = _label(value, "donnee")
            val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            grid.addWidget(val, r, 1)
        lay.addLayout(grid)
        lay.addWidget(_label(note, "legende", wrap=True))
        return card

    def _moons_card(self, planet):
        """The moons of Mars, Saturn (with its rings), Uranus, Neptune or Pluto: a drawing as in a
        telescope and, for each moon, its magnitude and its place from the planet."""
        tc = AstroEngine.julian_century_j2000(self._dte)
        southern = self._lat is not None and self._lat < 0
        moons = AstroEngine.planet_moons(tc, planet)
        card = _card()
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(8)
        def table(rows):
            grid = QGridLayout()
            grid.setHorizontalSpacing(24)
            grid.setVerticalSpacing(6)
            for r, (key, value) in enumerate(rows):
                grid.addWidget(_label(key, "legende"), r, 0)
                val = _label(value, "donnee")
                val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                grid.addWidget(val, r, 1)
            lay.addLayout(grid)

        rows = []
        if planet == "Saturn":
            rings = AstroEngine.saturn_rings(tc)
            lay.addWidget(_label(t("saturn.title"), "label"))
            self._rings_drawing = SaturnRings(rings["tilt"], southern)
            lay.addWidget(self._rings_drawing)
            face = t("saturn.north_face" if rings["tilt"] >= 0 else "saturn.south_face")
            if not rings["lit"]:
                face = f"{face}, {t('saturn.unlit')}"
            table([(t("saturn.tilt"), f"{_deg(abs(rings['tilt']), 1)} · {face}"),
                   (t("saturn.size"), f"{self._diameter(rings['major_arcsec'])} × "
                                      f"{self._diameter(rings['minor_arcsec'])}")])
        lay.addWidget(_label(t("moons.title"), "label"))
        if not moons:
            first, last = AstroEngine.moon_years()
            lay.addWidget(_label(tf("moons.out_of_range", first=first, last=last), "legende", wrap=True))
        else:
            radius = (AstroEngine.body_details(tc, planet).get("diameter_arcsec") or 1.0) / 2.0
            self._moons_drawing = PlanetMoons(moons, radius, southern)
            lay.addWidget(self._moons_drawing)
            for moon in sorted(moons, key=lambda m: m["separation"]):
                if moon["state"] == "free":
                    side = t("skymap.cardinal_e") if moon["east"] > 0 else t("skymap.cardinal_w")
                    where = f"{self._diameter(moon['separation'])} {side}"
                else:
                    where = tf(f"moons.{moon['state']}", planet=_planet_name(planet))
                rows.append((t(f"moons.{moon['name']}"), f"mag {_num(moon['mag'], 1)} · {where}"))
        table(rows)
        lay.addWidget(_label(t("moons.note_south" if southern else "moons.note_north"), "legende", wrap=True))
        return card

    def _moon_text(self, moon, radius_arcsec):
        """"4,9 R à l'ouest · 1′ 32″", "devant Jupiter", "dans l'ombre de Jupiter"…"""
        if moon["state"] == "free":
            side = "jupiter.west" if moon["x"] > 0 else "jupiter.east"
            text = tf(side, r=_num(abs(moon["x"]), 1),
                      sep=self._diameter(math.hypot(moon["x"], moon["y"]) * radius_arcsec))
        else:
            text = t(f"jupiter.{moon['state']}")
        return f"{text} · {t('jupiter.shadow')}" if moon["shadow"] else text

    def _show_object_detail(self, obj):
        """Detailed card of a body of the sky map."""
        self._build_detail_dialog(obj).exec()

    # ──────────────────────────────────────────────────────────────────────────
    # EVENTS
    # ──────────────────────────────────────────────────────────────────────────

    def _clear_evt_layout(self):
        while self._evt_layout.count():
            item = self._evt_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()           # deleteLater only acts back in the event loop
                widget.deleteLater()

    def _show_events_placeholder(self):
        self._clear_evt_layout()
        self._evt_layout.addWidget(_label(t("events.click_to_search"), "corps",
                                          tone="attenuee", wrap=True))
        self._evt_layout.addStretch()

    def _events_header(self, title, count_text, note=None):
        self._evt_layout.addWidget(_label(title, "sous-titre"))
        self._evt_layout.addWidget(_label(count_text, "legende"))
        if note:
            self._evt_layout.addWidget(_label(note, "legende", wrap=True))
        self._evt_layout.addSpacing(8)

    def _event_card(self, symbol, accent, title, when, pills=(), details=(), action=None, lines=()):
        """Event card: symbol, title, badges, date; details below; *action*:
        (text, function) of a button on the right."""
        card = _card()
        card.setObjectName("card")
        card.setProperty("eventCard", True)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(6)
        top = QHBoxLayout()
        top.setSpacing(8)
        top.addWidget(_label(symbol, "symbol", tone=accent))
        top.addWidget(_label(title, "corps", strong=True))
        for text, tone in pills:
            top.addWidget(_badge(text, tone))
        top.addStretch()
        top.addWidget(_label(when, "donnee"))
        if action:
            btn = _button(action[0], "place", "secondaire", compact=True)
            btn.setToolTip(action[2] if len(action) > 2 else t("eclipse_map.button_tip"))
            btn.clicked.connect(action[1])
            top.addWidget(btn)
        lay.addLayout(top)
        if details:
            lay.addWidget(_label("   ·   ".join(details), "legende", wrap=True))
        for line in lines:
            lay.addWidget(_label(line, "legende", wrap=True))
        self._evt_layout.addWidget(card)

    def _search_start(self, kind):
        self._last_search = kind
        self._ics_items = []
        self._btn_ics.setEnabled(False)
        self._evt_filter_bar.setVisible(kind == "conjunctions")
        dte = self._edit_datetime()
        self._clear_evt_layout()
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        return dte

    def _search_failed(self, exc):
        self._evt_layout.addWidget(_label(tf("events.search_error", detail=exc),
                                          "corps", tone="alerte", wrap=True))
        self._evt_layout.addStretch()

    def _eclipse_details(self, ec):
        details = []
        if ec["type"] == "solar":
            details.append(tf("events.magnitude", value=_num(ec["magnitude"], 3)))
            if ec.get("duration_min") is not None:
                details.append(tf("events.duration_central",
                                  value=_num(ec["duration_min"], 1)))
            details.append(tf("events.diameter_ratio", value=_num(ec["diameter_ratio"], 4)))
        else:
            if ec["sub_type"] != "penumbral":
                details.append(tf("events.umbral_magnitude",
                                  value=_num(ec["umbral_magnitude"], 3)))
            details.append(tf("events.penumbral_magnitude",
                              value=_num(ec["penumbral_magnitude"], 3)))
            durations = ec.get("durations") or {}
            for phase in ("total", "partial", "penumbral"):
                if durations.get(phase):
                    details.append(tf(f"events.duration_{phase}",
                                      value=_duration(durations[phase])))
        return details

    @staticmethod
    def _seconds(value):
        """"2 min 15 s"."""
        value = int(round(value))
        return f"{value // 60} min {value % 60:02d} s"

    def _eclipse_local_lines(self, ec, loc):
        """Local circumstances of an eclipse, in the place's time."""
        if ec["type"] == "solar":
            if loc is None:
                return [t("events.local_none")]
            if not loc["visible"]:
                return [t("events.local_sun_down")]
            down, body_down = -0.83, t("events.sun_down")
        else:
            if not loc["visible"]:
                return [t("events.local_moon_down")]
            down, body_down = -0.5, t("events.moon_set")
        c, alt = loc["contacts"], loc["altitudes"]

        def at(key):
            text = self._clock(c[key])
            return text if alt[key] > down else f"{text} ({body_down})"
        if ec["type"] == "solar":
            first, last = "c1", "c4"
        else:
            first, last = ("u1", "u4") if c.get("u1") else ("p1", "p4")
        parts = [tf("events.local_start", time=at(first)) if c.get(first) else None,
                 tf("events.local_max", time=at("max")),
                 tf("events.local_end", time=at(last)) if c.get(last) else None]
        lines = [tf("events.local_here", detail=" · ".join(p for p in parts if p))]
        if ec["type"] == "solar":
            info = [tf("events.local_magnitude", value=_num(loc["magnitude"], 3)),
                    tf("events.local_obscuration", value=_num(100.0 * loc["obscuration"])),
                    tf("events.local_sun_alt", value=_num(alt["max"]))]
            if loc["central"]:
                info.insert(0, tf(f"events.local_{loc['central']}", start=self._clock(c["c2"]),
                                  end=self._clock(c["c3"]), duration=self._seconds(loc["duration_s"])))
        else:
            info = [tf("events.local_moon_alt", value=_num(alt["max"]))]
            if c.get("u2"):
                info.insert(0, tf("events.local_totality", start=self._clock(c["u2"]),
                                  end=self._clock(c["u3"])))
            if not loc["all_visible"]:
                info.append(t("events.local_moon_partly"))
        text = "   ·   ".join(info)
        lines.append(text[:1].upper() + text[1:])
        return lines

    def _search_eclipses_gui(self):
        """Searches and shows the eclipses of the next 12 months."""
        dte = self._search_start("eclipses")
        try:
            eclipses = AstroEngine.find_eclipses(dte, num_months=12)
        except Exception as exc:
            QApplication.restoreOverrideCursor()
            self._search_failed(exc)
            return
        QApplication.restoreOverrideCursor()

        n = len(eclipses)
        self._events_header(tf("events.eclipses_title", date=dte.strftime("%d/%m/%Y")),
                            tf(_plural_key("events.eclipse_count", n), n=n),
                            t("events.eclipse_note"))
        if not eclipses:
            self._evt_layout.addWidget(_label(t("events.no_eclipse"), "corps", tone="attenuee"))
        for ec in eclipses:
            solar = ec["type"] == "solar"
            pills = [(t(f"events.subtype_{ec['sub_type']}"), "info")]
            if ec.get("certainty") == "possible":
                pills.append((t("events.certainty_possible"), "neutre"))
            greatest = ec.get("greatest", ec["date"]) + timedelta(seconds=30)  # nearest minute
            when = greatest.strftime("%d/%m/%Y %H:%M") + f" {t('chart.ut')}"
            title = t("events.solar_eclipse" if solar else "events.lunar_eclipse")
            local = None
            if self._lat is not None:
                local = AstroEngine.eclipse_local(ec, self._lat, self._lon, self._elevation())
            lines = self._eclipse_local_lines(ec, local) if self._lat is not None else []
            details = self._eclipse_details(ec)
            self._event_card(SYMBOL["Sun"] if solar else SYMBOL["Moon"],
                             "or" if solar else "lune", title, when, pills, details,
                             (t("eclipse_map.button"), lambda _=False, e=ec: self._show_eclipse_map(e)),
                             lines)
            start, end = ec.get("greatest", ec["date"]), None
            if local and local["visible"]:
                c = local["contacts"]
                first, last = (("c1", "c4") if solar else (("u1", "u4") if c.get("u1") else ("p1", "p4")))
                start, end = c[first] or start, c[last]
            sub_type = t(f"events.subtype_{ec['sub_type']}").lower()
            self._ics_add(start, end, f"{title} {sub_type}", details + lines)
        self._evt_layout.addStretch()
        self._btn_ics.setEnabled(bool(self._ics_items))

    def _show_eclipse_map(self, ec):
        """Window: the eclipse projected on the ground (path, central line, partiality)."""
        solar = ec["type"] == "solar"
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            if solar:
                scene = AstroEngine.eclipse_map(ec["greatest"], "solar")
            else:
                durations = ec.get("durations") or {}
                minutes = durations.get("partial") or durations.get("penumbral") or 120.0
                scene = AstroEngine.eclipse_map(ec["greatest"], "lunar", half_span_hours=minutes / 120.0)
        finally:
            QApplication.restoreOverrideCursor()
        sub_type = t(f"events.subtype_{ec['sub_type']}")
        when = (ec["greatest"] + timedelta(seconds=30)).strftime("%d/%m/%Y %H:%M")
        labels = {
            "title": tf("eclipse_map.title", eclipse=t("events.solar_eclipse" if solar
                                                       else "events.lunar_eclipse"),
                        type=sub_type.lower(), date=f"{when} {t('chart.ut')}"),
            "greatest": t("eclipse_map.greatest"), "observer": t("eclipse_map.observer"),
            "central": t("eclipse_map.central"), "partial": t("eclipse_map.partial"),
            "path": t("eclipse_map.path_annular" if ec["sub_type"] == "annular"
                      else "eclipse_map.path_total"),
            "moon_up": t("eclipse_map.moon_up"), "limits": t("eclipse_map.limits"),
            "decimal": _locale().decimalPoint(),
        }
        dlg = QDialog(self)
        dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)           # and its figure with it
        dlg.setWindowTitle(t("eclipse_map.window_title"))
        dlg.resize(1000, 640)
        lay = QVBoxLayout(dlg)
        fig = Figure(facecolor=Config.CIEL_100)
        canvas = FigureCanvasQTAgg(fig)
        lay.addWidget(canvas, stretch=1)
        observer = (self._lat, self._lon) if self._lat is not None else None
        charts.draw_eclipse_map(fig, scene, labels, observer)
        lay.addWidget(_label(t("eclipse_map.note_solar" if solar else "eclipse_map.note_lunar"),
                             "legende", wrap=True))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dlg.reject)
        lay.addWidget(buttons)
        canvas.draw_idle()
        self._eclipse_dialog = dlg
        dlg.show()

    # ── Events of the year: planets, minor planets, Moon, seasons ─────────────

    _EVENT_GROUPS = ("planets", "minor", "comets", "moon", "seasons", "meteors")
    _WINDS = ("n", "ne", "e", "se", "s", "sw", "w", "nw")

    def _body_name(self, name, symbol=False):
        """Name of a body of the events: planet, Sun, Moon or star."""
        if name in ("Sun", "Moon"):
            text = t(f"chart.{name.lower()}")
            return f"{SYMBOL[name]} {text}" if symbol else text
        if name in AstroEngine.MOON_STARS:
            return t(f"events.star_{name.lower()}")
        return _planet_name(name, symbol=symbol)

    def _event_title(self, ev, symbol=True):
        """Title of an event of the year."""
        kind = ev["type"]
        if kind == "season":
            return t(f"events.{ev['kind']}")
        if kind == "meteor_shower":
            return tf("meteors.title", name=t(f"meteors.name_{ev['kind']}"))
        if kind.startswith("comet_"):
            return tf(f"events.{kind}", comet=_planet_name(ev["bodies"][0], symbol=symbol, numbered=True))
        if kind in ("perihelion", "aphelion", "perigee", "apogee"):
            return t(f"events.{kind}")
        a = ev["bodies"][0]
        planet = self._body_name(a, symbol=symbol)
        if kind == "opposition":
            return tf("events.opposition", planet=planet)
        if kind == "greatest_elongation":
            return tf(f"events.greatest_elongation_{ev['side']}", planet=planet)
        b = ev["bodies"][1]
        if b == "Sun":
            key = f"events.conjunction_{ev['kind']}" if ev.get("kind") else "events.solar_conjunction"
            return tf(key, planet=planet)
        return tf("events.conjunction_pair", a=planet, b=self._body_name(b, symbol=symbol))

    def _event_when(self, dt):
        """"06/01/2026 16:36 UT": the instant to the nearest minute."""
        return (dt + timedelta(seconds=30)).strftime("%d/%m/%Y %H:%M") + f" {t('chart.ut')}"

    def _clock(self, dt):
        """Local time of the place, to the nearest minute."""
        return self._fmt_clock(self._local(dt + timedelta(seconds=30)))

    @staticmethod
    def _elide(text):
        """"de Uranus" → "d'Uranus" in French."""
        if get_lang() != "fr":
            return text
        return re.sub(r"\bde (?=[AEIOUYÉÈÊaeiouyéèê])", "d'", text)

    def _visibility_text(self, vis):
        if vis["period"] is None:
            return t(f"events.invisible_{vis['reason']}")
        wind = self._WINDS[int(round(vis["az"] / 45.0)) % 8]
        return tf(f"events.visible_{vis['period']}", alt=_num(vis["alt"]),
                  dir=t(f"skymap.cardinal_{wind}"), time=self._clock(vis["best"]))

    def _meteor_lines(self, vis):
        """The night of the peak from here: best moment (radiant, expected rate), then the Moon."""
        if vis["period"] is None:
            first = t(f"events.invisible_{vis['reason']}")
        else:
            wind = self._WINDS[int(round(vis["az"] / 45.0)) % 8]
            first = tf("meteors.best", time=self._clock(vis["best"]), alt=_num(vis["alt"]),
                       dir=t(f"skymap.cardinal_{wind}"), rate=vis["rate"])
        moon = vis["moon"]
        if moon == "none":
            moon_text = t("meteors.moon_new" if vis["moon_fraction"] < 0.1 else "meteors.moon_set")
        else:
            moon_text = tf(f"meteors.moon_{moon}", pct=_num(100.0 * vis["moon_fraction"]))
        return [first, moon_text]

    def _wind(self, az):
        """Compass point of an azimuth, in the active language ("SO")."""
        return t(f"skymap.cardinal_{self._WINDS[int(round(az / 45.0)) % 8]}")

    # ── Satellite passes ─────────────────────────────────────────────────────

    def _search_satellites_gui(self):
        """Visible passes of the ISS, Tiangong and Hubble over the next 10 days; the
        orbits are downloaded in the background when older than two days."""
        dte = self._search_start("satellites")
        self._evt_layout.addWidget(_label(t("satellites.loading"), "legende", tone="attenuee"))

        lat, lon, elevation = self._lat, self._lon, self._elevation()
        visual_wanted = bool(prefs.get("satellites_visual"))

        def work():
            """In the background: the orbits, then the passes (150 satellites take a few seconds)."""
            elements, error = satellites.refresh()
            followed = dict(elements)
            if visual_wanted:
                visual, visual_error = satellites.refresh_visual()
                elements = satellites.with_visual(elements, visual)
                error = error or visual_error
            if not elements:
                return elements, error, []
            passes = AstroEngine.satellite_passes(elements, dte, lat, lon, elevation)
            if visual_wanted:                             # the others: only their high passes
                passes = [p for p in passes if p["name"] in followed or p["max_alt"] >= 40.0]
            return elements, error, passes

        def done(result):
            elements, error, passes = result
            QApplication.restoreOverrideCursor()
            if self._last_search != "satellites":
                return
            self._clear_evt_layout()
            if not elements:
                self._search_failed(error or t("satellites.no_elements"))
                return
            self._render_satellites(dte, passes, {k: v for k, v in elements.items()
                                                  if k in satellites.SATELLITES}, error)
            _TONIGHT_CACHE.clear()                        # "Tonight" can now show the passes
            self._tonight_key = None
            self._update_tonight(self._dte, self._lat, self._lon, self._elevation())

        def failed(exc):
            QApplication.restoreOverrideCursor()
            if self._last_search == "satellites":
                self._clear_evt_layout()
                self._search_failed(exc)
        _run_in_background(work, done, failed)

    def _render_satellites(self, dte, passes, elements, error=None):
        n = len(passes)
        age = satellites.epoch_age_days(elements)
        note = tf("satellites.note", days=_num(age, 1))
        if error is not None:
            note += " " + tf("satellites.not_refreshed", detail=error)
        if age > satellites.STALE_DAYS:
            note += " " + t("satellites.too_old")
        self._events_header(tf("satellites.title", date=dte.strftime("%d/%m/%Y")),
                            tf(_plural_key("satellites.count", n), n=n), note)
        if not passes:
            self._evt_layout.addWidget(_label(t("satellites.none"), "corps", tone="attenuee", wrap=True))
        for p in passes:
            clock = self._clock
            first = tf("satellites.from_shadow" if p["from_shadow"] else "satellites.appears",
                       time=clock(p["start"]), alt=_num(p["start_alt"]), dir=self._wind(p["start_az"]))
            top = tf("satellites.highest", time=clock(p["max"]), alt=_num(p["max_alt"]),
                     dir=self._wind(p["max_az"]))
            last = tf("satellites.into_shadow" if p["into_shadow"] else "satellites.vanishes",
                      time=clock(p["end"]), alt=_num(p["end_alt"]), dir=self._wind(p["end_az"]))
            seconds = int(round((p["end"] - p["start"]).total_seconds()))
            details = [tf("satellites.duration", min=seconds // 60, s=f"{seconds % 60:02d}")]
            local = self._local(p["start"])
            if local != p["start"].replace(tzinfo=None):
                details.append(tf("events.local_time", time=f"{local:%d/%m} {self._fmt_clock(local)}",
                                  zone=getattr(self._zone, "key", "UTC")))
            pills = [(t("satellites.overhead"), "info")] if p["max_alt"] >= 60.0 else []
            title = _satellite_name(p["name"])
            self._event_card(SYMBOL["dot"], "attenuee", title, self._event_when(p["start"]), pills, details,
                             None, [f"{first} · {top} · {last}"])
            self._ics_add(p["start"], p["end"], title, details + [f"{first} · {top} · {last}"])
        self._evt_layout.addStretch()
        self._btn_ics.setEnabled(bool(self._ics_items))

    def _event_shown(self, ev):
        if not self._evt_filters[ev.get("group", "planets")].isChecked():
            return False
        vis = ev.get("visibility")
        return not (self._evt_filters["visible"].isChecked() and vis is not None and vis["period"] is None)

    # ── Astronomical calendar ─────────────────────────────────────────────

    _CAL_SYMBOLS = {"phases": "Moon", "eclipses": "Sun", "planets": "conjunction", "minor": "conjunction",
                    "comets": "meteors", "moon": "Moon", "seasons": "Sun", "meteors": "meteors",
                    "satellites": "star"}

    def _calendar_title(self, item):
        """Title of an event of the calendar, in the interface language."""
        cat, ev = item["category"], item["event"]
        if cat == "phases":
            return t(f"phases.{item['kind']}")
        if cat == "eclipses":
            title = t("events.solar_eclipse" if ev["type"] == "solar" else "events.lunar_eclipse")
            return f"{title} ({t('events.subtype_' + ev['sub_type'])})"
        if cat == "satellites":
            return tf("astro_calendar.pass", name=_satellite_name(ev["name"], short=True))
        return self._event_title(ev, symbol=False)

    def _calendar_symbol(self, item):
        ev = item["event"]
        if item["category"] == "eclipses":
            return SYMBOL["Sun" if ev["type"] == "solar" else "Moon"]
        if item["category"] in ("planets", "minor") and ev.get("type") == "opposition":
            return SYMBOL["opposition"]
        return SYMBOL[self._CAL_SYMBOLS[item["category"]]]

    def _calendar_details(self, item):
        """The lines under an event of the day: time, visibility, the engine's figures."""
        ev, lines = item["event"], []
        when = self._local(item["date"] + timedelta(seconds=30))
        lines.append(tf("astro_calendar.at", time=self._fmt_clock(when),
                        zone=getattr(self._zone, "key", "UTC") if self._zone else "UTC"))
        if item["category"] == "eclipses":
            lines += self._eclipse_details(ev)
        elif item["category"] == "satellites":
            lines.append(tf("satellites.highest", time=self._clock(ev["max"]), alt=_num(ev["max_alt"]),
                            dir=self._wind(ev["max_az"])))
        else:
            vis = ev.get("visibility")
            if vis is not None and item["category"] not in ("phases", "seasons"):
                lines.append(self._visibility_text(vis) if item["kind"] != "meteor_shower"
                             else " · ".join(self._meteor_lines(vis)))
        return lines

    def show_calendar(self):
        """The calendar view of the Events tab: every event of a period (a year by default),
        by category, in a month grid; the day's events below; the .ics export of what the
        filters let through."""
        self._last_search = "calendar"
        self._ics_items = []
        self._btn_ics.setEnabled(False)
        self._evt_filter_bar.setVisible(False)
        self._clear_evt_layout()
        cal = getattr(self, "_cal_state", None)
        local_now = self._local(self._edit_datetime())
        if cal is None:
            start = local_now.date()
            cal = {"start": start, "end": start.replace(year=start.year + 1) if not (start.month == 2 and start.day == 29)
                   else start + timedelta(days=365), "items": None, "key": None,
                   "month": (start.year, start.month), "day": start,
                   "shown": {c: c != "satellites" or bool(satellites.load()) for c in astro_calendar.CATEGORIES}}
            self._cal_state = cal

        controls = QHBoxLayout()
        controls.setSpacing(12)
        start_edit, end_edit = QDateEdit(), QDateEdit()
        for edit, value in ((start_edit, cal["start"]), (end_edit, cal["end"])):
            edit.setCalendarPopup(True)
            edit.setDisplayFormat("dd/MM/yyyy")
            edit.setMinimumDate(QDate(EPHEMERIS_YEARS[0], 1, 1))
            edit.setMaximumDate(QDate(EPHEMERIS_YEARS[1], 12, 31))
            edit.setDate(QDate(value.year, value.month, value.day))
        controls.addWidget(InputField(t("astro_calendar.from"), start_edit))
        controls.addWidget(InputField(t("astro_calendar.to"), end_edit))
        compute = _button(t("astro_calendar.compute"), "calculate", "principal", compact=True)
        compute.setToolTip(t("astro_calendar.compute_tip"))
        controls.addWidget(compute, alignment=Qt.AlignmentFlag.AlignBottom)
        controls.addStretch()
        holder = QWidget()
        holder.setLayout(controls)
        self._evt_layout.addWidget(holder)

        filters = QWidget()
        frow = QGridLayout(filters)
        frow.setContentsMargins(0, 0, 0, 0)
        frow.setHorizontalSpacing(16)
        frow.setVerticalSpacing(4)
        boxes = {}
        for n, key in enumerate(astro_calendar.CATEGORIES):
            box = QCheckBox(t(f"astro_calendar.cat_{key}"))
            box.setChecked(cal["shown"][key])
            boxes[key] = box
            frow.addWidget(box, n // 5, n % 5)
        frow.setColumnStretch(5, 1)
        self._evt_layout.addWidget(filters)

        nav = QHBoxLayout()
        prev_btn = _icon_button("previous", t("astro_calendar.previous"), compact=True)
        next_btn = _icon_button("next", t("astro_calendar.next"), compact=True)
        month_label = _label("", "sous-titre")
        nav.addWidget(prev_btn)
        nav.addWidget(month_label)
        nav.addWidget(next_btn)
        nav.addStretch()
        status = _label("", "legende", wrap=True)
        nav.addWidget(status, stretch=1)
        nav_holder = QWidget()
        nav_holder.setLayout(nav)
        self._evt_layout.addWidget(nav_holder)

        grid_card = _card()
        grid = QGridLayout(grid_card)
        grid.setContentsMargins(8, 8, 8, 8)
        grid.setSpacing(4)
        for d in range(7):
            head = _label(t(f"astro_calendar.weekday_{d}"), "legende")
            head.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(head, 0, d)
        cells = []
        for w in range(6):
            for d in range(7):
                cell = _DayCell(lambda day: choose_day(day))
                grid.addWidget(cell, w + 1, d)
                cells.append(cell)
        for d in range(7):
            grid.setColumnStretch(d, 1)
        self._evt_layout.addWidget(grid_card)
        day_title = _label("", "label", strong=True)
        self._evt_layout.addWidget(day_title)
        day_box = QVBoxLayout()
        day_box.setSpacing(6)
        day_holder = QWidget()
        day_holder.setLayout(day_box)
        self._evt_layout.addWidget(day_holder)
        self._evt_layout.addStretch()
        self._cal_widgets = {"cells": cells, "month": month_label, "status": status, "boxes": boxes,
                             "start": start_edit, "end": end_edit, "day_title": day_title, "day_box": day_box}

        def shown_items():
            return [i for i in (cal["items"] or []) if boxes[i["category"]].isChecked()]

        def fill_day():
            while day_box.count():
                w = day_box.takeAt(0).widget()
                if w is not None:
                    w.deleteLater()
            day = cal["day"]
            items = [i for i in shown_items() if self._local(i["date"]).date() == day]
            day_title.setText(tf("astro_calendar.day_title", date=day.strftime("%d/%m/%Y"), n=len(items)))
            for item in items:
                row = _card()
                lay = QVBoxLayout(row)
                lay.setContentsMargins(12, 8, 12, 8)
                lay.setSpacing(2)
                lay.addWidget(_label(f"{self._calendar_symbol(item)}  {self._calendar_title(item)}", "corps",
                                     strong=True))
                for line in self._calendar_details(item):
                    if line:
                        lay.addWidget(_label(line, "legende", wrap=True))
                day_box.addWidget(row)

        def fill_month():
            year, month = cal["month"]
            month_label.setText(f"{t(f'workshop.month_{month}')} {year}")
            days = astro_calendar.by_day(shown_items(), self._local)
            for cell, day in zip(cells, [d for week in astro_calendar.month_grid(year, month) for d in week]):
                items = days.get(day, [])
                lines = []
                for item in items[:3]:
                    title = self._calendar_title(item)
                    lines.append(f"{self._calendar_symbol(item)} {title if len(title) <= 22 else title[:21] + '…'}")
                if len(items) > 3:
                    lines.append(tf("astro_calendar.more", n=len(items) - 3))
                tip = "\n".join(f"{self._clock(i['date'])}  {self._calendar_title(i)}" for i in items)
                cell.show_day(day, str(day.day), lines, tip, day.month == month, day == cal["day"])
            self._ics_items = []
            for item in shown_items():
                end = item["end"] or item["date"] + timedelta(minutes=1)
                self._ics_add(item["date"], end, self._calendar_title(item), self._calendar_details(item))
            self._btn_ics.setEnabled(bool(self._ics_items))
            fill_day()

        def choose_day(day):
            cal["day"] = day
            fill_month()

        def turn(step):
            year, month = cal["month"]
            month += step
            year, month = year + (month - 1) // 12, (month - 1) % 12 + 1
            cal["month"] = (year, month)
            fill_month()

        def toggled():
            for key, box in boxes.items():
                cal["shown"][key] = box.isChecked()
            fill_month()

        def run():
            a, b = start_edit.date(), end_edit.date()
            first = datetime(a.year(), a.month(), a.day())
            last = datetime(b.year(), b.month(), b.day()) + timedelta(days=1)
            if last <= first:
                status.setText(t("astro_calendar.bad_period"))
                return
            cal["start"], cal["end"] = first.date(), (last - timedelta(days=1)).date()
            zone = self._zone
            start_ut = first.replace(tzinfo=zone).astimezone(timezone.utc).replace(tzinfo=None) if zone else first
            end_ut = last.replace(tzinfo=zone).astimezone(timezone.utc).replace(tzinfo=None) if zone else last
            key = (start_ut, end_ut, self._lat, self._lon)
            if cal["key"] == key and cal["items"] is not None:
                fill_month()
                return
            elements = satellites.load()
            if elements and satellites.epoch_age_days(elements) > satellites.STALE_DAYS:
                elements = None
            lat, lon, elev = self._lat, self._lon, self._elevation()
            status.setText(t("astro_calendar.computing"))
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

            def done(items):
                QApplication.restoreOverrideCursor()
                cal["items"], cal["key"] = items, key
                if self._last_search == "calendar":
                    status.setText(tf("astro_calendar.found", n=len(items), start=cal["start"].strftime("%d/%m/%Y"),
                                      end=cal["end"].strftime("%d/%m/%Y")))
                    fill_month()

            def failed(exc):
                QApplication.restoreOverrideCursor()
                status.setText(tf("events.search_error", detail=exc))
            _run_in_background(lambda: astro_calendar.collect(start_ut, end_ut, lat, lon, elev, zone, elements),
                               done, failed)

        prev_btn.clicked.connect(lambda _c=False: turn(-1))
        next_btn.clicked.connect(lambda _c=False: turn(1))
        compute.clicked.connect(lambda _c=False: run())
        for box in boxes.values():
            box.toggled.connect(lambda _v: toggled())
        self._cal_run, self._cal_turn, self._cal_choose = run, turn, choose_day
        if cal["items"] is None:
            run()
        else:
            status.setText(tf("astro_calendar.found", n=len(cal["items"]), start=cal["start"].strftime("%d/%m/%Y"),
                              end=cal["end"].strftime("%d/%m/%Y")))
            fill_month()

    def _search_conjunctions_gui(self):
        """Searches the events of 12 months: conjunctions, oppositions and
        elongations, minor planets, Moon, seasons, meteor showers; their
        visibility from here."""
        dte = self._search_start("conjunctions")
        try:
            events = (AstroEngine.find_conjunctions(dte, num_days=365)
                      + AstroEngine.find_moon_events(dte, num_days=365)
                      + AstroEngine.find_seasons(dte, num_days=365)
                      + AstroEngine.find_meteor_showers(dte, num_days=365)
                      + AstroEngine.find_comet_events(dte, num_days=365))
            events.sort(key=lambda e: e["date"])
            if self._lat is not None:
                AstroEngine.event_visibility(events, self._lat, self._lon, self._elevation(), self._zone)
        except Exception as exc:
            QApplication.restoreOverrideCursor()
            self._search_failed(exc)
            return
        QApplication.restoreOverrideCursor()
        self._events_found = (dte, events)
        self._render_events()

    def _render_events(self, *_args):
        """Shows the events found that the filters let through."""
        found = getattr(self, "_events_found", None)
        if not found or self._last_search != "conjunctions":
            return
        dte, events = found
        self._clear_evt_layout()
        self._ics_items = []
        shown = [e for e in events if self._event_shown(e)]
        n = len(shown)
        self._events_header(
            tf("events.conjunctions_title", date=dte.strftime("%d/%m/%Y")),
            tf(_plural_key("events.event_count", n), n=n), t("events.precise_note"))
        if not shown:
            self._evt_layout.addWidget(_label(t("events.no_conjunction"), "corps",
                                              tone="attenuee", wrap=True))
        for ev in shown:
            self._add_event_card(ev)
        self._evt_layout.addStretch()
        self._btn_ics.setEnabled(bool(self._ics_items))

    def _add_event_card(self, ev):
        kind = ev["type"]
        a = ev["bodies"][0]
        pills, details, lines, action = [], [], [], None
        if kind == "season":
            symbol = SYMBOL["Sun"]
        elif kind == "meteor_shower":
            symbol = SYMBOL["meteors"]
            (m1, d1), (m2, d2) = ev["activity"]
            details += [tf("meteors.zhr", value=ev["zhr"]), tf("meteors.speed", value=ev["velocity"]),
                        tf("meteors.activity", start=f"{d1:02d}/{m1:02d}", end=f"{d2:02d}/{m2:02d}")]
        elif kind.startswith("comet_"):
            symbol = SYMBOL[a]
            if kind != "comet_brightest":
                key = "events.distance_au" if kind == "comet_perihelion" else "events.distance_earth"
                details.append(tf(key, value=_num(ev["distance_au"], 3)))
            details.append(tf("events.magnitude", value=_num(ev["mag"], 1)))
        elif kind in ("perihelion", "aphelion"):
            symbol = SYMBOL["Earth"]
            details.append(tf("events.distance_au", value=_num(ev["distance_au"], 5)))
        elif kind in ("perigee", "apogee"):
            symbol = SYMBOL["Moon"]
            details.append(tf("events.distance_km", value=_num(ev["distance_km"])))
            if kind == "perigee" and ev.get("syzygy") == "full":
                pills.append((t("events.supermoon"), "info"))
            elif ev.get("syzygy"):
                details.append(t(f"events.near_{ev['syzygy']}_moon"))
        else:
            sep = ev["separation"]
            if kind == "opposition":
                symbol = SYMBOL["opposition"]
                details.append(tf("events.elongation", value=_num(sep, 1)))
            elif kind == "greatest_elongation":
                symbol = SYMBOL[a]
                details.append(tf("events.elongation", value=_num(sep, 1)))
            else:
                symbol = SYMBOL["conjunction"]
                b = ev["bodies"][1]
                side = (tf(f"events.{ev['side']}_of_sun", a=_planet_name(a)) if b == "Sun"
                        else tf(f"events.{ev['side']}_of", a=self._body_name(a), b=self._body_name(b)))
                details += [tf("events.separation", value=_num(sep, 2)), self._elide(side)]
                if ev.get("transit"):
                    pills.append((t("events.transit"), "info"))
            if ev.get("mag") is not None:
                details.append(tf("events.magnitude", value=_num(ev["mag"], 1)))
            action = (t("event_map.button"), lambda _=False, e=ev: self._show_event_map(e),
                      t("event_map.button_tip"))
        local = self._local(ev["date"] + timedelta(seconds=30))
        if local != (ev["date"] + timedelta(seconds=30)).replace(tzinfo=None):
            details.append(tf("events.local_time", time=f"{local:%d/%m} {self._fmt_clock(local)}",
                              zone=getattr(self._zone, "key", "UTC")))
        vis = ev.get("visibility")
        if vis is not None and kind == "meteor_shower":
            lines += self._meteor_lines(vis)
        elif vis is not None and kind not in ("perigee", "apogee"):
            lines.append(self._visibility_text(vis))
        occ = ev.get("occultation")
        if occ and any((occ.get(k) or -90.0) > 0.0 for k in ("moon_alt_start", "moon_alt_end")):
            pills.append((t("events.occultation"), "info"))
            parts = []
            for key, label in (("start", "events.occ_start"), ("end", "events.occ_end")):
                if occ[key] is not None:
                    alt = occ[f"moon_alt_{key}"]
                    where = tf("events.moon_alt", value=_num(alt)) if alt > 0 else t("events.moon_set")
                    parts.append(tf(label, time=self._clock(occ[key]), alt=where))
            text = tf("events.occultation_here", detail=" · ".join(parts))
            if occ.get("sun_alt_start") is not None and occ["sun_alt_start"] > -0.83:
                text += " " + t("events.by_day")
            lines.append(text)
        if kind in ("conjunction", "opposition", "greatest_elongation"):
            title = self._event_title(ev, symbol=kind != "greatest_elongation")
        else:
            title = self._event_title(ev)
        self._event_card(symbol, "attenuee", title, self._event_when(ev["date"]), pills, details,
                         action, lines)
        self._ics_add(ev["date"], None, self._event_title(ev, symbol=False), details + lines)

    def _ics_add(self, start, end, summary, details):
        self._ics_items.append((start, end or start + timedelta(minutes=1), summary,
                                "\n".join(details)))

    def _export_ics(self):
        """Saves the shown events to an iCalendar calendar (.ics)."""
        if not getattr(self, "_ics_items", None):
            return
        default = os.path.join(os.path.expanduser("~"), t("events.export_filename"))
        path, _filter = QFileDialog.getSaveFileName(self, t("events.export_title"), default,
                                                    "iCalendar (*.ics)")
        if not path:
            return
        if not path.lower().endswith(".ics"):
            path += ".ics"
        try:
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(_ics_calendar(self._ics_items, _utc_now()))
        except OSError as exc:
            QMessageBox.warning(self, t("errors.error_title"), tf("events.export_error", detail=exc))
            return
        self.statusBar().showMessage(tf("events.exported", path=path), 8000)

    def _show_event_map(self, ev):
        """Window: paths of the bodies among the stars around the event."""
        from star_catalog import CATALOG

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            scene = AstroEngine.event_scene(ev, CATALOG)
        finally:
            QApplication.restoreOverrideCursor()
        names = {name: self._body_name(name) for name in ev["bodies"]}
        labels = {
            "title": tf("event_map.title", event=self._event_title(ev, symbol=False),
                        date=self._event_when(ev["date"])),
            "ecliptic": t("event_map.ecliptic"), "bodies": names,
            "date_format": t("event_map.date_format"), "hour_format": t("event_map.hour_format"),
        }
        dlg = QDialog(self)
        dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dlg.setWindowTitle(t("event_map.window_title"))
        dlg.resize(820, 720)
        lay = QVBoxLayout(dlg)
        fig = Figure(facecolor=Config.CIEL_100)
        canvas = FigureCanvasQTAgg(fig)
        lay.addWidget(canvas, stretch=1)
        charts.draw_event_map(fig, scene, labels, ev["date"])
        lay.addWidget(_label(t("event_map.note"), "legende", wrap=True))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dlg.reject)
        lay.addWidget(buttons)
        canvas.draw_idle()
        self._event_dialog = dlg
        dlg.show()
