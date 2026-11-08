#!/usr/bin/env bash
# CI emulator fixture only. Use an installed real keyboard; never fake IME insets or skip tests.
set -euo pipefail

adb shell input keyevent KEYCODE_WAKEUP
adb shell wm dismiss-keyguard
adb shell settings put system screen_off_timeout 2147483647
adb shell settings put secure show_ime_with_hard_keyboard 1

available="$(adb shell ime list -s -a | tr -d '\r')"
current="$(adb shell settings get secure default_input_method | tr -d '\r')"
if [[ -z "$available" ]]; then
  echo 'No real input method installed in the emulator; device validation cannot proceed.' >&2
  exit 1
fi
# The pinned google_apis emulator normally contains AOSP LatinIME. If an image changes,
# only ever use an ID actually listed by that emulator, not an invented component.
keyboard="$(printf '%s\n' "$available" | grep -i 'inputmethod.latin\|LatinIME' | head -n 1 || true)"
if [[ -z "$keyboard" ]]; then
  if grep -Fxq "$current" <<< "$available"; then keyboard="$current"
  else keyboard="${available%%$'\n'*}"
  fi
fi
adb shell ime enable "$keyboard"
adb shell ime set "$keyboard"
actual="$(adb shell settings get secure default_input_method | tr -d '\r')"
hardware="$(adb shell settings get secure show_ime_with_hard_keyboard | tr -d '\r')"
if [[ "$actual" != "$keyboard" || "$hardware" != '1' ]]; then
  echo "Real IME fixture not applied: requested=$keyboard actual=$actual showWithHardware=$hardware" >&2
  exit 1
fi
printf 'Real emulator keyboard: %s; showWithHardware=%s\n' "$actual" "$hardware"
adb shell ime list -s
