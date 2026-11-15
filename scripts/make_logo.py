"""
scripts/make_logo.py — Céleste's logo, from its geometry
========================================================
The C of Céleste, open like an orbit, and its gold dot: a thick arc in the
Astræos design system's ink, opened on the right, where a dot shines in its
gold, as on the logos of the other Astraeos projects. Like the design system's
symbols, the letter and the dot keep their colours (the interface puts the
active theme's encre and or in place of #e8ecf2 and #f2b84b) and are never
given a shadow, an outline, a gradient or a distortion.

Writes assets/celeste-icone.svg (the symbol on its Nuit tile: the window,
the taskbar, the installer, the Android launcher) and
assets/celeste-symbole.svg (the symbol alone: the header).

Run: python scripts/make_logo.py
"""
import math
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INK, GOLD, NIGHT = "#e8ecf2", "#f2b84b", "#0b0f17"

# the C: an arc around (CX, CY), RHO its middle radius, STROKE thick, open
# OPEN degrees above and below the right-hand side, its ends rounded
CX, CY, RHO, STROKE, OPEN = 46.0, 53.0, 25.0, 9.0, 42.0
# the dot: a disc of radius DOT, its middle GAP to the right of the arc's
# middle line, in the opening of the C
DOT, GAP = 7.0, 3.0
# the tile: the symbol moved to its middle; the symbol alone: its box
TILE_SHIFT = (1.25, -3.0)
SYMBOL_BOX = (14.5, 21.5, 69.0, 63.0)


def _n(value):
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _at(angle_deg, radius=RHO, cx=CX, cy=CY):
    a = math.radians(angle_deg)
    return cx + radius * math.cos(a), cy + radius * math.sin(a)


def mark():
    """The symbol's SVG elements (y downwards)."""
    top, bottom = _at(-OPEN), _at(OPEN)
    arc = (f'<path fill="none" stroke="{INK}" stroke-width="{_n(STROKE)}" stroke-linecap="round" '
           f'd="M{_n(top[0])} {_n(top[1])} A{_n(RHO)} {_n(RHO)} 0 1 0 {_n(bottom[0])} {_n(bottom[1])}"/>')
    dot = f'<circle cx="{_n(CX + RHO + GAP)}" cy="{_n(CY)}" r="{_n(DOT)}" fill="{GOLD}"/>'
    return arc + dot


def tile_svg():
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" role="img" aria-label="Céleste">'
            f'<title>Céleste</title><rect width="100" height="100" rx="22" fill="{NIGHT}"/>'
            f'<g transform="translate({_n(TILE_SHIFT[0])} {_n(TILE_SHIFT[1])})">{mark()}</g></svg>\n')


def symbol_svg():
    box = " ".join(_n(v) for v in SYMBOL_BOX)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{box}" role="img" aria-label="Céleste">'
            f'<title>Céleste</title>{mark()}</svg>\n')


def main():
    for name, text in (("celeste-icone.svg", tile_svg()), ("celeste-symbole.svg", symbol_svg())):
        path = os.path.join(ROOT, "assets", name)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        print("written", path)


if __name__ == "__main__":
    main()
