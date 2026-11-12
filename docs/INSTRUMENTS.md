# The Workshop — astronomical instruments to make

A section of Céleste where the user prints, cuts and assembles real instruments, **computed for their own place**:
an astrolabe engraved for their latitude, a sundial that reads their legal time, a planisphere of their sky. This
document is the design: the instruments, what Céleste computes for each, how they are printed and checked, and the
steps. A first prototype exists: `instruments.py` draws the plate and the rete of an astrolabe (see the end).

## Why in Céleste

- Céleste already knows the place (latitude, longitude, time zone, summer time, elevation), the stars brought to the
  date, the Sun's declination and the equation of time: everything an instrument maker needs.
- An instrument made for one's own latitude is what old makers did, and what printed kits rarely offer.
- Each instrument can be **checked against the app**: the astrolabe's reading of the time, the sundial's shadow,
  the planisphere's sky, against Céleste's computation for the same moment.

## The instruments

Ordered from the simplest to make to the most demanding.

| # | Instrument | What Céleste computes for the place | Parts | Level |
|---|---|---|---|---|
| 1 | **Planisphere** (star wheel) | Stars to magnitude 4.5 and the 88 figures, projected for the latitude; the horizon window; the date and hour rings, with the longitude's offset from the time zone | Star disc, mask, pin | Easy |
| 2 | **Equatorial sundial** | Dial tilted to the latitude, hour lines every 15°; a table of the corrections (equation of time, longitude, summer time) to read the legal time | Dial (two faces: summer and winter), gnomon, stand | Easy |
| 3 | **Horizontal sundial** | Hour lines `tan H' = sin φ · tan H` for the latitude, shifted by the longitude; gnomon angle = latitude; optional date lines (solstices, equinoxes) | Dial, triangular gnomon | Easy |
| 4 | **Nocturnal** | Reading the time at night from Polaris and the pointers of the Big Dipper (or Kochab): date ring and hour ring for the longitude | Two discs, rule, eyehole | Medium |
| 5 | **Horary quadrant** | Altitude scale with a plumb line; the curves of the Sun's altitude for each hour through the year at the latitude | Card quadrant, sights, thread and weight | Medium |
| 6 | **Planispheric astrolabe** | Plate for the latitude (horizon, almucantars, azimuths, twilight, unequal hours), rete (ecliptic and stars of the date), mater with hour and degree scales, back with the calendar–zodiac scale and the shadow square, rule (alidade) | Mater, plate, rete, rule, alidade, pin and wedge | Demanding |
| 7 | **Vertical declining sundial** (on a wall) | The wall's orientation measured with the Sun (its azimuth at the moment of a shadow), then the hour lines for that wall | Dial, gnomon (style) | Demanding |
| 8 | **Noon mark (meridian line) with analemma** | The figure-eight of the Sun at true local noon through the year, at the scale of a wall or a floor | Template in sections, to transfer | Project |

Also possible later: a cross-staff (Jacob's staff) with its graduations for the user's arm, a kamal, a sun ring
(anneau astronomique), a Moon-phase volvelle.

## What each printout holds

- **True scale**, with a ruler of 100 mm on every page to check the printer did not resize it; A4, A3 or Letter.
- **Cut lines** distinct from **drawn lines**; folds and glue tabs marked.
- An **assembly sheet** in the interface language: materials (card of 250–300 g/m², a split pin, a transparent
  sheet for a rete), steps with drawings.
- A **use sheet** with a worked example **for tonight or today at the place**, computed by Céleste: "at 22:00, set
  Vega on the 30° almucantar, read the time on the limb: 22:00" — and what the user should find.
- An **SVG** next to the PDF, for a laser cutter (cut and engrave on separate layers).

## How the geometry is checked

Every instrument gets tests of two kinds, as the engine has:

1. **Closed formulas.** The prototype's almucantars lie on the classic circles — centre at `cos φ / (sin φ + sin h)`,
   radius `cos h / (sin φ + sin h)` — to 10⁻¹⁶; the zenith at `tan((90° − φ) / 2)`; the tropics at `tan(45° ∓ ε/2)`.
   The sundials have their own: `tan H' = sin φ tan H` for a horizontal dial.
2. **The sky of Céleste.** A reading done on the instrument's geometry matches the engine: the time read on the
   astrolabe from a star's altitude, the shadow of the sundial's gnomon from the Sun's position, the stars inside the
   planisphere's window at a given date and hour.

## In the application

- **Desktop:** a *Workshop* window, opened from the side panel (the window already has nine tabs): the list of
  instruments with a drawing, the options (size, paper, hemisphere, stars, line density), a preview, and *Print*
  / *Save PDF* / *Save SVG*.
- **Android (version 5):** an entry of the *More* page; the PDF shared to a printer or another app.
- **Code:** `instruments.py` holds the geometry (no Qt, tested); the drawing goes through matplotlib's PDF and SVG
  backends (already used by Céleste), at true scale; the interface only collects the options.

## Steps

| Step | Content |
|---|---|
| Prototype (done) | `instruments.py`: astrolabe plate and rete for any latitude, PDF at true scale, tests against the classic formulas |
| Workshop 1 | The Workshop window; the **planisphere**, the **equatorial** and **horizontal sundials**; assembly and use sheets in four languages |
| Workshop 2 | The complete **astrolabe** (mater, back, unequal hours, rule, alidade, rete as a cut-out frame); the **nocturnal** |
| Workshop 3 | **Horary quadrant**, **vertical declining sundial** (wall orientation measured with the Sun), **noon mark** |

Where these steps fall among the versions is to be decided with the Android port (4.11 and 4.12 prepare it).

## The prototype

`instruments.py`:

- `plate(lat)` — tropics and equator, horizon, almucantars every 10°, azimuths every 15°, astronomical twilight,
  zenith; the mirror image for the southern hemisphere.
- `rete(stars)` — the ecliptic with a mark every 30° (the signs) and the stars that fall on the plate.
- `print_astrolabe(path, lat, place, plate_mm)` — two A4 pages at true scale: the plate, then the rete (to print on
  a transparent sheet).

It follows the astrolabes of old: the north celestial pole at the centre, the south (noon) at the top under the
ring, the east on the left; the projection is stereographic from the south pole onto the plane of the equator. Still
missing for a usable instrument: the mater and its scales, the unequal hours, the rule, a cut-out rete, labels and
the assembly sheet.
