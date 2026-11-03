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
from PyQt6.QtWidgets import (  # noqa: E402
    QAbstractButton, QApplication, QDialog, QFrame, QLabel,
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
    win.deleteLater()
    qapp.processEvents()
    Config.apply_theme("nuit")
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
        assert window.sun_labels["rise"].text() == "06:55"
        assert window._lbl_phase_name.text() == "Dernier quartier"
        assert "Cherbourg-en-Cotentin" in window._lbl_pos.text()

    def test_planet_table(self, window):
        items = window._planet_items["Saturn"]
        assert items["col_dist"].text().endswith("UA")
        assert items["col_state"].text() == "Visible"

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
_ALLOWED = set("☉☽☾♀♂♃♄⊕♈★●○☌☍☄")


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
    """Service de localisation simulé : répond une position, ou une erreur."""
    def __init__(self, coord):
        from PyQt6.QtCore import QObject, pyqtSignal

        class Source(QObject):
            positionUpdated = pyqtSignal(object)
            errorOccurred = pyqtSignal(int)

            def requestUpdate(self, _timeout):
                if coord is None:
                    self.errorOccurred.emit(2)              # UpdateTimeoutError
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


# ──────────────────────────────────────────────────────────────────────
# Onglet Coordonnées et format des angles
# ──────────────────────────────────────────────────────────────────────

class TestCoordinatesTab:
    """Onglet Coordonnées : x, y, z et angles en même temps."""

    BODIES = ["Soleil", "Lune", "Mercure", "Vénus", "Terre", "Mars", "Jupiter", "Saturne",
              "Uranus", "Neptune", "Pluton"]

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
            "Astre", "x (UA)", "y (UA)", "z (UA)", "Distance (UA)", "Mag.",
            "Angle Soleil", "Const.", "Ascension droite α", "Déclinaison δ"]
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

