"""
orientation.py — Where the phone looks, and how the sky map turns with it
=========================================================================
Qt's rotation sensor (QRotationSensor; on Android the rotation vector, where
the gyroscope, the accelerometer and the magnetometer are fused) gives three
angles x, y and z in degrees. From the phone lying flat, screen up, its top
to the magnetic north, they turn it about its z axis (out of the screen) by
z, then about its x axis (to the right of the screen) by x, then about its y
axis (to the top of the screen) by y, each counterclockwise seen from the tip
of the axis: in the frame of the place (east, north, up), the phone's axes
are the columns of Rz(z)·Rx(x)·Ry(y). (Qt's Android plugin computes them from
Android's own rotation matrix, androidrotation.cpp: tests/test_orientation.py
goes through the same steps.) Held exactly upright, the angles lose the
azimuth, as Android's getOrientation() meets the gimbal lock there; a hand
never holds a phone that still.

From them:
- where the back of the phone points (its camera: what one sees through the
  phone held up to the sky), as an altitude and an azimuth counted from the
  true north once the magnetic declination of the place is added (geomag.py);
- how much the sky map turns so that the screen's up is the sky's up there:
  holding the phone upright and facing north, the map is upside down (north
  at the bottom, the zenith above it), facing south it is as drawn.

Android turns the screen a quarter at a time when the phone is turned on its
side: the screen's up is then another of the phone's axes (quarter_turns()).

No Qt here.
"""
import math

# Qt's screen orientations, each a quarter turn counterclockwise from the one
# before, as Qt's Android plugin names Android's rotations (androidjnimain.cpp)
ORIENTATIONS = ("portrait", "landscape", "inverted_portrait", "inverted_landscape")


def quarter_turns(screen, native="portrait"):
    """
    How many quarter turns counterclockwise the phone is turned from its
    natural position, from the screen's orientation and the screen's natural
    one (Qt's names, without "Orientation": "portrait", "landscape"...).
    """
    return (ORIENTATIONS.index(screen) - ORIENTATIONS.index(native)) % 4


def phone_axes(x, y, z):
    """The phone's x, y and z axes, unit vectors (east, north, up), from the sensor's angles."""
    a, b, c = (math.radians(v) for v in (z, x, y))
    ca, sa, cb, sb, cc, sc = math.cos(a), math.sin(a), math.cos(b), math.sin(b), math.cos(c), math.sin(c)
    # Rz(a)·Rx(b)·Ry(c), by columns
    return ((ca * cc - sa * sb * sc, sa * cc + ca * sb * sc, -cb * sc),
            (-sa * cb, ca * cb, sb),
            (ca * sc + sa * sb * cc, sa * sc - ca * sb * cc, cb * cc))


def directions(x, y, z, turns=0):
    """
    (back, up): where the back of the phone points and where the screen's up
    points, unit vectors (east, north, up) in the magnetic frame. *turns*:
    quarter_turns() of the screen.
    """
    ex, ey, ez = phone_axes(x, y, z)
    back = tuple(-v for v in ez)
    angle = turns * math.pi / 2
    up = tuple(math.sin(angle) * a + math.cos(angle) * b for a, b in zip(ex, ey))
    return back, up


def _unit(v):
    norm = math.sqrt(sum(c * c for c in v))
    return tuple(c / norm for c in v)


def altitude_azimuth(v, declination=0.0):
    """Altitude and azimuth (from the true north, eastwards), degrees, of a magnetic (east, north, up) vector."""
    east, north, up = _unit(v)
    return (math.degrees(math.asin(max(-1.0, min(1.0, up)))),
            (math.degrees(math.atan2(east, north)) + declination) % 360.0)


def aim(back, up, declination=0.0):
    """
    Where the phone looks and the sky map's turn: (altitude, azimuth, turn) in
    degrees, the azimuth from the true north, the turn counterclockwise, the
    one that puts the screen's up along the sky map toward the sky above the
    point looked at (charts.sky_xy: the zenith in the middle, east on the
    left when north is up).
    """
    from charts import sky_xy
    alt, az = altitude_azimuth(back, declination)
    x0, y0 = sky_xy(alt, az)
    ahead = _unit(tuple(b + 1e-3 * u for b, u in zip(back, up)))     # a step toward the screen's up
    x1, y1 = sky_xy(*altitude_azimuth(ahead, declination))
    turn = 90.0 - math.degrees(math.atan2(y1 - y0, x1 - x0))
    return alt, az, turn % 360.0


class Steady:
    """
    The phone's two directions, smoothed from one reading to the next: a hand
    shakes, and so does a sensor. *weight*: the share of each new reading.
    """

    def __init__(self, weight=0.35):
        self.weight = weight
        self.back = self.up = None

    def add(self, back, up):
        """A new reading; returns the smoothed (back, up), up kept square to back."""
        if self.back is None or sum(a * b for a, b in zip(self.back, back)) < 0.5:
            self.back, self.up = _unit(back), _unit(up)          # the first, or a sudden turn: taken whole
        else:
            w = self.weight
            self.back = _unit(tuple(a + w * (b - a) for a, b in zip(self.back, back)))
            mixed = tuple(a + w * (b - a) for a, b in zip(self.up, up))
            along = sum(a * b for a, b in zip(mixed, self.back))
            self.up = _unit(tuple(m - along * b for m, b in zip(mixed, self.back)))
        return self.back, self.up

    def reset(self):
        self.back = self.up = None
