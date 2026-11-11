# Assets of the interface

## Astræos logo

SVG files of the Logos group of the Astræos design system, copied unchanged:

| File | Use in Céleste |
|---|---|
| `astraeos-icone.svg` | Icon of the window and the taskbar |
| `astraeos-symbole-nuit.svg` | Symbol of the header; `icons.py` replaces, when drawing it, the ink `#e8ecf2` and the star `#f2b84b` with the `encre` and `or` colours of the active theme |

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
