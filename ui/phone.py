"""
ui/phone.py — What a phone tells Céleste: where it is, and where it looks
=========================================================================
- Where it is: Android asks the person before an app reads its position,
  and since Qt 6.6 Qt Positioning no longer asks by itself: the app asks
  for QLocationPermission. location_allowed() does, once; the window's
  geolocation goes on when the answer is yes (gui.geolocate()).
- Where it looks: Qt's rotation sensor (QtSensors' QRotationSensor; on
  Android the rotation vector, the gyroscope, the accelerometer and the
  magnetometer fused), read by the sky map that follows the phone
  (ui/sky.py, the angles turned into a direction by orientation.py).

On a desktop the position needs no permission (Qt answers Granted) and there
is no rotation sensor: the sky map's follow button stays hidden.
"""
import mobile
import qt
from qt.QtCore import QCoreApplication, Qt

QtSensors = getattr(qt, "QtSensors", None)              # not in a desktop build
_LOCATION = getattr(qt.QtCore, "QLocationPermission", None)


def location_allowed(context, go_on, refused, app=None):
    """
    True when the position may be read now. On Android the first time, asks
    for it and returns False: *go_on* runs once the person said yes, *refused*
    once they said no (or had said no before: Android then asks no more).
    *context*: the QObject the answer is delivered to; *app*: the application
    (QCoreApplication.instance()).
    """
    if not mobile.is_android() or _LOCATION is None:
        return True
    app = app or QCoreApplication.instance()
    permission = _LOCATION()
    permission.setAccuracy(_LOCATION.Accuracy.Precise)
    permission.setAvailability(_LOCATION.Availability.WhenInUse)
    status = app.checkPermission(permission)
    if status == Qt.PermissionStatus.Granted:
        return True
    if status == Qt.PermissionStatus.Denied:
        refused()
        return False

    def answered(*_args):
        if app.checkPermission(permission) == Qt.PermissionStatus.Granted:
            go_on()
        else:
            refused()
    app.requestPermission(permission, context, answered)
    return False


def screen_turns(screen):
    """How many quarter turns the screen is turned from the phone's natural position (orientation.quarter_turns)."""
    import orientation
    names = {Qt.ScreenOrientation.PortraitOrientation: "portrait",
             Qt.ScreenOrientation.LandscapeOrientation: "landscape",
             Qt.ScreenOrientation.InvertedPortraitOrientation: "inverted_portrait",
             Qt.ScreenOrientation.InvertedLandscapeOrientation: "inverted_landscape"}
    if screen is None:
        return 0
    current, native = names.get(screen.orientation()), names.get(screen.nativeOrientation())
    if current is None or native is None:
        return 0
    return orientation.quarter_turns(current, native)


class PhoneAim:
    """
    The phone's rotation sensor, started while the sky map follows the phone:
    reading() gives its latest angles (x, y, z in degrees, orientation.py) or
    None before the first one.
    """

    def __init__(self, parent=None):
        self.sensor = None
        if QtSensors is not None:
            sensor = QtSensors.QRotationSensor(parent)
            if sensor.connectToBackend():
                sensor.setDataRate(30)                  # readings a second, where the sensor lets it be set
                self.sensor = sensor
            else:
                sensor.deleteLater()                    # a desktop: none

    def available(self):
        """True when the phone has a rotation sensor."""
        return self.sensor is not None

    def start(self):
        if self.sensor is not None and not self.sensor.isActive():
            self.sensor.start()

    def stop(self):
        if self.sensor is not None and self.sensor.isActive():
            self.sensor.stop()

    def active(self):
        return self.sensor is not None and self.sensor.isActive()

    def reading(self):
        if self.sensor is None:
            return None
        value = self.sensor.reading()
        if value is None or not value.timestamp():
            return None
        return value.x(), value.y(), value.z()
