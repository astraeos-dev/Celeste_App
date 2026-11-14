"""
ui/touch.py — Céleste with a finger (Android, a touch screen)
==============================================================
Qt Widgets were made for a mouse: on a phone, a page or a list does not scroll
when the finger drags it, a window wider than the screen runs off it, and the
Back key does nothing. TouchSupport, an event filter on the application (set by
main.py on Android, or with CELESTE_TOUCH=1 to try it on a desktop), makes:

- every scroll area scroll with the finger, with inertia (QScroller): pages,
  lists, tables;
- every window (QDialog) fill the screen and scroll when its content is
  taller, so that its buttons stay within reach;
- the Back key close the window on top, then the drawer;

and the sky map zoom with two fingers (ui/sky.py, pinch).
"""
import os

from qt.QtCore import QEvent, QObject, Qt
from qt.QtWidgets import (
    QAbstractScrollArea, QApplication, QColorDialog, QDialog, QFileDialog, QFrame, QMessageBox, QScrollArea,
    QScroller, QVBoxLayout, QWidget,
)

# Qt's own small windows keep their size (QFileDialog is the phone's own)
_KEEP_SIZE = (QMessageBox, QFileDialog, QColorDialog)


def touch_mode():
    """True on Android, or with CELESTE_TOUCH=1."""
    import mobile
    return mobile.is_android() or os.environ.get("CELESTE_TOUCH") == "1"


def scroll_by_finger(area):
    """The area scrolls when the finger drags it (once per area)."""
    viewport = area.viewport()
    if not QScroller.hasScroller(viewport):
        QScroller.grabGesture(viewport, QScroller.ScrollerGestureType.LeftMouseButtonGesture)


def fit_to_screen(dialog):
    """
    The window over the whole screen, its content in a scroll area: a form
    taller or wider than the phone keeps its buttons within reach. Once per
    window.
    """
    if dialog.property("touchFitted") or isinstance(dialog, _KEEP_SIZE):
        return
    dialog.setProperty("touchFitted", True)
    layout = dialog.layout()
    if layout is not None:
        content = QWidget()
        content.setObjectName("dialogContent")
        content.setLayout(layout)                    # the window's widgets move into the scroll area
        area = QScrollArea(dialog)
        area.setObjectName("dialogScroll")
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.Shape.NoFrame)
        area.setWidget(content)
        outer = QVBoxLayout(dialog)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(area)
        scroll_by_finger(area)
    dialog.setMinimumSize(0, 0)
    screen = dialog.screen() or QApplication.primaryScreen()
    if screen is not None:
        dialog.setGeometry(screen.availableGeometry())


class TouchSupport(QObject):
    """The application's event filter on a touch screen (see the module)."""

    def __init__(self, window):
        super().__init__(window)
        self.window = window

    def eventFilter(self, obj, event):
        kind = event.type()
        if kind == QEvent.Type.Show and obj.isWidgetType():
            if isinstance(obj, QAbstractScrollArea):
                scroll_by_finger(obj)
            if isinstance(obj, QDialog) and obj.isWindow():
                fit_to_screen(obj)
        elif kind == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Back:
            return self.back()
        return False

    def back(self):
        """Back: the window on top closes, then the drawer; else Android's own (leaving)."""
        top = QApplication.activeModalWidget() or QApplication.activeWindow()
        if isinstance(top, QDialog) and top is not self.window:
            top.reject()
            return True
        if getattr(self.window, "_drawer_open", False):
            self.window.set_drawer(False)
            return True
        return False


def install(app, window):
    """On a touch screen: the event filter on the application; returns it, or None."""
    if not touch_mode():
        return None
    support = TouchSupport(window)
    app.installEventFilter(support)
    for area in window.findChildren(QAbstractScrollArea):    # those already on screen
        scroll_by_finger(area)
    return support
