"""
ui/bodies.py — Astres: planets, Solar System (orrery), coordinates and the data window of a body.

A mixin of the main window (gui.AstroApp): its methods use the window's state
(self.*) and those of the other spaces.
"""
from ui import common
from ui.common import *  # noqa: F401,F403


class BodiesSpace:
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
