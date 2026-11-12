"""
ui/settings_tab.py — Settings: the settings tab, themes, languages, favourites place, updates.

A mixin of the main window (gui.AstroApp): its methods use the window's state
(self.*) and those of the other spaces.
"""
from ui import common
from ui.common import *  # noqa: F401,F403


class SettingsSpace:
    # ── Updates ───────────────────────────────────────────────────────────────

    def check_updates(self, interactive=True):
        """
        Looks for a newer version (GitHub Release). *interactive* (button):
        the answer always shows; at startup, only when there is a new version
        the user did not choose to skip.
        """
        if getattr(self, "_update_busy", False):
            return
        self._update_busy = True
        self._update_interactive = interactive
        self._update_info.setText(t("update.checking"))
        common._run_in_background(updater.latest_release, self._on_release, self._on_update_error)

    def _on_release(self, release):
        self._update_busy = False
        interactive = self._update_interactive
        if release is None or not updater.is_newer(release["version"]):
            self._update_info.setText(tf("update.up_to_date", version=_version_text()))
            if interactive:
                self.statusBar().showMessage(tf("update.up_to_date", version=_version_text()), 8000)
            return
        self._update_info.setText(tf("update.available", version=release["version"],
                                       current=_version_text()))
        if interactive or prefs.get("update_skipped") != release["version"]:
            self._show_update_dialog(release)

    def _on_update_error(self, error):
        self._update_busy = False
        self._update_info.setText(tf("update.error", detail=error))
        if self._update_interactive:
            common.QMessageBox.warning(self, t("update.title"), tf("update.error", detail=error))

    def _show_update_dialog(self, release):
        """Window (non-modal): the new version, its notes, and what to do."""
        box = common.QMessageBox(common.QMessageBox.Icon.Information, t("update.title"),
                          tf("update.available", version=release["version"], current=_version_text()),
                          parent=self)
        box.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)           # once closed, it does not stay in memory
        notes = updater.plain_notes(release.get("notes", ""))
        if len(notes) > 800:
            notes = notes[:800].rsplit("\n", 1)[0] + "\n…"
        info = notes or ""
        if not updater.can_self_update():
            info = (info + "\n\n" if info else "") + t("update.from_source")
        box.setInformativeText(info)
        install = None
        if updater.can_self_update():
            install = box.addButton(t("update.install"), common.QMessageBox.ButtonRole.AcceptRole)
        page = box.addButton(t("update.open_page"), common.QMessageBox.ButtonRole.ActionRole)
        skip = box.addButton(t("update.skip"), common.QMessageBox.ButtonRole.DestructiveRole)
        box.addButton(t("update.later"), common.QMessageBox.ButtonRole.RejectRole)

        def done(_result):
            clicked = box.clickedButton()
            if install is not None and clicked is install:
                self._install_update(release)
            elif clicked is page:
                _open_url(release["page"])
            elif clicked is skip:
                prefs.set("update_skipped", release["version"])
        box.finished.connect(done)
        self._update_dialog = box
        box.open()

    def _install_update(self, release):
        """Downloads and checks the installer, runs it, then closes Céleste."""
        state = {"done": 0, "total": release.get("setup_size") or 0, "cancel": False,
                 "closing": False}
        progress = QProgressDialog(tf("update.downloading", version=release["version"]),
                                   t("update.cancel"), 0, 1000, self)
        progress.setWindowTitle(t("update.title"))
        progress.setMinimumDuration(0)
        # close() emits canceled too: only the Cancel button (or the window's ×)
        # before the end of the download is the user's cancellation
        progress.canceled.connect(lambda: state["closing"] or state.update(cancel=True))
        ticker = QTimer(progress)
        ticker.timeout.connect(lambda: progress.setValue(
            int(1000 * state["done"] / state["total"]) if state["total"] else 0))
        ticker.start(200)
        self._update_progress = progress

        def fetch():
            return updater.download(release, progress=lambda d, n: state.update(done=d, total=n),
                                    cancelled=lambda: state["cancel"])

        def finish():
            state["closing"] = True
            ticker.stop()
            progress.close()

        def downloaded(path):
            finish()
            self.statusBar().showMessage(tf("update.installing", version=release["version"]))
            updater.launch_installer(path)
            QTimer.singleShot(300, QApplication.instance().quit)

        def failed(error):
            cancelled = state["cancel"]
            finish()
            if not cancelled:
                self._show_update_failure(release, error)
        common._run_in_background(fetch, downloaded, failed)

    def _show_update_failure(self, release, error):
        """Window (non-modal): why the download failed, the release page to
        install by hand, and the log."""
        box = common.QMessageBox(common.QMessageBox.Icon.Warning, t("update.title"),
                          tf("update.error", detail=error), parent=self)
        box.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        box.setInformativeText(tf("update.failed_hint", path=updater.log_path()))
        page = box.addButton(t("update.open_page"), common.QMessageBox.ButtonRole.ActionRole)
        box.addButton(common.QMessageBox.StandardButton.Close)

        def done(_result):
            if box.clickedButton() is page:
                _open_url(release["page"])
        box.finished.connect(done)
        self._update_failure = box
        box.open()

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

        # Language and display
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
        self._anglefmt_combo = QComboBox()
        for key in Formatters.ANGLE_FORMATS:
            self._anglefmt_combo.addItem(t(f"coordinates.angle_{key}"), key)
        self._anglefmt_combo.setCurrentIndex(max(0, self._anglefmt_combo.findData(_angle_format())))
        self._anglefmt_combo.setToolTip(t("settings.angle_format_tip"))
        self._anglefmt_combo.currentIndexChanged.connect(self._on_anglefmt_change)
        row = QHBoxLayout()
        row.setSpacing(16)
        row.addWidget(InputField(t("settings.language"), self._lang_combo), stretch=1)
        row.addWidget(InputField(t("settings.time_format"), self._timefmt_combo), stretch=1)
        row.addWidget(InputField(t("settings.angle_format"), self._anglefmt_combo), stretch=1)
        box.addLayout(row)
        box.addWidget(_label(t("settings.theme_hint"), "legende", wrap=True))

        # Starting place
        box = section(t("settings.default_place_section"))
        self._place_entry = QLineEdit(_clean_place(prefs.get("default_place")))
        box.addWidget(InputField(t("settings.default_place_name"), self._place_entry))
        coords = QVBoxLayout()
        coords.setSpacing(4)
        coords.addWidget(_label(t("settings.default_place_coords"), "label"))
        self._default_coords_lbl = _label("", "donnee")
        coords.addWidget(self._default_coords_lbl)
        box.addLayout(coords)
        self._update_default_place_label()
        buttons = QHBoxLayout()
        btn_use = _button(t("settings.use_current"), "place")
        btn_use.setToolTip(t("settings.use_current_tip"))
        btn_use.clicked.connect(self._save_default_place)
        buttons.addWidget(btn_use)
        buttons.addStretch()
        box.addLayout(buttons)
        self._autogeo_cb = QCheckBox(t("settings.auto_geoloc"))
        self._autogeo_cb.setChecked(bool(prefs.get("auto_geoloc")))
        self._autogeo_cb.toggled.connect(lambda v: prefs.set("auto_geoloc", bool(v)))
        box.addWidget(self._autogeo_cb)

        # Real time
        box = section(t("settings.live_section"))
        box.addWidget(_label(t("settings.live_interval"), "label"))
        iv = QHBoxLayout()
        iv.setSpacing(12)
        self._iv_slider = QSlider(Qt.Orientation.Horizontal)
        self._iv_slider.setRange(1, 20)            # steps of 500 ms
        self._iv_slider.setValue(int((prefs.get("live_interval") or 2000) / 500))
        self._iv_lbl = _label("", "donnee")
        self._iv_lbl.setMinimumWidth(80)
        self._iv_slider.valueChanged.connect(self._on_interval_changed)
        iv.addWidget(self._iv_slider, stretch=1)
        iv.addWidget(self._iv_lbl)
        self._iv_lbl.setText(tf("units.ms", value=_num(self._iv_slider.value() * 500)))
        box.addLayout(iv)

        # Observing site: refraction and horizon mask (night planner, sky map)
        box = section(t("observatory.section"))
        box.addWidget(_label(t("observatory.hint"), "legende", wrap=True))
        row = QHBoxLayout()
        row.setSpacing(16)
        self._env_temp = QLineEdit(_num(_pref_float("env_temperature", 10.0), 1))
        self._env_pressure = QLineEdit(_num(_pref_float("env_pressure", 1010.0), 0))
        for edit in (self._env_temp, self._env_pressure):
            edit.editingFinished.connect(self._save_environment)
        self._env_temp_field = InputField(t("observatory.temperature"), self._env_temp, unit="°C", numeric=True)
        self._env_pressure_field = InputField(t("observatory.pressure"), self._env_pressure, unit="hPa",
                                              numeric=True, hint=t("observatory.pressure_hint"))
        row.addWidget(self._env_temp_field, stretch=1, alignment=Qt.AlignmentFlag.AlignTop)
        row.addWidget(self._env_pressure_field, stretch=1, alignment=Qt.AlignmentFlag.AlignTop)
        box.addLayout(row)
        self._horizon_edit = QLineEdit(self._horizon_text(prefs.get("horizon_points") or []))
        self._horizon_edit.setPlaceholderText(t("observatory.horizon_placeholder"))
        self._horizon_edit.editingFinished.connect(self._save_horizon)
        self._horizon_field = InputField(t("observatory.horizon"), self._horizon_edit,
                                         hint=t("observatory.horizon_hint"))
        box.addWidget(self._horizon_field)
        # light pollution of the place (quality of the night)
        self._bortle_combo = QComboBox()
        self._bortle_combo.addItem(t("quality.bortle_none"), 0)
        for n in range(1, 10):
            self._bortle_combo.addItem(tf("quality.bortle_item", n=n, label=t(f"quality.bortle_{n}")), n)
        self._bortle_combo.setCurrentIndex(max(0, self._bortle_combo.findData(int(prefs.get("bortle") or 0))))
        self._bortle_combo.currentIndexChanged.connect(self._on_bortle_changed)
        box.addWidget(InputField(t("quality.bortle_field"), self._bortle_combo, hint=t("quality.bortle_hint")))

        # Reset (irreversible: danger button and confirmation)
        box = section(t("settings.reset_section"))
        box.addWidget(_label(t("settings.reset_hint"), "legende", wrap=True))
        buttons = QHBoxLayout()
        btn_reset = _button(t("settings.reset_btn"), variant="danger")
        btn_reset.clicked.connect(self._reset_settings)
        buttons.addWidget(btn_reset)
        buttons.addStretch()
        box.addLayout(buttons)

        # About: updates, links
        box = section(t("settings.about_section"))
        box.addWidget(_label(tf("settings.about", version=APP_VERSION), "corps", wrap=True))
        box.addWidget(_label(t("settings.credits"), "legende", wrap=True))
        row = QHBoxLayout()
        row.setSpacing(12)
        self._btn_update = _button(t("update.check_now"), "now", "secondaire", compact=True)
        self._btn_update.setToolTip(t("update.check_now_tip"))
        self._btn_update.clicked.connect(lambda _checked=False: self.check_updates())
        row.addWidget(self._btn_update)
        self._update_auto = QCheckBox(t("update.auto"))
        self._update_auto.setChecked(bool(prefs.get("update_check")))
        self._update_auto.toggled.connect(lambda on: prefs.set("update_check", bool(on)))
        row.addWidget(self._update_auto)
        row.addStretch()
        box.addLayout(row)
        self._update_info = _label(tf("update.current", version=APP_VERSION), "legende", wrap=True)
        box.addWidget(self._update_info)
        self._link_buttons = {}
        for links in ((("site", _URL_SITE), ("source", _URL_REPO), ("coffee", _URL_COFFEE)),
                      (("bug", _issue_url("bug")), ("feature", _issue_url("feature")),
                       ("body", _issue_url("body")))):
            row = QHBoxLayout()
            row.setSpacing(8)
            for key, url in links:
                btn = _button(t(f"links.{key}"), variant="secondaire", compact=True)
                btn.setToolTip(t(f"links.{key}_tip"))
                btn.clicked.connect(lambda _checked=False, u=url: _open_url(u))
                self._link_buttons[key] = btn
                row.addWidget(btn)
            row.addStretch()
            box.addLayout(row)

        lay.addStretch()
        # nine tabs: the settings show as an icon, named in its tooltip and for screen readers
        index = self.tabs.addTab(scroll, _icon("settings", Config.ENCRE_ATTENUEE, 18), "")
        self.tabs.setTabToolTip(index, t("tabs.settings"))
        self.tabs.tabBar().setAccessibleTabName(index, t("tabs.settings")) \
            if hasattr(self.tabs.tabBar(), "setAccessibleTabName") else None
        self._settings_page = scroll

    # ──────────────────────────────────────────────────────────────────────────
    # SETTINGS HANDLERS
    # ──────────────────────────────────────────────────────────────────────────

    def _on_bortle_changed(self, _index):
        prefs.set("bortle", int(self._bortle_combo.currentData() or 0))
        self._update_night_quality()

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

    def _on_anglefmt_change(self, index):
        """Angle format of the whole software (and of the coordinates table when it follows)."""
        prefs.set("angle_format", self._anglefmt_combo.itemData(index))
        self.calculate()

    def _on_messier_toggled(self, checked):
        prefs.set("show_messier", bool(checked))
        if self._dte is not None:
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
        """The typed place becomes the starting place (name, coordinates, time zone)."""
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
        answer = common.QMessageBox.question(
            self, t("settings.reset_title"), t("settings.reset_confirm"),
            common.QMessageBox.StandardButton.Yes | common.QMessageBox.StandardButton.No)
        if answer != common.QMessageBox.StandardButton.Yes:
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
