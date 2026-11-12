"""
ui/calendar_tab.py — Calendrier: events, eclipses, satellite passes, the lunar and astronomical calendars.

A mixin of the main window (gui.AstroApp): its methods use the window's state
(self.*) and those of the other spaces.
"""
from ui import common
from ui.common import *  # noqa: F401,F403


class CalendarSpace:
    # ── Tab 7: events ─────────────────────────────────────────────────────────

    def _build_events_tab(self):
        page = QWidget()
        page.setObjectName("page")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 16, 0, 0)
        lay.setSpacing(16)

        bar = QHBoxLayout()
        bar.setSpacing(8)
        btn_cal = _button(t("astro_calendar.button"), "calendar", "secondaire")
        btn_cal.setToolTip(t("astro_calendar.button_tip"))
        btn_cal.clicked.connect(lambda _c=False: self.show_calendar())
        bar.addWidget(btn_cal)
        btn_ecl = _button(t("events.search_eclipses"), "search")
        btn_ecl.clicked.connect(self._search_eclipses_gui)
        btn_conj = _button(t("events.search_conjunctions"), "search")
        btn_conj.clicked.connect(self._search_conjunctions_gui)
        btn_sat = _button(t("satellites.search"), "search")
        btn_sat.setToolTip(t("satellites.search_tip"))
        btn_sat.clicked.connect(self._search_satellites_gui)
        bar.addWidget(btn_ecl)
        bar.addWidget(btn_conj)
        bar.addWidget(btn_sat)
        bar.addStretch()
        self._btn_ics = _button(t("events.export_ics"), "export")
        self._btn_ics.setToolTip(t("events.export_tip"))
        self._btn_ics.setEnabled(False)
        self._btn_ics.clicked.connect(self._export_ics)
        bar.addWidget(self._btn_ics)
        lay.addLayout(bar)
        options = QHBoxLayout()
        self._sat_visual = QCheckBox(t("satellites.visual"))
        self._sat_visual.setToolTip(t("satellites.visual_tip"))
        self._sat_visual.setChecked(bool(prefs.get("satellites_visual")))
        self._sat_visual.toggled.connect(lambda v: prefs.set("satellites_visual", bool(v)))
        options.addStretch()
        options.addWidget(self._sat_visual)
        lay.addLayout(options)

        # filters of the year's events
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
        self._events_page = page
        self._add_page(page, t("tabs.events"))

    # ──────────────────────────────────────────────────────────────────────────
    # UPDATING THE CARDS
    # ──────────────────────────────────────────────────────────────────────────

    def _events_title(self):
        return tf("common.events_title", offset=_fmt_offset(self.utc_offset))

    # ── Lunar calendar ────────────────────────────────────────────────────────

    def _show_moon_calendar(self, year=None, month=None):
        """Window (non-modal): the Moon day by day over a month, seen from here."""
        if not self._check_inputs():
            self._warn_invalid_coords()
            return
        local = self._local(self._dte or _utc_now())
        dlg = getattr(self, "_calendar_dialog", None)
        if dlg is None:
            dlg = QDialog(self)
            dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
            dlg.setWindowTitle(t("calendar.window_title"))
            dlg.resize(980, 720)
            lay = QVBoxLayout(dlg)
            lay.setContentsMargins(24, 24, 24, 16)
            lay.setSpacing(12)
            head = QHBoxLayout()
            prev = _icon_button("previous", t("calendar.previous"))
            nxt = _icon_button("next", t("calendar.next"))
            prev.clicked.connect(lambda: self._fill_moon_calendar(-1))
            nxt.clicked.connect(lambda: self._fill_moon_calendar(+1))
            dlg._title = _label("", "sous-titre")
            head.addWidget(prev)
            head.addWidget(dlg._title)
            head.addWidget(nxt)
            head.addStretch()
            lay.addLayout(head)
            dlg._grid = QGridLayout()
            dlg._grid.setSpacing(6)
            lay.addLayout(dlg._grid, stretch=1)
            dlg._note = _label("", "legende", tone="attenuee", wrap=True)
            lay.addWidget(dlg._note)
            buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
            buttons.rejected.connect(dlg.reject)
            lay.addWidget(buttons)
            dlg.destroyed.connect(lambda *_: setattr(self, "_calendar_dialog", None))
            self._calendar_dialog = dlg
        dlg._month = (year or local.year, month or local.month)
        self._fill_moon_calendar(0)
        dlg.show()
        dlg.raise_()

    def _fill_moon_calendar(self, step):
        """Fills the grid of the month shown, moved by *step* months."""
        dlg = self._calendar_dialog
        year, month = dlg._month
        month += step
        year, month = year + (month - 1) // 12, (month - 1) % 12 + 1
        dlg._month = (year, month)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            days = AstroEngine.moon_calendar(year, month, self._lat, self._lon, self._elevation(), self._zone)
        finally:
            QApplication.restoreOverrideCursor()
        grid = dlg._grid
        while grid.count():
            item = grid.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()
        loc = _locale()
        name = loc.standaloneMonthName(month, QLocale.FormatType.LongFormat)
        dlg._title.setText(f"{name[:1].upper()}{name[1:]} {year}")
        first = loc.firstDayOfWeek().value                # 1 Monday … 7 Sunday
        for col in range(7):
            day = (first - 1 + col) % 7 + 1
            head = _label(loc.standaloneDayName(day, QLocale.FormatType.ShortFormat), "legende",
                          tone="attenuee")
            head.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(head, 0, col)
        offset = (days[0]["date"].isoweekday() - first) % 7
        today = self._local(self._dte).date() if self._dte else None
        southern = (self._lat or 0) < 0
        for i, d in enumerate(days):
            cell = _card()
            cell.setProperty("calendarDay", True)
            box = QVBoxLayout(cell)
            box.setContentsMargins(8, 6, 8, 6)
            box.setSpacing(2)
            top = QHBoxLayout()
            top.addWidget(_label(str(d["date"].day), "corps", tone="or" if d["date"] == today else None,
                                 strong=True))
            top.addStretch()
            disc = MoonPhase(26)
            disc.set_phase(d["phase"], southern=southern)
            top.addWidget(disc)
            box.addLayout(top)
            box.addWidget(_label(f"{_num(100.0 * d['fraction'])} %", "legende"))
            rise = self._clock(d["rise"]) if d["rise"] else "—"
            sets = self._clock(d["set"]) if d["set"] else "—"
            times = _label(f"↑ {rise}   ↓ {sets}", "legende", tone="attenuee")
            times.setToolTip(t("calendar.rise_set_tip"))
            box.addWidget(times)
            if d["event"]:
                ev = d["event"]
                box.addWidget(_label(f"{t('phases.' + ev['kind'])} {self._clock(ev['time'])}", "legende",
                                     tone="lune", strong=True))
            box.addStretch()
            grid.addWidget(cell, 1 + (offset + i) // 7, (offset + i) % 7)
        for row in range(1, 7):
            grid.setRowStretch(row, 1)
        for col in range(7):
            grid.setColumnStretch(col, 1)
            grid.setColumnMinimumWidth(col, 110)
        dlg._note.setText(tf("calendar.note", zone=getattr(self._zone, "key", "UTC"),
                             place=self.location_name or f"{_fmt_lat(self._lat)}, {_fmt_lon(self._lon)}"))

    # ──────────────────────────────────────────────────────────────────────────
    # EVENTS
    # ──────────────────────────────────────────────────────────────────────────

    def _clear_evt_layout(self):
        while self._evt_layout.count():
            item = self._evt_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()           # deleteLater only acts back in the event loop
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

    def _event_card(self, symbol, accent, title, when, pills=(), details=(), action=None, lines=()):
        """Event card: symbol, title, badges, date; details below; *action*:
        (text, function) of a button on the right."""
        card = _card()
        card.setObjectName("card")
        card.setProperty("eventCard", True)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(6)
        top = QHBoxLayout()
        top.setSpacing(8)
        top.addWidget(_label(symbol, "symbol", tone=accent))
        top.addWidget(_label(title, "corps", strong=True))
        for text, tone in pills:
            top.addWidget(_badge(text, tone))
        top.addStretch()
        top.addWidget(_label(when, "donnee"))
        if action:
            btn = _button(action[0], "place", "secondaire", compact=True)
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
        """"2 min 15 s"."""
        value = int(round(value))
        return f"{value // 60} min {value % 60:02d} s"

    def _eclipse_local_lines(self, ec, loc):
        """Local circumstances of an eclipse, in the place's time."""
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
        """Searches and shows the eclipses of the next 12 months."""
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
            greatest = ec.get("greatest", ec["date"]) + timedelta(seconds=30)  # nearest minute
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
        """Window: the eclipse projected on the ground (path, central line, partiality)."""
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
        dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)           # and its figure with it
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

    # ── Events of the year: planets, minor planets, Moon, seasons ─────────────

    _EVENT_GROUPS = ("planets", "minor", "comets", "moon", "seasons", "meteors")
    _WINDS = ("n", "ne", "e", "se", "s", "sw", "w", "nw")

    def _body_name(self, name, symbol=False):
        """Name of a body of the events: planet, Sun, Moon or star."""
        if name in ("Sun", "Moon"):
            text = t(f"chart.{name.lower()}")
            return f"{SYMBOL[name]} {text}" if symbol else text
        if name in AstroEngine.MOON_STARS:
            return t(f"events.star_{name.lower()}")
        return _planet_name(name, symbol=symbol)

    def _event_title(self, ev, symbol=True):
        """Title of an event of the year."""
        kind = ev["type"]
        if kind == "season":
            return t(f"events.{ev['kind']}")
        if kind == "meteor_shower":
            return tf("meteors.title", name=t(f"meteors.name_{ev['kind']}"))
        if kind.startswith("comet_"):
            return tf(f"events.{kind}", comet=_planet_name(ev["bodies"][0], symbol=symbol, numbered=True))
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
        """"06/01/2026 16:36 UT": the instant to the nearest minute."""
        return (dt + timedelta(seconds=30)).strftime("%d/%m/%Y %H:%M") + f" {t('chart.ut')}"

    def _clock(self, dt):
        """Local time of the place, to the nearest minute."""
        return self._fmt_clock(self._local(dt + timedelta(seconds=30)))

    @staticmethod
    def _elide(text):
        """"de Uranus" → "d'Uranus" in French."""
        if get_lang() != "fr":
            return text
        return re.sub(r"\bde (?=[AEIOUYÉÈÊaeiouyéèê])", "d'", text)

    def _visibility_text(self, vis):
        if vis["period"] is None:
            return t(f"events.invisible_{vis['reason']}")
        wind = self._WINDS[int(round(vis["az"] / 45.0)) % 8]
        return tf(f"events.visible_{vis['period']}", alt=_num(vis["alt"]),
                  dir=t(f"skymap.cardinal_{wind}"), time=self._clock(vis["best"]))

    def _meteor_lines(self, vis):
        """The night of the peak from here: best moment (radiant, expected rate), then the Moon."""
        if vis["period"] is None:
            first = t(f"events.invisible_{vis['reason']}")
        else:
            wind = self._WINDS[int(round(vis["az"] / 45.0)) % 8]
            first = tf("meteors.best", time=self._clock(vis["best"]), alt=_num(vis["alt"]),
                       dir=t(f"skymap.cardinal_{wind}"), rate=vis["rate"])
        moon = vis["moon"]
        if moon == "none":
            moon_text = t("meteors.moon_new" if vis["moon_fraction"] < 0.1 else "meteors.moon_set")
        else:
            moon_text = tf(f"meteors.moon_{moon}", pct=_num(100.0 * vis["moon_fraction"]))
        return [first, moon_text]

    def _wind(self, az):
        """Compass point of an azimuth, in the active language ("SO")."""
        return t(f"skymap.cardinal_{self._WINDS[int(round(az / 45.0)) % 8]}")

    # ── Satellite passes ─────────────────────────────────────────────────────

    def _search_satellites_gui(self):
        """Visible passes of the ISS, Tiangong and Hubble over the next 10 days; the
        orbits are downloaded in the background when older than two days."""
        dte = self._search_start("satellites")
        self._evt_layout.addWidget(_label(t("satellites.loading"), "legende", tone="attenuee"))

        lat, lon, elevation = self._lat, self._lon, self._elevation()
        visual_wanted = bool(prefs.get("satellites_visual"))

        def work():
            """In the background: the orbits, then the passes (150 satellites take a few seconds)."""
            elements, error = satellites.refresh()
            followed = dict(elements)
            if visual_wanted:
                visual, visual_error = satellites.refresh_visual()
                elements = satellites.with_visual(elements, visual)
                error = error or visual_error
            if not elements:
                return elements, error, []
            passes = AstroEngine.satellite_passes(elements, dte, lat, lon, elevation)
            if visual_wanted:                             # the others: only their high passes
                passes = [p for p in passes if p["name"] in followed or p["max_alt"] >= 40.0]
            return elements, error, passes

        def done(result):
            elements, error, passes = result
            QApplication.restoreOverrideCursor()
            if self._last_search != "satellites":
                return
            self._clear_evt_layout()
            if not elements:
                self._search_failed(error or t("satellites.no_elements"))
                return
            self._render_satellites(dte, passes, {k: v for k, v in elements.items()
                                                  if k in satellites.SATELLITES}, error)
            _TONIGHT_CACHE.clear()                        # "Tonight" can now show the passes
            self._tonight_key = None
            self._update_tonight(self._dte, self._lat, self._lon, self._elevation())

        def failed(exc):
            QApplication.restoreOverrideCursor()
            if self._last_search == "satellites":
                self._clear_evt_layout()
                self._search_failed(exc)
        common._run_in_background(work, done, failed)

    def _render_satellites(self, dte, passes, elements, error=None):
        n = len(passes)
        age = satellites.epoch_age_days(elements)
        note = tf("satellites.note", days=_num(age, 1))
        if error is not None:
            note += " " + tf("satellites.not_refreshed", detail=error)
        if age > satellites.STALE_DAYS:
            note += " " + t("satellites.too_old")
        self._events_header(tf("satellites.title", date=dte.strftime("%d/%m/%Y")),
                            tf(_plural_key("satellites.count", n), n=n), note)
        if not passes:
            self._evt_layout.addWidget(_label(t("satellites.none"), "corps", tone="attenuee", wrap=True))
        for p in passes:
            clock = self._clock
            first = tf("satellites.from_shadow" if p["from_shadow"] else "satellites.appears",
                       time=clock(p["start"]), alt=_num(p["start_alt"]), dir=self._wind(p["start_az"]))
            top = tf("satellites.highest", time=clock(p["max"]), alt=_num(p["max_alt"]),
                     dir=self._wind(p["max_az"]))
            last = tf("satellites.into_shadow" if p["into_shadow"] else "satellites.vanishes",
                      time=clock(p["end"]), alt=_num(p["end_alt"]), dir=self._wind(p["end_az"]))
            seconds = int(round((p["end"] - p["start"]).total_seconds()))
            details = [tf("satellites.duration", min=seconds // 60, s=f"{seconds % 60:02d}")]
            local = self._local(p["start"])
            if local != p["start"].replace(tzinfo=None):
                details.append(tf("events.local_time", time=f"{local:%d/%m} {self._fmt_clock(local)}",
                                  zone=getattr(self._zone, "key", "UTC")))
            pills = [(t("satellites.overhead"), "info")] if p["max_alt"] >= 60.0 else []
            title = _satellite_name(p["name"])
            self._event_card(SYMBOL["dot"], "attenuee", title, self._event_when(p["start"]), pills, details,
                             None, [f"{first} · {top} · {last}"])
            self._ics_add(p["start"], p["end"], title, details + [f"{first} · {top} · {last}"])
        self._evt_layout.addStretch()
        self._btn_ics.setEnabled(bool(self._ics_items))

    def _event_shown(self, ev):
        if not self._evt_filters[ev.get("group", "planets")].isChecked():
            return False
        vis = ev.get("visibility")
        return not (self._evt_filters["visible"].isChecked() and vis is not None and vis["period"] is None)

    # ── Astronomical calendar ─────────────────────────────────────────────

    _CAL_SYMBOLS = {"phases": "Moon", "eclipses": "Sun", "planets": "conjunction", "minor": "conjunction",
                    "comets": "meteors", "moon": "Moon", "seasons": "Sun", "meteors": "meteors",
                    "variables": "star", "satellites": "star"}

    def _calendar_title(self, item):
        """Title of an event of the calendar, in the interface language."""
        cat, ev = item["category"], item["event"]
        if cat == "phases":
            return t(f"phases.{item['kind']}")
        if cat == "eclipses":
            title = t("events.solar_eclipse" if ev["type"] == "solar" else "events.lunar_eclipse")
            return f"{title} ({t('events.subtype_' + ev['sub_type'])})"
        if cat == "satellites":
            return tf("astro_calendar.pass", name=_satellite_name(ev["name"], short=True))
        if cat == "variables":
            return t("variables.algol_minimum")
        return self._event_title(ev, symbol=False)

    def _calendar_symbol(self, item):
        ev = item["event"]
        if item["category"] == "eclipses":
            return SYMBOL["Sun" if ev["type"] == "solar" else "Moon"]
        if item["category"] in ("planets", "minor") and ev.get("type") == "opposition":
            return SYMBOL["opposition"]
        return SYMBOL[self._CAL_SYMBOLS[item["category"]]]

    def _calendar_details(self, item):
        """The lines under an event of the day: time, visibility, the engine's figures."""
        ev, lines = item["event"], []
        when = self._local(item["date"] + timedelta(seconds=30))
        lines.append(tf("astro_calendar.at", time=self._fmt_clock(when),
                        zone=getattr(self._zone, "key", "UTC") if self._zone else "UTC"))
        if item["category"] == "eclipses":
            lines += self._eclipse_details(ev)
        elif item["category"] == "satellites":
            lines.append(tf("satellites.highest", time=self._clock(ev["max"]), alt=_num(ev["max_alt"]),
                            dir=self._wind(ev["max_az"])))
        elif item["category"] == "variables":
            lines.append(tf("variables.algol_details", alt=_num(ev["alt"]), dir=self._wind(ev["az"]),
                            uncertainty=variables.UNCERTAINTY_MIN))
        else:
            vis = ev.get("visibility")
            if vis is not None and item["category"] not in ("phases", "seasons"):
                lines.append(self._visibility_text(vis) if item["kind"] != "meteor_shower"
                             else " · ".join(self._meteor_lines(vis)))
        return lines

    def show_calendar(self):
        """The calendar view of the Events tab: every event of a period (a year by default),
        by category, in a month grid; the day's events below; the .ics export of what the
        filters let through."""
        self._last_search = "calendar"
        self._ics_items = []
        self._btn_ics.setEnabled(False)
        self._evt_filter_bar.setVisible(False)
        self._clear_evt_layout()
        cal = getattr(self, "_cal_state", None)
        local_now = self._local(self._edit_datetime())
        if cal is None:
            start = local_now.date()
            cal = {"start": start, "end": start.replace(year=start.year + 1) if not (start.month == 2 and start.day == 29)
                   else start + timedelta(days=365), "items": None, "key": None,
                   "month": (start.year, start.month), "day": start,
                   "shown": {c: c != "satellites" or bool(satellites.load()) for c in astro_calendar.CATEGORIES}}
            self._cal_state = cal

        controls = QHBoxLayout()
        controls.setSpacing(12)
        start_edit, end_edit = QDateEdit(), QDateEdit()
        for edit, value in ((start_edit, cal["start"]), (end_edit, cal["end"])):
            edit.setCalendarPopup(True)
            edit.setDisplayFormat("dd/MM/yyyy")
            edit.setMinimumDate(QDate(EPHEMERIS_YEARS[0], 1, 1))
            edit.setMaximumDate(QDate(EPHEMERIS_YEARS[1], 12, 31))
            edit.setDate(QDate(value.year, value.month, value.day))
        controls.addWidget(InputField(t("astro_calendar.from"), start_edit))
        controls.addWidget(InputField(t("astro_calendar.to"), end_edit))
        compute = _button(t("astro_calendar.compute"), "calculate", "principal", compact=True)
        compute.setToolTip(t("astro_calendar.compute_tip"))
        controls.addWidget(compute, alignment=Qt.AlignmentFlag.AlignBottom)
        controls.addStretch()
        holder = QWidget()
        holder.setLayout(controls)
        self._evt_layout.addWidget(holder)

        filters = QWidget()
        frow = QGridLayout(filters)
        frow.setContentsMargins(0, 0, 0, 0)
        frow.setHorizontalSpacing(16)
        frow.setVerticalSpacing(4)
        boxes = {}
        for n, key in enumerate(astro_calendar.CATEGORIES):
            box = QCheckBox(t(f"astro_calendar.cat_{key}"))
            box.setChecked(cal["shown"][key])
            boxes[key] = box
            frow.addWidget(box, n // 5, n % 5)
        frow.setColumnStretch(5, 1)
        self._evt_layout.addWidget(filters)

        nav = QHBoxLayout()
        prev_btn = _icon_button("previous", t("astro_calendar.previous"), compact=True)
        next_btn = _icon_button("next", t("astro_calendar.next"), compact=True)
        month_label = _label("", "sous-titre")
        nav.addWidget(prev_btn)
        nav.addWidget(month_label)
        nav.addWidget(next_btn)
        nav.addStretch()
        status = _label("", "legende", wrap=True)
        nav.addWidget(status, stretch=1)
        nav_holder = QWidget()
        nav_holder.setLayout(nav)
        self._evt_layout.addWidget(nav_holder)

        grid_card = _card()
        grid = QGridLayout(grid_card)
        grid.setContentsMargins(8, 8, 8, 8)
        grid.setSpacing(4)
        for d in range(7):
            head = _label(t(f"astro_calendar.weekday_{d}"), "legende")
            head.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(head, 0, d)
        cells = []
        for w in range(6):
            for d in range(7):
                cell = _DayCell(lambda day: choose_day(day))
                grid.addWidget(cell, w + 1, d)
                cells.append(cell)
        for d in range(7):
            grid.setColumnStretch(d, 1)
        self._evt_layout.addWidget(grid_card)
        day_title = _label("", "label", strong=True)
        self._evt_layout.addWidget(day_title)
        day_box = QVBoxLayout()
        day_box.setSpacing(6)
        day_holder = QWidget()
        day_holder.setLayout(day_box)
        self._evt_layout.addWidget(day_holder)
        self._evt_layout.addStretch()
        self._cal_widgets = {"cells": cells, "month": month_label, "status": status, "boxes": boxes,
                             "start": start_edit, "end": end_edit, "day_title": day_title, "day_box": day_box}

        def shown_items():
            return [i for i in (cal["items"] or []) if boxes[i["category"]].isChecked()]

        def fill_day():
            while day_box.count():
                w = day_box.takeAt(0).widget()
                if w is not None:
                    w.deleteLater()
            day = cal["day"]
            items = [i for i in shown_items() if self._local(i["date"]).date() == day]
            day_title.setText(tf("astro_calendar.day_title", date=day.strftime("%d/%m/%Y"), n=len(items)))
            for item in items:
                row = _card()
                lay = QVBoxLayout(row)
                lay.setContentsMargins(12, 8, 12, 8)
                lay.setSpacing(2)
                lay.addWidget(_label(f"{self._calendar_symbol(item)}  {self._calendar_title(item)}", "corps",
                                     strong=True))
                for line in self._calendar_details(item):
                    if line:
                        lay.addWidget(_label(line, "legende", wrap=True))
                day_box.addWidget(row)

        def fill_month():
            year, month = cal["month"]
            month_label.setText(f"{t(f'workshop.month_{month}')} {year}")
            days = astro_calendar.by_day(shown_items(), self._local)
            for cell, day in zip(cells, [d for week in astro_calendar.month_grid(year, month) for d in week]):
                items = days.get(day, [])
                lines = []
                for item in items[:3]:
                    title = self._calendar_title(item)
                    lines.append(f"{self._calendar_symbol(item)} {title if len(title) <= 22 else title[:21] + '…'}")
                if len(items) > 3:
                    lines.append(tf("astro_calendar.more", n=len(items) - 3))
                tip = "\n".join(f"{self._clock(i['date'])}  {self._calendar_title(i)}" for i in items)
                cell.show_day(day, str(day.day), lines, tip, day.month == month, day == cal["day"])
            self._ics_items = []
            for item in shown_items():
                end = item["end"] or item["date"] + timedelta(minutes=1)
                self._ics_add(item["date"], end, self._calendar_title(item), self._calendar_details(item))
            self._btn_ics.setEnabled(bool(self._ics_items))
            fill_day()

        def choose_day(day):
            cal["day"] = day
            fill_month()

        def turn(step):
            year, month = cal["month"]
            month += step
            year, month = year + (month - 1) // 12, (month - 1) % 12 + 1
            cal["month"] = (year, month)
            fill_month()

        def toggled():
            for key, box in boxes.items():
                cal["shown"][key] = box.isChecked()
            fill_month()

        def run():
            a, b = start_edit.date(), end_edit.date()
            first = datetime(a.year(), a.month(), a.day())
            last = datetime(b.year(), b.month(), b.day()) + timedelta(days=1)
            if last <= first:
                status.setText(t("astro_calendar.bad_period"))
                return
            cal["start"], cal["end"] = first.date(), (last - timedelta(days=1)).date()
            zone = self._zone
            start_ut = first.replace(tzinfo=zone).astimezone(timezone.utc).replace(tzinfo=None) if zone else first
            end_ut = last.replace(tzinfo=zone).astimezone(timezone.utc).replace(tzinfo=None) if zone else last
            key = (start_ut, end_ut, self._lat, self._lon)
            if cal["key"] == key and cal["items"] is not None:
                fill_month()
                return
            elements = satellites.load()
            if elements and satellites.epoch_age_days(elements) > satellites.STALE_DAYS:
                elements = None
            lat, lon, elev = self._lat, self._lon, self._elevation()
            status.setText(t("astro_calendar.computing"))
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

            def done(items):
                QApplication.restoreOverrideCursor()
                cal["items"], cal["key"] = items, key
                if self._last_search == "calendar":
                    status.setText(tf("astro_calendar.found", n=len(items), start=cal["start"].strftime("%d/%m/%Y"),
                                      end=cal["end"].strftime("%d/%m/%Y")))
                    fill_month()

            def failed(exc):
                QApplication.restoreOverrideCursor()
                status.setText(tf("events.search_error", detail=exc))
            common._run_in_background(lambda: astro_calendar.collect(start_ut, end_ut, lat, lon, elev, zone, elements),
                               done, failed)

        prev_btn.clicked.connect(lambda _c=False: turn(-1))
        next_btn.clicked.connect(lambda _c=False: turn(1))
        compute.clicked.connect(lambda _c=False: run())
        for box in boxes.values():
            box.toggled.connect(lambda _v: toggled())
        self._cal_run, self._cal_turn, self._cal_choose = run, turn, choose_day
        if cal["items"] is None:
            run()
        else:
            status.setText(tf("astro_calendar.found", n=len(cal["items"]), start=cal["start"].strftime("%d/%m/%Y"),
                              end=cal["end"].strftime("%d/%m/%Y")))
            fill_month()

    def _search_conjunctions_gui(self):
        """Searches the events of 12 months: conjunctions, oppositions and
        elongations, minor planets, Moon, seasons, meteor showers; their
        visibility from here."""
        dte = self._search_start("conjunctions")
        try:
            events = (AstroEngine.find_conjunctions(dte, num_days=365)
                      + AstroEngine.find_moon_events(dte, num_days=365)
                      + AstroEngine.find_seasons(dte, num_days=365)
                      + AstroEngine.find_meteor_showers(dte, num_days=365)
                      + AstroEngine.find_comet_events(dte, num_days=365))
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
        """Shows the events found that the filters let through."""
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
            symbol = SYMBOL["Sun"]
        elif kind == "meteor_shower":
            symbol = SYMBOL["meteors"]
            (m1, d1), (m2, d2) = ev["activity"]
            details += [tf("meteors.zhr", value=ev["zhr"]), tf("meteors.speed", value=ev["velocity"]),
                        tf("meteors.activity", start=f"{d1:02d}/{m1:02d}", end=f"{d2:02d}/{m2:02d}")]
        elif kind.startswith("comet_"):
            symbol = SYMBOL[a]
            if kind != "comet_brightest":
                key = "events.distance_au" if kind == "comet_perihelion" else "events.distance_earth"
                details.append(tf(key, value=_num(ev["distance_au"], 3)))
            details.append(tf("events.magnitude", value=_num(ev["mag"], 1)))
        elif kind in ("perihelion", "aphelion"):
            symbol = SYMBOL["Earth"]
            details.append(tf("events.distance_au", value=_num(ev["distance_au"], 5)))
        elif kind in ("perigee", "apogee"):
            symbol = SYMBOL["Moon"]
            details.append(tf("events.distance_km", value=_num(ev["distance_km"])))
            if kind == "perigee" and ev.get("syzygy") == "full":
                pills.append((t("events.supermoon"), "info"))
            elif ev.get("syzygy"):
                details.append(t(f"events.near_{ev['syzygy']}_moon"))
        else:
            sep = ev["separation"]
            if kind == "opposition":
                symbol = SYMBOL["opposition"]
                details.append(tf("events.elongation", value=_num(sep, 1)))
            elif kind == "greatest_elongation":
                symbol = SYMBOL[a]
                details.append(tf("events.elongation", value=_num(sep, 1)))
            else:
                symbol = SYMBOL["conjunction"]
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
        if vis is not None and kind == "meteor_shower":
            lines += self._meteor_lines(vis)
        elif vis is not None and kind not in ("perigee", "apogee"):
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
        self._event_card(symbol, "attenuee", title, self._event_when(ev["date"]), pills, details,
                         action, lines)
        self._ics_add(ev["date"], None, self._event_title(ev, symbol=False), details + lines)

    def _ics_add(self, start, end, summary, details):
        self._ics_items.append((start, end or start + timedelta(minutes=1), summary,
                                "\n".join(details)))

    def _export_ics(self):
        """Saves the shown events to an iCalendar calendar (.ics)."""
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
            common.QMessageBox.warning(self, t("errors.error_title"), tf("events.export_error", detail=exc))
            return
        self.statusBar().showMessage(tf("events.exported", path=path), 8000)

    def _show_event_map(self, ev):
        """Window: paths of the bodies among the stars around the event."""
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
        dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
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
