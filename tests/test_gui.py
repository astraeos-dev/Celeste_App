"""
tests/test_gui.py — Tests of the PyQt6 interface (without a screen)
===================================================================
Builds the Céleste window off screen (QT_QPA_PLATFORM=offscreen) and drives
it: calculation, change of language and theme (Nuit, Jour, Observation)
without restarting, favourites, event search, tooltips and cards of the sky
map, real time; also checks two rules of the Astræos design (no emoji,
symbols followed by U+FE0E).

The preferences and favourites are written to a temporary folder: the
user's (~/.celeste) are never modified.
The tests are skipped when PyQt6 (or Qt's system libraries) is
missing.

Run with:  pytest tests/test_gui.py -v
"""

import io
import json
import re
import os
import sys
from datetime import datetime

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

pytest.importorskip("PyQt6.QtWidgets", reason="PyQt6 or the Qt libraries are missing")
pytest.importorskip("matplotlib")

from engine import COMETS  # noqa: E402
from matplotlib.backend_bases import MouseEvent  # noqa: E402
from PyQt6.QtCore import QEvent, Qt  # noqa: E402
from PyQt6.QtWidgets import (  # noqa: E402
    QAbstractButton, QApplication, QDialog, QFrame, QLabel, QMessageBox,
)

DTE = datetime(2026, 11, 1, 21, 30, 0)     # night in Cherbourg, Vega high in the sky


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    import gui
    gui.init_style(app)
    return app


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    import gui
    import settings as prefs
    from config import Config
    from i18n import switch_lang

    monkeypatch.setattr(prefs, "_SETTINGS_FILE", str(tmp_path / "settings.json"))
    prefs.reset()
    prefs.set("default_tz", "UTC")      # times expected in UT; the automatic zone has its own tests
    favorites = tmp_path / "favorites.json"
    favorites.write_text(json.dumps({
        "Paris": {"lat": 48.8566, "lon": 2.3522},
        "Tokyo": {"lat": 35.6762, "lon": 139.6503},
    }), encoding="utf-8")
    monkeypatch.setattr(gui, "_FAVORITES_FILE", str(favorites))
    import satellites
    monkeypatch.setattr(satellites, "CACHE", str(tmp_path / "satellites.tle"))    # none on disk
    import history
    monkeypatch.setattr(history, "FILE", str(tmp_path / "history.json"))          # empty
    import mpc
    monkeypatch.setattr(mpc, "CACHE", str(tmp_path / "CometEls.txt"))             # none, and no download:
    prefs.set("planner_mpc", False)                                                # Céleste's comets only
    Config.apply_theme("nuit")
    switch_lang("fr")
    gui.apply_theme(qapp)

    win = gui.AstroApp()
    win.resize(1350, 820)
    win.show()
    win._set_datetime(DTE)
    win.calculate()
    qapp.processEvents()
    yield win

    win.toggle_live(False)
    win.close()
    _destroy(qapp, win)
    Config.apply_theme("nuit")
    switch_lang("fr")


def _destroy(qapp, widget):
    """Really destroys the window: processEvents() alone does not process deleteLater(),
    and the windows of earlier tests, still there, slowed down every change of
    theme or language (the whole application is restyled)."""
    widget.deleteLater()
    qapp.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qapp.processEvents()


def _pump(qapp, n=10):
    for _ in range(n):
        qapp.processEvents()


def _yes_box(gui):
    class YesBox(gui.QMessageBox):
        @staticmethod
        def question(*_args, **_kwargs):
            return gui.QMessageBox.StandardButton.Yes
    return YesBox


# ──────────────────────────────────────────────────────────────────────
# 1. Calculation and display
# ──────────────────────────────────────────────────────────────────────

class TestCalculation:
    def test_cards_are_filled(self, window):
        assert window.sun_labels["ra"].text().startswith("14h")
        assert window.moon_labels["dist"].text().endswith("km")
        assert window.sun_labels["rise"].text() == "06:55"
        assert window._lbl_phase_name.text() == "Dernier quartier"
        assert "Cherbourg-en-Cotentin" in window._lbl_pos.text()

    def test_planet_table(self, window):
        items = window._planet_items["Saturn"]
        assert re.match(r"^\d+,\d{4}$", items["col_dist"].text())      # the unit is in the header
        assert items["col_planet"].toolTip() == "Visible"
        assert re.match(r"^\d\d:\d\d$", items["col_rise"].text())
        shown = [r for r in range(window.planet_table.rowCount()) if not window.planet_table.isRowHidden(r)]
        assert len(shown) == 7                                             # Mercury to Neptune

    def test_tonight(self, window):
        """"Tonight" (times in UT in these tests): the night, the Moon, the planets, what comes next."""
        lines = [text for text, _tone in window._tonight_lines()]
        assert lines[0] == "Nuit noire de 18:33 à 05:08"
        assert lines[1].endswith("Lune éclairée à 49 %, se lève à 22:42")
        assert any("Jupiter · visible le matin" in x and "magnitude −2,0" in x for x in lines)
        assert lines[-1].startswith("À venir : 03/11 Lune et Mars, le matin")
        shown = [w.text() for w in window.findChildren(QLabel) if w.isVisible()]
        assert "Nuit noire de 18:33 à 05:08" in shown

    def test_minor_planets_of_the_planet_table(self, window):
        """The "Minor planets" choice shows Ceres … Makemake, magnitude included."""
        window._planet_selector.buttons["minor"].click()
        table = window.planet_table
        shown = [table.item(r, 0).text().split(" ", 1)[-1] for r in range(table.rowCount())
                 if not table.isRowHidden(r)]
        assert shown == ["Cérès", "Pallas", "Junon", "Vesta", "Pluton", "Éris", "Hauméa", "Makémaké", "Sedna"]
        assert table.item(window._planet_items["Eris"]["col_planet"].row(), 0).toolTip().startswith("(136199) Éris")
        vesta = window._planet_items["Vesta"]
        assert re.match(r"^\d,\d$", vesta["col_mag"].text())               # Vesta: magnitude 6 to 8
        assert re.match(r"^\d\d:\d\d$", vesta["col_rise"].text())
        window._planet_selector.buttons["planets"].click()
        vesta_row = window._planet_items["Vesta"]["col_planet"].row()
        assert table.isRowHidden(vesta_row)

    def _shown(self, window):
        table = window.planet_table
        return [table.item(r, 0).data(Qt.ItemDataRole.UserRole + 1) for r in range(table.rowCount())
                if not table.isRowHidden(r)]

    def test_all_bodies_and_visible_only(self, window):
        """Issue #21: all the bodies, or only those above the horizon; in 2026,
        7 planets, 9 minor planets and the comets followed."""
        window._planet_selector.buttons["all"].click()
        assert len(self._shown(window)) == 16 + len(COMETS)
        window._planet_visible.setChecked(True)
        up = self._shown(window)
        assert 0 < len(up) < 16 + len(COMETS)
        assert all(window._planet_alt[name] > 0 for name in up)
        window._planet_visible.setChecked(False)
        window._planet_selector.buttons["planets"].click()

    def test_sort_by_magnitude(self, window):
        """Click on "Mag.": brightest to faintest; "Planet": order of the Solar System."""
        table = window.planet_table
        window._planet_selector.buttons["all"].click()
        mag = [table.horizontalHeaderItem(c).text() for c in range(table.columnCount())].index("Mag.")
        table.sortItems(mag, Qt.SortOrder.AscendingOrder)
        names = self._shown(window)
        values = [window._planet_items[n]["col_mag"].data(Qt.ItemDataRole.UserRole) for n in names]
        assert values == sorted(values) and names[0] == "Venus"
        table.sortItems(0, Qt.SortOrder.AscendingOrder)
        assert self._shown(window)[:3] == ["Mercury", "Venus", "Mars"]
        window._planet_selector.buttons["planets"].click()

    def test_invalid_latitude_is_flagged_without_dialog(self, window):
        """The error shows under the field (InputField), without a window."""
        before = dict(window.sun_data)
        window.entry_lat.setText("123")
        window.calculate()
        assert window.entry_lat.property("invalid") is True
        assert window.field_lat.error.isVisibleTo(window)
        assert "−90" in window.field_lat.error.text()
        assert window.sun_data == before
        window.entry_lat.setText("49,6333")
        window.calculate()
        assert window.entry_lat.property("invalid") is False
        assert not window.field_lat.error.isVisibleTo(window)

    def test_data_cards(self, window):
        """The highlighted values in the cadran style, numbers in the French style."""
        assert window.card_sun_rise.value.text() == "06:55"
        assert window.card_sun_alt.unit.text() == "°"
        assert "," in window.card_moon_alt.value.text()
        assert window.card_moon_illum.detail.text() == "Dernier quartier"

    def test_timezone_shifts_local_times(self, window):
        window.tz_menu.setCurrentIndex(window.tz_menu.findData("Etc/GMT-2"))
        assert window.sun_labels["rise"].text() == "08:55"
        assert "UTC+2" in window._sun_events_title.text()

    def test_automatic_zone_follows_the_place(self, window):
        """Cherbourg on 1 November: Europe/Paris, in winter time (UTC+1)."""
        window.tz_menu.setCurrentIndex(window.tz_menu.findData("auto"))
        assert window.sun_labels["rise"].text() == "07:55"
        assert "UTC+1" in window._sun_events_title.text()
        assert "Europe/Paris" in window._lbl_time.text()

    def test_half_hour_zone(self, window):
        """Asia/Kolkata is UTC+5:30: its local day is 2 November."""
        window.tz_menu.setCurrentIndex(window.tz_menu.findData("Asia/Kolkata"))
        assert "UTC+5:30" in window._sun_events_title.text()
        assert window.sun_labels["rise"].text() == "12:27"

    def test_elevation_brings_sunrise_forward(self, window):
        """From 1000 m, the horizon is 0.93° lower: the Sun rises ~6 min earlier."""
        window.entry_elev.setText("1000")
        window.calculate()
        assert window.sun_labels["rise"].text() == "06:49"

    def test_twelve_hour_format(self, window):
        window._timefmt_combo.setCurrentIndex(window._timefmt_combo.findData("12h"))
        assert window.sun_labels["rise"].text() == "6:55 AM"

    def test_hidden_charts_are_drawn_on_demand(self, window, qapp):
        window.tabs.setCurrentIndex(0)
        window.calculate()
        assert {"traj", "sky", "orrery"} <= window._dirty
        window.tabs.setCurrentIndex(1)
        _pump(qapp)
        assert "traj" not in window._dirty and "sky" in window._dirty


# ──────────────────────────────────────────────────────────────────────
# 2. Language and theme applied without restarting
# ──────────────────────────────────────────────────────────────────────

class TestLiveSwitching:
    def test_language_switch_keeps_date_and_place(self, window, qapp):
        import settings as prefs
        window.entry_lat.setText("48.8566")
        window._lang_combo.setCurrentIndex(window._lang_combo.findData("en"))
        _pump(qapp)
        assert window.tabs.tabText(0) == "Ephemeris"
        assert window.btn_calc.text() == "Calculate"
        assert window._edit_datetime() == DTE
        assert window.entry_lat.text() == "48.8566"
        assert prefs.get("lang") == "en"

    @pytest.mark.parametrize("lang, word", [("es", "Efemérides"), ("de", "Ephemeriden")])
    def test_every_language_builds(self, window, qapp, lang, word):
        window._lang_combo.setCurrentIndex(window._lang_combo.findData(lang))
        _pump(qapp)
        assert window.tabs.tabText(0).endswith(word)
        assert "[" not in window.sun_labels["rise"].text()

    @pytest.mark.parametrize("theme", ["jour", "observation"])
    def test_theme_switch(self, window, qapp, theme):
        """The theme selector of the side panel applies the theme at once."""
        import settings as prefs
        from config import Config
        window.theme_selector.buttons[theme].click()
        _pump(qapp)
        assert Config.THEME == theme and prefs.get("theme") == theme
        assert Config.CIEL_000.lower() in qapp.styleSheet().lower()
        assert window.theme_selector.buttons[theme].isChecked()
        assert window._edit_datetime() == DTE

    def test_reset_restores_defaults(self, window, qapp, monkeypatch):
        import gui
        import settings as prefs
        from config import Config
        window.theme_selector.buttons["observation"].click()
        _pump(qapp)
        monkeypatch.setattr(gui, "QMessageBox", _yes_box(gui))
        window._reset_settings()
        _pump(qapp)
        assert prefs.get("theme") == "nuit" and Config.THEME == "nuit"
        assert window._edit_datetime() == DTE


# ──────────────────────────────────────────────────────────────────────
# 3. Favourites
# ──────────────────────────────────────────────────────────────────────

class TestFavorites:
    def test_apply_favorite(self, window):
        window._apply_favorite(window.combo_fav.findText("Tokyo"))
        assert window.entry_lat.text() == "35,6762"
        assert window.location_name == "Tokyo"
        assert "Tokyo" in window._lbl_pos.text()

    def test_typing_coordinates_clears_the_place_name(self, window):
        window._apply_favorite(window.combo_fav.findText("Paris"))
        window._on_coords_edited("48.9")
        assert window.location_name == "" and window.combo_fav.currentIndex() == -1

    def test_save_and_delete(self, window, monkeypatch):
        import gui

        class Input(gui.QInputDialog):
            @staticmethod
            def getText(*_args, **_kwargs):
                return "Maison", True

        monkeypatch.setattr(gui, "QInputDialog", Input)
        window.save_location()
        with open(gui._FAVORITES_FILE, encoding="utf-8") as f:
            assert json.load(f)["Maison"] == {"lat": 49.6333, "lon": -1.6167, "elev": 0}
        assert window.combo_fav.currentText() == "Maison"

        monkeypatch.setattr(gui, "QMessageBox", _yes_box(gui))
        window.delete_location()
        with open(gui._FAVORITES_FILE, encoding="utf-8") as f:
            assert "Maison" not in json.load(f)


# ──────────────────────────────────────────────────────────────────────
# 4. Events
# ──────────────────────────────────────────────────────────────────────

def _event_cards(window):
    cards = []
    for i in range(window._evt_layout.count()):
        w = window._evt_layout.itemAt(i).widget()
        if isinstance(w, QFrame) and w.property("eventCard"):
            cards.append(w)
    return cards


class TestEvents:
    def test_eclipse_search(self, window):
        """From 1 November 2026: 2 solar eclipses, 3 penumbral lunar ones."""
        window._search_eclipses_gui()
        cards = _event_cards(window)
        assert len(cards) == 5
        assert QApplication.overrideCursor() is None
        texts = [" ".join(lbl.text() for lbl in c.findChildren(QLabel)) for c in cards]
        assert "Annulaire" in texts[0] and "06/02/2027" in texts[0]
        assert "Totale" in texts[3] and "02/08/2027" in texts[3]
        assert all("Pénombrale" in texts[i] for i in (1, 2, 4))
        assert "Incertaine" in texts[2]              # 18/07/2027, magnitude 0.001

    def test_eclipse_time_is_greatest_eclipse_in_ut(self, window):
        """Maximum in UT, to the minute: NASA 16:00:47 and 10:07:49 TD, ΔT ≈ 69 s."""
        window._search_eclipses_gui()
        texts = [" ".join(lbl.text() for lbl in c.findChildren(QLabel))
                 for c in _event_cards(window)]
        assert "06/02/2027 16:00 TU" in texts[0]
        assert "02/08/2027 10:07 TU" in texts[3]

    def test_conjunction_time_and_kind(self, window):
        """Mercury at inferior conjunction on 04/11/2026 at 14:24 UT (Horizons 14:24:19)."""
        window._search_conjunctions_gui()
        texts = [" ".join(lbl.text() for lbl in c.findChildren(QLabel))
                 for c in _event_cards(window)]
        first = next(text for text in texts if "Mercure en conjonction inférieure" in text)
        assert "04/11/2026 14:24 TU" in first and "Mercure au sud du Soleil" in first
        assert "Heure locale" not in first                  # place in UT: nothing to add
        assert any("plus grande élongation ouest (matin)" in text for text in texts)
        assert any("Mars au nord de Jupiter" in text for text in texts)

    def test_conjunction_local_time(self, window):
        """The local time of the place, Paris winter time included, under the UT instant."""
        window.tz_menu.setCurrentIndex(window.tz_menu.findData("auto"))     # Cherbourg
        window._search_conjunctions_gui()
        texts = [" ".join(lbl.text() for lbl in c.findChildren(QLabel))
                 for c in _event_cards(window)]
        first = next(text for text in texts if "Mercure en conjonction inférieure" in text)
        assert "Heure locale 04/11 15:24 (Europe/Paris)" in first

    def test_map_of_a_conjunction(self, window, qapp):
        """The "Map" button of a conjunction opens the path of the bodies among the stars."""
        from PyQt6.QtWidgets import QPushButton
        window._search_conjunctions_gui()
        qapp.processEvents()
        buttons = [b for card in _event_cards(window) for b in card.findChildren(QPushButton)
                   if b.text() == "Carte"]
        assert 0 < len(buttons) < len(_event_cards(window))     # seasons, perigees: no map
        buttons[0].click()
        qapp.processEvents()
        dlg = window._event_dialog
        assert dlg.isVisible() and dlg.windowTitle() == "Carte de l'évènement"
        dlg.close()

    def _texts(self, window):
        return [" ".join(lbl.text() for lbl in c.findChildren(QLabel)) for c in _event_cards(window)]

    def test_moon_seasons_and_minor_planets(self, window):
        """Moon, seasons and minor planets among the events of the year."""
        window._search_conjunctions_gui()
        texts = self._texts(window)
        assert any("Solstice de décembre" in x and "21/12/2026 20:50 TU" in x for x in texts)
        assert any("Lune au périgée" in x and "Super lune" in x for x in texts)     # 24/12/2026
        assert any("Lune et" in x for x in texts)
        assert any("Vesta à l'opposition" in x for x in texts) is False           # in 2027: no
        assert any(x.startswith("☍") or "à l'opposition" in x for x in texts)

    def test_visibility_line(self, window):
        """Each conjunction says whether it can be seen from here, and when."""
        window._search_conjunctions_gui()
        for text in self._texts(window):
            if "Lune et" in text:
                assert "Visible" in text or "Inobservable" in text
                break
        else:
            pytest.fail("aucune conjonction de la Lune")

    def test_filters(self, window):
        window._search_conjunctions_gui()
        everything = len(_event_cards(window))
        window._evt_filters["moon"].setChecked(False)
        without_moon = self._texts(window)
        assert len(without_moon) < everything and not any("Lune et" in x for x in without_moon)
        window._evt_filters["visible"].setChecked(True)
        visible = self._texts(window)
        assert len(visible) < len(without_moon)
        assert not any("Inobservable" in x for x in visible)
        window._evt_filters["moon"].setChecked(True)
        window._evt_filters["visible"].setChecked(False)
        assert len(_event_cards(window)) == everything

    def test_export_ics(self, window, tmp_path, monkeypatch):
        """The events shown go into an iCalendar calendar."""
        import gui
        target = tmp_path / "agenda"
        monkeypatch.setattr(gui.QFileDialog, "getSaveFileName",
                            staticmethod(lambda *a, **k: (str(target), "")))
        window._evt_filters["moon"].setChecked(False)
        window._search_conjunctions_gui()
        assert window._btn_ics.isEnabled()
        window._btn_ics.click()
        text = (tmp_path / "agenda.ics").read_bytes().decode("utf-8")      # CRLF kept
        assert text.startswith("BEGIN:VCALENDAR\r\n") and text.endswith("END:VCALENDAR\r\n")
        assert text.count("BEGIN:VEVENT") == len(_event_cards(window))
        assert "SUMMARY:Solstice de décembre\r\n" in text and "DTSTART:20261221T205014Z" in text
        assert all(len(line.encode("utf-8")) <= 75 for line in text.split("\r\n"))
        window._evt_filters["moon"].setChecked(True)

    def test_meteor_showers(self, window, tmp_path, monkeypatch):
        """Meteor showers: their filter, the night of the peak seen from here, the calendar."""
        import gui
        window._search_conjunctions_gui()
        for key, box in window._evt_filters.items():
            box.setChecked(key == "meteors")
        texts = self._texts(window)
        assert len(texts) == 13 and all(x.startswith("☄") for x in texts)
        gem = next(x for x in texts if "Maximum des Géminides" in x)
        assert "14/12/2026 13:41 TU" in gem and "Taux zénithal 150 météores/h" in gem
        assert "Actives du 04/12 au 20/12" in gem and "Lune couchée : pas de gêne" in gem
        assert re.search(r"Meilleur moment vers \d\d:\d\d : radiant à \d+° de hauteur", gem)
        qua = next(x for x in texts if "Maximum des Quadrantides" in x)
        assert "04/01/2027" in qua
        assert any("gêne forte" in x for x in texts)            # the Ursids, at full Moon
        target = tmp_path / "agenda.ics"
        monkeypatch.setattr(gui.QFileDialog, "getSaveFileName",
                            staticmethod(lambda *a, **k: (str(target), "")))
        window._btn_ics.click()
        agenda = target.read_bytes().decode("utf-8")
        assert agenda.count("BEGIN:VEVENT") == 13 and "SUMMARY:Maximum des Géminides\r\n" in agenda
        for box in window._evt_filters.values():
            box.setChecked(box is not window._evt_filters["visible"])

    def test_eclipses_seen_from_here(self, window):
        """Cherbourg: the annular eclipse of 06/02/2027 does not pass there, the one of 02/08/2027 does."""
        window._search_eclipses_gui()
        texts = self._texts(window)
        assert "Ici : pas d'éclipse" in texts[0]
        assert "Ici, heure locale : début" in texts[3] and "% du Soleil caché" in texts[3]

    def test_conjunction_search_replaces_previous_results(self, window):
        window._search_eclipses_gui()
        n_eclipses = len(_event_cards(window))
        window._search_conjunctions_gui()
        cards = _event_cards(window)
        assert cards and len(cards) != n_eclipses


# ──────────────────────────────────────────────────────────────────────
# 5. Sky map, trajectories: tooltips and cards
# ──────────────────────────────────────────────────────────────────────

def _vega(window):
    return next(o for o in window._sky_objects if o["name"] == "Vega")


class TestSkyMapAndTrajectory:
    def test_star_card_names_its_constellation(self, window):
        title, rows = window._object_details(_vega(window))
        assert title == "Vega"
        assert ("Constellation", "Lyre (Lyr)") in rows
        dialog = window._build_detail_dialog(_vega(window))
        assert isinstance(dialog, QDialog)
        dialog.close()

    def test_cards_for_every_kind_of_object(self, window):
        scene = window._sky_scene
        for obj in [scene["sun"], scene["moon"]] + scene["planets"]:
            title, rows = window._object_details(obj)
            assert title and len(rows) >= 6
            window._build_detail_dialog(obj).close()

    def test_sky_tooltip(self, window, qapp):
        window.tabs.setCurrentIndex(2)
        _pump(qapp)
        window.canvas_sky.draw()
        vega = _vega(window)
        x, y = window._sky_ax.transData.transform((vega["x"], vega["y"]))
        window._on_sky_hover(MouseEvent("motion_notify_event", window.canvas_sky, x, y))
        tip = window._sky_tip.artist
        assert tip.get_visible() and tip.get_text().startswith("Vega")
        window._on_sky_leave(None)
        assert not tip.get_visible()

    def test_trajectory_tooltip(self, window, qapp):
        window.tabs.setCurrentIndex(1)
        _pump(qapp)
        window.canvas_traj.draw()
        x, y = window._traj_ax.transData.transform((12.0, 0.0))
        window._on_traj_hover(MouseEvent("motion_notify_event", window.canvas_traj, x, y))
        tip = window._traj_tip.artist
        assert tip.get_visible() and tip.get_text().startswith("12:00 TU")

    def test_magnitude_limit_filters_the_map(self, window, qapp):
        import settings as prefs
        n_all = len(window.visible_stars)
        window._mag_slider.setValue(10)           # magnitude 1.0
        window.calculate()
        assert prefs.get("mag_limit") == 1.0
        assert 0 < len(window.visible_stars) < n_all


# ──────────────────────────────────────────────────────────────────────
# 6. Real time
# ──────────────────────────────────────────────────────────────────────

class TestLiveAndExport:
    def test_live_mode(self, window):
        window.btn_live.toggle()
        assert window.live_mode and window.dt_edit.isReadOnly()
        assert window._live_timer.isActive()
        assert window._edit_datetime() != DTE
        window.btn_live.toggle()
        assert not window.live_mode and not window._live_timer.isActive()


# ──────────────────────────────────────────────────────────────────────
# 7. Rules of the Astræos design
# ──────────────────────────────────────────────────────────────────────

# Astronomical symbols allowed (Astraeos Symboles font), dot of the badges
# astronomical symbols of the Astraeos Symboles font (text presentation, U+FE0E)
_ALLOWED = set("☉☽☾☿♀♂♃♄♅♆♇⊕♈★●○☌☍☄⚳⚴⚵⚶\u2bf1\u2bf2\U0001f77b\U0001f77c")


def _is_emoji(ch):
    code = ord(ch)
    return ch not in _ALLOWED and (0x1F000 <= code <= 0x1FAFF or 0x2600 <= code <= 0x27BF
                                   or 0x2B00 <= code <= 0x2BFF)


class TestAstraeosRules:
    @pytest.mark.parametrize("lang", ["fr", "en", "es", "de"])
    def test_no_emoji_in_the_interface(self, window, qapp, lang):
        """"Interface: no emoji": neither in the texts nor in the tabs."""
        window._lang_combo.setCurrentIndex(window._lang_combo.findData(lang))
        _pump(qapp)
        texts = [w.text() for w in window.findChildren(QLabel)]
        texts += [w.text() for w in window.findChildren(QAbstractButton)]
        texts += [window.tabs.tabText(i) for i in range(window.tabs.count())]
        bad = {text for text in texts if any(_is_emoji(ch) for ch in text)}
        assert not bad, bad

    def test_symbols_use_text_presentation(self, window):
        """Each body symbol is followed by U+FE0E (never shown as an emoji)."""
        name = window._planet_items["Venus"]["col_planet"].text()
        assert name.startswith("\u2640\ufe0e")

    def test_single_gold_area(self, window):
        """A single primary button (gold fill) in the window."""
        from PyQt6.QtWidgets import QPushButton
        principal = [b for b in window.findChildren(QPushButton)
                     if b.property("variant") == "principal" and b.isVisibleTo(window)]
        assert principal == [window.btn_calc]

    def test_focused_field_shows_the_gold_ring(self, window, qapp):
        """v4.8: the box of a field with the keyboard focus is outlined in gold (the
        property was named "focus", Qt's own read-only one, and never changed)."""
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QFocusEvent
        from config import Config
        for field in (window.field_lat, window.field_date):
            box = field.box
            assert box.grab().toImage().pixelColor(0, 20).name() == Config.ENCRE_ATTENUEE
            qapp.sendEvent(field.input, QFocusEvent(QEvent.Type.FocusIn, Qt.FocusReason.TabFocusReason))
            _pump(qapp, 3)
            assert box.property("focused") is True
            assert box.grab().toImage().pixelColor(0, 20).name() == Config.OR
            qapp.sendEvent(field.input, QFocusEvent(QEvent.Type.FocusOut, Qt.FocusReason.TabFocusReason))
            _pump(qapp, 3)
            assert box.grab().toImage().pixelColor(0, 20).name() == Config.ENCRE_ATTENUEE

    def test_live_mode_is_a_pressed_toggle(self, window):
        """Real time: toggle pressed and "Live" badge."""
        window.btn_live.toggle()
        assert window.btn_live.isChecked()
        assert window._lbl_live.isVisibleTo(window)
        assert window._lbl_live.text().endswith("En direct")
        window.btn_live.toggle()


# ──────────────────────────────────────────────────────────────────────
# Geolocation: the device's service, the IP address as a fallback
# ──────────────────────────────────────────────────────────────────────

class _FakeSource:
    """Simulated location service: answers a position, or the error *error*
    (0 access denied, 1 closed, 2 unknown, 4 timeout), with or without a last
    known position."""
    def __init__(self, coord, error=2, last=None):
        from PyQt6.QtCore import QObject, pyqtSignal

        class Source(QObject):
            positionUpdated = pyqtSignal(object)
            errorOccurred = pyqtSignal(int)

            def lastKnownPosition(self, *_args):
                from PyQt6.QtCore import QDateTime
                from PyQt6.QtPositioning import QGeoCoordinate, QGeoPositionInfo
                if last is None:
                    return QGeoPositionInfo()
                return QGeoPositionInfo(QGeoCoordinate(*last), QDateTime.currentDateTime())

            def requestUpdate(self, _timeout):
                if coord is None:
                    self.errorOccurred.emit(error)
                else:
                    from PyQt6.QtCore import QDateTime
                    from PyQt6.QtPositioning import QGeoCoordinate, QGeoPositionInfo
                    info = QGeoPositionInfo(QGeoCoordinate(*coord), QDateTime.currentDateTime())
                    info.setAttribute(QGeoPositionInfo.Attribute.HorizontalAccuracy, 25.0)
                    self.positionUpdated.emit(info)

        self.cls = Source

    def createDefaultSource(self, parent):
        return self.cls(parent)


class _FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class TestMoonCalendar:
    def _cells(self, dlg):
        return [w for w in dlg.findChildren(QFrame) if w.property("calendarDay") and w.isVisibleTo(dlg)]

    def test_month_and_navigation(self, window, qapp):
        """November 2026 (times in UT here), then December, then back through the year."""
        window._show_moon_calendar()
        _pump(qapp)
        dlg = window._calendar_dialog
        assert dlg._title.text() == "Novembre 2026" and len(self._cells(dlg)) == 30
        texts = [" ".join(l.text() for l in c.findChildren(QLabel)) for c in self._cells(dlg)]
        assert "Pleine lune 14:54" in texts[23] and texts[23].startswith("24 100 %")   # 14:53:34
        assert "↑ —" in texts[1]                                  # no moonrise on the 2nd
        window._fill_moon_calendar(+1)
        _pump(qapp)                                   # the new cells show on the next turn
        assert dlg._title.text() == "Décembre 2026" and len(self._cells(dlg)) == 31
        window._fill_moon_calendar(-12)
        assert dlg._title.text() == "Décembre 2025"
        dlg.close()
        qapp.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        assert window._calendar_dialog is None

    def test_first_day_of_the_week(self, window, qapp):
        """In French, the week starts on Monday: 1 November 2026, a Sunday, is in the 7th column."""
        window._show_moon_calendar(2026, 11)
        dlg = window._calendar_dialog
        first = self._cells(dlg)[0]
        assert dlg._grid.getItemPosition(dlg._grid.indexOf(first))[:2] == (1, 6)
        dlg.close()


class TestOrreryAnimation:
    def _planets_tab(self, window, qapp):
        window.tabs.setCurrentWidget(next(p for p, n in window._chart_tabs.items() if n == "orrery"))
        _pump(qapp)

    def test_steps_move_the_planets(self, window, qapp):
        self._planets_tab(window, qapp)
        assert window._orrery_date.text() == "01/11/2026"
        mars = next(m for name, m, _l in window.fig_orrery._orrery_moving if name == "Mars")
        before = mars.get_xydata().copy()
        window._orrery_speed.setCurrentIndex(2)                       # 1 month per step
        window._orrery_step(+1)
        assert window._orrery_offset == 30.0 and window._orrery_date.text() == "01/12/2026"
        assert window._orrery_date.property("tone") == "or"
        assert (mars.get_xydata() != before).any()
        window._orrery_step(-1)
        assert window._orrery_offset == 0.0 and window._orrery_date.property("tone") is None

    def test_play_pause_and_leaving_the_tab(self, window, qapp):
        self._planets_tab(window, qapp)
        window._orrery_play.click()
        assert window._orrery_timer.isActive()
        window.tabs.setCurrentIndex(0)
        assert not window._orrery_timer.isActive()

    def test_back_to_the_date(self, window, qapp):
        self._planets_tab(window, qapp)
        window._orrery_speed.setCurrentIndex(3)                       # 1 year per step
        window._orrery_step(+1)
        window._reset_orrery()
        assert window._orrery_offset == 0.0 and window._orrery_date.text() == "01/11/2026"

    def test_stops_at_the_end_of_the_ephemeris(self, window, qapp):
        self._planets_tab(window, qapp)
        window._toggle_orrery()
        window._orrery_offset = 200 * 365.25
        window._orrery_step(+1)
        assert window._orrery_date.text() == "30/12/2149" and not window._orrery_timer.isActive()


class TestSatellites:
    @pytest.fixture
    def orbits(self, monkeypatch):
        """Background tasks run at once; the elements of 7 November 2026."""
        import gui
        import satellites
        from tests.test_satellites import ELEMENTS

        def run_now(func, on_done, on_error):
            try:
                result = func()
            except Exception as exc:  # noqa: BLE001
                on_error(exc)
            else:
                on_done(result)
        monkeypatch.setattr(gui, "_run_in_background", run_now)
        answer = {"refresh": (ELEMENTS, None)}
        monkeypatch.setattr(satellites, "refresh", lambda: answer["refresh"])
        return answer

    def test_search(self, window, qapp, orbits, tmp_path, monkeypatch):
        """From Cherbourg, from 10 November 2026 (times in UT here): the ISS in the evening."""
        import gui
        window._set_datetime(datetime(2026, 11, 10, 12, 0))
        window.calculate()
        window._search_satellites_gui()
        texts = [" ".join(l.text() for l in c.findChildren(QLabel)) for c in _event_cards(window)]
        assert len(texts) >= 8 and QApplication.overrideCursor() is None
        assert all("Station spatiale internationale (ISS)" in x or "Tiangong" in x for x in texts)
        assert any("entre dans l'ombre de la Terre" in x for x in texts)
        assert re.search(r"Visible \d+ min \d\d s", texts[0])
        target = tmp_path / "passes.ics"
        monkeypatch.setattr(gui.QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(target), "")))
        window._btn_ics.click()
        assert target.read_bytes().decode("utf-8").count("BEGIN:VEVENT") == len(texts)

    def test_offline_without_orbits(self, window, orbits):
        import satellites
        orbits["refresh"] = ({}, satellites.SatelliteError("offline"))
        window._search_satellites_gui()
        listed = [window._evt_layout.itemAt(i).widget() for i in range(window._evt_layout.count())]
        assert any(isinstance(w, QLabel) and "offline" in w.text() for w in listed)
        assert not _event_cards(window)

    def test_tonight_from_the_orbits_on_disk(self, window, qapp, orbits):
        import satellites
        from tests.test_satellites import ELEMENTS
        satellites.save(ELEMENTS)
        window._set_datetime(datetime(2026, 11, 14, 20, 0))
        window.calculate()
        line = next(text for text, _tone in window._tonight_lines() if text.startswith("Passages"))
        assert re.match(r"Passages : ISS 18:2\d–18:2\d \(\d+° [A-Z]+\)", line)


class TestDeepSky:
    def test_on_the_sky_map(self, window, qapp):
        window.tabs.setCurrentWidget(next(p for p, n in window._chart_tabs.items() if n == "sky"))
        _pump(qapp)
        dso = [o for o in window._sky_objects if o["kind"] == "deep_sky"]
        assert 30 < len(dso) < 110 and all(o["alt"] > 0 for o in dso)
        m31 = next(o for o in dso if o["m"] == 31)
        title, rows = window._object_details(m31)
        assert title == "M31 Galaxie d'Andromède"
        assert ("Type", "Galaxie") in rows and ("Désignation", "NGC 224") in rows
        assert ("Taille apparente", "178′ × 70′") in rows
        window._messier_box.setChecked(False)
        assert not [o for o in window._sky_objects if o["kind"] == "deep_sky"]
        window._messier_box.setChecked(True)

    def test_tonight_line(self, window):
        line = next(text for text, _tone in window._tonight_lines() if text.startswith("Ciel profond"))
        assert "M31 Galaxie d'Andromède (82°, 22:05)" in line and line.count("·") == 4

    def test_every_common_name_is_translated(self):
        import json
        from engine import messier_catalog
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for lang in ("fr", "en", "es", "de"):
            with open(os.path.join(root, "locales", f"{lang}.json"), encoding="utf-8") as f:
                names = json.load(f)["messier"]
            missing = [o["m"] for o in messier_catalog() if o["name"] and f"name_{o['m']}" not in names]
            assert not missing, (lang, missing)


class TestComets:
    def _at(self, window, qapp, when, lat=None, lon=None):
        if lat is not None:
            window.entry_lat.setText(str(lat).replace(".", ","))
            window.entry_lon.setText(str(lon).replace(".", ","))
        window._set_datetime(when)
        window.calculate()
        _pump(qapp)

    def test_planet_table_group(self, window, qapp):
        self._at(window, qapp, datetime(2027, 8, 25, 3))
        window._on_planet_group("comets")
        rows = {name: items for name, items in window._planet_items.items()
                if not window.planet_table.isRowHidden(items["col_planet"].row())}
        assert set(rows) == set(COMETS)
        honda = rows["Honda"]["col_planet"]
        assert honda.text() == "\u2604\ufe0e 45P/Honda" and honda.toolTip().startswith("45P/Honda-Mrkos-Pajdušáková")
        assert rows["Honda"]["col_mag"].text() == "8,2"
        assert window._planet_empty.isHidden()

    def test_not_shown_outside_their_tables(self, window, qapp):
        self._at(window, qapp, datetime(2035, 6, 1))
        window._on_planet_group("comets")
        assert all(window.planet_table.isRowHidden(window._planet_items[n]["col_planet"].row())
                   for n in COMETS)
        assert not window._planet_empty.isHidden() and "C/2026 C1" in window._planet_empty.text()
        window._on_planet_group("planets")

    def test_data_window_and_events(self, window, qapp):
        self._at(window, qapp, datetime(2027, 8, 25, 3))
        window._show_body_detail("Honda")
        texts = [lbl.text() for lbl in window._detail_dialog.findChildren(QLabel)]
        assert "☄\ufe0e 45P/Honda-Mrkos-Pajdušáková" in texts and "Comète" in texts
        window._detail_dialog.close()
        window._search_conjunctions_gui()
        for key, box in window._evt_filters.items():
            box.setChecked(key == "comets")
        cards = [" ".join(l.text() for l in c.findChildren(QLabel)) for c in _event_cards(window)]
        assert any("45P/Honda-Mrkos-Pajdušáková au périhélie" in c and "0,559 UA" in c for c in cards)
        for box in window._evt_filters.values():
            box.setChecked(box is not window._evt_filters["visible"])

    def test_on_the_sky_map(self, window, qapp, monkeypatch):
        """C/2026 C1 (magnitude 6.6) seen from Santiago, limit 7: on the sky map."""
        monkeypatch.setattr(window, "_mag_limit", lambda: 7.0)
        self._at(window, qapp, datetime(2028, 11, 11, 3), -33.45, -70.67)
        assert "Tsuchinshan" in [o.get("name") for o in window._sky_objects]
        window.tabs.setCurrentWidget(next(p for p, n in window._chart_tabs.items() if n == "sky"))
        _pump(qapp)                                       # the map draws, name included


class TestPlaceSearch:
    def test_suggestions_then_choice(self, window, qapp):
        """"londres" offers London; choosing it fills place, elevation and name."""
        window._on_place_typed("londres")
        assert window._place_model.stringList() == ["London · England · GB"]
        window._on_place_chosen("London · England · GB")
        _pump(qapp)
        assert window.entry_lat.text() == "51,5085" and window.entry_lon.text() == "−0,1257"
        assert window.location_name == "London" and window.entry_place.text() == ""
        assert window._lbl_pos.text().startswith("London · 51,5085° N")
        assert window.combo_fav.currentIndex() == -1

    def test_return_takes_the_first(self, window, qapp):
        window.entry_place.setText("tokyo")
        window._on_place_return()
        _pump(qapp)
        assert window.location_name == "Tokyo" and window.entry_lat.text().startswith("35,6")

    def test_unknown_place(self, window):
        window.entry_place.setText("zzzqqq")
        window._on_place_return()
        assert "zzzqqq" in window.statusBar().currentMessage()

    def test_one_letter_is_not_enough(self, window):
        window._on_place_typed("p")
        assert window._place_model.stringList() == []

    def test_name_without_network(self, monkeypatch):
        """Without Nominatim, the nearest city of the offline list names the point."""
        import gui
        monkeypatch.setattr(gui, "_nominatim_name", lambda lat, lon: "")
        assert gui._place_name(49.6333, -1.6167) == "Cherbourg"
        assert gui._place_name(48.0, -30.0) == ""


class TestGeolocation:
    def test_device_position_is_used(self, window, monkeypatch):
        """Cherbourg given by the device's service, named by OpenStreetMap."""
        import gui
        monkeypatch.setattr(gui, "QGeoPositionInfoSource", _FakeSource((49.6386, -1.6164)))
        monkeypatch.setattr(gui, "_place_name", lambda lat, lon: "Cherbourg-en-Cotentin")
        window.geolocate()
        assert window.entry_lat.text().replace(",", ".") == "49.6386"
        assert window.location_name == "Cherbourg-en-Cotentin"
        assert "±25 m" in window.statusBar().currentMessage()

    def test_ip_address_only_as_a_fallback(self, window, monkeypatch):
        """Silent service: position of the IP address, announced as approximate."""
        import gui
        monkeypatch.setattr(gui, "QGeoPositionInfoSource", _FakeSource(None))
        answer = {"status": "success", "city": "Paris", "country": "France",
                  "lat": 48.8566, "lon": 2.3522, "timezone": "Europe/Paris"}
        monkeypatch.setattr(gui.urllib.request, "urlopen",
                            lambda *a, **k: _FakeResponse(json.dumps(answer).encode()))
        window.geolocate()
        assert window.location_name == "Paris"
        assert "approximative" in window.statusBar().currentMessage()

    def _ip_answer(self, monkeypatch):
        import gui
        answer = {"status": "success", "city": "Paris", "country": "France",
                  "lat": 48.8566, "lon": 2.3522, "timezone": "Europe/Paris"}
        monkeypatch.setattr(gui.urllib.request, "urlopen",
                            lambda *a, **k: _FakeResponse(json.dumps(answer).encode()))

    def test_access_denied_is_explained(self, window, monkeypatch):
        """Issue #19: access denied by Windows — the window says so and opens the settings."""
        import gui
        monkeypatch.setattr(gui, "QGeoPositionInfoSource", _FakeSource(None, error=0))
        monkeypatch.setattr(gui.sys, "platform", "win32")
        opened = []
        monkeypatch.setattr(gui.QDesktopServices, "openUrl", staticmethod(lambda url: opened.append(url)))
        self._ip_answer(monkeypatch)
        window.geolocate()
        box = window._geo_dialog
        assert box.isVisible() and "Paris" in box.text()
        assert "Autoriser les applications de bureau" in box.informativeText()
        button = next(b for b in box.buttons() if b.text() == "Ouvrir les réglages de localisation")
        button.click()
        assert opened and opened[0].toString() == "ms-settings:privacy-location"

    def test_last_known_position_before_the_ip_address(self, window, monkeypatch):
        """Timeout: the device's last known position rather than the IP address."""
        import gui
        monkeypatch.setattr(gui, "QGeoPositionInfoSource",
                            _FakeSource(None, error=4, last=(49.6386, -1.6164)))
        monkeypatch.setattr(gui, "_place_name", lambda lat, lon: "Cherbourg-en-Cotentin")
        monkeypatch.setattr(gui.urllib.request, "urlopen", lambda *a, **k: pytest.fail("adresse IP"))
        window.geolocate()
        assert window.location_name == "Cherbourg-en-Cotentin"

    def test_no_window_at_startup(self, window, monkeypatch):
        """At startup (automatic geolocation), the status bar only."""
        import gui
        monkeypatch.setattr(gui, "QGeoPositionInfoSource", _FakeSource(None, error=4))
        self._ip_answer(monkeypatch)
        window._geo_dialog = None
        window.geolocate(interactive=False)
        assert window._geo_dialog is None
        assert "approximative" in window.statusBar().currentMessage()


# ──────────────────────────────────────────────────────────────────────
# Coordinates tab and angle format
# ──────────────────────────────────────────────────────────────────────

class TestCoordinatesTab:
    """Coordinates tab: x, y, z and angles at the same time."""

    BODIES = ["Soleil", "Lune", "Mercure", "Vénus", "Terre", "Mars", "Cérès", "Pallas", "Junon",
              "Vesta", "Jupiter", "Saturne", "Uranus", "Neptune", "Pluton", "Hauméa", "Makémaké",
              "Éris", "Sedna"]

    def _open(self, window):
        window.tabs.setCurrentWidget(window._coord_page)

    def _choose(self, window, key, value):
        menu = window.coord_menus[key]
        menu.setCurrentIndex(menu.findData(value))

    def _row(self, window, name):
        table = window.coord_table
        r = next(r for r in range(table.rowCount()) if table.item(r, 0).text().endswith(name))
        return [table.item(r, c).text() for c in range(table.columnCount())]

    def _headers(self, window):
        table = window.coord_table
        return [table.horizontalHeaderItem(c).text() for c in range(table.columnCount())]

    def test_short_lists_show_every_choice(self, window, qapp):
        """Lists in list mode: no choice hidden behind scroll arrows."""
        self._open(window)
        for menu in window.coord_menus.values():
            menu.showPopup()
            qapp.processEvents()
            view = menu.view()
            last = view.visualRect(menu.model().index(menu.count() - 1, 0))
            assert last.bottom() <= view.viewport().height(), menu.currentText()
            assert not view.verticalScrollBar().isVisible()
            menu.hidePopup()

    def test_default_heliocentric_and_equatorial(self, window):
        """By default: heliocentric x, y, z, equatorial angles."""
        self._open(window)
        assert self._headers(window) == [
            "Astre", "x (UA)", "y (UA)", "z (UA)", "Dist. (UA)", "Mag.",
            "Angle Soleil", "Const.", "Asc. droite α", "Déclinaison δ"]
        rows = [window.coord_table.item(r, 0).text() for r in range(window.coord_table.rowCount())]
        assert [r.split(" ", 1)[-1] for r in rows] == self.BODIES
        sun, earth = self._row(window, "Soleil"), self._row(window, "Terre")
        assert sun[1:5] == ["—"] * 4                      # the Sun is the origin
        assert sun[5].startswith("−26,7") and sun[7] == "Lib"
        assert earth[1] != "—" and earth[5:] == ["—"] * 5   # the Earth: x, y, z only
        assert sun[8].endswith("s")                           # right ascension in h m s

    def test_cartesian_and_angular_are_independent(self, window):
        """Changing the cartesian origin does not change the angles, and vice versa."""
        self._open(window)
        before = self._row(window, "Mars")
        self._choose(window, "cartesian", "geocentric")
        after = self._row(window, "Mars")
        assert after[1:5] != before[1:5] and after[8:] == before[8:]
        assert self._row(window, "Terre")[1:5] == ["—"] * 4
        self._choose(window, "angular", "horizontal")
        assert self._headers(window)[8:] == ["Azimut", "Hauteur"]
        assert self._row(window, "Mars")[1:5] == after[1:5]

    def test_ecliptic_from_the_sun_or_the_earth(self, window):
        self._open(window)
        assert not window.coord_menus["ecliptic_from"].isEnabled()
        self._choose(window, "angular", "ecliptic")
        assert window.coord_menus["ecliptic_from"].isEnabled()
        assert self._headers(window)[8:] == ["Longitude λ", "Latitude β"]
        assert self._row(window, "Soleil")[8:] == ["—", "—"]   # seen from the Sun
        assert self._row(window, "Terre")[8] != "—"
        assert "vues du Soleil" in window._coord_note.text()
        self._choose(window, "ecliptic_from", "earth")
        assert self._row(window, "Terre")[8:] == ["—", "—"]    # seen from the Earth
        assert self._row(window, "Soleil")[8] != "—"
        assert "vues de la Terre" in window._coord_note.text()

    @pytest.mark.parametrize("fmt, pattern", [("dms", r"^\d+h \d\dm \d\d,\ds$"),
                                              ("dm", r"^\d+h \d\d,\d{3}m$"),
                                              ("dd", r"^\d+,\d{5}h$")])
    def test_settings_format_applies_everywhere(self, window, fmt, pattern):
        """Format of the settings: the whole software, and the table that follows it by default."""
        self._open(window)
        assert window.coord_menus["angle"].currentData() == "global"
        combo = window._anglefmt_combo
        combo.setCurrentIndex(combo.findData(fmt))
        assert re.match(pattern, window.sun_labels["ra"].text())
        assert re.match(pattern, self._row(window, "Vénus")[8])

    def test_coordinates_format_only_for_the_table(self, window):
        """The format chosen in the tab only changes the table (issue #13)."""
        self._open(window)
        ephemeris = window.sun_labels["ra"].text()
        self._choose(window, "angle", "dd")
        assert re.match(r"^\d+,\d{5}h$", self._row(window, "Vénus")[8])
        assert window.sun_labels["ra"].text() == ephemeris
        window._anglefmt_combo.setCurrentIndex(window._anglefmt_combo.findData("dm"))
        assert re.match(r"^\d+h \d\d,\d{3}m$", window.sun_labels["ra"].text())
        assert re.match(r"^\d+,\d{5}h$", self._row(window, "Vénus")[8])   # keeps its own


# ──────────────────────────────────────────────────────────────────────
# Preferences and favourites outside the repository (~/.celeste)
# ──────────────────────────────────────────────────────────────────────

class TestUserFiles:
    def test_settings_live_in_the_user_folder(self, tmp_path, monkeypatch):
        """Written to the user's folder, created when needed."""
        import settings as prefs
        target = tmp_path / "celeste" / "settings.json"
        monkeypatch.setattr(prefs, "_SETTINGS_FILE", str(target))
        monkeypatch.setattr(prefs, "_LEGACY_SETTINGS_FILE", str(tmp_path / "absent.json"))
        prefs.load()
        prefs.set("theme", "jour")
        assert json.loads(target.read_text(encoding="utf-8"))["theme"] == "jour"

    def test_settings_of_a_previous_version_are_taken_over(self, tmp_path, monkeypatch):
        """A settings.json left in the application folder is taken over."""
        import settings as prefs
        legacy = tmp_path / "settings.json"
        legacy.write_text(json.dumps({"theme": "observation", "default_utc": 2}), encoding="utf-8")
        monkeypatch.setattr(prefs, "_SETTINGS_FILE", str(tmp_path / "user" / "settings.json"))
        monkeypatch.setattr(prefs, "_LEGACY_SETTINGS_FILE", str(legacy))
        prefs.load()
        assert prefs.get("theme") == "observation"
        assert prefs.get("default_tz") == "Etc/GMT-2"

    def test_favorites_start_from_the_default_list(self, window, tmp_path, monkeypatch):
        """Without saved favourites, the starting list (36 cities); saved in the user's folder."""
        import gui
        monkeypatch.setattr(gui, "_FAVORITES_FILE", str(tmp_path / "user" / "favorites.json"))
        monkeypatch.setattr(gui, "_LEGACY_FAVORITES_FILE", str(tmp_path / "absent.json"))
        favorites = window._load_favorites()
        assert len(favorites) == 36 and "Paris" in favorites
        assert favorites["Mexico"] == {"lat": 19.4326, "lon": -99.1332, "elev": 2240}
        window.favorites = {"Ici": {"lat": 1.0, "lon": 2.0, "elev": 0}}
        window._save_favorites()
        assert json.loads((tmp_path / "user" / "favorites.json").read_text(encoding="utf-8")) == \
            window.favorites

    def test_preloaded_places_in_the_interface_language(self, window, tmp_path, monkeypatch, qapp):
        """v4.8: London, Londres, Londres, London; a language without its own name: English."""
        import gui
        monkeypatch.setattr(gui, "_FAVORITES_FILE", str(tmp_path / "user" / "favorites.json"))
        monkeypatch.setattr(gui, "_LEGACY_FAVORITES_FILE", str(tmp_path / "legacy.json"))
        names = {lang: list(gui._default_favorites(lang)) for lang in ("fr", "en", "es", "de", "it")}
        assert all(len(n) == len(set(n)) == 36 for n in names.values())
        assert [n[14] for n in names.values()] == ["Londres", "London", "Londres", "London", "London"]
        assert "Pékin" in names["fr"] and "Beijing" in names["en"] and "Pekín" in names["es"] \
            and "Peking" in names["de"]
        assert all("names" not in place for place in gui._default_favorites("en").values())
        # the window follows the language, and keeps the chosen place
        window._rebuild()
        window.combo_fav.setCurrentIndex(window.combo_fav.findText("Londres"))
        window._apply_favorite(window.combo_fav.currentIndex())
        assert window.location_name == "Londres" and window.entry_elev.text() == "25"
        window._lang_combo.setCurrentIndex(window._lang_combo.findData("en"))
        _pump(qapp)
        assert window.combo_fav.currentText() == "London" and window.location_name == "London"
        assert window.combo_fav.findText("Londres") < 0
        assert window.entry_lat.text() == "51.5074"


class TestEclipseMap:
    def test_map_of_a_solar_eclipse(self, window, qapp):
        """The "Map" button of an eclipse opens its ground projection."""
        from PyQt6.QtWidgets import QPushButton
        window._search_eclipses_gui()
        qapp.processEvents()
        buttons = [b for b in window.findChildren(QPushButton) if b.text() == "Carte"]
        assert buttons, "aucun bouton Carte"
        buttons[0].click()
        qapp.processEvents()
        dlg = window._eclipse_dialog
        assert dlg.isVisible() and dlg.windowTitle() == "Éclipse projetée au sol"
        dlg.close()



# ──────────────────────────────────────────────────────────────────────
# Links: website, source code, coffee, requests on GitHub (issue #22)
# ──────────────────────────────────────────────────────────────────────

class TestLinks:
    def test_links_open_in_the_browser(self, window, monkeypatch):
        import gui
        opened = []
        monkeypatch.setattr(gui.QDesktopServices, "openUrl",
                            staticmethod(lambda url: opened.append(url.toString())))
        window._link_buttons["coffee"].click()
        window._link_buttons["bug"].click()
        window._propose_body.click()
        assert opened[0] == "https://buymeacoffee.com/gregorychau"
        assert opened[1].startswith("https://github.com/astraeos-dev/Celeste_App/issues/new?template=bug.yml")
        from config import APP_VERSION
        assert f"version={APP_VERSION}" in opened[1] and "system=" in opened[1]
        assert "template=body.yml" in opened[2]

    def test_every_issue_form_exists(self):
        """Each link to GitHub has its form in .github/ISSUE_TEMPLATE."""
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for template in ("bug", "feature", "body"):
            assert os.path.isfile(os.path.join(root, ".github", "ISSUE_TEMPLATE", f"{template}.yml"))



# ──────────────────────────────────────────────────────────────────────
# Data window of a body (issue #23)
# ──────────────────────────────────────────────────────────────────────

class TestDataWindow:
    def _rows(self, dlg):
        labels = [lbl.text() for lbl in dlg.findChildren(QLabel)]
        return labels

    def test_click_on_a_planet(self, window, qapp):
        """A click on Jupiter in the Planets tab opens its data window."""
        table = window.planet_table
        row = window._planet_items["Jupiter"]["col_planet"].row()
        table.cellClicked.emit(row, 3)
        qapp.processEvents()
        dlg = window._detail_dialog
        text = " | ".join(self._rows(dlg))
        assert dlg.isVisible() and "Jupiter" in dlg.windowTitle()
        for label in ("Diamètre apparent", "Fraction éclairée", "Angle de phase", "Temps de lumière",
                      "Distance au Soleil", "Lever", "Coucher", "Constellation"):
            assert label in text, label
        dlg.close()

    def test_click_in_the_coordinates_table(self, window, qapp):
        """Sun and Vesta from the Coordinates tab; the Earth has no card."""
        window.tabs.setCurrentWidget(window._coord_page)
        from engine import AstroEngine
        bodies = list(AstroEngine.BODIES)
        window._detail_dialog = None
        window.coord_table.cellClicked.emit(bodies.index("earth"), 0)
        assert window._detail_dialog is None
        window.coord_table.cellClicked.emit(bodies.index("sun"), 0)
        qapp.processEvents()
        text = " | ".join(self._rows(window._detail_dialog))
        assert "Soleil" in window._detail_dialog.windowTitle() and "Diamètre apparent" in text
        window._detail_dialog.close()
        window.coord_table.cellClicked.emit(bodies.index("Vesta"), 0)
        qapp.processEvents()
        assert "Planète mineure" in " | ".join(self._rows(window._detail_dialog))
        assert "(4) Vesta" in window._detail_dialog.windowTitle()
        window._detail_dialog.close()

    def test_closed_windows_are_freed(self, window, qapp):
        """Closed data windows and maps do not stay in memory, under the window."""
        for name in ("Jupiter", "Vesta", "sun"):
            window._show_body_detail(name)
            qapp.processEvents()
            window._detail_dialog.reject()
        qapp.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        assert window.findChildren(QDialog) == []



# ──────────────────────────────────────────────────────────────────────
# First launch: download of the ephemeris
# ──────────────────────────────────────────────────────────────────────

def tmp_user(engine):
    return os.path.dirname(engine.user_ephemeris_path())


class TestFirstLaunch:
    @pytest.fixture
    def missing(self, qapp, tmp_path, monkeypatch):
        """No ephemeris: main.ensure_ephemeris() downloads it (here, without network)."""
        import engine
        import main
        monkeypatch.setattr(engine, "ephemeris_path", lambda: str(tmp_path / "absente.bsp"))
        monkeypatch.setattr(engine, "user_ephemeris_path", lambda: str(tmp_path / "user" / "de440s.bsp"))
        loaded = []
        monkeypatch.setattr(engine, "load_ephemeris", lambda *a, **k: loaded.append(True))
        errors = []
        monkeypatch.setattr(QMessageBox, "critical",
                            staticmethod(lambda _parent, _title, text: errors.append(text)))
        return engine, main, loaded, errors

    def test_downloaded_with_its_progress(self, missing, monkeypatch):
        engine, main, loaded, errors = missing
        steps = []

        def download(progress=None, cancelled=None, **_kw):
            for done in (0, 16, 32):
                progress(done, 32)
                steps.append(cancelled())
        monkeypatch.setattr(engine, "download_ephemeris", download)
        assert main.ensure_ephemeris() is True
        assert steps == [False, False, False] and loaded == [True] and errors == []

    def test_cancelled(self, missing, monkeypatch):
        engine, main, loaded, errors = missing

        def download(**_kw):
            raise engine.DownloadCancelled("download cancelled")
        monkeypatch.setattr(engine, "download_ephemeris", download)
        assert main.ensure_ephemeris() is False
        assert loaded == [] and errors == []               # no message: the user chose to cancel

    def test_no_network(self, missing, monkeypatch):
        engine, main, loaded, errors = missing

        def download(**_kw):
            raise engine.EphemerisUnavailable("no network")
        monkeypatch.setattr(engine, "download_ephemeris", download)
        assert main.ensure_ephemeris() is False
        assert loaded == [] and len(errors) == 1
        assert "no network" in errors[0] and str(tmp_user(engine)) in errors[0]


# ──────────────────────────────────────────────────────────────────────
# Solar System tab and tab bar (v4.9, issue #35)
# ──────────────────────────────────────────────────────────────────────

class TestSolarSystemTab:
    def test_its_own_tab_after_the_planets(self, window, qapp):
        names = [window.tabs.tabText(i) for i in range(window.tabs.count())]
        assert names == ["Éphémérides", "Trajectoires", "Carte du ciel", "Planètes", "Système solaire",
                         "Coordonnées", "Événements", "Cibles", ""]
        assert window.tabs.tabToolTip(8) == "Paramètres" and not window.tabs.tabIcon(8).isNull()
        page = window.tabs.widget(4)
        assert window.canvas_orrery.isAncestorOf(window.canvas_orrery) and page.isAncestorOf(window.canvas_orrery)
        assert not window.tabs.widget(3).isAncestorOf(window.canvas_orrery)
        assert window.tabs.widget(3).isAncestorOf(window.planet_table)
        window.tabs.setCurrentIndex(4)
        _pump(qapp, 3)
        assert "orrery" not in window._dirty                     # drawn when its tab shows
        assert window.fig_orrery.axes

    def test_animation_stops_when_the_tab_is_left(self, window, qapp):
        window.tabs.setCurrentIndex(4)
        window._toggle_orrery()
        assert window._orrery_timer.isActive()
        window.tabs.setCurrentIndex(3)
        _pump(qapp, 3)
        assert not window._orrery_timer.isActive()

    def test_every_body_fits_in_the_planets_tab(self, window, qapp):
        """With the map gone, the table shows the 7 planets, 9 minor planets and the comets at once."""
        window.tabs.setCurrentIndex(3)
        window._planet_selector.buttons["all"].click()
        _pump(qapp, 3)
        table = window.planet_table
        assert table.maximumHeight() >= 40 * (16 + len(COMETS))
        assert table.height() >= 40 * 12                         # 820 px window: most of them, the rest scrolls
        window._planet_selector.buttons["planets"].click()

    @pytest.mark.parametrize("lang", ["fr", "en", "es", "de"])
    def test_the_nine_tabs_fit_at_the_minimum_width(self, window, qapp, lang):
        window._lang_combo.setCurrentIndex(window._lang_combo.findData(lang))
        _pump(qapp)
        window.resize(window.minimumWidth(), window.minimumHeight())
        _pump(qapp, 3)
        assert window.tabs.count() == 9
        assert window.tabs.tabBar().sizeHint().width() <= window.tabs.width()


# ──────────────────────────────────────────────────────────────────────
# Night planner, the Targets tab (v4.10, after uptonight)
# ──────────────────────────────────────────────────────────────────────

@pytest.fixture
def planner_tab(window, qapp, monkeypatch):
    """The Targets tab, its computations run at once."""
    import gui

    def run_now(func, on_done, on_error):
        try:
            result = func()
        except Exception as exc:  # noqa: BLE001
            on_error(exc)
        else:
            on_done(result)
    monkeypatch.setattr(gui, "_run_in_background", run_now)
    window.tabs.setCurrentWidget(window._planner_page)              # computes the night
    _pump(qapp, 3)
    return window


class TestPlanner:
    @staticmethod
    def _column(window, key, name):
        table = window._plan_tables[key]
        col = table.property("columns").index(name)
        return [table.item(r, col).text() for r in range(table.rowCount())]

    def test_computed_when_the_tab_shows(self, planner_tab):
        w = planner_tab
        assert w._plan is not None and w._plan["window"]["kind"] == "astro"
        assert w._plan_summary.text() == ("Nuit astronomique de 18:33 à 05:08. "
                                          "Lune éclairée à 49 % : écart minimal de 45°.")
        assert w._plan_status.text() == "8 cibles retenues sur 48 objets (Messier (110))."
        assert self._column(w, "deep_sky", "col_target")[:2] == ["M33 Galaxie du Triangle", "M34"]
        assert self._column(w, "deep_sky", "col_fraction")[0] == "91 %"
        assert self._column(w, "deep_sky", "col_best")[0] == "18:33–04:08"
        assert w._plan_tabs.tabText(0) == "Ciel profond (8)" and w._plan_tabs.tabText(1) == "Lune et planètes (6)"
        assert w._btn_plan_export.isEnabled()

    def test_not_computed_again_without_a_change(self, planner_tab, monkeypatch):
        import gui
        monkeypatch.setattr(gui.planner, "plan", lambda *a, **k: pytest.fail("computed again"))
        planner_tab._compute_plan()
        planner_tab.tabs.setCurrentIndex(0)
        planner_tab.tabs.setCurrentWidget(planner_tab._planner_page)

    def test_constraints_are_read_checked_and_kept(self, planner_tab):
        w = planner_tab
        w._plan_fields["fraction_min"][0].setText("80")
        w._plan_fields["size_max"][0].setText("1 000")                 # grouped as _num writes it
        w._plan_types["open_cluster"].setChecked(False)
        w._compute_plan()
        import settings as prefs
        kept = prefs.get("planner_constraints")
        assert kept["fraction_min"] == 0.8 and kept["size_max"] == 1000.0 and "open_cluster" not in kept["types"]
        assert all(o["fraction"] >= 0.8 and o["type"] != "open_cluster" for o in w._plan["deep_sky"])
        w._plan_fields["altitude_min"][0].setText("95")
        w._compute_plan(force=True)
        assert w._plan_fields["altitude_min"][1].error.text() == "Entre 0 et 90"
        assert w._plan_status.text() == "Corrigez les contraintes signalées."
        w._plan_fields["altitude_min"][0].setText("85")
        w._compute_plan(force=True)
        assert w._plan_fields["altitude_max"][1].error.text() == "Doit dépasser le minimum"

    def test_other_catalogue(self, planner_tab):
        w = planner_tab
        w._plan_catalog.setCurrentIndex(w._plan_catalog.findData("caldwell"))
        w._compute_plan()
        assert all(o["label"].startswith("C") for o in w._plan["deep_sky"])
        assert "Caldwell (109)" in w._plan_status.text()

    def test_bucket_and_done_lists_from_the_menu(self, planner_tab, qapp):
        import settings as prefs
        w = planner_tab
        table = w._plan_tables["deep_sky"]
        table.selectRow(3)                                              # M31
        w._plan_context_menu(table.visualItemRect(table.item(3, 0)).center())
        actions = {a.text(): a for a in w._plan_menu.actions()}
        assert set(actions) == {"Voir sur la carte du ciel", "Ajouter à « à faire »", "Marquer comme déjà fait"}
        actions["Marquer comme déjà fait"].trigger()
        w._plan_menu.close()
        assert prefs.get("planner_done") == ["M31"]
        assert "M31" not in [o["label"] for o in w._plan["deep_sky"]]
        w._plan_list_add("planner_bucket", ["M31", "M42"])                # to do again: out of "done"
        assert prefs.get("planner_done") == [] and prefs.get("planner_bucket") == ["M31", "M42"]
        targets = self._column(w, "deep_sky", "col_target")
        assert "★\ufe0e M42 Nébuleuse d'Orion" in targets and "★\ufe0e M31 Galaxie d'Andromède" in targets

    def test_custom_targets(self, planner_tab):
        w = planner_tab
        target = w._parse_custom("Mon objet; 0h 42m 44s; +41° 16′ 09″; galaxy; 30; 9,0")
        assert target == {"name": "Mon objet", "ra": pytest.approx(10.68333, abs=1e-4),
                          "dec": pytest.approx(41.26917, abs=1e-4), "type": "galaxy", "size": 30.0, "mag": 9.0}
        assert w._parse_custom("X; 10.5; -20")["ra"] == 10.5            # degrees without h
        with pytest.raises(ValueError, match="illisible"):
            w._parse_custom("X; abc; 10")
        import settings as prefs
        prefs.set("planner_custom", [target])
        w._compute_plan(force=True)
        assert "Mon objet" in self._column(w, "deep_sky", "col_target")

    def test_target_shown_on_the_sky_map(self, planner_tab, qapp):
        w = planner_tab
        w._show_plan_target_on_map(3)                                   # M31
        assert w.tabs.currentIndex() == 2 and w._sky_found == ("messier", 31)
        w._plan_catalog.setCurrentIndex(w._plan_catalog.findData("caldwell"))
        w._compute_plan()
        w.tabs.setCurrentWidget(w._planner_page)
        first = w._plan["deep_sky"][0]
        row = next(r for r in range(w._plan_tables["deep_sky"].rowCount())
                   if w._plan_tables["deep_sky"].item(r, 0).data(gui_name_role()) == first["label"])
        w._show_plan_target_on_map(row)
        assert w._sky_found == ("deep", first["label"]) or w._sky_found == ("messier", first.get("m"))
        assert w._find_entry.text().startswith(first["label"])

    def test_chart_follows_the_selection(self, planner_tab):
        w = planner_tab
        legend = lambda: [t.get_text() for t in w.fig_plan.axes[0].get_legend().get_texts()]   # noqa: E731
        assert legend()[1:] == ["M33", "M34", "M45", "M31", "M82"]       # the first five, the Moon first
        table = w._plan_tables["deep_sky"]
        table.clearSelection()
        table.selectRow(7)
        assert legend()[1:] == ["M39"]

    def test_exports(self, planner_tab, tmp_path, monkeypatch):
        import json
        import gui
        w = planner_tab
        for name, kind in (("plan.txt", "Texte (*.txt)"), ("plan.json", "JSON (*.json)"), ("plan.png", "PNG (*.png)")):
            monkeypatch.setattr(gui.QFileDialog, "getSaveFileName",
                                staticmethod(lambda *a, n=name, k=kind: (str(tmp_path / n), k)))
            w._export_plan()
        text = (tmp_path / "plan.txt").read_text(encoding="utf-8")
        assert text.startswith("Céleste — cibles de la nuit, Cherbourg-en-Cotentin")
        assert "Ciel profond (8)" in text and "M33 Galaxie du Triangle" in text and "91 %" in text
        data = json.loads((tmp_path / "plan.json").read_text(encoding="utf-8"))
        assert data["deep_sky"][0]["label"] == "M33" and data["place"] == "Cherbourg-en-Cotentin"
        assert (tmp_path / "plan.png").read_bytes()[:4] == b"\x89PNG"

    def test_polar_day(self, planner_tab):
        w = planner_tab
        w.entry_lat.setText("78,22")
        w.entry_lon.setText("15,65")
        w._set_datetime(datetime(2026, 6, 21, 22, 0))
        w.calculate()
        w._compute_plan()
        assert w._plan_summary.text().startswith("Pas de nuit")
        assert w._plan_tables["deep_sky"].rowCount() == 0 and not w._btn_plan_export.isEnabled()

    def test_survives_a_change_of_language(self, planner_tab, qapp):
        w = planner_tab
        w._lang_combo.setCurrentIndex(w._lang_combo.findData("en"))
        _pump(qapp)
        assert w._plan_summary.text().startswith("Astronomical night from 18:33 to 05:08.")
        assert w._plan_tabs.tabText(0) == "Deep sky (8)"


class TestObservingSite:
    def test_horizon_mask(self, window):
        import settings as prefs
        window._horizon_edit.setText("0 10, 90 25, 180 5, 270 15")
        window._save_horizon()
        assert prefs.get("horizon_points") == [[0.0, 10.0], [90.0, 25.0], [180.0, 5.0], [270.0, 15.0]]
        assert window._horizon_field.error.isHidden()
        assert len(window._sky_scene["horizon_mask"]) == 181                # drawn on the sky map
        window._horizon_edit.setText("0 10, 400 25")
        window._save_horizon()
        assert window._horizon_field.error.text().startswith("Paires")
        assert len(prefs.get("horizon_points")) == 4                       # unchanged

    def test_environment(self, window):
        import settings as prefs
        window._env_temp.setText("−5,5")
        window._env_pressure.setText("1 020")
        window._save_environment()
        assert prefs.get("env_temperature") == -5.5 and prefs.get("env_pressure") == 1020.0
        window._env_pressure.setText("5000")
        window._save_environment()
        assert window._env_pressure_field.error.text() == "Entre 0 et 1\u202f100"           # narrow space, as _num
        assert prefs.get("env_pressure") == 1020.0


def gui_name_role():
    import gui
    return gui._NAME_ROLE


# ──────────────────────────────────────────────────────────────────────
# Search by name on the sky map (v4.8)
# ──────────────────────────────────────────────────────────────────────

class TestSkySearch:
    @staticmethod
    def _find(window, text):
        window.tabs.setCurrentIndex(2)
        window._find_entry.setText(text)
        window._on_find_return()

    @staticmethod
    def _rings(window):
        """Gold circles drawn on the map: [(x, y, radius)]."""
        from matplotlib.colors import to_hex
        from matplotlib.patches import Circle
        from config import Config
        return [(c.center[0], c.center[1], c.radius) for c in window._sky_ax.patches
                if isinstance(c, Circle) and to_hex(c.get_edgecolor()) == Config.OR]

    @pytest.mark.parametrize("text, first", [
        ("vega", "Vega (α Lyr)"), ("VÉGA", "Vega (α Lyr)"), ("alpha cy", "Deneb (α Cyg)"),
        ("m 31", "M31 Galaxie d'Andromède"), ("Messier 31", "M31 Galaxie d'Andromède"),
        ("andro", "Andromède"), ("galaxie d'andro", "M31 Galaxie d'Andromède"), ("m3", "M3"), ("jup", "Jupiter"), ("cérès", "Cérès"),
        ("lune", "Lune"), ("cassio", "Cassiopée"), ("orion", "Orion"), ("epsilon car", "ε Car"),
    ])
    def test_names_found(self, window, text, first):
        assert window._find_targets(text)[0][0] == first

    def test_suggestions(self, window):
        assert [label for label, _ref in window._find_targets("ourse")] == ["Grande Ourse", "Petite Ourse"]
        assert window._find_targets("") == [] and window._find_targets("zzz") == []
        window._on_find_typed("m3")
        assert window._find_model.stringList()[:3] == ["M3", "M30", "M31 Galaxie d'Andromède"]
        assert len(window._find_model.stringList()) == 10
        window._find_completer.popup().hide()

    def test_star_is_circled(self, window):
        self._find(window, "véga")
        assert window._sky_found == ("star", "α Lyr") and window._find_entry.text() == "Vega (α Lyr)"
        assert window._chart_hints["sky"].text() == \
            "Vega (α Lyr) : hauteur 32,9°, direction NO (azimut 293,1°), cerclé d'or sur la carte."
        vega = next(s for s in window._sky_scene["stars"] if s["name"] == "Vega")
        (x, y, radius), = self._rings(window)
        assert (x, y) == (vega["x"], vega["y"]) and radius < 0.05

    def test_constellation_gets_a_wide_circle(self, window):
        self._find(window, "cassio")
        assert window._sky_found == ("figure", "Cas")
        (_x, _y, radius), = self._rings(window)
        assert radius > 0.1 and "Cassiopée : hauteur 82,4°" in window._chart_hints["sky"].text()

    def test_below_the_horizon(self, window):
        self._find(window, "sirius")
        assert window._chart_hints["sky"].text() == "Sirius (α CMa) est sous l'horizon (−18,8°)."
        assert self._rings(window) == []
        self._find(window, "jupiter")                            # a planet: with its rise
        assert window._chart_hints["sky"].text().startswith("Jupiter est sous l'horizon (−")
        assert window._chart_hints["sky"].text().endswith(" ; lever à 23:57.")

    def test_object_too_faint_to_be_drawn(self, window, qapp):
        """Ceres (magnitude 8.9) is not on the map at the limit 6: circled, and it answers the pointer."""
        assert "Ceres" not in [o.get("name") for o in window._sky_objects]
        self._find(window, "ceres")
        (x, y, _radius), = self._rings(window)
        ceres = next(o for o in window._sky_objects if o.get("name") == "Ceres")
        assert (ceres["x"], ceres["y"]) == (x, y) and ceres["kind"] == "planet"
        window._messier_box.setChecked(False)                    # the Messier objects hidden
        _pump(qapp, 3)
        self._find(window, "m31")
        assert window._sky_found == ("messier", 31) and len(self._rings(window)) == 1
        assert [o["m"] for o in window._sky_objects if o["kind"] == "deep_sky"] == [31]

    def test_follows_the_date_and_the_language(self, window, qapp):
        self._find(window, "lune")
        assert "Lune est sous l'horizon" in window._chart_hints["sky"].text()
        window._set_datetime(datetime(2026, 11, 2, 3, 0))        # the Moon has risen
        window.calculate()
        assert "Lune : hauteur" in window._chart_hints["sky"].text() and len(self._rings(window)) == 1
        window._lang_combo.setCurrentIndex(window._lang_combo.findData("en"))
        _pump(qapp)
        window.tabs.setCurrentIndex(2)
        _pump(qapp, 3)
        assert window._find_entry.text() == "Moon" and window._sky_found == ("moon",)
        assert window._chart_hints["sky"].text().startswith("Moon: altitude ")
        assert len(self._rings(window)) == 1

    def test_unknown_name_and_clearing(self, window):
        self._find(window, "véga")
        self._find(window, "zzz")
        assert window._chart_hints["sky"].text() == "Aucun astre nommé « zzz »."
        assert window._sky_found == ("star", "α Lyr")            # the last object found stays circled
        window._find_entry.setText("")
        assert window._sky_found is None and self._rings(window) == []
        assert window._chart_hints["sky"].text().startswith("Zénith au centre")


# ──────────────────────────────────────────────────────────────────────
# Jupiter's moons and Saturn's rings in their data windows (v4.8)
# ──────────────────────────────────────────────────────────────────────

class TestMoonsAndRings:
    @staticmethod
    def _texts(card):
        return [label.text() for label in card.findChildren(QLabel)]

    def test_jupiter_moons(self, window):
        """16 January 2026, 18:00 UT: Io crosses the disc with its shadow, the others are west."""
        window._set_datetime(datetime(2026, 1, 16, 18, 0))
        window.calculate()
        card = window._companions_card(window._body_object("Jupiter"))
        texts = self._texts(card)
        assert texts[0] == "Lunes galiléennes"
        assert texts[1:9] == ["I  Io", "devant Jupiter · son ombre sur Jupiter",
                              "II  Europe", "5,5 R à l'ouest · 2′ 08″",
                              "III  Ganymède", "12,5 R à l'ouest · 4′ 50″",
                              "IV  Callisto", "16,9 R à l'ouest · 6′ 33″"]
        assert "Nord en haut, est à gauche" in texts[9]
        points, scale = window._moons_drawing.positions()
        centre = window._moons_drawing.width() / 2
        assert abs(points["Io"][0] - centre) < scale                       # on the disc
        assert centre < points["Europa"][0] < points["Ganymede"][0] < points["Callisto"][0]   # west: right

    def test_hidden_moon_and_southern_sky(self, window):
        """16 February 2026, 16:00 UT: Io is behind Jupiter. From Sydney the view is upside down."""
        window._set_datetime(datetime(2026, 2, 16, 16, 0))
        window.entry_lat.setText("-33,8688")
        window.entry_lon.setText("151,2093")
        window.calculate()
        card = window._companions_card(window._body_object("Jupiter"))
        texts = self._texts(card)
        assert texts[2] == "derrière Jupiter" and "Sud en haut, ouest à gauche" in texts[9]
        drawing = window._moons_drawing
        points, _scale = drawing.positions()
        assert "Io" not in points and len(points) == 3
        centre = drawing.width() / 2
        for moon in drawing.moons[1:]:
            assert (points[moon["name"]][0] < centre) == (moon["x"] > 0)   # west: left
        drawing.grab()                                                     # it draws

    def test_saturn_rings(self, window):
        window._set_datetime(datetime(2026, 11, 5, 0, 0))
        window.calculate()
        card = window._companions_card(window._body_object("Saturn"))
        texts = self._texts(card)
        assert texts[:5] == ["Anneaux", "Inclinaison", "6,5° · face sud", "Taille apparente", "43,9″ × 5,0″"]
        assert abs(window._rings_drawing.tilt + 6.4771) < 0.01
        window._rings_drawing.grab()

    def test_rings_seen_from_their_unlit_side(self, window):
        """25 March 2025: the Earth has just crossed the ring plane, the Sun has not."""
        window._set_datetime(datetime(2025, 3, 25, 0, 0))
        window.calculate()
        texts = self._texts(window._companions_card(window._body_object("Saturn")))
        assert texts[2] == "0,1° · face sud, non éclairée"

    def test_in_the_data_window_of_these_two_planets_only(self, window, qapp):
        assert window._companions_card(window._body_object("Mars")) is None
        assert window._companions_card(window._body_object("sun")) is None
        assert window._companions_card(None) is None
        dlg = window._build_detail_dialog(window._body_object("Jupiter"))
        assert "Lunes galiléennes" in [label.text() for label in dlg.findChildren(QLabel)]
        dlg.close()
        _destroy(qapp, dlg)


# ──────────────────────────────────────────────────────────────────────
# History of the calculations (v4.8)
# ──────────────────────────────────────────────────────────────────────

class TestHistory:
    def test_a_calculation_enters_after_a_moment(self, window):
        """Not at once: the user may only be passing through this date."""
        import history
        assert window.history == [] and window._history_timer.isActive()
        assert window._history_timer.interval() == 3000
        window._commit_history()                                # what the timer does
        assert [window._history_label(e) for e in window.history] == \
            ["01/11/2026 21:30 TU · Cherbourg-en-Cotentin"]
        assert history.load() == window.history                 # written at once
        assert window.history[0]["tz"] == "UTC" and window.history[0]["elev"] == 0

    def test_only_the_date_the_user_stops_on(self, window):
        for day in (2, 3, 4):
            window._set_datetime(datetime(2026, 11, day, 21, 30))
            window.calculate()
        window._commit_history()
        assert [e["date"] for e in window.history] == ["2026-11-04T21:30:00"]

    def test_start_rebuild_and_real_time_stay_out(self, window, qapp):
        window._commit_history()
        assert len(window.history) == 1
        window._rebuild()                                        # new theme or language
        assert window._history_pending is None and not window._history_timer.isActive()
        window.btn_live.setChecked(True)                         # each tick calculates
        _pump(qapp, 3)
        assert window._history_pending is None
        window.btn_live.setChecked(False)
        import gui
        other = gui.AstroApp()                                   # the calculation of the start
        assert other._history_pending is None and len(other.history) == 1
        other.close()
        _destroy(qapp, other)

    def test_menu_brings_a_calculation_back(self, window, qapp):
        window._commit_history()
        window.tz_name = "Asia/Tokyo"
        window._select_zone("Asia/Tokyo")
        window._set_datetime(datetime(2027, 8, 2, 9, 0))
        window._apply_favorite(window.combo_fav.findText("Tokyo"))
        window._show_history_menu()                              # the calculation shown comes first
        actions = window._history_menu.actions()
        assert [a.text() for a in actions if not a.isSeparator()] == [
            "02/08/2027 09:00 TU · Tokyo", "01/11/2026 21:30 TU · Cherbourg-en-Cotentin",
            "Effacer l'historique"]
        window.btn_live.setChecked(True)                         # bringing one back leaves real time
        actions[1].trigger()
        assert not window.live_mode
        assert window.current_inputs() == (DTE, 49.6333, -1.6167)
        assert window.location_name == "Cherbourg-en-Cotentin" and window.tz_name == "UTC"
        assert window.tz_menu.currentData() == "UTC" and window.combo_fav.currentIndex() == -1
        assert window.card_sun_rise.value.text() == "06:55"      # and it is calculated
        assert [e["name"] for e in window.history] == ["Cherbourg-en-Cotentin", "Tokyo"]
        window._history_menu.close()
        window._restore_calculation(window.history[1])
        assert window.combo_fav.currentText() == "Tokyo" and window.tz_name == "Asia/Tokyo"
        assert window.entry_lat.text() == "35,6762"

    def test_unnamed_place_and_clear(self, window):
        window.entry_lat.setText("10,5")
        window.entry_lon.setText("-20,25")
        window._on_coords_edited("")
        window.calculate()
        window._commit_history()
        assert window._history_label(window.history[0]).endswith("TU · 10,5000° N, 20,2500° O")
        window._clear_history()
        import history
        assert window.history == [] and history.load() == []
        window._show_history_menu()
        only = window._history_menu.actions()
        assert [a.text() for a in only] == ["Aucun calcul pour l'instant"] and not only[0].isEnabled()
        window._history_menu.close()

    def test_a_calculation_made_just_before_closing_is_kept(self, window):
        import history
        assert history.load() == []
        window.close()
        assert [e["date"] for e in history.load()] == ["2026-11-01T21:30:00"]

    def test_button_and_shortcut(self, window):
        assert window.btn_history.text() == "Historique"
        assert "Ctrl+H" in window.btn_history.toolTip()
        assert window.btn_history.property("variant") == "discret"


# ──────────────────────────────────────────────────────────────────────
# Updates (Settings › About)
# ──────────────────────────────────────────────────────────────────────

class TestUpdates:
    RELEASE = {"version": "99.0", "tag": "v99.0", "notes": "What's new",
               "page": "https://github.com/astraeos-dev/Celeste_App/releases/tag/v99.0",
               "setup_url": "https://example.test/Celeste-99.0-Setup.exe",
               "setup_name": "Celeste-99.0-Setup.exe", "setup_size": 10, "sha256_url": "x"}

    @pytest.fixture
    def offline(self, monkeypatch):
        """Background tasks run at once; simulated Release."""
        import gui

        def run_now(func, on_done, on_error):
            try:
                result = func()
            except Exception as exc:  # noqa: BLE001
                on_error(exc)
            else:
                on_done(result)
        monkeypatch.setattr(gui, "_run_in_background", run_now)
        answer = {"release": dict(self.RELEASE)}
        monkeypatch.setattr(gui.updater, "latest_release", lambda: answer["release"])
        return answer

    def test_up_to_date(self, window, offline):
        from config import APP_VERSION
        offline["release"] = dict(self.RELEASE, version=APP_VERSION)
        window.check_updates()
        assert window._update_info.text() == f"Céleste {APP_VERSION} est à jour."

    def test_new_version_offers_the_update(self, window, offline, monkeypatch):
        import gui
        monkeypatch.setattr(gui.updater, "can_self_update", lambda: True)
        window.check_updates()
        box = window._update_dialog
        assert box.isVisible() and "Céleste 99.0 est disponible" in box.text()
        assert {b.text() for b in box.buttons()} >= {"Mettre à jour", "Voir la version",
                                                     "Ignorer cette version", "Plus tard"}
        box.close()

    def test_notes_in_plain_text(self, window, offline):
        """The note of the Release (CHANGELOG.md) shows without Markdown tags."""
        offline["release"] = dict(self.RELEASE, notes="- Meteor **showers**\n  in the `Events` tab")
        window.check_updates()
        box = window._update_dialog
        assert box.informativeText().startswith("• Meteor showers in the Events tab")
        box.close()

    def test_from_the_sources_git_pull(self, window, offline, monkeypatch):
        import gui
        monkeypatch.setattr(gui.updater, "can_self_update", lambda: False)
        window.check_updates()
        box = window._update_dialog
        assert "git pull" in box.informativeText()
        assert "Mettre à jour" not in {b.text() for b in box.buttons()}
        box.close()

    def test_skipped_version_is_not_offered_at_startup(self, window, offline):
        import settings as prefs
        window.check_updates()
        skip = next(b for b in window._update_dialog.buttons() if b.text() == "Ignorer cette version")
        skip.click()
        assert prefs.get("update_skipped") == "99.0"
        window._update_dialog = None
        window.check_updates(interactive=False)                  # at startup: silence
        assert window._update_dialog is None
        assert "99.0" in window._update_info.text()

    def test_error_is_reported(self, window, offline, monkeypatch):
        import gui

        def fail():
            raise gui.updater.UpdateError("no network")
        monkeypatch.setattr(gui.updater, "latest_release", fail)
        window.check_updates(interactive=False)
        assert "no network" in window._update_info.text()

    def test_failed_download_is_reported(self, window, offline, monkeypatch):
        """v4.7.1: closing the progress window emitted canceled, which hid the error."""
        import gui

        def fail(release, progress=None, cancelled=None):
            progress(1000, 10_000)
            raise gui.updater.UpdateError("api.github.com: HTTP Error 504: Gateway Timeout")
        monkeypatch.setattr(gui.updater, "download", fail)
        window._install_update(dict(self.RELEASE))
        box = window._update_failure
        assert box.isVisible() and "Mise à jour impossible" in box.text() and "504" in box.text()
        assert gui.updater.log_path() in box.informativeText()
        assert "Voir la version" in {b.text() for b in box.buttons()}
        assert not window._update_progress.isVisible()
        box.close()

    def test_cancelled_download_is_silent(self, window, offline, monkeypatch):
        import gui

        def cancel(release, progress=None, cancelled=None):
            window._update_progress.canceled.emit()            # what the Cancel button sends
            assert cancelled()
            raise gui.updater.UpdateCancelled("download interrupted")
        monkeypatch.setattr(gui.updater, "download", cancel)
        window._install_update(dict(self.RELEASE))
        assert getattr(window, "_update_failure", None) is None

    def test_downloaded_installer_is_launched(self, window, offline, monkeypatch):
        import gui
        launched, timers = [], []
        monkeypatch.setattr(gui.updater, "download", lambda release, **_kw: "/tmp/Celeste-99.0-Setup.exe")
        monkeypatch.setattr(gui.updater, "launch_installer", launched.append)
        monkeypatch.setattr(gui.QTimer, "singleShot", lambda *args: timers.append(args))
        window._install_update(dict(self.RELEASE))
        assert launched == ["/tmp/Celeste-99.0-Setup.exe"] and timers and timers[0][0] == 300
        assert getattr(window, "_update_failure", None) is None


def test_workshop_window(window, qapp, tmp_path, monkeypatch):
    """The Workshop opens for the place, previews each instrument and saves its PDF."""
    import gui
    dlg = window.show_workshop()
    qapp.processEvents()
    combos = dlg.findChildren(gui.QComboBox)
    kinds = next(c for c in combos if c.count() == 3)
    preview = dlg.findChild(gui.QLabel, "workshopPreview")
    assert not preview.pixmap().isNull()
    kinds.setCurrentIndex(2)                         # horizontal sundial
    qapp.processEvents()
    assert not preview.pixmap().isNull()
    target = tmp_path / "dial.pdf"
    monkeypatch.setattr(gui.QFileDialog, "getSaveFileName", lambda *a, **k: (str(target)[:-4], ""))
    save = next(b for b in dlg.findChildren(gui.QPushButton) if b.text() == gui.t("workshop.save"))
    save.click()
    assert target.read_bytes()[:5] == b"%PDF-"
    assert "dial.pdf" in window.statusBar().currentMessage()
    dlg.close()
    qapp.processEvents()


def test_workshop_refuses_the_tropics(window, qapp, monkeypatch):
    import gui
    shown = []
    monkeypatch.setattr(gui.QMessageBox, "information", lambda *a: shown.append(a[2]))
    window.entry_lat.setText("5")
    assert window.show_workshop() is None
    assert shown == [gui.t("workshop.latitude_range")]
