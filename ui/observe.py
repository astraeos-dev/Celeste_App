"""
ui/observe.py — Observer: the night planner (targets), its maps and lists, the Workshop.

A mixin of the main window (gui.AstroApp): its methods use the window's state
(self.*) and those of the other spaces.
"""
from ui import common
from ui.common import *  # noqa: F401,F403


class ObserveSpace:
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
        # compact layout: back to the night's targets, computed with these constraints
        self._btn_plan_back = _button(t("planner.show_results"), "search")
        self._btn_plan_back.clicked.connect(lambda: (self._show_plan_side(False), self._compute_plan(force=True)))
        form.addWidget(self._btn_plan_back)
        form.addStretch()
        outer.addWidget(side)

        # right: the night, the tables, the chart
        right_w = QWidget()
        right = QVBoxLayout(right_w)
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(12)
        bar = QHBoxLayout()
        bar.setSpacing(8)
        # compact layout: the constraints take the whole page, from this button
        self._btn_plan_side = _icon_button("tune", t("planner.constraints"))
        self._btn_plan_side.clicked.connect(lambda: self._show_plan_side(True))
        bar.addWidget(self._btn_plan_side)
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
        self._plan_enlarge = _button(t("planner.sky_enlarge"), "zoom_in", "discret", compact=True)
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
        outer.addWidget(right_w, stretch=1)
        self._plan_side, self._plan_right = side, right_w
        self._compact_hooks.append(self._plan_compact)
        self._add_page(page, t("tabs.planner"))
        self._planner_page = page
        if self._plan is not None:                        # rebuilt (language, theme): shown again
            self._show_plan()

    def _plan_compact(self, compact):
        """Compact layout: the constraints as a page of their own, the results otherwise."""
        side = self._plan_side
        if compact:
            side.setMinimumWidth(0)
            side.setMaximumWidth(16777215)
        else:
            side.setFixedWidth(320)
        self._btn_plan_side.setVisible(compact)
        self._plan_status.setVisible(not compact)        # the summary under the bar says it too
        self._btn_plan_export.setText("" if compact else t("planner.export"))    # a phone: the icons (tooltips)
        self._plan_enlarge.setText("" if compact else t("planner.sky_enlarge"))
        self._btn_plan_back.setVisible(compact)
        self._show_plan_side(False)

    def _show_plan_side(self, shown):
        """Compact layout: the constraints (*shown*) or the night's targets."""
        compact = self.is_compact()
        self._plan_side.setVisible(not compact or shown)
        self._plan_right.setVisible(not compact or not shown)

    def _refresh_plan_summary(self):
        """The planner's summary of the night, with the quality of the night of Tonight under it."""
        base = getattr(self, "_plan_summary_base", None)
        if base is None or not hasattr(self, "_plan_summary"):
            return
        quality = getattr(self, "_quality_text", "")
        self._plan_summary.setText(f"{base}\n{quality}" if quality else base)

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
        common._run_in_background(work, done_, failed)

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
        self._plan_summary_base = tf(
            "planner.summary", kind=t(f"planner.night_{window['kind']}"), start=self._hm(window["start"]),
            end=self._hm(window["end"]), moon=_num(moon["illumination"], 0),
            separation=_num(moon["separation_min"], 0))
        self._refresh_plan_summary()
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
                common.QMessageBox.critical(dlg, t("errors.error_title"), str(exc))
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
            menu.addAction(t("journal.log_target")).triggered.connect(
                lambda: self._journal_open(target=labels[0]))
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
        self.show_page(self._sky_page)
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
        from qt.QtWidgets import QPlainTextEdit
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
        from qt.QtWidgets import QPlainTextEdit
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
            common.QMessageBox.critical(self, t("errors.error_title"), str(exc))
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
                common.QMessageBox.warning(dlg, t("errors.error_title"), tf("workshop.save_error", error=exc))
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
