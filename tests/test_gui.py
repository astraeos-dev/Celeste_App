"""
tests/test_gui.py — Tests de l'interface PyQt6 (sans écran)
============================================================
Construit la fenêtre de Céleste hors écran (QT_QPA_PLATFORM=offscreen) et
la pilote : calcul, changement de langue et de thème sans redémarrage,
favoris, recherche d'événements, info-bulles et fiches de la carte du ciel,
temps réel, export PDF.

Les préférences et les favoris sont écrits dans un dossier temporaire : le
settings.json et le favorites.json du dépôt ne sont jamais modifiés.
Les tests sont ignorés si PyQt6 (ou les bibliothèques système de Qt)
manquent.

Lancer avec :  pytest tests/test_gui.py -v
"""

import json
import os
import sys
from datetime import datetime

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

pytest.importorskip("PyQt6.QtWidgets", reason="PyQt6 ou les bibliothèques de Qt manquent")
pytest.importorskip("matplotlib")

from matplotlib.backend_bases import MouseEvent  # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog, QFrame  # noqa: E402

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
    favorites = tmp_path / "favorites.json"
    favorites.write_text(json.dumps({
        "Paris": {"lat": 48.8566, "lon": 2.3522},
        "Tokyo": {"lat": 35.6762, "lon": 139.6503},
    }), encoding="utf-8")
    monkeypatch.setattr(gui, "_FAVORITES_FILE", str(favorites))
    Config.apply_theme("mocha")
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
    win.deleteLater()
    qapp.processEvents()
    Config.apply_theme("mocha")
    switch_lang("fr")


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
        assert window.sun_labels["rise"].text() == "06:56"
        assert window._lbl_phase_name.text() == "Dernier quartier"
        assert "Cherbourg-en-Cotentin" in window._lbl_pos.text()

    def test_planet_table(self, window):
        items = window._planet_items["Saturn"]
        assert items["col_dist"].text().endswith("UA")
        assert items["col_state"].text() == "Visible"

    def test_invalid_latitude_is_flagged_without_dialog(self, window):
        before = dict(window.sun_data)
        window.entry_lat.setText("123")
        window.calculate()
        assert window.entry_lat.property("invalid") is True
        assert window.sun_data == before
        window.entry_lat.setText("49.6333")
        window.calculate()
        assert window.entry_lat.property("invalid") is False

    def test_timezone_shifts_local_times(self, window):
        window.offset_menu.setCurrentIndex(window.offset_menu.findData(2))
        assert window.sun_labels["rise"].text() == "08:56"
        assert "UTC+2" in window._sun_events_title.text()

    def test_twelve_hour_format(self, window):
        window._timefmt_combo.setCurrentIndex(window._timefmt_combo.findData("12h"))
        assert window.sun_labels["rise"].text() == "6:56 AM"

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
        assert window.tabs.tabText(0).endswith("Ephemeris")
        assert window.btn_calc.text().endswith("CALCULATE")
        assert window._edit_datetime() == DTE
        assert window.entry_lat.text() == "48.8566"
        assert prefs.get("lang") == "en"

    @pytest.mark.parametrize("lang, word", [("es", "Efemérides"), ("de", "Ephemeriden")])
    def test_every_language_builds(self, window, qapp, lang, word):
        window._lang_combo.setCurrentIndex(window._lang_combo.findData(lang))
        _pump(qapp)
        assert window.tabs.tabText(0).endswith(word)
        assert "[" not in window.sun_labels["rise"].text()

    def test_theme_switch(self, window, qapp):
        from config import Config
        window._theme_combo.setCurrentIndex(window._theme_combo.findData("latte"))
        _pump(qapp)
        assert Config.THEME == "latte"
        assert Config.BG_PANEL.lower() in qapp.styleSheet().lower()
        assert window._theme_combo.currentData() == "latte"

    def test_reset_restores_defaults(self, window, qapp, monkeypatch):
        import gui
        import settings as prefs
        from config import Config
        window._theme_combo.setCurrentIndex(window._theme_combo.findData("latte"))
        _pump(qapp)
        monkeypatch.setattr(gui, "QMessageBox", _yes_box(gui))
        window._reset_settings()
        _pump(qapp)
        assert prefs.get("theme") == "mocha" and Config.THEME == "mocha"
        assert window._edit_datetime() == DTE


# ──────────────────────────────────────────────────────────────────────
# 3. Favoris
# ──────────────────────────────────────────────────────────────────────

class TestFavorites:
    def test_apply_favorite(self, window):
        window._apply_favorite(window.combo_fav.findText("Tokyo"))
        assert window.entry_lat.text() == "35.6762"
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
            assert json.load(f)["Maison"] == {"lat": 49.6333, "lon": -1.6167}
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
        if isinstance(w, QFrame) and w.objectName() == "eventCard":
            cards.append(w)
    return cards


class TestEvents:
    def test_eclipse_search(self, window):
        window._search_eclipses_gui()
        assert _event_cards(window)
        assert QApplication.overrideCursor() is None

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
# 6. Temps réel et export PDF
# ──────────────────────────────────────────────────────────────────────

class TestLiveAndExport:
    def test_live_mode(self, window):
        window.btn_live.toggle()
        assert window.live_mode and window.dt_edit.isReadOnly()
        assert window._live_timer.isActive()
        assert window._edit_datetime() != DTE
        window.btn_live.toggle()
        assert not window.live_mode and not window._live_timer.isActive()

    def test_pdf_report(self, window, tmp_path):
        from export_pdf import build_data_from_app, generate_report_pdf
        data = build_data_from_app(window)
        assert data["location"] == "Cherbourg-en-Cotentin"
        assert data["date"] == DTE
        assert data["events"]["sun"]["rise"] == "06:56"
        path = generate_report_pdf(data, str(tmp_path / "report.pdf"))
        with open(path, "rb") as f:
            assert f.read(5) == b"%PDF-"
