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
echo "--- what the app and the system said about it"
grep -E "python|Python|Qt|qt\.|Céleste|Celeste|AndroidRuntime|FATAL|linker|dlopen|$package" logcat.txt | grep -v "extracting _python_bundle" | tail -200
if grep -q "android self-test OK" logcat.txt; then
  echo "Céleste started on the emulator"
else
  echo "::error::no self-test line in logcat: the app did not start (see logcat.txt)"
  exit 1
fi
