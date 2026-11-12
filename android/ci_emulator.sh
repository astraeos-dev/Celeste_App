#!/usr/bin/env bash
# Run by the Android workflow inside the emulator step: installs the APK, starts it,
# keeps the system log (logcat) and checks that main.py printed its self-test line.
# Usage: android/ci_emulator.sh <apk> <package>
set -u
apk="$1"
package="$2"
adb install -r "$apk" || { echo "::error::adb install failed"; exit 1; }
adb logcat -c
adb shell monkey -p "$package" -c android.intent.category.LAUNCHER 1
sleep 45
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
if grep -q "android self-test OK" logcat.txt; then
  echo "Céleste started on the emulator"
else
  echo "::error::no self-test line in logcat: the app did not start (see logcat.txt)"
  exit 1
fi
