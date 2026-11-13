"""
tests/test_touch.py — Céleste with a finger (ui/touch.py; the 5.0 alpha on a phone)

The owner's report on the alpha: no scrolling, a window that blocks the app,
no touch navigation or zoom, windows wider than the screen. Touch mode is
forced here with CELESTE_TOUCH=1.
"""
import json
import os
import sys
from datetime import datetime

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from qt.QtCore import QEvent, Qt  # noqa: E402
from qt.QtGui import QKeyEvent  # noqa: E402
from qt.QtWidgets import QAbstractScrollArea, QApplication, QMessageBox, QScrollArea, QScroller  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    import gui
    gui.init_style(app)
    return app


@pytest.fixture
def phone(qapp, tmp_path, monkeypatch):
    """The window at a phone's width, touch mode on; the filter taken off afterwards."""
    import gui
    import settings as prefs
    from config import Config
    from i18n import switch_lang
    from ui import touch
    monkeypatch.setenv("CELESTE_TOUCH", "1")
    monkeypatch.setattr(prefs, "_SETTINGS_FILE", str(tmp_path / "settings.json"))
    monkeypatch.setattr(prefs, "USER_DIR", str(tmp_path))
    prefs.reset()
    prefs.set("default_tz", "UTC")
    favorites = tmp_path / "favorites.json"
    favorites.write_text(json.dumps({"Paris": {"lat": 48.8566, "lon": 2.3522}}), encoding="utf-8")
    monkeypatch.setattr(gui.common, "_FAVORITES_FILE", str(favorites))
    import history
    monkeypatch.setattr(history, "FILE", str(tmp_path / "history.json"))
    monkeypatch.setattr(gui.OsmMap, "fetch", False)
    Config.apply_theme("nuit")
    switch_lang("fr")
    gui.apply_theme(qapp)
    win = gui.AstroApp()
    win.resize(360, 740)
    support = touch.install(qapp, win)
    win.show()
    win._set_datetime(datetime(2026, 11, 12, 20, 0))
    win.calculate()
    _pump(qapp)
    yield win, support
    qapp.removeEventFilter(support)
    for widget in QApplication.topLevelWidgets():
        if widget is not win and widget.isVisible():
            widget.close()
    win.close()
    win.deleteLater()
    qapp.processEvents()


def _pump(qapp, n=8):
    for _ in range(n):
        qapp.processEvents()


def test_touch_mode(monkeypatch):
    from ui import touch
    monkeypatch.delenv("CELESTE_TOUCH", raising=False)
    assert not touch.touch_mode()                                    # a desktop
    monkeypatch.setenv("CELESTE_TOUCH", "1")
    assert touch.touch_mode()


def test_the_window_fits_the_phone(phone):
    win, support = phone
    assert support is not None and win.is_compact()
    assert win.minimumSizeHint().width() <= 360


def test_pages_and_lists_scroll_with_the_finger(phone, qapp):
    win, _support = phone
    shown = [a for a in win.findChildren(QAbstractScrollArea) if a.isVisible()]
    assert shown and all(QScroller.hasScroller(a.viewport()) for a in shown)
    win.show_page(win._journal_page)                                 # a page shown later: its table too
    _pump(qapp)
    assert QScroller.hasScroller(win._journal_table.viewport())


def test_a_window_fills_the_screen_and_scrolls(phone, qapp):
    win, _support = phone
    dlg = win._journal_open(target="M31")
    _pump(qapp)
    screen = dlg.screen().availableGeometry()
    assert dlg.property("touchFitted") and dlg.size() == screen.size()     # (the test screen adds a frame offset)
    area = dlg.findChild(QScrollArea, "dialogScroll")
    assert area is not None and QScroller.hasScroller(area.viewport())
    assert dlg.minimumWidth() < 360 and dlg.fields["target"].text() == "M31"     # was 460: wider than a phone
    dlg.save()                                                       # the form still works
    assert not dlg.isVisible() and win._journal_table.rowCount() == 1


def test_back_closes_the_window_then_the_drawer(phone, qapp):
    win, _support = phone
    dlg = win._month_sheet_dialog()
    _pump(qapp)
    QApplication.sendEvent(dlg, QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Back, Qt.KeyboardModifier.NoModifier))
    _pump(qapp)
    assert not dlg.isVisible()
    win.set_drawer(True)
    QApplication.sendEvent(win, QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Back, Qt.KeyboardModifier.NoModifier))
    assert not win._drawer_open


def test_a_tap_on_the_map_opens_the_card_without_blocking(phone, qapp):
    """The body's card opens over the window (no nested loop in the tap), fits the screen, Back closes it."""
    win, _support = phone
    win.show_page(win._sky_page)
    _pump(qapp)
    obj = next(o for o in win._sky_objects if o["kind"] == "star")
    dlg = win._show_object_detail(obj)                    # returns at once: it used to wait in exec()
    _pump(qapp)
    assert dlg.isVisible() and dlg.property("touchFitted")
    closed = []
    dlg.finished.connect(closed.append)                   # the card deletes itself once closed
    QApplication.sendEvent(dlg, QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Back, Qt.KeyboardModifier.NoModifier))
    assert closed == [0]                                  # rejected by Back


def test_qt_message_boxes_keep_their_size(phone, qapp):
    win, _support = phone
    box = QMessageBox(QMessageBox.Icon.Information, "Céleste", "Bonjour", parent=win)
    box.open()
    _pump(qapp)
    assert not box.property("touchFitted") and box.findChild(QScrollArea, "dialogScroll") is None
    box.close()


def _visible_dialogs():
    from qt.QtWidgets import QDialog
    return [w for w in QApplication.topLevelWidgets() if isinstance(w, QDialog) and w.isVisible()]


def test_the_sky_map_by_touch(phone, qapp):
    """Two fingers zoom (lifting them is no tap), one finger moves the zoomed map, a tap opens a card."""
    win, _support = phone
    win.show_page(win._sky_page)
    _pump(qapp)
    win.canvas_sky.draw()
    fingers = win._sky_touch
    cx, cy = win.canvas_sky.width() / 2, win.canvas_sky.height() / 2     # the middle of the map
    fingers.handle("press", [(cx - 50, cy)])
    fingers.handle("move", [(cx - 50, cy), (cx + 50, cy)])           # the second finger
    fingers.handle("move", [(cx - 100, cy), (cx + 100, cy)])         # spread 100 → 200 px
    assert win._sky_zoom == pytest.approx(2.0)
    fingers.handle("move", [(cx - 80, cy)])                          # one finger left
    fingers.handle("release", [(cx - 80, cy)])
    assert not _visible_dialogs()
    center = win._sky_center
    for kind, dx in (("press", -30), ("move", 0), ("move", 40), ("release", 40)):
        fingers.handle(kind, [(cx + dx, cy)])
    assert win._sky_center[0] < center[0]                            # dragged right: the view moved left
    win._sky_reset_view()
    win.canvas_sky.draw()
    canvas, ax = win.canvas_sky, win._sky_ax
    star = min((o for o in win._sky_objects if o["kind"] == "star"), key=lambda o: o["mag"])
    dx, dy = ax.transData.transform((star["x"], star["y"]))
    ratio = canvas.device_pixel_ratio
    tap = (dx / ratio, canvas.figure.bbox.height / ratio - dy / ratio)
    fingers.handle("press", [tap])
    fingers.handle("release", [tap])
    cards = _visible_dialogs()
    assert len(cards) == 1 and star["name"] in cards[0].windowTitle()
    cards[0].reject()


def test_the_android_line(phone, qapp, capsys):
    """What the emulator check reads: the window and a form fit the screen."""
    import main
    win, _support = phone
    main.report_android(win)
    line = capsys.readouterr().out
    assert "android window OK" in line and "touch True" in line
    assert "fits True" in line and "dialog fits True" in line and "fits False" not in line
