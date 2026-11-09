# Dkord for PC

**The Dkord phone experience, rendered natively for Windows, macOS and Linux.**

The phone owns the design: five destinations, the same red/near-black Material
palette, English/Hindi resources, Roboto/Devanagari fonts, music shelves and
mini/full player. PC widths use a navigation rail or sidebar; compact windows use
bottom navigation. This is a real Qt application, not an APK, website or mockup.

## Version 0.10.1

This version is being prepared for the requested **Android + PC release**. Release
publication requires passing exact-source Android tests, six native OS/CPU builds,
actual frozen Windows32 captures, real old-to-new installer fixture checks and the original Android signing identity. The
release page is [Dkord releases](https://github.com/DeepuExplainsAi/dkord/releases).
Historical v0.10.0 and Desktop Preview2 assets are preserved, not replaced.

### Included

- Phone-derived Home/chips/curated shelves, search scopes/suggestions/corrections
  and music continuations, collection headers/queues, dated New Releases with the
  same category and 24-hour/7-day/10-day windows.
- Library, likes, playlists, Listen Again, Downloads and Mashup Studio. Online
  catalogue songs go directly into Studio preparation; no manual download first.
  Device files and existing private downloads also work. Real FFmpeg handles
  millisecond ranges, ordered clips, mixed sample rates and AAC/M4A export.
- **Download in Dkord** keeps a managed private copy; **Download to device** adds an
  explicitly chosen accessible copy. Removing a private copy does not remove
  independent device copies or original Studio inputs.
- A global **Listen Together** hub, also reachable from Library and the player.
  Rooms apply to supported songs and playlists, not a special song. Host-only
  default; creator grants/revokes selected members or everyone. Permission grants
  do not opt listeners in or start audio. Shared public test vectors exercise
  Android/native canonical JSON, Unicode, P-256/DER signatures and two-member grants.
- Artwork, timed lyric highlighting/seeking, queue management, shuffle/repeat,
  speed, volume, saved playback position, the phone's sleep presets/fade/end-of-track
  option, and a separate optional native video player. Closing video never
  automatically resumes background music.
- Local-only **Copy playback diagnostics**, with no repository/issue navigation,
  upload, song titles, signed URLs, file paths, queries or room codes. About is
  concise and includes **© 2026 dKORD**.

### Updates and data

Use the installer matching the **installed app's OS/CPU profile**. Install over the
old app; do **not** uninstall or clear data. Windows x86 and x64 retain their own
existing installation directories/IDs, avoiding mixed Qt5/Qt6 DLLs. The library
remains at `platformdirs.user_data_path("Dkord", "Dkord", roaming=False)`, protected
by the same single-instance lock. SQLite, settings, queues, playlists, downloads
and Studio sources are outside the executable directory. Corrupt/newer data is
refused without a destructive reset.

The old PC previews shipped with **no trusted update key**. They cannot learn a
new trust root through their existing updater: the first 0.10.1 PC setup must be
run once **over the old installation**. No reinstall/data deletion is required.

0.10.1 pins the **existing v0.10.0 APK's public signing identity**, verified against
its immutable APK SHA-256 and `apksigner` report. No replacement key is generated.
`assets/update-trust-provenance.json` records the public-only verification receipt.
Future common `vX.Y.Z` releases can carry a format-2 desktop manifest signed by
that same protected identity, with explicit desktop-protocol domain separation.
The app verifies signature, exact OS/CPU/installer kind, version, bounded size,
SHA-256 and native file format before a consent-based install. It never offers an
APK as a PC update. Legacy pinned Ed25519 desktop channels remain verified and
separate. All four worker pools drain before update restart releases the data lock.

**Application update verification is not Windows Authenticode or Apple Developer
ID/notarization.** Those OS publisher certificates are not configured; do not
bypass OS security warnings or describe these packages as notarized.

### Supported native profiles

| Profile | Runtime | Package |
|---|---|---|
| Windows x64, Windows 10/11 | Python 3.11, Qt6/PyQt6, PyAV | `.exe` |
| Windows x86, Windows 10 / WoW64 | Genuine 32-bit Python 3.11, Qt5/PyQt5, Node22 ia32; FFmpeg/ffprobe8.1.3 from pinned source | `.exe` |
| macOS Intel / Apple Silicon, macOS13+ | Matching native Qt6/PyAV | Separate `.pkg` |
| Linux x64 / arm64, glibc2.39+ | Matching native Qt6/PyAV | Separate `.deb` and `.AppImage` |

Windows7/8 and unlisted CPUs are not claimed. The genuine Win32 profile does not
bundle unavailable Qt6/PyAV Win32 wheels or the obsolete 2019 FFmpeg4.2.2 wheel.
Linux needs system GL/EGL, DBus, xkbcommon/XCB and an appropriate audio/display stack.

## Acceptance boundaries

**Physical install-over**, heard audio/video, live-provider restrictions,
OS-specific media-key integration and live multi-phone/PC relay sessions still
need device acceptance. Native fixture/codec/UI tests and cross-language vectors
are not a physical-device or live-provider pass. Enhanced phone language/mood/era
radio-ranking equivalence is still being validated; anonymous-provider availability
is not guaranteed. Account sign-in is intentionally unavailable on both clients.

There is **no cloud or automatic phone-to-PC audio sync**. JSON import/export is
metadata, not music bytes. Each device retains its own data. Desktop private data
is a per-user folder, not an Android-style sandbox against other apps of that user.

## Development and proof

```sh
python -m venv .venv
# Activate it, then use the matching profile/lock file.
python -m pip install -r requirements-build.txt -c constraints.lock
PYTHONPATH=. python -m dkord_desktop
python -m pytest tests --junitxml=.artifacts/test-results.xml
python -m dkord_desktop --self-test
python scripts/export_phone_contract.py --check
python packaging/build.py --help
```

Six-host CI installs the immutable Preview2 package, then installs the new
package over it, without uninstalling. The new **installed frozen executable**
reads the unchanged normal user-data path and verifies seeded settings, queue,
likes/history/playlists, both download copies and Studio clip/source bytes, and
decodes the preserved generated audio. Linux exercises **both** `.deb` and
portable `.AppImage` replacement. These are disposable hosted-OS fixtures, not
physical-user or live-provider acceptance.

The release-only Android gate uses the original signed code14 APK, seeds its
actual Room/settings/queue/private download/MediaStore/Studio data through the
same signed instrumentation APK, performs `adb install -r` to code15, and verifies
that the package UID and all those rows/files survive. It never clears data,
uninstalls, hides failures or retries a failing case.

Six-host PR CI is read-only: no signing secrets, release/tag writes or fake search
results. It tests real Qt widgets/codecs, packages native binaries and captures
the actual frozen Win32 app with explicitly labelled generated audio. Source,
bitness, frozen status and image hashes accompany the images. Only a separately
authorized publication job promotes exact-source validated packages. Build outputs,
installers and generated captures belong in artifacts, **never Git**.

Copyright/platform terms apply: import/download/edit only audio you may use.
Bundled Material icons, fonts, Qt and native runtimes retain their licenses and
corresponding-source notices; see [THIRD_PARTY.md](THIRD_PARTY.md).
