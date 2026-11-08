# Dkord Desktop — native preview

**Music, a private offline library and a real Mashup Studio, built for a laptop screen.**

This is a separate **native Qt/Python desktop client**, not an Android APK in a browser frame. It is under active development; it is **not yet a finished Android-parity, signed or notarized public release**. The Android app and existing official APK/update feed are unchanged by desktop packaging.

## Implemented
- PC sidebar, resizable music tables, queue dock, timeline, native media playback, volume/speed/repeat/shuffle/sleep, saved queue and real local history.
- Real anonymous YouTube Music songs/albums/artists/playlists and explicit broader YouTube search. Song selection is separate from explicit Play all shown; provider errors never become fake demo results.
- Likes, playlists, local search history/pins, Android-compatible Dkord playlist/likes JSON import/export. JSON contains **metadata, not offline audio**.
- **Download in Dkord**: managed user-data folder, not public Music. **Download to device**: additionally save an explicit accessible copy. Already-local bytes are reused offline, failures retain private sources, and removing the private download keeps independent device copies.
- Online Studio sources without manually downloading first, device files or existing offline audio; durable private project sources, millisecond clip ranges/order/preview and **actual FFmpeg AAC/M4A merging**, including different sample rates/channel layouts. Source files are never edited in place; active render snapshots pin their inputs.
- Separate desktop-only update channel with pinned Ed25519 signatures, SHA-256/size/native-format checks and **OS + CPU + installer-kind** routing. No APK substitution or downgrade. Installation does not delete the stable user-data directory.

## Not production-ready / not yet equivalent to Android
- **No official signed desktop release/update key/channel is configured.** `assets/update-keys.json` is intentionally empty. Preview builds refuse untrusted updates; hashes alone are not described as publisher authentication. Windows Authenticode and Apple Developer ID signing/notarization must be configured and verified before trusted public distribution. Never disable OS security to call a preview production-ready.
- Android account sign-in, Listen Together protocol interoperability, enhanced Android language/mood/era radio ranking, optional in-app video, synchronized lyric highlighting and full EN/HI desktop UI/OS-media integration remain acceptance gaps. Native desktop currently has plain/synchronized LRC text, English controls and Unicode search/file/clip input.
- Live-provider/guest restrictions, physical OS installation/update-over/data retention and Linux audio/display compatibility require actual acceptance tests. Fixtures/native CI are not a live music-provider pass.
- There is **no cloud or automatic phone-to-PC audio sync**. Each device keeps its own files; updates retain that device's local data. Desktop managed storage is a private *per-user* folder, not an Android-style per-app sandbox against other apps running as the same user.

## Development
Python3.11, Qt6.10.2, real FFmpeg/PyAV, yt-dlp+bundled EJS and a matching Node22 runtime (included by native packaging). No external music API key, paid service or browser login capture.

```sh
python -m venv .venv
# activate .venv for your shell
python -m pip install -r requirements-build.txt -c constraints.lock
python -m dkord_desktop
python -m pytest tests --junitxml=dist/tests.xml
python -m dkord_desktop --self-test
python packaging/build.py
```

Linux needs glibc2.34+ for x64 (2.39+ for arm64), system GL/EGL, DBus, xkbcommon/XCB, and a supported audio/display stack. CI installs these explicitly and executes real native widget and codec tests. macOS baseline13+; Windows10/11 x64. Unsupported OS/CPU updates are refused, not silently replaced with another build.

Preview native outputs are built in read-only pull-request CI for Windows x64, macOS x64/arm64 and Linux x64/arm64. `.exe`/`.pkg`/`.deb`/`.AppImage` files, reports and hashes belong in Actions artifacts, **never Git**. A successful source test alone is not proof these packages built or installed; see the exact workflow run before claiming readiness.

## Local data and updates
`platformdirs.user_data_path("Dkord", "Dkord", roaming=False)` is stable across versions: Windows LocalAppData, macOS Application Support, Linux XDG data. SQLite/WAL, metadata and audio live there, outside the executable installation folder. Corrupt/newer schemas are refused without reset. Installers do not contain user-data delete scripts. Do not uninstall/clear data to test an update.

A future official desktop tag is `desktop-vX.Y.Z`, distinct from Android's `vX.Y.Z`. The signed manifest must list each real native artifact, exact version/platform/architecture/installer type/size/digest. Publishing requires fresh owner authorization, verified native packages, corresponding-source/license distribution, protected signing secrets and the installed public key. **No publication or signing is performed by the PR-validation workflow.**

Copyright/platform terms still apply: import/download/edit only audio you have permission to use. Dependencies and native runtimes have their own license/source notices; see [THIRD_PARTY.md](THIRD_PARTY.md). No measured search-volume or similarity guarantees are claimed.
