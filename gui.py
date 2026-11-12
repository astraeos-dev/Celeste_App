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

from ui import common
from ui.common import *  # noqa: F401,F403
from ui.tonight import TonightSpace
from ui.sky import SkySpace
from ui.bodies import BodiesSpace
from ui.calendar_tab import CalendarSpace
from ui.observe import ObserveSpace
from ui.settings_tab import SettingsSpace


class AstroApp(TonightSpace, SkySpace, BodiesSpace, CalendarSpace, ObserveSpace, SettingsSpace, QMainWindow):
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
    # FAVOURITES
    # ──────────────────────────────────────────────────────────────────────────

    def _load_favorites(self):
        """The user's favourites; until one is saved, the preloaded places."""
        for path in (common._FAVORITES_FILE, common._LEGACY_FAVORITES_FILE):
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        return json.load(f)
                except (OSError, json.JSONDecodeError):
                    continue
        return _default_favorites()

    def _save_favorites(self):
        try:
            os.makedirs(os.path.dirname(common._FAVORITES_FILE), exist_ok=True)
            with open(common._FAVORITES_FILE, "w", encoding="utf-8") as f:
                json.dump(self.favorites, f, ensure_ascii=False, indent=2)
        except OSError as exc:
            common.QMessageBox.critical(self, t("errors.error_title"), str(exc))

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
        name, ok = common.QInputDialog.getText(self, t("favs.save_title"),
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
        answer = common.QMessageBox.question(
            self, t("favs.delete_title"), tf("favs.delete_confirm", name=name),
            common.QMessageBox.StandardButton.Yes | common.QMessageBox.StandardButton.No)
        if answer != common.QMessageBox.StandardButton.Yes:
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
        source = common.QGeoPositionInfoSource.createDefaultSource(self)
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
        name = common._place_name(lat, lon)
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
        """The place picked on a map (common.PlacePicker): coordinates, name, time zone, elevation of
        the nearest city, then calculation."""
        try:
            _dte, lat, lon = self.current_inputs()
        except ValueError:
            lat, lon = 48.0, 2.0
        picker = common.PlacePicker(self, lat, lon)
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
        box = common.QMessageBox(common.QMessageBox.Icon.Information, t("errors.geoloc_title"), text, parent=self)
        box.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        box.setInformativeText(t(f"errors.geoloc_reason_{reason}"))
        on_map = box.addButton(t("errors.geoloc_choose_map"), common.QMessageBox.ButtonRole.AcceptRole)
        url = _LOCATION_SETTINGS.get(sys.platform)
        settings = None
        if url and reason in ("access", "closed", "no_source", "timeout"):
            settings = box.addButton(t("errors.geoloc_open_settings"), common.QMessageBox.ButtonRole.ActionRole)
        box.addButton(common.QMessageBox.StandardButton.Close)
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
        common.QMessageBox.warning(self, t("errors.error_title"), t("status.invalid_coords"))

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
