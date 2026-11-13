# The Workshop — astronomical instruments to make

A section of Céleste where the user prints, cuts and assembles real instruments, **computed for their own place**:
an astrolabe engraved for their latitude, a sundial that reads their legal time, a planisphere of their sky. This
document is the design: the instruments, what Céleste computes for each, how they are printed and checked, and the
steps. Workshop 1 (4.11: the planisphere and the two sundials) and Workshop 2 (4.12: the complete astrolabe and the
nocturnal) are done (see the end).

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
| 1 | **Planisphere** (star wheel) | Stars to magnitude 4.5 and the 88 figures, projected for the latitude; the horizon window; the date ring and the night's hours, with the longitude's offset from the time zone | Star wheel, holder folded in two, pin, glue | Easy |
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
  instruments with a description, its own place, time zone and date (from the side panel at first), the size of the
  astrolabe, the paper, a preview page by page, and *Save PDF*; later, *Save SVG*.
- **Android (version 5):** an entry of the *More* page; the PDF shared to a printer or another app.
- **Code:** `instruments.py` holds the geometry (no Qt, tested); the drawing goes through matplotlib's PDF and SVG
  backends (already used by Céleste), at true scale; the interface only collects the options.

## Steps

| Step | Content |
|---|---|
| Prototype (done) | `instruments.py`: astrolabe plate and rete for any latitude, PDF at true scale, tests against the classic formulas |
| Workshop 1 (done, 4.11) | The Workshop window; the **planisphere**, the **equatorial** and **horizontal sundials**; assembly and use sheets in four languages |
| Workshop 2 (done, 4.12) | The complete **astrolabe** (mater, back, unequal hours, rule, alidade, rete on a transparent sheet); the **nocturnal** |
| Workshop 3 | **Horary quadrant**, **vertical declining sundial** (wall orientation measured with the Sun), **noon mark** |

Workshop 3 comes after the first steps of the Android port (4.13 and 4.14).

## Workshop 1

`instruments.py` holds the geometry, `workshop.py` draws the pages (matplotlib, one axis in millimetres per A4 or
Letter page) and writes the explanation sheets from the `workshop` texts of `locales/`. The window, in `ui/observe.py`
(`show_workshop`), takes the place, the time zone and the date of the side panel.

- **Planisphere** — `planisphere(lat, lon, std_offset, year, r_edge, stars, figures, margin)`: azimuthal
  equidistant projection from the visible pole, to `margin` degrees beyond the horizon of the meridian; stars to
  magnitude 4.5, the 88 figures, the ecliptic and the equator; a date ring giving the local sidereal time at 0:00
  standard time of each day of the year; the window of the horizon and the directions around it; the hours at the
  sidereal rate. Since 4.23 the pieces are those of the planispheres of the shops (and of in-the-sky.org): the star
  wheel with the date ring on its rim; a holder folded in two, its front with the window, the directions, the night's
  hours (17 h to 7 h) along its rounded edge facing the dates, the title and the steps; its back with the tab of the
  pin and the glue strips (`workshop.planisphere_holder_outline`). The chart reaches 24° past the horizon, under the
  holder, so that the window ends well inside the hours. Two pages and the sheets; the southern sky is the mirror
  image (east on the right).
- **Equatorial sundial** — `equatorial_dial(lat, lon, std_offset)`: the dial at 90° − |φ|, hours 15° apart shifted
  by the longitude's offset from the time zone; the upper face (lit when the Sun is on the side of the visible pole)
  and the lower face, mirror images, then two wedges.
- **Horizontal sundial** — `horizontal_dial(lat, lon, std_offset, height)`: hour lines and half hours from the
  shadow of the polar style, date lines (solstices, equinoxes, entries of the signs) from the shadow of the nodus,
  whose height puts the noon shadow of the winter solstice near the edge of the dial; the triangular gnomon with its
  sizes.
- **Corrections** — `dial_reading(legal, dst, eot)`: what the dials show at a legal time; the sheets give the
  equation of time on the 1st, 11th and 21st of each month (DE440, through the engine).

Checked by `tests/test_workshop.py`: `tan θ = sin φ tan H`, the nodus and the equinox line; the shadow of the
engine's Sun at eight moments, north and south, on the line of the reading (within 2 × 10⁻⁴ rad) and the equatorial
dial's angle against the Sun's hour angle (0.02°); the date ring against Skyfield's sidereal time (20 s); Vega in the
planisphere's window where the engine puts it (1 mm); the PDF in the four languages.

## Workshop 2

- **Astrolabe** — `plate(lat)` (almucantars every 5°, azimuths every 15°, astronomical twilight, the unequal hours
  of the night, the east and west points), `rete(stars)` (the ecliptic, a circle, graduated degree by degree, and
  the stars brought to the year by `workshop.stars_of_date`), `turn()` (the rete at a sidereal time), `limb_angle()`
  and `limb_reading()` (the hour scale of the limb: apparent solar time), `solar_longitudes(year)` and
  `back_angle()` (the calendar and zodiac rings of the back, the Sun's longitude of each day from DE440),
  `shadow_square(alt)`. Six pages: the front (mater, limb and plate), the rete and the rule on a transparent sheet,
  the back, the alidade with its vanes, then the sheets. The prototype drew the astrolabe as a mirror image (east on
  the right); the east is now on the left and the rete turns clockwise, as on the astrolabes of old, and the southern
  plate is the mirror image.
- **Nocturnal** — `nocturnal(lat, lon, std_offset, year, pointers)`: the date ring gives the pointer's hour angle at
  0:00 standard time of each day; the hour disc turns at the sidereal rate; one tooth per pointer star (Dubhe for
  the Great Bear, Kochab for the Little Bear; Acrux in the south, the disc turning the other way). Three pages and
  the sheets.

Checked by `tests/test_instruments.py` and `tests/test_workshop.py`: east on the left and the sky turning
clockwise; the unequal hours equal at the equinox; the ecliptic a circle; Vega, turned with the rete to the sidereal
time, on the point of its engine altitude and azimuth (0.1 mm); the limb reading of the Sun set on its almucantar
against UT + longitude + equation of time (a minute, north and south); the calendar against the equinox and the
solstice; the nocturnal's reading against the standard time from the pointers' hour angles (two minutes).
