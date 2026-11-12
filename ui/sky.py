"""
ui/sky.py — Ciel: trajectories and the sky map (search, hover, click).

A mixin of the main window (gui.AstroApp): its methods use the window's state
(self.*) and those of the other spaces.
"""
import numpy as np

from ui import common
from ui.common import *  # noqa: F401,F403


SKY_HALF = 1.17          # half the width of the whole map (charts.draw_sky_map)
SKY_ZOOM_STEP = 1.25     # a notch of the wheel, a click of the buttons
SKY_ZOOM_MAX = 12.0

# The time bar under the map (v4.18): the night from sunset to sunrise
SKY_STEP_MIN = 5                          # a step of the bar, minutes
SKY_FRAME_MIN = 10                        # the animation: ten minutes of sky a frame
SKY_FRAME_MS = 40                         # the rest between two frames (drawing one takes longer)
SKY_NIGHT_MARGIN = timedelta(minutes=30)  # the bar starts before sunset, ends after sunrise


class SkySpace:
    def _build_trajectories_tab(self):
        page, self.fig_traj, self.canvas_traj = self._chart_page(
            "traj", hint=t("chart.hint"))
        self._traj_ax = None
        self._traj_tip = _TooltipLayer(self.canvas_traj)
        self.canvas_traj.mpl_connect("motion_notify_event", self._on_traj_hover)
        self.canvas_traj.mpl_connect("figure_leave_event",
                                     lambda _e: self._traj_tip.hide())
        self._traj_page = page
        self._add_page(page, t("tabs.trajectory"))

    def _build_skymap_tab(self):
        # the toolbar: one row; in the compact layout three (the stars shown, the
        # Messier objects and the zoom, the search), each as wide as the phone
        bar = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        bar.setSpacing(12)
        mag_row = QHBoxLayout()
        mag_row.setSpacing(12)
        mag_row.addWidget(_label(t("skymap.mag_limit"), "label"))
        self._mag_slider = QSlider(Qt.Orientation.Horizontal)
        self._mag_slider.setRange(10, 70)          # magnitude × 10
        self._mag_slider.setValue(int(round(self._mag_limit() * 10)))
        self._mag_slider.setToolTip(t("skymap.mag_tip"))
        self._mag_lbl = _label(_num(self._mag_limit(), 1), "donnee")
        self._mag_lbl.setMinimumWidth(36)
        self._mag_slider.valueChanged.connect(self._on_mag_changed)
        mag_row.addWidget(self._mag_slider, stretch=1)
        mag_row.addWidget(self._mag_lbl)
        mag_row.addSpacing(12)
        bar.addLayout(mag_row)
        tools_row = QHBoxLayout()
        tools_row.setSpacing(12)
        self._messier_box = QCheckBox(t("skymap.messier"))
        self._messier_box.setToolTip(t("skymap.messier_tip"))
        self._messier_box.setChecked(bool(prefs.get("show_messier")))
        self._messier_box.toggled.connect(self._on_messier_toggled)
        tools_row.addWidget(self._messier_box)
        tools_row.addSpacing(12)
        # zoom: the wheel (on the pointer), these buttons, a drag to move around
        for key, tip, slot in (("zoom_out", "skymap.zoom_out", lambda: self._sky_zoom_by(1 / SKY_ZOOM_STEP)),
                               ("zoom_in", "skymap.zoom_in", lambda: self._sky_zoom_by(SKY_ZOOM_STEP)),
                               ("reset", "skymap.zoom_reset", lambda: self._sky_reset_view())):
            button = _icon_button(key, t(tip), compact=True)
            button.clicked.connect(slot)
            tools_row.addWidget(button)
        self._sky_zoom_lbl = _label("", "donnee")
        self._sky_zoom_lbl.setMinimumWidth(40)
        tools_row.addWidget(self._sky_zoom_lbl)
        tools_row.addStretch()
        bar.addLayout(tools_row, stretch=1)
        # find a star, a planet, a Messier object or a constellation by its name
        self._find_entry = QLineEdit()
        self._find_entry.setPlaceholderText(t("skymap.find_placeholder"))
        self._find_entry.setToolTip(t("skymap.find_tip"))
        self._find_entry.setAccessibleName(t("skymap.find_tip"))
        self._find_entry.setClearButtonEnabled(True)
        self._find_model = QStringListModel(self)
        self._find_matches = {}
        self._find_completer = QCompleter(self._find_model, self)
        self._find_completer.setCompletionMode(QCompleter.CompletionMode.UnfilteredPopupCompletion)
        self._find_completer.setMaxVisibleItems(10)
        self._find_completer.activated.connect(self._on_find_chosen)
        self._find_entry.setCompleter(self._find_completer)
        self._find_entry.textEdited.connect(self._on_find_typed)
        self._find_entry.returnPressed.connect(self._on_find_return)
        self._find_entry.textChanged.connect(lambda text: text or self._clear_found())
        if self._sky_found is not None:                   # rebuilt: the object found stays circled
            self._find_entry.blockSignals(True)
            self._find_entry.setText(self._target_label(self._sky_found))
            self._find_entry.blockSignals(False)
        bar.addWidget(self._find_entry)
        self._reflow.append(bar)
        self._compact_hooks.append(self._sky_toolbar_compact)
        self._sky_toolbar_compact(False)

        page, self.fig_sky, self.canvas_sky = self._chart_page(
            "sky", toolbar=bar, hint=t("skymap.hint"), footer=self._build_sky_time_bar())
        self._sky_ax = None
        self._sky_tip = _TooltipLayer(self.canvas_sky)
        self.canvas_sky.mpl_connect("motion_notify_event", self._on_sky_hover)
        self.canvas_sky.mpl_connect("button_press_event", self._on_sky_press)
        self.canvas_sky.mpl_connect("button_release_event", self._on_sky_release)
        self.canvas_sky.mpl_connect("scroll_event", self._on_sky_scroll)
        self.canvas_sky.mpl_connect("figure_leave_event", self._on_sky_leave)
        if not hasattr(self, "_sky_zoom"):                 # kept through the rebuilds
            self._sky_zoom, self._sky_center = 1.0, (0.0, 0.0)
        self._sky_drag = None
        self._show_sky_zoom()
        self._sky_page = page
        self._add_page(page, t("tabs.skymap"))

    def _sky_toolbar_compact(self, compact):
        """The magnitude slider and the search: set widths in a row, the phone's
        width once the rows are stacked."""
        for widget, width in ((self._mag_slider, 240), (self._find_entry, 220)):
            if compact:
                widget.setMinimumWidth(0)
                widget.setMaximumWidth(16777215)              # QWIDGETSIZE_MAX
            else:
                widget.setFixedWidth(width)

    def _build_sky_time_bar(self):
        """Under the map: the night on a time bar, and ▶ to watch the sky turn. Only
        the map moves: the window's calculation keeps its date."""
        bar = QHBoxLayout()
        bar.setSpacing(8)
        self._sky_play = _icon_button("play", t("skymap.time_play"), compact=True)
        self._sky_play.clicked.connect(self._toggle_sky_animation)
        bar.addWidget(self._sky_play)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setSingleStep(SKY_STEP_MIN)
        slider.setPageStep(60)
        slider.setToolTip(t("skymap.time_tip"))
        slider.setAccessibleName(t("skymap.time_tip"))
        slider.valueChanged.connect(self._on_sky_time_moved)
        self._sky_time_slider = slider
        bar.addWidget(slider, stretch=1)
        self._sky_time_lbl = _label("", "donnee")
        self._sky_time_lbl.setMinimumWidth(48)
        bar.addWidget(self._sky_time_lbl)
        self._sky_time_reset = _icon_button("reset", t("skymap.time_reset"), compact=True)
        self._sky_time_reset.clicked.connect(self._reset_sky_time)
        bar.addWidget(self._sky_time_reset)
        if getattr(self, "_sky_anim_timer", None) is None:          # kept through the rebuilds
            self._sky_anim_timer = QTimer(self)
            self._sky_anim_timer.setSingleShot(True)
            self._sky_anim_timer.timeout.connect(self._sky_animation_step)
            self._sky_redraw_timer = QTimer(self)                   # a drag sends many values: one map
            self._sky_redraw_timer.setSingleShot(True)
            self._sky_redraw_timer.timeout.connect(self._show_sky_time_view)
        self._sky_anim_timer.stop()
        self._sky_animating = False
        self._show_sky_time_bar()
        return bar

    # ── The time bar: the night on the map ───────────────────────────────────

    def _sky_time_span(self):
        """
        The bar's span, minutes from the calculation's instant: from half an hour
        before sunset to half an hour after sunrise, the night of the calculation
        (in the morning, the night under way), widened to hold the calculation's
        instant; twelve hours on each side when the Sun does not set.
        """
        night = planner.night_window(self._dte, self._lat, self._lon, self._elevation(), self._zone,
                                     depths=((-0.833, "night"),))
        if night["start"] is None:                                  # polar day
            start, end = self._dte - timedelta(hours=12), self._dte + timedelta(hours=12)
        else:
            start, end = night["start"] - SKY_NIGHT_MARGIN, night["end"] + SKY_NIGHT_MARGIN
        lo = math.floor((start - self._dte).total_seconds() / 60.0 / SKY_STEP_MIN) * SKY_STEP_MIN
        hi = math.ceil((end - self._dte).total_seconds() / 60.0 / SKY_STEP_MIN) * SKY_STEP_MIN
        return min(0, lo), max(0, hi)

    def _sync_sky_time(self):
        """
        After a calculation: the bar over its night. The same date and place (a
        new magnitude limit, the Messier objects shown…) keep the time shown;
        another stops the animation and brings the map back to the calculation.
        """
        key = (self._dte, self._lat, self._lon, self._elevation(), str(self._zone))
        if key != self._sky_time_key:
            self._sky_time_key = key
            self._sky_offset_min = 0
            self._sky_span = self._sky_time_span()
            self._stop_sky_animation()
        self._apply_sky_offset()
        self._show_sky_time_bar()

    def _sky_time(self):
        """The instant the map shows (UT)."""
        return self._dte + timedelta(minutes=self._sky_offset_min)

    def _apply_sky_offset(self):
        """The sky and the scene the map shows: the calculation's, or the bar's time."""
        if self._sky_offset_min == 0 or self._sky_calc_state is None:
            self._sky_view, self._sky_scene = self._sky_calc_state, self._sky_calc_scene
            return
        self._sky_view = self._sky_frame_state()
        self._sky_scene = self._sky_scene_for(self._sky_view, self._sky_view["dte"], self._lat, self._lon,
                                              quick=True)

    def _sky_night_tracks(self):
        """
        The bodies along the bar, at each of its steps, computed at once the
        first time the bar leaves the calculation's time: altitudes and
        azimuths of the Sun, the Moon (refraction included, as the
        calculation), the planets, the minor planets and the comets.
        """
        tracks = getattr(self, "_sky_tracks", None)
        if tracks is not None and tracks["key"] == self._sky_time_key:
            return tracks
        lo, hi = self._sky_span
        minutes = np.arange(lo, hi + 1, SKY_STEP_MIN)
        tcs = AstroEngine.julian_century_j2000(self._dte) + minutes / 1440.0 / 36525.0
        calc = self._sky_calc_state
        bodies = ["sun", "moon"] + [p["name"] for p in calc["planets"] + calc["minor_planets"]]
        tracks = AstroEngine.horizontal_tracks(tcs, self._lat, self._lon, bodies, self._elevation())
        tracks.update(key=self._sky_time_key, lo=lo)
        self._sky_tracks = tracks
        return tracks

    def _sky_frame_state(self):
        """
        The sky at the bar's time: the bodies from the night's tracks, the
        Messier objects turned by the sidereal time; their distances,
        magnitudes and the Moon's phase as at the calculation, which a night
        hardly changes.
        """
        tracks = self._sky_night_tracks()
        i = (self._sky_offset_min - tracks["lo"]) // SKY_STEP_MIN
        calc = self._sky_calc_state

        def moved(body, name):
            alt, az = tracks[name]
            return {**body, "alt": float(alt[i]), "az": float(az[i])}

        when = self._sky_time()
        alts, azs = charts.turned_places("messier", AstroEngine.julian_day(when), self._lat, self._lon)
        return {"dte": when, "sun": moved(calc["sun"], "sun"), "moon": moved(calc["moon"], "moon"),
                "planets": [moved(p, p["name"]) for p in calc["planets"]],
                "minor_planets": [moved(p, p["name"]) for p in calc["minor_planets"]],
                "comets": calc["comets"],
                "deep_sky": [{**o, "alt": float(alt), "az": float(az)}
                             for o, alt, az in zip(calc["deep_sky"], alts, azs)]}

    def _show_sky_time_bar(self):
        """The bar's span and place, and the time it shows."""
        slider = getattr(self, "_sky_time_slider", None)
        if slider is None or self._dte is None:
            return
        slider.blockSignals(True)
        slider.setRange(*self._sky_span)
        slider.setValue(self._sky_offset_min)
        slider.blockSignals(False)
        self._show_sky_time_label()

    def _show_sky_time_label(self):
        when = self._sky_time()
        local = self._local(when)
        moved = self._sky_offset_min != 0
        self._sky_time_lbl.setText(self._fmt_clock(local))
        self._sky_time_lbl.setToolTip(tf("skymap.time_label_tip", date=local.strftime("%d/%m/%Y"),
                                         ut=self._fmt_clock(when)))
        self._sky_time_lbl.setProperty("tone", "or" if moved else None)   # gold: not the calculation's time
        self._sky_time_lbl.style().polish(self._sky_time_lbl)
        self._sky_time_reset.setEnabled(moved)

    def _on_sky_time_moved(self, value):
        """The bar moved (by hand or by the animation): the map follows once it rests."""
        if self._dte is None:
            return
        step = int(round(value / SKY_STEP_MIN)) * SKY_STEP_MIN      # on the bar's steps (the tracks')
        if step != value:
            self._sky_time_slider.blockSignals(True)
            self._sky_time_slider.setValue(step)
            self._sky_time_slider.blockSignals(False)
            value = step
        self._sky_offset_min = int(value)
        if self.live_mode and value:                     # another time than now: the real time ends
            self.btn_live.setChecked(False)
        self._show_sky_time_label()
        self._sky_redraw_timer.start(0)

    def _show_sky_time_view(self):
        """The map at the bar's time."""
        self._sky_redraw_timer.stop()
        if self._dte is None:
            return
        self._apply_sky_offset()
        self._refresh_sky_objects()
        self._sky_hover = None
        self._sky_tip.hide()
        self._dirty.add("sky")
        self._draw_visible_chart()                      # now when the map is shown, else when it is
        if self._sky_found is not None:
            self._show_find_result()

    def _reset_sky_time(self):
        """Back to the calculation's time."""
        self._stop_sky_animation()
        self._sky_time_slider.setValue(0)
        self._show_sky_time_view()

    def _toggle_sky_animation(self):
        """▶: the night goes by on the map, ten minutes a frame, to the end of the bar."""
        if self._sky_animating:
            self._stop_sky_animation()
            return
        if self._dte is None:
            return
        slider = self._sky_time_slider
        if slider.value() >= slider.maximum():               # at the end: from the start again
            slider.setValue(slider.minimum())
        if self.live_mode:
            self.btn_live.setChecked(False)
        self._sky_animating = True
        self._sky_play.setIcon(_icon("pause", Config.ENCRE, 16))
        self._sky_play.setToolTip(t("skymap.time_pause"))
        self._sky_anim_timer.start(SKY_FRAME_MS)

    def _stop_sky_animation(self):
        self._sky_animating = False
        timer = getattr(self, "_sky_anim_timer", None)
        if timer is not None:
            timer.stop()
        play = getattr(self, "_sky_play", None)
        if play is not None:
            play.setIcon(_icon("play", Config.ENCRE, 16))
            play.setToolTip(t("skymap.time_play"))

    def _sky_animation_step(self):
        """A frame: the sky ten minutes later; at the end of the bar, the animation stops."""
        if not self._sky_animating:
            return
        slider = self._sky_time_slider
        value = min(slider.maximum(), slider.value() + SKY_FRAME_MIN)
        slider.setValue(value)
        self._show_sky_time_view()                       # this frame now, not after the next one
        if value >= slider.maximum():
            self._stop_sky_animation()
        else:
            self._sky_anim_timer.start(SKY_FRAME_MS)

    def _draw_trajectory(self):
        if not self.hours:
            return
        dte, start = self._dte, self._day_start
        offset = self._midnight_offset()
        labels = {
            "title": tf("chart.trajectory_title", date=self._local(start).strftime("%d/%m/%Y")),
            "xlabel": tf("chart.hour_local", offset=_fmt_offset(offset)),
            "ylabel": t("chart.altitude"),
            "top_axis": t("chart.hour_ut"),
            "sun": t("chart.sun"),
            "moon": t("chart.moon"),
        }
        labels.update({p: t(f"chart.phase_{p}") for p in charts.DAY_PHASES})
        now_h = (dte - start).total_seconds() / 3600       # since local midnight
        self._traj_ax, tip = charts.draw_trajectory(
            self.fig_traj, self.hours, self.sun_altitudes, self.moon_altitudes,
            now_h, self.sun_data["alt"], self.moon_data["alt"], labels, offset)
        self._traj_tip.attach(tip)
        self.canvas_traj.draw_idle()

    def _draw_sky_map(self):
        dte = self._sky_time()
        labels = {
            "title": tf("skymap.title", datetime=dte.strftime("%d/%m/%Y %H:%M")),
            "sun": t("chart.sun"),
            "moon": t("chart.moon"),
            "horizon": t("skymap.horizon"),
            "cardinals": [t(f"skymap.cardinal_{c}")
                          for c in ("n", "ne", "e", "se", "s", "sw", "w", "nw")],
            "planets": {n: _planet_name(n) for n in _PLANETS + MINOR_PLANETS + COMETS},
        }
        found = self._resolve_target(self._sky_found)
        highlight = None
        if found is not None and found["alt"] > 0:
            highlight = {"x": found["x"], "y": found["y"], "label": self._target_label(self._sky_found),
                         "wide": found["kind"] == "figure"}
        self._sky_ax, tip = charts.draw_sky_map(self.fig_sky, self._sky_scene, labels, highlight)
        for text in self._sky_ax.texts:                    # zoomed in: no label outside the map
            text.set_clip_on(True)
        self._apply_sky_view()
        self._show_find_result()
        self._sky_tip.attach(tip)
        self._sky_hover = None
        self.canvas_sky.draw_idle()

    # ── Search by name on the sky map ─────────────────────────────────────────
    #    A reference names an object from one calculation to the next: ("sun",),
    #    ("moon",), ("planet", name), ("star", designation), ("messier", number),
    #    ("figure", constellation).

    @staticmethod
    def _find_key(text):
        """Search key of a name: no accents or case, Greek letters spelled out
        ("α¹ Cen": "alpha1 cen"), "M 31" and "Messier 31" as "m31"."""
        key = places.normalize("".join(_GREEK.get(ch, ch) for ch in text))
        return re.sub(r"\b(?:messier|m) (?=\d)", "m", key)

    @staticmethod
    def _star_label(star):
        return star["name"] if star["name"] == star["designation"] else f"{star['name']} ({star['designation']})"

    def _target_label(self, ref):
        kind = ref[0]
        if kind in ("sun", "moon"):
            return t(f"chart.{kind}")
        if kind == "planet":
            return _planet_name(ref[1])
        if kind == "figure":
            return t(f"constellations.{ref[1]}")
        if kind == "messier":
            return _messier_label(next(o for o in messier_catalog() if o["m"] == ref[1]))
        if kind == "deep":
            return _messier_label(self._deep_object(ref[1]))
        return self._star_label(next(s for s in self._sky_scene["catalog"] if s["designation"] == ref[1]))

    def _deep_object(self, label):
        """A deep-sky object of the planner's catalogues or of the user's targets, by its label."""
        custom = [planner.custom_target(**c) for c in prefs.get("planner_custom") or []]
        for obj in list(planner.deep_sky_catalog()) + custom:
            if planner.label(obj) == label or obj["id"] == label:
                return obj
        return None

    def _sky_targets(self):
        """Everything the search knows, [(label, search key, reference)]: the Sun, the
        Moon, the planets, minor planets and comets, the Messier objects, the
        constellations and the stars of the catalogue (their keys computed once)."""
        targets = [(self._target_label(ref), None, ref) for ref in [("sun",), ("moon",)]
                   + [("planet", p["name"]) for p in self.planets + self.minor_planets]]
        targets += [(_messier_label(o), None, ("messier", o["m"])) for o in self._deep_sky_all]
        targets += [(t(f"constellations.{key}"), None, ("figure", key)) for key in self._sky_scene["figures"]]
        targets = [(label, self._find_key(label), ref) for label, _key, ref in targets]
        if type(self)._STAR_TARGETS is None:
            stars = [(self._star_label(s), ("star", s["designation"])) for s in self._sky_scene["catalog"]]
            type(self)._STAR_TARGETS = [(label, self._find_key(label), ref) for label, ref in stars]
        return targets + type(self)._STAR_TARGETS

    _STAR_TARGETS = None            # the stars do not change: their labels and keys are built once

    def _find_targets(self, text, limit=10):
        """The targets whose name matches *text*: the exact name (or its first
        word, "m3") first, then names starting with it, then a word starting
        with it, then any place in the name."""
        query = self._find_key(text)
        if not query or self._sky_scene is None:
            return []
        ranked = []
        for index, (label, key, ref) in enumerate(self._sky_targets()):
            words = key.split()
            if key == query or words[0] == query:
                rank = 0
            elif key.startswith(query):
                rank = 1
            elif any(word.startswith(query) for word in words) or f" {query}" in f" {key}":
                rank = 2
            elif query in key:
                rank = 3
            else:
                continue
            ranked.append((rank, index, label, ref))
        return [(label, ref) for _rank, _index, label, ref in sorted(ranked)[:limit]]

    def _resolve_target(self, ref):
        """The object behind a reference as the sky map describes it (altitude,
        azimuth, map position); None without a reference, or for a comet that
        has left its table."""
        if ref is None or self._sky_scene is None:
            return None
        scene, kind = self._sky_scene, ref[0]
        sky = self._sky_view or self._sky_calc_state             # the sky at the time the map shows
        if kind in ("sun", "moon"):
            return scene[kind]
        if kind == "star":
            return next((s for s in scene["catalog"] if s["designation"] == ref[1]), None)
        if kind == "planet":
            body = next((p for p in sky["planets"] + sky["minor_planets"] if p["name"] == ref[1]), None)
            obj = {**body, "kind": "planet"} if body else None
        elif kind == "messier":
            obj = next(({**o, "kind": "deep_sky"} for o in sky["deep_sky"] if o["m"] == ref[1]), None)
        elif kind == "deep":
            found = self._deep_object(ref[1])
            if found is None:
                return None
            tc = AstroEngine.julian_century_j2000(sky["dte"])
            alt, az = AstroEngine.stars_horizontal(tc, self._lat, self._lon, [found["ra"] / 15.0], [found["dec"]],
                                                   self._elevation())
            obj = {**found, "kind": "deep_sky", "alt": float(alt[0]), "az": float(az[0])}
        else:
            alt, az = scene["figures"][ref[1]]
            obj = {"kind": "figure", "name": ref[1], "alt": alt, "az": az}
        if obj is None:
            return None
        x, y = charts.sky_xy(obj["alt"], obj["az"])
        return {**obj, "x": x, "y": y}

    def _refresh_sky_objects(self):
        """What the pointer finds on the map: the objects drawn and, when it is
        too faint to be drawn, the object found by name."""
        self._sky_objects = charts.visible_objects(self._sky_scene)
        found = self._resolve_target(self._sky_found)
        if found is None or found["kind"] == "figure" or found["alt"] <= 0:
            return
        same = (lambda o: o.get("id") == found.get("id")) if found["kind"] == "deep_sky" else \
            (lambda o: o.get("name") == found.get("name"))
        if not any(o["kind"] == found["kind"] and same(o) for o in self._sky_objects):
            self._sky_objects.append(found)

    def _on_find_typed(self, text):
        """Suggestions at each letter."""
        self._find_matches = dict(self._find_targets(text))
        self._find_model.setStringList(list(self._find_matches))
        if self._find_matches:
            self._find_completer.complete()

    def _on_find_chosen(self, label):
        ref = self._find_matches.get(label)
        if ref is not None:
            self._find_on_sky(ref)

    def _on_find_return(self):
        """Return without choosing: the first suggestion."""
        text = self._find_entry.text().strip()
        if not text:
            return
        ref = self._find_matches.get(text)
        if ref is None:
            found = self._find_targets(text, limit=1)
            ref = found[0][1] if found else None
        if ref is None:
            message = tf("skymap.not_found", name=text)
            self._chart_hints["sky"].setText(message)
            self.statusBar().showMessage(message, 6000)
            return
        self._find_on_sky(ref)

    def _find_on_sky(self, ref):
        """Circles the object on the map and says where it is."""
        self._find_completer.popup().hide()
        self._sky_found = ref
        self._find_entry.blockSignals(True)
        self._find_entry.setText(self._target_label(ref))
        self._find_entry.blockSignals(False)
        self._refresh_sky_objects()
        self._dirty.add("sky")
        self._draw_visible_chart()
        self._show_find_result()                          # also when another tab is shown
        self.statusBar().showMessage(self._chart_hints["sky"].text(), 6000)

    def _clear_found(self):
        if self._sky_found is None:
            self._chart_hints["sky"].setText(t("skymap.hint"))
            return
        self._sky_found = None
        self._refresh_sky_objects()
        self._dirty.add("sky")
        self._draw_visible_chart()
        self._show_find_result()

    def _show_find_result(self):
        """Under the map: where the object found is, or that it is below the horizon."""
        hint = self._chart_hints["sky"]
        found = self._resolve_target(self._sky_found)
        if found is None:
            hint.setText(t("skymap.hint"))
            return
        name = self._target_label(self._sky_found)
        if found["alt"] > 0:
            hint.setText(tf("skymap.found", name=name, alt=_deg(found["alt"], 1),
                            dir=self._wind(found["az"]), az=_deg(found["az"], 1)))
            return
        rise = None
        if found["kind"] in ("sun", "moon", "planet"):
            body = found["kind"] if found["kind"] != "planet" else found["name"]
            rise = AstroEngine.next_rise(self._sky_time(), self._lat, self._lon, body, self._elevation())
        if rise is not None:
            hint.setText(tf("skymap.found_below_rise", name=name, alt=_deg(found["alt"], 1, signed=True),
                            time=self._format_event(rise)))
        else:
            hint.setText(tf("skymap.found_below", name=name, alt=_deg(found["alt"], 1, signed=True)))

    # ── Hover and click ──────────────────────────────────────────────────────

    def _on_traj_hover(self, event):
        tip = self._traj_tip.artist
        if tip is None:
            return
        if event.inaxes is not self._traj_ax or event.xdata is None or not self.hours:
            self._traj_tip.hide()
            return
        step = self.hours[1] - self.hours[0]
        i = max(0, min(len(self.hours) - 1, int(round(event.xdata / step))))
        hour = self.hours[i]                                  # since local midnight
        base, offset = datetime(2000, 1, 1), self._midnight_offset()
        ut = self._fmt_clock(base + timedelta(hours=hour - offset))
        first = f"{ut} {t('chart.ut')}"
        if offset:
            local = self._fmt_clock(base + timedelta(hours=hour))
            first = f"{local} {t('chart.local')}  ·  {first}"
        tip.set_text(f"{first}\n"
                     f"{charts.SYMBOL['Sun']} {t('chart.sun')}  {_deg(self.sun_altitudes[i], 1, True)}\n"
                     f"{charts.SYMBOL['Moon']} {t('chart.moon')}  {_deg(self.moon_altitudes[i], 1, True)}")
        tip.xy = (hour, event.ydata)
        right = hour > 16
        tip.set_position((-14 if right else 14, 12))
        tip.set_horizontalalignment("right" if right else "left")
        tip.set_visible(True)
        self._traj_tip.refresh()

    def _sky_object_at(self, event):
        if event.inaxes is not self._sky_ax or event.xdata is None:
            return None
        return charts.hit_test(self._sky_objects, event.xdata, event.ydata, radius=0.06 / self._sky_zoom)

    # ── Zoom and move on the sky map ──────────────────────────────────────────

    def _apply_sky_view(self):
        """The map's limits for the zoom and the centre."""
        ax = self._sky_ax
        if ax is None:
            return
        half = SKY_HALF / self._sky_zoom
        cx, cy = self._sky_center
        ax.set_xlim(cx - half, cx + half)
        ax.set_ylim(cy - half, cy + half)

    def _show_sky_zoom(self):
        label = getattr(self, "_sky_zoom_lbl", None)
        if label is not None:
            label.setText("" if self._sky_zoom == 1.0 else f"×{_num(self._sky_zoom, 1)}")

    def _sky_set_view(self, zoom, center):
        zoom = min(SKY_ZOOM_MAX, max(1.0, zoom))
        limit = SKY_HALF - SKY_HALF / zoom                 # the map's edge stays in view
        cx, cy = center
        self._sky_zoom = zoom
        self._sky_center = (0.0, 0.0) if zoom == 1.0 else (max(-limit, min(limit, cx)),
                                                          max(-limit, min(limit, cy)))
        self._show_sky_zoom()
        if self._sky_ax is not None:
            self._apply_sky_view()
            self._sky_tip.hide()
            self.canvas_sky.draw_idle()

    def _sky_zoom_by(self, factor, at=None):
        """Zooms by *factor*, keeping the point *at* (map coordinates) under the pointer."""
        cx, cy = self._sky_center
        px, py = at if at is not None else (cx, cy)
        zoom = min(SKY_ZOOM_MAX, max(1.0, self._sky_zoom * factor))
        ratio = self._sky_zoom / zoom
        self._sky_set_view(zoom, (px + (cx - px) * ratio, py + (cy - py) * ratio))

    def _sky_reset_view(self):
        self._sky_set_view(1.0, (0.0, 0.0))

    def _on_sky_scroll(self, event):
        if event.inaxes is not self._sky_ax or event.xdata is None:
            return
        step = getattr(event, "step", 0) or (1 if event.button == "up" else -1)
        self._sky_zoom_by(SKY_ZOOM_STEP ** step, (event.xdata, event.ydata))

    def _on_sky_press(self, event):
        if getattr(event, "button", None) != 1 or event.inaxes is not self._sky_ax:
            return
        if getattr(event, "dblclick", False):
            self._sky_reset_view()
            return
        self._sky_drag = (event.x, event.y, self._sky_center, False)

    def _sky_drag_move(self, event):
        """Moving the pressed pointer: the map follows it (when zoomed in)."""
        x0, y0, center, moved = self._sky_drag
        if not moved and math.hypot(event.x - x0, event.y - y0) < 5:
            return
        self._sky_drag = (x0, y0, center, True)
        if self._sky_zoom == 1.0 or self._sky_ax is None:
            return
        inverse = self._sky_ax.transData.inverted()
        (ax0, ay0), (ax1, ay1) = inverse.transform([(x0, y0), (event.x, event.y)])
        self._sky_set_view(self._sky_zoom, (center[0] - (ax1 - ax0), center[1] - (ay1 - ay0)))

    def _on_sky_release(self, event):
        drag, self._sky_drag = self._sky_drag, None
        if drag is not None and not drag[3]:
            self._on_sky_click(event)                      # a click, not a drag: the object's card

    def _on_sky_leave(self, _event):
        self.canvas_sky.unsetCursor()
        self._sky_hover = None
        self._sky_tip.hide()

    def _on_sky_hover(self, event):
        if self._sky_drag is not None and getattr(event, "x", None) is not None:
            self._sky_drag_move(event)
            if self._sky_drag[3]:
                return
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
        title, _rows = self._object_details(obj, symbols=False)
        line = (f"{t('detail.alt')} {_deg(obj['alt'], 1)}  ·  "
                f"{t('detail.az')} {_deg(obj['az'], 1)}")
        if obj["kind"] in ("star", "deep_sky"):
            line += f"  ·  {t('detail.mag')} {_num(obj['mag'], 2 if obj['kind'] == 'star' else 1)}"
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
