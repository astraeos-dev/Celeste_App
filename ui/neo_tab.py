"""
ui/neo_tab.py — Astres › Near-Earth asteroids: those passing close to the Earth.

A mixin of the main window (gui.AstroApp): the close approaches listed by
CNEOS (neo.py) in the coming days, the notable ones marked; for those that
could get brighter than magnitude 16, the magnitude JPL Horizons gives at the
approach and when the asteroid is high in a dark sky from the place. All of
it in the background, when the page is first shown.
"""
from ui import common
from ui.common import *  # noqa: F401,F403

import html

import neo
from engine import constellation_at

_NEO_COLUMNS = ("date", "name", "distance", "size", "speed", "mag")
_NEO_DAYS = (30, 60, 365)
_NEO_ROLE = Qt.ItemDataRole.UserRole + 13
_NEO_EPHEMERIDES = 12          # Horizons asked for this many asteroids at most, the nearest in time first
_EPOCH = datetime(2000, 1, 1)  # the date column sorts by seconds since then (UT)


def _approach_key(approach):
    return approach["designation"], approach["date"]


class NeoSpace:
    # ── The page ──────────────────────────────────────────────────────────

    def _build_neo_tab(self):
        page, _inner, lay = _scroll_page()                       # a phone: the page scrolls
        lay.setSpacing(12)
        lay.addWidget(_label(t("neo.intro"), "corps", tone="attenuee", wrap=True))

        bar = QBoxLayout(QBoxLayout.Direction.LeftToRight)     # a phone: two rows
        bar.setSpacing(8)
        choices = QHBoxLayout()
        choices.setSpacing(8)
        self._neo_days = QComboBox()
        for days in _NEO_DAYS:
            self._neo_days.addItem(t(f"neo.period_{days}"), days)
        self._neo_days.setCurrentIndex(max(0, self._neo_days.findData(int(_pref_float("neo_days", 60)))))
        choices.addWidget(InputField(t("neo.period"), self._neo_days), stretch=1)
        bar.addLayout(choices)
        rest = QHBoxLayout()
        rest.setSpacing(8)
        self._neo_notable = QCheckBox(t("neo.notable_only"))
        self._neo_notable.setToolTip(t("neo.notable_tip"))
        self._neo_notable.setChecked(bool(prefs.get("neo_notable_only")))
        rest.addWidget(self._neo_notable, alignment=Qt.AlignmentFlag.AlignBottom)
        rest.addStretch()
        self._neo_refresh_btn = _button(t("neo.refresh"), "reset", compact=True)
        self._neo_refresh_btn.setToolTip(t("neo.refresh_tip"))
        self._neo_refresh_btn.clicked.connect(lambda _c=False: self._refresh_neo(force=True))
        rest.addWidget(self._neo_refresh_btn, alignment=Qt.AlignmentFlag.AlignBottom)
        bar.addLayout(rest, stretch=1)
        self._reflow.append(bar)
        lay.addLayout(bar)
        self._neo_status = _label("", "legende", tone="attenuee", wrap=True)
        lay.addWidget(self._neo_status)

        table = QTableWidget(0, len(_NEO_COLUMNS))
        table.setHorizontalHeaderLabels([t(f"neo.col_{key}") for key in _NEO_COLUMNS])
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setWordWrap(False)
        table.setSortingEnabled(True)
        header = table.horizontalHeader()
        for col, key in enumerate(_NEO_COLUMNS):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch if key == "name"
                                        else QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeaderItem(_NEO_COLUMNS.index("distance")).setToolTip(t("neo.ld_tip"))
        table.horizontalHeaderItem(_NEO_COLUMNS.index("mag")).setToolTip(t("neo.mag_tip"))
        table.itemSelectionChanged.connect(self._neo_selection_changed)
        table.setMinimumHeight(240)
        self._neo_table = table
        lay.addWidget(table, stretch=1)
        self._neo_details = _label("", "corps", wrap=True)
        self._neo_details.setTextFormat(Qt.TextFormat.RichText)
        self._neo_details.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(self._neo_details)
        lay.addWidget(_label(t("neo.credit"), "legende", tone="attenuee", wrap=True))

        self._neo_days.currentIndexChanged.connect(lambda _i: self._neo_choice_changed())
        self._neo_notable.toggled.connect(lambda _v: self._neo_choice_changed())
        self._compact_hooks.append(self._neo_compact)
        self._neo_shown, self._neo_seen, self._neo_key, self._neo_busy = [], {}, None, False
        self._neo_page = page
        self._add_page(page, t("tabs.neo"))

    def _neo_compact(self, compact):
        """On a phone: two columns, the date without the year and the asteroid with how near and how bright."""
        self._neo_short = compact
        table = self._neo_table
        for col, key in enumerate(_NEO_COLUMNS):
            table.setColumnHidden(col, compact and key not in ("date", "name"))
        self._neo_texts()

    def _neo_texts(self):
        """The texts of the rows shown, for the layout (wide or phone)."""
        table = self._neo_table
        for row in range(table.rowCount()):
            first = table.item(row, 0)
            if first is None or first.data(_NEO_ROLE) is None:
                continue
            cells = self._neo_cells(self._neo_shown[first.data(_NEO_ROLE)])
            for col, key in enumerate(_NEO_COLUMNS):
                table.item(row, col).setText(cells[key][0])

    def _neo_choice_changed(self):
        prefs.set("neo_days", self._neo_days.currentData())
        prefs.set("neo_notable_only", self._neo_notable.isChecked())
        self._refresh_neo()

    # ── Finding them (in the background) ─────────────────────────────────

    def _refresh_neo(self, force=False):
        """The approaches of the days after the date of the calculation: CNEOS' list
        (downloaded twice a day), then Horizons for those that could get bright, seen
        from the place."""
        if self._neo_busy or self._lat is None or self._dte is None:
            return
        days, notable_only = self._neo_days.currentData(), self._neo_notable.isChecked()
        now = self._dte.replace(tzinfo=None)                      # from the date of the calculation
        lat, lon, elev = self._lat, self._lon, self._elevation()
        key = (now.date(), round(lat, 4), round(lon, 4), elev, days, notable_only, neo.cache_stamp())
        if not force and key == self._neo_key:
            return
        self._neo_busy = True
        self._neo_refresh_btn.setEnabled(False)
        self._neo_status.setText(t("neo.loading"))

        def work():
            approaches, error = neo.refresh(max_age_hours=0.0 if force else neo.MAX_AGE_HOURS)
            shown = [a for a in approaches if now - timedelta(days=1) <= a["date"] <= now + timedelta(days=days)
                     and (not notable_only or neo.notable(a))]
            seen = {}
            for approach in [a for a in shown if a["date"] >= now and neo.worth_an_ephemeris(a)][:_NEO_EPHEMERIDES]:
                try:
                    rows = neo.seen_from(neo.ephemeris(approach), lat, lon, elev)
                except Exception as exc:              # Horizons down, unknown name: the list all the same
                    seen[_approach_key(approach)] = {"error": str(exc)}
                    continue
                if not rows:
                    continue
                nearest = min(rows, key=lambda r: abs((r["date"] - approach["date"]).total_seconds()))
                windows = neo.windows(rows)
                for window in windows:
                    best = window["best"]
                    window["constellation"] = constellation_at(best["ra"], best["dec"],
                                                               AstroEngine.julian_day(best["date"]))
                seen[_approach_key(approach)] = {"mag": nearest["mag"], "windows": windows,
                                                 "span": (rows[0]["date"], rows[-1]["date"])}
            return len(approaches), shown, seen, error

        def done(answer):
            total, shown, seen, error = answer
            self._neo_busy = False
            self._neo_refresh_btn.setEnabled(True)
            self._neo_key = (*key[:-1], neo.cache_stamp())
            self._neo_shown, self._neo_seen = shown, seen
            self._show_neo(total, days, error)

        def failed(exc):
            self._neo_busy = False
            self._neo_refresh_btn.setEnabled(True)
            self._neo_status.setText(tf("neo.error", detail=str(exc)))
        common._run_in_background(work, done, failed)

    # ── Showing them ──────────────────────────────────────────────────────

    def _neo_size(self, approach):
        size = neo.size_m(approach)
        if size is None:
            return "—"
        small, large = size
        if abs(large - small) < 0.5:
            return tf("neo.size_one", value=_num(small))
        return tf("neo.size", min=_num(small), max=_num(large))

    def _neo_mag(self, approach):
        """The magnitude cell and its sort value: Horizons' at the approach, else a bound."""
        seen = self._neo_seen.get(_approach_key(approach))
        if seen and seen.get("mag") is not None:
            text = _num(seen["mag"], 1)
            if seen["windows"] and seen["mag"] <= neo.FAINTEST:          # high in a dark sky, and bright enough
                text += " · " + t("neo.visible")
            return text, seen["mag"]
        best = neo.best_magnitude(approach)
        if best is None:
            return "—", None
        if best > neo.FAINTEST:
            return tf("neo.mag_faint", mag=_num(neo.FAINTEST)), best
        return tf("neo.mag_bound", mag=_num(best, 1)), best

    def _neo_cells(self, approach):
        """{column: (text, sort value)} of an approach's row (shorter on a phone)."""
        local = self._local(approach["date"])
        short = getattr(self, "_neo_short", False)
        size = neo.size_m(approach)
        mag_text, mag_sort = self._neo_mag(approach)
        ld = neo.lunar_distances(approach["distance_au"])
        distance = tf("neo.ld", value=_num(ld, 1 if ld >= 1 else 2))
        return {
            "date": (f"{local:%d/%m}{'' if short else f'/{local:%Y}'} {self._fmt_clock(local)}",
                     (approach["date"] - _EPOCH).total_seconds()),
            "name": (f"{approach['name']} · {distance} · {mag_text}" if short else approach["name"], approach["name"]),
            "distance": (distance, approach["distance_au"]),
            "size": (self._neo_size(approach), -size[1] if size else None),
            "speed": (tf("neo.speed", value=_num(approach["speed"], 1)) if approach["speed"] else "—",
                      approach["speed"]),
            "mag": (mag_text, mag_sort),
        }

    def _show_neo(self, total, days, error):
        shown = self._neo_shown
        table = self._neo_table
        table.setSortingEnabled(False)
        table.clearContents()
        table.setRowCount(len(shown))
        for row, approach in enumerate(shown):
            cells = self._neo_cells(approach)
            for col, key in enumerate(_NEO_COLUMNS):
                text, sort = cells[key]
                item = _SortItem(text)
                item.setData(_NEO_ROLE, row)
                item.setData(_SORT_ROLE, sort)
                if key == "name" and neo.notable(approach):
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                    item.setToolTip(t("neo.notable_row"))
                if key == "distance":
                    item.setToolTip(tf("units.km", value=_num(approach["distance_au"] * neo.AU_KM)))
                table.setItem(row, col, item)
        table.setSortingEnabled(True)
        table.sortItems(0, Qt.SortOrder.AscendingOrder)
        status = tf(_plural_key("neo.count", len(shown)), n=len(shown))
        if neo.cache_stamp():
            stamp = self._local(datetime.fromtimestamp(neo.cache_stamp(), timezone.utc).replace(tzinfo=None))
            status += " · " + tf("neo.list_of", date=f"{stamp:%d/%m}", time=self._fmt_clock(stamp), total=total)
        if error:
            status += " · " + tf("neo.offline", detail=error)
        self._neo_status.setText(status)
        table.setVisible(bool(shown))
        self._neo_details.setText("" if shown else html.escape(t("neo.none"), quote=False))
        if shown:
            table.selectRow(0)

    def _neo_selected(self):
        items = self._neo_table.selectedItems()
        if not items:
            return None
        index = items[0].data(_NEO_ROLE)
        return self._neo_shown[index] if index is not None and index < len(self._neo_shown) else None

    def _neo_selection_changed(self):
        approach = self._neo_selected()
        if approach is not None:
            self._neo_details.setText(_rich_lines(self._neo_detail_lines(approach)))

    def _neo_when(self, dt):
        local = self._local(dt)
        return f"{local:%d/%m} {self._fmt_clock(local)}"

    def _neo_detail_lines(self, approach):
        """The chosen approach in words: when and how near, how big and fast, and what the place sees."""
        local = self._local(approach["date"])
        zone = getattr(self._zone, "key", "UTC") if self._zone else "UTC"
        ld = neo.lunar_distances(approach["distance_au"])
        title = approach["name"]
        if neo.notable(approach):
            title += " · " + t("neo.notable_row")
        lines = [title, tf("neo.details_when", date=f"{local:%d/%m/%Y}", time=self._fmt_clock(local), zone=zone,
                           km=_num(approach["distance_au"] * neo.AU_KM), ld=_num(ld, 2))]
        if approach["sigma_minutes"]:
            lines.append(tf("neo.details_sigma", value=_duration(approach["sigma_minutes"])))
        low, high = approach["distance_min_au"], approach["distance_max_au"]
        if high - low > 0.02 * approach["distance_au"]:
            lines.append(tf("neo.details_range", min=_num(low * neo.AU_KM), max=_num(high * neo.AU_KM)))
        size = neo.size_m(approach)
        if approach.get("diameter_km"):
            lines.append(tf("neo.details_measured", value=_num(size[0])))
        elif size:
            lines.append(tf("neo.details_size", min=_num(size[0]), max=_num(size[1]), h=_num(approach["h"], 1)))
        if approach["speed"]:
            lines.append(tf("neo.details_speed", value=_num(approach["speed"], 1)))
        seen = self._neo_seen.get(_approach_key(approach))
        best = neo.best_magnitude(approach)
        if seen and "error" in seen:
            lines.append(tf("neo.details_error", detail=seen["error"]))
        elif seen:
            if seen.get("mag") is not None:
                lines.append(tf("neo.details_mag", mag=_num(seen["mag"], 1)))
            for window in seen["windows"][:4]:
                b = window["best"]
                lines.append(tf("neo.details_window", start=self._neo_when(window["start"]),
                                end=self._neo_when(window["end"]),
                                mag=_num(b["mag"], 1) if b["mag"] is not None else "—", time=self._neo_when(b["date"]),
                                alt=_num(b["alt"]), dir=self._wind(b["az"]),
                                constellation=t(f"constellations.{window['constellation']}"),
                                rate=_num(b["rate"])))
            if not seen["windows"]:
                first, last = seen["span"]
                lines.append(tf("neo.details_no_window", start=self._neo_when(first), end=self._neo_when(last)))
        elif best is not None and best > neo.FAINTEST:
            lines.append(tf("neo.details_faint", mag=_num(best, 1)))
        elif best is not None and self._dte is not None and approach["date"] >= self._dte.replace(tzinfo=None):
            lines.append(tf("neo.details_not_asked", mag=_num(best, 1)))
        return lines
