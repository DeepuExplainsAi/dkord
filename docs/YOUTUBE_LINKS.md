# Open an exact YouTube link — Android + PC v0.10.2

This separate Android and native Windows/macOS/Linux flow is **included in the
[public v0.10.2 downloads](https://github.com/DeepuExplainsAi/dkord/releases/tag/v0.10.2)**. No old APK, installer, tag or asset was replaced.
[Complete signing/install-over/publication receipt](releases/v0.10.2-publication.md).

## Use it

1. Open **Search → Open YouTube link**. The same action is also in the top app
   bar and Library. Hindi: **YouTube लिंक खोलें**.
2. Tap **Paste link** or enter a YouTube video link.
3. Tap **Show video** to fetch the exact upload's title, uploader and artwork.
4. Tap **Play**. The ordinary track menu also offers queue, likes/playlists,
   both download destinations and **Use in Mashup Studio**.

Opening the form, reading the clipboard after a tap, typing and previewing do not
start/stop existing playback or write search history, downloads or Studio sources.
The result is identified by video ID, not a title search or a Music catalogue hit.
This lets an accessible flip, cover or creator upload be chosen even if Songs
search does not index it. Normal Songs search and music-only radio are unchanged.

## Supported and unavailable links

- Standard YouTube `watch?v=…`, `youtu.be/…`, Shorts, live, embed and YouTube Music
  video links are accepted. IDs are case-sensitive.
- A video link with a playlist or timestamp still opens **only that video**, from
  its ordinary beginning. It does not import/play the whole playlist.
- Playlist-only links ask for an individual video link. Channels, clips, redirect
  wrappers, malformed IDs, credentials, nonstandard ports and other websites are
  rejected before a provider call. The pasted authority/tracking is not fetched.
- A link does not bypass private/deleted/age/country/member/bot restrictions or
  guarantee that every live upload has a supported audio stream. Metadata and
  playback can fail independently; the existing playback errors/retries remain.
  No replacement song or fake successful download is invented.

## Implementation and preservation

Android validates/canonicalizes locally, then requests NewPipe metadata for the
canonical YouTube watch URL. Native PC uses the existing yt-dlp runtime for the
same canonical ID. Neither path searches a title, limits the manual selection to
music categories, downloads audio for a preview, captures cookies or introduces a
second playback engine. Optional duration/uploader/artwork may be absent.

The Android controller and native page have separate request ownership. Editing,
clearing, cancelling or leaving invalidates late results; repeated Show taps
while loading do not duplicate extraction. Play and the menu pass the same
ordinary `Track` into existing actions. Existing five tabs, queue format,
Room/SQLite schemas, download paths, Studio formats and update/signing identity
remain unchanged. Search input/filter/results are retained when returning.

All labels come from the Android English/Hindi resources through the generated
phone/PC contract. The native page is Qt, not an embedded website or browser.

## Validation status

- Shared offline URL corpus: **29 valid + 46 invalid cases**, executed by both
  platform parser suites. Metadata is not invented for live acceptance.
- Exact released application/test/tag source: **`3e71ff57432232641e1e69f3c4b6c2c7a49b9b18`**; one metadata-only
  child of the fully validated `a378de97aa561af551f39e0fe079b92a7bf5ab80`.
- [Android validation](https://github.com/DeepuExplainsAi/dkord/actions/runs/42618720910) **SUCCESS**: 458 JVM cases/52 XML reports,
  50 API35 device cases/1 XML report including seven real production Compose link
  page cases, plus 144 fast native cases. No failures/errors/skips.
- [All-six native validation](https://github.com/DeepuExplainsAi/dkord/actions/runs/42618720890) **SUCCESS**: 144 cases on every
  genuine OS/CPU host, actual codecs/Qt widgets, entry/frozen/package/install-over
  checks and 30 actual frozen native screenshots per target. Real Windows x86
  runtime and source-built codec, not renamed x64.
- [Original-key publication](https://github.com/DeepuExplainsAi/dkord/actions/runs/42618713053) **SUCCESS**: original certificate,
  actual Android versionCode 15 → 16/same-UID retention, all eight client-verified signed PC
  update plans, 22 uploaded-byte hashes and unchanged four historical releases/
  53 original assets. [Complete receipt](releases/v0.10.2-publication.md).
- **[180 actual PC screenshots](PC_SCREENSHOTS.md)**, all decoded/source/runtime/
  PNG-hash verified and visually reviewed. Clearly labelled offline tone/sample
  metadata fixtures; they do not establish live-stream availability/heard audio.
- Local 280 repository guards + 108 non-GUI native cases/99 subtests, phone-owned
  EN/HI/theme/navigation contract, syntax/XML/YAML/whitespace checks passed.
- Real pre-release failures were fixed, not hidden: explicit GUI-thread page
  cancellation before C++ deletion; proper new Android test IME calls; readable
  real modal sizes; actual frozen Linux X11 shape-library dependency; native
  white-on-white player tabs. The original tests, strict capture provenance and
  actual native Windows/cocoa/xcb plugins remained mandatory. Rendered pixel tests
  now check all player-tab selections in dark/light/AMOLED themes.
- Sandbox GUI/Android execution is not claimed: actual native/emulator evidence
  above comes from CI. No physical hardware, heard/live audio or particular
  user-upload success is inferred from fixture or compilation results.

## Still requires real-device/provider acceptance

- [ ] On a real phone and each relevant native OS/CPU, paste an accessible upload
  absent from Songs search. Confirm the **same video ID/title/uploader** appears
  and its real audio starts only after Play. Record the actual link/device/result.
- [ ] Check normal/short/Music/Shorts/live video forms; private/deleted/restricted,
  playlist-only, malformed, offline and slow/cancelled lookups. Existing audio
  must not stop when paste/preview fails. Check English/Hindi and large fonts.
- [ ] From the linked result use queue, likes/playlist, private/device downloads,
  and online Studio. Confirm real audio/file destination, cancellation and original
  project/file retention; then retest ordinary search/radio/history/rooms.

The user's example audio flip has **no supplied URL**. Its metadata, availability
and heard playback have not been verified and must not be inferred from fixtures.
