# Céleste 5 — the Android port

Version 5 brings Céleste to Android phones and tablets **with the same Qt interface as the desktop**: one code
base, one look, the Astræos design everywhere. This document is the plan: what is reused, the tools, the steps from
4.x to 5.0, and the risks. It will be updated as the work goes.

## What can be reused

Everything. The engine and the data are reused as they are; the Qt interface is reused too, given a compact layout
for small screens:

| Module | Lines | On Android |
|---|---|---|
| `engine.py` (DE440, rises, eclipses, events, moons, rings, satellites) | 2,800 | as is |
| `planner.py`, `mpc.py`, `places.py`, `satellites.py`, `history.py`, `settings.py`, `i18n.py`, `utils.py`, `config.py` | 1,800 | as is (user folder from `QStandardPaths`) |
| `charts.py` (matplotlib, drawn in Qt by its QtAgg backend) | 1,100 | as is |
| `gui.py`, `icons.py`, `main.py` (Qt) | 5,400 | the same code, with a compact layout below 600 pixels of width |
| `assets/`, `locales/`, `star_catalog.py`, `fonts/` | — | as is |

The 688 tests run unchanged, and the interface tests also run in the compact layout.

## The tools: Qt for Python on Android

Two ways lead to Android with a Python Qt application:

| Option | For | Against |
|---|---|---|
| **PySide6 and `pyside6-android-deploy`** (recommended) | The official tool of the Qt Company; builds an APK from a Python project with python-for-android, whose recipes include NumPy and matplotlib; PySide6 is under the LGPL | Still labelled a technical preview; Céleste moves from PyQt6 to PySide6 |
| PyQt6 and `pyqtdeploy` | No change of binding | Every package with C code (NumPy, matplotlib) must be cross-built by hand; little used for Android |

Recommendation: **PySide6**. The move from PyQt6 is mostly mechanical in Qt 6 (same class and enum names):
`pyqtSignal` becomes `Signal`, the imports change, and a few calls differ. Going through one small module
(`qt.py`) that imports either binding lets the desktop switch first and keeps PyQt6 working during the move.

## What changes in the interface

The window today is made for a screen at least 1180 pixels wide: a side panel and nine tabs. Below 600 pixels of
width (a phone, or a narrow window on the desktop), `gui.py` switches to a **compact layout**:

- the side panel (date, place, time zone, favourites, Calculate) becomes a drawer opened from a button at the top;
- the tabs become a bar at the bottom with five entries — **Tonight**, **Sky**, **Targets**, **Events**, **More**
  (ephemeris tables, trajectories, planets, Solar System, coordinates, settings);
- the touch targets grow to 48 pixels at least; what the mouse hover shows today (chart tooltips, help texts) shows
  on a tap or a long press;
- the tables keep their first columns and scroll sideways; the planner's constraints open in a full-screen page.

Because the compact layout is part of `gui.py`, it can be built and tested on the desktop, by narrowing the window,
long before the first APK.

What Android brings on top, through Qt:

- **location** of the phone: `QtPositioning`, already used on the desktop;
- **a sky map that follows the phone** (compass and accelerometer): `QtSensors`;
- **storage** in the app's private folder: `QStandardPaths`;
- **sharing** an export (plan, calendar) with other apps: `QDesktopServices` and Android intents.

Notifications (an ISS pass in ten minutes, a meteor peak) and a home-screen widget have no Qt API on Android; they
would need Java calls through `QJniObject` or pyjnius. They come after 5.0, if they are wanted.

## Steps

| Version | Content |
|---|---|
| **4.11** | `qt.py` and the move from PyQt6 to PySide6 on the desktop (same app for its users; Windows build and tests on PySide6). A first APK in GitHub Actions: an empty window that loads the engine and runs the self-test on an emulator, to settle the tools early. |
| **4.12** | The compact layout in `gui.py`, tested by narrowing the window; user folder from `QStandardPaths`. |
| **5.0 alpha** | The full app as a debug APK built by GitHub Actions: first start (ephemeris download with its progress), Tonight, ephemeris, sky map, planets, Targets, events; location by GPS; the four languages and the three themes. |
| **5.0 beta** | Sky map following the phone; Android back button and screen rotation; sharing exports; speed on modest phones. A signed APK for testers. |
| **5.0** | Release: signed APK on GitHub Releases, then Google Play if wanted. The desktop app becomes 5.0 too: the same code. |

## Risks and how to meet them

| Risk | Answer |
|---|---|
| `pyside6-android-deploy` is a technical preview | Settled in 4.11 with the smallest APK, before any interface work; the fallback is pyqtdeploy, with the same code |
| A package without a python-for-android recipe | Skyfield, jplephem and sgp4 are pure Python (sgp4's C part is optional); timezonefinder is the one to check, with the offline place list of `places.py` as a fallback for the time zone |
| APK size (Qt, Python, NumPy, matplotlib: about 60 to 80 MB) | arm64-v8a only at first; the ephemeris (32 MB) downloaded at the first start, not shipped; only the Qt modules used |
| First start slow | A start screen with progress; the heavy computations already run in the background |
| Speed of the charts on a phone | matplotlib redraws only the shown chart, as on the desktop; the sky map can move to `QPainter` if needed |
| Touch use of a desktop interface | The compact layout is designed for touch and tested on the desktop at phone width |
| Store requirements (privacy policy, location permission) | Location only when the user asks, no account, no tracking: a short privacy page on the website |

## Decisions to take

- **One app or two?** Céleste for Android as its own app, or inside the existing
  [Ganymede](https://github.com/astraeos-dev/Ganymede) Android app.
- **Distribution:** GitHub Releases only, or Google Play too (a developer account is needed, 25 USD once).
- **Minimum Android version:** Android 9 (API 28) is what recent Qt 6 versions require.
