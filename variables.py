"""
variables.py — Famous variable stars: the minima of Algol
=========================================================
Algol (β Persei), the Demon Star, is an eclipsing binary: every 2 days
20 h 49 min its fainter companion passes in front of the bright star, which
fades from magnitude 2.1 to 3.4 in about five hours and comes back in five
more, a change the eye follows against the stars around it.

The minima come from a linear ephemeris fitted to the 39 CCD and
photoelectric minima of 2006–2017 in the Lichtenknecker Database of the BAV
(Bundesdeutsche Arbeitsgemeinschaft für Veränderliche Sterne; residuals of
7 minutes, rms):

    Min I = HJD 2458065.6768 + 2.8673382 E

The BAV/Kreiner elements of 2017 (HJD 2452500.1750 + 2.8673390 E) give the
same minima to within 6 minutes in 2026. Algol's period wanders slowly (a
third star, the stars' magnetic cycles): the GCVS elements (HJD 2445641.5135
+ 2.86730431 E) are now four hours early, and the times here hold to about
half an hour (UNCERTAINTY_MIN). The heliocentric times are brought to the
Earth: the light crosses the Earth's orbit in up to 8 minutes either way.

No Qt: Tonight (ui/tonight.py) and the calendar (astro_calendar.py) use it.
"""
import math

import numpy as np
from skyfield.api import Star, wgs84

from engine import AstroEngine, _sky

ALGOL = {
    "name": "Algol", "designation": "β Per",
    "ra": 3.136148, "dec": 40.955647,               # J2000 (hours, degrees)
    "epoch": 2458065.6768, "period": 2.8673382,     # HJD of a primary minimum, days
    "bright": 2.1, "faint": 3.4,                    # V magnitudes, out of eclipse and at minimum
}
UNCERTAINTY_MIN = 30          # how far the predicted minima may be off, minutes
VISIBLE_ALT = 15.0            # the star at least this high at the minimum…
DARK_SUN = -12.0              # …in a sky dark enough to compare it with its neighbours
_LIGHT_DAYS_PER_AU = 499.004784 / 86400.0


def _direction(star):
    """Unit vector towards the star (ICRS)."""
    ra, dec = math.radians(star["ra"] * 15.0), math.radians(star["dec"])
    return np.array([math.cos(dec) * math.cos(ra), math.cos(dec) * math.sin(ra), math.sin(dec)])


def light_time_days(jd, star=ALGOL):
    """
    HJD − JD (days) at the UT Julian days *jd* (number or array): the time
    the star's light takes between the Earth and the Sun's plane across its
    direction, positive when the Earth is on the star's side (it sees the
    eclipse first). Within ±8.3 minutes.
    """
    sky = _sky()
    time = sky["ts"].ut1_jd(jd)
    earth = sky["earth"].at(time).position.au - sky["sun"].at(time).position.au
    return np.tensordot(_direction(star), earth, axes=1) * _LIGHT_DAYS_PER_AU


def minima(start, end, star=ALGOL):
    """The primary minima between the UT datetimes *start* and *end*, as seen
    from the Earth: UT datetimes (as *start*: naive or aware)."""
    jd0, jd1 = AstroEngine.julian_day(start), AstroEngine.julian_day(end)
    period, epoch = star["period"], star["epoch"]
    first = math.ceil((jd0 - 0.01 - epoch) / period)      # 0.01 d: room for the light time
    last = math.floor((jd1 + 0.01 - epoch) / period)
    if last < first:
        return []
    hjd = epoch + period * np.arange(first, last + 1)
    jd = hjd - light_time_days(hjd, star)
    jd = hjd - light_time_days(jd, star)                    # the light time of the instant itself
    dates = [AstroEngine._jd_to_datetime(float(j), start) for j in np.atleast_1d(jd)]
    return [d for d in dates if start <= d < end]


def visible_minima(start, end, lat, lon, elevation_m=0.0, star=ALGOL, min_alt=VISIBLE_ALT,
                   dark_sun=DARK_SUN):
    """
    The minima between *start* and *end* worth watching from the place: the
    star at least *min_alt* high and the Sun *dark_sun* below the horizon at
    the minimum.

    Returns:
        list[dict]: name, date (UT, as *start*), alt, az of the star, sun
        (the Sun's altitude), all in degrees.
    """
    dates = minima(start, end, star)
    if not dates:
        return []
    sky = _sky()
    jds = np.array([AstroEngine.julian_day(d) for d in dates])
    here = (sky["earth"] + wgs84.latlon(lat, lon, elevation_m=elevation_m)).at(sky["ts"].ut1_jd(jds))
    alt, az, _ = here.observe(Star(ra_hours=star["ra"], dec_degrees=star["dec"])).apparent().altaz()
    sun = here.observe(sky["sun"]).apparent().altaz()[0].degrees
    return [{"name": star["name"], "date": date, "alt": float(a), "az": float(z), "sun": float(s)}
            for date, a, z, s in zip(dates, alt.degrees, az.degrees, sun)
            if a >= min_alt and s <= dark_sun]
