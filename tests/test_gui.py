"""
tests/test_gui.py — Tests de l'interface PyQt6 (sans écran)
============================================================
Construit la fenêtre de Céleste hors écran (QT_QPA_PLATFORM=offscreen) et
la pilote : calcul, changement de langue et de thème (Nuit, Jour,
Observation) sans redémarrer, favoris, recherche d'événements, info-bulles
et fiches de la carte du ciel, temps réel ; vérifie aussi deux
règles du design Astræos (pas d'emoji, symboles suivis de U+FE0E).

Les préférences et les favoris sont écrits dans un dossier temporaire : ceux
de l'utilisateur (~/.celeste) ne sont jamais modifiés.
Les tests sont ignorés si PyQt6 (ou les bibliothèques système de Qt)
manquent.

Lancer avec :  pytest tests/test_gui.py -v
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

pytest.importorskip("PyQt6.QtWidgets", reason="PyQt6 ou les bibliothèques de Qt manquent")
pytest.importorskip("matplotlib")

from matplotlib.backend_bases import MouseEvent  # noqa: E402
from PyQt6.QtCore import QEvent, Qt  # noqa: E402
from PyQt6.QtWidgets import (  # noqa: E402
    QAbstractButton, QApplication, QDialog, QFrame, QLabel, QMessageBox,
)

DTE = datetime(2026, 11, 1, 21, 30, 0)     # nuit à Cherbourg, Véga bien haute


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
    prefs.set("default_tz", "UTC")      # heures attendues en TU ; l'automatique a ses tests
    favorites = tmp_path / "favorites.json"
    favorites.write_text(json.dumps({
        "Paris": {"lat": 48.8566, "lon": 2.3522},
        "Tokyo": {"lat": 35.6762, "lon": 139.6503},
    }), encoding="utf-8")
    monkeypatch.setattr(gui, "_FAVORITES_FILE", str(favorites))
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
    """Détruit vraiment la fenêtre : processEvents() seul ne traite pas deleteLater(),
    et les fenêtres des tests précédents, toujours là, ralentissaient chaque
    changement de thème ou de langue (toute l'application est restylée)."""
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
# 1. Calcul et affichage
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
        assert re.match(r"^\d+,\d{4}$", items["col_dist"].text())      # l'unité est dans l'en-tête
        assert items["col_planet"].toolTip() == "Visible"
        assert re.match(r"^\d\d:\d\d$", items["col_rise"].text())
        shown = [r for r in range(window.planet_table.rowCount()) if not window.planet_table.isRowHidden(r)]
        assert len(shown) == 7                                             # Mercure à Neptune

    def test_tonight(self, window):
        """« Ce soir » (heures en TU dans ces tests) : la nuit, la Lune, les planètes, la suite."""
        lines = [text for text, _tone in window._tonight_lines()]
        assert lines[0] == "Nuit noire de 18:33 à 05:08"
        assert lines[1].endswith("Lune éclairée à 49 %, se lève à 22:42")
        assert any("Jupiter · visible le matin" in x and "magnitude −2,0" in x for x in lines)
        assert lines[-1].startswith("À venir : 03/11 Lune et Mars, le matin")
        shown = [w.text() for w in window.findChildren(QLabel) if w.isVisible()]
        assert "Nuit noire de 18:33 à 05:08" in shown

    def test_minor_planets_of_the_planet_table(self, window):
        """Le choix « Planètes mineures » montre Cérès … Makemake, magnitude comprise."""
        window._planet_selector.buttons["minor"].click()
        table = window.planet_table
        shown = [table.item(r, 0).text().split(" ", 1)[-1] for r in range(table.rowCount())
                 if not table.isRowHidden(r)]
        assert shown == ["Cérès", "Pallas", "Junon", "Vesta", "Pluton", "Éris", "Hauméa", "Makémaké", "Sedna"]
        assert table.item(window._planet_items["Eris"]["col_planet"].row(), 0).toolTip().startswith("(136199) Éris")
        vesta = window._planet_items["Vesta"]
        assert re.match(r"^\d,\d$", vesta["col_mag"].text())               # Vesta : magnitude 6 à 8
        assert re.match(r"^\d\d:\d\d$", vesta["col_rise"].text())
        window._planet_selector.buttons["planets"].click()
        vesta_row = window._planet_items["Vesta"]["col_planet"].row()
        assert table.isRowHidden(vesta_row)

    def _shown(self, window):
        table = window.planet_table
        return [table.item(r, 0).data(Qt.ItemDataRole.UserRole + 1) for r in range(table.rowCount())
                if not table.isRowHidden(r)]

    def test_all_bodies_and_visible_only(self, window):
        """Issue #21 : tous les astres, ou seulement ceux au-dessus de l'horizon."""
        window._planet_selector.buttons["all"].click()
        assert len(self._shown(window)) == 16
        window._planet_visible.setChecked(True)
        up = self._shown(window)
        assert 0 < len(up) < 16
        assert all(window._planet_alt[name] > 0 for name in up)
        window._planet_visible.setChecked(False)
        window._planet_selector.buttons["planets"].click()

    def test_sort_by_magnitude(self, window):
        """Clic sur « Mag. » : du plus brillant au plus faible ; « Planète » : ordre du Système solaire."""
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
        """L'erreur s'affiche sous le champ (ChampSaisie), sans fenêtre."""
        before = dict(window.sun_data)
        window.entry_lat.setText("123")
        window.calculate()
        assert window.entry_lat.property("invalid") is True
        assert window.field_lat.erreur.isVisibleTo(window)
        assert "−90" in window.field_lat.erreur.text()
        assert window.sun_data == before
        window.entry_lat.setText("49,6333")
        window.calculate()
        assert window.entry_lat.property("invalid") is False
        assert not window.field_lat.erreur.isVisibleTo(window)

    def test_data_cards(self, window):
        """Les valeurs vedettes en style cadran, nombres à la française."""
        assert window.card_sun_rise.valeur.text() == "06:55"
        assert window.card_sun_alt.unite.text() == "°"
        assert "," in window.card_moon_alt.valeur.text()
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
# 2. Langue et thème appliqués sans redémarrage
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
        """Le sélecteur de thème de la barre latérale applique le thème aussitôt."""
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
# 3. Favoris
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
# 4. Événements
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
        """Depuis le 1er novembre 2026 : 2 éclipses de Soleil, 3 de Lune pénombrales."""
        window._search_eclipses_gui()
        cards = _event_cards(window)
        assert len(cards) == 5
        assert QApplication.overrideCursor() is None
        texts = [" ".join(lbl.text() for lbl in c.findChildren(QLabel)) for c in cards]
        assert "Annulaire" in texts[0] and "06/02/2027" in texts[0]
        assert "Totale" in texts[3] and "02/08/2027" in texts[3]
        assert all("Pénombrale" in texts[i] for i in (1, 2, 4))
        assert "Incertaine" in texts[2]              # 18/07/2027, magnitude 0,001

    def test_eclipse_time_is_greatest_eclipse_in_ut(self, window):
        """Maximum en TU, à la minute près : NASA 16:00:47 et 10:07:49 TD, ΔT ≈ 69 s."""
        window._search_eclipses_gui()
        texts = [" ".join(lbl.text() for lbl in c.findChildren(QLabel))
                 for c in _event_cards(window)]
        assert "06/02/2027 16:00 TU" in texts[0]
        assert "02/08/2027 10:07 TU" in texts[3]

    def test_conjunction_time_and_kind(self, window):
        """Mercure en conjonction inférieure le 04/11/2026 à 14:24 TU (Horizons 14:24:19)."""
        window._search_conjunctions_gui()
        texts = [" ".join(lbl.text() for lbl in c.findChildren(QLabel))
                 for c in _event_cards(window)]
        first = next(text for text in texts if "Mercure en conjonction inférieure" in text)
        assert "04/11/2026 14:24 TU" in first and "Mercure au sud du Soleil" in first
        assert "Heure locale" not in first                  # lieu en TU : rien à ajouter
        assert any("plus grande élongation ouest (matin)" in text for text in texts)
        assert any("Mars au nord de Jupiter" in text for text in texts)

    def test_conjunction_local_time(self, window):
        """L'heure locale du lieu, heure d'hiver de Paris comprise, sous l'instant TU."""
        window.tz_menu.setCurrentIndex(window.tz_menu.findData("auto"))     # Cherbourg
        window._search_conjunctions_gui()
        texts = [" ".join(lbl.text() for lbl in c.findChildren(QLabel))
                 for c in _event_cards(window)]
        first = next(text for text in texts if "Mercure en conjonction inférieure" in text)
        assert "Heure locale 04/11 15:24 (Europe/Paris)" in first

    def test_map_of_a_conjunction(self, window, qapp):
        """Le bouton « Carte » d'une conjonction ouvre le trajet des astres parmi les étoiles."""
        from PyQt6.QtWidgets import QPushButton
        window._search_conjunctions_gui()
        qapp.processEvents()
        buttons = [b for card in _event_cards(window) for b in card.findChildren(QPushButton)
                   if b.text() == "Carte"]
        assert 0 < len(buttons) < len(_event_cards(window))     # saisons, périgées : sans carte
        buttons[0].click()
        qapp.processEvents()
        dlg = window._event_dialog
        assert dlg.isVisible() and dlg.windowTitle() == "Carte de l'évènement"
        dlg.close()

    def _texts(self, window):
        return [" ".join(lbl.text() for lbl in c.findChildren(QLabel)) for c in _event_cards(window)]

    def test_moon_seasons_and_minor_planets(self, window):
        """Lune, saisons et planètes mineures parmi les évènements de l'année."""
        window._search_conjunctions_gui()
        texts = self._texts(window)
        assert any("Solstice de décembre" in x and "21/12/2026 20:50 TU" in x for x in texts)
        assert any("Lune au périgée" in x and "Super lune" in x for x in texts)     # 24/12/2026
        assert any("Lune et" in x for x in texts)
        assert any("Vesta à l'opposition" in x for x in texts) is False           # en 2027 : non
        assert any(x.startswith("☍") or "à l'opposition" in x for x in texts)

    def test_visibility_line(self, window):
        """Chaque conjonction dit si on la voit d'ici, et quand."""
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
        """Les évènements affichés vont dans un agenda iCalendar."""
        import gui
        target = tmp_path / "agenda"
        monkeypatch.setattr(gui.QFileDialog, "getSaveFileName",
                            staticmethod(lambda *a, **k: (str(target), "")))
        window._evt_filters["moon"].setChecked(False)
        window._search_conjunctions_gui()
        assert window._btn_ics.isEnabled()
        window._btn_ics.click()
        text = (tmp_path / "agenda.ics").read_bytes().decode("utf-8")      # CRLF gardés
        assert text.startswith("BEGIN:VCALENDAR\r\n") and text.endswith("END:VCALENDAR\r\n")
        assert text.count("BEGIN:VEVENT") == len(_event_cards(window))
        assert "SUMMARY:Solstice de décembre\r\n" in text and "DTSTART:20261221T205014Z" in text
        assert all(len(line.encode("utf-8")) <= 75 for line in text.split("\r\n"))
        window._evt_filters["moon"].setChecked(True)

    def test_meteor_showers(self, window, tmp_path, monkeypatch):
        """Les étoiles filantes : leur filtre, la nuit du maximum vue d'ici, l'agenda."""
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
        assert any("gêne forte" in x for x in texts)            # les Ursides, à la pleine Lune
        target = tmp_path / "agenda.ics"
        monkeypatch.setattr(gui.QFileDialog, "getSaveFileName",
                            staticmethod(lambda *a, **k: (str(target), "")))
        window._btn_ics.click()
        agenda = target.read_bytes().decode("utf-8")
        assert agenda.count("BEGIN:VEVENT") == 13 and "SUMMARY:Maximum des Géminides\r\n" in agenda
        for box in window._evt_filters.values():
            box.setChecked(box is not window._evt_filters["visible"])

    def test_eclipses_seen_from_here(self, window):
        """Cherbourg : l'éclipse annulaire du 06/02/2027 n'y passe pas, celle du 02/08/2027 oui."""
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
# 5. Carte du ciel, trajectoires : info-bulles et fiches
# ──────────────────────────────────────────────────────────────────────

def _vega(window):
    return next(o for o in window._sky_objects if o["name"] == "Vega")


class TestSkyMapAndTrajectory:
    def test_star_card_names_its_constellation(self, window):
        title, rows = window._object_details(_vega(window))
        assert title == "Vega"
        assert ("Constellation", "Triangle d'été") in rows
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
# 6. Temps réel
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
# 7. Règles du design Astræos
# ──────────────────────────────────────────────────────────────────────

# Symboles astronomiques admis (police Astraeos Symboles), point des pastilles
# symboles astronomiques de la police Astraeos Symboles (présentation texte, U+FE0E)
_ALLOWED = set("☉☽☾☿♀♂♃♄♅♆♇⊕♈★●○☌☍☄⚳⚴⚵⚶\u2bf1\u2bf2\U0001f77b\U0001f77c")


def _is_emoji(ch):
    code = ord(ch)
    return ch not in _ALLOWED and (0x1F000 <= code <= 0x1FAFF or 0x2600 <= code <= 0x27BF
                                   or 0x2B00 <= code <= 0x2BFF)


class TestAstraeosRules:
    @pytest.mark.parametrize("lang", ["fr", "en", "es", "de"])
    def test_no_emoji_in_the_interface(self, window, qapp, lang):
        """« Interface : pas d'emoji » : ni dans les textes, ni dans les onglets."""
        window._lang_combo.setCurrentIndex(window._lang_combo.findData(lang))
        _pump(qapp)
        texts = [w.text() for w in window.findChildren(QLabel)]
        texts += [w.text() for w in window.findChildren(QAbstractButton)]
        texts += [window.tabs.tabText(i) for i in range(window.tabs.count())]
        bad = {text for text in texts if any(_is_emoji(ch) for ch in text)}
        assert not bad, bad

    def test_symbols_use_text_presentation(self, window):
        """Chaque symbole d'astre est suivi de U+FE0E (jamais affiché en emoji)."""
        name = window._planet_items["Venus"]["col_planet"].text()
        assert name.startswith("\u2640\ufe0e")

    def test_single_gold_area(self, window):
        """Un seul bouton principal (aplat or) dans la fenêtre."""
        from PyQt6.QtWidgets import QPushButton
        principal = [b for b in window.findChildren(QPushButton)
                     if b.property("variante") == "principal" and b.isVisibleTo(window)]
        assert principal == [window.btn_calc]

    def test_live_mode_is_a_pressed_toggle(self, window):
        """Temps réel : bascule enfoncée et pastille « En direct »."""
        window.btn_live.toggle()
        assert window.btn_live.isChecked()
        assert window._lbl_live.isVisibleTo(window)
        assert window._lbl_live.text().endswith("En direct")
        window.btn_live.toggle()


# ──────────────────────────────────────────────────────────────────────
# Géolocalisation : service de l'appareil, adresse IP en secours
# ──────────────────────────────────────────────────────────────────────

class _FakeSource:
    """Service de localisation simulé : répond une position, ou l'erreur *error*
    (0 accès refusé, 1 fermé, 2 inconnue, 4 délai dépassé), avec ou sans dernière
    position connue."""
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
        """Novembre 2026 (heures en TU ici), puis décembre, puis retour à travers l'année."""
        window._show_moon_calendar()
        _pump(qapp)
        dlg = window._calendar_dialog
        assert dlg._title.text() == "Novembre 2026" and len(self._cells(dlg)) == 30
        texts = [" ".join(l.text() for l in c.findChildren(QLabel)) for c in self._cells(dlg)]
        assert "Pleine lune 14:54" in texts[23] and texts[23].startswith("24 100 %")   # 14:53:34
        assert "↑ —" in texts[1]                                  # pas de lever le 2
        window._fill_moon_calendar(+1)
        _pump(qapp)                                   # les nouvelles cases s'affichent au tour suivant
        assert dlg._title.text() == "Décembre 2026" and len(self._cells(dlg)) == 31
        window._fill_moon_calendar(-12)
        assert dlg._title.text() == "Décembre 2025"
        dlg.close()
        qapp.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        assert window._calendar_dialog is None

    def test_first_day_of_the_week(self, window, qapp):
        """En français, la semaine commence le lundi : le 1er novembre 2026, un dimanche, est en 7e colonne."""
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
        window._orrery_speed.setCurrentIndex(2)                       # 1 mois par pas
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
        window._orrery_speed.setCurrentIndex(3)                       # 1 an par pas
        window._orrery_step(+1)
        window._reset_orrery()
        assert window._orrery_offset == 0.0 and window._orrery_date.text() == "01/11/2026"

    def test_stops_at_the_end_of_the_ephemeris(self, window, qapp):
        self._planets_tab(window, qapp)
        window._toggle_orrery()
        window._orrery_offset = 200 * 365.25
        window._orrery_step(+1)
        assert window._orrery_date.text() == "30/12/2149" and not window._orrery_timer.isActive()


class TestPlaceSearch:
    def test_suggestions_then_choice(self, window, qapp):
        """« londres » propose London ; la choisir remplit lieu, altitude et nom."""
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
        """Sans Nominatim, la ville la plus proche de la liste hors ligne nomme le point."""
        import gui
        monkeypatch.setattr(gui, "_nominatim_name", lambda lat, lon: "")
        assert gui._place_name(49.6333, -1.6167) == "Cherbourg"
        assert gui._place_name(48.0, -30.0) == ""


class TestGeolocation:
    def test_device_position_is_used(self, window, monkeypatch):
        """Cherbourg donné par le service de l'appareil, nommé par OpenStreetMap."""
        import gui
        monkeypatch.setattr(gui, "QGeoPositionInfoSource", _FakeSource((49.6386, -1.6164)))
        monkeypatch.setattr(gui, "_place_name", lambda lat, lon: "Cherbourg-en-Cotentin")
        window.geolocate()
        assert window.entry_lat.text().replace(",", ".") == "49.6386"
        assert window.location_name == "Cherbourg-en-Cotentin"
        assert "±25 m" in window.statusBar().currentMessage()

    def test_ip_address_only_as_a_fallback(self, window, monkeypatch):
        """Service muet : position de l'adresse IP, annoncée comme approximative."""
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
        """Issue #19 : accès refusé par Windows — la fenêtre le dit et ouvre les réglages."""
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
        """Délai dépassé : la dernière position connue de l'appareil plutôt que l'adresse IP."""
        import gui
        monkeypatch.setattr(gui, "QGeoPositionInfoSource",
                            _FakeSource(None, error=4, last=(49.6386, -1.6164)))
        monkeypatch.setattr(gui, "_place_name", lambda lat, lon: "Cherbourg-en-Cotentin")
        monkeypatch.setattr(gui.urllib.request, "urlopen", lambda *a, **k: pytest.fail("adresse IP"))
        window.geolocate()
        assert window.location_name == "Cherbourg-en-Cotentin"

    def test_no_window_at_startup(self, window, monkeypatch):
        """Au démarrage (géolocalisation automatique), la barre d'état seulement."""
        import gui
        monkeypatch.setattr(gui, "QGeoPositionInfoSource", _FakeSource(None, error=4))
        self._ip_answer(monkeypatch)
        window._geo_dialog = None
        window.geolocate(interactive=False)
        assert window._geo_dialog is None
        assert "approximative" in window.statusBar().currentMessage()


# ──────────────────────────────────────────────────────────────────────
# Onglet Coordonnées et format des angles
# ──────────────────────────────────────────────────────────────────────

class TestCoordinatesTab:
    """Onglet Coordonnées : x, y, z et angles en même temps."""

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
        """Listes en mode liste : aucun choix caché derrière des flèches de défilement."""
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
        """Par défaut : x, y, z héliocentriques, angles équatoriaux."""
        self._open(window)
        assert self._headers(window) == [
            "Astre", "x (UA)", "y (UA)", "z (UA)", "Dist. (UA)", "Mag.",
            "Angle Soleil", "Const.", "Asc. droite α", "Déclinaison δ"]
        rows = [window.coord_table.item(r, 0).text() for r in range(window.coord_table.rowCount())]
        assert [r.split(" ", 1)[-1] for r in rows] == self.BODIES
        sun, earth = self._row(window, "Soleil"), self._row(window, "Terre")
        assert sun[1:5] == ["—"] * 4                      # le Soleil est l'origine
        assert sun[5].startswith("−26,7") and sun[7] == "Lib"
        assert earth[1] != "—" and earth[5:] == ["—"] * 5   # la Terre : x, y, z seulement
        assert sun[8].endswith("s")                           # ascension droite en h m s

    def test_cartesian_and_angular_are_independent(self, window):
        """Changer l'origine cartésienne ne change pas les angles, et inversement."""
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
        assert self._row(window, "Soleil")[8:] == ["—", "—"]   # vu du Soleil
        assert self._row(window, "Terre")[8] != "—"
        assert "vues du Soleil" in window._coord_note.text()
        self._choose(window, "ecliptic_from", "earth")
        assert self._row(window, "Terre")[8:] == ["—", "—"]    # vu de la Terre
        assert self._row(window, "Soleil")[8] != "—"
        assert "vues de la Terre" in window._coord_note.text()

    @pytest.mark.parametrize("fmt, pattern", [("dms", r"^\d+h \d\dm \d\d,\ds$"),
                                              ("dm", r"^\d+h \d\d,\d{3}m$"),
                                              ("dd", r"^\d+,\d{5}h$")])
    def test_settings_format_applies_everywhere(self, window, fmt, pattern):
        """Format des paramètres : tout le logiciel, et le tableau qui le suit par défaut."""
        self._open(window)
        assert window.coord_menus["angle"].currentData() == "global"
        combo = window._anglefmt_combo
        combo.setCurrentIndex(combo.findData(fmt))
        assert re.match(pattern, window.sun_labels["ra"].text())
        assert re.match(pattern, self._row(window, "Vénus")[8])

    def test_coordinates_format_only_for_the_table(self, window):
        """Le format choisi dans l'onglet ne change que le tableau (issue #13)."""
        self._open(window)
        ephemeris = window.sun_labels["ra"].text()
        self._choose(window, "angle", "dd")
        assert re.match(r"^\d+,\d{5}h$", self._row(window, "Vénus")[8])
        assert window.sun_labels["ra"].text() == ephemeris
        window._anglefmt_combo.setCurrentIndex(window._anglefmt_combo.findData("dm"))
        assert re.match(r"^\d+h \d\d,\d{3}m$", window.sun_labels["ra"].text())
        assert re.match(r"^\d+,\d{5}h$", self._row(window, "Vénus")[8])   # garde le sien


# ──────────────────────────────────────────────────────────────────────
# Préférences et favoris hors du dépôt (~/.celeste)
# ──────────────────────────────────────────────────────────────────────

class TestUserFiles:
    def test_settings_live_in_the_user_folder(self, tmp_path, monkeypatch):
        """Écrites dans le dossier de l'utilisateur, créé au besoin."""
        import settings as prefs
        target = tmp_path / "celeste" / "settings.json"
        monkeypatch.setattr(prefs, "_SETTINGS_FILE", str(target))
        monkeypatch.setattr(prefs, "_LEGACY_SETTINGS_FILE", str(tmp_path / "absent.json"))
        prefs.load()
        prefs.set("theme", "jour")
        assert json.loads(target.read_text(encoding="utf-8"))["theme"] == "jour"

    def test_settings_of_a_previous_version_are_taken_over(self, tmp_path, monkeypatch):
        """Un settings.json resté dans le dossier de l'application est repris."""
        import settings as prefs
        legacy = tmp_path / "settings.json"
        legacy.write_text(json.dumps({"theme": "observation", "default_utc": 2}), encoding="utf-8")
        monkeypatch.setattr(prefs, "_SETTINGS_FILE", str(tmp_path / "user" / "settings.json"))
        monkeypatch.setattr(prefs, "_LEGACY_SETTINGS_FILE", str(legacy))
        prefs.load()
        assert prefs.get("theme") == "observation"
        assert prefs.get("default_tz") == "Etc/GMT-2"

    def test_favorites_start_from_the_default_list(self, window, tmp_path, monkeypatch):
        """Sans favoris enregistrés, la liste de départ (36 villes) ; enregistrés chez l'utilisateur."""
        import gui
        monkeypatch.setattr(gui, "_FAVORITES_FILE", str(tmp_path / "user" / "favorites.json"))
        monkeypatch.setattr(gui, "_LEGACY_FAVORITES_FILE", str(tmp_path / "absent.json"))
        favorites = window._load_favorites()
        assert len(favorites) == 36 and "Paris" in favorites
        window.favorites = {"Ici": {"lat": 1.0, "lon": 2.0, "elev": 0}}
        window._save_favorites()
        assert json.loads((tmp_path / "user" / "favorites.json").read_text(encoding="utf-8")) == \
            window.favorites


class TestEclipseMap:
    def test_map_of_a_solar_eclipse(self, window, qapp):
        """Le bouton « Carte » d'une éclipse ouvre sa projection au sol."""
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
# Liens : site, code source, café, demandes sur GitHub (issue #22)
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
        """Chaque lien vers GitHub a son formulaire dans .github/ISSUE_TEMPLATE."""
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for template in ("bug", "feature", "body"):
            assert os.path.isfile(os.path.join(root, ".github", "ISSUE_TEMPLATE", f"{template}.yml"))



# ──────────────────────────────────────────────────────────────────────
# Fenêtre de données d'un astre (issue #23)
# ──────────────────────────────────────────────────────────────────────

class TestDataWindow:
    def _rows(self, dlg):
        labels = [lbl.text() for lbl in dlg.findChildren(QLabel)]
        return labels

    def test_click_on_a_planet(self, window, qapp):
        """Un clic sur Jupiter dans l'onglet Planètes ouvre sa fenêtre de données."""
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
        """Soleil et Vesta depuis l'onglet Coordonnées ; la Terre n'a pas de fiche."""
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
        """Fenêtres de données et cartes fermées ne restent pas en mémoire, sous la fenêtre."""
        for name in ("Jupiter", "Vesta", "sun"):
            window._show_body_detail(name)
            qapp.processEvents()
            window._detail_dialog.reject()
        qapp.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        assert window.findChildren(QDialog) == []



# ──────────────────────────────────────────────────────────────────────
# Premier lancement : téléchargement de l'éphéméride
# ──────────────────────────────────────────────────────────────────────

def tmp_user(engine):
    return os.path.dirname(engine.user_ephemeris_path())


class TestFirstLaunch:
    @pytest.fixture
    def missing(self, qapp, tmp_path, monkeypatch):
        """Pas d'éphéméride : main.ensure_ephemeris() la télécharge (ici, sans réseau)."""
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
        assert loaded == [] and errors == []               # pas de message : on a choisi d'annuler

    def test_no_network(self, missing, monkeypatch):
        engine, main, loaded, errors = missing

        def download(**_kw):
            raise engine.EphemerisUnavailable("pas de réseau")
        monkeypatch.setattr(engine, "download_ephemeris", download)
        assert main.ensure_ephemeris() is False
        assert loaded == [] and len(errors) == 1
        assert "pas de réseau" in errors[0] and str(tmp_user(engine)) in errors[0]


# ──────────────────────────────────────────────────────────────────────
# Mises à jour (Paramètres › À propos)
# ──────────────────────────────────────────────────────────────────────

class TestUpdates:
    RELEASE = {"version": "99.0", "tag": "v99.0", "notes": "Nouveautés",
               "page": "https://github.com/astraeos-dev/Celeste_App/releases/tag/v99.0",
               "setup_url": "https://example.test/Celeste-99.0-Setup.exe",
               "setup_name": "Celeste-99.0-Setup.exe", "setup_size": 10, "sha256_url": "x"}

    @pytest.fixture
    def offline(self, monkeypatch):
        """Tâches de fond exécutées tout de suite ; Release simulée."""
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
        """La note de la Release (CHANGELOG.md) s'affiche sans balises Markdown."""
        offline["release"] = dict(self.RELEASE, notes="- Étoiles **filantes**\n  dans `Évènements`")
        window.check_updates()
        box = window._update_dialog
        assert box.informativeText().startswith("• Étoiles filantes dans Évènements")
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
        window.check_updates(interactive=False)                  # au démarrage : silence
        assert window._update_dialog is None
        assert "99.0" in window._update_info.text()

    def test_error_is_reported(self, window, offline, monkeypatch):
        import gui

        def fail():
            raise gui.updater.UpdateError("pas de réseau")
        monkeypatch.setattr(gui.updater, "latest_release", fail)
        window.check_updates(interactive=False)
        assert "pas de réseau" in window._update_info.text()
