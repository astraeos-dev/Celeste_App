"""
scripts/add_font_symbols.py — Adds symbols to the Astraeos Symboles font
=========================================================================
Astraeos Symboles (fonts/AstraeosSymboles-Regular.ttf) is a subset of Noto
Sans Symbols, Symbols 2 and Math. This script copies into it, unchanged, the
glyphs of Noto Sans Symbols 2 (SIL OFL 1.1 licence, like Astraeos Symboles)
of the dwarf planets it lacked:

    U+2BF1 ⯱ Eris (form two)     U+2BF2 ⯲ Sedna
    U+1F77B 🝻 Haumea            U+1F77C 🝼 Makemake

Usage:
    python scripts/add_font_symbols.py path/NotoSansSymbols2-Regular.ttf

(NotoSansSymbols2-Regular.ttf, version 2.008: repository
notofonts/notofonts.github.io, fonts/NotoSansSymbols2/hinted/ttf/.)
"""
import copy
import os
import sys

from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._c_m_a_p import CmapSubtable

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(ROOT, "fonts", "AstraeosSymboles-Regular.ttf")
SYMBOLS = (0x2BF1, 0x2BF2, 0x1F77B, 0x1F77C)


def add_symbols(source_path, target_path=TARGET, codes=SYMBOLS):
    source, target = TTFont(source_path), TTFont(target_path)
    if source["head"].unitsPerEm != target["head"].unitsPerEm:
        sys.exit("the two fonts do not share the same grid (unitsPerEm)")
    source_cmap = source.getBestCmap()
    mapping = dict(target.getBestCmap())
    glyf, hmtx = target["glyf"], target["hmtx"]
    for code in codes:
        if code in mapping:
            continue
        name = source_cmap[code]
        glyph = copy.deepcopy(source["glyf"][name])
        if glyph.isComposite():
            sys.exit(f"U+{code:04X}: composite glyph, not supported")
        glyf[name] = glyph
        hmtx[name] = source["hmtx"][name]
        mapping[code] = name
    target.setGlyphOrder(glyf.glyphOrder)
    # Unicode tables: BMP (format 4) and, for the symbols beyond U+FFFF, format 12
    bmp = {c: g for c, g in mapping.items() if c <= 0xFFFF}
    tables = []
    for platform, encoding in ((0, 3), (3, 1)):
        table = CmapSubtable.newSubtable(4)
        table.platformID, table.platEncID, table.language, table.cmap = platform, encoding, 0, dict(bmp)
        tables.append(table)
    if any(c > 0xFFFF for c in mapping):
        for platform, encoding in ((0, 4), (3, 10)):
            table = CmapSubtable.newSubtable(12)
            table.platformID, table.platEncID, table.language, table.cmap = platform, encoding, 0, dict(mapping)
            tables.append(table)
    target["cmap"].tables = tables
    target.save(target_path)
    return sorted(mapping)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    codes = add_symbols(sys.argv[1])
    print(f"{TARGET}: {len(codes)} symbols")
