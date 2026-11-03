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
  ★ Raccourcis : F5 calculer, Ctrl+L temps réel, Ctrl+E export PDF

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
from engine import EPHEMERIS_YEARS, AstroEngine  # noqa: E402
from i18n import (  # noqa: E402
    available_langs, get_lang, lang_name, resolve_lang, switch_lang, t, tf,
)
from utils import Formatters  # noqa: E402

# ── Constantes ────────────────────────────────────────────────────────────────


_FAVORITES_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "favorites.json")
_FONTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")

_AUTO_ZONE = "auto"           # fuseau déduit du lieu (timezonefinder)
_GEOLOC_TIMEOUT_MS = 15000    # attente du service de localisation de l'appareil
_PLANETS = ("Venus", "Mars", "Jupiter", "Saturn")
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


def _ra(hours):
    """Ascension droite « 14h 28m 19,0s »."""
    return Formatters.hms(hours).replace(".", _locale().decimalPoint())


def _dec(degrees):
    """Déclinaison « −14° 38′ 49″ » (signe toujours écrit)."""
    text = Formatters.dms(degrees).replace("'", "′").replace('"', "″")
    return text.replace("-", "−") if text.startswith("-") else "+" + text


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
    """SelecteurTheme Astræos : Nuit, Jour, Observation, l'option active en aplat encre."""

    def __init__(self, current, on_change):
        super().__init__()
        self.setObjectName("selecteurTheme")
        self.setAccessibleName(t("theme.legend"))
        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(4)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons = {}
        for key in THEME_NAMES:
            btn = QPushButton(t(f"theme.{key}"))
            btn.setObjectName("optionTheme")
            btn.setCheckable(True)
            btn.setFixedHeight(32)
            btn.setToolTip(t(f"theme.{key}_tip"))
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
QComboBox QAbstractItemView {{
    background: {C.CIEL_100}; border: 1px solid {C.CIEL_200}; outline: 0;
    selection-background-color: {C.CIEL_200}; selection-color: {C.ENCRE};
}}

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
        self.moon_events         = {}
        self.planets             = []
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
                           (("Ctrl+L",), lambda: self.btn_live.toggle()),
                           (("Ctrl+E",), self.export_pdf)):
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
        btn_geo.clicked.connect(self.geolocate)
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
        btn_pdf = _bouton(t("side.export"), "export", "secondaire")
        btn_pdf.setToolTip(tf("side.export_tip", key="Ctrl+E"))
        btn_pdf.clicked.connect(self.export_pdf)
        lay.addWidget(btn_pdf)

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

        columns = ["col_planet", "col_ra", "col_dec", "col_alt", "col_az",
                   "col_dist", "col_elong", "col_state"]
        table = QTableWidget(len(_PLANETS), len(columns))
        table.setHorizontalHeaderLabels([t(f"planets.{c}") for c in columns])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        table.setShowGrid(False)
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        table.verticalHeader().setDefaultSectionSize(40)
        mono = QFont()
        mono.setFamilies(list(_fonts["mono"]))
        mono.setPixelSize(15)
        mono.setWeight(QFont.Weight.Medium)
        self._planet_items = {}
        for r, name in enumerate(_PLANETS):
            items = {}
            for c, col in enumerate(columns):
                item = QTableWidgetItem("—")
                item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                if col == "col_planet":
                    item.setText(_planet_name(name, symbol=True))
                    bold = QFont()
                    bold.setFamilies(list(_fonts["sans"]))
                    bold.setPixelSize(15)
                    bold.setWeight(QFont.Weight.DemiBold)
                    item.setFont(bold)
                elif col != "col_state":
                    item.setFont(mono)
                table.setItem(r, c, item)
                items[col] = item
            self._planet_items[name] = items
        table.setFixedHeight(40 * len(_PLANETS) + header.sizeHint().height() + 4)
        self.planet_table = table
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
        lay.addLayout(bar)

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
        row = QHBoxLayout()
        row.setSpacing(16)
        row.addWidget(ChampSaisie(t("settings.language"), self._lang_combo), stretch=1)
        row.addWidget(ChampSaisie(t("settings.time_format"), self._timefmt_combo), stretch=1)
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

        # À propos
        box = section(t("settings.about_section"))
        box.addWidget(_label(tf("settings.about", version=APP_VERSION), "corps", wrap=True))
        box.addWidget(_label(t("settings.credits"), "legende", wrap=True))

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
        if os.path.exists(_FAVORITES_FILE):
            try:
                with open(_FAVORITES_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (OSError, json.JSONDecodeError):
                pass
        return {}

    def _save_favorites(self):
        try:
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

    def geolocate(self):
        """
        Position de l'appareil par le service de localisation du système
        (GPS, Wi-Fi : QtPositioning) ; s'il est absent, refusé ou muet, position
        approximative d'après l'adresse IP, annoncée comme telle.
        """
        if self._geo_source is not None:                     # une requête est en cours
            return
        source = QGeoPositionInfoSource.createDefaultSource(self)
        if source is None:
            self._geolocate_by_ip()
            return
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
            self._geolocate_by_ip()
            return
        lat, lon = coord.latitude(), coord.longitude()
        name = _place_name(lat, lon)
        self._set_place(lat, lon, name, _zone_at(round(lat, 3), round(lon, 3)))
        accuracy = info.attribute(QGeoPositionInfo.Attribute.HorizontalAccuracy)
        precision = f" (±{_num(accuracy)} m)" if accuracy == accuracy and accuracy > 0 else ""
        self.statusBar().showMessage(
            tf("errors.geoloc_device", place=name or f"{_fmt_lat(lat)}, {_fmt_lon(lon)}",
               precision=precision), 8000)

    def _on_device_position_error(self, _error):
        self._end_device_request()
        self._geolocate_by_ip()

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

    def _geolocate_by_ip(self):
        """Secours : position de l'adresse IP, souvent celle du fournisseur d'accès."""
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
    # EXPORT PDF
    # ──────────────────────────────────────────────────────────────────────────

    def export_pdf(self):
        try:
            from export_pdf import build_data_from_app, generate_report_pdf
        except ImportError as exc:
            QMessageBox.critical(self, t("pdf.title"), tf("pdf.error", detail=exc))
            return
        if not self._check_inputs():
            self._warn_invalid_coords()
            return
        self.calculate()        # le rapport suit exactement les valeurs saisies
        stamp = _utc_now().strftime("%Y%m%d_%H%M%S")
        path, _ = QFileDialog.getSaveFileName(
            self, t("pdf.dialog"),
            os.path.join(os.path.expanduser("~"), f"celeste_{stamp}.pdf"),
            t("pdf.filter"))
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        try:
            generate_report_pdf(build_data_from_app(self), path)
        except Exception as exc:
            QMessageBox.critical(self, t("pdf.title"), tf("pdf.error", detail=exc))
            return
        box = QMessageBox(QMessageBox.Icon.Information, t("pdf.title"),
                          tf("pdf.saved", path=path), parent=self)
        open_btn = box.addButton(t("pdf.open"), QMessageBox.ButtonRole.ActionRole)
        box.addButton(QMessageBox.StandardButton.Ok)
        box.exec()
        if box.clickedButton() is open_btn:
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))

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
            self.hours, self.sun_altitudes, self.moon_altitudes = \
                charts.sample_day(dte, lat, lon, elevation_m=elev, tz=self._zone)
            self._day_start = AstroEngine._local_day(dte, self._zone)[0]
            self.last_cache_key = key

        self.planets = []
        for name in _PLANETS:
            ra, dec, dist = AstroEngine.planet_position(tc, name)
            alt, az = AstroEngine.horizontal(tc, lat, lon, name, elev)
            self.planets.append({
                "name": name, "ra": ra, "dec": dec, "dist": dist, "alt": alt, "az": az,
                "elong": AstroEngine.angular_separation(ra, dec, s_ra, s_dec),
                "east": (ra - s_ra) % 24 < 12,
            })

        self._sky_scene = charts.sky_scene(jd, lat, lon, self._mag_limit(),
                                           self.sun_data, self.moon_data, self.planets)
        self._sky_objects = charts.visible_objects(self._sky_scene)
        self.visible_stars = [s["name"] for s in self._sky_scene["stars"]]
        self.visible_planets_map = [p["name"] for p in self.planets if p["alt"] > 0]

        self._update_data_cards()
        self._update_sun_card()
        self._update_moon_card()
        self._update_planet_table()
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
        lb["alt"].setText(_deg(sd["alt"], 2, signed=True))
        lb["az"].setText(_deg(sd["az"], 2))
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
        lb["alt"].setText(_deg(md["alt"], 2, signed=True))
        lb["az"].setText(_deg(md["az"], 2))
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
        for p in self.planets:
            items = self._planet_items[p["name"]]
            side = t("coords.east") if p["east"] else t("coords.west")
            items["col_ra"].setText(_ra(p["ra"]))
            items["col_dec"].setText(_dec(p["dec"]))
            items["col_alt"].setText(_deg(p["alt"], 2, signed=True))
            items["col_az"].setText(_deg(p["az"], 2))
            items["col_dist"].setText(tf("units.au", value=_num(p["dist"], 4)))
            items["col_elong"].setText(f"{_deg(p['elong'], 1)} {side}")
            up = p["alt"] > 0
            items["col_state"].setText(t("common.visible" if up else "common.below_horizon"))
            items["col_state"].setForeground(
                QBrush(QColor(Config.LUNE if up else Config.ENCRE_ATTENUEE)))

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
            "planets": {n: _planet_name(n) for n in _PLANETS},
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

    def _object_details(self, obj, symbols=True):
        """
        Titre et lignes (libellé, valeur) de la fiche d'un astre. *symbols* :
        symboles suivis de U+FE0E (Qt) ; sans, pour matplotlib.
        """
        sym = SYMBOL if symbols else charts.SYMBOL
        kind = obj["kind"]
        rows = []
        if kind == "star":
            title = obj["name"]
            rows.append((t("detail.type"), t("detail.type_star")))
            consts = STAR_CONSTELLATION.get(obj["name"], [])
            if consts:
                rows.append((t("detail.constellation"),
                             ", ".join(t(f"constellations.{c}") for c in consts)))
            rows.append((t("detail.mag"), _num(obj["mag"], 2)))
        elif kind == "planet":
            title = f"{sym[obj['name']]} {_planet_name(obj['name'])}"
            side = t("coords.east") if obj.get("east") else t("coords.west")
            rows.append((t("detail.type"), t("detail.type_planet")))
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
            (t("detail.alt"), _deg(obj["alt"], 2, signed=True)),
            (t("detail.az"), _deg(obj["az"], 2)),
        ]
        return title, rows

    def _build_detail_dialog(self, obj):
        title, rows = self._object_details(obj)
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

    def _event_card(self, symbole, accent, title, when, pills=(), details=()):
        """Carte d'événement : symbole, titre, pastilles, date ; détails dessous."""
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
        lay.addLayout(top)
        if details:
            lay.addWidget(_label("   ·   ".join(details), "legende", wrap=True))
        self._evt_layout.addWidget(card)

    def _search_start(self, kind):
        self._last_search = kind
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
            self._event_card(SYMBOL["Sun"] if solar else SYMBOL["Moon"],
                             "or" if solar else "lune",
                             t("events.solar_eclipse" if solar else "events.lunar_eclipse"),
                             when, pills, self._eclipse_details(ec))
        self._evt_layout.addStretch()

    def _search_conjunctions_gui(self):
        """Recherche et affiche les conjonctions et oppositions sur 12 mois."""
        dte = self._search_start("conjunctions")
        try:
            conjs = AstroEngine.find_conjunctions(dte, num_days=365)
        except Exception as exc:
            QApplication.restoreOverrideCursor()
            self._search_failed(exc)
            return
        QApplication.restoreOverrideCursor()

        n = len(conjs)
        self._events_header(
            tf("events.conjunctions_title", date=dte.strftime("%d/%m/%Y")),
            tf(_plural_key("events.event_count", n), n=n), t("events.daily_note"))
        if not conjs:
            self._evt_layout.addWidget(_label(t("events.no_conjunction"), "corps",
                                              tone="attenuee"))
        for cj in conjs:
            a, b = cj.get("bodies", ("?", "?"))
            sep = cj.get("separation")
            if cj.get("type") == "opposition":
                symbole = SYMBOL["opposition"]
                title = tf("events.opposition", planet=_planet_name(a, symbol=True))
                detail_key, digits = "events.elongation", 1
            elif b == "Sun":
                symbole = SYMBOL["conjunction"]
                title = tf("events.solar_conjunction", planet=_planet_name(a, symbol=True))
                detail_key, digits = "events.separation", 2
            else:
                symbole = SYMBOL["conjunction"]
                title = tf("events.conjunction_pair", a=_planet_name(a, symbol=True),
                           b=_planet_name(b, symbol=True))
                detail_key, digits = "events.separation", 2
            details = [tf(detail_key, value=_num(sep, digits))] if sep is not None else []
            self._event_card(symbole, "attenuee", title, cj["date"].strftime("%d/%m/%Y"),
                             details=details)
        self._evt_layout.addStretch()
