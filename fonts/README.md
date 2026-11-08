# Fonts

The fonts of the Astræos design system, shipped with Céleste so that the interface
looks the same on every machine. `gui.py` registers them at startup
(`QFontDatabase.addApplicationFont`) and `charts.py` gives them to matplotlib.

| File | Family | Role |
|---|---|---|
| `IBMPlexSans-Regular.ttf` | IBM Plex Sans 400 | Body text (`corps`, `legende`) |
| `IBMPlexSans-SemiBold.ttf` | IBM Plex Sans 600 | Titles, buttons, tabs, field labels |
| `IBMPlexMono-Medium.ttf` | IBM Plex Mono 500 | Data (`donnee`, `cadran`): fixed-width figures |
| `AstraeosSymboles-Regular.ttf` | Astraeos Symboles | Astronomical symbols (☉ ☽ ♀ ♂ ♃ ♄ ☌ ☍ ♈ …), after Plex in each stack |

## Origin and licences

- **IBM Plex Sans and IBM Plex Mono**: TTF files of the
  [IBM/plex](https://github.com/IBM/plex) repository (`packages/plex-sans` and `packages/plex-mono`,
  `fonts/complete/ttf/`), unmodified. SIL Open Font License 1.1, reserved font name
  "Plex": see `OFL-IBM-Plex.txt`.
- **Astraeos Symboles**: font of the Astræos design system, a subset of Noto Sans
  Symbols, Symbols 2 and Math (34 symbols). WOFF2 file of the design system converted to TTF
  without changing the glyphs; the symbols of Eris (U+2BF1), Sedna (U+2BF2), Haumea
  (U+1F77B) and Makemake (U+1F77C) are copied into it, as they are, from Noto Sans Symbols 2
  (version 2.008) by `scripts/add_font_symbols.py`. SIL Open Font License 1.1: see
  `OFL-Astraeos-Symboles.txt`.
