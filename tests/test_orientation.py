"""
tests/test_orientation.py — Where the phone looks (orientation.py, v4.22)

A pose of the phone (where its back and its top point) is turned into what
Android's rotation vector sensor gives (a quaternion), then into Qt's three
angles by the steps of Qt's Android plugin (qtsensors,
src/plugins/sensors/android/androidrotation.cpp: Android's
getRotationMatrixFromVector() then getOrientation()); orientation.py must
find the pose again from those angles.
"""
import math
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import orientation as orient  # noqa: E402

EAST, NORTH, UP = (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)


def _vec(alt, az):
    """Unit vector (east, north, up) of an altitude and an azimuth (degrees)."""
    a, z = math.radians(alt), math.radians(az)
    return (math.cos(a) * math.sin(z), math.cos(a) * math.cos(z), math.sin(a))


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _pose(back, top):
    """The phone's rotation matrix (rows: east, north, up; columns: its x, y, z axes)."""
    z = tuple(-v for v in back)
    x = _cross(top, z)
    return [[x[i], top[i], z[i]] for i in range(3)]


def _quaternion(m):
    """(q0, q1, q2, q3) of a rotation matrix, scalar first (as Android's rotation vector: values[3], values[0..2])."""
    trace = m[0][0] + m[1][1] + m[2][2]
    if trace > 0:
        s = math.sqrt(trace + 1.0) * 2
        return (0.25 * s, (m[2][1] - m[1][2]) / s, (m[0][2] - m[2][0]) / s, (m[1][0] - m[0][1]) / s)
    if m[0][0] > m[1][1] and m[0][0] > m[2][2]:
        s = math.sqrt(1.0 + m[0][0] - m[1][1] - m[2][2]) * 2
        return ((m[2][1] - m[1][2]) / s, 0.25 * s, (m[0][1] + m[1][0]) / s, (m[0][2] + m[2][0]) / s)
    if m[1][1] > m[2][2]:
        s = math.sqrt(1.0 + m[1][1] - m[0][0] - m[2][2]) * 2
        return ((m[0][2] - m[2][0]) / s, (m[0][1] + m[1][0]) / s, 0.25 * s, (m[1][2] + m[2][1]) / s)
    s = math.sqrt(1.0 + m[2][2] - m[0][0] - m[1][1]) * 2
    return ((m[1][0] - m[0][1]) / s, (m[0][2] + m[2][0]) / s, (m[1][2] + m[2][1]) / s, 0.25 * s)


def _qt_reading(back, top):
    """Qt's (x, y, z) for a pose, computed as androidrotation.cpp does from the rotation vector."""
    q0, q1, q2, q3 = _quaternion(_pose(back, top))
    sq_q1, sq_q2, sq_q3 = 2 * q1 * q1, 2 * q2 * q2, 2 * q3 * q3
    q1_q2, q3_q0, q1_q3 = 2 * q1 * q2, 2 * q3 * q0, 2 * q1 * q3
    q2_q0, q2_q3, q1_q0 = 2 * q2 * q0, 2 * q2 * q3, 2 * q1 * q0
    azimuth = math.atan2(q1_q2 - q3_q0, 1 - sq_q1 - sq_q3)
    pitch = math.asin(-(q2_q3 + q1_q0))
    roll = math.atan2(-(q1_q3 - q2_q0), 1 - sq_q1 - sq_q2)
    return -math.degrees(pitch), math.degrees(roll), -math.degrees(azimuth)


def _close(a, b, tol=1e-6):
    return all(abs(x - y) < tol for x, y in zip(a, b))


def _angle(a, b):
    """The difference of two angles in degrees, wrapped to [0, 180]."""
    return abs((a - b + 180) % 360 - 180)


# poses: (where the back points: alt, az), (where the top points). Held
# exactly upright, Qt's angles lose the azimuth (Android's getOrientation()
# meets the gimbal lock there), which a hand never holds that still: the
# upright poses look half a degree up.
POSES = {
    "upright, north": ((0.5, 0), _vec(89.5, 180)),
    "upright, east": ((0.5, 90), _vec(89.5, 270)),
    "upright, south": ((0.5, 180), _vec(89.5, 0)),
    "upright, west": ((0.5, 270), _vec(89.5, 90)),
    "30 degrees up, south-west": ((30, 225), _vec(60, 45)),
    "70 degrees up, north-east": ((70, 45), _vec(20, 225)),
    "below the horizon, south": ((-20, 180), _vec(70, 180)),
}


@pytest.mark.parametrize("name", POSES)
def test_the_pose_found_again_from_qt_s_angles(name):
    (alt, az), top = POSES[name]
    back = _vec(alt, az)
    x, y, z = _qt_reading(back, top)
    assert -90 <= x <= 90 and -180 <= y <= 180 and -180 <= z <= 180   # Qt's ranges
    found_back, found_up = orient.directions(x, y, z)
    assert _close(found_back, back) and _close(found_up, top)
    found_alt, found_az, turn = orient.aim(found_back, found_up)
    assert found_alt == pytest.approx(alt, abs=1e-6) and _angle(found_az, az) < 1e-6
    # held with no tilt to the side: the turn puts the horizon faced at the bottom
    assert _angle(turn, 180 - az) < 1e-4


def test_lying_flat():
    back, up = orient.directions(0, 0, 0)
    assert _close(back, (0, 0, -1)) and _close(up, NORTH)
    assert orient.aim(back, up)[0] == pytest.approx(-90)


def test_the_zenith():
    """Back up to the zenith: the horizon at the bottom of the screen is the one the person faces."""
    facing_north = _qt_reading(UP, tuple(-v for v in NORTH))          # the top of the phone to the south
    alt, _az, turn = orient.aim(*orient.directions(*facing_north))
    assert alt == pytest.approx(90) and _angle(turn, 180) < 1e-4       # north at the bottom
    facing_east = _qt_reading(UP, (-1.0, 0.0, 0.0))
    assert _angle(orient.aim(*orient.directions(*facing_east))[2], 90) < 1e-4


def test_the_declination():
    """The sensor's north is the magnetic one: 2° east of it, a magnetic azimuth of 0 is 2°."""
    back, up = orient.directions(*_qt_reading(_vec(10, 0), _vec(80, 180)))
    alt, az, turn = orient.aim(back, up, declination=2.1)
    assert alt == pytest.approx(10) and az == pytest.approx(2.1)
    assert _angle(turn, 180 - 2.1) < 1e-4
    assert orient.aim(back, up, declination=-11.0)[1] == pytest.approx(349.0)


def test_a_phone_on_its_side():
    """Turned a quarter counterclockwise (its top to the left), Android turns the screen: its up is the phone's x."""
    assert orient.quarter_turns("landscape") == 1
    assert orient.quarter_turns("inverted_landscape") == 3
    assert orient.quarter_turns("inverted_portrait") == 2
    assert orient.quarter_turns("landscape", native="landscape") == 0                # a tablet
    assert orient.quarter_turns("portrait", native="landscape") == 3
    west = (-1.0, 0.0, 0.0)
    reading = _qt_reading(NORTH, west)             # facing north, upright, the phone's top to the west
    back, up = orient.directions(*reading, turns=1)
    assert _close(back, NORTH) and _close(up, UP)
    assert _angle(orient.aim(back, up)[2], 180) < 1e-4
    back, up = orient.directions(*_qt_reading(NORTH, (1.0, 0.0, 0.0)), turns=3)
    assert _close(up, UP)
    back, up = orient.directions(*_qt_reading(_vec(0.5, 0), _vec(-89.5, 0)), turns=2)   # upside down
    assert _close(up, _vec(89.5, 180))


def test_steady():
    steady = orient.Steady(weight=0.5)
    back, up = steady.add(_vec(0, 0), UP)
    assert _close(back, _vec(0, 0)) and _close(up, UP)
    for _ in range(30):                                         # the phone now held at 10° up
        back, up = steady.add(_vec(10, 0), _vec(80, 180))
    assert orient.altitude_azimuth(back)[0] == pytest.approx(10, abs=1e-3)
    assert abs(sum(a * b for a, b in zip(back, up))) < 1e-9    # still square
    back, _up = steady.add(_vec(0, 180), UP)                    # turned round at once: taken whole
    assert _close(back, _vec(0, 180))
    halfway = orient.Steady(weight=0.5)
    halfway.add(_vec(0, 0), UP)
    back, _up = halfway.add(_vec(20, 0), _vec(70, 180))
    assert orient.altitude_azimuth(back)[0] == pytest.approx(10, abs=0.01)
    halfway.reset()
    assert halfway.back is None
