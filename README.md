# ✨ Céleste — astronomical observatory

> A desktop application that computes and shows the positions of the Sun, the Moon and the planets, from the JPL DE440 ephemeris (through Skyfield).

[![Version](https://img.shields.io/github/v/release/astraeos-dev/Celeste_App?label=version&color=f2b84b)](https://github.com/astraeos-dev/Celeste_App/releases/latest)
[![Download for Windows](https://img.shields.io/badge/Download-Windows-0078D6?logo=windows)](https://github.com/astraeos-dev/Celeste_App/releases/latest)
[![CI](https://github.com/astraeos-dev/Celeste_App/actions/workflows/ci.yml/badge.svg)](https://github.com/astraeos-dev/Celeste_App/actions/workflows/ci.yml)
[![MIT licence](https://img.shields.io/github/license/astraeos-dev/Celeste_App?label=licence)](LICENSE)
[![GitHub repository](https://img.shields.io/github/stars/astraeos-dev/Celeste_App?style=social&label=Repository)](https://github.com/astraeos-dev/Celeste_App)
[![Wiki](https://img.shields.io/badge/Wiki-how--to%20guides-1f2a3b)](https://github.com/astraeos-dev/Celeste_App/wiki)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)
![PyQt6](https://img.shields.io/badge/UI-PyQt6-blueviolet)

<a href="https://buymeacoffee.com/gregorychau"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me a Coffee" height="40"></a>

**Download**: the Windows installer is on the
[Releases](https://github.com/astraeos-dev/Celeste_App/releases/latest) page; Céleste then updates itself.
An idea, a problem, a body to add? [Open a request](https://github.com/astraeos-dev/Celeste_App/issues/new/choose).

**Active project** · part of the Ganymede family: [website](https://astraeos-dev.github.io/personnal-site/) ·
[Android app](https://github.com/astraeos-dev/Ganymede) · [Céleste for Home Assistant](https://github.com/astraeos-dev/Celeste_HA)

---

## Overview

Céleste computes in real time — or for any date — the positions of the Sun, the Moon, the planets (Mercury to
Neptune) and the minor planets, the events of the day (rise, set, twilights), the phases of the Moon, the eclipses
(seen from the chosen place) and the events of the year: conjunctions, oppositions, close approaches of the Moon,
seasons. The results show in a PyQt6 interface with the Astræos design (Nuit, Jour and Observation themes), with
interactive charts and a sky map.

The interface is translated into French, English, Spanish and German.

**Main features:**

- **Tonight** — at the top of the ephemeris: the dark night, the Moon, the visible planets (and comets) with their best
  moment, the finest deep-sky objects, the satellite passes and the next three events visible from here
- **Instant positions** — right ascension, declination, altitude, azimuth, distance
- **Events of the day** — rise, set, culmination, day length; civil (−6°), nautical (−12°) and astronomical (−18°)
  twilights
- **Moon phase** — name of the phase, illuminated fraction, age and distance of the Moon
- **Lunar calendar** — "Calendar" button of the Moon card: the month day by day, phase drawn, rise and set, new moon,
  quarters and full moon to the minute
- **Real-time mode** — automatic update every 2 s (adjustable)
- **Place search** — the name of a city (34,205 GeoNames cities, offline; "Paris, US" for a country) fills latitude,
  longitude and elevation
- **Geolocation** — position of the device from the system's location service (GPS, Wi-Fi), name of the town from
  OpenStreetMap; otherwise its last known position, then the approximate position of the IP address (ip-api.com),
  flagged as such: a window then says why (access denied by Windows, service turned off, timeout) and opens the
  location settings
- **24-hour paths** — altitude curves over a background coloured by the time of day (day, twilights, night), over the
  local day (local time below, UT above), tooltip on hover
- **Polar sky map** — zenith at the centre, 513 stars down to magnitude 4 (Yale Bright Star Catalogue, brought to the
  date: proper motion, precession, nutation, aberration) sized by magnitude, constellations, planets; tooltip on hover
  and detailed card on click (constellation, magnitude, coordinates)
- **Planets** — Mercury, Venus, Mars, Jupiter, Saturn, Uranus and Neptune: coordinates, altitude and azimuth,
  distance, elongation, magnitude, times of rise, culmination and set (name dimmed below the horizon); all the bodies
  or one group, "Visible only", sort by clicking a header; the Solar System seen from above, inner and outer
- **Data window** — a click on a body (sky map, Planets and Coordinates tabs) opens its card: magnitude,
  constellation, apparent diameter, illuminated fraction and phase angle, light time, distance from the Sun,
  coordinates, rise, culmination and set
- **Minor planets** — Ceres, Pallas, Juno, Vesta, the dwarf planets Pluto, Eris, Haumea and Makemake, and Sedna, to
  choose in the Planets tab, in the Coordinates tab and, when bright enough for the limiting magnitude, on the sky map:
  positions from JPL Horizons (to 0.001″), magnitudes from the H, G system; their Minor Planet Center number
  ("(1) Ceres") in their card and their tooltip
- **Coordinates** — Sun, Moon, planets, minor planets and Earth, with at the same time x, y, z and distance
  (heliocentric, geocentric or topocentric) and two angles (equatorial or horizontal seen from the place, ecliptic seen
  from the Sun or the Earth), magnitude, angle from the Sun and constellation; angles in the format of the settings, or
  in dd° mm′ ss″, dd° mm.mm′ or dd.ddddd° for this table only
- **Angle format** — chosen in the settings (dd° mm′ ss″, dd° mm.mm′ or dd.ddddd°), for the whole software
- **Eclipse forecast** — solar eclipses (total, annular, hybrid, partial; magnitude, duration of the central phase)
  and lunar eclipses (total, partial, penumbral; umbral and penumbral magnitudes, duration of each phase), with the
  time of greatest eclipse; **seen from here**: local times of the start, the maximum and the end, magnitude, share of
  the Sun hidden, totality or annularity, altitude of the Sun or the Moon
- **Eclipse projected on the ground** — "Map" button of each eclipse: band of totality or annularity, central line,
  maximum magnitude of the partial phase and point of greatest eclipse (solar eclipses); area where the Moon is up
  (lunar eclipses); on a Natural Earth background, with the chosen place
- **Conjunctions, oppositions and elongations** — instant to the minute (in UT and in the place's time) of the
  conjunctions between planets (which one passes north of the other) and with the Sun (inferior or superior for
  Mercury and Venus, with the transits), of the oppositions and of the greatest elongations of Mercury and Venus (east
  in the evening, west in the morning); oppositions of the minor planets; "Map" button: the paths of the bodies among
  the stars around the event
- **Moon and seasons** — close approaches of the Moon to the planets and to Aldebaran, the Pleiades, Regulus, Spica
  and Antares, occultations seen from here; perigees, apogees and supermoons; equinoxes, solstices, perihelion and
  aphelion
- **Meteor showers** — peaks of the 13 major showers of the year (IMO calendar); the night of the peak seen from here:
  best moment, altitude and direction of the radiant, meteors per hour under a dark sky, interference from the Moon
- **Comets** — C/2026 O1 (PANSTARRS), 45P/Honda-Mrkos-Pajdušáková, C/2026 C1 (Tsuchinshan) and 19P/Borrelly during
  their apparition (2025–2031, JPL Horizons tables): position, predicted magnitude, sky map, perihelion, closest
  approach and greatest brightness among the events
- **Animated orrery** — Planets tab: the Solar System seen from above, moving forward by a day to a year per step
- **Deep sky** — the 110 Messier objects on the sky map (atlas symbols, card on click) and the finest of the night in
  "Tonight"
- **Satellite passes** — International Space Station, Tiangong and Hubble over 10 days: time of appearance, highest
  point, entry into the Earth's shadow; CelesTrak orbits (AMSAT as a fallback) refreshed every two days
- **Visibility from here** — for each event, the night to see it (evening, morning or all night), with the altitude,
  the direction and the time; filters by group and "Visible from here only"; export to a calendar (.ics)
- **Equation of time** — difference between apparent and mean solar time
- **Automatic update** — a newly published version is offered at startup, installed in one click
- **Links** — Settings › About: website, source code, coffee, and requests on GitHub (problem, feature, body to add)
  pre-filled with the version and the system
- **Favourites** — saved places (36 preloaded cities)
- **Time zones** — IANA time zones, summer time included; "Automatic" follows the place
- **Multilingual interface** — French, English, Spanish, German; the system's language by default, immediate change in
  the settings (or `--lang`)
- **Themes** — Nuit (dark), Jour (light) and Observation (red on black, to keep night vision), chosen at the bottom of
  the side panel without restarting (or `--theme`)
- **Keyboard shortcuts** — `F5` calculate, `Ctrl+L` real time
- **Persistent settings** — theme, language, time format, starting place, limiting magnitude, real-time interval
  (`~/.celeste/settings.json`, outside the repository)

---

## Installation

Requirements: Python 3.10 or newer, and pip. PyQt6 bundles Qt; on a minimal Linux, Qt also needs a few system
libraries (`sudo apt install libegl1 libxkbcommon0` on Debian or Ubuntu).

```bash
git clone https://github.com/astraeos-dev/Celeste_App.git
cd Celeste_App
pip install -r requirements.txt
python main.py
```

Choice of language:

```bash
python main.py --lang fr   # French
python main.py --lang en   # English
python main.py --lang es   # Spanish
python main.py --lang de   # German
python main.py --theme jour   # light theme (nuit, jour, observation)
```

Without an option, the language follows the system's (English when it is not translated) and the theme is Nuit. The
language can then be changed in the Settings tab and the theme at the bottom of the side panel, without restarting.
The old theme names (`mocha`, `frape`, `latte`) are still accepted.

---

## Usage

| Field | Description |
|-------|-------------|
| **Date and time** | Format `DD/MM/YYYY HH:MM:SS`, in universal time (UT); the arrow opens a calendar |
| **Place** | The name of a city, chosen among the suggestions; fills latitude, longitude and elevation |
| **Latitude** | Decimal degrees, positive = north (e.g. `48.85` for Paris), point or comma |
| **Longitude** | Decimal degrees, positive = east (e.g. `2.35` for Paris), point or comma |
| **Time zone** | IANA time zone applied to the times of the events (summer time included); "Automatic" follows the place |
| **Favourites** | Choosing a place applies it at once; the star adds the typed place to the favourites, the bin deletes the chosen favourite |

An invalid coordinate gets an alert-coloured outline and a message shows under the field, without an error window.
Changing the date computes everything again after a moment.

**Buttons:**

- Clock, to the right of the date — back to the present instant
- Crosshair, to the right of the longitude — fills the latitude, the longitude and the time zone from the device's
  location service (to be allowed in the privacy settings of Windows or macOS); otherwise, from the IP address
- **Calculate** (`F5`) — runs the calculations for the typed date and place
- **Follow in real time** (`Ctrl+L`) — toggle button: follows the current time while it stays pressed (interval
  adjustable in the settings)
- **Nuit · Jour · Observation** — theme selector, at the bottom of the side panel

**Events:** the buttons of the tab search for the eclipses of the next 12 lunations, the events of the coming year and
the satellite passes of the next 10 days; "Export (.ics)" saves them to a calendar. Each eclipse gives its type, the
time of greatest eclipse (in universal time), the magnitudes and the duration of the phases. A penumbral eclipse so
faint that its existence depends on the precision of the calculation (penumbral magnitude below 0.01) is marked
"Uncertain".

The conjunctions follow the definition of the almanacs: same apparent ecliptic longitude seen from the centre of the
Earth (opposition: 180° from the Sun). Found day by day, the events are refined hour by hour then interpolated: over
the year 2026, their instants differ by at most one second from those of JPL Horizons (one to three minutes for the
greatest elongations, whose maximum is very flat). The map shows the paths in equatorial coordinates of the date, north
up and east to the left, with the stars of the catalogue, the ecliptic and dated marks (every 6 hours for the Moon).

An event is **visible from here** when the body stands at least 5° above the horizon while the Sun is 6° below the
horizon (12° for the fainter minor planets), in the night of the event; the map gives the best moment. A conjunction
of the Moon becomes an **occultation** when, seen from the place (parallax included), the body passes behind the lunar
disc: times of disappearance and reappearance. The **local circumstances of the eclipses** follow the Sun and the Moon
seen from the place every 20 s; the contacts are interpolated with the lunar radii of the NASA predictions (mean limb,
valleys for totality): on the central line of 12 August 2026, the duration of totality differs by less than 0.1 s
from NASA's.

A satellite pass is counted when the satellite rises at least 10° above the horizon, lit by the Sun, while the Sun is
6° below the horizon, for at least 30 seconds.

**Charts:**

- Hover over the 24-hour curves to read the altitude at any time; the background follows the altitude of the Sun
- The sky map puts the zenith at the centre and the horizon on the circle, north up; the slider sets the limiting
  magnitude of the stars
- Hover over a body of the map to identify it, click to show its card

---

## Astræos design

The interface and the charts follow the Astræos design system:

- **Themes** — Nuit (dark, the default), Jour (light) and Observation (red on black, to keep night vision outdoors).
  The colours are the tokens of the design system (`ciel-000`, `ciel-100`, `ciel-200`, `encre`, `encre-attenuee`,
  `or`, `lune`, `signal-ok`, `signal-alerte`), defined once in `config.py` and shared by Qt and matplotlib.
- **Typography** — IBM Plex Sans for the text, IBM Plex Mono for the figures, Astraeos Symboles for the astronomical
  symbols (☉ ☽ ♀ ♂ ♃ ♄ ⊕ ♈ ☌ ☍). The fonts are provided in `fonts/`, for the same rendering on every machine.
- **Components** — buttons (primary, secondary, quiet, danger), input fields with label, unit and error message, data
  cards, status badges, gauge, tabs and theme selector.
- **Rules** — no emoji (Material Design Icons instead); a single gold area per screen, the Calculate button;
  hairlines rather than shadows; a symbol always goes with the name of the body, never replaces it; labels without
  capitals; a text contrast of at least 4.5:1 in the three themes (checked by `tests/test_config.py`).

IBM Plex fonts (© IBM) and Astraeos Symboles (after Noto Sans Symbols) under the SIL Open Font License 1.1; Material
Design Icons (Pictogrammers) under the Apache 2.0 licence: see `fonts/README.md` and `assets/README.md`.

---

## Architecture

> **Changing Céleste**: how-to guides (texts and tooltips, adding a minor planet, a comet, a star, a meteor shower, a
> language, testing, publishing a version) are in [`docs/wiki`](docs/wiki/Home.md) and in the repository's
> [wiki](https://github.com/astraeos-dev/Celeste_App/wiki), in French.

The project follows the **MVC (model-view-controller)** pattern:

```
Celeste_App/
├── main.py              # Entry point — --lang / --theme options, Qt window
├── engine.py            # Model — pure astronomical calculations (AstroEngine)
├── gui.py               # View + controller — PyQt6 interface and application logic
├── charts.py            # matplotlib charts — paths, sky map, Solar System
├── utils.py             # Utilities — HMS/DMS formats, phase names
├── config.py            # Astræos design — colours of the Nuit, Jour and Observation themes, spacing, text styles
├── icons.py             # Material Design icons (SVG) and the Astræos symbol in the theme's colours
├── i18n.py              # Internationalisation — translations by key, with fallback
├── updater.py           # Updates: latest GitHub Release, checked download, installation
├── settings.py          # Persistent preferences (~/.celeste/settings.json)
├── places.py            # Offline place search (GeoNames cities)
├── satellites.py        # Orbital elements (TLE) of the satellites: download, checks, cache
├── constellations.py    # Constellation figures and the names of their stars
├── star_catalog.py      # 513 bright stars (Yale Bright Star Catalogue, magnitude < 4), generated
├── favorites_default.json # Preloaded places (36 cities), copied to ~/.celeste at the first save
├── locales/             # Translations (fr.json is the reference)
├── fonts/               # IBM Plex Sans, IBM Plex Mono and Astraeos Symboles fonts (OFL licence)
├── assets/              # Astræos symbol and icon (SVG), land, minor planets, comets, cities, Messier objects
├── scripts/             # Application build, star catalogue, data tables, release notes
├── celeste.spec         # PyInstaller recipe of Celeste.exe (Windows)
├── installer/           # Inno Setup installer (celeste.iss)
├── requirements.txt     # Runtime dependencies
├── requirements-dev.txt # Development dependencies (pytest)
├── CHANGELOG.md         # Changes of each version, the source of the release notes
├── docs/wiki/           # How-to guides (in French), published to the GitHub wiki
└── tests/               # Unit tests (engine, charts, interface, themes, i18n, updates, utilities)
```

### Model: `AstroEngine`

A fully decoupled calculation engine: class or static methods only, without internal state. The positions come from
the **JPL DE440** ephemeris (file `de440s.bsp`, 1850–2149) through [Skyfield]: IAU 2006 precession, IAU 2000A
nutation, light time, aberration, deflection; UT1 and ΔT from the IERS. Precision: planets within 0.07″ of JPL
Horizons, rises and sets to the second (within 30 s of the rounded times of the USNO).

The minor planets (except Pluto, in DE440) come from a **JPL Horizons** table (`assets/minor_planets.npz`, 2.4 MB,
`scripts/make_minor_planets.py`): heliocentric position and velocity every 10 days (60 for Eris, Haumea, Makemake and
Sedna), Hermite-interpolated; positions within 0.001″ of Horizons from 1850 to 2149.

The ephemeris (32 MB) is looked for in `data/` next to the program, then in `~/.celeste` (or `$CELESTE_DATA`), where it
is downloaded from the JPL/NAIF server at the first launch, then checked (size and SHA-256 of the published file).

| Method | Role |
|--------|------|
| `julian_day(dte)` | Julian day (JD) |
| `julian_century_j2000(dte)` | T in Julian centuries since J2000.0 |
| `delta_t(year)` | ΔT = TT − UT in seconds (IERS; Stephenson, Morrison and Hohenkerk 2016 before 1973) |
| `sun_position(t)` / `sun_position_tt(t)` | Apparent longitude and distance of the Sun (t in UT / in TT) |
| `moon_position(t)` | Apparent longitude, latitude and parallax of the Moon (t in UT) |
| `moon_position_tt(t)` | Same calculation in TT, with the distance of the Moon |
| `ecliptic_to_equatorial(l, b, t)` | Ecliptic → equatorial (RA, Dec), true obliquity (IAU 2006 + nutation) |
| `equatorial_to_horizontal(jd, lat, lon, ra, dec)` | Equatorial → horizontal (altitude, azimuth), apparent sidereal time |
| `elevation_correction(h, p)` | Parallax in altitude (π cos h), then atmospheric refraction |
| `find_events(dte, lat, lon, body, tz, elevation_m)` | Sun, Moon or planet: rise, set (upper limb), culmination, twilights over the local day (IANA time zone, summer time included), to the second; the elevation lowers the horizon |
| `horizontal(t, lat, lon, body, elevation_m, refraction)` | Topocentric altitude and azimuth (seen from the place, parallax included) |
| `coordinates(t, body, center, frame, lat, lon)` | Coordinates in the chosen system: heliocentric (geometric, J2000) or geo/topocentric (apparent, of the date); ecliptic, equatorial or horizontal; angles and x, y, z |
| `eclipse_map(greatest, kind)` | Eclipse projected on the ground: central line, shadow band, partial phase (Sun); Moon up (Moon) |
| `body_details(t, body)` | Data window: distance, light time, apparent diameter, distance from the Sun, phase angle, illuminated fraction |
| `observations(t, bodies)` | Visual magnitude, angle from the Sun and constellation (IAU), seen from the Earth |
| `moon_phase(t)` | Illuminated fraction of the Moon (%) and age since the last true new moon |
| `altitudes(dtes, lat, lon, elevation_m)` | Altitudes of the Sun and the Moon at a series of instants, in one vectorised calculation |
| `planet_heliocentric(t, name)` | Heliocentric ecliptic J2000 position (x, y, z in AU), Earth included |
| `planet_position(t, name)` | Apparent geocentric position: RA, Dec and distance (Mercury to Pluto) |
| `equation_of_time(t)` | Equation of time in minutes |
| `angular_separation(ra1, dec1, ra2, dec2)` | Angular separation between two bodies |
| `find_conjunctions(dte_start, num_days, max_separation)` | Conjunctions (inferior, superior, transit; north or south), oppositions and greatest elongations, to the minute |
| `find_moon_events(dte_start, num_days, max_separation)` | Conjunctions of the Moon with the planets and the bright stars of its path, perigees, apogees, supermoons |
| `find_seasons(dte_start, num_days)` | Equinoxes, solstices, perihelion and aphelion of the Earth |
| `tonight(dte, lat, lon, elevation_m, tz)` | The night seen from the place: dark night, Moon, visible planets and comets (best moment, rise, set), deep sky |
| `upcoming_events(dte, lat, lon, elevation_m, tz)` | The next three events visible from here within 30 days |
| `moon_calendar(year, month, lat, lon, elevation_m, tz)` | The Moon day by day over a month: phase, fraction, rise, set, main phases |
| `messier_catalog()` / `deep_sky_horizontal(t, lat, lon)` | The 110 Messier objects (OpenNGC) and their position seen from the place |
| `satellite_passes(elements, dte_start, lat, lon, elevation_m, num_days)` | Visible satellite passes (SGP4): lit by the Sun, dark sky, Earth's shadow |
| `comets_at(t)` / `find_comet_events(dte_start, num_days)` | Comets within their tables at a date; their perihelion, closest approach and greatest brightness |
| `find_meteor_showers(dte_start, num_days)` | Peaks of the major meteor showers (`METEOR_SHOWERS`, IMO calendar), at the solar longitude of their peak |
| `meteor_visibility(event, lat, lon, elevation_m, tz)` | Night of the peak seen from the place: best moment, radiant, hourly rate under a dark sky, Moon |
| `event_visibility(events, lat, lon, elevation_m, tz)` | Visibility of each event from the place, at nightfall (evening, morning, all night), occultations |
| `moon_occultation(event, lat, lon, elevation_m)` | Occultation seen from the place: disappearance, reappearance, altitude of the Moon |
| `eclipse_local(eclipse, lat, lon, elevation_m)` | Local circumstances of an eclipse: contacts, magnitude, obscuration, duration of totality |
| `event_scene(event, star_catalog)` | Paths of the two bodies around an event, stars of the field and ecliptic (for its map) |
| `find_eclipses(dte_start, num_months)` | Solar eclipses (Besselian elements) and lunar eclipses (umbra and penumbra of the Earth, Danjon's rule): type, magnitudes, durations, time of greatest eclipse in UT |

[Skyfield]: https://rhodesmill.org/skyfield/

### Cache

A cache keyed by the local date, the place, the time zone and the elevation avoids computing the events of the day
again while the date, the place and the time zone do not change, which matters in real-time mode. For the same reason,
only the chart of the shown tab is redrawn; the others are when they are opened.

## Scientific references

- **R. S. Park et al.** (2021), *The JPL Planetary and Lunar Ephemerides DE440 and DE441*, AJ 161, 105 — positions
- **B. Rhodes**, *Skyfield* — reduction of the positions (IAU 2006/2000A), rises, sets and phases of the Moon,
  satellite orbits (SGP4)
- **F. R. Stephenson, L. V. Morrison and C. Y. Hohenkerk** (2016), Proc. R. Soc. A 472 — historical ΔT; IERS after
- **Jean Meeus**, *Astronomical Algorithms*, 2nd edition, Willmann-Bell, 1998 — chapter 54 (eclipse rules), chapters
  13 and 16 (coordinate transformations, refraction)
- **Explanatory Supplement to the Astronomical Almanac** (1992), chapter 8 — Besselian elements of solar eclipses
- **André Danjon** — enlargement of the Earth's shadow by the atmosphere (1/85 of the Earth's radius), used for lunar
  eclipses
- **Fred Espenak and Jean Meeus**, *Five Millennium Canon of Solar Eclipses* and *Five Millennium Canon of Lunar
  Eclipses*, NASA — reference values of the eclipse tests
- **JPL Horizons** and **USNO** (aa.usno.navy.mil) — reference values of the tests of positions, rises and sets
- **D. Hoffleit and W. H. Warren** (1991), *Yale Bright Star Catalogue*, 5th ed. — stars of the sky map (public domain)
- **Natural Earth** (naturalearthdata.com), land at 1:110,000,000 — background of the eclipse maps (public domain)
- **International Meteor Organization**, *Meteor Shower Calendar 2026* (J. Rendtel), table 5 — meteor showers:
  activity, solar longitude at the peak, radiant, velocity, ZHR
- **GeoNames** (www.geonames.org), cities of more than 15,000 inhabitants, CC BY 4.0 licence — place search
- **OpenNGC** (M. Verga, CC BY-SA 4.0 licence) and the **SEDS** Messier database — Messier objects
- **CelesTrak** and **AMSAT** — orbital elements (TLE) of the space stations and of Hubble
- **JPL Small-Body Database** — magnitude parameters M1, K1 of the comets; **JPL Horizons** — their positions
- **E. Bowell et al.** (1989), *Application of photometric models to asteroids*, Asteroids II — H, G magnitudes of
  the minor planets (parameters from the JPL Small-Body Database)

---

## Windows application

Céleste builds into a standalone Windows application (`Celeste.exe`) with [PyInstaller]. The JPL ephemeris (32 MB) is
not in the installer: Céleste downloads it only once, at its first launch, into `~/.celeste`. An Internet connection
is needed on that day; after that everything works offline, and the updates (≈ 80 MB) do not download it again.

- **From GitHub**: *Actions* tab, "Build — Windows application" workflow, *Run workflow* button (or push a `v*` tag).
  Two artifacts: `Celeste-Windows-Setup`, the installer `Celeste-<version>-Setup.exe` (Start menu and Desktop
  shortcuts, uninstall from the Windows settings), and `Celeste-Windows`, the application folder to run without
  installing (`Celeste.exe`).
- **New version**: change `APP_VERSION` in `config.py` (the only place: window, installer, GitHub requests), write its
  changes in [`CHANGELOG.md`](CHANGELOG.md) and merge: the workflow publishes the `v<version>` Release (installer,
  SHA-256 checksum, and the note of the version, taken from the changelog).
- **Automatic update**: an installed Céleste looks for a newer version at startup (or through Settings › About › Check
  for updates), downloads it, checks its checksum, installs it over the old one and reopens, with the settings and
  favourites kept (`updater.py`). When a download fails, the window says why; each attempt is logged in
  `%TEMP%\Celeste-update\update.log`. See the wiki, [Publier une version](docs/wiki/Publier-une-version.md) (in French).
- **On a Windows PC**:

```bash
pip install pyinstaller
python scripts/build_exe.py
```

The script puts the ephemeris in `~/.celeste` for the start-up check, draws the icon from `assets/astraeos-icone.svg`,
runs PyInstaller (`celeste.spec`), checks that the ephemeris is not in the application and that the application starts
(`--self-test`), and creates the archive in `dist/`. When [Inno Setup 6](https://jrsoftware.org/isinfo.php) is
installed, it also builds the installer (`installer/celeste.iss`, with Céleste's icon). Neither is signed: at the first
launch, SmartScreen shows "Windows protected your PC" (*More info*, then *Run anyway*). The preferences and favourites
(`%USERPROFILE%\.celeste`) survive an uninstall.

[PyInstaller]: https://pyinstaller.org/

---

## Dependencies

| Package | Min. version | Role |
|---------|-------------|------|
| [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) | 6.5 | Graphical interface (Qt 6) |
| [matplotlib](https://matplotlib.org/) | 3.10.8 | Interactive astronomical charts |
| [Skyfield](https://rhodesmill.org/skyfield/) | 1.47 | JPL DE440 ephemeris, time (UT1, ΔT), rises and sets, satellites (installs NumPy) |
| [timezonefinder](https://github.com/jannikmi/timezonefinder) | 6.5 | IANA time zone of a place, offline ("Automatic" mode) |
| [tzdata](https://pypi.org/project/tzdata/) | — | IANA time zone database for `zoneinfo` (needed on Windows) |

`urllib`, `json` and `argparse` are part of the Python standard library. The fonts and icons come with the project
(`fonts/`, `assets/`): nothing to install.

---

## Roadmap

### Data and calculations

- [x] Nautical (−12°) and astronomical (−18°) twilights
- [x] **Solar System** — positions of Venus, Mars, Jupiter and Saturn
- [x] **Solar eclipses** — type, magnitude, duration of the central phase
- [x] **Conjunctions and oppositions** — next planetary events, to the minute, with their map
- [x] **Minor planets** — Ceres, Pallas, Juno, Vesta, Pluto, Eris, Haumea, Makemake, Sedna (JPL Horizons)
- [x] **Events seen from here** — visibility, occultations, Moon, seasons, local circumstances of eclipses, .ics export
- [x] **Meteor showers** — peaks of the major showers, radiant and Moon on the night of the peak
- [x] **Precision** — JPL DE440 ephemeris (Skyfield) instead of the Meeus series; rises and sets to the second
- [x] **Equation of time**
- [x] **2D orrery** — animated orbits
- [x] **Lunar eclipses** — type (total, partial, penumbral), magnitudes, duration of the phases, time of greatest eclipse
- [x] **Comets** — position, magnitude, perihelion and closest approach
- [x] **Deep sky** — the Messier catalogue
- [x] **Satellites** — visible passes of the ISS, Tiangong and Hubble

### Interface and visualisation

- [x] Main stars on the map (32+, sized by magnitude)
- [x] Constellation figures on the polar map
- [x] Planets on the sky map (tooltip and card on click)
- [x] **Twilight colours** — background of the path chart coloured by the time of day
- [x] **Interactive sky map** — full card of a star on click
- [x] **Astræos design** — Nuit, Jour and Observation themes without restarting, IBM Plex fonts, vector icons

### Ease of use

- [x] Favourites — saved places (`~/.celeste/favorites.json`)
- [x] IANA time zones, summer time included; "Automatic" takes the place's zone (timezonefinder)
- [x] Observer's elevation (lowered horizon), topocentric positions, exact phase of the Moon
- [x] **Multilingual interface** — FR / EN / ES / DE
- [x] **Persistent settings** — language, theme, place, real-time interval (`~/.celeste/settings.json`)
- [ ] **Calculation history** — last calculations reloadable in one click
- [x] **Place search** — geocoding by city name
- [x] **Monthly lunar calendar** — month view with the phase of each day

### Engineering and quality

- [x] **Unit tests** — pytest on the engine, the charts, the interface (off screen), the themes, the updates,
  `utils.py` and `i18n.py` (12 files, ~550 cases)
- [x] **Windows executable** — standalone `Celeste.exe` (PyInstaller), ephemeris downloaded at the first launch

---

## Licence

The project is distributed under the MIT licence: see the `LICENSE` file. The fonts of `fonts/` are under the SIL Open
Font License 1.1 and the Material Design Icons under the Apache 2.0 licence (see `fonts/README.md` and
`assets/README.md`).
