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
| `gui.py`, `ui/` (one module per space), `icons.py`, `main.py` (Qt) | 6,600 | the same code, with a compact layout below 600 pixels of width |
| `assets/`, `locales/`, `star_catalog.py`, `fonts/` | — | as is |

The 786 tests run unchanged, and the interface tests also run in the compact layout.

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

The window is made for a screen at least 1180 pixels wide: a side panel and five spaces (4.13). Below 600 pixels
of width — 900 in practice, below which the wide layout no longer fits — the window switches to a **compact
layout**:

- the side panel (date, place, time zone, favourites, Calculate) becomes a drawer opened from a button at the top;
- the five spaces become a bar at the bottom — **Tonight**, **Sky**, **Bodies**, **Calendar**, **Observe** — and
  the settings move to the drawer;
- the touch targets grow to 48 pixels at least; what the mouse hover shows today (chart tooltips, help texts) shows
  on a tap or a long press;
- the tables keep their first columns and scroll sideways; the planner's constraints open in a full-screen page.

Because the compact layout is part of the Qt interface, it can be built and tested on the desktop, by narrowing the window,
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
| **4.13** | `gui.py` split into one module per space (`ui/`); the interface in five spaces, the ones of the phone's bottom bar. |
| **4.14** | `qt.py` and the move from PyQt6 to PySide6 on the desktop (same app for its users; Windows build and tests on PySide6; `CELESTE_QT=pyqt6` still runs PyQt6). A first APK in GitHub Actions (`.github/workflows/android.yml`): the smallest app, `android/main.py` (version, theme), to settle the tools early; the engine (NumPy, Skyfield) needs python-for-android recipes and comes with the alpha. |
| **4.15** | The compact layout below 900 pixels of width (`COMPACT_WIDTH` in `gui.py`), tested by narrowing the window: drawer, bottom bar, 48-pixel touch targets, stacked cards, the Targets' constraints on their own page. Next: user folder from `QStandardPaths`. |
| **4.16–4.17** | The engine on the phone: `android/deploy.py` runs `pyside6-android-deploy` (PySide6 6.12, whose deploy tool pins python-for-android and CPython 3.14) with the engine's packages added — NumPy (a recipe), Skyfield, jplephem, sgp4 without its C++ part, certifi — and the Internet permission. The emulator test of the workflow downloads the JPL ephemeris over HTTPS (`mobile.py`: certifi's and Android's CA certificates) and computes the Sun and the Moon. |
| **5.0 alpha** | The full app as a debug APK built by GitHub Actions (`CELESTE_ANDROID_APP: full` in the workflow; `lite` builds the small test app): `mobile.py` puts the user folder in the app's private storage and leaves out the automatic update; matplotlib, Pillow and tzdata join the packages; `android/qt_modules.py` names the Qt modules (qt.py imports them by name, which the deploy tool cannot read: without them the APK had no `Qt6Android.jar`, plugins nor permissions); the time zone of the place falls back on the phone's own (timezonefinder is not packaged). Verified on the workflow's emulator (Android 14): the window opens, compact, with the ephemeris downloaded at the first start and the sky map computed (4.18: its time bar is light enough for a phone). 4.19, after a first try on a phone: `ui/touch.py` makes pages and lists scroll with the finger (QScroller), fits every window to the screen in a scroll area, closes it with Back, and the sky map zooms with two fingers; the sizes kept from the wide layout are thrown away at each switch, and the emulator check fails when the window or a form is wider than the screen. Then: first start (ephemeris download with its progress), Tonight, ephemeris, sky map, planets, Targets, events; location by GPS; the four languages and the three themes. |
| **5.0 beta** | Sky map following the phone; Android back button and screen rotation; sharing exports; speed on modest phones. Google Play closed test (see below). |
| **5.0** | Release on Google Play (closed test, then production) and the APK on GitHub Releases. The desktop app becomes 5.0 too: the same code. |

## Risks and how to meet them

| Risk | Answer |
|---|---|
| `pyside6-android-deploy` is a technical preview | Settled in 4.14 with the smallest APK, before any interface work; the fallback is pyqtdeploy, with the same code |
| A package without a python-for-android recipe | Skyfield, jplephem and sgp4 are pure Python (sgp4's C part is optional); timezonefinder is the one to check, with the offline place list of `places.py` as a fallback for the time zone |
| APK size (Qt, Python, NumPy, matplotlib: about 60 to 80 MB) | arm64-v8a only at first; the ephemeris (32 MB) downloaded at the first start, not shipped; only the Qt modules used |
| First start slow | A start screen with progress; the heavy computations already run in the background |
| Speed of the charts on a phone | matplotlib redraws only the shown chart, as on the desktop; the sky map can move to `QPainter` if needed |
| Touch use of a desktop interface | The compact layout is designed for touch and tested on the desktop at phone width |
| Store requirements (privacy policy, location permission) | Location only when the user asks, no account, no tracking: a short privacy page on the website |

## Google Play

Céleste for Android is **its own app**, published on **Google Play** (and its APK on GitHub Releases). What the store
asks, and what it means here:

| Requirement | What to do |
|---|---|
| A developer account (25 USD once, identity checked) | Opened by the project's owner; the app's identifier chosen once and for good, e.g. `dev.astraeos.celeste` |
| An **Android App Bundle** (`.aab`), not an APK | Check in 4.13 that the PySide6 tools produce one (python-for-android can); else build the bundle from their Gradle project |
| A recent **target API level** (the store raises it every year) | Follow the Qt 6 version that supports it; checked at each release |
| **16 KB memory pages** for the native libraries of apps targeting Android 15 and later | Python, NumPy and Qt libraries built with 16 KB alignment: one of the points the 4.13 trial settles |
| **Play App Signing** | Google keeps the app's key; the project keeps an upload key, in the GitHub secrets of the release workflow |
| A **closed test** with at least 12 testers for 14 days before the first production release (new personal accounts) | The 5.0 beta: testers invited by e-mail through the Play Console |
| **Data safety** form and a **privacy policy** | Nothing collected or shared: the location stays on the phone and is sent nowhere but to the OpenStreetMap name lookup when the user asks; the policy published on the website |
| Store listing: icon, screenshots of a phone and a tablet, short and long descriptions in the four languages | Made from the app itself (compact layout, the three themes) |

A GitHub workflow builds and signs the bundle when `APP_VERSION` changes, like the Windows installer today, and can
upload it to the Play Console's internal track.

## Decisions taken

- **Its own app**, separate from any other project.
- **Google Play**, plus the APK on GitHub Releases.
- **Minimum Android version:** Android 9 (API 28), what recent Qt 6 versions require.
