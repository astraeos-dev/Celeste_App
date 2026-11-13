# Assets of the interface

## Céleste's logo

The C of Céleste, open like an orbit, and its star, drawn for Céleste in the language of the Astræos design system
(the letter in its ink, the star in its gold) by `scripts/make_logo.py`, which writes:

| File | Use in Céleste |
|---|---|
| `celeste-icone.svg` | Icon of the window, the taskbar, the installer (`scripts/build_exe.py`) and the Android launcher (`android/make_images.py`) |
| `celeste-symbole.svg` | Symbol of the header; `icons.py` replaces, when drawing it, the ink `#e8ecf2` and the star `#f2b84b` with the `encre` and `or` colours of the active theme |

Rules of the design system: the star stays `or` and in its place, never a shadow, outline, gradient or distortion;
the symbol is at least 20 px high.

## Icons

The action icons come from [Material Design Icons](https://pictogrammers.com/library/mdi/) (package `@mdi/js`
7.4.47), copied into `icons.py`. Licence: Pictogrammers Free License, icons under the Apache 2.0 licence — see
`LICENSE-MDI.txt`.

## World map background

`world_land.json`: land outlines of **Natural Earth** at 1:110,000,000 (naturalearthdata.com, public domain), reduced
to their outer ring and two decimals; background of the map of eclipses projected on the ground (`charts.py`).

## Cities

`cities.tsv.gz`: the 34,205 cities of more than 15,000 inhabitants of **GeoNames** (`cities15000`, www.geonames.org,
licence [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)), reduced by `scripts/make_cities.py`: name, other
names in Latin script (cities of more than 100,000 inhabitants), country, region, coordinates, elevation, population.
They serve the search for a place by its name (`places.py`) and name a point without a network.

## Comets

`comets.npz`: heliocentric positions and velocities (ICRF, AU, TDB) of the comets followed, every 2 days from 2025 to
2031, and their magnitude parameters M1, K1; taken from **JPL Horizons** and the Small-Body Database by
`scripts/make_comets.py`. See the wiki page "Ajouter une comète".

## Messier catalogue

`messier.csv`: the 110 Messier objects (type, J2000 coordinates, visual magnitude, apparent size, English common
name), extracted by `scripts/make_messier.py` from **OpenNGC** (github.com/mattiaverga/OpenNGC, fixed commit),
© Mattia Verga, licence [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). This file is shared under
the same licence. Seven magnitudes OpenNGC lacks (M22, M35, M62, M69, M70, M71, M107) come from the SEDS Messier
database (messier.seds.org); M102 is taken to be NGC 5866.

## Constellation figures

`constellations.json`: the lines of the 88 constellations and the point where each is named (J2000), taken by
`scripts/make_constellations.py` from **d3-celestial** (github.com/ofrohn/d3-celestial, files
`data/constellations.lines.json` and `data/constellations.json`), © 2015 Olaf Frohn, BSD 3-Clause licence: see
`LICENSE-d3-celestial.txt`. The French, Spanish and German names of the constellations in `locales/` come from the
same files; the English interface uses the Latin names of the IAU.

## Deep-sky catalogue of the night planner

`deep_sky.csv.gz`: every object of **OpenNGC** that is not a star (12,822: NGC, IC and OpenNGC's addendum), with
its type, J2000 position, constellation, magnitude, size, Messier and Caldwell numbers and English common name,
extracted by `scripts/make_deep_sky.py` at the same fixed commit as `messier.csv`. © Mattia Verga, licence
[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/); this file is shared under the same licence.

The comets of the Minor Planet Center are not shipped: `mpc.py` downloads their elements (`CometEls.txt`) when the
user asks for them, and keeps them a week in `~/.celeste`.
