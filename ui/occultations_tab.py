"""
ui/occultations_tab.py — Observer › Occultations: stars hidden by asteroids.

A mixin of the main window (gui.AstroApp): the events of the IOTA predictions
(occultations.py) whose band passes within a chosen distance of the place in
the coming months, with the star high enough in a dark sky; the details of
the chosen one; OccultWatcher Cloud for the updated paths. The predictions
are downloaded in the background when the page is first shown.
"""
from ui import common
from ui.common import *  # noqa: F401,F403

import html

import occultations
from engine import constellation_at

_OCC_COLUMNS = ("date", "asteroid", "star", "where", "duration", "alt")
_OCC_DISTANCES = (25, 50, 100, 200, 500)
_OCC_MONTHS = (3, 6, 12)
_OCC_ROLE = Qt.ItemDataRole.UserRole + 11
_OWC_URL = "https://cloud.occultwatcher.net/"
_DAYS_PER_MONTH = 30.44
_EPOCH = datetime(2000, 1, 1)  # the date column sorts by seconds since then (UT)


class OccultationSpace:
    # ── The page ──────────────────────────────────────────────────────────

    def _build_occultations_tab(self):
        page, _inner, lay = _scroll_page()                       # a phone: the page scrolls
        lay.setSpacing(12)
        lay.addWidget(_label(t("occultations.intro"), "corps", tone="attenuee", wrap=True))

        bar = QBoxLayout(QBoxLayout.Direction.LeftToRight)     # a phone: two rows
        bar.setSpacing(8)
        choices = QHBoxLayout()
        choices.setSpacing(8)
        self._occ_distance = QComboBox()
        for km in _OCC_DISTANCES:
            self._occ_distance.addItem(tf("occultations.km", value=km), km)
        self._occ_distance.setCurrentIndex(max(0, self._occ_distance.findData(int(_pref_float("occultation_km", 100)))))
        self._occ_distance.setToolTip(t("occultations.distance_tip"))
        choices.addWidget(InputField(t("occultations.distance"), self._occ_distance), stretch=1)
        self._occ_months = QComboBox()
        for months in _OCC_MONTHS:
            self._occ_months.addItem(tf("occultations.months", n=months), months)
        self._occ_months.setCurrentIndex(max(0, self._occ_months.findData(int(_pref_float("occultation_months", 6)))))
        choices.addWidget(InputField(t("occultations.period"), self._occ_months), stretch=1)
        bar.addLayout(choices)
        rest = QHBoxLayout()
        rest.setSpacing(8)
        self._occ_refresh_btn = _button(t("occultations.refresh"), "reset", compact=True)
        self._occ_refresh_btn.setToolTip(t("occultations.refresh_tip"))
        self._occ_refresh_btn.clicked.connect(lambda _c=False: self._refresh_occultations(force=True))
        rest.addWidget(self._occ_refresh_btn, alignment=Qt.AlignmentFlag.AlignBottom)
        self._occ_owc_btn = _button(t("occultations.owc"), "cloud", "discret", compact=True)
        self._occ_owc_btn.setToolTip(t("occultations.owc_tip"))
        self._occ_owc_btn.clicked.connect(lambda _c=False: _open_url(_OWC_URL))
        rest.addWidget(self._occ_owc_btn, alignment=Qt.AlignmentFlag.AlignBottom)
        rest.addStretch()
        bar.addLayout(rest, stretch=1)
        self._reflow.append(bar)
        lay.addLayout(bar)
        self._occ_status = _label("", "legende", tone="attenuee", wrap=True)
        lay.addWidget(self._occ_status)

        table = QTableWidget(0, len(_OCC_COLUMNS))
        table.setHorizontalHeaderLabels([t(f"occultations.col_{key}") for key in _OCC_COLUMNS])
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setWordWrap(False)
        table.setSortingEnabled(True)
        header = table.horizontalHeader()
        for col, key in enumerate(_OCC_COLUMNS):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch if key == "asteroid"
                                        else QHeaderView.ResizeMode.ResizeToContents)
        table.itemSelectionChanged.connect(self._occ_selection_changed)
        table.setMinimumHeight(240)
        self._occ_table = table
        lay.addWidget(table, stretch=1)
        self._occ_details = _label("", "corps", wrap=True)
        self._occ_details.setTextFormat(Qt.TextFormat.RichText)
        self._occ_details.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(self._occ_details)
        lay.addWidget(_label(t("occultations.credit"), "legende", tone="attenuee", wrap=True))

        self._occ_distance.currentIndexChanged.connect(lambda _i: self._occ_choice_changed())
        self._occ_months.currentIndexChanged.connect(lambda _i: self._occ_choice_changed())
        self._compact_hooks.append(self._occ_compact)
        self._occ_found, self._occ_key, self._occ_busy = [], None, False
        self._occultations_page = page
        self._add_page(page, t("tabs.occultations"))

    def _occ_compact(self, compact):
        """On a phone: two columns, the date without the year and the asteroid with where its band passes."""
        self._occ_short = compact
        table = self._occ_table
        for col, key in enumerate(_OCC_COLUMNS):
            table.setColumnHidden(col, compact and key not in ("date", "asteroid"))
        self._occ_texts()

    def _occ_cells(self, seen):
        """{column: (text, sort value)} of an occultation's row (shorter on a phone)."""
        event = seen["event"]
        local = self._local(seen["date"])
        short = getattr(self, "_occ_short", False)
        asteroid = f"{self._occ_asteroid(event)} · {tf('units.km', value=_num(event['diameter_km']))}"
        return {
            "date": (f"{local:%d/%m}{'' if short else f'/{local:%Y}'} {self._fmt_clock(local)}",
                     (seen["date"] - _EPOCH).total_seconds()),
            "asteroid": (f"{self._occ_asteroid(event)} · {self._occ_where(seen, short=True)}" if short else asteroid,
                         event["name"]),
            "star": (tf("occultations.star_cell", mag=_num(event["star_mag"], 1)), event["star_mag"] or 99.0),
            "where": (self._occ_where(seen), seen["edge_km"]),
            "duration": (tf("occultations.seconds", value=_num(seen["duration"], 1)) if seen["inside"] else "—",
                         -seen["duration"]),
            "alt": (f"{_num(seen['alt'])}°", -seen["alt"]),
        }

    def _occ_texts(self):
        """The texts of the rows shown, for the layout (wide or phone)."""
        table = self._occ_table
        for row in range(table.rowCount()):
            first = table.item(row, 0)
            if first is None or first.data(_OCC_ROLE) is None:
                continue
            seen = self._occ_found[first.data(_OCC_ROLE)]
            cells = self._occ_cells(seen)
            for col, key in enumerate(_OCC_COLUMNS):
                table.item(row, col).setText(cells[key][0])
            asteroid = table.item(row, _OCC_COLUMNS.index("asteroid"))       # gold over the place, on a phone
            if seen["inside"] and getattr(self, "_occ_short", False):
                asteroid.setForeground(QBrush(QColor(Config.OR)))
            else:
                asteroid.setData(Qt.ItemDataRole.ForegroundRole, None)

    def _occ_choice_changed(self):
        prefs.set("occultation_km", self._occ_distance.currentData())
        prefs.set("occultation_months", self._occ_months.currentData())
        self._refresh_occultations()

    # ── Finding them (in the background) ─────────────────────────────────

    def _refresh_occultations(self, force=False):
        """The events near the place for the distance and the months chosen, from the
        date of the calculation: the predictions downloaded if needed, then searched,
        in the background."""
        if self._occ_busy or self._lat is None or self._dte is None:
            return
        km, months = self._occ_distance.currentData(), self._occ_months.currentData()
        start = self._dte.replace(tzinfo=None)                    # from the date of the calculation
        end = start + timedelta(days=months * _DAYS_PER_MONTH)
        lat, lon, elev = self._lat, self._lon, self._elevation()
        key = (start.date(), round(lat, 4), round(lon, 4), elev, km, months, occultations.cache_stamp())
        if not force and key == self._occ_key:
            return
        self._occ_busy = True
        self._occ_refresh_btn.setEnabled(False)
        self._occ_status.setText(t("occultations.loading"))
        years = occultations.years_between(start, end)

        def work():
            events, missing = occultations.refresh(years)
            found = occultations.near(events, lat, lon, elev, start, end, max_km=km)
            occultations.moonlight(found)
            for seen in found:
                event = seen["event"]
                seen["constellation"] = constellation_at(event["ra2000"], event["dec2000"],
                                                         AstroEngine.julian_day(seen["date"]))
            return found, missing

        def done(answer):
            found, missing = answer
            self._occ_busy = False
            self._occ_refresh_btn.setEnabled(True)
            self._occ_key = (*key[:-1], occultations.cache_stamp())
            self._occ_found = found
            self._show_occultations(km, months, missing)

        def failed(exc):
            self._occ_busy = False
            self._occ_refresh_btn.setEnabled(True)
            self._occ_status.setText(tf("occultations.error", detail=str(exc)))
        common._run_in_background(work, done, failed)

    # ── Showing them ──────────────────────────────────────────────────────

    def _occ_asteroid(self, event):
        return f"({event['number']}) {event['name']}" if event["number"] else event["name"]

    def _occ_where(self, seen, short=False):
        if seen["inside"]:
            return t("occultations.inside")
        return tf("occultations.outside_short" if short else "occultations.outside", km=_num(seen["edge_km"]),
                  dir=self._wind(seen["direction"]))

    def _show_occultations(self, km, months, missing):
        found = self._occ_found
        table = self._occ_table
        table.setSortingEnabled(False)
        table.clearContents()
        table.setRowCount(len(found))
        for row, seen in enumerate(found):
            cells = self._occ_cells(seen)
            for col, key in enumerate(_OCC_COLUMNS):
                text, sort = cells[key]
                item = _SortItem(text)
                item.setData(_OCC_ROLE, row)
                item.setData(_SORT_ROLE, sort)
                if seen["inside"] and key == "where":
                    item.setForeground(QBrush(QColor(Config.OR)))
                table.setItem(row, col, item)
        table.setSortingEnabled(True)
        table.sortItems(0, Qt.SortOrder.AscendingOrder)
        self._occ_texts()
        inside = sum(1 for s in found if s["inside"])
        status = tf(_plural_key("occultations.count", len(found)), n=len(found), km=km, months=months)
        if inside:
            status += " · " + tf(_plural_key("occultations.count_inside", inside), n=inside)
        for year, reason in sorted(missing.items()):
            status += " · " + tf("occultations.missing", year=year, detail=reason)
        self._occ_status.setText(status)
        table.setVisible(bool(found))
        self._occ_details.setText("" if found else html.escape(tf("occultations.none", km=km), quote=False))
        if found:
            table.selectRow(0)

    def _occ_selected(self):
        items = self._occ_table.selectedItems()
        if not items:
            return None
        index = items[0].data(_OCC_ROLE)
        return self._occ_found[index] if index is not None and index < len(self._occ_found) else None

    def _occ_selection_changed(self):
        seen = self._occ_selected()
        if seen is not None:
            self._occ_details.setText(_rich_lines(self._occ_detail_lines(seen)))

    def _occ_detail_lines(self, seen):
        """The chosen occultation in words: when, where the band passes, the star, the Moon, the source."""
        event = seen["event"]
        local = self._local(seen["date"])
        zone = getattr(self._zone, "key", "UTC") if self._zone else "UTC"
        lines = [tf("occultations.details_title", asteroid=self._occ_asteroid(event), star=event["star"]),
                 tf("occultations.details_when", date=f"{local:%d/%m/%Y}", time=self._fmt_clock(local), zone=zone,
                    alt=_num(seen["alt"]), dir=self._wind(seen["az"]))]
        width = _num(2 * seen["half_width_km"])
        if seen["inside"]:
            lines.append(tf("occultations.details_inside", distance=_num(seen["distance_km"]), width=width,
                            duration=_num(seen["duration"], 1)))
        else:
            lines.append(tf("occultations.details_outside", edge=_num(seen["edge_km"]),
                            dir=self._wind(seen["direction"]), distance=_num(seen["distance_km"]), width=width))
        constellation = seen.get("constellation")
        lines.append(tf("occultations.details_star", mag=_num(event["star_mag"], 1),
                        ra=_ra(event["ra2000"]), dec=_dec(event["dec2000"]),
                        constellation=t(f"constellations.{constellation}") if constellation else "—",
                        drop=_num(seen["drop"], 1) if seen["drop"] is not None else "—",
                        diameter=_num(event["diameter_km"]), amag=_num(event["mag"], 1) if event["mag"] else "—"))
        if "moon_fraction" in seen:
            lines.append(tf("occultations.details_moon", pct=_num(100 * seen["moon_fraction"]),
                            sep=_num(seen["moon_separation"])))
        lines.append(tf("occultations.details_source", orbit=event["orbit"].split(":")[0]))
        return lines
