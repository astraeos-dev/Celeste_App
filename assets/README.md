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

`constellation_bounds.json`: the official boundaries of the 88 constellations (E. Delporte for the IAU, 1930, brought
to J2000 and cut into lines of right ascension and declination), taken by `scripts/make_constellations.py --bounds`
from d3-celestial's `data/constellations.bounds.json` (same author, same licence): for each constellation its
outlines (two for Serpens), as right ascensions in hours and declinations in degrees. The constellation charts of Sky
draw them.

## World Magnetic Model

`wmm2025.cof`: the coefficients of the **World Magnetic Model 2025** (WMM2025, valid 2025.0–2030.0), the file
`WMM2025.COF` of `WMM2025COF.zip` as NOAA's National Centers for Environmental Information publish it
(ncei.noaa.gov/products/world-magnetic-model), unchanged. A work of the US government with the British Geological
Survey, in the public domain. `geomag.py` computes from it the magnetic declination of the place, by which the sky
map that follows the phone turns the compass to the true north; `tests/data/wmm2025_test_values.txt` is the model's
own file of test values from the same archive.

## Deep-sky catalogue of the night planner

`deep_sky.csv.gz`: every object of **OpenNGC** that is not a star (12,822: NGC, IC and OpenNGC's addendum), with
its type, J2000 position, constellation, magnitude, size, Messier and Caldwell numbers and English common name,
extracted by `scripts/make_deep_sky.py` at the same fixed commit as `messier.csv`. © Mattia Verga, licence
[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/); this file is shared under the same licence.

The comets of the Minor Planet Center are not shipped: `mpc.py` downloads their elements (`CometEls.txt`) when the
user asks for them, and keeps them a week in `~/.celeste`.
