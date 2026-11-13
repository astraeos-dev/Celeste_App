"""
tests/test_logo.py — Céleste's logo (scripts/make_logo.py, v4.21)

The SVG files of assets/ are the script's; they use only the design system's
ink and gold, which the interface replaces with the active theme's; the
symbol and the icon are drawn at every size, the star in the theme's gold.
"""
import importlib.util
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _script():
    spec = importlib.util.spec_from_file_location("make_logo", os.path.join(ROOT, "scripts", "make_logo.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _asset(name):
    with open(os.path.join(ROOT, "assets", name), encoding="utf-8") as f:
        return f.read()


def test_the_files_are_the_script_s():
    logo = _script()
    assert _asset("celeste-icone.svg") == logo.tile_svg()
    assert _asset("celeste-symbole.svg") == logo.symbol_svg()


def test_only_the_ink_and_the_gold():
    """The interface recolours the symbol by replacing these two colours (icons.py)."""
    import icons
    colours = set(re.findall(r"#[0-9a-f]{6}", _asset("celeste-symbole.svg")))
    assert colours == {icons._FILE_ENCRE, icons._FILE_OR}
    assert set(re.findall(r"#[0-9a-f]{6}", _asset("celeste-icone.svg"))) == colours | {"#0b0f17"}
    assert 'aria-label="Céleste"' in _asset("celeste-icone.svg")


@pytest.fixture(scope="module")
def qt():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("qt", reason="PySide6 (or PyQt6) or the Qt libraries are missing")
    from qt.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize("theme", ["nuit", "jour", "observation"])
def test_the_symbol_in_every_theme(qt, theme):
    import icons
    from config import Config
    from qt.QtGui import QColor
    Config.apply_theme(theme)
    try:
        image = icons.symbol_pixmap(64, Config.ENCRE, Config.OR).toImage()
        gold = QColor(Config.OR)
        found = {(c.red(), c.green(), c.blue()) for c in
                 (image.pixelColor(x, y) for x in range(0, image.width(), 2) for y in range(0, image.height(), 2))
                 if c.alpha() == 255}
        assert (gold.red(), gold.green(), gold.blue()) in found               # the star, in the theme's gold
        ink = QColor(Config.ENCRE)
        assert (ink.red(), ink.green(), ink.blue()) in found                  # the letter, in its ink
        box = _script().SYMBOL_BOX                                            # drawn without distortion
        assert image.height() >= 64 and image.width() / image.height() == pytest.approx(box[2] / box[3], rel=0.03)
    finally:
        Config.apply_theme("nuit")


def test_the_icon_at_every_size(qt):
    import icons
    icon = icons.app_icon()
    for size in icons.APP_ICON_SIZES:
        assert not icon.pixmap(size, size).isNull(), size
