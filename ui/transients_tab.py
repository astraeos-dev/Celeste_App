"""
ui/transients_tab.py — Ciel › Novae and supernovae: the new stars of the moment.

A mixin of the main window (gui.AstroApp): the supernovae and novae bright
enough for the magnitude chosen (transients.py: David Bishop's active
supernovae, Koji Mukai's galactic novae), when each is highest in a dark sky
tonight, the details of the chosen one, and a button that circles it on the
sky map (where they are drawn too). The lists are downloaded in the background
when the page is first shown.
"""
from ui import common
from ui.common import *  # noqa: F401,F403

import html

from engine import constellation_at

_TR_COLUMNS = ("name", "kind", "where", "mag", "discovered", "tonight")
_TR_MAGS = (12, 13, 14, 15, 16, 17)
_TR_MONTHS = (3, 6, 12, 24)
_TR_ROLE = Qt.ItemDataRole.UserRole + 15


class TransientSpace:
    # ── The page ──────────────────────────────────────────────────────────

    def _build_transients_tab(self):
        page, _inner, lay = _scroll_page()                       # a phone: the page scrolls
        lay.setSpacing(12)
        lay.addWidget(_label(t("transients.intro"), "corps", tone="attenuee", wrap=True))

        bar = QBoxLayout(QBoxLayout.Direction.LeftToRight)     # a phone: rows, one under another
        bar.setSpacing(8)
        choices = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        choices.setSpacing(8)
        self._tr_mag = QComboBox()
        for mag in _TR_MAGS:
            self._tr_mag.addItem(tf("transients.mag_item", mag=mag), mag)
        self._tr_mag.setCurrentIndex(max(0, self._tr_mag.findData(int(_pref_float("transients_mag", 15)))))
        self._tr_mag.setToolTip(t("transients.mag_tip"))
        choices.addWidget(InputField(t("transients.mag"), self._tr_mag), stretch=1)
        self._tr_months = QComboBox()
        for months in _TR_MONTHS:
            self._tr_months.addItem(tf("transients.months", n=months), months)
        self._tr_months.setCurrentIndex(max(0, self._tr_months.findData(int(_pref_float("transients_months", 12)))))
        self._tr_months.setToolTip(t("transients.months_tip"))
        choices.addWidget(InputField(t("transients.novae_since"), self._tr_months), stretch=1)
        bar.addLayout(choices)
        rest = QHBoxLayout()
        rest.setSpacing(8)
        self._tr_on_map = QCheckBox(t("transients.show_on_map"))
        self._tr_on_map.setToolTip(t("transients.show_on_map_tip"))
        self._tr_on_map.setChecked(bool(prefs.get("show_transients")))
        self._tr_on_map.toggled.connect(self._tr_map_toggled)
        rest.addWidget(self._tr_on_map, alignment=Qt.AlignmentFlag.AlignBottom)
        self._tr_refresh_btn = _button(t("transients.refresh"), "reset", compact=True)
        self._tr_refresh_btn.setToolTip(t("transients.refresh_tip"))
        self._tr_refresh_btn.clicked.connect(lambda _c=False: self._refresh_transients(force=True))
        rest.addWidget(self._tr_refresh_btn, alignment=Qt.AlignmentFlag.AlignBottom)
        self._tr_map_btn = _button(t("transients.on_map"), "map", "discret", compact=True)
        self._tr_map_btn.setToolTip(t("transients.on_map_tip"))
        self._tr_map_btn.setEnabled(False)
        self._tr_map_btn.clicked.connect(lambda _c=False: self._show_transient_on_map())
        rest.addWidget(self._tr_map_btn, alignment=Qt.AlignmentFlag.AlignBottom)
        rest.addStretch()
        bar.addLayout(rest, stretch=1)
        self._reflow += [bar, choices]
        lay.addLayout(bar)
        self._tr_status = _label("", "legende", tone="attenuee", wrap=True)
        lay.addWidget(self._tr_status)

        table = QTableWidget(0, len(_TR_COLUMNS))
        table.setHorizontalHeaderLabels([t(f"transients.col_{key}") for key in _TR_COLUMNS])
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setWordWrap(False)
        table.setSortingEnabled(True)
        header = table.horizontalHeader()
        for col, key in enumerate(_TR_COLUMNS):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch if key == "where"
                                        else QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeaderItem(_TR_COLUMNS.index("mag")).setToolTip(t("transients.col_mag_tip"))
        table.itemSelectionChanged.connect(self._tr_selection_changed)
        table.itemDoubleClicked.connect(lambda _item: self._show_transient_on_map())
        table.setMinimumHeight(240)
        self._tr_table = table
        lay.addWidget(table, stretch=1)
        self._tr_details = _label("", "corps", wrap=True)
        self._tr_details.setTextFormat(Qt.TextFormat.RichText)
        self._tr_details.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(self._tr_details)
        lay.addWidget(_label(t("transients.credit"), "legende", tone="attenuee", wrap=True))

        self._tr_mag.currentIndexChanged.connect(lambda _i: self._tr_choice_changed())
        self._tr_months.currentIndexChanged.connect(lambda _i: self._tr_choice_changed())
        self._compact_hooks.append(self._tr_compact)
        self._tr_shown, self._tr_seen, self._tr_key, self._tr_busy = [], [], None, False
        self._transients_page = page
        self._add_page(page, t("tabs.transients"), short=t("tabs.transients_short"))

    def _tr_compact(self, compact):
        """On a phone: the buttons as icons, and two columns, the object with its magnitude,
        and tonight."""
        self._tr_short = compact
        self._tr_refresh_btn.setText("" if compact else t("transients.refresh"))
        self._tr_map_btn.setText("" if compact else t("transients.on_map"))
        header = self._tr_table.horizontalHeader()        # a phone: the object takes the room left, elided
        header.setSectionResizeMode(_TR_COLUMNS.index("name"), QHeaderView.ResizeMode.Stretch if compact
                                    else QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(_TR_COLUMNS.index("where"), QHeaderView.ResizeMode.ResizeToContents if compact
                                    else QHeaderView.ResizeMode.Stretch)
        for col, key in enumerate(_TR_COLUMNS):
            self._tr_table.setColumnHidden(col, compact and key not in ("name", "tonight"))
        self._tr_texts()

    def _tr_map_toggled(self, checked):
        prefs.set("show_transients", bool(checked))
        self._redraw_sky_transients()

    def _tr_choice_changed(self):
        prefs.set("transients_mag", self._tr_mag.currentData())
        prefs.set("transients_months", self._tr_months.currentData())
        self._refresh_transients()
        self._redraw_sky_transients()

    # ── The objects shown (the page and the sky map) ──────────────────────

    def _transients_chosen(self, objects=None):
        """The novae and supernovae the page's choices let through, from the lists kept on disk."""
        today = (self._dte or common._utc_now()).date()
        return transients.chosen(transients.load() if objects is None else objects, today,
                                 _pref_float("transients_mag", 15.0), int(_pref_float("transients_months", 12)) * 30)

    def _redraw_sky_transients(self):
        """The sky map's scenes again (the calculation's and the time bar's), with the
        novae and supernovae of the new lists or choices."""
        calc = getattr(self, "_sky_calc_state", None)
        if self._dte is None or calc is None:
            return
        self._sky_calc_scene = self._sky_scene_for(calc, calc["dte"], self._lat, self._lon)
        self._show_sky_time_view()

    # ── Finding them (in the background) ─────────────────────────────────

    def _refresh_transients(self, force=False):
        """The lists (downloaded twice a day at most), the objects chosen, and when each
        is highest in the dark tonight from the place, in the background."""
        if self._tr_busy or self._lat is None or self._dte is None:
            return
        mag, months = self._tr_mag.currentData(), self._tr_months.currentData()
        dte, lat, lon, elev, zone = self._dte, self._lat, self._lon, self._elevation(), self._zone
        key = (dte.date(), round(lat, 4), round(lon, 4), elev, mag, months, transients.cache_stamp())
        if not force and key == self._tr_key:
            return
        self._tr_busy = True
        self._tr_refresh_btn.setEnabled(False)
        self._tr_status.setText(t("transients.loading"))

        def work():
            objects, error = transients.refresh(max_age_hours=0.0 if force else transients.MAX_AGE_HOURS)
            shown = transients.chosen(objects, dte.replace(tzinfo=None).date(), mag, months * 30)
            night = planner.night_window(dte, lat, lon, elev, zone, depths=((transients.DARK_SUN, "naut"),))
            seen = transients.tonight(shown, night["start"], night["end"], lat, lon, elev)
            constellations = [constellation_at(o["ra"], o["dec"], AstroEngine.julian_day(dte)) for o in shown]
            return shown, seen, constellations, error, len(objects)

        def done(answer):
            shown, seen, constellations, error, total = answer
            self._tr_busy = False
            self._tr_refresh_btn.setEnabled(True)
            self._tr_key = (*key[:-1], transients.cache_stamp())
            self._tr_shown = [dict(o, constellation=c) for o, c in zip(shown, constellations)]
            self._tr_seen = seen
            self._show_transients(error, total)
            self._redraw_sky_transients()

        def failed(exc):
            self._tr_busy = False
            self._tr_refresh_btn.setEnabled(True)
            self._tr_status.setText(tf("transients.error", detail=str(exc)))
        common._run_in_background(work, done, failed)

    # ── Showing them ──────────────────────────────────────────────────────

    def _tr_kind(self, obj):
        """"Supernova Ia", "Nova", "Nova (LMC)"."""
        if obj["kind"] == "supernova":
            return tf("transients.kind_supernova", type=obj["type"])
        return t("transients.kind_nova")

    def _tr_mag_text(self, obj):
        """The latest magnitude when it is recent; else the peak (a galactic nova that has faded
        since, or one of Koji Mukai's list, which gives only the peak)."""
        today = (self._dte or common._utc_now()).date()
        recent = obj.get("mag_date") is not None and (today - obj["mag_date"]).days <= transients.RECENT_DAYS
        if obj.get("mag") is not None and (recent or obj.get("peak") is None):
            return _num(obj["mag"], 1)
        if obj.get("peak") is not None:
            return tf("transients.peak_cell", mag=_num(obj["peak"], 1))
        return "—"

    def _tr_tonight(self, index):
        seen = self._tr_seen[index] if index < len(self._tr_seen) else None
        if seen is None:
            return t("transients.not_tonight")
        return tf("transients.tonight_cell", time=self._clock(seen["best"]), alt=_num(seen["alt"]))

    def _tr_cells(self, index):
        """{column: (text, sort value)} of a row (shorter on a phone)."""
        obj = self._tr_shown[index]
        short = getattr(self, "_tr_short", False)
        found = obj["discovered"]
        seen = self._tr_seen[index] if index < len(self._tr_seen) else None
        return {
            "name": (f"{obj['name']} · {self._tr_mag_text(obj)}" if short else obj["name"], obj["name"]),
            "kind": (self._tr_kind(obj), obj["type"]),
            "where": (obj["host"] or t(f"constellations.{obj['constellation']}"), obj["host"] or obj["constellation"]),
            "mag": (self._tr_mag_text(obj), index),                      # the list's order: the brightest now first
            "discovered": (f"{found:%d/%m/%Y}" if found else "—", found.toordinal() if found else None),
            "tonight": (self._tr_tonight(index), -seen["alt"] if seen else None),
        }

    def _tr_texts(self):
        table = self._tr_table
        for row in range(table.rowCount()):
            first = table.item(row, 0)
            if first is None or first.data(_TR_ROLE) is None:
                continue
            cells = self._tr_cells(first.data(_TR_ROLE))
            for col, key in enumerate(_TR_COLUMNS):
                table.item(row, col).setText(cells[key][0])

    def _show_transients(self, error, total):
        shown = self._tr_shown
        table = self._tr_table
        table.setSortingEnabled(False)
        table.clearContents()
        table.setRowCount(len(shown))
        for row in range(len(shown)):
            cells = self._tr_cells(row)
            for col, key in enumerate(_TR_COLUMNS):
                text, sort = cells[key]
                item = _SortItem(text)
                item.setData(_TR_ROLE, row)
                item.setData(_SORT_ROLE, sort)
                if key == "tonight" and self._tr_seen[row] is not None:
                    item.setForeground(QBrush(QColor(Config.OR)))
                table.setItem(row, col, item)
        table.setSortingEnabled(True)
        table.sortItems(_TR_COLUMNS.index("mag"), Qt.SortOrder.AscendingOrder)
        visible = sum(1 for s in self._tr_seen if s is not None)
        status = tf(_plural_key("transients.count", len(shown)), n=len(shown))
        if shown:
            status += " · " + tf(_plural_key("transients.count_tonight", visible), n=visible)
        stamp = transients.cache_stamp()
        if stamp:
            local = self._local(datetime.fromtimestamp(stamp, timezone.utc).replace(tzinfo=None))
            status += " · " + tf("transients.lists_of", date=f"{local:%d/%m}", time=self._fmt_clock(local))
        if error:
            status += " · " + tf("transients.offline", detail=error)
        self._tr_status.setText(status)
        table.setVisible(bool(shown))
        self._tr_details.setText("" if shown else html.escape(t("transients.none"), quote=False))
        if shown:
            table.selectRow(0)
        self._tr_selection_changed()

    def _tr_selected(self):
        items = self._tr_table.selectedItems()
        if not items:
            return None
        index = items[0].data(_TR_ROLE)
        return index if index is not None and index < len(self._tr_shown) else None

    def _tr_selection_changed(self):
        index = self._tr_selected()
        self._tr_map_btn.setEnabled(index is not None)
        if index is not None:
            self._tr_details.setText(_rich_lines(self._tr_detail_lines(index)))

    def _tr_detail_lines(self, index):
        """The chosen object in words: what and where, how bright, how far, and tonight from the place."""
        obj = self._tr_shown[index]
        lines = [f"{obj['name']} · {self._tr_kind(obj)}"]
        if obj["aka"]:
            lines.append(tf("transients.details_aka", names=", ".join(obj["aka"][:4])))
        where = t(f"constellations.{obj['constellation']}")
        if obj["host"]:
            lines.append(tf("transients.details_host", host=obj["host"], constellation=where))
        else:
            lines.append(tf("transients.details_galactic", constellation=where))
        lines.append(tf("transients.details_position", ra=_ra(obj["ra"]), dec=_dec(obj["dec"])))
        if obj["mag"] is not None:
            when = obj["mag_date"]
            lines.append(tf("transients.details_mag", mag=_num(obj["mag"], 1),
                            date=f"{when:%d/%m/%Y}" if when else "—"))
        if obj["peak"] is not None:
            when = obj["peak_date"]
            lines.append(tf("transients.details_peak", mag=_num(obj["peak"], 1)) if when is None else
                         tf("transients.details_peak_on", mag=_num(obj["peak"], 1), date=f"{when:%d/%m/%Y}"))
        if obj["discovered"]:
            day = f"{obj['discovered']:%d/%m/%Y}"
            lines.append(tf("transients.details_found_by", date=day, who=obj["discoverer"]) if obj["discoverer"]
                         else tf("transients.details_found", date=day))
        distance = transients.distance_mly(obj["z"])
        if distance:
            lines.append(tf("transients.details_distance", mly=_num(distance)))
        seen = self._tr_seen[index] if index < len(self._tr_seen) else None
        if seen is None:
            lines.append(t("transients.details_not_tonight"))
        else:
            lines.append(tf("transients.details_tonight", time=self._clock(seen["best"]), alt=_num(seen["alt"]),
                            dir=self._wind(seen["az"])))
        return lines

    def _show_transient_on_map(self):
        """The chosen object circled on the sky map, at the calculation's time."""
        index = self._tr_selected()
        if index is None:
            return
        self.show_page(self._sky_page)
        self._find_on_sky(("transient", self._tr_shown[index]["name"]))
