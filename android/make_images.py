"""
android/make_images.py — The pictures of the Android build
==========================================================
Draws, from Céleste's SVG files (assets/, scripts/make_logo.py), into the
folder given:
- icon.png: the launcher icon, Céleste's symbol on its Nuit tile (512 px);
- logo.png: the symbol alone in the Nuit theme's colours, for the window.

Run by the Android workflow with the desktop PySide6, before
pyside6-android-deploy: python android/make_images.py <project folder>
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QByteArray, QRectF, Qt  # noqa: E402
from PySide6.QtGui import QGuiApplication, QImage, QPainter  # noqa: E402
from PySide6.QtSvg import QSvgRenderer  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def render(svg_text, width, height, path):
    image = QImage(width, height, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    QSvgRenderer(QByteArray(svg_text.encode("utf-8"))).render(painter, QRectF(0, 0, width, height))
    painter.end()
    if not image.save(path):
        sys.exit(f"cannot write {path}")
    print("written", path, f"{width}x{height}")


def main(out):
    app = QGuiApplication.instance() or QGuiApplication([])  # noqa: F841 (needed to paint)
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(ROOT, "assets", "celeste-icone.svg"), encoding="utf-8") as f:
        render(f.read(), 512, 512, os.path.join(out, "icon.png"))
    import icons
    from config import Config
    Config.apply_theme("nuit")
    with open(os.path.join(ROOT, "assets", "celeste-symbole.svg"), encoding="utf-8") as f:
        svg = f.read().replace(icons._FILE_ENCRE, Config.ENCRE).replace(icons._FILE_OR, Config.OR)
    box = QSvgRenderer(QByteArray(svg.encode("utf-8"))).viewBoxF()
    height = 192
    render(svg, round(height * box.width() / box.height()), height, os.path.join(out, "logo.png"))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "build", "android"))
