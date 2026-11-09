# Open an exact YouTube link — next update (unreleased)

This is a separate Android and native Windows/macOS/Linux flow. It is **not yet
in the published v0.10.1 downloads**; no old APK, installer, tag or asset is replaced.

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

- Shared offline URL corpus: **29 valid +46 invalid cases**, executed by both
  platform parser suites.
- Local sandbox: **108 non-GUI native tests +99 subtests** and **240 repository
  guard tests passed**. Python syntax, EN/HI XML and phone-contract checks passed.
- Exact application/test source: **`64e178b45dda68785b5eea787d768d53a5a511d4`**.
  [Android validation42602798355](https://github.com/DeepuExplainsAi/dkord/actions/runs/42602798355)
  **succeeded**: main/APK compilation, **458 JVM cases /52 XML reports**, and
  **50 API35 emulator device cases /1 XML report**, including seven production
  Compose link-page cases. Zero test failures/errors/skips. The same run's
  independent Linux native job passed **142 cases +actual codec/widget entry**.
- [Native validation42602798430](https://github.com/DeepuExplainsAi/dkord/actions/runs/42602798430)
  **succeeded at the same exact source on all six genuine targets**. Each ran
  **142 cases with zero failures/errors/skips**, real codec/data/update/widget
  tests, the native entry-point smoke, and real package/frozen-executable smokes.
  Windows32 compiled and executed its actual x86 codec/runtime; it is not x64
  renamed as x86. This generated development artifacts, not a public release.

  | Native target | Successful job |
  |---|---|
  | Windows x64 | [129114755268](https://github.com/DeepuExplainsAi/dkord/actions/runs/42602798430/job/129114755268) |
  | Windows x86 /32-bit | [129114755357](https://github.com/DeepuExplainsAi/dkord/actions/runs/42602798430/job/129114755357) |
  | macOS x64 | [129114754950](https://github.com/DeepuExplainsAi/dkord/actions/runs/42602798430/job/129114754950) |
  | macOS arm64 | [129114755084](https://github.com/DeepuExplainsAi/dkord/actions/runs/42602798430/job/129114755084) |
  | Linux x64 | [129114755127](https://github.com/DeepuExplainsAi/dkord/actions/runs/42602798430/job/129114755127) |
  | Linux arm64 | [129114754952](https://github.com/DeepuExplainsAi/dkord/actions/runs/42602798430/job/129114754952) |

  Released v0.10.1 proof remains separate history, not evidence for this feature.
  The final receipt/HANDOFF edits are documentation-only after the source above.
- A real native crash trace identified a Python `QObject.destroyed` closure during
  garbage collection. The fix cancels the page explicitly on the GUI thread,
  before page replacement/close/deferred deletion, rather than in a destructor.
  The deleted-widget/late-callback regression and original metadata-thread tests
  remain in the full suite. The Android IME helper now uses separate set-text and
  IME calls; no production behavior/assertions were weakened to get a pass.
- The sandbox has no Android SDK or GL/EGL/DBus/xkbcommon runtime. It cannot
  independently establish Android/native GUI execution or heard/live audio.

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
