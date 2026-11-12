"""
ui/sky.py — Ciel: trajectories and the sky map (search, hover, click).

A mixin of the main window (gui.AstroApp): its methods use the window's state
(self.*) and those of the other spaces.
"""
from ui import common
from ui.common import *  # noqa: F401,F403


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
        bar = QHBoxLayout()
        bar.setSpacing(12)
        bar.addWidget(_label(t("skymap.mag_limit"), "label"))
        self._mag_slider = QSlider(Qt.Orientation.Horizontal)
        self._mag_slider.setRange(10, 70)          # magnitude × 10
        self._mag_slider.setFixedWidth(240)
        self._mag_slider.setValue(int(round(self._mag_limit() * 10)))
        self._mag_slider.setToolTip(t("skymap.mag_tip"))
        self._mag_lbl = _label(_num(self._mag_limit(), 1), "donnee")
        self._mag_lbl.setMinimumWidth(36)
        self._mag_slider.valueChanged.connect(self._on_mag_changed)
        bar.addWidget(self._mag_slider)
        bar.addWidget(self._mag_lbl)
        bar.addSpacing(24)
        self._messier_box = QCheckBox(t("skymap.messier"))
        self._messier_box.setToolTip(t("skymap.messier_tip"))
        self._messier_box.setChecked(bool(prefs.get("show_messier")))
        self._messier_box.toggled.connect(self._on_messier_toggled)
        bar.addWidget(self._messier_box)
        bar.addStretch()
        # find a star, a planet, a Messier object or a constellation by its name
        self._find_entry = QLineEdit()
        self._find_entry.setPlaceholderText(t("skymap.find_placeholder"))
        self._find_entry.setToolTip(t("skymap.find_tip"))
        self._find_entry.setAccessibleName(t("skymap.find_tip"))
        self._find_entry.setClearButtonEnabled(True)
        self._find_entry.setFixedWidth(220)
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

        page, self.fig_sky, self.canvas_sky = self._chart_page(
            "sky", toolbar=bar, hint=t("skymap.hint"))
        self._sky_ax = None
        self._sky_tip = _TooltipLayer(self.canvas_sky)
        self.canvas_sky.mpl_connect("motion_notify_event", self._on_sky_hover)
        self.canvas_sky.mpl_connect("button_press_event", self._on_sky_click)
        self.canvas_sky.mpl_connect("figure_leave_event", self._on_sky_leave)
        self._sky_page = page
        self._add_page(page, t("tabs.skymap"))

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
        dte = self._dte
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
        if kind in ("sun", "moon"):
            return scene[kind]
        if kind == "star":
            return next((s for s in scene["catalog"] if s["designation"] == ref[1]), None)
        if kind == "planet":
            obj = self._body_object(ref[1])
        elif kind == "messier":
            obj = next(({**o, "kind": "deep_sky"} for o in self._deep_sky_all if o["m"] == ref[1]), None)
        elif kind == "deep":
            found = self._deep_object(ref[1])
            if found is None:
                return None
            tc = AstroEngine.julian_century_j2000(self._dte)
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
            rise = AstroEngine.next_rise(self._dte, self._lat, self._lon, body, self._elevation())
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
        return charts.hit_test(self._sky_objects, event.xdata, event.ydata)

    def _on_sky_leave(self, _event):
        self.canvas_sky.unsetCursor()
        self._sky_hover = None
        self._sky_tip.hide()

    def _on_sky_hover(self, event):
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
