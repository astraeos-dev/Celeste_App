"""
ui/tonight.py — Ce soir: the ephemeris page (the night ahead, the Sun, the Moon, the bodies).

A mixin of the main window (gui.AstroApp): its methods use the window's state
(self.*) and those of the other spaces.
"""
from ui import common
from ui.common import *  # noqa: F401,F403


class TonightSpace:
    # ── Tab 1: ephemeris ──────────────────────────────────────────────────────

    def _build_ephemeris_tab(self):
        scroll, _page, lay = _scroll_page()

        # The values read at a glance
        cards = QHBoxLayout()
        cards.setSpacing(16)
        self.card_sun_alt = DataCard(t("cards.sun_alt"), SYMBOL["Sun"], "or")
        self.card_sun_rise = DataCard(t("cards.sun_rise"), SYMBOL["Sun"], "or")
        self.card_moon_alt = DataCard(t("cards.moon_alt"), SYMBOL["Moon"], "lune")
        self.card_moon_illum = DataCard(t("cards.moon_illum"), SYMBOL["Moon"], "lune")
        for card in (self.card_sun_alt, self.card_sun_rise, self.card_moon_alt,
                     self.card_moon_illum):
            cards.addWidget(card, stretch=1)
        lay.addLayout(cards)

        # Tonight: the night, the Moon, the visible planets and the next events
        card = _card()
        card.setObjectName("card")
        outer = QVBoxLayout(card)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(6)
        head = QHBoxLayout()
        head.setSpacing(8)
        head.addWidget(_label(SYMBOL["star"], "symbol", tone="or"))
        head.addWidget(_label(t("tonight.title"), "sous-titre"))
        head.addStretch()
        outer.addLayout(head)
        self._tonight_box = QVBoxLayout()
        self._tonight_box.setSpacing(6)
        outer.addLayout(self._tonight_box)
        self._tonight_key = None
        lay.addWidget(card)

        row = QHBoxLayout()
        row.setSpacing(16)

        # Sun
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

        # Moon
        card, body, self._lbl_moon_state = self._body_card(SYMBOL["Moon"], "lune", t("moon.title"))
        btn_calendar = _button(t("calendar.button"), "calendar", "secondaire", compact=True)
        btn_calendar.setToolTip(t("calendar.button_tip"))
        btn_calendar.clicked.connect(lambda _=False: self._show_moon_calendar())
        card.layout().itemAt(0).layout().insertWidget(3, btn_calendar)
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
        self._phase_disc = MoonPhase(56)
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

    def _body_card(self, symbol, accent, title):
        """Card of a body: (card, data grid, state badge)."""
        card = _card()
        outer = QVBoxLayout(card)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(12)
        head = QHBoxLayout()
        head.setSpacing(8)
        head.addWidget(_label(symbol, "symbol", tone=accent))
        head.addWidget(_label(title, "sous-titre"))
        head.addStretch()
        badge = _badge()
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
        Adds a heading (text, QLabel or None), then a "label … value" line per
        field (compact DataCard); returns the next row.
        Field: (key, translation key[, emphasised]).
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
        self.card_sun_alt.set_value(
            _num(sd["alt"], 1, signed=True), "°",
            f"{tf('cards.azimuth', value=_deg(sd['az'], 1))} · {t('sun.state_' + self._sun_phase())}")
        rise, sunset = self.sun_events.get("rise"), self.sun_events.get("set")
        self.card_sun_rise.set_value(
            self._format_event(rise), "",
            tf("cards.set_at", time=self._format_event(sunset)))
        self.card_moon_alt.set_value(
            _num(md["alt"], 1, signed=True), "°",
            f"{tf('cards.rise_at', time=self._format_event(self.moon_events.get('rise')))} · "
            f"{tf('cards.set_at', time=self._format_event(self.moon_events.get('set')))}")
        key = Formatters.PHASES[Formatters.phase_index(md["phase"])][0]
        self.card_moon_illum.set_value(_num(md["illum"], 0), "%", t(f"phases.{key}"))

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
        _set_badge(self._lbl_sun_state, t(f"sun.state_{phase}"),
                      "info" if phase == "day" else "neutre")

    def _update_tonight(self, dte, lat, lon, elev):
        """The "Tonight" summary, computed again when the night, the place or the time zone change."""
        start = AstroEngine._local_day(dte - timedelta(hours=12), self._zone)[0]
        key = (f"{start:%Y-%m-%d %H}", round(lat, 4), round(lon, 4),
               getattr(self._zone, "key", "UTC"), elev)
        if key == self._tonight_key:
            return
        self._tonight_key = key
        self._tonight, self._upcoming = _tonight_and_upcoming(key, dte, lat, lon, elev, self._zone)
        while self._tonight_box.count():
            item = self._tonight_box.takeAt(0)
            if item.widget():
                item.widget().hide()                  # deleteLater() only acts on the next turn
                item.widget().deleteLater()
        for text, tone in self._tonight_lines():
            self._tonight_box.addWidget(_label(text, "corps" if tone is None else "legende",
                                               tone=tone or None, wrap=True))

    def _tonight_lines(self):
        """[(text, tone)] of the summary: the night, the Moon, a line per visible planet, what comes next."""
        n, clock = self._tonight, self._clock
        lines = []
        if n["dark"] is None:
            lines.append((t("tonight.no_night"), None))
        else:
            lines.append((tf(f"tonight.dark_{n['dark']}", start=clock(n["dusk"]), end=clock(n["dawn"])), None))
        moon = n["moon"]
        rise, sets = moon["rise"], moon["set"]
        if rise and sets:
            when = (tf("tonight.moon_rises_sets", rise=clock(rise), set=clock(sets)) if rise < sets
                    else tf("tonight.moon_sets_rises", rise=clock(rise), set=clock(sets)))
        elif rise:
            when = tf("tonight.moon_rises", time=clock(rise))
        elif sets:
            when = tf("tonight.moon_sets", time=clock(sets))
        else:
            when = t("tonight.moon_up" if moon["up"] > 0.5 else "tonight.moon_down")
        lines.append((f"{SYMBOL['Moon']} " + tf("tonight.moon", pct=_num(100.0 * moon["fraction"]), when=when),
                      None))
        if not n["planets"]:
            lines.append((t("tonight.no_planet"), "attenuee"))
        for planet in n["planets"]:
            seen = self._visibility_text(planet)
            text = f"{_planet_name(planet['name'], symbol=True)} · {seen[:1].lower()}{seen[1:]}"
            mag = tf("events.magnitude", value=_num(planet["mag"], 1))
            text += f" · {mag[:1].lower()}{mag[1:]}"
            if planet["rise"]:
                text += " · " + tf("tonight.rises", time=clock(planet["rise"]))
            if planet["set"]:
                text += " · " + tf("tonight.sets", time=clock(planet["set"]))
            lines.append((text, None))
        if n.get("satellites"):
            items = [tf("tonight.satellite_item", name=_satellite_name(p["name"], short=True),
                        start=clock(p["start"]), end=clock(p["end"]), alt=_num(p["max_alt"]),
                        dir=self._wind(p["max_az"])) for p in n["satellites"][:4]]
            lines.append((tf("tonight.satellites", passes=" · ".join(items)), None))
        if n.get("deep_sky"):
            catalog = messier_catalog()
            items = [tf("tonight.deep_sky_item", name=_messier_label(catalog[o["m"] - 1]), alt=_num(o["alt"]),
                        time=clock(o["best"])) for o in n["deep_sky"]]
            lines.append((tf("tonight.deep_sky", objects=" · ".join(items)), None))
        if self._upcoming:
            items = []
            for ev in self._upcoming:
                best = self._local(ev["visibility"]["best"])
                items.append(tf("tonight.event", date=f"{best:%d/%m}", title=self._event_title(ev, symbol=False),
                                when=t(f"tonight.period_{ev['visibility']['period']}")))
            lines.append((tf("tonight.upcoming", events=" · ".join(items)), "attenuee"))
        else:
            lines.append((t("tonight.no_upcoming"), "attenuee"))
        return lines

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
            _set_badge(self._lbl_moon_state, t("common.above_horizon"), "info")
        else:
            _set_badge(self._lbl_moon_state, t("common.below_horizon"), "neutre")
