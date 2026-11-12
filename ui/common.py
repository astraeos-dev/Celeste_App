"""
ui/common.py — What every space of the interface shares
=======================================================
The imports, constants, formatting helpers, the components of the Astræos
design system (buttons, fields, cards, badges), the style sheet, and the
widgets used by several spaces (place map, place picker, moons, rings).

The spaces (ui/tonight.py, ui/sky.py…) take everything with
``from ui.common import *``. The names that the tests replace
(``_run_in_background``, ``QMessageBox``…) are read as ``common.<name>``, so
that a replacement here reaches every space.
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

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # the application folder

# ── Constants ─────────────────────────────────────────────────────────────────


# The user's favourites, outside the repository; at the first launch, those of an
# earlier version (application folder) or the starting list
_FAVORITES_FILE = os.path.join(prefs.USER_DIR, "favorites.json")
_LEGACY_FAVORITES_FILE = os.path.join(_ROOT, "favorites.json")
_DEFAULT_FAVORITES_FILE = os.path.join(_ROOT,
                                       "favorites_default.json")
_FONTS_DIR = os.path.join(_ROOT, "fonts")

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
QTabWidget#space > QTabBar::tab {{ font-size: 13px; font-weight: 500; padding: 6px 8px; }}
QTabWidget#space > QTabBar::tab:selected {{ border-bottom-width: 1px; }}
QTabWidget#space::pane {{ border-top: none; }}

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




# Every name above, underscored ones included, for ``from ui.common import *``
__all__ = [name for name in dir() if not name.startswith("__")]
