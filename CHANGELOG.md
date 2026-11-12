# Changelog

What is new in each version of Céleste, the latest first.

A version's section becomes, as it is, the note of its GitHub Release and the text the update window shows to users.
Write for them: short sentences, as dashes, no bold or code (the window of versions 4.4 and earlier would show the
markup as it is), about 800 characters at most (the window cuts the rest, GitHub does not). See the wiki page
"Publier une version".

## 4.12

- Workshop: a complete planispheric astrolabe (plate of your latitude, rete of the stars of the year, rule, back
  with calendar and shadow square, alidade) and a nocturnal that tells the time at night from the Great Bear.
- The Workshop window has its own place, time zone and date: no need to change the side panel.
- Location: pick your place on a map, when Windows does not let Céleste use its location service.
- Targets: a sky map of the night as uptonight draws it, in Céleste's colours, with the numbered targets, the
  planets, the comets and the header of the night; in a large window, the legend shows or hides each target.

## 4.11

- New Workshop, from the side panel: instruments to print at true scale, cut out and assemble, computed for your
  place.
- A planisphere of your sky, with its date ring set for your longitude.
- An equatorial sundial and a horizontal sundial that read your time zone's hours, with the curves of the solstices
  and the equinoxes.
- Each comes with sheets in your language: how to assemble it, how to use it, the astronomy behind it, the table of
  the equation of time and an example computed for the chosen date.

## 4.10

- New Targets tab: what to observe or photograph tonight from here, among the Messier, Caldwell or 12,700 NGC and
  IC objects, with your constraints (altitude, airmass, size, time in the night, distance to the Moon), the Moon and
  the planets, and the comets brighter than magnitude 12.
- Your own targets, a to-do list and a done list; an altitude chart of the night; export as text, JSON or image.
- Settings: the obstacles of your horizon (also drawn on the sky map), the temperature and the pressure.
- The settings tab is now a gear icon, at the end of the tabs.

## 4.9

- Sky map: 8,400 stars down to magnitude 6.5 instead of 513, and the figures of all 88 constellations, each of which
  can be found by its name.
- The sky map now shows the sky as you see it: north up, east on the left.
- The map of the Solar System has its own tab, and the Planets tab shows all the bodies at once.
- Comet C/2025 A6 (Lemmon) joins the comets followed.

## 4.8

- History: the History button (Ctrl+H) lists your last calculations and brings one back in a click, with its date,
  place and time zone.
- Jupiter: its data window shows the four Galilean moons, with those passing in front of the planet, behind it or
  in its shadow. Saturn: the tilt and the size of its rings.
- Sky map: type the name of a star, a planet, a Messier object or a constellation to find it, circled in gold.
- The preloaded favourites are named in your language (London, Londres…) and know their elevation.
- A field reached with the keyboard is outlined in gold again.

## 4.7.1

- Updates hold up when GitHub answers badly (errors 503 or 504, as during its incidents): Céleste asks two ways,
  through the GitHub API and through github.com, three times before giving up.
- When an update cannot be downloaded, Céleste now says why, instead of closing the progress window without a word,
  and offers the release page to install it by hand.

## 4.7

- Deep sky: the 110 Messier objects (nebulae, clusters, galaxies) on the sky map, with their card; a switch turns
  them off.
- Tonight lists the best deep-sky objects of the night and the visible passes of the space stations.
- Satellite passes: the International Space Station, Tiangong and Hubble over the next 10 days, with the time they
  appear, their highest point and when they vanish into the Earth's shadow. The orbits are downloaded every two days.
- Release notes, code and documentation are now written in English; the interface stays in French, English,
  Spanish and German.

## 4.6

- Place search: type the name of a city (34,000 cities, no connection needed); latitude, longitude and elevation
  are filled in.
- Tonight, at the top of the ephemeris: the dark night, the Moon, the visible planets and the next three events
  visible from your place.
- Monthly lunar calendar: the phase, rise and set of the Moon each day.
- The orrery of the Planets tab is animated, from one day to one year per step.
- Comets: C/2026 O1, 45P, C/2026 C1 and 19P, from 2025 to 2031, in the planets, the sky map and the events.

## 4.5

- Meteor showers in the Events tab: the peaks of the 13 major showers of the year (Quadrantids, Lyrids, Perseids,
  Orionids, Leonids, Geminids…), from the calendar of the International Meteor Organization.
- For each, the night of the peak seen from your place: best moment, height and direction of the radiant, meteors
  per hour under a dark sky, and the Moon's interference.
- A "Meteor showers" filter, and export to your calendar like the other events.
- Release notes, like this one, are now in French.

## 4.4

- Lighter updates: 82 MB instead of 111. The JPL ephemeris (32 MB) is no longer in the installer; Céleste
  downloads it once, at the first launch, and checks it.
- An existing installation keeps its ephemeris: nothing is downloaded again.
- Closed data windows and maps no longer stay in memory.

## 4.3.1

- Badges and a Buy Me a Coffee button on the repository page.
- The silent update writes its log to %TEMP%\Celeste-update\install.log.

## 4.3

- Automatic update: Céleste looks for a new version at startup and installs it without a full reinstall
  (Settings › About).
- Sedna joins the minor planets, which carry their Minor Planet Center number: (136199) Eris.
- Symbols for Eris, Haumea, Makemake and Sedna.
- A wiki of how-to pages for changing Céleste.

## 4.2

- Events seen from your place: visible in the evening, the morning or all night, and occultations by the Moon.
- Local circumstances of eclipses: contact times, magnitude, length of totality.
- Minor planets: Ceres, Pallas, Juno, Vesta, Pluto, Eris, Haumea, Makemake.
- Conjunctions of the Moon, perigees, apogees and supermoons; equinoxes, solstices, perihelion and aphelion.
- Data window of a body, sorting in the Planets tab, links in the settings, safer geolocation, installer logo.

## 4.1

- JPL DE440 engine: positions within 0.07″ of JPL Horizons, rises and sets to the second, time zones and summer
  time of the place.
- Coordinates tab, stars brought to the date, true GPS position.
- Conjunctions, oppositions and elongations to the minute, with their map; eclipses projected on the Earth.
- Preferences and favourites in the user's folder; standalone Windows application.

Earlier versions are described by the history of the repository.
