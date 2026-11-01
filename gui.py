"""
gui.py — Interface graphique de Céleste (PyQt6)
================================================
v3.2 — Interface mise à jour :
  ★ Textes traduits (fr, en, es, de) ; langue et thème appliqués sans redémarrage
  ★ Barre latérale : date TU avec calendrier, lieu, fuseau, favoris, actions
  ★ Éphémérides en cartes : durée du jour, phase, âge et distance de la Lune
  ★ Trajectoires sur fond coloré selon les crépuscules, heure locale en haut
  ★ Carte du ciel : étoiles à l'échelle de leur magnitude, info-bulles, fiches
  ★ Planètes : tableau (élongation comprise) et système solaire en deux vues
  ★ Raccourcis : F5 calculer, Ctrl+L temps réel, Ctrl+E export PDF

Architecture :
  - Barre latérale  : date, lieu, fuseau, favoris, boutons
  - Zone principale : QTabWidget (Éphémérides / Trajectoires / Carte du ciel /
                      Planètes / Événements / Paramètres)
  - Barre d'état    : lieu, astres visibles, heure TU et heure locale

Les calculs viennent de engine.py, les graphiques sont dessinés par charts.py.
"""

import json
import math
import os
import urllib.request
from datetime import datetime, timedelta, timezone

from PyQt6.QtCore import (
    QDate, QDateTime, QLocale, QRegularExpression, Qt, QTime, QTimer,
    QTimeZone, QUrl,
)
from PyQt6.QtGui import (
    QBrush, QColor, QDesktopServices, QFont, QFontDatabase, QIcon, QKeySequence,
    QPainter, QPainterPath, QPalette, QPixmap, QRegularExpressionValidator,
    QShortcut,
)
from PyQt6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QDateTimeEdit,
    QDialog, QDialogButtonBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout,
    QHeaderView, QInputDialog, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QProgressBar, QPushButton, QScrollArea, QSizePolicy, QSlider, QStatusBar,
    QTabWidget, QTableWidget, QTableWidgetItem, QToolButton, QVBoxLayout,
    QWidget,
)

import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

import charts  # noqa: E402
import settings as prefs  # noqa: E402
from config import THEME_NAMES, Config  # noqa: E402
from constellations import STAR_CONSTELLATION  # noqa: E402
from engine import MeeusEngine  # noqa: E402
from i18n import (  # noqa: E402
    available_langs, get_lang, lang_name, resolve_lang, switch_lang, t, tf,
)
from utils import Formatters  # noqa: E402

# ── Constantes ────────────────────────────────────────────────────────────────

APP_VERSION = "3.2"

_FAVORITES_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "favorites.json")

_UTC_OFFSETS = range(-12, 15)
_PLANETS = ("Venus", "Mars", "Jupiter", "Saturn")
_PLANET_SYMBOLS = {"Venus": "♀", "Mars": "♂", "Jupiter": "♃", "Saturn": "♄"}
_QT_DATETIME_FORMAT = "dd/MM/yyyy HH:mm:ss"

# Degrés décimaux, avec un point ou une virgule (49.6333 ou 49,6333)
_COORD_REGEX = r"^\s*[+-]?\d{0,3}(?:[.,]\d{0,8})?\s*$"

# Polices : la première installée de chaque liste. Aucune police emoji ici :
# placée dans la liste, elle dessinerait aussi les chiffres et les espaces
# (Linux, macOS). Qt trouve tout seul une police pour les emoji.
_UI_FONTS = ("Segoe UI", "Inter", "SF Pro Text", "Helvetica Neue", "Noto Sans",
             "Ubuntu", "Cantarell", "DejaVu Sans", "Arial")
_MONO_FONTS = ("Cascadia Mono", "Consolas", "JetBrains Mono", "SF Mono", "Menlo",
               "DejaVu Sans Mono", "Liberation Mono", "Courier New")
_fonts = {"ui": None, "mono": None}


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
    value = float(text.strip().replace(",", "."))
    if math.isnan(value) or not -limit <= value <= limit:
        raise ValueError(text)
    return value


def _fmt_offset(offset):
    return f"UTC{'+' if offset >= 0 else '−'}{abs(offset)}"


def _fmt_lat(lat):
    return f"{abs(lat):.4f}° {t('coords.north') if lat >= 0 else t('coords.south')}"


def _fmt_lon(lon):
    return f"{abs(lon):.4f}° {t('coords.east') if lon >= 0 else t('coords.west')}"


def _clean_place(name):
    """Nom de lieu sans l'épingle 📍 que contient la valeur par défaut."""
    return (name or "").replace("\U0001f4cd", "").strip()


def _planet_name(name, symbol=False):
    text = t(f"planets.{name.lower()}")
    return f"{_PLANET_SYMBOLS[name]}  {text}" if symbol else text


def _plural_key(base, n):
    """Clé « _one » ou « _many » ; en français, 0 est singulier."""
    one = n == 1 or (n == 0 and get_lang() == "fr")
    return f"{base}_{'one' if one else 'many'}"


def _fmt_int(value):
    """Entier avec séparateur de milliers de la langue active."""
    return QLocale(get_lang()).toString(int(round(value)))


def _rgba(color, alpha):
    """Couleur QSS avec transparence (alpha de 0 à 255)."""
    c = QColor(color)
    return f"rgba({c.red()}, {c.green()}, {c.blue()}, {alpha})"


def _repolish(widget):
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def _set_invalid(widget, invalid):
    if bool(widget.property("invalid")) != invalid:
        widget.setProperty("invalid", invalid)
        _repolish(widget)


def _label(text="", name=None, role=None, tone=None, strong=False, wrap=False):
    """QLabel avec nom d'objet et propriétés utilisés par la feuille de style."""
    lbl = QLabel(text)
    if name:
        lbl.setObjectName(name)
    if role:
        lbl.setProperty("role", role)
    if tone:
        lbl.setProperty("tone", tone)
    if strong:
        lbl.setProperty("strong", True)
    if wrap:
        lbl.setWordWrap(True)
    return lbl


def _card(name="card"):
    frame = QFrame()
    frame.setObjectName(name)
    return frame


def _scroll_page():
    """(QScrollArea, page intérieure, layout vertical de la page)."""
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    page = QWidget()
    page.setObjectName("page")
    layout = QVBoxLayout(page)
    layout.setContentsMargins(14, 14, 14, 14)
    layout.setSpacing(12)
    scroll.setWidget(page)
    return scroll, page, layout


def _set_badge(label, text, color):
    """Pastille d'état colorée (texte, couleur du thème)."""
    style = (f"color: {color}; background: {_rgba(color, 34)};"
             f" border: 1px solid {_rgba(color, 110)}; border-radius: 11px;"
             f" padding: 2px 10px; font-weight: 600;")
    if label.text() != text:
        label.setText(text)
    if label.styleSheet() != style:
        label.setStyleSheet(style)


# ── Style de l'application ────────────────────────────────────────────────────

def init_style(app):
    """
    Police, style Fusion, palette et feuille de style de l'application.
    À appeler une fois, après la création de QApplication.
    """
    installed = set(QFontDatabase.families())
    ui = next((f for f in _UI_FONTS if f in installed),
              QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont).family())
    mono = next((f for f in _MONO_FONTS if f in installed),
                QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont).family())
    _fonts.update(ui=ui, mono=mono)
    font = QFont(ui)
    font.setPointSizeF(10)
    app.setFont(font)
    app.setStyle("Fusion")
    charts.configure_fonts((ui,) + charts.PREFERRED_FONTS)
    apply_theme(app)


def apply_theme(app):
    """Palette et feuille de style du thème actif (``Config``)."""
    app.setPalette(_build_palette())
    app.setStyleSheet(build_stylesheet())


def _build_palette():
    C, role = Config, QPalette.ColorRole
    palette = QPalette()
    for r, color in (
        (role.Window, C.BG_MAIN), (role.WindowText, C.FG_WHITE),
        (role.Base, C.BG_CARD), (role.AlternateBase, C.BG_PANEL),
        (role.ToolTipBase, C.BG_CARD), (role.ToolTipText, C.FG_WHITE),
        (role.PlaceholderText, C.FG_MUTED), (role.Text, C.FG_WHITE),
        (role.Button, C.BG_CARD), (role.ButtonText, C.FG_WHITE),
        (role.BrightText, C.FG_RED), (role.Highlight, C.BTN_COLOR),
        (role.HighlightedText, C.BG_MAIN), (role.Link, C.BTN_COLOR),
        (role.Light, C.BG_CARD), (role.Midlight, C.BG_PANEL),
        (role.Mid, C.GRID_COLOR), (role.Dark, C.BG_MAIN), (role.Shadow, "#000000"),
    ):
        palette.setColor(r, QColor(color))
    for r in (role.Text, role.ButtonText, role.WindowText):
        palette.setColor(QPalette.ColorGroup.Disabled, r, QColor(C.FG_MUTED))
    return palette


def build_stylesheet():
    """Feuille de style Qt du thème actif."""
    C = Config
    acc, red, grid = C.BTN_COLOR, C.FG_RED, C.GRID_COLOR
    mono = _fonts["mono"] or "monospace"
    return f"""
QMainWindow, QDialog, QWidget#central, QWidget#sidebar {{ background: {C.BG_MAIN}; }}
QWidget#page {{ background: {C.BG_PANEL}; }}
QWidget#qt_scrollarea_viewport {{ background: transparent; }}
QScrollArea {{ background: transparent; border: none; }}
QLabel {{ background: transparent; }}
QToolTip {{
    background: {C.BG_CARD}; color: {C.FG_WHITE}; border: 1px solid {grid};
    padding: 5px 8px; border-radius: 4px;
}}

QFrame#card, QFrame#eventCard {{
    background: {C.BG_CARD}; border: 1px solid {grid}; border-radius: 10px;
}}
QLabel#appTitle {{ color: {C.FG_MOON}; font-size: 16pt; font-weight: 700; }}
QLabel#appSubtitle, QLabel#hint {{ color: {C.FG_MUTED}; }}
QLabel#section {{ color: {C.FG_MUTED}; font-size: 8pt; font-weight: 700; }}
QLabel#cardTitle {{ font-size: 12.5pt; font-weight: 700; }}
QLabel#cardIcon {{ font-size: 17pt; }}
QLabel#phaseEmoji {{ font-size: 30pt; }}
QLabel#phaseName {{ color: {C.FG_MOON}; font-size: 12pt; font-weight: 600; }}
QLabel#eventTitle {{ font-size: 10.5pt; font-weight: 700; }}
QLabel#emptyState {{ color: {C.FG_MUTED}; font-size: 11pt; padding: 24px 4px; }}
QLabel[role="key"] {{ color: {C.FG_LABEL}; }}
QLabel[role="key"][strong="true"] {{ color: {C.FG_WHITE}; font-weight: 600; }}
QLabel[role="value"] {{ font-family: "{mono}"; color: {C.FG_WHITE}; }}
QLabel[role="value"][strong="true"] {{ font-weight: 700; }}
QLabel[tone="sun"] {{ color: {C.FG_SUN}; }}
QLabel[tone="moon"] {{ color: {C.FG_MOON}; }}
QLabel[tone="muted"] {{ color: {C.FG_MUTED}; }}
QLabel[tone="error"] {{ color: {red}; }}

QPushButton, QToolButton {{
    background: {C.BG_CARD}; border: 1px solid {grid}; border-radius: 7px;
    padding: 6px 12px;
}}
QToolButton {{ padding: 3px; min-width: 26px; min-height: 24px; }}
QPushButton:hover, QToolButton:hover {{ border-color: {acc}; background: {_rgba(acc, 28)}; }}
QPushButton:pressed, QToolButton:pressed {{ background: {_rgba(acc, 64)}; }}
QPushButton:disabled, QToolButton:disabled {{ color: {C.FG_MUTED}; border-color: {_rgba(grid, 120)}; }}
QPushButton#primary {{
    background: {acc}; color: {C.BG_MAIN}; border: 1px solid {acc};
    font-weight: 700; padding: 8px 12px;
}}
QPushButton#primary:hover {{ background: {_rgba(acc, 215)}; }}
QPushButton#primary:pressed {{ background: {_rgba(acc, 170)}; }}
QPushButton#live:checked {{ background: {_rgba(red, 52)}; border-color: {red}; font-weight: 700; }}
QPushButton#live:checked:hover {{ background: {_rgba(red, 80)}; }}

QLineEdit, QComboBox, QDateTimeEdit {{
    background: {C.BG_INPUT}; border: 1px solid {grid}; border-radius: 6px;
    padding: 4px 8px; min-height: 22px;
    selection-background-color: {_rgba(acc, 110)}; selection-color: {C.FG_WHITE};
}}
QLineEdit:focus, QComboBox:focus, QDateTimeEdit:focus {{ border-color: {acc}; }}
QLineEdit[invalid="true"] {{ border-color: {red}; background: {_rgba(red, 26)}; }}
QDateTimeEdit[readOnly="true"] {{ color: {C.FG_LABEL}; }}
QComboBox QAbstractItemView {{
    background: {C.BG_CARD}; border: 1px solid {grid};
    selection-background-color: {_rgba(acc, 70)}; selection-color: {C.FG_WHITE};
}}

QTabWidget::pane {{
    border: 1px solid {grid}; border-radius: 8px; background: {C.BG_PANEL}; top: -1px;
}}
QTabBar::tab {{
    background: transparent; color: {C.FG_LABEL}; padding: 8px 14px;
    margin-right: 2px; border: none; border-bottom: 2px solid transparent;
}}
QTabBar::tab:selected {{ color: {C.FG_WHITE}; border-bottom: 2px solid {acc}; }}
QTabBar::tab:hover:!selected {{ color: {C.FG_WHITE}; }}

QTableWidget {{
    background: {C.BG_CARD}; border: 1px solid {grid}; border-radius: 8px;
    gridline-color: {_rgba(grid, 110)};
}}
QTableWidget::item {{ padding: 3px 8px; }}
QHeaderView::section {{
    background: {C.BG_PANEL}; color: {C.FG_LABEL}; border: none;
    border-bottom: 1px solid {grid}; padding: 6px 8px; font-weight: 600;
}}
QTableCornerButton::section {{ background: {C.BG_PANEL}; border: none; }}

QProgressBar {{
    background: {C.BG_INPUT}; border: 1px solid {grid}; border-radius: 4px;
    max-height: 8px;
}}
QProgressBar::chunk {{ background: {C.FG_MOON}; border-radius: 3px; }}

QSlider::groove:horizontal {{ background: {grid}; height: 4px; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {acc}; border-radius: 2px; }}
QSlider::handle:horizontal {{
    background: {acc}; width: 14px; height: 14px; margin: -5px 0; border-radius: 7px;
}}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {grid}; border-radius: 3px; min-height: 28px; }}
QScrollBar::handle:horizontal {{ background: {grid}; border-radius: 3px; min-width: 28px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QStatusBar {{ background: {C.BG_MAIN}; color: {C.FG_LABEL}; border-top: 1px solid {grid}; }}
QStatusBar::item {{ border: none; }}
QStatusBar QLabel {{ color: {C.FG_LABEL}; padding: 0 6px; }}
QStatusBar QLabel#liveIndicator {{ color: {red}; font-weight: 700; }}

QCheckBox {{ spacing: 8px; }}
QCalendarWidget QWidget#qt_calendar_navigationbar {{ background: {C.BG_PANEL}; }}
QCalendarWidget QToolButton {{ background: transparent; border: none; padding: 4px 8px; }}
QCalendarWidget QAbstractItemView {{
    background: {C.BG_CARD}; selection-background-color: {acc};
    selection-color: {C.BG_MAIN};
}}
QMenu {{ background: {C.BG_CARD}; border: 1px solid {grid}; }}
QMenu::item:selected {{ background: {_rgba(acc, 70)}; }}
"""


def app_icon():
    """Icône de la fenêtre : un croissant de lune sur un ciel de nuit."""
    pix = QPixmap(64, 64)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#1B1B25"))
    painter.drawRoundedRect(0, 0, 64, 64, 14, 14)
    moon, shadow = QPainterPath(), QPainterPath()
    moon.addEllipse(12, 12, 40, 40)
    shadow.addEllipse(24, 5, 40, 40)
    painter.setBrush(QColor("#F9E2AF"))
    painter.drawPath(moon.subtracted(shadow))
    painter.setBrush(QColor("#89B4FA"))
    for x, y, r in ((47, 41, 3), (40, 52, 2), (54, 30, 2)):
        painter.drawEllipse(x - r, y - r, 2 * r, 2 * r)
    painter.end()
    return QIcon(pix)


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
        self.resize(1360, 840)
        self.setMinimumSize(1080, 680)
        self.setWindowIcon(app_icon())

        # État
        self.live_mode           = False
        self.utc_offset          = int(prefs.get("default_utc") or 0)
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
        """Construit (ou reconstruit) toute la fenêtre dans la langue active."""
        self.setWindowTitle(t("app.title"))
        central = QWidget()
        central.setObjectName("central")
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_sidebar())

        main = QWidget()
        main_l = QVBoxLayout(main)
        main_l.setContentsMargins(2, 10, 12, 8)
        self.tabs = QTabWidget()
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
        self.btn_calc.setFocus()

    # ── Barre latérale ────────────────────────────────────────────────────────

    def _build_sidebar(self):
        side = QWidget()
        side.setObjectName("sidebar")
        side.setFixedWidth(300)
        lay = QVBoxLayout(side)
        lay.setContentsMargins(14, 14, 10, 12)
        lay.setSpacing(10)

        # En-tête
        head = QHBoxLayout()
        head.setSpacing(10)
        icon = QLabel()
        icon.setPixmap(app_icon().pixmap(40, 40))
        head.addWidget(icon)
        titles = QVBoxLayout()
        titles.setSpacing(0)
        title = _label(t("app.header"), name="appTitle")
        font = title.font()
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2.0)
        title.setFont(font)
        titles.addWidget(title)
        titles.addWidget(_label(t("app.subtitle"), name="appSubtitle"))
        head.addLayout(titles, stretch=1)
        lay.addLayout(head)

        # Date et heure
        card = _card()
        card_l = QVBoxLayout(card)
        card_l.setContentsMargins(12, 10, 12, 12)
        card_l.setSpacing(6)
        card_l.addWidget(_label(t("side.datetime").upper(), name="section"))
        row = QHBoxLayout()
        row.setSpacing(6)
        self.dt_edit = QDateTimeEdit()
        if hasattr(self.dt_edit, "setTimeZone"):
            self.dt_edit.setTimeZone(_utc_zone())
        else:
            self.dt_edit.setTimeSpec(Qt.TimeSpec.UTC)
        self.dt_edit.setDisplayFormat(_QT_DATETIME_FORMAT)
        self.dt_edit.setCalendarPopup(True)
        self.dt_edit.setToolTip(t("side.datetime_tip"))
        self._set_datetime(_utc_now())
        self.dt_edit.dateTimeChanged.connect(lambda _dt: self._schedule_recalc())
        row.addWidget(self.dt_edit, stretch=1)
        self.btn_now = QToolButton()
        self.btn_now.setText("🕒")
        self.btn_now.setToolTip(t("side.now_tip"))
        self.btn_now.clicked.connect(self.set_now)
        row.addWidget(self.btn_now)
        card_l.addLayout(row)
        lay.addWidget(card)

        # Lieu
        card = _card()
        grid = QGridLayout(card)
        grid.setContentsMargins(12, 10, 12, 12)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(7)
        grid.addWidget(_label(t("side.place").upper(), name="section"), 0, 0, 1, 3)

        validator = QRegularExpressionValidator(QRegularExpression(_COORD_REGEX))
        self.entry_lat = QLineEdit(f"{_pref_float('default_lat', 49.6333):.4f}")
        self.entry_lon = QLineEdit(f"{_pref_float('default_lon', -1.6167):.4f}")
        for row_i, (edit, key) in enumerate(((self.entry_lat, "latitude"),
                                             (self.entry_lon, "longitude")), start=1):
            edit.setValidator(validator)
            edit.setToolTip(t(f"side.{key}_tip"))
            edit.returnPressed.connect(self.calculate)
            edit.textEdited.connect(self._on_coords_edited)
            grid.addWidget(_label(t(f"side.{key}"), role="key"), row_i, 0)
            grid.addWidget(edit, row_i, 1, 1, 1 if key == "longitude" else 2)
        btn_geo = QToolButton()
        btn_geo.setText("📍")
        btn_geo.setToolTip(t("side.geoloc_tip"))
        btn_geo.clicked.connect(self.geolocate)
        grid.addWidget(btn_geo, 2, 2)

        grid.addWidget(_label(t("side.timezone"), role="key"), 3, 0)
        self.offset_menu = QComboBox()
        for offset in _UTC_OFFSETS:
            self.offset_menu.addItem(_fmt_offset(offset), offset)
        self.offset_menu.setCurrentIndex(self.offset_menu.findData(self.utc_offset))
        self.offset_menu.setToolTip(t("side.timezone_tip"))
        self.offset_menu.currentIndexChanged.connect(self._on_offset_change)
        grid.addWidget(self.offset_menu, 3, 1, 1, 2)

        grid.setRowMinimumHeight(4, 4)
        grid.addWidget(_label(t("side.favorites").upper(), name="section"), 5, 0, 1, 3)
        fav_row = QHBoxLayout()
        fav_row.setSpacing(4)
        self.combo_fav = QComboBox()
        self.combo_fav.setPlaceholderText(t("side.favorites_placeholder"))
        self.combo_fav.setSizePolicy(QSizePolicy.Policy.Expanding,
                                     QSizePolicy.Policy.Fixed)
        self.combo_fav.setMinimumContentsLength(8)
        self._refresh_favorites_combo()
        self.combo_fav.activated.connect(self._apply_favorite)
        fav_row.addWidget(self.combo_fav, stretch=1)
        for text, tip, slot in (("💾", "side.fav_save_tip", self.save_location),
                                ("🗑", "side.fav_delete_tip", self.delete_location)):
            btn = QToolButton()
            btn.setText(text)
            btn.setToolTip(t(tip))
            btn.clicked.connect(slot)
            fav_row.addWidget(btn)
        grid.addLayout(fav_row, 6, 0, 1, 3)
        grid.setColumnStretch(1, 1)
        lay.addWidget(card)

        # Actions
        self.btn_calc = QPushButton(f"⚡  {t('side.calculate')}")
        self.btn_calc.setObjectName("primary")
        self.btn_calc.setToolTip(tf("side.calculate_tip", key="F5"))
        self.btn_calc.clicked.connect(self.calculate)
        lay.addWidget(self.btn_calc)

        self.btn_live = QPushButton()
        self.btn_live.setObjectName("live")
        self.btn_live.setCheckable(True)
        self.btn_live.setToolTip(tf("side.live_tip", key="Ctrl+L"))
        self.btn_live.toggled.connect(self.toggle_live)
        lay.addWidget(self.btn_live)

        btn_pdf = QPushButton(f"📄  {t('side.export')}")
        btn_pdf.setToolTip(tf("side.export_tip", key="Ctrl+E"))
        btn_pdf.clicked.connect(self.export_pdf)
        lay.addWidget(btn_pdf)

        lay.addStretch()
        lay.addWidget(_label(f"Céleste v{APP_VERSION}", name="hint"))
        return side

    # ── Onglet 1 : éphémérides ────────────────────────────────────────────────

    def _build_ephemeris_tab(self):
        scroll, _page, lay = _scroll_page()
        row = QHBoxLayout()
        row.setSpacing(12)

        # Soleil
        card, body, self._lbl_sun_state = self._body_card("☀️", t("sun.title"))
        self.sun_labels = {}
        r = self._section_rows(body, 0, t("sun.section_position"), [
            ("ra", "sun.ra"), ("dec", "sun.dec"), ("alt", "sun.alt"),
            ("az", "sun.az"), ("eot", "sun.eot"), ("dist", "sun.dist"),
        ], self.sun_labels, tone="sun")
        self._sun_events_title = _label("", name="section")
        self._section_rows(body, r, self._sun_events_title, [
            ("dawn_astro", "sun.dawn_astro"), ("dawn_naut", "sun.dawn_naut"),
            ("dawn_civ", "sun.dawn_civil"), ("rise", "sun.rise", True),
            ("transit", "sun.transit"), ("set", "sun.set", True),
            ("dusk_civ", "sun.dusk_civil"), ("dusk_naut", "sun.dusk_naut"),
            ("dusk_astro", "sun.dusk_astro"), ("day_length", "sun.day_length"),
        ], self.sun_labels)
        row.addWidget(card, stretch=1)

        # Lune
        card, body, self._lbl_moon_state = self._body_card("🌙", t("moon.title"))
        self.moon_labels = {}
        r = self._section_rows(body, 0, t("moon.section_position"), [
            ("ra", "moon.ra"), ("dec", "moon.dec"), ("alt", "moon.alt"),
            ("az", "moon.az"), ("dist", "moon.dist"),
        ], self.moon_labels, tone="moon")

        body.setRowMinimumHeight(r, 14)
        body.addWidget(_label(t("moon.section_phase").upper(), name="section"), r + 1, 0, 1, 2)
        r += 1
        phase_row = QHBoxLayout()
        phase_row.setSpacing(12)
        self._lbl_phase_emoji = _label("🌑", name="phaseEmoji")
        phase_row.addWidget(self._lbl_phase_emoji)
        phase_text = QVBoxLayout()
        phase_text.setSpacing(4)
        self._lbl_phase_name = _label("—", name="phaseName")
        phase_text.addWidget(self._lbl_phase_name)
        self._illum_bar = QProgressBar()
        self._illum_bar.setRange(0, 1000)
        self._illum_bar.setTextVisible(False)
        phase_text.addWidget(self._illum_bar)
        phase_row.addLayout(phase_text, stretch=1)
        body.addLayout(phase_row, r + 1, 0, 1, 2)
        r = self._section_rows(body, r + 2, None, [
            ("illum", "moon.illum"), ("age", "moon.age"),
        ], self.moon_labels, tone="moon")

        self._moon_events_title = _label("", name="section")
        self._section_rows(body, r, self._moon_events_title, [
            ("rise", "moon.rise", True), ("transit", "moon.transit"),
            ("set", "moon.set", True),
        ], self.moon_labels)
        row.addWidget(card, stretch=1)

        lay.addLayout(row)
        lay.addStretch()
        self.tabs.addTab(scroll, t("tabs.ephemeris"))

    def _body_card(self, icon, title):
        """Carte d'un astre : (carte, grille des données, pastille d'état)."""
        card = _card()
        outer = QVBoxLayout(card)
        outer.setContentsMargins(16, 12, 16, 14)
        outer.setSpacing(10)
        head = QHBoxLayout()
        head.addWidget(_label(icon, name="cardIcon"))
        head.addWidget(_label(title, name="cardTitle"))
        head.addStretch()
        badge = QLabel()
        head.addWidget(badge)
        outer.addLayout(head)
        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(5)
        grid.setColumnStretch(0, 1)
        outer.addLayout(grid)
        outer.addStretch()
        return card, grid, badge

    @staticmethod
    def _section_rows(grid, row, title, fields, labels, tone=None):
        """
        Ajoute un intertitre (texte, QLabel ou None) puis une ligne
        « libellé … valeur » par champ ; retourne la ligne suivante.
        Champ : (clé, clé de traduction[, mise en avant]).
        """
        if title is not None:
            if isinstance(title, str):
                title = _label(title.upper(), name="section")
            if row:
                grid.setRowMinimumHeight(row, 14)
                row += 1
            grid.addWidget(title, row, 0, 1, 2)
            row += 1
        for key, text_key, *opt in fields:
            strong = bool(opt and opt[0])
            grid.addWidget(_label(t(text_key), role="key", strong=strong), row, 0)
            value = _label("—", role="value", tone=tone, strong=strong)
            value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            grid.addWidget(value, row, 1)
            labels[key] = value
            row += 1
        return row

    # ── Onglets 2 et 3 : graphiques ───────────────────────────────────────────

    def _chart_page(self, name, toolbar=None, hint=None):
        """Page d'onglet contenant un graphique matplotlib."""
        page = QWidget()
        page.setObjectName("page")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)
        if toolbar is not None:
            lay.addLayout(toolbar)
        figure = Figure(facecolor=Config.BG_PANEL)
        canvas = FigureCanvasQTAgg(figure)
        canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        lay.addWidget(canvas, stretch=1)
        if hint:
            lay.addWidget(_label(hint, name="hint"))
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
        bar.setSpacing(10)
        bar.addWidget(_label(t("skymap.mag_limit"), role="key"))
        self._mag_slider = QSlider(Qt.Orientation.Horizontal)
        self._mag_slider.setRange(10, 70)          # magnitude × 10
        self._mag_slider.setFixedWidth(220)
        self._mag_slider.setValue(int(round(self._mag_limit() * 10)))
        self._mag_slider.setToolTip(t("skymap.mag_tip"))
        self._mag_lbl = _label(f"{self._mag_limit():.1f}", role="value")
        self._mag_lbl.setMinimumWidth(30)
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
        lay.setContentsMargins(12, 12, 12, 8)
        lay.setSpacing(8)

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
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(len(columns) - 1, QHeaderView.ResizeMode.ResizeToContents)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        table.verticalHeader().setDefaultSectionSize(32)
        mono = QFont(_fonts["mono"] or "monospace")
        self._planet_items = {}
        for r, name in enumerate(_PLANETS):
            items = {}
            for c, col in enumerate(columns):
                item = QTableWidgetItem("—")
                item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                if col == "col_planet":
                    item.setText(_planet_name(name, symbol=True))
                    item.setForeground(QBrush(QColor(Config.planet_color(name))))
                    bold = item.font()
                    bold.setBold(True)
                    item.setFont(bold)
                elif col != "col_state":
                    item.setFont(mono)
                table.setItem(r, c, item)
                items[col] = item
            self._planet_items[name] = items
        table.setFixedHeight(32 * len(_PLANETS) + table.horizontalHeader().sizeHint().height() + 4)
        self.planet_table = table
        lay.addWidget(table)

        self.fig_orrery = Figure(facecolor=Config.BG_PANEL)
        self.canvas_orrery = FigureCanvasQTAgg(self.fig_orrery)
        lay.addWidget(self.canvas_orrery, stretch=1)
        self._chart_tabs[page] = "orrery"
        self.tabs.addTab(page, t("tabs.planets"))

    # ── Onglet 5 : événements ─────────────────────────────────────────────────

    def _build_events_tab(self):
        page = QWidget()
        page.setObjectName("page")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(14, 14, 14, 8)
        lay.setSpacing(10)

        bar = QHBoxLayout()
        btn_ecl = QPushButton(f"🌘  {t('events.search_eclipses')}")
        btn_ecl.clicked.connect(self._search_eclipses_gui)
        btn_conj = QPushButton(f"🪐  {t('events.search_conjunctions')}")
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
        self._evt_layout.setContentsMargins(0, 0, 4, 0)
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
            card.setMaximumWidth(760)
            grid = QGridLayout(card)
            grid.setContentsMargins(16, 12, 16, 14)
            grid.setHorizontalSpacing(14)
            grid.setVerticalSpacing(8)
            grid.setColumnMinimumWidth(0, 220)
            grid.setColumnStretch(1, 1)
            grid.addWidget(_label(title.upper(), name="section"), 0, 0, 1, 2)
            lay.addWidget(card)
            return grid

        def row(grid, text, widget):
            r = grid.rowCount()
            grid.addWidget(_label(text, role="key"), r, 0)
            if isinstance(widget, QWidget):
                grid.addWidget(widget, r, 1)
            else:
                grid.addLayout(widget, r, 1)

        # Apparence
        grid = section(t("settings.appearance"))
        self._theme_combo = QComboBox()
        for key in THEME_NAMES:
            self._theme_combo.addItem(t(f"settings.theme_{key}"), key)
        self._theme_combo.setCurrentIndex(self._theme_combo.findData(Config.THEME))
        self._theme_combo.currentIndexChanged.connect(self._on_theme_change)
        row(grid, t("settings.theme"), self._theme_combo)

        self._timefmt_combo = QComboBox()
        for key in ("24h", "12h"):
            self._timefmt_combo.addItem(t(f"settings.time_{key}"), key)
        self._timefmt_combo.setCurrentIndex(
            max(0, self._timefmt_combo.findData(prefs.get("time_format") or "24h")))
        self._timefmt_combo.currentIndexChanged.connect(self._on_timefmt_change)
        row(grid, t("settings.time_format"), self._timefmt_combo)

        # Langue
        grid = section(t("settings.language_section"))
        self._lang_combo = QComboBox()
        auto_lang = resolve_lang("auto", QLocale.system().name())
        self._lang_combo.addItem(
            f"{t('settings.lang_auto')} ({lang_name(auto_lang)})", "auto")
        for code in available_langs():
            self._lang_combo.addItem(lang_name(code), code)
        self._lang_combo.setCurrentIndex(
            max(0, self._lang_combo.findData(prefs.get("lang") or "auto")))
        self._lang_combo.currentIndexChanged.connect(self._on_lang_change)
        row(grid, t("settings.language"), self._lang_combo)

        # Lieu par défaut
        grid = section(t("settings.default_place_section"))
        self._place_entry = QLineEdit(_clean_place(prefs.get("default_place")))
        row(grid, t("settings.default_place_name"), self._place_entry)
        self._default_coords_lbl = _label("", role="value")
        row(grid, t("settings.default_place_coords"), self._default_coords_lbl)
        self._update_default_place_label()
        btn_use = QPushButton(f"📍  {t('settings.use_current')}")
        btn_use.setToolTip(t("settings.use_current_tip"))
        btn_use.clicked.connect(self._save_default_place)
        buttons = QHBoxLayout()
        buttons.addWidget(btn_use)
        buttons.addStretch()
        row(grid, "", buttons)
        self._autogeo_cb = QCheckBox(t("settings.auto_geoloc"))
        self._autogeo_cb.setChecked(bool(prefs.get("auto_geoloc")))
        self._autogeo_cb.toggled.connect(lambda v: prefs.set("auto_geoloc", bool(v)))
        grid.addWidget(self._autogeo_cb, grid.rowCount(), 0, 1, 2)

        # Temps réel
        grid = section(t("settings.live_section"))
        iv = QHBoxLayout()
        self._iv_slider = QSlider(Qt.Orientation.Horizontal)
        self._iv_slider.setRange(1, 20)            # pas de 500 ms
        self._iv_slider.setValue(int((prefs.get("live_interval") or 2000) / 500))
        self._iv_lbl = _label("", role="value")
        self._iv_lbl.setMinimumWidth(70)
        self._iv_slider.valueChanged.connect(self._on_interval_changed)
        iv.addWidget(self._iv_slider, stretch=1)
        iv.addWidget(self._iv_lbl)
        self._iv_lbl.setText(tf("units.ms", value=self._iv_slider.value() * 500))
        row(grid, t("settings.live_interval"), iv)

        # Réinitialisation et à propos
        grid = section(t("settings.reset_section"))
        btn_reset = QPushButton(f"🔄  {t('settings.reset_btn')}")
        btn_reset.clicked.connect(self._reset_settings)
        buttons = QHBoxLayout()
        buttons.addWidget(btn_reset)
        buttons.addStretch()
        grid.addLayout(buttons, grid.rowCount(), 0, 1, 2)
        grid.addWidget(_label(tf("settings.about", version=APP_VERSION),
                              name="hint", wrap=True), grid.rowCount(), 0, 1, 2)

        lay.addStretch()
        self.tabs.addTab(scroll, t("tabs.settings"))

    # ── Barre d'état ──────────────────────────────────────────────────────────

    def _build_status_bar(self):
        bar = QStatusBar()
        self.setStatusBar(bar)
        self._lbl_pos = QLabel("📍 —")
        self._lbl_stars = QLabel("")
        self._lbl_live = _label(t("status.live_on"), name="liveIndicator")
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
            "lat": self.entry_lat.text(),
            "lon": self.entry_lon.text(),
            "tab": self.tabs.currentIndex(),
            "fav": self.combo_fav.currentIndex(),
        }

    def _rebuild(self, keep_place=True):
        """Reconstruit la fenêtre (nouvelle langue ou nouveau thème) en gardant
        la date, l'onglet, le mode temps réel et, si *keep_place*, le lieu."""
        state = self._snapshot()
        apply_theme(QApplication.instance())
        self._build_ui()
        self._set_datetime(state["dte"])
        if keep_place:
            self.entry_lat.setText(state["lat"])
            self.entry_lon.setText(state["lon"])
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

    def _on_theme_change(self, index):
        key = self._theme_combo.itemData(index)
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
        self._mag_lbl.setText(f"{mag:.1f}")
        self._schedule_recalc(120)

    def _on_interval_changed(self, value):
        interval = value * 500
        prefs.set("live_interval", interval)
        self._iv_lbl.setText(tf("units.ms", value=interval))
        if self.live_mode:
            self._live_timer.setInterval(interval)

    def _update_default_place_label(self):
        lat = _pref_float("default_lat", 0.0)
        lon = _pref_float("default_lon", 0.0)
        utc = int(prefs.get("default_utc") or 0)
        self._default_coords_lbl.setText(
            f"{_fmt_lat(lat)}, {_fmt_lon(lon)} · {_fmt_offset(utc)}")

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
        prefs.set("default_utc", self.utc_offset)
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
        self.utc_offset = int(prefs.get("default_utc") or 0)
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
        self.entry_lat.setText(f"{float(loc['lat']):.4f}")
        self.entry_lon.setText(f"{float(loc['lon']):.4f}")
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
        self.favorites[name] = {"lat": round(lat, 4), "lon": round(lon, 4)}
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

    def _on_offset_change(self, index):
        self.utc_offset = int(self.offset_menu.itemData(index) or 0)
        self.calculate()

    def _fmt_clock(self, dt):
        if prefs.get("time_format") == "12h":
            return dt.strftime("%I:%M %p").lstrip("0")
        return dt.strftime("%H:%M")

    def _format_event(self, dt):
        if dt is None:
            return "--:--"
        return self._fmt_clock(dt + timedelta(hours=self.utc_offset))

    # ──────────────────────────────────────────────────────────────────────────
    # GÉOLOCALISATION / TEMPS RÉEL
    # ──────────────────────────────────────────────────────────────────────────

    def geolocate(self):
        url = ("http://ip-api.com/json/"
               "?fields=status,message,country,city,lat,lon,offset")
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
        self.entry_lat.setText(f"{float(data['lat']):.4f}")
        self.entry_lon.setText(f"{float(data['lon']):.4f}")
        offset = data.get("offset")
        if isinstance(offset, int) and offset % 3600 == 0:
            idx = self.offset_menu.findData(offset // 3600)
            if idx >= 0:
                self.offset_menu.blockSignals(True)
                self.offset_menu.setCurrentIndex(idx)
                self.offset_menu.blockSignals(False)
                self.utc_offset = offset // 3600
        self.location_name = data.get("city") or ""
        self.combo_fav.setCurrentIndex(-1)
        self.calculate()
        self.statusBar().showMessage(
            tf("errors.geoloc_success", city=data.get("city", "?"),
               country=data.get("country", "?")), 8000)

    def toggle_live(self, checked):
        self.live_mode = bool(checked)
        self._apply_live_ui()
        if self.live_mode:
            self._live_timer.start(int(prefs.get("live_interval") or 2000))
            self._live_tick()
        else:
            self._live_timer.stop()

    def _apply_live_ui(self):
        on = self.live_mode
        self.btn_live.setText(f"⏸  {t('side.pause')}" if on else f"⏱  {t('side.live')}")
        self.dt_edit.setReadOnly(on)
        _repolish(self.dt_edit)
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
        """Signale en rouge les coordonnées invalides ; True si tout est valide."""
        ok = True
        for edit, limit in ((self.entry_lat, 90.0), (self.entry_lon, 180.0)):
            try:
                _parse_coord(edit.text(), limit)
                _set_invalid(edit, False)
            except ValueError:
                _set_invalid(edit, True)
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

        jd = MeeusEngine.julian_day(dte)
        tc = MeeusEngine.julian_century_j2000(dte)

        s_l, r_sun  = MeeusEngine.sun_position(tc)
        s_ra, s_dec = MeeusEngine.ecliptic_to_equatorial(s_l, 0, tc)
        s_alt, s_az = MeeusEngine.equatorial_to_horizontal(jd, lat, lon, s_ra, s_dec)

        m_l, m_b, m_p = MeeusEngine.moon_position(tc)
        m_ra, m_dec   = MeeusEngine.ecliptic_to_equatorial(m_l, m_b, tc)
        m_alt, m_az   = MeeusEngine.equatorial_to_horizontal(jd, lat, lon, m_ra, m_dec)
        m_alt_c       = MeeusEngine.elevation_correction(m_alt, m_p)

        phase = MeeusEngine.mod360(m_l - s_l)
        illum = (1 - math.cos(math.radians(phase))) / 2.0 * 100.0

        self.sun_data  = {"name": "Sun", "ra": s_ra, "dec": s_dec, "alt": s_alt,
                          "az": s_az, "dist": r_sun,
                          "eot": MeeusEngine.equation_of_time(tc)}
        self.moon_data = {"name": "Moon", "ra": m_ra, "dec": m_dec, "alt": m_alt_c,
                          "az": m_az, "illum": illum, "phase": phase,
                          "dist": 6378.14 / math.sin(math.radians(m_p)),
                          "age": phase / 360.0 * 29.530588}

        # Événements du jour et courbes 24 h : seulement si la date ou le lieu change
        key = f"{dte:%Y-%m-%d}_{lat:.4f}_{lon:.4f}"
        if key != self.last_cache_key:
            self.sun_events  = MeeusEngine.find_events(dte, lat, lon, "sun")
            self.moon_events = MeeusEngine.find_events(dte, lat, lon, "moon")
            self.hours, self.sun_altitudes, self.moon_altitudes = \
                charts.sample_day(dte, lat, lon)
            self.last_cache_key = key

        self.planets = []
        for name in _PLANETS:
            ra, dec, dist = MeeusEngine.planet_position(tc, name)
            alt, az = MeeusEngine.equatorial_to_horizontal(jd, lat, lon, ra, dec)
            self.planets.append({
                "name": name, "ra": ra, "dec": dec, "dist": dist, "alt": alt, "az": az,
                "elong": MeeusEngine.angular_separation(ra, dec, s_ra, s_dec),
                "east": (ra - s_ra) % 24 < 12,
            })

        self._sky_scene = charts.sky_scene(jd, lat, lon, self._mag_limit(),
                                           self.sun_data, self.moon_data, self.planets)
        self._sky_objects = charts.visible_objects(self._sky_scene)
        self.visible_stars = [s["name"] for s in self._sky_scene["stars"]]
        self.visible_planets_map = [p["name"] for p in self.planets if p["alt"] > 0]

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
        return tf("common.events_title", offset=_fmt_offset(self.utc_offset)).upper()

    def _day_length(self):
        rise, sunset = self.sun_events.get("rise"), self.sun_events.get("set")
        if rise is None or sunset is None:
            return "—"
        minutes = round((sunset - rise).total_seconds() / 60) % 1440
        return tf("units.duration", h=minutes // 60, m=f"{minutes % 60:02d}")

    def _update_sun_card(self):
        sd, lb, ev = self.sun_data, self.sun_labels, self.sun_events
        lb["ra"].setText(f"{Formatters.hms(sd['ra'])}  ({sd['ra']:.2f}h)")
        lb["dec"].setText(f"{Formatters.dms(sd['dec'])}  ({sd['dec']:+.2f}°)")
        lb["alt"].setText(f"{sd['alt']:+.2f}°")
        lb["az"].setText(f"{sd['az']:.2f}°")
        lb["eot"].setText(tf("units.minutes", value=f"{sd['eot']:+.1f}"))
        lb["dist"].setText(tf("units.au", value=f"{sd['dist']:.4f}"))
        for key in ("dawn_astro", "dawn_naut", "dawn_civ", "rise", "transit",
                    "set", "dusk_civ", "dusk_naut", "dusk_astro"):
            lb[key].setText(self._format_event(ev.get(key)))
        lb["day_length"].setText(self._day_length())
        self._sun_events_title.setText(self._events_title())

        phase = charts.day_phase(sd["alt"])
        color = {"day": Config.FG_GREEN, "civil": Config.FG_SUN,
                 "nautical": Config.BTN_COLOR, "astronomical": Config.FG_PURPLE,
                 "night": Config.FG_RED}[phase]
        _set_badge(self._lbl_sun_state, t(f"sun.state_{phase}"), color)

    def _update_moon_card(self):
        md, lb, ev = self.moon_data, self.moon_labels, self.moon_events
        lb["ra"].setText(f"{Formatters.hms(md['ra'])}  ({md['ra']:.2f}h)")
        lb["dec"].setText(f"{Formatters.dms(md['dec'])}  ({md['dec']:+.2f}°)")
        lb["alt"].setText(f"{md['alt']:+.2f}°")
        lb["az"].setText(f"{md['az']:.2f}°")
        lb["dist"].setText(tf("units.km", value=_fmt_int(md["dist"])))
        key, emoji, _english = Formatters.PHASES[Formatters.phase_index(md["phase"])]
        self._lbl_phase_emoji.setText(emoji)
        self._lbl_phase_name.setText(t(f"phases.{key}"))
        self._illum_bar.setValue(int(round(md["illum"] * 10)))
        lb["illum"].setText(f"{md['illum']:.1f} %")
        lb["age"].setText(tf("units.days", value=f"{md['age']:.1f}"))
        for key in ("rise", "transit", "set"):
            lb[key].setText(self._format_event(ev.get(key)))
        self._moon_events_title.setText(self._events_title())
        if md["alt"] > 0:
            _set_badge(self._lbl_moon_state, t("common.above_horizon"), Config.FG_GREEN)
        else:
            _set_badge(self._lbl_moon_state, t("common.below_horizon"), Config.FG_RED)

    def _update_planet_table(self):
        for p in self.planets:
            items = self._planet_items[p["name"]]
            side = t("coords.east") if p["east"] else t("coords.west")
            items["col_ra"].setText(Formatters.hms(p["ra"]))
            items["col_dec"].setText(Formatters.dms(p["dec"]))
            items["col_alt"].setText(f"{p['alt']:+.2f}°")
            items["col_az"].setText(f"{p['az']:.2f}°")
            items["col_dist"].setText(tf("units.au", value=f"{p['dist']:.4f}"))
            items["col_elong"].setText(f"{p['elong']:.1f}° {side}")
            up = p["alt"] > 0
            items["col_state"].setText(t("common.visible" if up else "common.below_horizon"))
            items["col_state"].setForeground(
                QBrush(QColor(Config.FG_GREEN if up else Config.FG_MUTED)))

    def _update_status(self):
        if self._lat is None:
            return
        coords = f"{_fmt_lat(self._lat)}, {_fmt_lon(self._lon)}"
        self._lbl_pos.setText(f"📍 {self.location_name} · {coords}"
                              if self.location_name else f"📍 {coords}")
        n, n_pl = len(self.visible_stars), len(self.visible_planets_map)
        self._lbl_stars.setText(
            f"★ {tf(_plural_key('status.stars', n), n=n)}   "
            f"🪐 {tf(_plural_key('status.planets', n_pl), n=n_pl)}")
        local = self._dte + timedelta(hours=self.utc_offset)
        self._lbl_time.setText(
            f"{tf('status.ut', time=self._dte.strftime('%d/%m/%Y %H:%M:%S'))}   ·   "
            f"{tf('status.local', time=self._fmt_clock(local), offset=_fmt_offset(self.utc_offset))}")

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
        dte = self._dte
        labels = {
            "title": tf("chart.trajectory_title", date=dte.strftime("%d/%m/%Y")),
            "xlabel": t("chart.hour_ut"),
            "ylabel": t("chart.altitude"),
            "local_axis": tf("chart.hour_local", offset=_fmt_offset(self.utc_offset)),
            "sun": t("chart.sun"),
            "moon": t("chart.moon"),
        }
        labels.update({p: t(f"chart.phase_{p}") for p in charts.DAY_PHASES})
        now_h = dte.hour + dte.minute / 60 + dte.second / 3600
        self._traj_ax, tip = charts.draw_trajectory(
            self.fig_traj, self.hours, self.sun_altitudes, self.moon_altitudes,
            now_h, self.sun_data["alt"], self.moon_data["alt"], labels,
            self.utc_offset)
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
        tc = MeeusEngine.julian_century_j2000(self._dte)
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
        hour = self.hours[i]
        base = datetime(2000, 1, 1)
        ut = self._fmt_clock(base + timedelta(hours=hour))
        first = f"{ut} {t('chart.ut')}"
        if self.utc_offset:
            local = self._fmt_clock(base + timedelta(hours=hour + self.utc_offset))
            first += f"  ·  {local} {t('chart.local')}"
        tip.set_text(f"{first}\n"
                     f"☀ {t('chart.sun')}  {self.sun_altitudes[i]:+.1f}°\n"
                     f"☾ {t('chart.moon')}  {self.moon_altitudes[i]:+.1f}°")
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
        title, _rows = self._object_details(obj)
        line = (f"{t('detail.alt')} {obj['alt']:.1f}°  ·  "
                f"{t('detail.az')} {obj['az']:.1f}°")
        if obj["kind"] == "star":
            line += f"  ·  {t('detail.mag')} {obj['mag']:.2f}"
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

    def _object_details(self, obj):
        """Titre et lignes (libellé, valeur) de la fiche d'un astre."""
        kind = obj["kind"]
        rows = []
        if kind == "star":
            title = obj["name"]
            rows.append((t("detail.type"), t("detail.type_star")))
            consts = STAR_CONSTELLATION.get(obj["name"], [])
            if consts:
                rows.append((t("detail.constellation"),
                             ", ".join(t(f"constellations.{c}") for c in consts)))
            rows.append((t("detail.mag"), f"{obj['mag']:.2f}"))
        elif kind == "planet":
            title = _planet_name(obj["name"])
            side = t("coords.east") if obj.get("east") else t("coords.west")
            rows.append((t("detail.type"), t("detail.type_planet")))
            rows.append((t("detail.distance"), tf("units.au", value=f"{obj['dist']:.4f}")))
            rows.append((t("detail.elongation"), f"{obj['elong']:.1f}° {side}"))
        elif kind == "sun":
            title = t("chart.sun")
            rows.append((t("detail.type"), t("detail.type_sun")))
            rows.append((t("detail.distance"), tf("units.au", value=f"{obj['dist']:.4f}")))
        else:
            title = t("chart.moon")
            key = Formatters.PHASES[Formatters.phase_index(obj["phase"])][0]
            rows.append((t("detail.type"), t("detail.type_moon")))
            rows.append((t("detail.phase"), t(f"phases.{key}")))
            rows.append((t("detail.illumination"), f"{obj['illum']:.1f} %"))
            rows.append((t("detail.distance"), tf("units.km", value=_fmt_int(obj["dist"]))))
        rows += [
            (t("detail.ra"), Formatters.hms(obj["ra"])),
            (t("detail.dec"), Formatters.dms(obj["dec"])),
            (t("detail.alt"), f"{obj['alt']:+.2f}°"),
            (t("detail.az"), f"{obj['az']:.2f}°"),
        ]
        return title, rows

    def _build_detail_dialog(self, obj):
        title, rows = self._object_details(obj)
        dlg = QDialog(self)
        dlg.setWindowTitle(tf("detail.title", name=title))
        dlg.setMinimumWidth(340)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(18, 16, 18, 14)
        lay.setSpacing(10)
        lay.addWidget(_label(title, name="cardTitle"))
        card = _card()
        grid = QGridLayout(card)
        grid.setContentsMargins(14, 10, 14, 10)
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(6)
        for r, (key, value) in enumerate(rows):
            grid.addWidget(_label(key, role="key"), r, 0)
            val = _label(value, role="value")
            val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            grid.addWidget(val, r, 1)
        lay.addWidget(card)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText(t("detail.close"))
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
        self._evt_layout.addWidget(_label(t("events.click_to_search"),
                                          name="emptyState", wrap=True))
        self._evt_layout.addStretch()

    def _events_header(self, title, count_text, note=None):
        self._evt_layout.addWidget(_label(title, name="cardTitle"))
        self._evt_layout.addWidget(_label(count_text, name="hint"))
        if note:
            self._evt_layout.addWidget(_label(note, name="hint", wrap=True))

    def _event_card(self, accent, icon, title, when, pill=None, details=()):
        """Carte d'événement : liseré de couleur, titre, date, détails."""
        card = _card("eventCard")
        card.setStyleSheet(f"QFrame#eventCard {{ border-left: 4px solid {accent}; }}")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(4)
        top = QHBoxLayout()
        top.setSpacing(10)
        head = _label(f"{icon}  {title}", name="eventTitle")
        head.setStyleSheet(f"color: {accent};")
        top.addWidget(head)
        top.addStretch()
        if pill:
            badge = QLabel()
            _set_badge(badge, *pill)
            top.addWidget(badge)
        top.addWidget(_label(when, role="value", strong=True))
        lay.addLayout(top)
        if details:
            lay.addWidget(_label("   ·   ".join(details), role="key", wrap=True))
        self._evt_layout.addWidget(card)

    def _search_start(self, kind):
        self._last_search = kind
        dte = self._edit_datetime()
        self._clear_evt_layout()
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        return dte

    def _search_failed(self, exc):
        self._evt_layout.addWidget(_label(tf("events.search_error", detail=exc),
                                          tone="error", wrap=True))
        self._evt_layout.addStretch()

    def _search_eclipses_gui(self):
        """Recherche et affiche les éclipses des 12 prochains mois."""
        dte = self._search_start("eclipses")
        try:
            eclipses = MeeusEngine.find_eclipses(dte, num_months=12)
        except Exception as exc:
            QApplication.restoreOverrideCursor()
            self._search_failed(exc)
            return
        QApplication.restoreOverrideCursor()

        n = len(eclipses)
        self._events_header(tf("events.eclipses_title", date=dte.strftime("%d/%m/%Y")),
                            tf(_plural_key("events.eclipse_count", n), n=n))
        if not eclipses:
            self._evt_layout.addWidget(_label(t("events.no_eclipse"), name="emptyState"))
        for ec in eclipses:
            solar = ec.get("type") == "solar"
            accent = Config.FG_SUN if solar else Config.FG_MOON
            title = t("events.solar_eclipse" if solar else "events.lunar_eclipse")
            if ec.get("sub_type"):
                title += f" — {t('events.subtype_' + ec['sub_type'])}"
            certainty = ec.get("certainty", "")
            pill = None
            if certainty:
                color = Config.FG_GREEN if certainty == "certain" else Config.FG_LABEL
                pill = (t(f"events.certainty_{certainty}"), color)
            when = ec["date"].strftime("%d/%m/%Y %H:%M") + f" {t('chart.ut')}"
            details = []
            if ec.get("magnitude") is not None:
                details.append(tf("events.magnitude", value=f"{ec['magnitude']:.3f}"))
            if ec.get("duration_min") is not None:
                details.append(tf("events.duration", value=ec["duration_min"]))
            if ec.get("diameter_ratio") is not None:
                details.append(tf("events.diameter_ratio",
                                  value=f"{ec['diameter_ratio']:.4f}"))
            if ec.get("moon_latitude") is not None:
                details.append(tf("events.moon_lat", value=f"{ec['moon_latitude']:+.2f}"))
            self._event_card(accent, "☀️" if solar else "🌕", title, when, pill, details)
        self._evt_layout.addStretch()

    def _search_conjunctions_gui(self):
        """Recherche et affiche les conjonctions et oppositions sur 12 mois."""
        dte = self._search_start("conjunctions")
        try:
            conjs = MeeusEngine.find_conjunctions(dte, num_days=365)
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
            self._evt_layout.addWidget(_label(t("events.no_conjunction"), name="emptyState"))
        for cj in conjs:
            a, b = cj.get("bodies", ("?", "?"))
            sep = cj.get("separation")
            if cj.get("type") == "opposition":
                icon, accent = "🔭", Config.FG_PURPLE
                title = tf("events.opposition", planet=_planet_name(a))
                detail_key, digits = "events.elongation", 1
            elif b == "Sun":
                icon, accent = "☀️", Config.FG_SUN
                title = tf("events.solar_conjunction", planet=_planet_name(a))
                detail_key, digits = "events.separation", 2
            else:
                icon, accent = "✨", Config.planet_color(a)
                title = tf("events.conjunction_pair", a=_planet_name(a), b=_planet_name(b))
                detail_key, digits = "events.separation", 2
            details = [tf(detail_key, value=f"{sep:.{digits}f}")] if sep is not None else []
            self._event_card(accent, icon, title, cj["date"].strftime("%d/%m/%Y"),
                             details=details)
        self._evt_layout.addStretch()
