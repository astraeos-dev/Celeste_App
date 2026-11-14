# Céleste on the web: what is possible

The roadmap asks to look into a web version of Céleste, alongside a new Ganymède website in the Astræos design
system with a section for Céleste. This page weighs the ways to put Céleste in a browser and proposes an order.
The website lives in its own repository (astraeos-dev/Ganymede); this page only covers Céleste's side.

## What a web version can reuse

- **The engine and the computations without Qt**: `engine.py` (Skyfield, jplephem, NumPy), `planner.py`,
  `night_quality.py`, `variables.py`, `neo.py`, `occultations.py`, `transients.py`, `astro_calendar.py`,
  `month_sheet.py`, `charts.py` (matplotlib), `instruments.py` and `workshop.py`. They are pure Python with NumPy,
  and their tests already pin their results.
- **The texts** (`locales/*.json`, four languages) and **the design tokens** (`config.py`: the colours of the Nuit,
  Jour and Observation themes, the type styles), which a web page can take as CSS variables.
- **Not the interface**: `gui.py` and `ui/` are Qt widgets.

## The options

| Option | How | For | Against |
|---|---|---|---|
| Qt in the browser (Qt for WebAssembly) | The same Qt interface compiled to WebAssembly | One interface for every platform | Qt for WebAssembly is C++; PySide6 has no WebAssembly build (the request, PYSIDE-962, is open); a community build exists for PyQt6 only. Not usable today |
| Python in the browser (Pyodide) | Céleste's Qt-free modules run in the page through Pyodide; a light HTML interface in the Astræos design system | The same computations as the desktop, to the arcsecond; the tests stay valid | A first load of about 30 MB (Python, NumPy, matplotlib) plus the ephemeris (32 MB, or a 2000–2100 extract of a few MB), kept by the browser after the first visit; a new interface to write |
| A JavaScript engine (Astronomy Engine, MIT licence) | The computations redone in JavaScript, a light page | Fast, a few hundred kB | A second engine to keep in step with Céleste's, about one arcminute instead of arcseconds; minor planets, comets, occultations and the Workshop to redo |
| Pages computed in advance | Céleste's own Python writes pages (the night of the main cities, the month's sheet, the calendar) when the site is built | Nothing to load, works everywhere | Not interactive: no place or date of one's own |

## Proposed order

1. **The Ganymède website**, static (GitHub Pages), in the Astræos design system: a Céleste section with what it
   does, screenshots in the three themes, the download of the Windows installer and of the Android test version,
   the privacy table and the changelog. Nothing to compute.
2. **A first "Tonight" page in the browser** with Pyodide: the place (typed in or the browser's position, which
   stays in the page), the night's quality, the Sun, the Moon and the planets, computed by `engine.py` itself. It
   answers the question of this roadmap row: how fast it loads, how big it is, on a computer and on a phone.
3. Then, if the first page holds: the sky map (matplotlib in the page, or drawn in SVG from `charts.sky_scene`),
   the calendar, the Workshop's PDFs (made in the page, nothing sent anywhere).

What decides between the second and the third option is the weight of the first load on a phone. The Pyodide page
of step 2 measures it.

## Privacy

As in the desktop app: no account, no tracking. A web page computes in the browser, so the place does not leave
the visitor's computer; only the files (Pyodide, the ephemeris) are downloaded, from the site itself.
