#!/usr/bin/env bash
# Isolated CI emulator only: replace the observed ANR-prone Google HOME, not the real IME/app.
# Do this ONCE before instrumentation. No error-dialog hiding, input dismissal, data clears or retries.
set -euo pipefail

if [[ "${1:-}" != '--installed' ]]; then
  chmod +x gradlew
  ./gradlew assembleDebug assembleDebugAndroidTest --stacktrace 2>&1 | tee "$RUNNER_TEMP/dkord-device-build.log"
  adb install -r -t app/build/outputs/apk/debug/app-debug.apk
  adb install -r -t app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk
fi

component='app.dkord.test/app.dkord.EmulatorHomeActivity'
adb shell cmd package set-home-activity --user 0 "$component"
actual="$(adb shell cmd package resolve-activity --brief -a android.intent.action.MAIN -c android.intent.category.HOME | tr -d '\r' | tail -n 1)"
if [[ "$actual" != "$component" ]]; then
  echo "::error title=CI HOME fixture not applied::Expected $component but resolved $actual"
  exit 1
fi
# The prior real failure identified this exact external process in dumpsys, not Dkord.
# Only after replacing HOME, stop that old launcher once so it cannot leave an ANR overlay.
launcher="$(adb shell pm path com.google.android.apps.nexuslauncher | tr -d '\r')"
if [[ "$launcher" == package:* ]]; then
  adb shell am force-stop --user 0 com.google.android.apps.nexuslauncher
fi
adb shell am start -W -a android.intent.action.MAIN -c android.intent.category.HOME
printf 'CI idle HOME verified: %s; real IME/window assertions remain mandatory.\n' "$actual"
