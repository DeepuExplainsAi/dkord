# 180 actual native PC screenshots — v0.10.2

**[Download the complete gallery ZIP](https://github.com/DeepuExplainsAi/dkord/releases/download/v0.10.2/Dkord-PC-screenshots-v0.10.2.zip)** ·
[public source/runtime/PNG manifest](https://github.com/DeepuExplainsAi/dkord/releases/download/v0.10.2/Dkord-PC-screenshots-v0.10.2.json) ·
[verified publication receipt](releases/v0.10.2-publication.md).

Extract the ZIP and open **`index.html`**. Platform buttons filter the gallery;
click any image for the full-resolution original or download that PNG. The
viewer works offline and uses only relative image URLs.

**30 production pages/dialogs/theme/compact states × 6 genuine frozen OS/CPU
builds = 180 original PNGs.** Windows x64 and real x86/32-bit; macOS Intel and
Apple Silicon; Linux x64 and arm64. Exact released source:
`3e71ff57432232641e1e69f3c4b6c2c7a49b9b18`. [All-six actual validation/capture run](https://github.com/DeepuExplainsAi/dkord/actions/runs/42618720890) passed 144
native cases per host and all 30 frozen captures per target, without skips.

Actual application `QWidget.grab` captures use native Windows/cocoa/Linux xcb
plugins, with Xvfb only providing Linux's isolated real X display. Not AI,
phone images, browser-rendered app mockups, retouched or composited originals.
This is hosted-OS execution, **not physical hardware acceptance**.

All 180 originals were strictly source/runtime/byte/SHA/dimension verified and
fully decoded. Visual review used labelled thumbnail contact sheets/full-size
originals; 176 release PNGs are byte-identical to the reviewed corrected parent,
and all 4 differing originals were reopened (tiny native clear-button/caret blink
changes). An actual white-on-white native player-tab issue found in review was
fixed and re-captured before release, with selected/unselected dark/light/AMOLED
rendered-pixel checks. The Linux X11 dependency failure was fixed without hiding
it behind an offscreen screenshot fallback.

Published original archive: **7,474,662 bytes**, SHA-256
`06dfa18b4173d0bdb12fdaf73b3a747bcbeaa2bc4627eaa215f252cd5bc8b4d6`.
The publisher verified and copied these same CI ZIP bytes, **without rezipping**;
its public JSON is identical to the archive's `gallery-manifest.json`.

## Screens in each platform gallery

1. Home / native shelves and navigation
2. Home discovery shelves
3. Search history and separate link entry
4. Songs search results
5. All YouTube search filter
6. Empty YouTube-link input
7. Entered link before submission
8. Exact-ID link preview
9. Invalid-link error
10. Playlist-only guidance
11. Library
12. Liked songs
13. Listen Again history
14. Playlist
15. Downloads
16. Private/device destination chooser
17. Mashup Studio arrangement
18. Millisecond clip editor
19. Online Studio source picker
20. Listen Together create/join hub
21. Full player
22. Player queue
23. Lyrics / honest absence for generated tones
24. Sleep timer
25. Settings
26. About
27. Light theme
28. AMOLED theme
29. Hindi exact-link page
30. Compact responsive PC layout

## Honest sample data and safety

**OFFLINE DEMO:** audio consists of real locally generated sine-tone WAV files;
search/link metadata is an explicitly labelled fixture, not claimed live YouTube
metadata. Preview screenshots do not establish real stream availability or heard
audio. No room is started, no real query is sent, no download is enqueued by a
chooser, no user library is read/reset and no original audio file is used.

Each platform's `gallery-proof.json` records the exact source, version, actual
OS/CPU bitness/Qt/frozen status, screen identity/dimensions and original PNG
SHA-256. Release staging verified all 180 images and all six runtime receipts
before packaging the offline `index.html` gallery and originals into
`Dkord-PC-screenshots-v0.10.2.zip`. A corresponding public JSON manifest and the
common release checksums bind those bytes. Images and native installers remain
CI/release artifacts, not committed bulk binaries.

Normal application launch never activates screenshot fixtures. A screenshot
output must be new/empty; existing directories/files/captures are never replaced.
The legacy two Windows 32 captures and their immutable historical receipts remain
separate and unchanged.
