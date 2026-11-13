"""
tests/test_gui.py — Tests of the Qt interface (without a screen)
===================================================================
Builds the Céleste window off screen (QT_QPA_PLATFORM=offscreen) and drives
it: calculation, change of language and theme (Nuit, Jour, Observation)
without restarting, favourites, event search, tooltips and cards of the sky
map, real time; also checks two rules of the Astræos design (no emoji,
symbols followed by U+FE0E).

The preferences and favourites are written to a temporary folder: the
user's (~/.celeste) are never modified.
The tests are skipped when PySide6 and PyQt6 (or Qt's system libraries) are
missing.

Run with:  pytest tests/test_gui.py -v
"""

import io
import json
import math
import re
import os
import sys
from datetime import datetime, timedelta

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

pytest.importorskip("qt", reason="PySide6 (or PyQt6) or the Qt libraries are missing")
pytest.importorskip("matplotlib")

from engine import COMETS  # noqa: E402
from matplotlib.backend_bases import MouseEvent  # noqa: E402
from qt.QtCore import QDate, QDateTime, QEvent, Qt, QTime  # noqa: E402
from qt.QtWidgets import (  # noqa: E402
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
    monkeypatch.setattr(prefs, "USER_DIR", str(tmp_path))      # the journal, the forecast: nothing in ~/.celeste
    prefs.reset()
    prefs.set("default_tz", "UTC")      # times expected in UT; the automatic zone has its own tests
    favorites = tmp_path / "favorites.json"
    favorites.write_text(json.dumps({
        "Paris": {"lat": 48.8566, "lon": 2.3522},
        "Tokyo": {"lat": 35.6762, "lon": 139.6503},
    }), encoding="utf-8")
    monkeypatch.setattr(gui.common, "_FAVORITES_FILE", str(favorites))
    import satellites
    monkeypatch.setattr(satellites, "CACHE", str(tmp_path / "satellites.tle"))    # none on disk
    import history
    monkeypatch.setattr(history, "FILE", str(tmp_path / "history.json"))          # empty
    monkeypatch.setattr(gui.OsmMap, "fetch", False)                              # no map tiles from the network
    monkeypatch.setattr(gui.OsmMap, "CACHE", str(tmp_path / "tiles"))
    import mpc
    monkeypatch.setattr(mpc, "CACHE", str(tmp_path / "CometEls.txt"))             # none, and no download:
    prefs.set("planner_mpc", False)                                                # Céleste's comets only
    import neo
    import occultations

    def offline(*_args, **_kwargs):
        raise OSError("offline in the tests")
    monkeypatch.setattr(neo, "CACHE", str(tmp_path / "neo_approaches.json"))       # the asteroids: none on
    monkeypatch.setattr(neo, "EPHEMERIS_DIR", str(tmp_path / "neo"))               # disk, and no download
    monkeypatch.setattr(neo, "_get", offline)
    monkeypatch.setattr(occultations, "CACHE_DIR", str(tmp_path / "occultations"))
    monkeypatch.setattr(occultations, "_download", offline)
    import transients
    monkeypatch.setattr(transients, "CACHE", str(tmp_path / "transients.json"))   # the novae: none on disk
    monkeypatch.setattr(transients, "_get", offline)
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
        window.show_page(window._ephem_page)
        window.calculate()
        assert {"traj", "sky", "orrery"} <= window._dirty
        window.show_page(window._traj_page)
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
        assert window.tabs.tabText(0) == "Tonight"
        assert window.btn_calc.text() == "Calculate"
        assert window._edit_datetime() == DTE
        assert window.entry_lat.text() == "48.8566"
        assert prefs.get("lang") == "en"

    @pytest.mark.parametrize("lang, word", [("es", "Esta noche"), ("de", "Heute Nacht")])
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
        monkeypatch.setattr(gui.common, "QMessageBox", _yes_box(gui))
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

        monkeypatch.setattr(gui.common, "QInputDialog", Input)
        window.save_location()
        with open(gui.common._FAVORITES_FILE, encoding="utf-8") as f:
            assert json.load(f)["Maison"] == {"lat": 49.6333, "lon": -1.6167, "elev": 0}
        assert window.combo_fav.currentText() == "Maison"

        monkeypatch.setattr(gui.common, "QMessageBox", _yes_box(gui))
        window.delete_location()
        with open(gui.common._FAVORITES_FILE, encoding="utf-8") as f:
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
        from qt.QtWidgets import QPushButton
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
        window.show_page(window._sky_page)
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
        window.show_page(window._traj_page)
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

    def test_window_icon_at_taskbar_sizes(self, window):
        """The window carries Céleste's icon at every size the Windows taskbar takes."""
        import icons
        sizes = {(s.width(), s.height()) for s in window.windowIcon().availableSizes()}
        for size in (16, 24, 32, 40, 48):
            assert (size, size) in sizes
            assert not window.windowIcon().pixmap(size, size).isNull()
        assert set(icons.APP_ICON_SIZES) >= {16, 24, 32, 40, 48}

    def test_symbols_use_text_presentation(self, window):
        """Each body symbol is followed by U+FE0E (never shown as an emoji)."""
        name = window._planet_items["Venus"]["col_planet"].text()
        assert name.startswith("\u2640\ufe0e")

    def test_single_gold_area(self, window):
        """A single primary button (gold fill) in the window."""
        from qt.QtWidgets import QPushButton
        principal = [b for b in window.findChildren(QPushButton)
                     if b.property("variant") == "principal" and b.isVisibleTo(window)]
        assert principal == [window.btn_calc]

    def test_focused_field_shows_the_gold_ring(self, window, qapp):
        """v4.8: the box of a field with the keyboard focus is outlined in gold (the
        property was named "focus", Qt's own read-only one, and never changed)."""
        from qt.QtCore import Qt
        from qt.QtGui import QFocusEvent
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
        from qt import Signal
        from qt.QtCore import QObject

        class Source(QObject):
            positionUpdated = Signal(object)
            errorOccurred = Signal(int)

            def lastKnownPosition(self, *_args):
                from qt.QtCore import QDateTime
                from qt.QtPositioning import QGeoCoordinate, QGeoPositionInfo
                if last is None:
                    return QGeoPositionInfo()
                return QGeoPositionInfo(QGeoCoordinate(*last), QDateTime.currentDateTime())

            def requestUpdate(self, _timeout):
                if coord is None:
                    self.errorOccurred.emit(error)
                else:
                    from qt.QtCore import QDateTime
                    from qt.QtPositioning import QGeoCoordinate, QGeoPositionInfo
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
        window.show_page(next(p for p, n in window._chart_tabs.items() if n == "orrery"))
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
        window.show_page(window._ephem_page)
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
        monkeypatch.setattr(gui.common, "_run_in_background", run_now)
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
        window.show_page(next(p for p, n in window._chart_tabs.items() if n == "sky"))
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
        window.show_page(next(p for p, n in window._chart_tabs.items() if n == "sky"))
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
        monkeypatch.setattr(gui.common, "_nominatim_name", lambda lat, lon: "")
        assert gui._place_name(49.6333, -1.6167) == "Cherbourg"
        assert gui._place_name(48.0, -30.0) == ""


class TestGeolocation:
    def test_device_position_is_used(self, window, monkeypatch):
        """Cherbourg given by the device's service, named by OpenStreetMap."""
        import gui
        monkeypatch.setattr(gui.common, "QGeoPositionInfoSource", _FakeSource((49.6386, -1.6164)))
        monkeypatch.setattr(gui.common, "_place_name", lambda lat, lon, online=True: "Cherbourg-en-Cotentin")
        window.geolocate()
        assert window.entry_lat.text().replace(",", ".") == "49.6386"
        assert window.location_name == "Cherbourg-en-Cotentin"
        assert "±25 m" in window.statusBar().currentMessage()

    def test_the_point_sent_to_be_named(self, window, monkeypatch):
        """Asked for (the button): OpenStreetMap names the town from the point to the hundredth of a
        degree; at startup (a phone does it each time), the list on the computer names it, nothing is sent."""
        import gui
        monkeypatch.setattr(gui.common, "QGeoPositionInfoSource", _FakeSource((49.6386, -1.6164)))
        sent = []

        def answer(request, timeout):
            sent.append(request.full_url)
            return _FakeResponse(json.dumps({"address": {"city": "Cherbourg-en-Cotentin"}}).encode())
        monkeypatch.setattr(gui.common.urllib.request, "urlopen", answer)
        window.geolocate(interactive=True)
        assert len(sent) == 1 and "lat=49.64&lon=-1.62" in sent[0]
        assert window.location_name == "Cherbourg-en-Cotentin"
        window.geolocate(interactive=False)
        assert len(sent) == 1 and window.location_name == "Cherbourg"

    def test_ip_address_only_as_a_fallback(self, window, monkeypatch):
        """Silent service: position of the IP address, announced as approximate."""
        import gui
        monkeypatch.setattr(gui.common, "QGeoPositionInfoSource", _FakeSource(None))
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
        monkeypatch.setattr(gui.common, "QGeoPositionInfoSource", _FakeSource(None, error=0))
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

    def test_access_denied_offers_the_map(self, window, monkeypatch):
        """Access that cannot be allowed (setting greyed out): the window offers the map,
        and the place picked there is used."""
        import gui
        monkeypatch.setattr(gui.common, "QGeoPositionInfoSource", _FakeSource(None, error=0))
        self._ip_answer(monkeypatch)
        picked = []
        monkeypatch.setattr(window, "choose_on_map", lambda: picked.append(True))
        window.geolocate()
        box = window._geo_dialog
        button = next(b for b in box.buttons() if b.text() == "Choisir sur la carte")
        button.click()
        QApplication.processEvents()
        assert picked

    def test_no_answer_at_all_offers_the_map(self, window, monkeypatch):
        import gui
        monkeypatch.setattr(gui.common, "QGeoPositionInfoSource", _FakeSource(None, error=0))

        def offline(*a, **k):
            raise OSError("offline")
        monkeypatch.setattr(gui.urllib.request, "urlopen", offline)
        window.geolocate()
        box = window._geo_dialog
        assert box.isVisible() and box.text() == gui.t("errors.geoloc_no_answer")
        assert any(b.text() == "Choisir sur la carte" for b in box.buttons())

    def test_ip_services_in_turn(self, monkeypatch):
        """The first HTTPS service fails, the second answers in its own format."""
        import gui
        asked = []

        def urlopen(req, timeout=0):
            asked.append(req.full_url)
            if "ipwho.is" in req.full_url:
                raise OSError("blocked")
            return _FakeResponse(json.dumps({"latitude": 45.76, "longitude": 4.84, "city": "Lyon",
                                             "country_name": "France", "timezone": "Europe/Paris"}).encode())
        monkeypatch.setattr(gui.urllib.request, "urlopen", urlopen)
        assert gui._ip_location() == (45.76, 4.84, "Lyon", "France", "Europe/Paris")
        assert len(asked) == 2 and asked[0].startswith("https://")

    def test_place_picked_on_the_map(self, window, monkeypatch):
        """The map: a city found by its name, then a click elsewhere; the place is used with
        its time zone and the elevation of the nearest city."""
        import gui
        picker = gui.PlacePicker(window, 49.63, -1.62)
        picker.resize(800, 600)
        picker.show()
        picker.search.setText("Brest, FR")
        picker._find()
        assert picker.chosen == pytest.approx((48.39, -4.49), abs=0.05) and picker.name == "Brest"
        assert picker.use.isEnabled() and picker.map.zoom == 13
        m = picker.map                                           # a click on the map: the point under it
        lat, lon = m.to_latlon(m.width() / 2 + 40, m.height() / 2 - 25)
        x, y = m.to_screen(lat, lon)
        assert (x, y) == pytest.approx((m.width() / 2 + 40, m.height() / 2 - 25), abs=1e-6)
        m.on_pick(lat, lon)
        assert picker.chosen == (lat, lon)
        before = m.to_latlon(100, 100)                           # the wheel keeps the point under the pointer
        m.zoom_by(1, (100, 100))
        assert m.to_latlon(100, 100) == pytest.approx(before, abs=1e-6)
        picker.grab()                                            # offline: Céleste's coastlines and cities
        picker.close()

        class Fake:
            def __init__(self, parent, lat, lon):
                self.chosen, self.name = (43.2965, 5.3698), "Marseille"

            def exec(self):
                return gui.QDialog.DialogCode.Accepted
        monkeypatch.setattr(gui.common, "PlacePicker", Fake)
        window.choose_on_map()
        assert window.location_name == "Marseille"
        assert window.entry_lat.text().startswith("43,2965")

    def test_last_known_position_before_the_ip_address(self, window, monkeypatch):
        """Timeout: the device's last known position rather than the IP address."""
        import gui
        monkeypatch.setattr(gui.common, "QGeoPositionInfoSource",
                            _FakeSource(None, error=4, last=(49.6386, -1.6164)))
        monkeypatch.setattr(gui.common, "_place_name", lambda lat, lon, online=True: "Cherbourg-en-Cotentin")
        monkeypatch.setattr(gui.urllib.request, "urlopen", lambda *a, **k: pytest.fail("adresse IP"))
        window.geolocate()
        assert window.location_name == "Cherbourg-en-Cotentin"

    def test_no_window_at_startup(self, window, monkeypatch):
        """At startup (automatic geolocation), the status bar only."""
        import gui
        monkeypatch.setattr(gui.common, "QGeoPositionInfoSource", _FakeSource(None, error=4))
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
        window.show_page(window._coord_page)

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
        monkeypatch.setattr(gui.common, "_FAVORITES_FILE", str(tmp_path / "user" / "favorites.json"))
        monkeypatch.setattr(gui.common, "_LEGACY_FAVORITES_FILE", str(tmp_path / "absent.json"))
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
        monkeypatch.setattr(gui.common, "_FAVORITES_FILE", str(tmp_path / "user" / "favorites.json"))
        monkeypatch.setattr(gui.common, "_LEGACY_FAVORITES_FILE", str(tmp_path / "legacy.json"))
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
        from qt.QtWidgets import QPushButton
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
        window.show_page(window._coord_page)
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
        assert names == ["Ce soir", "Ciel", "Astres", "Calendrier", "Observer", ""]
        assert window.tabs.tabToolTip(5) == "Paramètres" and not window.tabs.tabIcon(5).isNull()
        bodies = window.tabs.widget(2)
        assert [bodies.tabText(i) for i in range(bodies.count())] == ["Planètes", "Système solaire", "Coordonnées",
                                                                       "Géocroiseurs"]
        observe = window.tabs.widget(4)
        assert [observe.tabText(i) for i in range(observe.count())] == ["Cibles", "Occultations", "Journal"]
        page = window._orrery_page
        assert bodies.indexOf(page) == 1 and page.isAncestorOf(window.canvas_orrery)
        assert not window._planets_page.isAncestorOf(window.canvas_orrery)
        assert window._planets_page.isAncestorOf(window.planet_table)
        window.show_page(page)
        _pump(qapp, 3)
        assert window.tabs.currentIndex() == 2 and window.current_page() is page
        assert "orrery" not in window._dirty                     # drawn when its tab shows
        assert window.fig_orrery.axes

    def test_the_page_survives_a_rebuild(self, window, qapp):
        """A new language rebuilds the window on the same page of the same space."""
        window.show_page(window._coord_page)
        window._lang_combo.setCurrentIndex(window._lang_combo.findData("en"))
        _pump(qapp)
        assert window.current_page() is window._coord_page and window.tabs.tabText(2) == "Bodies"

    def test_animation_stops_when_the_tab_is_left(self, window, qapp):
        window.show_page(window._orrery_page)
        window._toggle_orrery()
        assert window._orrery_timer.isActive()
        window.show_page(window._planets_page)
        _pump(qapp, 3)
        assert not window._orrery_timer.isActive()

    def test_every_body_fits_in_the_planets_tab(self, window, qapp):
        """With the map gone, the table shows the 7 planets, 9 minor planets and the comets at once."""
        window.show_page(window._planets_page)
        window._planet_selector.buttons["all"].click()
        _pump(qapp, 3)
        table = window.planet_table
        assert table.maximumHeight() >= 40 * (16 + len(COMETS))
        assert table.height() >= 40 * 12                         # 820 px window: most of them, the rest scrolls
        window._planet_selector.buttons["planets"].click()

    @pytest.mark.parametrize("lang", ["fr", "en", "es", "de"])
    def test_the_spaces_fit_at_the_minimum_width(self, window, qapp, lang):
        window._lang_combo.setCurrentIndex(window._lang_combo.findData(lang))
        _pump(qapp)
        window.resize(window.minimumWidth(), window.minimumHeight())
        _pump(qapp, 3)
        assert window.tabs.count() == 6
        assert window.tabs.tabBar().sizeHint().width() <= window.tabs.width()
        for space in window._space_tabs:
            assert space.tabBar().sizeHint().width() <= window.tabs.width()

    def test_a_short_title_when_the_row_is_full(self, window, qapp):
        """On a phone, the Sky's four pages: the Novae page under its short title, the full one in its
        tooltip; back to the full title on a computer's window."""
        space = next(s for s in window._space_tabs if s.indexOf(window._transients_page) >= 0)
        index = space.indexOf(window._transients_page)
        window.resize(window.minimumWidth(), window.minimumHeight())
        _pump(qapp, 3)
        assert space.tabText(index) == "Novae" and space.tabToolTip(index) == "Novae et supernovae"
        window.resize(1350, 820)
        _pump(qapp, 3)
        assert space.tabText(index) == "Novae et supernovae" and space.tabToolTip(index) == ""


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
    monkeypatch.setattr(gui.common, "_run_in_background", run_now)
    window.show_page(window._planner_page)              # computes the night
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
        assert w._plan_summary.text().splitlines()[0] == ("Nuit astronomique de 18:33 à 05:08. "
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
        planner_tab.show_page(planner_tab._ephem_page)
        planner_tab.show_page(planner_tab._planner_page)

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
        assert set(actions) == {"Voir sur la carte du ciel", "Noter une observation", "Ajouter à « à faire »",
                                "Marquer comme déjà fait"}
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
        assert w.current_page() is w._sky_page and w._sky_found == ("messier", 31)
        w._plan_catalog.setCurrentIndex(w._plan_catalog.findData("caldwell"))
        w._compute_plan()
        w.show_page(w._planner_page)
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

    def test_map_of_the_night(self, planner_tab, qapp, monkeypatch):
        """The Sky map view: the paths of the chosen targets, the slider through the night,
        and the tooltip of a point (after uptonight's sky plots)."""
        import gui
        w = planner_tab
        w._plan_view_buttons["map"].setChecked(True)
        qapp.processEvents()
        assert w._plan_slider.isVisible() and w._plan_slider.maximum() == len(w._plan["times"]) - 1
        assert w._plan_points
        names = {p[0] for p in w._plan_points}
        assert "M33" in names
        w._plan_slider.setValue(w._plan_slider.maximum() // 2)
        assert w._plan_time.text() == w._plan_times()[w._plan_slider.maximum() // 2]
        shown = []
        monkeypatch.setattr(gui.QToolTip, "showText", lambda pos, text, *a: shown.append(text))
        label, x, y, i = next(p for p in w._plan_points if p[0] == "M33")

        class Event:
            xdata, ydata = x, y
        w._on_plan_hover(Event())
        assert shown and shown[0].startswith(f"M33 — {w._plan_times()[i]} · hauteur")
        w._plan_view_buttons["altitude"].setChecked(True)
        assert not w._plan_slider.isVisible()

    def test_large_map_of_the_night(self, planner_tab, qapp, tmp_path, monkeypatch):
        """The large map, as uptonight in Céleste's colours: every target numbered as in the
        table, the planets, the header of the night; the legend shows and hides a target;
        the east on either side; the image."""
        import gui
        from config import Config
        w = planner_tab
        dlg = w.show_night_sky()
        qapp.processEvents()
        ns = dlg.night_sky
        data = ns["data"]
        deep = [tr for tr in data["tracks"] if tr["kind"] == "deep_sky"]
        assert [tr["number"] for tr in deep] == list(range(1, len(deep) + 1))
        assert deep[0]["legend"].startswith("1 : M33 Galaxie du Triangle (Galaxie")
        assert deep[0]["shape"] == "circle" and deep[0]["color"] == Config.OR        # the theme's colours
        bodies = [tr for tr in data["tracks"] if tr["kind"] == "body"]
        assert bodies and all(tr["shape"] == "big" and tr["color"] == Config.ENCRE for tr in bodies)
        assert data["info"][1].startswith("Coucher / lever du Soleil : ")
        assert ns["state"]["points"]
        def on_the_first_row():                    # the legend is drawn again at each change
            legend, rows, _step = ns["figure"].night_legend

            class Event:
                inaxes, ydata, xdata = legend, rows[0][0], 0.5
            return Event()
        first = ns["figure"].night_legend[1][0][1]
        ns["clicked"](on_the_first_row())
        assert data["tracks"][first]["on"] is False
        assert all(p[0] != data["tracks"][first]["name"] for p in ns["state"]["points"])
        ns["clicked"](on_the_first_row())
        assert data["tracks"][first]["on"] is True
        ns["moved"](on_the_first_row())
        assert ns["state"]["highlight"] == first
        ns["show"](False)
        assert not ns["state"]["points"]
        ns["show"](True)
        ns["east"].setChecked(True)
        assert gui.prefs.get("plan_map_east_right") is True
        monkeypatch.setattr(gui.QFileDialog, "getSaveFileName", staticmethod(lambda *a: (str(tmp_path / "nuit"), "")))
        ns["save"]()
        assert (tmp_path / "nuit.png").read_bytes()[:4] == b"\x89PNG"
        dlg.close()
        gui.prefs.set("plan_map_east_right", False)

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
        window.show_page(window._sky_page)
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
        window.show_page(window._sky_page)
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

    def test_moons_of_the_other_planets(self, window, qapp):
        """Mars, Saturn (after its rings), Uranus, Neptune and Pluto show their moons too (4.12)."""
        import gui
        window._set_datetime(datetime(2026, 11, 12, 21, 0))
        window.calculate()
        texts = self._texts(window._companions_card(window._body_object("Mars")))
        assert texts[0] == "Lunes" and "Phobos" in texts and "Déimos" in texts
        card = window._companions_card(window._body_object("Saturn"))
        texts = self._texts(card)
        assert texts.index("Lunes") > texts.index("Taille apparente") and "Titan" in texts and "Japet" in texts
        assert "devant Saturne" in " ".join(texts)                     # Mimas in front of the globe
        card.findChild(gui.PlanetMoons).grab()                         # it draws

    def test_in_the_data_window_of_planets_only(self, window, qapp):
        assert window._companions_card(window._body_object("Venus")) is None
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
        monkeypatch.setattr(gui.common, "_run_in_background", run_now)
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
    """The Workshop opens for the side panel's place, previews each instrument, takes its
    own place and date, and saves the PDF."""
    import gui
    dlg = window.show_workshop()
    qapp.processEvents()
    f = dlg.workshop_fields
    assert f["kinds"].count() == 5
    assert not f["preview"].pixmap().isNull()
    f["kinds"].setCurrentIndex(f["kinds"].findData("horizontal_dial"))
    qapp.processEvents()
    assert not f["preview"].pixmap().isNull()
    # another place, typed in the window: the side panel does not change
    f["place"].setText("Sydney")
    f["place"].textEdited.emit("Sydney")
    f["place"].returnPressed.emit()
    qapp.processEvents()
    assert gui._parse_coord(f["lat"].text(), 90.0) < -30
    assert window.entry_lat.text().startswith("49")
    target = tmp_path / "dial.pdf"
    monkeypatch.setattr(gui.QFileDialog, "getSaveFileName", lambda *a, **k: (str(target)[:-4], ""))
    f["save"].click()
    assert target.read_bytes()[:5] == b"%PDF-"
    assert "dial.pdf" in window.statusBar().currentMessage()
    dlg.close()
    qapp.processEvents()


def test_workshop_astrolabe_options(window, qapp):
    dlg = window.show_workshop()
    f = dlg.workshop_fields
    f["kinds"].setCurrentIndex(f["kinds"].findData("astrolabe"))
    qapp.processEvents()
    assert f["size"].isVisibleTo(dlg)
    f["size"].setCurrentIndex(0)
    qapp.processEvents()
    assert not f["preview"].pixmap().isNull()
    f["kinds"].setCurrentIndex(f["kinds"].findData("nocturnal"))
    qapp.processEvents()
    assert not f["size"].isVisibleTo(dlg)
    dlg.close()
    qapp.processEvents()


def test_workshop_refuses_the_tropics(window, qapp):
    """Below 10° of latitude the window says why and cannot save."""
    dlg = window.show_workshop()
    f = dlg.workshop_fields
    f["lat"].setText("5")
    f["lat"].textEdited.emit("5")
    f["timer"].timeout.emit()
    qapp.processEvents()
    assert not f["save"].isEnabled()
    import gui
    assert f["problem"].text() == gui.t("workshop.latitude_range")
    dlg.close()
    qapp.processEvents()


def test_astronomical_calendar(window, qapp, tmp_path, monkeypatch):
    """The calendar of the Events tab: a year of events in a month grid, a day's details,
    the filters, and the .ics export of what they let through."""
    import gui
    from datetime import date
    monkeypatch.setattr(gui.common, "_run_in_background", lambda func, done, err: done(func()))
    window.show_calendar()
    qapp.processEvents()
    cal = window._cal_state
    assert cal["items"] and len(cal["items"]) > 150
    window._cal_choose(date(2026, 11, 24))
    widgets = window._cal_widgets
    assert widgets["day_title"].text().startswith("24/11/2026")
    assert any("Pleine lune" in c.lines.text() for c in widgets["cells"])
    n_all = len(window._ics_items)
    widgets["boxes"]["moon"].setChecked(False)
    assert 0 < len(window._ics_items) < n_all
    target = tmp_path / "ciel.ics"
    monkeypatch.setattr(gui.QFileDialog, "getSaveFileName", lambda *a, **k: (str(target), ""))
    window._export_ics()
    text = target.read_text(encoding="utf-8")
    assert text.count("BEGIN:VEVENT") == len(window._ics_items) and "Pleine lune" in text
    widgets["boxes"]["moon"].setChecked(True)
    # v4.18: the minima of Algol seen from the place, under their own filter
    assert widgets["boxes"]["variables"].text() == "Étoiles variables"
    assert any(i["category"] == "variables" for i in cal["items"])
    window._cal_choose(date(2026, 11, 10))                       # 00:12 UT, Algol near the zenith
    assert any("Minimum d'Algol" in c.lines.text() for c in window._cal_widgets["cells"])


def test_month_sheet(window, qapp, tmp_path, monkeypatch):
    """v4.19: the month's sheet to print: the calculation's month by default, the PDF written
    in the colours of the Jour theme, the window's theme kept."""
    import gui
    import month_sheet
    from config import Config
    monkeypatch.setattr(gui.common, "_run_in_background", lambda func, done, err: done(func()))
    dlg = window._month_sheet_dialog()
    assert (dlg.month.date().year(), dlg.month.date().month()) == (2026, 11)
    target = tmp_path / "ciel.pdf"
    monkeypatch.setattr(gui.QFileDialog, "getSaveFileName", lambda *a, **k: (str(target), ""))
    seen, real_save = {}, month_sheet.save

    def spy(path, sheet, texts):
        seen["theme"], seen["texts"] = Config.THEME, texts
        real_save(path, sheet, texts)

    monkeypatch.setattr(month_sheet, "save", spy)
    dlg.save()
    assert target.read_bytes().startswith(b"%PDF")
    assert seen["theme"] == "jour" and Config.THEME == "nuit"
    texts = seen["texts"]
    assert texts["title"] == "Novembre 2026" and len(texts["phases"]) == 4
    assert any(title == "Minimum d'Algol" for _when, title in texts["events"])
    assert "vers" in texts["map_caption"] and "Fiche enregistrée" in window.statusBar().currentMessage()
    window._sheet_btn.click()                                        # the button of the Tonight card
    assert window._month_sheet_dlg.isVisible()
    window._month_sheet_dlg.reject()


def test_algol_minimum_tonight(window, qapp):
    """v4.18: Tonight names the minimum of Algol of the night when it can be watched."""
    window._set_datetime(datetime(2026, 11, 9, 21, 0))
    window.calculate()
    algol = [text for text, _tone in window._tonight_lines() if "Algol" in text]
    assert len(algol) == 1 and "00:1" in algol[0] and "±30 min" in algol[0]
    window._set_datetime(datetime(2026, 11, 8, 21, 0))                 # no minimum that night
    window.calculate()
    assert not any("Algol" in text for text, _tone in window._tonight_lines())


# ──────────────────────────────────────────────────────────────────────
# Compact layout: a phone, or a narrow window (v4.15, docs/ANDROID.md)
# ──────────────────────────────────────────────────────────────────────

class TestCompactLayout:
    from qt.QtWidgets import QTabWidget

    @staticmethod
    def _phone(window, qapp, width=360, height=740):
        window.resize(width, height)
        _pump(qapp, 5)

    def test_wide_by_default(self, window, qapp):
        assert not window.is_compact()
        assert window._sidebar_scroll.isVisible() and window._main.isVisible()
        assert window.tabs.tabPosition() == self.QTabWidget.TabPosition.North
        assert not window._top_summary.parentWidget().isVisible()

    def test_phone_width(self, window, qapp):
        self._phone(window, qapp)
        assert window.is_compact()
        assert window.width() == 360
        assert not window._sidebar_scroll.isVisible() and window._main.isVisible()
        assert window.tabs.tabPosition() == self.QTabWidget.TabPosition.South
        assert window._top_summary.parentWidget().isVisible()
        assert "Cherbourg" in window._top_summary.text()
        assert not window.statusBar().isVisible()

    def test_the_spaces_fit_the_bottom_bar(self, window, qapp):
        self._phone(window, qapp)
        bar = window.tabs.tabBar()
        right = max(bar.tabRect(i).right() for i in range(bar.count()))
        assert right <= window.tabs.width()
        assert all(bar.tabRect(i).height() >= 44 for i in range(bar.count()))     # touch targets

    def test_sky_map_toolbar_in_rows(self, window, qapp):
        """The map's tools stacked at a phone's width, nothing over another; the time bar under the map."""
        self._phone(window, qapp)
        window.show_page(window._sky_page)
        _pump(qapp, 5)
        boxes = [w.geometry().translated(w.parentWidget().mapTo(window, w.pos()) - w.pos())
                 for w in (window._mag_slider, window._messier_box, window._find_entry)]
        assert boxes[0].bottom() < boxes[1].top() and boxes[1].bottom() < boxes[2].top()
        assert window._find_entry.width() > 300 and window._mag_slider.width() > 150
        slider = window._sky_time_slider
        assert slider.mapTo(window, slider.rect().topLeft()).y() > window.canvas_sky.mapTo(window, window.canvas_sky.rect().bottomLeft()).y()
        self._phone(window, qapp, 1350, 820)
        assert window._find_entry.width() == 220 and window._mag_slider.width() == 240

    def test_the_window_fits_the_phone_in_every_language(self, window, qapp):
        """The 5.0 alpha ran off the phone's screen: the sizes kept from the wide layout,
        and rows too wide in German (the longest labels)."""
        for lang in ("fr", "de"):
            window._lang_combo.setCurrentIndex(window._lang_combo.findData(lang))
            _pump(qapp)
            for width in (360, 411, 360):
                self._phone(window, qapp, width)
                assert window.minimumSizeHint().width() <= width, (lang, width)
        window._lang_combo.setCurrentIndex(window._lang_combo.findData("fr"))
        _pump(qapp)

    def test_calendar_buttons_in_two_columns(self, window, qapp):
        """The Calendar space's buttons: two columns of short labels on a phone, nothing clipped."""
        self._phone(window, qapp)
        buttons = window._evt_bar_buttons
        assert all("(" not in b.text() for b in buttons)
        assert len({window._evt_bar.getItemPosition(window._evt_bar.indexOf(b))[1] for b in buttons}) == 2
        self._phone(window, qapp, 1350, 820)
        assert buttons[1].text() == "Éclipses (12 mois)" and buttons[-1].text() == "Exporter (.ics)"

    def test_drawer(self, window, qapp):
        self._phone(window, qapp)
        window._drawer_btn.click()
        _pump(qapp, 3)
        assert window._sidebar_scroll.isVisible() and not window._main.isVisible()
        assert window._sidebar_scroll.width() > 312                               # the whole width
        window.btn_calc.click()
        _pump(qapp, 3)
        assert not window._sidebar_scroll.isVisible() and window._main.isVisible()

    def test_cards_one_under_another(self, window, qapp):
        self._phone(window, qapp)
        assert window.card_sun_alt.y() < window.card_sun_rise.y()
        window.resize(1400, 880)
        _pump(qapp, 5)
        assert not window.is_compact()
        assert window.card_sun_alt.y() == window.card_sun_rise.y()
        assert window._sidebar_scroll.isVisible()

    def test_targets_constraints_on_their_own_page(self, window, qapp):
        self._phone(window, qapp)
        window.show_page(window._planner_page)
        _pump(qapp, 3)
        assert not window._plan_side.isVisible() and window._plan_right.isVisible()
        window._btn_plan_side.click()
        assert window._plan_side.isVisible() and not window._plan_right.isVisible()
        window._show_plan_side(False)
        assert not window._plan_side.isVisible()

    def test_survives_a_rebuild(self, window, qapp):
        self._phone(window, qapp)
        window._lang_combo.setCurrentIndex(window._lang_combo.findData("en"))
        _pump(qapp, 5)
        assert window.is_compact()
        assert window.tabs.tabPosition() == self.QTabWidget.TabPosition.South


class TestSkyMapZoom:
    @staticmethod
    def _sky(window, qapp):
        window.show_page(window._sky_page)
        _pump(qapp, 3)
        window.canvas_sky.draw()
        return window._sky_ax

    def test_whole_sky_by_default(self, window, qapp):
        ax = self._sky(window, qapp)
        assert ax.get_xlim() == pytest.approx((-1.17, 1.17))
        assert window._sky_zoom_lbl.text() == ""

    def test_zoom_keeps_the_point_under_the_pointer(self, window, qapp):
        ax = self._sky(window, qapp)
        window._sky_zoom_by(2.0, (0.5, 0.2))
        x0, x1 = ax.get_xlim()
        assert x1 - x0 == pytest.approx(1.17)
        # the point (0.5, 0.2) stays at the same fraction of the view
        assert (0.5 - x0) / (x1 - x0) == pytest.approx((0.5 + 1.17) / 2.34)
        assert window._sky_zoom_lbl.text() == "×2,0"

    def test_kept_when_the_map_is_redrawn(self, window, qapp):
        ax = self._sky(window, qapp)
        window._sky_zoom_by(3.0, (0.0, 0.5))
        window.calculate()
        window._dirty.add("sky")
        window._draw_visible_chart()
        x0, x1 = window._sky_ax.get_xlim()
        assert x1 - x0 == pytest.approx(2.34 / 3.0)
        window._sky_reset_view()
        assert window._sky_ax.get_xlim() == pytest.approx((-1.17, 1.17))

    def test_limits(self, window, qapp):
        self._sky(window, qapp)
        window._sky_zoom_by(0.5)
        assert window._sky_zoom == 1.0
        window._sky_zoom_by(1000.0, (5.0, 5.0))
        assert window._sky_zoom == 12.0
        cx, cy = window._sky_center
        assert cx <= 1.17 and cy <= 1.17                       # the map's edge stays in view

    def test_drag_moves_a_zoomed_map(self, window, qapp):
        from matplotlib.backend_bases import MouseEvent
        ax = self._sky(window, qapp)
        window._sky_zoom_by(4.0)
        x, y = ax.transData.transform((0.0, 0.0))
        window._on_sky_press(MouseEvent("button_press_event", window.canvas_sky, x, y, button=1))
        window._on_sky_hover(MouseEvent("motion_notify_event", window.canvas_sky, x + 60, y, button=1))
        window._on_sky_release(MouseEvent("button_release_event", window.canvas_sky, x + 60, y, button=1))
        assert window._sky_center[0] < 0                     # dragged right: the view moved left
        assert window._sky_drag is None


class _FakeAim:
    """A phone's rotation sensor (ui/phone.PhoneAim) held by the test: *angles* are Qt's x, y, z."""

    def __init__(self):
        self.angles, self.running = None, False

    def available(self):
        return True

    def start(self):
        self.running = True

    def stop(self):
        self.running = False

    def active(self):
        return self.running

    def reading(self):
        return self.angles


def _held(alt, az):
    """Qt's angles of a phone held upright then tilted, its back at (*alt*, magnetic *az*), not tilted sideways."""
    return 90.0 + alt, 0.0, -az


class TestFollowThePhone:
    """Ciel › Carte du ciel: the map turned and moved by the phone's rotation sensor (v4.22)."""

    @staticmethod
    def _sky(window, qapp):
        window._phone_aim = _FakeAim()
        window.show_page(window._sky_page)
        _pump(qapp, 3)
        window.canvas_sky.draw()
        return window._sky_ax

    @staticmethod
    def _aim_at(window, alt, az):
        window._phone_aim.angles = _held(alt, az)
        for _ in range(40):                              # four seconds held still: the map settles
            window._sky_follow_tick()

    def test_no_sensor_on_a_desktop(self, window):
        assert window._sky_follow_btn.isHidden()
        window._set_sky_follow(True)
        assert not window._sky_follow and not window._sky_follow_btn.isChecked()

    def test_the_map_turns_to_the_sky_behind_the_phone(self, window, qapp):
        import charts
        ax = self._sky(window, qapp)
        window._sky_follow_btn.setChecked(True)          # the button
        assert window._sky_follow and window._phone_aim.running and window._sky_zoom == 2.5
        assert "déclinaison magnétique" in window.statusBar().currentMessage()
        decl = window._sky_declination
        assert -1.0 < decl < 3.0                          # Cherbourg: about 1° east
        self._aim_at(window, 30, 120)                     # 30° up, toward the south-east (magnetic)
        alt, az, turn = window._sky_aim
        assert alt == pytest.approx(30, abs=0.01) and az == pytest.approx(120 + decl, abs=0.01)
        assert turn == pytest.approx(60 - decl, abs=0.01) and window._sky_turn == turn
        # the view centred where the phone looks, that point straight below the zenith on the screen
        cx, cy = charts.turned_xy(*charts.sky_xy(alt, az), turn)
        assert cx == pytest.approx(0, abs=1e-6) and cy == pytest.approx(-60 / 90, abs=1e-6)
        assert np.mean(ax.get_xlim()) == pytest.approx(cx) and np.mean(ax.get_ylim()) == pytest.approx(cy)
        ring = window._sky_reticle
        assert ring.get_visible() and (ring.get_xdata()[0], ring.get_ydata()[0]) == pytest.approx(
            charts.sky_xy(alt, az))
        # a star there is drawn at its turned place, and a tap on it opens its card
        shown = []
        window._show_object_detail = shown.append
        star = min(window._sky_scene["stars"], key=lambda s: math.hypot(s["x"] - charts.sky_xy(alt, az)[0],
                                                                         s["y"] - charts.sky_xy(alt, az)[1]))
        x, y = ax.transData.transform(charts.turned_xy(star["x"], star["y"], turn))
        window._on_sky_press(MouseEvent("button_press_event", window.canvas_sky, x, y, button=1))
        window._on_sky_release(MouseEvent("button_release_event", window.canvas_sky, x, y, button=1))
        assert shown and shown[0]["name"] == star["name"]

    def test_small_moves_do_not_redraw(self, window, qapp):
        self._sky(window, qapp)
        window._set_sky_follow(True)
        self._aim_at(window, 45, 200)
        before = window._sky_aim
        assert before[0] == pytest.approx(45, abs=0.02)   # settled where the phone points
        drawn = []
        window._show_sky_aim = lambda *aim: drawn.append(aim)
        window._phone_aim.angles = _held(45.1, 200.1)    # a hand's tremor, and back
        window._sky_follow_tick()
        window._phone_aim.angles = _held(45, 200)
        for _ in range(20):
            window._sky_follow_tick()
        assert drawn == []
        del window._show_sky_aim
        self._aim_at(window, 50, 210)                    # moved: the map follows, then settles
        assert window._sky_aim[0] == pytest.approx(50, abs=0.02)

    def test_back_to_north_up(self, window, qapp):
        import charts
        ax = self._sky(window, qapp)
        window._set_sky_follow(True)
        self._aim_at(window, 40, 0)                      # facing north: the map upside down
        assert window._sky_turn == pytest.approx(180 - window._sky_declination, abs=0.01)
        window._set_sky_follow(False)
        assert not window._phone_aim.running and window._sky_turn == 0 and not window._sky_reticle.get_visible()
        # the same sky in view, now north up: the north, 40° up
        x, y = charts.sky_xy(40, window._sky_declination)
        assert np.mean(ax.get_xlim()) == pytest.approx(x, abs=1e-6)
        assert np.mean(ax.get_ylim()) == pytest.approx(y, abs=1e-6)
        assert not window._sky_follow_btn.isChecked()

    def test_the_finger_does_not_move_a_followed_map(self, window, qapp):
        ax = self._sky(window, qapp)
        window._set_sky_follow(True)
        self._aim_at(window, 20, 90)
        center = window._sky_center
        x, y = ax.transData.transform(center)
        window._on_sky_press(MouseEvent("button_press_event", window.canvas_sky, x, y, button=1))
        window._on_sky_hover(MouseEvent("motion_notify_event", window.canvas_sky, x + 80, y, button=1))
        window._on_sky_release(MouseEvent("button_release_event", window.canvas_sky, x + 80, y, button=1))
        assert window._sky_center == center

    def test_the_sensor_rests_on_another_page(self, window, qapp):
        self._sky(window, qapp)
        window._set_sky_follow(True)
        window.show_page(window._traj_page)
        _pump(qapp)
        window._sky_follow_tick()
        assert not window._phone_aim.running and window._sky_follow
        window.show_page(window._sky_page)
        _pump(qapp)
        window._sky_follow_tick()
        assert window._phone_aim.running

    def test_kept_through_a_new_drawing(self, window, qapp):
        self._sky(window, qapp)
        window._set_sky_follow(True)
        self._aim_at(window, 25, 300)
        window._dirty.add("sky")
        window._draw_visible_chart()                      # a new calculation, a frame of the time bar
        assert window._sky_reticle.get_visible()
        assert window._sky_ax._celeste_turn.to_values() != (1, 0, 0, 1, 0, 0)    # still turned

    def test_reset_stops_following(self, window, qapp):
        self._sky(window, qapp)
        window._set_sky_follow(True)
        self._aim_at(window, 60, 45)
        window._sky_reset_view()
        assert not window._sky_follow and window._sky_turn == 0 and window._sky_zoom == 1.0


class TestPhoneLocation:
    """Android asks the person before Céleste reads the phone's position (v4.22)."""

    class _App:
        def __init__(self, status, answer=None):
            self.status, self.answer, self.asked = status, answer, 0

        def checkPermission(self, _permission):
            return self.status

        def requestPermission(self, _permission, _context, callback):
            self.asked += 1
            self.status = self.answer
            callback()

    def test_the_permission(self, monkeypatch):
        import mobile
        from qt.QtCore import Qt
        from ui import phone
        said = []
        go_on, refused = (lambda: said.append("yes")), (lambda: said.append("no"))
        assert phone.location_allowed(None, go_on, refused)                         # a desktop: nothing to ask
        monkeypatch.setattr(mobile, "is_android", lambda: True)
        status = Qt.PermissionStatus
        assert phone.location_allowed(None, go_on, refused, app=self._App(status.Granted))
        app = self._App(status.Undetermined, answer=status.Granted)
        assert not phone.location_allowed(None, go_on, refused, app=app)           # asked, then yes
        assert app.asked == 1 and said == ["yes"]
        app = self._App(status.Undetermined, answer=status.Denied)
        assert not phone.location_allowed(None, go_on, refused, app=app)
        assert said == ["yes", "no"]
        app = self._App(status.Denied)                                              # Android asks no more
        assert not phone.location_allowed(None, go_on, refused, app=app)
        assert app.asked == 0 and said == ["yes", "no", "no"]

    def test_refused_no_address_lookup(self, window, monkeypatch):
        import gui
        from ui import phone

        def no_lookup():
            raise AssertionError("the IP address looked up although the person said no")
        monkeypatch.setattr(gui, "_ip_location", no_lookup)
        monkeypatch.setattr(phone, "location_allowed", lambda _ctx, _go_on, refused, app=None: refused() or False)
        lat = window.entry_lat.text()
        window.geolocate(interactive=False)                                         # at launch: a word below
        assert "permission" in window.statusBar().currentMessage()
        window.geolocate(interactive=True)                                          # the button: a window
        box = window._geo_dialog
        assert "permission" in box.text() and "Android" in box.informativeText()
        box.close()
        assert window.entry_lat.text() == lat and window._geo_source is None


class TestSkyTimeBar:
    """Ciel › Carte du ciel: the night on a time bar under the map, played with ▶ (v4.18)."""

    @staticmethod
    def _sky(window, qapp):
        window.show_page(window._sky_page)
        _pump(qapp, 3)
        return window._sky_time_slider

    def test_the_bar_spans_the_night(self, window, qapp):
        import planner
        slider = self._sky(window, qapp)
        night = planner.night_window(DTE, window._lat, window._lon, 0.0, window._zone, depths=((-0.833, "n"),))
        start = (night["start"] - DTE).total_seconds() / 60 - 30           # half an hour before sunset
        end = (night["end"] - DTE).total_seconds() / 60 + 30               # and after sunrise
        assert start - 5 < slider.minimum() <= start and end <= slider.maximum() < end + 5
        assert slider.value() == 0 and window._sky_offset_min == 0
        assert window._sky_time_lbl.text() == "21:30"                      # the place's time (UTC here)
        assert not window._sky_time_reset.isEnabled()

    def test_the_map_moves_not_the_calculation(self, window, qapp):
        slider = self._sky(window, qapp)
        sun_alt, stars = window.sun_data["alt"], list(window.visible_stars)
        slider.setValue(120)
        _pump(qapp, 3)
        assert window._sky_time_lbl.text() == "23:30" and window._sky_time_reset.isEnabled()
        assert "01/11/2026 23:30" in window.fig_sky.texts[-1].get_text()     # the map's title
        assert window._sky_scene["sun"]["alt"] < sun_alt - 8                 # the Sun near its lowest, at midnight
        assert window.sun_data["alt"] == sun_alt and window.visible_stars == stars
        vega = next(s for s in window._sky_scene["catalog"] if s["name"] == "Vega")
        calc_vega = next(s for s in window._sky_calc_scene["catalog"] if s["name"] == "Vega")
        assert abs(vega["alt"] - calc_vega["alt"]) > 5                       # setting in the north-west
        window._reset_sky_time()
        assert slider.value() == 0 and window._sky_scene is window._sky_calc_scene
        assert not window._sky_time_reset.isEnabled()

    def test_steps_of_five_minutes(self, window, qapp):
        slider = self._sky(window, qapp)
        slider.setValue(123)
        assert slider.value() == 125 and window._sky_offset_min == 125

    def test_the_animation_plays_the_night_to_its_end(self, window, qapp):
        from i18n import t
        slider = self._sky(window, qapp)
        window._toggle_sky_animation()
        assert window._sky_animating and window._sky_play.toolTip() == t("skymap.time_pause")
        for _ in range(500):
            if not window._sky_animating:
                break
            window._sky_animation_step()
        assert slider.value() == slider.maximum() and not window._sky_animating
        assert window._sky_play.toolTip() == t("skymap.time_play")
        window._toggle_sky_animation()                                      # at the end: from the start
        assert slider.value() == slider.minimum()
        window._stop_sky_animation()

    def test_same_calculation_keeps_the_time_another_does_not(self, window, qapp):
        slider = self._sky(window, qapp)
        slider.setValue(60)
        _pump(qapp, 3)
        window.calculate()                                                  # a new magnitude limit, say
        assert window._sky_offset_min == 60 and window._sky_scene is not window._sky_calc_scene
        window._set_datetime(DTE + timedelta(days=1))
        window.calculate()
        assert window._sky_offset_min == 0 and slider.value() == 0
        assert window._sky_scene is window._sky_calc_scene

    def test_the_object_found_follows_the_bar(self, window, qapp):
        slider = self._sky(window, qapp)
        window._find_on_sky(("planet", "Jupiter"))
        slider.setValue(240)
        _pump(qapp, 3)
        found = window._resolve_target(("planet", "Jupiter"))
        on_map = next(p for p in window._sky_scene["planets"] if p["name"] == "Jupiter")
        calc = next(p for p in window.planets if p["name"] == "Jupiter")
        assert found["alt"] == pytest.approx(on_map["alt"]) and abs(found["alt"] - calc["alt"]) > 10

    def test_moving_the_bar_ends_the_real_time(self, window, qapp):
        window.btn_live.setChecked(True)
        slider = self._sky(window, qapp)
        # the bar spans the night of the clock's time: in the morning it ends at the present
        # (the night under way), so it moves back; else forward
        step = 60 if slider.value() + 60 <= slider.maximum() else -60
        slider.setValue(slider.value() + step)
        assert not window.live_mode and not window.btn_live.isChecked()

    def test_a_hidden_animation_stops(self, window, qapp):
        self._sky(window, qapp)
        window._toggle_sky_animation()
        window.show_page(window._traj_page)
        _pump(qapp, 3)
        assert not window._sky_animating and not window._sky_anim_timer.isActive()

    def test_the_bar_survives_a_rebuild(self, window, qapp):
        slider = self._sky(window, qapp)
        slider.setValue(90)
        _pump(qapp, 3)
        window._lang_combo.setCurrentIndex(window._lang_combo.findData("en"))
        _pump(qapp)
        assert window._sky_time_slider.value() == 90 and window._sky_time_lbl.text() == "23:00"


# ──────────────────────────────────────────────────────────────────────
# Quality of the night in the Tonight card (v4.16, night_quality.py)
# ──────────────────────────────────────────────────────────────────────

class TestNightQuality:
    @staticmethod
    def _forecast(window, cloud):
        import night_quality
        return {night_quality._forecast_key(h["time"]): {"cloud": cloud, "humidity": 70.0}
                for h in window._tonight["hours"]}

    def test_rated_from_the_moon_by_default(self, window):
        import settings as prefs
        assert not prefs.get("weather_forecast") and not window._weather_btn.isChecked()
        text = window._quality_label.text()
        assert text.startswith("Qualité de la nuit : ") and "/100" in text
        assert "d'après la Lune seule" in text
        assert window._night_strip.isVisibleTo(window) and window._night_strip._hours
        assert not window._weather_credit.isVisibleTo(window)
        assert "échelle de Bortle" in window._quality_note.text()

    def test_bortle_of_the_place(self, window):
        import settings as prefs
        combo = window._bortle_combo
        assert combo.count() == 10 and combo.currentData() == 0
        combo.setCurrentIndex(combo.findData(4))
        assert prefs.get("bortle") == 4
        assert window._quality_note.text().startswith("Ciel du lieu : Bortle 4")
        assert "6,3" in window._quality_note.text()

    def test_forecast_turned_on(self, window, monkeypatch):
        import gui
        import settings as prefs
        asked = []

        def at_once(func, on_done, on_error):
            asked.append(func)
            on_done(self._forecast(window, 50.0))

        monkeypatch.setattr(gui.common, "_run_in_background", at_once)
        window._weather_btn.setChecked(True)
        assert prefs.get("weather_forecast") is True and len(asked) == 1
        assert "nuages 50 %" in window._quality_label.text()
        assert window._weather_credit.isVisibleTo(window)
        assert "Open-Meteo" in window._weather_credit.text()
        window._update_night_quality()
        assert len(asked) == 1                                    # kept: not asked again
        window._weather_btn.setChecked(False)
        assert "d'après la Lune seule" in window._quality_label.text()
        assert not window._weather_credit.isVisibleTo(window)

    def test_forecast_unavailable(self, window, monkeypatch):
        import gui
        monkeypatch.setattr(gui.common, "_run_in_background",
                            lambda func, on_done, on_error: on_error(OSError("no network")))
        window._weather_btn.setChecked(True)
        assert "indisponible" in window._quality_label.text()

    def test_hour_tooltips(self, window):
        tips = window._night_strip._tips
        assert tips and all("/100" in tip for tip in tips)
        assert any("Lune" in tip for tip in tips)


# ──────────────────────────────────────────────────────────────────────
# Observation log, Observer › Journal (v4.17, journal.py)
# ──────────────────────────────────────────────────────────────────────

class TestJournal:
    @staticmethod
    def _add(window, target="M31 Galaxie d'Andromède", notes="Bras de poussière en vision décalée"):
        dlg = window._journal_dialog(target=target)
        dlg.fields["instrument"].setText("Lunette 80/480")
        dlg.fields["seeing"].setCurrentIndex(dlg.fields["seeing"].findData(4))
        dlg.fields["transparency"].setCurrentIndex(dlg.fields["transparency"].findData(3))
        dlg.fields["notes"].setPlainText(notes)
        return dlg, dlg.save()

    def test_a_page_of_observer(self, window, qapp):
        observe = window.tabs.widget(4)
        assert [observe.tabText(i) for i in range(observe.count())] == ["Cibles", "Occultations", "Journal"]
        window.show_page(window._journal_page)
        _pump(qapp, 3)
        assert window.current_page() is window._journal_page
        assert window._journal_empty.isVisibleTo(window) and not window._journal_table.isVisibleTo(window)
        assert window._journal_count.text() == "0 observation"

    def test_add(self, window, tmp_path):
        import settings as prefs
        dlg, kept = self._add(window)
        assert kept["target"] == "M31 Galaxie d'Andromède" and kept["place"] == "Cherbourg-en-Cotentin"
        assert kept["seeing"] == 4 and kept["transparency"] == 3 and kept["lat"] == pytest.approx(49.6333)
        assert kept["quality"] == window._night_quality["score"]
        assert (tmp_path / "journal.json").is_file()
        table = window._journal_table
        assert table.rowCount() == 1 and table.item(0, 1).text() == "M31 Galaxie d'Andromède"
        assert table.item(0, 4).text() == "4/5 · 3/5"
        assert window._journal_count.text() == "1 observation"
        assert prefs.get("journal_instrument") == "Lunette 80/480"
        assert window._journal_dialog().fields["instrument"].text() == "Lunette 80/480"   # remembered

    def test_the_date_is_kept_in_ut(self, window):
        import journal
        from datetime import datetime
        dlg = window._journal_dialog(target="Jupiter")
        dlg.fields["date"].setDateTime(QDateTime(QDate(2026, 11, 12), QTime(22, 15)))
        dlg.save()
        entry = journal.load()[0]
        assert entry["date"] == "2026-11-12T22:15:00"                         # the fixture's zone is UTC
        assert datetime.fromisoformat(entry["date"]).hour == 22

    def test_a_target_is_needed(self, window):
        import journal
        dlg = window._journal_dialog()
        assert dlg.save() is None and journal.load() == []

    def test_edit_and_delete(self, window, monkeypatch):
        import gui
        import journal
        self._add(window)
        window._journal_table.selectRow(0)
        assert window._journal_edit_btn.isEnabled()
        window._journal_edit_selected()
        dlg = window._journal_dlg
        assert dlg.fields["target"].text() == "M31 Galaxie d'Andromède"
        dlg.fields["notes"].setPlainText("Ciel voilé vers minuit")
        dlg.save()
        assert len(journal.load()) == 1 and journal.load()[0]["notes"] == "Ciel voilé vers minuit"
        window._journal_table.selectRow(0)
        monkeypatch.setattr(gui.common, "QMessageBox", _yes_box(gui))
        window._journal_delete_selected()
        assert journal.load() == [] and window._journal_count.text() == "0 observation"

    def test_export(self, window, tmp_path, monkeypatch):
        import gui
        self._add(window)
        out = tmp_path / "journal.csv"
        monkeypatch.setattr(gui.QFileDialog, "getSaveFileName", lambda *a, **k: (str(out), "CSV (*.csv)"))
        window._journal_export()
        text = out.read_text(encoding="utf-8-sig")
        assert text.splitlines()[0].startswith("Date (TU),Cible,Lieu")
        assert "M31 Galaxie d'Andromède" in text and "Lunette 80/480" in text

    def test_from_the_targets_list(self, planner_tab, qapp):
        w = planner_tab
        table = w._plan_tables["deep_sky"]
        table.selectRow(0)
        w._plan_context_menu(table.visualItemRect(table.item(0, 0)).center())
        actions = [a for a in w._plan_menu.actions() if a.text() == "Noter une observation"]
        assert actions
        actions[0].trigger()
        dlg = w._journal_dlg
        assert dlg.fields["target"].text() == table.item(0, 0).data(gui_name_role())
        dlg.reject()


def test_qt_standard_buttons_in_the_interface_language(qapp):
    """Qt's own texts follow the language: Save becomes Enregistrer (qtbase_fr.qm of the binding)."""
    import gui
    from qt.QtWidgets import QDialogButtonBox
    try:
        assert gui.install_qt_translation("fr")
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        texts = {b.text().replace("&", "") for b in box.buttons()}
        assert texts == {"Enregistrer", "Annuler"}
        assert gui.install_qt_translation("de")
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        assert box.buttons()[0].text().replace("&", "") == "Abbrechen"
    finally:
        assert not gui.install_qt_translation("en")                 # English: Qt's own texts
    box = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
    assert box.buttons()[0].text().replace("&", "") == "Cancel"


class TestWeekQuality:
    def test_seven_nights(self, window):
        dlg = window.show_week_quality()
        table = dlg.table
        assert table.rowCount() == 7 and table.columnCount() == 4               # no clouds column without forecast
        headers = [table.horizontalHeaderItem(c).text() for c in range(table.columnCount())]
        assert headers == ["Nuit", "Qualité", "Meilleur moment", "Lune"]
        quality = table.item(0, 1).data(Qt.ItemDataRole.UserRole)
        assert "/100" in quality and table.cellWidget(0, 1).text() == quality
        assert "éclairée à" in table.item(0, 3).text()
        first = window._week_quality(1)[0][1]
        assert quality.endswith(f"{first['score']}/100")                        # the night of the chosen date
        dlg.reject()

    def test_with_the_forecast(self, window, monkeypatch):
        import gui
        import night_quality
        night = window._tonight
        data = {night_quality._forecast_key(h["time"]): {"cloud": 80.0, "humidity": 70.0} for h in night["hours"]}
        monkeypatch.setattr(gui.common, "_run_in_background", lambda func, ok, ko: ok(data))
        window._weather_btn.setChecked(True)
        dlg = window.show_week_quality()
        table = dlg.table
        assert table.columnCount() == 5 and table.horizontalHeaderItem(4).text() == "Nuages"
        assert table.item(0, 4).text() == "80 %"
        assert table.item(6, 4).text() == "—"                                  # beyond the sample forecast
        dlg.reject()


def test_quality_of_the_night_in_the_targets(planner_tab):
    """Observer › Targets: the quality of the night under the planner's summary, as in Tonight."""
    w = planner_tab
    summary = w._plan_summary.text()
    assert summary.splitlines()[-1] == w._quality_label.text()
    assert "Qualité de la nuit" in summary


def test_zone_without_timezonefinder(monkeypatch):
    """Android ships no timezonefinder: the automatic zone is then the device's own."""
    import gui

    def missing():
        raise ImportError("No module named 'timezonefinder'")

    gui.common._zone_at.cache_clear()
    monkeypatch.setattr(gui.common, "_tz_finder", missing)
    try:
        monkeypatch.setattr(gui.common, "_system_zone", lambda: "Europe/Paris")
        assert gui.common._zone_at(35.68, 139.69) == "Europe/Paris"
    finally:
        gui.common._zone_at.cache_clear()
    assert gui.common._system_zone() in gui.common._zone_names() or gui.common._system_zone() == "UTC"


# ──────────────────────────────────────────────────────────────────────
# Near-Earth asteroids and occultations (v4.20)
# ──────────────────────────────────────────────────────────────────────

_DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


@pytest.fixture
def asteroids(window, qapp, monkeypatch):
    """The window at Paris, with the samples of the IOTA predictions (2026) and of CNEOS'
    list on disk, Horizons answering for 2016 NV only, and the background work done at once."""
    import zipfile
    import gui
    import neo
    import occultations

    os.makedirs(occultations.CACHE_DIR, exist_ok=True)
    with zipfile.ZipFile(occultations.cache_path(2026), "w") as archive:
        archive.write(os.path.join(_DATA, "occelmnt_sample.xml"), "2026-iota-all.xml")
    with open(os.path.join(_DATA, "cad_sample.json"), encoding="utf-8") as f:
        payload = f.read()
    with open(neo.CACHE, "w", encoding="utf-8") as f:
        f.write(payload)
    with open(os.path.join(_DATA, "horizons_2016NV.txt"), encoding="utf-8") as f:
        rows = neo.parse_ephemeris(f.read())

    def ephemeris(approach, timeout=30):
        if approach["designation"] != "2016 NV":
            raise OSError("no Horizons in the tests")
        return rows
    monkeypatch.setattr(neo, "ephemeris", ephemeris)

    def run_now(func, on_done, on_error):
        try:
            result = func()
        except Exception as exc:  # noqa: BLE001
            on_error(exc)
        else:
            on_done(result)
    monkeypatch.setattr(gui.common, "_run_in_background", run_now)
    window._set_place(48.85, 2.35, "Paris")
    return window


def _at(window, qapp, date):
    window._set_datetime(date)
    window.calculate()
    _pump(qapp, 3)


def _texts(table, col):
    return [table.item(r, col).text() for r in range(table.rowCount())]


def _plain(label):
    """The text of a rich-text label, without its tags."""
    import html
    return html.unescape(re.sub(r"<br>", "\n", re.sub(r"</?b>", "", label.text())))


class TestAsteroids:
    def test_occultations_page(self, asteroids, qapp):
        import settings as prefs
        window = asteroids
        _at(window, qapp, datetime(2026, 6, 1, 12, 0))
        window.show_page(window._occultations_page)
        _pump(qapp, 3)
        table = window._occ_table
        assert _texts(table, 1) == ["(954) Li · 52 km"]                  # 6 months: Juno is in December
        assert _texts(table, 3) == ["Sur le lieu"]
        assert _texts(table, 4) == ["2,0 s"]
        assert "1 occultation à moins de 100 km" in window._occ_status.text()
        assert "1 sur le lieu" in window._occ_status.text()
        details = _plain(window._occ_details)
        assert "(954) Li cache l'étoile UCAC4 348-085188" in details
        assert "La bande passe sur le lieu" in details and "Ophiuchus" in details
        assert "Lune éclairée à" in details and "JPL#71" in details
        window._occ_months.setCurrentIndex(window._occ_months.findData(12))      # into 2027: not published
        _pump(qapp, 3)
        assert prefs.get("occultation_months") == 12
        assert _texts(table, 1)[-1] == "(3) Juno · 249 km"
        assert "pas de prédictions 2027" in window._occ_status.text()

    def test_occultations_none_near(self, asteroids, qapp):
        window = asteroids
        window._set_place(-33.87, 151.21, "Sydney")
        _at(window, qapp, datetime(2026, 6, 1, 12, 0))
        window.show_page(window._occultations_page)
        _pump(qapp, 3)
        assert window._occ_table.rowCount() == 0
        assert "Aucune bande à moins de 100 km" in _plain(window._occ_details)

    def test_neo_page(self, asteroids, qapp):
        import settings as prefs
        window = asteroids
        _at(window, qapp, datetime(2026, 12, 1, 12, 0))
        window.show_page(window._neo_page)
        _pump(qapp, 3)
        table = window._neo_table
        assert _texts(table, 1) == ["2016 NV"]                              # 60 days
        assert _texts(table, 2) == ["14,3 DL"]
        assert _texts(table, 3) == ["284 à 634 m"]
        assert _texts(table, 5) == ["15,0 · visible"]                       # Horizons, seen from Paris
        details = _plain(window._neo_details)
        assert "remarquable" in details and "14,25 fois la distance de la Lune" in details
        assert "Magnitude 15,0 au plus près (JPL Horizons)" in details
        assert "Visible du 08/12 18:00 au 09/12 00:00" in details and "Poissons" in details
        assert "7 passages" in window._neo_status.text()                    # the sample's whole list
        window._neo_days.setCurrentIndex(window._neo_days.findData(365))
        _pump(qapp, 3)
        assert prefs.get("neo_days") == 365
        assert _texts(table, 1) == ["2016 NV", "506074 Svarog", "137108 (1999 AN10)", "2026 VP8"]
        assert _texts(table, 3)[1] == "665 m"                               # measured
        assert _texts(table, 5)[3] == "> 16"
        window._neo_notable.setChecked(True)
        _pump(qapp, 3)
        assert _texts(table, 1) == ["2016 NV", "506074 Svarog", "137108 (1999 AN10)"]

    def test_phone_rows(self, asteroids, qapp):
        window = asteroids
        _at(window, qapp, datetime(2026, 12, 1, 12, 0))
        window.show_page(window._neo_page)
        _pump(qapp, 3)
        window.resize(360, 740)
        _pump(qapp, 5)
        table = window._neo_table
        shown = [c for c in range(table.columnCount()) if not table.isColumnHidden(c)]
        assert shown == [0, 1]
        assert _texts(table, 0) == ["08/12 18:41"]
        assert _texts(table, 1) == ["2016 NV · 14,3 DL · 15,0 · visible"]
        window.resize(1350, 820)
        _pump(qapp, 5)
        assert _texts(table, 0) == ["08/12/2026 18:41"] and not table.isColumnHidden(5)

    def test_tonight(self, asteroids, qapp):
        window = asteroids
        _at(window, qapp, datetime(2026, 6, 6, 20, 0))
        lines = [text for text, _tone in window._tonight_lines()]
        assert any("Occultation à 23:22 : (954) Li cache une étoile de magnitude 10,4, la bande passe sur le lieu"
                   in line for line in lines), lines
        _at(window, qapp, datetime(2026, 12, 8, 17, 0))
        lines = [text for text, _tone in window._tonight_lines()]
        assert any("Astéroïde 2016 NV au plus près à 18:42, à 14,3 distances lunaires (284 à 634 m)" in line
                   for line in lines), lines

    def test_calendar_titles(self, asteroids, qapp):
        import astro_calendar
        window = asteroids
        items = astro_calendar.collect(datetime(2026, 6, 1), datetime(2027, 1, 1), 48.85, 2.35,
                                       categories=("neo", "occultations"))
        titles = [(i["category"], window._calendar_title(i)) for i in items]
        assert ("occultations", "(954) Li cache une étoile de magnitude 10,4") in titles
        assert ("neo", "Astéroïde 2016 NV à 14,3 distances lunaires") in titles
        li = next(i for i in items if i["category"] == "occultations")
        assert any("La bande passe sur le lieu (2,0 s)" in line for line in window._calendar_details(li))


# ──────────────────────────────────────────────────────────────────────
# Recent novae and supernovae (v4.21)
# ──────────────────────────────────────────────────────────────────────

@pytest.fixture
def novae_lists(window, qapp, monkeypatch):
    """The window at Paris on the night of 13 November 2026, the samples of both lists answering
    the downloads, and the background work done at once."""
    import gui
    import transients
    pages = {}
    for url, name in ((transients.SUPERNOVAE_URL, "snactive_sample.html"), (transients.NOVAE_URL, "novae_sample.html")):
        with open(os.path.join(_DATA, name), encoding="utf-8") as f:
            pages[url] = f.read()
    monkeypatch.setattr(transients, "_get", lambda url, timeout: pages[url])

    def run_now(func, on_done, on_error):
        try:
            result = func()
        except Exception as exc:  # noqa: BLE001
            on_error(exc)
        else:
            on_done(result)
    monkeypatch.setattr(gui.common, "_run_in_background", run_now)
    window._set_place(48.85, 2.35, "Paris")
    _at(window, qapp, datetime(2026, 11, 13, 21, 0))
    return window


class TestTransients:
    def test_a_page_of_the_sky(self, window):
        sky = window.tabs.widget(1)
        assert [sky.tabText(i) for i in range(sky.count())] == ["Carte du ciel", "Trajectoires", "Novae et supernovae"]

    def test_the_page(self, novae_lists, qapp):
        import settings as prefs
        window = novae_lists
        window.show_page(window._transients_page)
        _pump(qapp, 3)
        table = window._tr_table
        names = _texts(table, 0)
        assert names[:3] == ["V488 Sge", "SN 2026ahvu", "AT 2026aina"]           # the brightest now first
        assert set(names) == {"SN 2026ahvu", "AT 2026aina", "SN 2026sqf", "SN 2026ahvi", "V8056 Sgr",
                              "TCP J17520680-2343207", "V488 Sge", "V1452 Tau"}
        row = names.index("SN 2026sqf")
        assert table.item(row, 1).text() == "Supernova Ia-CSM" and table.item(row, 2).text() == "NGC 3310"
        assert table.item(row, 3).text() == "13,3" and table.item(row, 4).text() == "08/07/2026"
        assert table.item(row, 5).text().endswith("°")                          # high before dawn
        assert table.item(names.index("SN 2026ahvu"), 5).text() == "—"          # never up from Paris
        assert table.item(names.index("TCP J17520680-2343207"), 3).text() == "max 11,3"   # faded since
        assert "8 objets" in window._tr_status.text()
        table.selectRow(row)
        details = _plain(window._tr_details)
        assert "SN 2026sqf · Supernova Ia-CSM" in details and "Dans la galaxie NGC 3310 (Grande Ourse)" in details
        assert "Éclat maximal : magnitude 11,2 le 28/07/2026" in details
        assert "Découverte le 08/07/2026 par Patrick Wiggins" in details and "millions d'années-lumière" in details
        assert "Cette nuit, au plus haut dans le noir à" in details
        window._tr_mag.setCurrentIndex(window._tr_mag.findData(13))
        _pump(qapp, 3)
        assert prefs.get("transients_mag") == 13 and "SN 2026sqf" not in _texts(table, 0)

    def test_on_the_sky_map(self, novae_lists, qapp):
        window = novae_lists
        window.show_page(window._transients_page)
        _pump(qapp, 3)
        names = [o["name"] for o in window._sky_scene["transients"]]
        assert "V488 Sge" in names and "SN 2026ahvu" not in names                # above the horizon only
        assert all(o["kind"] == "transient" for o in window._sky_scene["transients"])
        table = window._tr_table
        table.selectRow(_texts(table, 0).index("V488 Sge"))
        window._show_transient_on_map()
        _pump(qapp, 3)
        assert window.current_page() is window._sky_page
        assert window._sky_found == ("transient", "V488 Sge")
        assert window._chart_hints["sky"].text().startswith("V488 Sge : hauteur")
        found = window._resolve_target(("transient", "V488 Sge"))
        title, rows = window._object_details(found)
        assert title == "V488 Sge" and ("Type", "Nova") in rows
        window._tr_on_map.setChecked(False)
        _pump(qapp, 3)
        assert window._sky_scene["transients"] == []

    def test_found_by_name(self, novae_lists, qapp):
        window = novae_lists
        window.show_page(window._transients_page)
        _pump(qapp, 3)
        window.show_page(window._sky_page)
        _pump(qapp, 3)
        assert window._find_targets("2026sqf")[0] == ("SN 2026sqf", ("transient", "SN 2026sqf"))

    def test_tonight(self, novae_lists, qapp):
        """A nova found three weeks before, high in the evening: in Tonight."""
        window = novae_lists
        window.show_page(window._transients_page)            # the lists on disk
        _pump(qapp, 3)
        _at(window, qapp, datetime(2026, 9, 15, 20, 0))
        lines = [text for text, _tone in window._tonight_lines()]
        assert any(line.startswith("★︎ V488 Sge (Nova), magnitude max 7,1, au plus haut à") for line in lines), lines



# ──────────────────────────────────────────────────────────────────────
# The constellation charts (v4.24)
# ──────────────────────────────────────────────────────────────────────

class TestConstellations:
    """Ciel › Constellations: the chart of the one chosen, its facts, its sheet."""

    @staticmethod
    def _page(window, qapp):
        window.show_page(window._constellation_page)
        _pump(qapp, 3)
        return window._co_combo

    def test_orion_by_default(self, window, qapp):
        combo = self._page(window, qapp)
        assert combo.count() == 88 and combo.currentData() == "Ori"
        assert window.fig_co.axes and window._co_scene["key"] == "Ori"
        facts = window._co_facts.text()
        assert "Orion" in facts and "594 degrés carrés" in facts and "janvier" in facts and "Rigel" in facts

    def test_alphabetical_without_accents(self, window, qapp):
        combo = self._page(window, qapp)
        names = [combo.itemText(i) for i in range(combo.count())]
        assert names.index("Écu de Sobieski (Sct)") < names.index("Eridan (Eri)") < names.index("Flèche (Sge)")

    def test_another_one_is_kept(self, window, qapp):
        import settings as prefs
        combo = self._page(window, qapp)
        combo.setCurrentIndex(combo.findData("Cru"))
        _pump(qapp)
        assert window._co_scene["key"] == "Cru" and prefs.get("constellation") == "Cru"
        assert "jamais visible depuis votre lieu" in window._co_facts.text()      # from Cherbourg

    def test_on_a_phone(self, window, qapp):
        """The chart as tall as the phone is wide, the page scrolling to the facts; the labels measured
        again at the phone's size, none on another."""
        combo = self._page(window, qapp)
        combo.setCurrentIndex(combo.findData("Vir"))
        window.resize(360, 740)
        _pump(qapp, 5)
        canvas = window.canvas_co
        assert canvas.height() >= 300 and abs(canvas.height() - canvas.width()) <= 2       # square
        assert window._constellation_page.verticalScrollBar().maximum() > 0
        ax = window.fig_co.axes[0]
        shown = [t.get_window_extent() for t in ax._celeste_labels if t.get_visible()]
        assert shown and not any(a.overlaps(b) for i, a in enumerate(shown) for b in shown[i + 1:])
        window.resize(1350, 820)
        _pump(qapp, 5)
        assert canvas.minimumHeight() == 0 and canvas.height() > 400

    def test_the_sheet(self, window, qapp, tmp_path):
        self._page(window, qapp)
        path = window._save_constellation_sheet(str(tmp_path / "orion.pdf"))
        assert path and open(path, "rb").read(5) == b"%PDF-"
        assert "orion.pdf" in window.statusBar().currentMessage()
