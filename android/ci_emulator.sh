#!/usr/bin/env bash
# Run by the Android workflow inside the emulator step: installs the APK, starts it,
# keeps the system log (logcat) and checks that main.py printed its self-test line.
# Usage: android/ci_emulator.sh <apk> <package>
set -u
apk="$1"
package="$2"
# -g: the runtime permissions (the location) granted at install. Otherwise Android's question,
# asked at the first start (4.22), waits for an answer nobody gives here, and while it is shown
# Qt stops the app's timers: the line looked for below would never come
adb install -r -g "$apk" || { echo "::error::adb install failed"; exit 1; }
adb logcat -c
adb shell monkey -p "$package" -c android.intent.category.LAUNCHER 1
# the engine's line comes once the ephemeris is downloaded (32 MB): up to 5 minutes
for _ in $(seq 60); do
  sleep 5
  adb logcat -d > logcat.txt
  if grep -qE "android (engine|window) (OK|FAILED)|android: (ephemeris FAILED|the event loop ended)" logcat.txt; then
    break
  fi
done
sleep 5
adb logcat -d > logcat.txt
echo "--- process"
adb shell pidof "$package" || echo "not running"
echo "--- everything the app's process wrote (but the unpacking), and the crash reports"
pid=$(sed -n "s/.*Start proc \([0-9]*\):$package.*/\1/p" logcat.txt | tail -1)
echo "pid: ${pid:-unknown}"
if [ -n "$pid" ]; then
  grep -E "^\S+ \S+ +$pid " logcat.txt | grep -v "extracting _python_bundle" | tail -250
fi
grep -E " F |DEBUG +:|libc +:|crash_dump|tombstone|Fatal signal|backtrace" logcat.txt | tail -80
grep -E "android (self-test|engine|window)|android: (ephemeris|the event loop)" logcat.txt
# the lite app: its self-test line, then the engine's; the full app: the window's, which
# also says whether the window and a form opened over it fit the phone's screen
if grep -q "android window OK" logcat.txt; then
  if grep "android window OK" logcat.txt | grep -q "fits False"; then
    echo "::error::Céleste's window or a form is wider than the phone's screen (see the line above)"
    exit 1
  fi
  echo "Céleste's window opened on the emulator"
  exit 0
fi
if grep -q "android: ephemeris FAILED" logcat.txt; then
  echo "::error::Céleste could not have the JPL ephemeris: $(grep -m1 -o "ephemeris FAILED.*" logcat.txt)"
  echo "--- the emulator's network"
  adb shell "ping -c 1 -W 5 naif.jpl.nasa.gov" || true
  exit 1
fi
if ! grep -q "android self-test OK" logcat.txt; then
  echo "::error::Céleste did not start (see the lines above and logcat.txt)"
  exit 1
fi
if ! grep -q "android engine OK" logcat.txt; then
  echo "::error::the engine did not run (see the lines above and logcat.txt)"
  exit 1
fi
echo "Céleste's engine ran on the emulator"
