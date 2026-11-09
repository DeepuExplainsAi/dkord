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
- Android main compilation/APK and **458 JVM tests /52 reports** passed at the
  initial feature checkpoint; no failures/errors/skips. The device-test compile
  helper needed separate IME/set-text calls; the corrected device suite is pending.
- A real native crash trace identified a Python `QObject.destroyed` closure during
  garbage collection. The fix cancels the page explicitly on the GUI thread,
  before page replacement/close/deferred deletion, rather than in a destructor.
  **142 real native cases plus the actual codec/widget entry smoke passed** on
  Linux at source `038b7cc26a1f5cc8ee10a083e47880090b9984fe`, including a new
  deleted-widget/late-callback regression and the original metadata-thread tests.
- Full Android device and six-host native package gates are still running. Do
  not treat pending checks as passed. Released v0.10.1 proof is separate history.
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
