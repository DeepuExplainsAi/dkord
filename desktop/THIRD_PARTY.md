# Native desktop license and source notices

Dkord desktop source is **GPL-3.0-only**, matching the repository [LICENSE](../LICENSE). Copyright belongs to the original contributors; third-party runtime copyrights remain theirs. This notice is not a claim of legal review or a replacement for corresponding-source distribution.

| Component | Purpose | License / exact-source entry point |
|---|---|---|
| Python3.11 | Application runtime | PSF; https://github.com/python/cpython/tree/3.11 |
| PyQt6 / Qt6.10.2 | Native widgets and multimedia | GPL-3.0 / Qt open-source terms; https://pypi.org/project/PyQt6/6.10.2/ and https://github.com/qt/qtbase/tree/v6.10.2 |
| yt-dlp2026.10.26 | Public provider metadata/audio | Unlicense; https://github.com/yt-dlp/yt-dlp/tree/2026.10.26 |
| yt-dlp-ejs0.8.0 | Bundled signature-challenge JavaScript runtime support | Unlicense/MIT/ISC; https://github.com/yt-dlp/ejs |
| ytmusicapi1.12.3 | Anonymous public music catalogue | MIT; https://github.com/sigma67/ytmusicapi/tree/1.12.3 |
| imageio-ffmpeg0.8.1 / bundled FFmpeg | Actual audio rendering | BSD wrapper; bundled FFmpeg licenses/configuration vary by wheel and must be preserved; https://github.com/imageio/imageio-ffmpeg/tree/v0.8.1 and https://ffmpeg.org/download.html |
| PyAV16.0.1 / bundled libav | Native audio probing/decoding | BSD wrapper / FFmpeg terms; https://github.com/PyAV-Org/PyAV/tree/v16.0.1 |
| Node22.22.3 | Included OS/CPU-matched JS runtime, no first-play install | MIT and included third-party terms; https://github.com/nodejs/node/tree/v22.22.3 ; full NODE-LICENSE.txt is included in native output |
| cryptography46.0.3 | Ed25519 update verification | Apache-2.0/BSD; https://github.com/pyca/cryptography/tree/46.0.3 |
| Requests / platformdirs and locked transitive dependencies | HTTPS / stable per-user data directory | Respective Apache/MIT/BSD licenses; versions in constraints.lock |
| PyInstaller6.22.3 | Native executable bundling | GPL with bootloader exception; https://github.com/pyinstaller/pyinstaller/tree/v6.22.3 |
| AppImage tooling / Inno Setup | Native preview packages | Respective upstream licenses; https://github.com/AppImage/appimagetool and https://github.com/jrsoftware/issrc |

Before an owner-authorized public release, inspect native dependency reports, include all applicable notices/license texts, provide the required complete corresponding sources/build recipes alongside binary distribution, and complete native signing/notarization. PR preview packages are explicitly unsigned/not notarized and are not an official trusted update channel. No paid service, provider credentials, browser cookies or private signing key is included in this source tree.

Node.js22.22.3's matching complete upstream license is vendored as `assets/Node-LICENSE.txt` (SHA256 `c738ae413cf561f174e34f6961f8ca458aae2369a73640dda6234c629b98bcc4`, source `https://github.com/nodejs/node/blob/v22.22.3/LICENSE`). The builder checks this digest before copying it to `licenses/NODE-LICENSE.txt`; no live license API quota or user first-play runtime download is required.

## Windows x86 compatibility profile
- **PyQt5 5.15.11 / Qt5 5.15.2 / PyQt5-sip12.20.0**: legacy Win32 native widgets/multimedia. GPL-3.0 / upstream Qt open-source terms; PyQt source at https://pypi.org/project/PyQt5/5.15.11/ and corresponding Qt modules at https://github.com/qt/qtbase/tree/v5.15.2, https://github.com/qt/qtmultimedia/tree/v5.15.2 and https://github.com/qt/qtsvg/tree/v5.15.2. No QtWebEngine/browser is bundled.
- **FFmpeg/ffprobe8.1.3 (native x86 source build)**: configured GPL-3.0-or-later, no nonfree/external codec libraries, local file/pipe protocols only. Exact source commit `1041abdc962f4cc4f394aa8de9dc5236c0c3b9e7`, archive SHA256 `a406fe831cbb605f5fe50e43eb566e502ae63ff3b3206bfa744e4b31b8bb73ac`; complete corresponding source https://codeload.github.com/FFmpeg/FFmpeg/tar.gz/1041abdc962f4cc4f394aa8de9dc5236c0c3b9e7. `licenses/FFmpeg-COPYING.GPLv3` and `licenses/FFmpeg-source.json` preserve the license, source URL/hash, exact configuration and built-binary hashes. The obsolete imageio Win32 FFmpeg4.2.2 is neither used nor bundled.
- The other targets keep their previous Qt6/PyAV/imageio profiles and notices. Bundled Node22.22.3 is CPU matched (`ia32` for Windows x86), with the same vendored/digest-verified upstream Node license.
