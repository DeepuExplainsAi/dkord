# Dkord Desktop0.10.0 Preview2 — genuine Windows32 x86 + actual app screenshots

## New Windows32 compatibility build
Download **Dkord-desktop-v0.10.0-windows-x86.exe** for a **32-bit Windows10 PC**, or an x86 process under WoW64. Windows7/8 are NOT supported by this Python3.11/Node22 profile. Windows11 has no 32-bit OS edition; x86 applications may run under its compatibility layer.

This is a real 32-bit Python/PyInstaller app with **Qt5 widgets and Windows multimedia**, a bundled Node22 ia32 runtime, and **FFmpeg8.1.3 compiled natively for x86** from a pinned/digest-verified source. Qt6/PyAV have no Win32 wheels; an x64 file has NOT been renamed as x86. The obsolete FFmpeg4.2.2 shipped in the usual Win32 imageio wheel is NOT used or bundled. Real app/Node/FFmpeg PE payload architecture and native execution are checked before packaging.

The x86 build shares the real player/library/Studio widget code and stable per-user data schema. Its executable directory, installer ID and shortcuts are separately named **Dkord-x86 / Dkord (32-bit)** so it does not overwrite an existing x64 installation or mix Qt5/Qt6 DLLs. The original x64 installer identity/path stays unchanged. Both use the same single-instance/data lock: close one before opening the other. Do not uninstall/clear data to test an upgrade.

## What the computer app looks like
**windows-x86-player.png** and **windows-x86-studio.png** are captured from the **actual frozen 32-bit Windows application**, not AI pictures, browser mockups or a fabricated Windows desktop. They show the actual window contents with isolated, locally generated audio samples. No user's library, account, provider response or private data is used. `windows-x86-screenshot-proof.json` records the source SHA, actual Windows/process/Qt/frozen profile and PNG hashes/dimensions. These are sample tones, not live catalogue results.

## Existing platforms preserved
Windows x64, Intel/Apple Silicon Mac, Linux x64/arm64 deb/AppImage previews are included separately. Existing Qt6/PyAV runtime profiles remain on those targets. Linux baseline remains glibc2.39/Ubuntu24.04-class; macOS13+; Windows10/11 x64. Original Android **v0.10.0/code14 remains the stable latest release**, with its original APK/key/tag/assets unchanged. This desktop prerelease contains no APK and is not marked latest.

## Validation and limits
Publication requires successful same-head six-host native CI: **at least36 actual cases/all3 required classes on every host**, no skips/failures/errors, source entry + actual frozen/codec/package/AppImage smoke, exact source/version/profile and package hashes. Win32 is executed as a **real32-bit process on an x64 Windows CI host**, not a physical32-bit Windows10 hardware pass. The unchanged Android features additionally require their full regression workflow to pass at the exact source head (432 JVM +38 Android emulator cases). SHA256SUMS covers every native package, preview receipt and screenshot.

**Development previews only:** no Windows Authenticode or trusted Apple Developer ID/notarization. Qt5 is the legacy Win32 UI compatibility profile; do not treat it as a newly supported Qt6 Win32 port. Production desktop update trust keys remain empty and refuse untrusted installs. Full Android parity, desktop Listen Together, enhanced recommendation parity, optional video, timed lyrics, full EN/HI/OS-media integration and physical installation/update-over/live-provider/audio-device acceptance remain open. Do not disable OS security to call these trusted production releases.

Private files still consume disk; each device owns its local media. JSON transfers metadata, not audio; no cloud phone-to-PC sync. Use only media you have permission to access/edit. The exact corresponding FFmpeg source/license/build flags are bundled in the package's license receipts. No previous publication authorization is replayed, and this publication does not merge a pull request.
