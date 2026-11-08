"""
icons.py — Icons and brand marks of the Céleste interface
=========================================================
The Astræos design system uses no emoji in an interface: actions get line
icons from Material Design Icons, drawn in encre-attenuee by default and in
an accent color only when the icon carries the meaning. The Astræos symbol
and the application icon come from the design system's SVG files in assets/.

Material Design Icons (Pictogrammers, package @mdi/js 7.4.47): the path data
below is copied unchanged. Pictogrammers Free License, icons under the
Apache License 2.0: see assets/LICENSE-MDI.txt.
"""

import os

from PyQt6.QtCore import QByteArray, QRectF, Qt
from PyQt6.QtGui import QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer

_ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

# Colors of the "Nuit" files of the design system, replaced by the active theme's
_FILE_ENCRE = "#e8ecf2"
_FILE_OR = "#f2b84b"

# Material Design Icons, 24 × 24 viewBox
MDI = {
    "calculate": (  # mdi-calculator-variant-outline
        "M19 3H5C3.9 3 3 3.9 3 5V19C3 20.1 3.9 21 5 21H19C20.1 21 21 20.1 21 19V5C21 3.9 20.1 3 19 3M19 19H5V5H19V19M6.2 7.7H11.2V9.2H6.2V7.7M13 15.8H18V17.3H13V15.8M13 13.2H18V14.7H13V13.2M8 18H9.5V16H11.5V14.5H9.5V12.5H8V14.5H6V16H8V18M14.1 10.9L15.5 9.5L16.9 10.9L18 9.9L16.6 8.5L18 7.1L16.9 6L15.5 7.4L14.1 6L13 7.1L14.4 8.5L13 9.9L14.1 10.9Z"),
    "live": (  # mdi-play-circle-outline
        "M12,20C7.59,20 4,16.41 4,12C4,7.59 7.59,4 12,4C16.41,4 20,7.59 20,12C20,16.41 16.41,20 12,20M12,2A10,10 0 0,0 2,12A10,10 0 0,0 12,22A10,10 0 0,0 22,12A10,10 0 0,0 12,2M10,16.5L16,12L10,7.5V16.5Z"),
    "export": (  # mdi-tray-arrow-down
        "M2 12H4V17H20V12H22V17C22 18.11 21.11 19 20 19H4C2.9 19 2 18.11 2 17V12M12 15L17.55 9.54L16.13 8.13L13 11.25V2H11V11.25L7.88 8.13L6.46 9.55L12 15Z"),
    "now": (  # mdi-update
        "M21,10.12H14.22L16.96,7.3C14.23,4.6 9.81,4.5 7.08,7.2C4.35,9.91 4.35,14.28 7.08,17C9.81,19.7 14.23,19.7 16.96,17C18.32,15.65 19,14.08 19,12.1H21C21,14.08 20.12,16.65 18.36,18.39C14.85,21.87 9.15,21.87 5.64,18.39C2.14,14.92 2.11,9.28 5.62,5.81C9.13,2.34 14.76,2.34 18.27,5.81L21,3V10.12M12.5,8V12.25L16,14.33L15.28,15.54L11,13V8H12.5Z"),
    "geolocate": (  # mdi-crosshairs-gps
        "M12,8A4,4 0 0,1 16,12A4,4 0 0,1 12,16A4,4 0 0,1 8,12A4,4 0 0,1 12,8M3.05,13H1V11H3.05C3.5,6.83 6.83,3.5 11,3.05V1H13V3.05C17.17,3.5 20.5,6.83 20.95,11H23V13H20.95C20.5,17.17 17.17,20.5 13,20.95V23H11V20.95C6.83,20.5 3.5,17.17 3.05,13M12,5A7,7 0 0,0 5,12A7,7 0 0,0 12,19A7,7 0 0,0 19,12A7,7 0 0,0 12,5Z"),
    "favorite_add": (  # mdi-star-plus-outline
        "M5.8 21L7.4 14L2 9.2L9.2 8.6L12 2L14.8 8.6L22 9.2L18.8 12H18C17.3 12 16.6 12.1 15.9 12.4L18.1 10.5L13.7 10.1L12 6.1L10.3 10.1L5.9 10.5L9.2 13.4L8.2 17.7L12 15.4L12.5 15.7C12.3 16.2 12.1 16.8 12.1 17.3L5.8 21M17 14V17H14V19H17V22H19V19H22V17H19V14H17Z"),
    "delete": (  # mdi-delete-outline
        "M6,19A2,2 0 0,0 8,21H16A2,2 0 0,0 18,19V7H6V19M8,9H16V19H8V9M15.5,4L14.5,3H9.5L8.5,4H5V6H19V4H15.5Z"),
    "search": (  # mdi-magnify
        "M9.5,3A6.5,6.5 0 0,1 16,9.5C16,11.11 15.41,12.59 14.44,13.73L14.71,14H15.5L20.5,19L19,20.5L14,15.5V14.71L13.73,14.44C12.59,15.41 11.11,16 9.5,16A6.5,6.5 0 0,1 3,9.5A6.5,6.5 0 0,1 9.5,3M9.5,5C7,5 5,7 5,9.5C5,12 7,14 9.5,14C12,14 14,12 14,9.5C14,7 12,5 9.5,5Z"),
    "reset": (  # mdi-restore
        "M13,3A9,9 0 0,0 4,12H1L4.89,15.89L4.96,16.03L9,12H6A7,7 0 0,1 13,5A7,7 0 0,1 20,12A7,7 0 0,1 13,19C11.07,19 9.32,18.21 8.06,16.94L6.64,18.36C8.27,20 10.5,21 13,21A9,9 0 0,0 22,12A9,9 0 0,0 13,3Z"),
    "place": (  # mdi-map-marker-outline
        "M12,6.5A2.5,2.5 0 0,1 14.5,9A2.5,2.5 0 0,1 12,11.5A2.5,2.5 0 0,1 9.5,9A2.5,2.5 0 0,1 12,6.5M12,2A7,7 0 0,1 19,9C19,14.25 12,22 12,22C12,22 5,14.25 5,9A7,7 0 0,1 12,2M12,4A5,5 0 0,0 7,9C7,10 7,12 12,18.71C17,12 17,10 17,9A5,5 0 0,0 12,4Z"),
    "calendar": (  # mdi-calendar-month-outline
        "M7 11H9V13H7V11M21 5V19C21 20.11 20.11 21 19 21H5C3.89 21 3 20.1 3 19V5C3 3.9 3.9 3 5 3H6V1H8V3H16V1H18V3H19C20.11 3 21 3.9 21 5M5 7H19V5H5V7M19 19V9H5V19H19M15 13V11H17V13H15M11 13V11H13V13H11M7 15H9V17H7V15M15 17V15H17V17H15M11 17V15H13V17H11Z"),
    "previous": (  # mdi-chevron-left
        "M15.41,16.58L10.83,12L15.41,7.41L14,6L8,12L14,18L15.41,16.58Z"),
    "next": (  # mdi-chevron-right
        "M8.59,16.58L13.17,12L8.59,7.41L10,6L16,12L10,18L8.59,16.58Z"),
    "play": (  # mdi-play
        "M8,5.14V19.14L19,12.14L8,5.14Z"),
    "pause": (  # mdi-pause
        "M14,19H18V5H14M6,19H10V5H6V19Z"),
    "step_back": (  # mdi-step-backward
        "M19,5V19H16V5M14,5V19L3,12"),
    "step_forward": (  # mdi-step-forward
        "M5,5V19H8V5M10,5V19L21,12"),
    "theme_nuit": (  # mdi-weather-night
        "M17.75,4.09L15.22,6.03L16.13,9.09L13.5,7.28L10.87,9.09L11.78,6.03L9.25,4.09L12.44,4L13.5,1L14.56,4L17.75,4.09M21.25,11L19.61,12.25L20.2,14.23L18.5,13.06L16.8,14.23L17.39,12.25L15.75,11L17.81,10.95L18.5,9L19.19,10.95L21.25,11M18.97,15.95C19.8,15.87 20.69,17.05 20.16,17.8C19.84,18.25 19.5,18.67 19.08,19.07C15.17,23 8.84,23 4.94,19.07C1.03,15.17 1.03,8.83 4.94,4.93C5.34,4.53 5.76,4.17 6.21,3.85C6.96,3.32 8.14,4.21 8.06,5.04C7.79,7.9 8.75,10.87 10.95,13.06C13.14,15.26 16.1,16.22 18.97,15.95M17.33,17.97C14.5,17.81 11.7,16.64 9.53,14.5C7.36,12.31 6.2,9.5 6.04,6.68C3.23,9.82 3.34,14.64 6.35,17.66C9.37,20.67 14.19,20.78 17.33,17.97Z"),
    "theme_jour": (  # mdi-white-balance-sunny
        "M3.55 19.09L4.96 20.5L6.76 18.71L5.34 17.29M12 6C8.69 6 6 8.69 6 12S8.69 18 12 18 18 15.31 18 12C18 8.68 15.31 6 12 6M20 13H23V11H20M17.24 18.71L19.04 20.5L20.45 19.09L18.66 17.29M20.45 5L19.04 3.6L17.24 5.39L18.66 6.81M13 1H11V4H13M6.76 5.39L4.96 3.6L3.55 5L5.34 6.81L6.76 5.39M1 13H4V11H1M13 20H11V23H13"),
    "theme_observation": (  # mdi-eye-outline
        "M12,9A3,3 0 0,1 15,12A3,3 0 0,1 12,15A3,3 0 0,1 9,12A3,3 0 0,1 12,9M12,4.5C17,4.5 21.27,7.61 23,12C21.27,16.39 17,19.5 12,19.5C7,19.5 2.73,16.39 1,12C2.73,7.61 7,4.5 12,4.5M3.18,12C4.83,15.36 8.24,17.5 12,17.5C15.76,17.5 19.17,15.36 20.82,12C19.17,8.64 15.76,6.5 12,6.5C8.24,6.5 4.83,8.64 3.18,12Z"),
}


def _render(svg, width, height, ratio=2.0):
    """Pixmap of an SVG document, drawn at *ratio* × its size for sharp edges."""
    pix = QPixmap(round(width * ratio), round(height * ratio))
    pix.fill(Qt.GlobalColor.transparent)
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter, QRectF(0, 0, pix.width(), pix.height()))
    painter.end()
    pix.setDevicePixelRatio(ratio)
    return pix


def mdi_svg(name, color):
    """SVG document of a Material Design icon filled with *color*."""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
            f'<path fill="{color}" d="{MDI[name]}"/></svg>')


def icon(name, color, size=20, checked_color=None, disabled_color=None):
    """
    QIcon of a Material Design icon.

    Args:
        name (str): Key of MDI.
        color (str): Hex color of the icon.
        size (int): Size in device-independent pixels (20, or 16 when compact).
        checked_color (str): Color when a toggle button is on (aplat encre:
            the icon takes ciel-000).
        disabled_color (str): Color when the button is disabled.
    """
    result = QIcon()
    result.addPixmap(_render(mdi_svg(name, color), size, size),
                     QIcon.Mode.Normal, QIcon.State.Off)
    if checked_color:
        result.addPixmap(_render(mdi_svg(name, checked_color), size, size),
                         QIcon.Mode.Normal, QIcon.State.On)
    if disabled_color:
        result.addPixmap(_render(mdi_svg(name, disabled_color), size, size),
                         QIcon.Mode.Disabled, QIcon.State.Off)
    return result


def _asset(name):
    with open(os.path.join(_ASSETS, name), encoding="utf-8") as f:
        return f.read()


def symbol_pixmap(height, encre, star):
    """
    The Astræos symbol (the æ and its star) at *height* pixels, ink in
    *encre* and star in *star* (the theme's encre and or).
    """
    svg = _asset("astraeos-symbole-nuit.svg").replace(_FILE_ENCRE, encre).replace(_FILE_OR, star)
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    box = renderer.viewBoxF()
    return _render(svg, height * box.width() / box.height(), height)


def app_icon():
    """Application icon: the Astræos symbol on its Nuit tile."""
    svg = _asset("astraeos-icone.svg")
    result = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        result.addPixmap(_render(svg, size, size, ratio=1.0))
    return result
