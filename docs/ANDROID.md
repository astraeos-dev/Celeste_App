# Céleste 5 — the Android port

Version 5 brings Céleste to Android phones and tablets. This document is the plan: what is reused, how the app is
built, the steps from 4.x to 5.0, and the risks. It will be updated as the work goes.

## What can be reused

Céleste was written model–view–controller from the start, and only the view depends on Qt:

| Module | Lines | Qt | On Android |
|---|---|---|---|
| `engine.py` (DE440, rises, eclipses, events, moons, rings, satellites) | 2,800 | no | reused as is |
| `planner.py`, `mpc.py` (night planner, comets) | 670 | no | reused as is |
| `places.py`, `satellites.py`, `history.py`, `settings.py`, `i18n.py`, `utils.py`, `config.py` | 1,100 | no | reused (paths adapted) |
| `assets/`, `locales/`, `star_catalog.py`, fonts | — | — | reused as is |
| `charts.py` (matplotlib) | 1,100 | no | its *scene* functions reused; drawing redone natively |
| `gui.py`, `icons.py`, `main.py` (PyQt6) | 5,400 | yes | rewritten for touch screens |

The 688 tests check the engine against JPL Horizons, NASA, the USNO and the IMO. Keeping that engine, rather than
rewriting it, keeps its precision.

## The choice: Python engine, native interface

| Option | For | Against |
|---|---|---|
| **Kotlin + Jetpack Compose interface, Python engine through [Chaquopy](https://chaquo.com/chaquopy/)** (recommended) | Native look and speed, Material components, Android sensors and notifications; the engine and its tests unchanged; Chaquopy is open source (MIT) and ships NumPy | Two languages; Python adds about 25 MB to the APK and a second or two at the first start |
| PySide6 for Android (Qt for Python) | One interface for desktop and phone | Still marked technical preview; the desktop layout (side panel, nine tabs) does not suit a phone anyway; NumPy and Skyfield must be cross-built |
| Kivy or BeeWare | All in Python | A third interface toolkit to learn; neither looks native; packaging of NumPy is fragile |
| Rewrite everything in Kotlin | Smallest, fastest app | Months of work and a new engine to validate: DE440 reading, ΔT, eclipses, events… |

Recommendation: **Chaquopy**. The Compose interface calls a thin Python API that returns plain data (dicts and
lists, or JSON), and draws the charts and the sky map itself on a `Canvas`.

## Architecture

```
Celeste_App/
├── celeste/              # (4.11) the Qt-free core, one package shared by both apps
│   ├── engine.py, planner.py, mpc.py, places.py, satellites.py, history.py, …
│   ├── scenes.py         # what charts.py computes before drawing: sky scene, curves, orrery
│   └── api.py            # entry points for Android: tonight(), ephemeris(), plan(), sky(), events()…
├── desktop/              # the PyQt6 app (today's gui.py, charts.py, main.py)
├── android/              # Gradle project: Kotlin, Jetpack Compose, Chaquopy
│   └── app/src/main/python → ../../celeste   (the same core)
├── assets/, locales/, fonts/
└── tests/                # unchanged, run on the core
```

- **Data:** the ephemeris (32 MB) is downloaded at the first start into the app's private storage, with the same
  size and SHA-256 checks as on Windows; the catalogues travel in the APK (about 1 MB).
- **Texts:** the same `locales/*.json` files; the Compose interface reads them, so a translation serves both apps.
- **Design:** the Astræos tokens of `config.py` become a Compose theme (Nuit, Jour, Observation in red).
- **Settings:** the same keys as `settings.py`, stored in the app's folder; favourites and history likewise.

## The phone interface

A phone shows one thing at a time, so the nine desktop tabs become five destinations of a bottom bar:

1. **Tonight** — the dark night, the Moon, the visible planets, the next events, the satellite passes.
2. **Sky** — the sky map, which can follow the phone's orientation (compass and accelerometer) to point at an
   object; search by name.
3. **Targets** — the night planner (constraints in a bottom sheet, the tables, the altitude chart).
4. **Events** — eclipses, conjunctions, meteor showers, comets, satellites; added to the phone's calendar.
5. **More** — ephemeris tables, planets, Solar System, coordinates, lunar calendar, settings, about.

The place comes from the phone's location (with permission), a search by name, or the favourites.

What Android adds: **notifications** (an ISS pass in ten minutes, the peak of a meteor shower, an eclipse seen from
here), a **home-screen widget** (tonight's Moon and the next event), and the red **Observation** theme kept on at
night to protect dark adaptation.

## Steps

| Version | Content |
|---|---|
| **4.11** | Move the Qt-free modules into the `celeste` package and `charts.py`'s computations into `scenes.py`; add `api.py` with JSON-ready results and its tests. The desktop app is unchanged for its users. |
| **5.0 alpha** | `android/` project built by GitHub Actions (debug APK as an artifact): Chaquopy, first start (ephemeris download), Tonight and the ephemeris, place by GPS or search, the four languages, the three themes. |
| **5.0 beta** | Sky map drawn natively, with orientation; Targets; Events and calendar export; notifications; widget. Testers through the Play Console's internal track or a signed APK on GitHub. |
| **5.0** | Release: signed APK on GitHub Releases, then Google Play (and F-Droid if the build is reproducible). The desktop app becomes 5.0 too, on the shared core. |

Each step keeps the full test suite green; the Android app adds its own interface tests (Compose UI tests) and a
check that the Python API gives the same results on the phone as on the desktop.

## Risks and how to meet them

| Risk | Answer |
|---|---|
| APK size (Python, NumPy, Skyfield: about 25 MB) | Only arm64-v8a and armeabi-v7a; the ephemeris downloaded, not shipped; Android App Bundle splits per device |
| First start slow (Python start, ephemeris load) | A splash with progress; the engine kept warm in a background service while the app is open |
| Speed on modest phones | The heavy work (events of the year, NGC/IC planner) already runs in the background on the desktop; same on Android, with cached results |
| Skyfield or NumPy versions Chaquopy does not offer | Pin the versions the tests pass with; Chaquopy offers NumPy builds for Python 3.10–3.13 |
| Two interfaces to maintain | The core holds the logic and the texts; the interfaces only lay out what `api.py` returns |
| Store requirements (privacy policy, location permission) | Location only when the user asks, no account, no tracking: a short privacy page on the website |

## Decisions to take

- **One app or two?** Céleste for Android as its own app, or inside the existing
  [Ganymede](https://github.com/astraeos-dev/Ganymede) Android app.
- **Distribution:** GitHub Releases only, or Google Play too (a developer account is needed, 25 USD once).
- **Minimum Android version:** Android 8 (API 26) reaches nearly every phone in use and is what Chaquopy needs.
