"""
gui.py — Interface graphique de Céleste (PyQt6), design Astræos
================================================================
v3.3 — Interface au design system Astræos :
  ★ Trois thèmes : Nuit (défaut), Jour, Observation (rouge sur noir, pour
    garder la vision de nuit), choisis dans la barre latérale
  ★ IBM Plex Sans pour le texte, IBM Plex Mono pour les données, symboles
    astronomiques (☉ ☽ ♀ ♂ ♃ ♄ ☌ ☍) toujours accompagnés du nom de l'astre
  ★ Aucun emoji : icônes au trait Material Design Icons
  ★ Composants : Bouton, BoutonIcone, ChampSaisie, CarteDonnee, PastilleEtat,
    Jauge, Onglets, SelecteurTheme ; une seule zone dorée par écran (le
    bouton Calculer), filets plutôt qu'ombres
  ★ Textes traduits (fr, en, es, de) ; nombres à la mode de la langue
  ★ Raccourcis : F5 calculer, Ctrl+L temps réel

Architecture :
  - Barre latérale  : date, lieu, fuseau, favoris, actions, thème
  - Zone principale : onglets Éphémérides / Trajectoires / Carte du ciel /
                      Planètes / Événements / Paramètres
  - Barre d'état    : lieu, astres visibles, heure TU et heure locale

Les calculs viennent de engine.py, les graphiques de charts.py, les couleurs
de config.py (tokens Astræos), les icônes et le logo de icons.py.
"""

import json
import math
import os
import re
import sys
import urllib.request
import functools
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

from PyQt6.QtCore import (
    QDate, QDateTime, QEvent, QLocale, QPointF, QRectF, QRegularExpression, QSize,
    Qt, QTime, QTimer, QTimeZone, QUrl,
)
from PyQt6.QtGui import (
    QBrush, QColor, QDesktopServices, QFont, QFontDatabase, QKeySequence,
    QPainter, QPainterPath, QPalette, QPen, QRegularExpressionValidator, QShortcut,
)
from PyQt6.QtPositioning import QGeoPositionInfo, QGeoPositionInfoSource
from PyQt6.QtWidgets import (
    QAbstractItemView, QApplication, QButtonGroup, QCheckBox, QComboBox, QCompleter,
    QDateTimeEdit, QDialog, QDialogButtonBox, QFileDialog, QFrame, QGridLayout,
    QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit, QMainWindow,
    QMessageBox, QProgressBar, QPushButton, QScrollArea, QSizePolicy, QSlider,
    QStatusBar, QTabWidget, QTableWidget, QTableWidgetItem, QToolButton,
    QVBoxLayout, QWidget,
)

import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

import charts  # noqa: E402
import icons  # noqa: E402
import settings as prefs  # noqa: E402
from config import APP_VERSION, FONT_MONO, FONT_SANS, THEME_NAMES, Config, mix  # noqa: E402
from constellations import STAR_CONSTELLATION  # noqa: E402
from engine import EPHEMERIS_YEARS, MINOR_PLANETS, PLANETS, AstroEngine, constellation_names  # noqa: E402
from i18n import (  # noqa: E402
    available_langs, get_lang, lang_name, resolve_lang, switch_lang, t, tf,
)
from utils import Formatters  # noqa: E402

# ── Constantes ────────────────────────────────────────────────────────────────


# Favoris de l'utilisateur, hors du dépôt ; au premier lancement, ceux d'une
# version précédente (dossier de l'application) ou la liste de départ
_FAVORITES_FILE = os.path.join(prefs.USER_DIR, "favorites.json")
_LEGACY_FAVORITES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "favorites.json")
_DEFAULT_FAVORITES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                       "favorites_default.json")
_FONTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")

_AUTO_ZONE = "auto"           # fuseau déduit du lieu (timezonefinder)
_GEOLOC_TIMEOUT_MS = 15000    # attente du service de localisation de l'appareil

_ALL_POSITIONING_METHODS = QGeoPositionInfoSource.PositioningMethod.AllPositioningMethods

# Liens : site, code source, soutien ; demandes sur GitHub (formulaires de .github/ISSUE_TEMPLATE)
_URL_SITE = "https://astraeos-dev.github.io/personnal-site/"
_URL_REPO = "https://github.com/astraeos-dev/Celeste_App"
_URL_COFFEE = "https://buymeacoffee.com/gregorychau"

# Réglages de la localisation du système, ouverts quand l'accès est refusé
_LOCATION_SETTINGS = {
    "win32": "ms-settings:privacy-location",
    "darwin": "x-apple.systempreferences:com.apple.preference.security?Privacy_LocationServices",
}
_PLANETS = PLANETS        # Mercure à Neptune (engine.PLANETS)
_QT_DATETIME_FORMAT = "dd/MM/yyyy HH:mm:ss"

# Degrés décimaux, avec un point ou une virgule (49.6333 ou 49,6333)
_COORD_REGEX = r"^\s*[+\-−]?\d{0,3}(?:[.,]\d{0,8})?\s*$"

# Symboles astronomiques, suivis de U+FE0E (présentation texte, jamais emoji)
_VS15 = "︎"
SYMBOL = {name: glyph + _VS15 for name, glyph in charts.SYMBOL.items()}
SYMBOL.update({"star": "★" + _VS15, "conjunction": "☌" + _VS15,
               "opposition": "☍" + _VS15, "dot": "●"})

# Polices de secours si les fichiers de fonts/ manquent. Aucune police emoji :
# placée dans une pile, elle dessinerait aussi les chiffres et les espaces.
_FALLBACK_SANS = ("Segoe UI", "Inter", "Helvetica Neue", "Noto Sans", "Ubuntu",
                  "Cantarell", "DejaVu Sans", "Arial")
_FALLBACK_MONO = ("Cascadia Mono", "Consolas", "JetBrains Mono", "Menlo",
                  "DejaVu Sans Mono", "Liberation Mono", "Courier New")
_fonts = {"sans": FONT_SANS, "mono": FONT_MONO}


# ── Petites fonctions ─────────────────────────────────────────────────────────

def _utc_now():
    """Instant présent en temps universel, sans fuseau ni microsecondes."""
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


def _utc_zone():
    return QTimeZone.utc() if hasattr(QTimeZone, "utc") else QTimeZone(b"UTC")


def _pref_float(key, fallback):
    """Préférence numérique ; *fallback* seulement si elle manque (0.0 est valide)."""
    value = prefs.get(key)
    try:
        return float(value) if value is not None else fallback
    except (TypeError, ValueError):
        return fallback


def _parse_coord(text, limit):
    """Degrés décimaux saisis (point ou virgule) ; ValueError hors de ±limit."""
    value = float(text.strip().replace(",", ".").replace("−", "-"))
    if math.isnan(value) or not -limit <= value <= limit:
        raise ValueError(text)
    return value


def _locale():
    return QLocale(get_lang())


def _num(value, decimals=0, signed=False):
    """Nombre à la mode de la langue active (« 12,4 » en français)."""
    text = _locale().toString(float(value), "f", decimals)
    text = text.replace("-", "−")
    if signed and value >= 0:
        text = "+" + text
    return text


def _deg(value, decimals=2, signed=False):
    return f"{_num(value, decimals, signed)}°"


def _angle_format():
    """Format des angles choisi : « dms », « dm » ou « dd » (Formatters.ANGLE_FORMATS)."""
    fmt = prefs.get("angle_format")
    return fmt if fmt in Formatters.ANGLE_FORMATS else "dms"


def _localized(text):
    """Séparateur décimal de la langue et vrai signe moins."""
    text = text.replace(".", _locale().decimalPoint())
    return "−" + text[1:] if text.startswith("-") else text


def _ra(hours, fmt=None):
    """Ascension droite « 14h 28m 19,0s », « 14h 28,317m » ou « 14,47194h »
    (*fmt* : format imposé, sinon celui des paramètres)."""
    return _localized(Formatters.angle(hours % 24.0, fmt or _angle_format(), hours=True))


def _dec(degrees, fmt=None):
    """Angle signé (déclinaison, latitude, hauteur) : « −14° 38′ 49″ », « +14° 38,82′ »…"""
    return _localized(Formatters.angle(degrees, fmt or _angle_format(), signed=True))


def _az(degrees, fmt=None):
    """Angle de 0 à 360° (azimut, longitude) dans le format choisi."""
    return _localized(Formatters.angle(degrees % 360.0, fmt or _angle_format()))


def _fmt_offset(offset):
    return Formatters.utc_offset(offset)


def _zone_names():
    """Fuseaux IANA proposés (base zoneinfo), UTC en tête."""
    hidden = ("posix/", "right/", "SystemV/")
    return ["UTC"] + sorted(z for z in available_timezones()
                            if z != "UTC" and not z.startswith(hidden))


@functools.lru_cache(maxsize=1)
def _tz_finder():
    from timezonefinder import TimezoneFinder
    return TimezoneFinder()


@functools.lru_cache(maxsize=256)
def _zone_at(lat, lon):
    """Fuseau IANA d'un lieu (timezonefinder, hors ligne) ; « UTC » s'il est inconnu."""
    try:
        return _tz_finder().timezone_at(lat=lat, lng=lon) or "UTC"
    except Exception:  # timezonefinder absent ou en échec : temps universel
        return "UTC"


def _zone(name, lat=None, lon=None):
    """tzinfo d'un fuseau ; « auto » est celui du lieu (lat, lon)."""
    name = name or _AUTO_ZONE
    if name == _AUTO_ZONE:
        name = _zone_at(round(lat, 3), round(lon, 3)) if lat is not None else "UTC"
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def _elev_text(metres):
    return str(int(round(metres)))


def _place_name(lat, lon):
    """Nom de la commune d'un point (OpenStreetMap Nominatim) ; « » sans réponse."""
    url = ("https://nominatim.openstreetmap.org/reverse?format=jsonv2&zoom=10"
           f"&lat={lat:.5f}&lon={lon:.5f}&accept-language={get_lang()}")
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": f"Celeste/{APP_VERSION} (+https://github.com/astraeos-dev/Celeste_App)"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:  # réseau, délai, JSON : les coordonnées suffisent
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


def _coord_text(value):
    """Coordonnée affichée dans un champ (virgule décimale en français)."""
    return _num(value, 4)


def _clean_place(name):
    """Nom de lieu sans l'épingle 📍 que contient l'ancienne valeur par défaut."""
    return (name or "").replace("\U0001f4cd", "").strip()


def _planet_name(name, symbol=False):
    text = t(f"planets.{name.lower()}")
    return f"{SYMBOL[name]} {text}" if symbol else text


def _plural_key(base, n):
    """Clé « _one » ou « _many » ; en français, 0 est singulier."""
    one = n == 1 or (n == 0 and get_lang() == "fr")
    return f"{base}_{'one' if one else 'many'}"


def _ics_text(text):
    """Texte d'une propriété iCalendar : \\ ; , et retours à la ligne protégés."""
    return (text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
            .replace("\n", "\\n"))


def _ics_fold(line):
    """Ligne iCalendar repliée à 75 octets (RFC 5545, 3.1)."""
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
    Agenda iCalendar des évènements *items* : (début, fin, titre, description),
    instants en TU (naïfs ou avec fuseau) ; *stamp* : instant de l'export.
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


# Groupes d'astres de l'onglet Planètes, dans leur ordre : un nouveau groupe
# (comètes, ciel profond…) s'ajoute ici avec ses noms, et une clé
# planets.group_<clé> dans les traductions
_BODY_GROUPS = (("planets", PLANETS), ("minor", MINOR_PLANETS))
_SORT_ROLE = Qt.ItemDataRole.UserRole          # valeur numérique du tri d'une cellule
_NAME_ROLE = Qt.ItemDataRole.UserRole + 1      # nom de l'astre d'une ligne


class _SortItem(QTableWidgetItem):
    """Cellule triée selon sa valeur numérique (_SORT_ROLE), pas selon son texte."""

    def __lt__(self, other):
        mine, theirs = self.data(_SORT_ROLE), other.data(_SORT_ROLE)
        if mine is None or theirs is None:
            return (mine is None) < (theirs is None)            # « — » à la fin
        return mine < theirs


def _issue_url(template):
    """Nouvelle demande sur GitHub, formulaire *template* (bug, feature, body) prérempli
    avec la version de Céleste et le système."""
    import platform
    from urllib.parse import urlencode
    query = {"template": f"{template}.yml", "version": APP_VERSION,
             "system": f"{platform.system()} {platform.release()}".strip()}
    return f"{_URL_REPO}/issues/new?{urlencode(query)}"


def _open_url(url):
    QDesktopServices.openUrl(QUrl(url))


def _duration(minutes):
    """Durée « 58 min » ou « 3 h 27 »."""
    minutes = int(round(minutes))
    if minutes < 60:
        return tf("units.minutes", value=minutes)
    return tf("units.duration", h=minutes // 60, m=f"{minutes % 60:02d}")


def _rgba(color, alpha):
    """Couleur QSS avec transparence (alpha de 0 à 1)."""
    c = QColor(color)
    return f"rgba({c.red()}, {c.green()}, {c.blue()}, {round(alpha * 255)})"


def _repolish(widget):
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def _set_prop(widget, name, value):
    """Propriété lue par la feuille de style ; repolit seulement si elle change."""
    if widget.property(name) != value:
        widget.setProperty(name, value)
        _repolish(widget)


def _set_invalid(widget, invalid):
    _set_prop(widget, "invalid", bool(invalid))


def _label(text="", style="corps", tone=None, strong=False, wrap=False, name=None):
    """QLabel dans un style de texte Astræos (corps, legende, donnee, cadran…)."""
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


def _bouton(text, icon_key=None, variante="secondaire", compact=False, checkable=False):
    """
    Bouton Astræos : « principal » (aplat or, une fois par écran),
    « secondaire » (filet), « discret » ou « danger » ; normal (40 px) ou compact.
    """
    btn = QPushButton(text)
    btn.setProperty("variante", variante)
    if compact:
        btn.setProperty("taille", "compact")
    btn.setFixedHeight(32 if compact else 40)
    btn.setCheckable(checkable)
    btn.setFocusPolicy(Qt.FocusPolicy.TabFocus)     # anneau de focus au clavier seulement
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    if icon_key:
        if variante == "principal":
            color = Config.SUR_OR
        elif variante == "danger":
            color = Config.SIGNAL_ALERTE
        else:
            color = Config.ENCRE
        size = 16 if compact else 20
        btn.setIcon(_icon(icon_key, color, size, checked=checkable))
        btn.setIconSize(QSize(size, size))
    return btn


def _bouton_icone(icon_key, libelle, variante="discret", compact=False, checkable=False):
    """BoutonIcone Astræos : rond, icône seule, nommé par *libelle* (infobulle)."""
    btn = QToolButton()
    btn.setObjectName("boutonIcone")
    btn.setProperty("variante", variante)
    if compact:
        btn.setProperty("taille", "compact")
    size = 32 if compact else 40
    icon_size = 16 if compact else 20
    btn.setFixedSize(size, size)
    btn.setIcon(_icon(icon_key, Config.ENCRE, icon_size, checked=checkable))
    btn.setIconSize(QSize(icon_size, icon_size))
    btn.setToolTip(libelle)
    btn.setAccessibleName(libelle)
    btn.setCheckable(checkable)
    btn.setFocusPolicy(Qt.FocusPolicy.TabFocus)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    return btn


def _set_pastille(label, text, ton):
    """PastilleEtat : un point et un ou deux mots ; ton neutre, info, ok ou alerte."""
    label.setText(f"{SYMBOL['dot']}  {text}")
    label.setFixedHeight(24)
    _set_prop(label, "pastille", ton)


def _pastille(text="", ton="neutre"):
    lbl = QLabel()
    _set_pastille(lbl, text, ton)
    return lbl


def _scroll_page():
    """(QScrollArea, page intérieure, layout vertical de la page)."""
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


# ── Composants Astræos ────────────────────────────────────────────────────────

class ChampSaisie(QWidget):
    """
    Champ de saisie Astræos : libellé toujours visible au-dessus, boîte de
    40 px (filet encre-attenuee, encre au survol, anneau or au focus), unité
    à droite, aide ou erreur dessous. *widget* : QLineEdit (par défaut),
    QComboBox ou QDateTimeEdit.
    """

    def __init__(self, libelle, widget=None, unite=None, numerique=False, aide=None):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        self.libelle = _label(libelle, "libelle")
        lay.addWidget(self.libelle)

        self.boite = QFrame()
        self.boite.setObjectName("champBoite")
        self.boite.setFixedHeight(40)
        row = QHBoxLayout(self.boite)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        self.saisie = widget if widget is not None else QLineEdit()
        if numerique:
            self.saisie.setProperty("numerique", True)
        row.addWidget(self.saisie, stretch=1)
        if unite:
            unit = _label(unite, "corps", tone="attenuee", name="champUnite")
            row.addWidget(unit)
            self.saisie.setAccessibleName(f"{libelle} ({unite})")
        else:
            self.saisie.setAccessibleName(libelle)
        lay.addWidget(self.boite)

        self.erreur = _label("", "legende", tone="alerte", strong=True, wrap=True)
        self.erreur.hide()
        lay.addWidget(self.erreur)
        self.aide = None
        if aide:
            self.aide = _label(aide, "legende", wrap=True)
            lay.addWidget(self.aide)

        self.saisie.installEventFilter(self)
        self.boite.installEventFilter(self)

    def eventFilter(self, obj, event):
        kind = event.type()
        if kind in (QEvent.Type.FocusIn, QEvent.Type.FocusOut):
            _set_prop(self.boite, "focus", kind == QEvent.Type.FocusIn)
        elif obj is self.boite and kind in (QEvent.Type.Enter, QEvent.Type.Leave):
            _set_prop(self.boite, "hover", kind == QEvent.Type.Enter)
        return False

    def set_erreur(self, message):
        """Affiche *message* (ce qui ne va pas et comment corriger), ou rien si None."""
        _set_prop(self.boite, "erreur", bool(message))
        self.erreur.setText(message or "")
        self.erreur.setVisible(bool(message))
        if self.aide is not None:
            self.aide.setVisible(not message)

    def set_desactive(self, off):
        _set_prop(self.boite, "desactive", bool(off))


class CarteDonnee(QFrame):
    """
    CarteDonnee Astræos, densité normale : symbole et libellé, la valeur en
    style cadran (Plex Mono 32 px) avec son unité, une ligne de contexte.
    """

    def __init__(self, libelle, symbole=None, accent=None):
        super().__init__()
        self.setObjectName("card")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(8)
        head = QHBoxLayout()
        head.setSpacing(8)
        if symbole:
            head.addWidget(_label(symbole, "symbole", tone=accent or "attenuee"))
        head.addWidget(_label(libelle, "legende"), stretch=1)
        lay.addLayout(head)
        mesure = QHBoxLayout()
        mesure.setSpacing(4)
        self.valeur = _label("—", "cadran")
        self.unite = _label("", "corps", tone="attenuee")
        mesure.addWidget(self.valeur, alignment=Qt.AlignmentFlag.AlignBaseline)
        mesure.addWidget(self.unite, alignment=Qt.AlignmentFlag.AlignBaseline)
        mesure.addStretch()
        lay.addLayout(mesure)
        self.detail = _label("", "legende", wrap=True)
        lay.addWidget(self.detail)
        lay.addStretch()

    def set_valeur(self, valeur, unite="", detail=""):
        self.valeur.setText(valeur)
        self.unite.setText(unite)
        self.unite.setVisible(bool(unite))
        self.detail.setText(detail)


class PhaseLune(QWidget):
    """Disque de la Lune éclairé selon l'angle de phase, au trait de la couleur lune."""

    def __init__(self, diametre=56):
        super().__init__()
        self.setFixedSize(diametre, diametre)
        self._phase = 0.0
        self._mirror = False

    def set_phase(self, phase_angle, southern=False):
        """*phase_angle* : longitude Lune − Soleil (0 nouvelle lune, 180 pleine lune)."""
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
        e = r * math.cos(math.radians(phi))                       # demi-axe du terminateur
        lit = QPainterPath()
        lit.moveTo(c.x(), c.y() - r)
        lit.arcTo(disc, 90, -180)                                 # bord droit, éclairé
        ell = QRectF(c.x() - abs(e), c.y() - r, 2 * abs(e), 2 * r)
        lit.arcTo(ell, -90, 180 if e > 0 else -180)               # terminateur
        lit.closeSubpath()
        if waxing == self._mirror:                                # décroissante : à gauche
            p.translate(2 * c.x(), 0)
            p.scale(-1, 1)
        p.setBrush(QColor(Config.LUNE))
        p.drawPath(lit)
        p.resetTransform()
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(Config.LUNE), 1.2))
        p.drawEllipse(disc)
        p.end()


class SelecteurTheme(QFrame):
    """SelecteurTheme Astræos : Nuit, Jour, Observation, l'option active en aplat encre ;
    *options* (clé, libellé, infobulle) pour un autre choix exclusif."""

    def __init__(self, current, on_change, options=None, legend=None):
        super().__init__()
        self.setObjectName("selecteurTheme")
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
            btn.setObjectName("optionTheme")
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


# ── Style de l'application ────────────────────────────────────────────────────

def _register_fonts():
    """Déclare les polices de fonts/ ; False si IBM Plex n'a pas pu être chargée."""
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
    Polices Astræos, style Fusion, palette et feuille de style de l'application.
    À appeler une fois, après la création de QApplication.
    """
    _register_fonts()
    font = QFont()
    font.setFamilies(list(_fonts["sans"]))
    font.setPixelSize(15)                       # style « corps »
    app.setFont(font)
    app.setStyle("Fusion")
    app.setWindowIcon(icons.app_icon())
    charts.configure_fonts()
    apply_theme(app)


def apply_theme(app):
    """Palette et feuille de style du thème actif (``Config``)."""
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
    """Feuille de style Qt du thème actif, d'après les composants Astræos."""
    C = Config
    sans, mono = _qss_family(_fonts["sans"]), _qss_family(_fonts["mono"])
    or_hover, or_press = mix(C.OR, C.ENCRE, 0.85), mix(C.OR, C.ENCRE, 0.72)
    off = mix(C.ENCRE, C.CIEL_100, 0.45)                       # opacité 45 %
    pressed_hover = mix(C.ENCRE, C.CIEL_000, 0.85)
    pills = "\n".join(
        f'QLabel[pastille="{ton}"] {{ color: {color}; border: 1px solid {_rgba(color, 0.45)}; }}'
        for ton, color in (("neutre", C.ENCRE_ATTENUEE), ("info", C.LUNE),
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
QLabel[textStyle="libelle"] {{ font-size: 13px; font-weight: 600; }}
QLabel[textStyle="section"] {{ font-size: 13px; font-weight: 600; color: {C.ENCRE_ATTENUEE}; }}
QLabel[textStyle="donnee"] {{ font-family: {mono}; font-size: 15px; font-weight: 500; }}
QLabel[textStyle="cadran"] {{ font-family: {mono}; font-size: 32px; font-weight: 500; }}
QLabel[textStyle="symbole"] {{ font-family: "Astraeos Symboles"; font-size: 20px; }}
QLabel[strong="true"] {{ font-weight: 600; }}
QLabel[tone="attenuee"] {{ color: {C.ENCRE_ATTENUEE}; }}
QLabel[tone="or"] {{ color: {C.OR}; }}
QLabel[tone="lune"] {{ color: {C.LUNE}; }}
QLabel[tone="alerte"] {{ color: {C.SIGNAL_ALERTE}; }}

QLabel[pastille="neutre"], QLabel[pastille="info"], QLabel[pastille="ok"], QLabel[pastille="alerte"] {{
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
QPushButton[variante="principal"] {{ background: {C.OR}; color: {C.SUR_OR}; border-color: {C.OR}; }}
QPushButton[variante="principal"]:hover {{ background: {or_hover}; border-color: {or_hover}; }}
QPushButton[variante="principal"]:pressed {{ background: {or_press}; border-color: {or_press}; }}
QPushButton[variante="principal"]:focus {{ border: 2px solid {C.ENCRE}; }}
QPushButton[variante="discret"] {{ border-color: transparent; }}
QPushButton[variante="discret"]:hover {{ background: {C.CIEL_200}; border-color: {C.CIEL_200}; }}
QPushButton[variante="danger"] {{ color: {C.SIGNAL_ALERTE}; border-color: {C.SIGNAL_ALERTE}; }}
QPushButton[variante="danger"]:hover {{ background: {C.SIGNAL_ALERTE}; color: {C.CIEL_000}; }}
QPushButton[taille="compact"] {{ border-radius: 4px; padding: 0px 12px; font-size: 13px; }}

QToolButton#boutonIcone {{ background: transparent; border: 1px solid transparent; border-radius: 20px; }}
QToolButton#boutonIcone[taille="compact"] {{ border-radius: 16px; }}
QToolButton#boutonIcone[variante="secondaire"] {{ border-color: {C.ENCRE_ATTENUEE}; }}
QToolButton#boutonIcone:hover {{ background: {C.CIEL_200}; }}
QToolButton#boutonIcone:focus {{ border: 2px solid {C.OR}; }}
QToolButton#boutonIcone:checked {{ background: {C.ENCRE}; border-color: {C.ENCRE}; }}

QPushButton#optionTheme {{
    background: transparent; border: none; border-radius: 4px; padding: 0px 10px;
    color: {C.ENCRE_ATTENUEE}; font-size: 13px; font-weight: 400;
}}
QPushButton#optionTheme:hover {{ background: {C.CIEL_200}; color: {C.ENCRE}; }}
QPushButton#optionTheme:checked {{ background: {C.ENCRE}; color: {C.CIEL_000}; font-weight: 600; }}
QPushButton#optionTheme:focus {{ border: 2px solid {C.OR}; }}
QFrame#selecteurTheme {{ background: {C.CIEL_100}; border: 1px solid {C.CIEL_200}; border-radius: 10px; }}

QLineEdit, QComboBox, QDateTimeEdit {{
    background: {C.CIEL_100}; border: 1px solid {C.ENCRE_ATTENUEE}; border-radius: 4px;
    padding: 6px 12px; font-size: 15px;
    selection-background-color: {C.CIEL_200}; selection-color: {C.ENCRE};
}}
QLineEdit:focus, QComboBox:focus, QDateTimeEdit:focus {{ border: 2px solid {C.OR}; }}
QFrame#champBoite {{ background: {C.CIEL_100}; border: 1px solid {C.ENCRE_ATTENUEE}; border-radius: 4px; }}
QFrame#champBoite[hover="true"] {{ border-color: {C.ENCRE}; }}
QFrame#champBoite[focus="true"] {{ border: 2px solid {C.OR}; }}
QFrame#champBoite[erreur="true"] {{ border-color: {C.SIGNAL_ALERTE}; }}
QFrame#champBoite[desactive="true"] {{ border-color: {off}; }}
QFrame#champBoite QLineEdit, QFrame#champBoite QComboBox, QFrame#champBoite QDateTimeEdit {{
    background: transparent; border: none; padding: 0px 12px;
}}
QLineEdit[numerique="true"], QDateTimeEdit {{ font-family: {mono}; font-weight: 500; }}
QDateTimeEdit[readOnly="true"] {{ color: {C.ENCRE_ATTENUEE}; }}
QLabel#champUnite {{ padding-right: 12px; }}
/* Listes déroulantes en mode liste : hauteur ajustée au contenu, barre de
   défilement seulement si la liste est longue (le mode « menu » de Qt
   cachait des choix derrière des flèches de défilement). */
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
    background: transparent; color: {C.ENCRE_ATTENUEE}; font-size: 15px; font-weight: 600;
    padding: 9px 12px; margin-right: 4px; border: none; border-bottom: 2px solid transparent;
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
QMenu {{ background: {C.CIEL_100}; border: 1px solid {C.CIEL_200}; }}
QMenu::item:selected {{ background: {C.CIEL_200}; }}
"""


# ── Info-bulles des graphiques ────────────────────────────────────────────────

class _TooltipLayer:
    """
    Info-bulle matplotlib redessinée par « blitting » : la survoler ne
    redessine pas toute la figure, seulement l'info-bulle.
    """

    def __init__(self, canvas):
        self.canvas = canvas
        self.artist = None
        self._background = None
        canvas.mpl_connect("draw_event", self._on_draw)

    def attach(self, artist):
        """Nouvelle info-bulle, après un redessin complet de la figure."""
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


# ── Classe principale ─────────────────────────────────────────────────────────

class AstroApp(QMainWindow):
    """Fenêtre principale de Céleste."""

    def __init__(self):
        super().__init__()
        self.resize(1400, 880)
        self.setMinimumSize(1120, 720)
        self.setWindowIcon(icons.app_icon())

        # État
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
        self._day_start          = None      # minuit local du jour calculé, en TU
        self._geo_source         = None      # requête au service de localisation en cours
        self.sun_altitudes       = []
        self.moon_altitudes      = []
        self.last_cache_key      = ""
        self._dte = self._lat = self._lon = None
        self._sky_scene          = None
        self._sky_objects        = []
        self._sky_hover          = None
        self._dirty              = set()
        self._last_search        = None

        # Minuteries : temps réel et recalcul différé après une saisie
        self._live_timer = QTimer(self)
        self._live_timer.timeout.connect(self._live_tick)
        self._recalc_timer = QTimer(self)
        self._recalc_timer.setSingleShot(True)
        self._recalc_timer.timeout.connect(self.calculate)

        # Raccourcis, attachés à la fenêtre : ils survivent aux reconstructions
        for keys, slot in ((("F5", "Ctrl+Return"), self.calculate),
                           (("Ctrl+L",), lambda: self.btn_live.toggle())):
            for key in keys:
                QShortcut(QKeySequence(key), self).activated.connect(slot)

        self._build_ui()
        self.calculate()

    # ──────────────────────────────────────────────────────────────────────────
    # CONSTRUCTION DE L'INTERFACE
    # ──────────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        """Construit (ou reconstruit) toute la fenêtre dans la langue et le thème actifs."""
        self.setWindowTitle(t("app.title"))
        central = QWidget()
        central.setObjectName("central")
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_sidebar())

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
        self._build_ephemeris_tab()
        self._build_trajectories_tab()
        self._build_skymap_tab()
        self._build_planets_tab()
        self._build_coordinates_tab()
        self._build_events_tab()
        self._build_settings_tab()
        self.tabs.currentChanged.connect(self._on_tab_changed)

        self.setCentralWidget(central)
        self._build_status_bar()
        # Sinon le champ de date reçoit le focus avec son jour sélectionné
        self.tabs.setFocus()

    # ── Barre latérale ────────────────────────────────────────────────────────

    def _build_sidebar(self):
        side = QFrame()
        side.setObjectName("sidebar")
        side.setFixedWidth(312)
        lay = QVBoxLayout(side)
        lay.setContentsMargins(24, 24, 24, 16)
        lay.setSpacing(16)

        # En-tête : le symbole Astræos, puis le nom de l'application
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

        # Date et heure TU
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
        self.field_date = ChampSaisie(t("side.datetime"), self.dt_edit)
        self.btn_now = _bouton_icone("now", t("side.now_tip"))
        self.btn_now.clicked.connect(self.set_now)
        lay.addLayout(self._with_button(self.field_date, self.btn_now))

        # Lieu
        validator = QRegularExpressionValidator(QRegularExpression(_COORD_REGEX))
        self.entry_lat = QLineEdit(_coord_text(_pref_float("default_lat", 49.6333)))
        self.entry_lon = QLineEdit(_coord_text(_pref_float("default_lon", -1.6167)))
        self.field_lat = ChampSaisie(t("side.latitude"), self.entry_lat, unite="°",
                                     numerique=True)
        self.field_lon = ChampSaisie(t("side.longitude"), self.entry_lon, unite="°",
                                     numerique=True)
        for edit, key in ((self.entry_lat, "latitude"), (self.entry_lon, "longitude")):
            edit.setValidator(validator)
            edit.setToolTip(t(f"side.{key}_tip"))
            edit.returnPressed.connect(self.calculate)
            edit.textEdited.connect(self._on_coords_edited)
        lay.addWidget(self.field_lat)
        btn_geo = _bouton_icone("geolocate", t("side.geoloc_tip"))
        btn_geo.clicked.connect(lambda _checked=False: self.geolocate())
        lay.addLayout(self._with_button(self.field_lon, btn_geo))

        self.entry_elev = QLineEdit(_elev_text(_pref_float("default_elevation", 0.0)))
        self.entry_elev.setValidator(QRegularExpressionValidator(QRegularExpression(r"^-?\d{0,4}$")))
        self.entry_elev.setToolTip(t("side.elevation_tip"))
        self.entry_elev.returnPressed.connect(self.calculate)
        lay.addWidget(ChampSaisie(t("side.elevation"), self.entry_elev, unite="m", numerique=True))

        # Fuseau IANA (heure d'été comprise), à taper ou choisir ; « Automatique » suit le lieu
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
        lay.addWidget(ChampSaisie(t("side.timezone"), self.tz_menu))

        self.combo_fav = QComboBox()
        self.combo_fav.setPlaceholderText(t("side.favorites_placeholder"))
        self.combo_fav.setMinimumContentsLength(6)
        self._refresh_favorites_combo()
        self.combo_fav.activated.connect(self._apply_favorite)
        fav_add = _bouton_icone("favorite_add", t("side.fav_save_tip"))
        fav_add.clicked.connect(self.save_location)
        fav_del = _bouton_icone("delete", t("side.fav_delete_tip"))
        fav_del.clicked.connect(self.delete_location)
        lay.addLayout(self._with_button(ChampSaisie(t("side.favorites"), self.combo_fav),
                                        fav_add, fav_del))

        # Actions : Calculer est la seule zone dorée de l'écran
        lay.addSpacing(4)
        self.btn_calc = _bouton(t("side.calculate"), "calculate", "principal")
        self.btn_calc.setToolTip(tf("side.calculate_tip", key="F5"))
        self.btn_calc.clicked.connect(self.calculate)
        lay.addWidget(self.btn_calc)
        self.btn_live = _bouton(t("side.live"), "live", "secondaire", checkable=True)
        self.btn_live.setToolTip(tf("side.live_tip", key="Ctrl+L"))
        self.btn_live.toggled.connect(self.toggle_live)
        lay.addWidget(self.btn_live)

        lay.addStretch()
        self.theme_selector = SelecteurTheme(Config.THEME, self._on_theme_selected)
        lay.addWidget(self.theme_selector)
        lay.addWidget(_label(tf("app.version", version=APP_VERSION), "legende"))
        return side

    @staticmethod
    def _with_button(field, *buttons):
        """Un champ et des boutons ronds alignés sur sa boîte de saisie."""
        row = QHBoxLayout()
        row.setSpacing(4)
        row.addWidget(field, stretch=1)
        for btn in buttons:
            row.addWidget(btn, alignment=Qt.AlignmentFlag.AlignBottom)
        return row

    # ── Onglet 1 : éphémérides ────────────────────────────────────────────────

    def _build_ephemeris_tab(self):
        scroll, _page, lay = _scroll_page()

        # Les valeurs qui se lisent d'un coup d'œil
        cards = QHBoxLayout()
        cards.setSpacing(16)
        self.card_sun_alt = CarteDonnee(t("cards.sun_alt"), SYMBOL["Sun"], "or")
        self.card_sun_rise = CarteDonnee(t("cards.sun_rise"), SYMBOL["Sun"], "or")
        self.card_moon_alt = CarteDonnee(t("cards.moon_alt"), SYMBOL["Moon"], "lune")
        self.card_moon_illum = CarteDonnee(t("cards.moon_illum"), SYMBOL["Moon"], "lune")
        for card in (self.card_sun_alt, self.card_sun_rise, self.card_moon_alt,
                     self.card_moon_illum):
            cards.addWidget(card, stretch=1)
        lay.addLayout(cards)

        row = QHBoxLayout()
        row.setSpacing(16)

        # Soleil
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

        # Lune
        card, body, self._lbl_moon_state = self._body_card(SYMBOL["Moon"], "lune", t("moon.title"))
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
        self._phase_disc = PhaseLune(56)
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

    def _body_card(self, symbole, accent, title):
        """Carte d'un astre : (carte, grille des données, pastille d'état)."""
        card = _card()
        outer = QVBoxLayout(card)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(12)
        head = QHBoxLayout()
        head.setSpacing(8)
        head.addWidget(_label(symbole, "symbole", tone=accent))
        head.addWidget(_label(title, "sous-titre"))
        head.addStretch()
        badge = _pastille()
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
        Ajoute un intertitre (texte, QLabel ou None) puis une ligne « libellé …
        valeur » par champ (CarteDonnee compacte) ; retourne la ligne suivante.
        Champ : (clé, clé de traduction[, mise en avant]).
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

    # ── Onglets 2 et 3 : graphiques ───────────────────────────────────────────

    def _chart_page(self, name, toolbar=None, hint=None):
        """Page d'onglet : un graphique matplotlib dans une carte."""
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
            lay.addWidget(_label(hint, "legende", wrap=True))
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
        bar.addWidget(_label(t("skymap.mag_limit"), "libelle"))
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
        bar.addStretch()

        page, self.fig_sky, self.canvas_sky = self._chart_page(
            "sky", toolbar=bar, hint=t("skymap.hint"))
        self._sky_ax = None
        self._sky_tip = _TooltipLayer(self.canvas_sky)
        self.canvas_sky.mpl_connect("motion_notify_event", self._on_sky_hover)
        self.canvas_sky.mpl_connect("button_press_event", self._on_sky_click)
        self.canvas_sky.mpl_connect("figure_leave_event", self._on_sky_leave)
        self.tabs.addTab(page, t("tabs.skymap"))

    # ── Onglet 4 : planètes ───────────────────────────────────────────────────

    def _build_planets_tab(self):
        page = QWidget()
        page.setObjectName("page")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 16, 0, 16)
        lay.setSpacing(16)

        # tous les astres, ou un groupe ; seulement ceux au-dessus de l'horizon
        self._planet_group = prefs.get("planet_group") or "planets"
        if self._planet_group not in ("all",) + tuple(k for k, _names in _BODY_GROUPS):
            self._planet_group = "planets"
        options = [("all", t("planets.group_all"), t("planets.group_all_tip"))]
        options += [(key, t(f"planets.group_{key}"), t(f"planets.group_{key}_tip"))
                    for key, _names in _BODY_GROUPS]
        self._planet_selector = SelecteurTheme(self._planet_group, self._on_planet_group, options,
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

        # la visibilité se lit à la couleur du nom (vive au-dessus de l'horizon)
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
            items["col_planet"].setData(_SORT_ROLE, r)                # ordre du Système solaire
            self._planet_items[name] = items
        self.planet_table = table
        # un clic sur un astre ouvre sa fenêtre de données
        table.cellClicked.connect(
            lambda row, _col: self._show_body_detail(table.item(row, 0).data(_NAME_ROLE)))
        table.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
        table.setToolTip(t("detail.click_tip"))
        # la dernière colonne s'étire : jamais de défilement horizontal pour quelques pixels
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._planet_alt = {}
        # clic sur un en-tête : tri croissant puis décroissant ; « Planète » : ordre naturel.
        # La colonne triée a son en-tête en or (la flèche de Qt élargirait toutes les colonnes)
        table.setSortingEnabled(True)
        header.setSortIndicatorShown(False)
        table.sortItems(0, Qt.SortOrder.AscendingOrder)
        header.sortIndicatorChanged.connect(self._on_planet_sort)
        self._show_planet_group()
        lay.addWidget(table)

        card = _card()
        card_l = QVBoxLayout(card)
        card_l.setContentsMargins(8, 8, 8, 8)
        self.fig_orrery = Figure(facecolor=Config.CIEL_100)
        self.canvas_orrery = FigureCanvasQTAgg(self.fig_orrery)
        card_l.addWidget(self.canvas_orrery)
        lay.addWidget(card, stretch=1)
        self._chart_tabs[page] = "orrery"
        self.tabs.addTab(page, t("tabs.planets"))

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

    _PLANET_ROWS_MAX = 8            # au-delà, le tableau défile

    def _show_planet_group(self):
        """N'affiche que les astres du groupe choisi, et seulement ceux au-dessus
        de l'horizon si « Visibles seulement » est cochée."""
        group = dict(_BODY_GROUPS).get(self._planet_group)
        visible_only = self._planet_visible.isChecked()
        table = self.planet_table
        shown = 0
        for r in range(table.rowCount()):
            name = table.item(r, 0).data(_NAME_ROLE)
            hide = bool((group is not None and name not in group) or (
                visible_only and float(self._planet_alt.get(name, 0.0)) <= 0.0))
            table.setRowHidden(r, hide)
            shown += not hide
        table.resizeColumnsToContents()
        header = table.horizontalHeader()
        rows = max(1, min(shown, self._PLANET_ROWS_MAX))
        table.setFixedHeight(40 * rows + header.sizeHint().height() + 4)

    # ── Onglet Coordonnées ────────────────────────────────────────────────────
    #    x, y, z et distance selon l'origine « cartésiennes » ; deux angles selon
    #    le repère « angulaires » ; magnitude, angle avec le Soleil, constellation.

    _COORD_CHOICES = (
        ("cartesian", AstroEngine.CENTERS, "coord_cartesian"),
        ("angular", AstroEngine.FRAMES, "coord_angular"),
        ("ecliptic_from", ("sun", "earth"), "coord_ecliptic_from"),
        ("angle", ("global",) + Formatters.ANGLE_FORMATS, "coord_angle_format"),
    )
    _COORD_COLUMNS = ("col_body", "col_x", "col_y", "col_z", "col_dist", "col_mag",
                      "col_sun_angle", "col_constellation", "angle1", "angle2")

    def _build_coordinates_tab(self):
        # dix-huit astres : la page défile si la fenêtre est trop basse
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
            row.addWidget(ChampSaisie(t(f"coordinates.{key}"), menu), stretch=1)
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
        propose = _bouton(t("links.body_more"), variante="discret", compact=True)
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
        """Le choix Soleil / Terre ne vaut que pour les coordonnées écliptiques."""
        self.coord_menus["ecliptic_from"].setEnabled(self._coord_choice("angular") == "ecliptic")

    def _on_coord_choice(self, key):
        pref = dict((k, p) for k, _o, p in self._COORD_CHOICES)[key]
        prefs.set(pref, self._coord_choice(key))
        self._sync_coord_menus()
        self._refresh_coordinates()

    def _coord_angle_format(self):
        """Format des angles du tableau : le sien, ou celui des paramètres (« global »)."""
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
        """Tableau des coordonnées, calculé quand son onglet est affiché."""
        if self._lat is None or self.tabs.currentWidget() is not getattr(self, "_coord_page", None):
            return
        cartesian, angular, from_body = (self._coord_choice(k)
                                         for k in ("cartesian", "angular", "ecliptic_from"))
        # (origine, repère) des angles : équatoriales et horizontales vues du lieu,
        # écliptiques vues du Soleil ou de la Terre
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
            self.coord_table.item(r, 7).setToolTip(obs["constellation_name"] if obs else "")
        self._coord_note.setText(" ".join((
            t(f"coordinates.note_cartesian_{cartesian}"),
            t(f"coordinates.note_angular_{angular if angular != 'ecliptic' else 'ecliptic_' + from_body}"),
            t("coordinates.note_observation"))))

    # ── Onglet 5 : événements ─────────────────────────────────────────────────

    def _build_events_tab(self):
        page = QWidget()
        page.setObjectName("page")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 16, 0, 0)
        lay.setSpacing(16)

        bar = QHBoxLayout()
        bar.setSpacing(8)
        btn_ecl = _bouton(t("events.search_eclipses"), "search")
        btn_ecl.clicked.connect(self._search_eclipses_gui)
        btn_conj = _bouton(t("events.search_conjunctions"), "search")
        btn_conj.clicked.connect(self._search_conjunctions_gui)
        bar.addWidget(btn_ecl)
        bar.addWidget(btn_conj)
        bar.addStretch()
        self._btn_ics = _bouton(t("events.export_ics"), "export")
        self._btn_ics.setToolTip(t("events.export_tip"))
        self._btn_ics.setEnabled(False)
        self._btn_ics.clicked.connect(self._export_ics)
        bar.addWidget(self._btn_ics)
        lay.addLayout(bar)

        # filtres des évènements de l'année
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

    # ── Onglet 6 : paramètres ─────────────────────────────────────────────────

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

        # Langue et affichage
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
        row.addWidget(ChampSaisie(t("settings.language"), self._lang_combo), stretch=1)
        row.addWidget(ChampSaisie(t("settings.time_format"), self._timefmt_combo), stretch=1)
        row.addWidget(ChampSaisie(t("settings.angle_format"), self._anglefmt_combo), stretch=1)
        box.addLayout(row)
        box.addWidget(_label(t("settings.theme_hint"), "legende", wrap=True))

        # Lieu de démarrage
        box = section(t("settings.default_place_section"))
        self._place_entry = QLineEdit(_clean_place(prefs.get("default_place")))
        box.addWidget(ChampSaisie(t("settings.default_place_name"), self._place_entry))
        coords = QVBoxLayout()
        coords.setSpacing(4)
        coords.addWidget(_label(t("settings.default_place_coords"), "libelle"))
        self._default_coords_lbl = _label("", "donnee")
        coords.addWidget(self._default_coords_lbl)
        box.addLayout(coords)
        self._update_default_place_label()
        buttons = QHBoxLayout()
        btn_use = _bouton(t("settings.use_current"), "place")
        btn_use.setToolTip(t("settings.use_current_tip"))
        btn_use.clicked.connect(self._save_default_place)
        buttons.addWidget(btn_use)
        buttons.addStretch()
        box.addLayout(buttons)
        self._autogeo_cb = QCheckBox(t("settings.auto_geoloc"))
        self._autogeo_cb.setChecked(bool(prefs.get("auto_geoloc")))
        self._autogeo_cb.toggled.connect(lambda v: prefs.set("auto_geoloc", bool(v)))
        box.addWidget(self._autogeo_cb)

        # Temps réel
        box = section(t("settings.live_section"))
        box.addWidget(_label(t("settings.live_interval"), "libelle"))
        iv = QHBoxLayout()
        iv.setSpacing(12)
        self._iv_slider = QSlider(Qt.Orientation.Horizontal)
        self._iv_slider.setRange(1, 20)            # pas de 500 ms
        self._iv_slider.setValue(int((prefs.get("live_interval") or 2000) / 500))
        self._iv_lbl = _label("", "donnee")
        self._iv_lbl.setMinimumWidth(80)
        self._iv_slider.valueChanged.connect(self._on_interval_changed)
        iv.addWidget(self._iv_slider, stretch=1)
        iv.addWidget(self._iv_lbl)
        self._iv_lbl.setText(tf("units.ms", value=_num(self._iv_slider.value() * 500)))
        box.addLayout(iv)

        # Réinitialisation (irréversible : bouton danger et confirmation)
        box = section(t("settings.reset_section"))
        box.addWidget(_label(t("settings.reset_hint"), "legende", wrap=True))
        buttons = QHBoxLayout()
        btn_reset = _bouton(t("settings.reset_btn"), variante="danger")
        btn_reset.clicked.connect(self._reset_settings)
        buttons.addWidget(btn_reset)
        buttons.addStretch()
        box.addLayout(buttons)

        # À propos : liens
        box = section(t("settings.about_section"))
        box.addWidget(_label(tf("settings.about", version=APP_VERSION), "corps", wrap=True))
        box.addWidget(_label(t("settings.credits"), "legende", wrap=True))
        self._link_buttons = {}
        for links in ((("site", _URL_SITE), ("source", _URL_REPO), ("coffee", _URL_COFFEE)),
                      (("bug", _issue_url("bug")), ("feature", _issue_url("feature")),
                       ("body", _issue_url("body")))):
            row = QHBoxLayout()
            row.setSpacing(8)
            for key, url in links:
                btn = _bouton(t(f"links.{key}"), variante="secondaire", compact=True)
                btn.setToolTip(t(f"links.{key}_tip"))
                btn.clicked.connect(lambda _checked=False, u=url: _open_url(u))
                self._link_buttons[key] = btn
                row.addWidget(btn)
            row.addStretch()
            box.addLayout(row)

        lay.addStretch()
        self.tabs.addTab(scroll, t("tabs.settings"))

    # ── Barre d'état ──────────────────────────────────────────────────────────

    def _build_status_bar(self):
        bar = QStatusBar()
        bar.setSizeGripEnabled(False)
        self.setStatusBar(bar)
        self._lbl_pos = QLabel("—")
        self._lbl_stars = QLabel("")
        self._lbl_live = _pastille(t("status.live_on"), "info")
        self._lbl_live.setVisible(False)
        self._lbl_time = QLabel("")
        bar.addWidget(self._lbl_pos)
        bar.addWidget(self._lbl_stars)
        bar.addPermanentWidget(self._lbl_live)
        bar.addPermanentWidget(self._lbl_time)
        self._apply_live_ui()

    # ──────────────────────────────────────────────────────────────────────────
    # RECONSTRUCTION (LANGUE / THÈME)
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
        """Coordonnée saisie (nombre), ou le texte tel quel s'il est invalide."""
        try:
            return float(edit.text().strip().replace(",", ".").replace("−", "-"))
        except ValueError:
            return edit.text()

    def _rebuild(self, keep_place=True):
        """Reconstruit la fenêtre (nouvelle langue ou nouveau thème) en gardant
        la date, l'onglet, le mode temps réel et, si *keep_place*, le lieu."""
        state = self._snapshot()
        apply_theme(QApplication.instance())
        self._build_ui()
        self._set_datetime(state["dte"])
        if keep_place:
            for edit, value in ((self.entry_lat, state["lat"]), (self.entry_lon, state["lon"])):
                edit.setText(_coord_text(value) if isinstance(value, float) else value)
            self.entry_elev.setText(state["elev"])
            self.combo_fav.setCurrentIndex(state["fav"])
        self._dirty = set()
        self.tabs.setCurrentIndex(state["tab"])
        self.btn_live.blockSignals(True)
        self.btn_live.setChecked(self.live_mode)
        self.btn_live.blockSignals(False)
        self._apply_live_ui()
        self.last_cache_key = ""
        self.calculate()
        if self._last_search == "eclipses":
            self._search_eclipses_gui()
        elif self._last_search == "conjunctions":
            self._search_conjunctions_gui()

    # ──────────────────────────────────────────────────────────────────────────
    # HANDLERS PARAMÈTRES
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
        """Format des angles de tout le logiciel (et du tableau des coordonnées s'il le suit)."""
        prefs.set("angle_format", self._anglefmt_combo.itemData(index))
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
        """Le lieu saisi devient le lieu de démarrage (nom, coordonnées, fuseau)."""
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
    # FAVORIS
    # ──────────────────────────────────────────────────────────────────────────

    def _load_favorites(self):
        for path in (_FAVORITES_FILE, _LEGACY_FAVORITES_FILE, _DEFAULT_FAVORITES_FILE):
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        return json.load(f)
                except (OSError, json.JSONDecodeError):
                    continue
        return {}

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

    def _on_coords_edited(self, _text):
        """Coordonnées tapées à la main : ce n'est plus un lieu nommé."""
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
    # DATE, FUSEAU, FORMAT DE L'HEURE
    # ──────────────────────────────────────────────────────────────────────────

    def _set_datetime(self, dte):
        """Affiche *dte* (TU, sans fuseau) sans déclencher de recalcul."""
        qdt = QDateTime(QDate(dte.year, dte.month, dte.day),
                        QTime(dte.hour, dte.minute, dte.second), _utc_zone())
        self.dt_edit.blockSignals(True)
        self.dt_edit.setDateTime(qdt)
        self.dt_edit.blockSignals(False)

    def _edit_datetime(self):
        """Date et heure TU saisies (datetime sans fuseau)."""
        qdt = self.dt_edit.dateTime().toUTC()
        d, tm = qdt.date(), qdt.time()
        return datetime(d.year(), d.month(), d.day(), tm.hour(), tm.minute(), tm.second())

    def current_inputs(self):
        """(date TU, latitude, longitude) saisies ; ValueError si invalides."""
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
        """Montre le fuseau *name* dans le sélecteur, sans recalcul."""
        idx = self.tz_menu.findData(name)
        if idx < 0:
            self.tz_menu.addItem(name, name)
            idx = self.tz_menu.count() - 1
        self.tz_menu.blockSignals(True)
        self.tz_menu.setCurrentIndex(idx)
        self.tz_menu.blockSignals(False)

    def _elevation(self):
        """Altitude saisie de l'observateur, en mètres (0 si vide ou invalide)."""
        try:
            return max(-500.0, min(9000.0, float(self.entry_elev.text().strip() or 0)))
        except ValueError:
            return 0.0

    def _local(self, dt):
        """Heure locale (sans fuseau) de l'instant TU *dt* : fuseau du lieu, heure d'été comprise."""
        return dt.replace(tzinfo=timezone.utc).astimezone(self._zone).replace(tzinfo=None)

    @property
    def utc_offset(self):
        """Décalage du fuseau à l'instant calculé, en heures (heure d'été comprise)."""
        dte = getattr(self, "_dte", None) or _utc_now()
        return dte.replace(tzinfo=timezone.utc).astimezone(self._zone).utcoffset().total_seconds() / 3600

    def _midnight_offset(self):
        """Décalage du fuseau au minuit local du jour calculé, en heures."""
        start = self._day_start or self._dte
        return (self._local(start) - start).total_seconds() / 3600

    def _zone_text(self):
        """« Europe/Paris · UTC+1 » : le fuseau et son décalage à l'instant calculé."""
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
    # GÉOLOCALISATION / TEMPS RÉEL
    # ──────────────────────────────────────────────────────────────────────────

    def geolocate(self, interactive=True):
        """
        Position de l'appareil par le service de localisation du système
        (GPS, Wi-Fi : QtPositioning) ; s'il est absent, refusé ou muet, sa
        dernière position connue, sinon la position approximative de l'adresse
        IP. *interactive* (bouton) : une fenêtre dit alors pourquoi le service
        n'a pas répondu et ouvre ses réglages ; au démarrage, la barre d'état.
        """
        if self._geo_source is not None:                     # une requête est en cours
            return
        self._geo_interactive = interactive
        source = QGeoPositionInfoSource.createDefaultSource(self)
        if source is None:
            self._geolocate_by_ip("no_source")
            return
        if hasattr(source, "setPreferredPositioningMethods"):           # GPS, Wi-Fi, réseau
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
            self._on_device_position(last)                    # dernière position connue
            return
        code = getattr(error, "value", error)
        reason = {0: "access", 1: "closed", 4: "timeout"}.get(code, "unknown")
        self._geolocate_by_ip(reason)

    def _set_place(self, lat, lon, name, zone=None):
        """Lieu trouvé par la géolocalisation : coordonnées, nom, fuseau, puis calcul."""
        self.entry_lat.setText(_coord_text(lat))
        self.entry_lon.setText(_coord_text(lon))
        if zone and self.tz_name != _AUTO_ZONE and self.tz_menu.findData(zone) >= 0:
            self.tz_name = zone
            self._select_zone(zone)
        self.location_name = name
        self.combo_fav.setCurrentIndex(-1)
        self.calculate()

    def _geolocate_by_ip(self, reason=None):
        """Secours : position de l'adresse IP, souvent celle du fournisseur d'accès ;
        *reason* : pourquoi le service de l'appareil n'a pas répondu."""
        url = ("http://ip-api.com/json/"
               "?fields=status,message,country,city,lat,lon,timezone")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": f"Celeste/{APP_VERSION}"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # réseau, délai, JSON
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, t("errors.network_title"),
                                 tf("errors.geoloc_network", detail=exc))
            return
        QApplication.restoreOverrideCursor()
        if data.get("status") != "success":
            QMessageBox.warning(self, t("errors.geoloc_title"), t("errors.geoloc_fail"))
            return
        self._set_place(float(data["lat"]), float(data["lon"]), data.get("city") or "",
                        data.get("timezone"))
        self.statusBar().showMessage(
            tf("errors.geoloc_ip", city=data.get("city", "?"),
               country=data.get("country", "?")), 12000)
        if reason and getattr(self, "_geo_interactive", False):
            self._explain_geolocation(reason, data.get("city", "?"), data.get("country", "?"))

    def _explain_geolocation(self, reason, city, country):
        """Fenêtre (non bloquante) : position de l'IP, pourquoi, et les réglages à ouvrir."""
        box = QMessageBox(QMessageBox.Icon.Information, t("errors.geoloc_title"),
                          tf("errors.geoloc_ip_short", city=city, country=country), parent=self)
        box.setInformativeText(t(f"errors.geoloc_reason_{reason}"))
        url = _LOCATION_SETTINGS.get(sys.platform)
        settings = None
        if url and reason in ("access", "closed", "no_source", "timeout"):
            settings = box.addButton(t("errors.geoloc_open_settings"), QMessageBox.ButtonRole.ActionRole)
        box.addButton(QMessageBox.StandardButton.Close)

        def done(_result):
            if settings is not None and box.clickedButton() is settings:
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
        """Temps réel : le bouton reste enfoncé (aplat encre), la date se fige."""
        on = self.live_mode
        self.dt_edit.setReadOnly(on)
        _repolish(self.dt_edit)
        self.field_date.set_desactive(on)
        self.btn_now.setEnabled(not on)
        self._lbl_live.setVisible(on)

    def _live_tick(self):
        self._set_datetime(_utc_now())
        self.calculate()

    # ──────────────────────────────────────────────────────────────────────────
    # CALCUL PRINCIPAL
    # ──────────────────────────────────────────────────────────────────────────

    def _warn_invalid_coords(self):
        QMessageBox.warning(self, t("errors.error_title"), t("status.invalid_coords"))

    def _check_inputs(self):
        """Signale les coordonnées invalides sous leur champ ; True si tout est valide."""
        ok = True
        for edit, field, limit, key in ((self.entry_lat, self.field_lat, 90.0, "side.lat_error"),
                                        (self.entry_lon, self.field_lon, 180.0, "side.lon_error")):
            try:
                _parse_coord(edit.text(), limit)
                _set_invalid(edit, False)
                field.set_erreur(None)
            except ValueError:
                _set_invalid(edit, True)
                field.set_erreur(t(key))
                ok = False
        return ok

    def calculate(self):
        """Recalcule tout pour la date et le lieu saisis, puis met l'affichage à jour."""
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

        # Événements du jour et courbes 24 h : seulement si la date ou le lieu change
        key = (f"{self._local(dte):%Y-%m-%d}_{lat:.4f}_{lon:.4f}_"
               f"{getattr(self._zone, 'key', 'UTC')}_{elev:g}")
        if key != self.last_cache_key:
            self.sun_events  = AstroEngine.find_events(dte, lat, lon, "sun", self._zone, elev)
            self.moon_events = AstroEngine.find_events(dte, lat, lon, "moon", self._zone, elev)
            self.planet_events = {name: AstroEngine.find_events(dte, lat, lon, name, self._zone, elev)
                                  for name in _PLANETS + MINOR_PLANETS}
            self.hours, self.sun_altitudes, self.moon_altitudes = \
                charts.sample_day(dte, lat, lon, elevation_m=elev, tz=self._zone)
            self._day_start = AstroEngine._local_day(dte, self._zone)[0]
            self.last_cache_key = key

        self.planets, self.minor_planets = [], []
        magnitudes = AstroEngine.observations(tc, _PLANETS + MINOR_PLANETS)
        for name in _PLANETS + MINOR_PLANETS:
            ra, dec, dist = AstroEngine.planet_position(tc, name)
            alt, az = AstroEngine.horizontal(tc, lat, lon, name, elev)
            minor = name in MINOR_PLANETS
            (self.minor_planets if minor else self.planets).append({
                "name": name, "ra": ra, "dec": dec, "dist": dist, "alt": alt, "az": az,
                "elong": AstroEngine.angular_separation(ra, dec, s_ra, s_dec),
                "east": (ra - s_ra) % 24 < 12, "mag": magnitudes[name]["mag"], "minor": minor,
            })

        # sur la carte, les planètes mineures assez brillantes pour la limite choisie
        bright = [m for m in self.minor_planets if m["mag"] <= self._mag_limit()]
        self._sky_scene = charts.sky_scene(jd, lat, lon, self._mag_limit(),
                                           self.sun_data, self.moon_data, self.planets + bright)
        self._sky_objects = charts.visible_objects(self._sky_scene)
        self.visible_stars = [s["name"] for s in self._sky_scene["stars"]]
        self.visible_planets_map = [p["name"] for p in self.planets if p["alt"] > 0]

        self._update_data_cards()
        self._update_sun_card()
        self._update_moon_card()
        self._update_planet_table()
        self._refresh_coordinates()
        self._update_status()
        self._dirty = {"traj", "sky", "orrery"}
        self._draw_visible_chart()

    # ──────────────────────────────────────────────────────────────────────────
    # MISE À JOUR DES CARTES
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
        self.card_sun_alt.set_valeur(
            _num(sd["alt"], 1, signed=True), "°",
            f"{tf('cards.azimuth', value=_deg(sd['az'], 1))} · {t('sun.state_' + self._sun_phase())}")
        rise, sunset = self.sun_events.get("rise"), self.sun_events.get("set")
        self.card_sun_rise.set_valeur(
            self._format_event(rise), "",
            tf("cards.set_at", time=self._format_event(sunset)))
        self.card_moon_alt.set_valeur(
            _num(md["alt"], 1, signed=True), "°",
            f"{tf('cards.rise_at', time=self._format_event(self.moon_events.get('rise')))} · "
            f"{tf('cards.set_at', time=self._format_event(self.moon_events.get('set')))}")
        key = Formatters.PHASES[Formatters.phase_index(md["phase"])][0]
        self.card_moon_illum.set_valeur(_num(md["illum"], 0), "%", t(f"phases.{key}"))

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
        _set_pastille(self._lbl_sun_state, t(f"sun.state_{phase}"),
                      "info" if phase == "day" else "neutre")

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
            _set_pastille(self._lbl_moon_state, t("common.above_horizon"), "info")
        else:
            _set_pastille(self._lbl_moon_state, t("common.below_horizon"), "neutre")

    def _update_planet_table(self):
        table = self.planet_table
        table.setSortingEnabled(False)                   # pas de tri pendant la mise à jour
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
            items["col_dist"].setText(_num(p["dist"], 4))                 # UA dans l'en-tête
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
            name.setToolTip(t("common.visible" if up else "common.below_horizon"))
        table.setSortingEnabled(True)
        table.horizontalHeader().setSortIndicatorShown(False)     # setSortingEnabled la remet
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
    # GRAPHIQUES
    # ──────────────────────────────────────────────────────────────────────────

    def _on_tab_changed(self, _index):
        self._draw_visible_chart()
        self._refresh_coordinates()

    def _draw_visible_chart(self):
        """Dessine le graphique de l'onglet affiché s'il n'est plus à jour : en
        temps réel, les graphiques cachés ne sont pas redessinés."""
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
        now_h = (dte - start).total_seconds() / 3600       # depuis minuit local
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
            "planets": {n: _planet_name(n) for n in _PLANETS + MINOR_PLANETS},
        }
        self._sky_ax, tip = charts.draw_sky_map(self.fig_sky, self._sky_scene, labels)
        self._sky_tip.attach(tip)
        self._sky_hover = None
        self.canvas_sky.draw_idle()

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
        tc = AstroEngine.julian_century_j2000(self._dte)
        charts.draw_orrery(self.fig_orrery, charts.orrery_scene(tc), labels)
        self.canvas_orrery.draw_idle()

    # ── Survol et clic ───────────────────────────────────────────────────────

    def _on_traj_hover(self, event):
        tip = self._traj_tip.artist
        if tip is None:
            return
        if event.inaxes is not self._traj_ax or event.xdata is None or not self.hours:
            self._traj_tip.hide()
            return
        step = self.hours[1] - self.hours[0]
        i = max(0, min(len(self.hours) - 1, int(round(event.xdata / step))))
        hour = self.hours[i]                                  # depuis minuit local
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
        if obj["kind"] == "star":
            line += f"  ·  {t('detail.mag')} {_num(obj['mag'], 2)}"
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
        Titre et lignes (libellé, valeur) de la fiche d'un astre. *symbols* :
        symboles suivis de U+FE0E (Qt) ; sans, pour matplotlib. *full* : la
        fenêtre de données du Soleil, de la Lune ou d'une planète, avec
        diamètre apparent, phase, distances, temps de lumière, lever et coucher.
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
            consts = STAR_CONSTELLATION.get(obj["name"], [])
            if consts:
                rows.append((t("detail.constellation"),
                             ", ".join(t(f"constellations.{c}") for c in consts)))
            elif designation and not designation.startswith("HR"):
                latin = constellation_names().get(designation.split()[-1])
                if latin:
                    rows.append((t("detail.constellation"), latin))
            rows.append((t("detail.mag"), _num(obj["mag"], 2)))
        elif kind == "planet":
            title = f"{sym[obj['name']]} {_planet_name(obj['name'])}"
            side = t("coords.east") if obj.get("east") else t("coords.west")
            rows.append((t("detail.type"), t("detail.type_minor_planet" if obj.get("minor")
                                             else "detail.type_planet")))
            if obj.get("mag") is not None:
                rows.append((t("detail.mag"), _num(obj["mag"], 1)))
            rows.append((t("detail.distance"), tf("units.au", value=_num(obj["dist"], 4))))
            rows.append((t("detail.elongation"), f"{_deg(obj['elong'], 1)} {side}"))
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
        """« 8 min 15 s », « 1 h 15 min »."""
        seconds = int(round(seconds))
        if seconds < 60:
            return f"{seconds} s"
        if seconds < 3600:
            return f"{seconds // 60} min {seconds % 60:02d} s"
        return f"{seconds // 3600} h {seconds % 3600 // 60:02d} min"

    @staticmethod
    def _diameter(arcsec):
        """« 31′ 34″ », « 58,4″ »."""
        if arcsec >= 60.0:
            minutes, seconds = divmod(int(round(arcsec)), 60)
            return f"{minutes}′ {seconds:02d}″"
        return f"{_num(arcsec, 1 if arcsec >= 1 else 2)}″"

    def _data_rows(self, obj):
        """Lignes de la fenêtre de données d'un astre du Système solaire."""
        body = {"sun": "sun", "moon": "moon"}.get(obj["kind"], obj.get("name"))
        d = AstroEngine.body_details(AstroEngine.julian_century_j2000(self._dte), body)
        rows = [] if obj.get("mag") is not None else [(t("detail.mag"), _num(d["mag"], 2))]
        if d.get("constellation"):
            rows.append((t("detail.constellation"), f"{d['constellation_name']} ({d['constellation']})"))
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
        """L'astre *name* tel que la carte du ciel le décrit : Soleil, Lune ou planète."""
        if name == "sun":
            return {**self.sun_data, "kind": "sun"}
        if name == "moon":
            return {**self.moon_data, "kind": "moon"}
        planet = next((p for p in self.planets + self.minor_planets if p["name"] == name), None)
        return {**planet, "kind": "planet"} if planet else None

    def _show_body_detail(self, name):
        """Fenêtre de données d'un astre choisi dans un tableau (non bloquante)."""
        obj = self._body_object(name)
        if obj is None:
            return
        dlg = self._build_detail_dialog(obj)
        self._detail_dialog = dlg
        dlg.open()

    def _build_detail_dialog(self, obj):
        title, rows = self._object_details(obj)
        if obj["kind"] in ("sun", "moon", "planet") and self._dte is not None:
            rows += self._data_rows(obj)
        dlg = QDialog(self)
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
        buttons = QDialogButtonBox()
        close = _bouton(t("detail.close"))
        buttons.addButton(close, QDialogButtonBox.ButtonRole.RejectRole)
        buttons.rejected.connect(dlg.reject)
        lay.addWidget(buttons)
        return dlg

    def _show_object_detail(self, obj):
        """Fiche détaillée d'un astre de la carte du ciel."""
        self._build_detail_dialog(obj).exec()

    # ──────────────────────────────────────────────────────────────────────────
    # ÉVÉNEMENTS
    # ──────────────────────────────────────────────────────────────────────────

    def _clear_evt_layout(self):
        while self._evt_layout.count():
            item = self._evt_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()           # deleteLater n'agit qu'au retour dans la boucle
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

    def _event_card(self, symbole, accent, title, when, pills=(), details=(), action=None, lines=()):
        """Carte d'événement : symbole, titre, pastilles, date ; détails dessous ;
        *action* : (texte, fonction) d'un bouton à droite."""
        card = _card()
        card.setObjectName("card")
        card.setProperty("eventCard", True)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(6)
        top = QHBoxLayout()
        top.setSpacing(8)
        top.addWidget(_label(symbole, "symbole", tone=accent))
        top.addWidget(_label(title, "corps", strong=True))
        for text, ton in pills:
            top.addWidget(_pastille(text, ton))
        top.addStretch()
        top.addWidget(_label(when, "donnee"))
        if action:
            btn = _bouton(action[0], "place", "secondaire", compact=True)
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
        """« 2 min 15 s »."""
        value = int(round(value))
        return f"{value // 60} min {value % 60:02d} s"

    def _eclipse_local_lines(self, ec, loc):
        """Circonstances locales d'une éclipse, en heure du lieu."""
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
        """Recherche et affiche les éclipses des 12 prochains mois."""
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
            greatest = ec.get("greatest", ec["date"]) + timedelta(seconds=30)  # minute la plus proche
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
        """Fenêtre : l'éclipse projetée au sol (bande, ligne de centralité, partialité)."""
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

    # ── Évènements de l'année : planètes, planètes mineures, Lune, saisons ─────

    _EVENT_GROUPS = ("planets", "minor", "moon", "seasons")
    _WINDS = ("n", "ne", "e", "se", "s", "sw", "w", "nw")

    def _body_name(self, name, symbol=False):
        """Nom d'un astre des évènements : planète, Soleil, Lune ou étoile."""
        if name in ("Sun", "Moon"):
            text = t(f"chart.{name.lower()}")
            return f"{SYMBOL[name]} {text}" if symbol else text
        if name in AstroEngine.MOON_STARS:
            return t(f"events.star_{name.lower()}")
        return _planet_name(name, symbol=symbol)

    def _event_title(self, ev, symbol=True):
        """Titre d'un évènement de l'année."""
        kind = ev["type"]
        if kind == "season":
            return t(f"events.{ev['kind']}")
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
        """« 06/01/2026 16:36 TU » : l'instant à la minute la plus proche."""
        return (dt + timedelta(seconds=30)).strftime("%d/%m/%Y %H:%M") + f" {t('chart.ut')}"

    def _clock(self, dt):
        """Heure locale du lieu, à la minute la plus proche."""
        return self._fmt_clock(self._local(dt + timedelta(seconds=30)))

    @staticmethod
    def _elide(text):
        """« de Uranus » → « d'Uranus » en français."""
        if get_lang() != "fr":
            return text
        return re.sub(r"\bde (?=[AEIOUYÉÈÊaeiouyéèê])", "d'", text)

    def _visibility_text(self, vis):
        if vis["period"] is None:
            return t(f"events.invisible_{vis['reason']}")
        wind = self._WINDS[int(round(vis["az"] / 45.0)) % 8]
        return tf(f"events.visible_{vis['period']}", alt=_num(vis["alt"]),
                  dir=t(f"skymap.cardinal_{wind}"), time=self._clock(vis["best"]))

    def _event_shown(self, ev):
        if not self._evt_filters[ev.get("group", "planets")].isChecked():
            return False
        vis = ev.get("visibility")
        return not (self._evt_filters["visible"].isChecked() and vis is not None and vis["period"] is None)

    def _search_conjunctions_gui(self):
        """Recherche les évènements des 12 mois : conjonctions, oppositions et
        élongations, planètes mineures, Lune, saisons ; leur visibilité d'ici."""
        dte = self._search_start("conjunctions")
        try:
            events = (AstroEngine.find_conjunctions(dte, num_days=365)
                      + AstroEngine.find_moon_events(dte, num_days=365)
                      + AstroEngine.find_seasons(dte, num_days=365))
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
        """Affiche les évènements trouvés que laissent passer les filtres."""
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
            symbole = SYMBOL["Sun"]
        elif kind in ("perihelion", "aphelion"):
            symbole = SYMBOL["Earth"]
            details.append(tf("events.distance_au", value=_num(ev["distance_au"], 5)))
        elif kind in ("perigee", "apogee"):
            symbole = SYMBOL["Moon"]
            details.append(tf("events.distance_km", value=_num(ev["distance_km"])))
            if kind == "perigee" and ev.get("syzygy") == "full":
                pills.append((t("events.supermoon"), "info"))
            elif ev.get("syzygy"):
                details.append(t(f"events.near_{ev['syzygy']}_moon"))
        else:
            sep = ev["separation"]
            if kind == "opposition":
                symbole = SYMBOL["opposition"]
                details.append(tf("events.elongation", value=_num(sep, 1)))
            elif kind == "greatest_elongation":
                symbole = SYMBOL[a]
                details.append(tf("events.elongation", value=_num(sep, 1)))
            else:
                symbole = SYMBOL["conjunction"]
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
        if vis is not None and kind not in ("perigee", "apogee"):
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
        self._event_card(symbole, "attenuee", title, self._event_when(ev["date"]), pills, details,
                         action, lines)
        self._ics_add(ev["date"], None, self._event_title(ev, symbol=False), details + lines)

    def _ics_add(self, start, end, summary, details):
        self._ics_items.append((start, end or start + timedelta(minutes=1), summary,
                                "\n".join(details)))

    def _export_ics(self):
        """Enregistre les évènements affichés dans un agenda iCalendar (.ics)."""
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
        """Fenêtre : trajets des astres parmi les étoiles autour de l'évènement."""
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
