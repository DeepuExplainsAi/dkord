<div align="center">
  <img src="desktop/assets/dkord.svg" alt="Dkord" width="96" height="96" />
  <h1>Dkord</h1>
  <p><strong>Your music. Your mix. Your space.</strong></p>
  <p>Open-source music player · private offline audio · real Mashup Studio</p>
  <p><a href="https://github.com/DeepuExplainsAi/dkord/releases/tag/v0.10.0">Android stable</a> · <a href="desktop/README.md">Native desktop preview</a> · <a href="#features">Features</a> · <a href="#build-and-regression-checks">Build & tests</a></p>
  <p>By <strong>DeepuGupta</strong> · GPL-3.0 · no paid custom backend</p>
</div>

**Dkord is a music-first YouTube / YouTube Music client and audio editor.** Discover a particular song/version, keep a local listening library, or turn selected audio into a real playable mix. Android playback, extraction and editing run on the device; optional Listen Together rooms use a public relay. Not affiliated with Google or YouTube.

## Next update: Android + PC 0.10.1

A fresh common release is being validated on the assigned branch: the responsive
phone-derived PC interface, discoverable global Listen Together, local-only
playback diagnostics and concise **© 2026 dKORD** About. It preserves the existing
APK signing identity and user-data locations. Publication is gated on Android and
all six native profiles, genuine frozen Windows32 captures, actual old-to-new
installer fixtures, and an original-identity signed PC update manifest. Existing
releases below are preserved. [PC scope, install-over and acceptance limits](desktop/README.md).

## What is available now?

| Platform / track | Availability | What to expect |
|---|---|---|
| **Android stable** | **[v0.10.0 / code14](https://github.com/DeepuExplainsAi/dkord/releases/tag/v0.10.0)** | Original-key APK; direct online Studio, explicit private/device downloads, selected/everyone co-host controls, additive migration and existing playback/library/in-app updates. |
| **Source integration** | **[PR8 merged](https://github.com/DeepuExplainsAi/dkord/pull/8)** | Original-key v0.10.0 release and source integration completed; [exact release receipt](docs/releases/v0.10.0-publication.md). The new [Windows x86 request/PR9](https://github.com/DeepuExplainsAi/dkord/pull/9) is separate and remains unmerged; its desktop preview is published. |
| **Windows / macOS / Linux** | **[v0.10.0 downloadable previews](https://github.com/DeepuExplainsAi/dkord/releases/tag/v0.10.0), not trusted signed releases** | Real native Qt client, real media/file backend and FFmpeg Studio; platform/CPU packaging and update-verification tests. **Full Android parity, trusted native signing/notarization and a production desktop update channel are not complete.** |
| **Windows32 x86** | **[Download Preview2 installer](https://github.com/DeepuExplainsAi/dkord/releases/download/desktop-v0.10.0-preview.2/Dkord-desktop-v0.10.0-windows-x86.exe)** | Genuine32-bit Windows10/WoW64 app; separate install path/shortcuts, preserved per-user data; unsigned experimental preview, not Windows7/8. |

### Windows32 x86 + real computer-app screenshots
[PR9](https://github.com/DeepuExplainsAi/dkord/pull/9) adds a genuine **Windows10 32-bit / WoW64** profile—not an x64 rename—with CPU-matched Python/Node, the real Qt5 widget/multimedia UI and source-built FFmpeg/ffprobe8.1.3. Existing64-bit Qt6 profiles remain. Its separately named installer avoids overwriting x64 program files while retaining the stable per-user library/data lock. Qt5.15.2 is a legacy compatibility runtime; physical32-bit OS/audio/install-over acceptance remains outstanding.

The separate [desktop Preview2](https://github.com/DeepuExplainsAi/dkord/releases/tag/desktop-v0.10.0-preview.2) is **published**, with **36 native cases×6 targets +432 JVM/38 Android emulator cases** and real frozen/package/screenshot gates successful at the exact release head; [immutable publication/hash receipt](docs/releases/desktop-v0.10.0-preview.2-publication.md). It does **not** replace Androidv0.10.0/latest. The player/Studio PNGs are taken from the actual frozen Windows32 application with clearly marked offline generated audio, not AI artwork, a phone screenshot or an invented live catalogue. [Player screenshot](https://github.com/DeepuExplainsAi/dkord/releases/download/desktop-v0.10.0-preview.2/windows-x86-player.png) · [Studio screenshot](https://github.com/DeepuExplainsAi/dkord/releases/download/desktop-v0.10.0-preview.2/windows-x86-studio.png) · [desktop scope/limits](desktop/README.md).

### Listen. Keep. Create.
- **Find your version.** Songs-first search, Hindi/Choliwood and Unicode input, explicit broad YouTube scopes, independent uploads kept separate—not a fixed demo catalogue.
- **You choose what plays.** The chosen song plays first; an explicit Play all is different from selecting one result. Queue, history, radio, lyrics, playlists and sleep controls stay yours.
- **Make a real mix.** Select precise clip ranges and arrange sources into one encoded AAC/M4A file—not a playlist renamed as audio. Original files stay unchanged.
- **Keep offline storage intentional** *(Androidv0.10.0)*: **Download in Dkord** for managed private offline audio, or **Download to device** for an additional accessible copy. Private audio still consumes disk space. Existing public files are not moved/deleted merely by upgrading.
- **Edit online songs directly** *(Androidv0.10.0)*: choose a normal song in Studio or its menu; Dkord prepares a private project copy without making you manually download it first. Audio bytes still need to be fetched; there is no claim of zero-storage editing.

There is **no automatic phone-to-PC/cloud audio sync**. Each installation keeps its own local files; updates are designed to retain that device’s library. Playlist/likes JSON transfers metadata, not audio bytes. Desktop managed storage is a per-user data directory, not an Android-style sandbox against other applications running as that user.

## Features
Listen Again resume/searchable history · real on-device clip/merge Mashup Studio · music-first search with optional broad YouTube scopes · Home with moods, charts and collapsed-by-default New Releases · background audio with notification, lock-screen and Bluetooth controls · music-only related-radio autoplay · queue, shuffle, repeat, speed and sleep timer · synced lyrics (LRCLIB) · tagged M4A downloads with pause/resume · local playlists with JSON import/export · song sharing · Listen Together rooms · compact in-app updates · dark / light / AMOLED / Material You themes.

## Install and updates
Latest official **[v0.10.0 / code14](https://github.com/DeepuExplainsAi/dkord/releases/tag/v0.10.0)**: **[download Dkord-v0.10.0.apk](https://github.com/DeepuExplainsAi/dkord/releases/download/v0.10.0/Dkord-v0.10.0.apk)**. Separate native exe/pkg/deb/AppImage assets on that page are **experimental desktop previews**, not full Android parity or trusted signed desktop updates. Future updates are available from [the latest stable release](https://github.com/DeepuExplainsAi/dkord/releases/latest). Official updates use the same package/signing identity: install over the existing app, **without uninstalling**, to retain playlists, likes, downloads and settings. Uninstalling generally removes local app data.

Home shows a small **Update / Later** notice, not a blocking dialog. Later defers that version for 24 hours; a different newer version can still appear. Foreground checks are throttled to 30 minutes. Settings also provides a manual check and live downloaded / total / remaining MB. APKs are downloaded only after consent, and `/releases/latest` is resolved again before the download, so skipped releases do not require intermediate installations. An old ready APK does not block newer-release checks.

The download is bounded and checked for size and optional release SHA-256. Before installation, the app verifies the APK's package, advertised version, increasing versionCode and installed signing certificates. Android's system installer/unknown-source permission UI completes installation. Downloads share app-lifetime state across screens/rotation; this is **not** a promise of update-download continuation after process death.

## Search and saved queries
New searches default to **Songs**, the YouTube Music catalogue, and clearing returns to Songs. Songs / Albums / Artists / Playlists are the first scopes; **Music videos / Videos / All YouTube** remain explicit options. Use All YouTube for creator uploads and versions outside the music catalogue. A saved shortcut still restores its original filter/pin, rather than silently changing your saved intent.

Queries are not rewritten with music keywords, and manual search results have no title/genre/duration whitelist: instrumentals, independent creators' covers, karaoke, piano/no-vocals, remixes, slowed/reverb versions, long mixes and short reel-style uploads can appear in provider order. These are examples, not a fixed category list. Searching for an “Instagram version” searches versions uploaded/indexed on YouTube, not Instagram's separate catalogue. Misspellings such as “instumental” go to the provider as typed; available YouTube suggestions/corrections can help without a client-side spelling dictionary silently changing your intent. Different uploads with the same title—even by the same creator—remain separate by video ID, including across pages. Search rows allow two title lines and show the creator plus a known duration; unknown durations are not labeled as zero/live. Existing automatic music-radio recommendation rules remain separate. Video IDs support watch, short, Shorts, live and embed links, including watch links with playlist context. This does not guarantee that every returned upload is playable in guest mode.

The Search screen shows **Recent searches** below the filter chips when the field is empty. Only submitted searches are saved, including submitted attempts that fail offline; typing and loading more results do not add history. Searches made before this feature cannot be recovered.

- Tap an entry to repeat its original query **and filter**. The pencil prefills it for editing without submitting.
- Use its three-dot menu (or long-press) to **Pin / Unpin** or **Remove**. Up to **50** searches are kept, including at most **10** pins. Pins stay above other recents and survive ordinary history eviction.
- **Clear all** asks for confirmation and removes both recent and pinned searches. Clearing the search input only returns to recents; it does not erase history.
- Matching saved queries appear immediately while typing, even offline, in their own section. Real debounced YouTube suggestions keep the provider's order in a separate section, with loading and Retry states instead of silently disappearing on failure. Up to 20 nonblank unique provider suggestions are retained.
- Provider **Did you mean / Showing results for** metadata is displayed when available; it does not silently alter your input or save a correction as a new search. Tap it to submit the corrected query explicitly. A compact catalogue hint and **Search all YouTube** action stay visible for every narrow filter, even when it already returned some results or an old Songs shortcut was repeated. While typing, changing scope only refreshes suggestions; after submission it searches the same query in the chosen scope. Tapping a search match starts **only that chosen track**, not the other matching versions/uploads. Typing, suggestions, submitting or loading another result page do not start audio. Explicit album/playlist/Home **Play all** queues keep full-list playback. Pagination failures keep existing results and offer Retry. Load more is also available for pages that add no visible rows.

Search has a separate 48dp submit button alongside the input (and keyboard Search), a compact non-wrapping placeholder, and the existing clear action. Player secondary actions wrap as whole buttons so Add to playlist / Play video are not squeezed into vertical letters on narrower screens.

### Search / Home playback and related autoplay
Tap a Search result or an ordinary Home song card to start **that exact song first**, not every search result or the whole mixed Home shelf. Home has a separate accessible **Play all** action when the full shelf is desired. Explicit album/playlist/category/New Releases playback keeps its chosen queue/order.

With Autoplay on, one private in-memory session anchor stays tied to the selection across subsequent batches instead of drifting from each queue tail. Submitted Search context (including actual provider corrections), Home discovery/shelf/chip intent and available provider metadata guide related radio. Known language, opposing moods and explicit distant-era/classic mismatches are filtered; matching provider style terms and genuine video view counts rank compatible music. Popularity never licenses a known language/mood mismatch. Music radio is anonymous and first choice; fallback searches stay music-only and context-scoped, with no unrestricted artist-only expansion.

This is **best-effort metadata-based continuity, not account-personalized YouTube Music AI or acoustic mood recognition**. A romanized title is not assumed English. Only explicitly original audio language evidence is used; missing facts (including era and vocal/instrumental status) remain unknown; numeric song/album names and re-upload/remaster dates are not claimed as original song release years, and views are provider video counts, not invented song streams. Unknown candidates require appropriate source/context evidence rather than fabricated facts; sparse/offline metadata can produce a shorter batch or none instead of unrelated filler. Candidate/profile count, memory, metadata timeout/concurrency and failure retries are bounded; the queue is not padded with uninspected candidates when the budget runs out. Private Search context is not added to song/MediaItem/room metadata or logs and is not persisted as a recommendation profile.

Automatic candidates still exclude already queued IDs, normalized base-song versions/covers/remixes of the seed/queue, invalid durations and explicit hour/all-version/full-album mixes; manual Search/queue choices remain unrestricted. Response ownership includes the whole queue, selection anchor, intent and session revision. Pause, sleep, repeat, Autoplay-off, disconnect and queue replacement cannot append a stale response or force playback to resume.

## Languages
The app interface defaults to **English even when the phone uses another language**. Choose **Settings → Appearance → App language → English / Hindi** to change it explicitly. Android 13+ per-app language choices are also honored; resetting the app-language override returns to the app's English default. Original song/artist metadata is not translated, and selecting an interface language retains the device region used for music discovery. Android-owned permission, installer and file-picker screens are controlled by Android.

English and Hindi are the translations actually included. To add a supported language, provide a complete `res/values-xx/strings.xml`, register its `AppLanguage`/Settings labels and `res/xml/locales_config.xml` entry, and extend the translation contract tests. Do not expose untranslated language options.

## Listen Together
1. The host starts a song, opens **Listen Together** from the full-player menu, and taps **Create room**.
2. Use **Copy code** or **Share** to send the ten-character code to everyone listening.
3. Each friend opens Listen Together, enters/pastes the same code, and taps **Join room**, then **Sync & play**.
4. Turn on **Follow host** to follow later song/playback changes. The host uses **Open player** to control the music. Multiple friends can use the same room code.

Going back does not leave the room; **Leave room** stops sharing/following without stopping ordinary local playback. Keep Dkord running: room sessions are app-process-lifetime, not persistent accounts or a guaranteed always-on room service. Reconnection resumes from the last received cursor, with backoff for network errors/rate limiting. Independent buffering/network/device clocks mean synchronization is approximate, not sample-accurate.

### Room transport and privacy (developer details)
The current transport is HTTPS to the **public ntfy.sh relay**, with a twelve-hour cache query. Room payloads contain video ID/title/artist/thumbnail, playback position/state/timestamp and at most ten upcoming tracks. They never contain audio streams, YouTube cookies or account credentials. Each phone resolves its own audio.

Room messages are **not end-to-end encrypted**, and anyone who knows the code can read or publish to its topic. Older0.9.1 has no authenticated host identity or participant-presence protocol. Androidv0.10.0 adds signed creator-bound state and a bounded recently-active updated-client roster, not a verified-account identity or total live-listener count (see the co-host section). Do not share a code publicly. Public-relay availability and free-service rate limits can affect room delivery. Live two-device/device compatibility has not been verified by the source/static checks below.

### Androidv0.10.0: selected co-hosts or everyone
The room creator can grant playback controls to **one, two or more selected members**, or **Everyone (including new members)**. Default stays host-only; untick a member to revoke, or choose **Only me** to take all controls back. Co-hosts use ordinary in-app play/pause/song/seek controls; only the original creator administers permissions. Grants do **not** force audio to start or enable Follow. Updated members use signed, room-bound proposals; old rooms/listeners retain one-way Sync/Follow compatibility. The creator must remain reachable; public-relay metadata is not end-to-end encrypted. Full behavior, compatibility/security boundaries and acceptance scope: **[Room controls](docs/ROOM_CONTROLS.md)**. This ships in the published Androidv0.10.0 APK. Desktop rooms and physical multi-phone/live-provider acceptance remain open; emulator/actor tests are not physical-phone passes.

## New Releases
The Home section stays collapsed until opened. Categories: All / Hollywood / Bollywood / **Choliwood** / Punjabi / Tamil / Telugu. Windows: last 24 hours / 7 days / 10 days. Discovery expands music albums and uses music-song searches; publication/upload metadata determines recency, **not a guarantee of the original commercial release date**. Unknown dates are not guessed; date/network failures have retryable states instead of pretending the catalogue is empty. Tapping a song retains the full shelf as the queue and existing related autoplay.

## Build and regression checks

**Published v0.10.0 proof:**432 JVM +38 Android35 emulator cases,30 actual native cases on each of5 OS/CPU hosts, original-key APK compatibility and all14 public assets/digests verified. [Exact source, CI and publication receipt](docs/releases/v0.10.0-publication.md). Physical-phone/live-provider and production desktop trust/parity remain separate unchecked acceptance work.

Stack: Kotlin, Jetpack Compose (Material 3), AppCompat application locales, NewPipeExtractor, Media3, Room, DataStore, WorkManager, Coil and Koin. Exact versions are in `gradle/libs.versions.toml`. Android builds require JDK 21 and SDK platform 37.

```sh
python3 -B -m unittest discover -s .github/scripts -p 'test_*.py' -v
./gradlew testDebugUnitTest assembleDebug --stacktrace
```

**Validate pull request** automatically runs for PRs targeting main, including draft PR updates. It uses a read-only token, no signing secrets, and runs the Python checks, full Android unit suite and APK compile. A separate Android35 emulator job requires all ten native regression classes: Search keyboard viewport, Studio audio export, Studio editor, export publication, Listen Again, related-playback routing, online source/storage migration, destination chooser, the online picker’s own-window IME, and room co-host UI/Android-crypto/actor cases. It uses an installed real keyboard with wake/unlock/hardware-keyboard policy setup. A minimal **androidTest-only idle HOME** prevents the image’s Google launcher/widgets from owning an ANR overlay between cases; the default HOME is verified before instrumentation and never changes the production app. Error dialogs are not hidden, failed tests are not retried, and real IME visibility, original keyboard deadlines, viewport geometry and navigation/font assertions remain mandatory. Failure-only diagnostics identify WindowManager focus ownership and keyguard state; there are no automatic test retries or fake insets. Actual JUnit XML counts and checked PR/merge SHAs are reported; no missing-class/empty/all-skipped report can establish a successful validation. Only test reports are uploaded—no release/tag or installer APK is published. This is the validation path when the agent cannot dispatch a manual workflow (integration HTTP403). It may still require owner approval if GitHub flags a contributor run.

**Build debug APK** remains manual-only. **Release APK** keeps its manual entrypoint and mandatory signing/update gates. For the now-completed, consumed **v0.10.0/code14** publication only, it additionally accepts a trusted push changing `.github/release-requests/v0.10.0.json` on `arena/a0209191-dkord`. Its pre-signing guard requires the exact tag/repository/ref and a non-forced/non-deleted, direct metadata-only child of the recorded validated source head. The v0.10.0 authorization is now consumed too; preserve every request as audit history and never replay publication. Historical v0.9.1 and older requests cannot enter this route. Publication additionally requires successful full PR Android validation at the exact release commit, including all10 mandatory native classes, plus successful same-head five-host CI for any attached explicitly experimental desktop previews. Each native package/provenance hash/format and actual30-case/all3-class JUnit proof is checked before upload; missing/failed validation refuses publication without retrying tests. Ordinary PR/code/docs pushes do not publish. The agent's dispatch403 permission is not changed; this is a version-scoped owner-authorized release event, not signing from a PR.
- **Build debug APK** runs the Python regressions, full Android unit suite and debug build, then uploads `dkord-debug-apk`. Without the existing signing secrets, a developer debug APK cannot update an official install.
- **Release APK** takes a tag matching `versionName` (current published release: `v0.10.0`, versionCode `14`; never reuse its tag/code), runs the Python and full Android unit suites/build, requires the existing stable key (`DKORD_KEYSTORE_B64`, `DKORD_KEYSTORE_PASS`, alias `dkord`), and checks the actual old/new APK signatures, package and increasing versionCode. Only then does it create the tag/release page and attach the APK. No previous release is overwritten or removed. Start a **fresh run on the prepared branch**, not a re-run of old jobs. The version-scoped trusted-push request used this same full pipeline; it never skips tests, signing or actual APK compatibility verification. v0.10.0, v0.9.1, v0.9.0 and v0.8.2 are already published: retain their requests as consumed audit metadata, never replay them to replace an APK. A future release requires a new higher version/code/tag and fresh authorization.
- All three workflows preserve Android unit-test reports as an artifact, including failed runs where reports exist. Resource/source/workflow checks are not a substitute for Android compilation, UI/device tests or a real multi-phone room session. Current validation/execution status is recorded in `HANDOFF.md`; pending tests are not claimed as passing.

## How playback works (and why it can break)
Streams are resolved on the phone through a chain: NewPipeExtractor, then the YouTube InnerTube ANDROID_VR and IOS clients, then both again with fresh visitor data. Only audio-only streams (m4a/opus) are used. URLs are cached until they expire and re-resolved automatically on HTTP 403.

YouTube changes often, so extraction can break. **Settings → Troubleshooting → Update extractor** checks the bundled extractor's upstream version; updating the extractor requires an app update. **Report broken playback** copies a redacted log and opens a GitHub issue; **Debug log** shows recent events. Bot checks, age/kids restrictions, private/region-locked/unavailable tracks and network errors have explicit messages. Guest mode does not bypass account/age restrictions.

## Downloads
**Stable0.9.1:** a single song downloads as tagged M4A from its three-dot menu → Download. A playlist/album's top-bar export saves a **JSON file** (name + tracks), not all of its audio; import it again from Library. Normal music downloads use WorkManager and support pause/resume across app restarts independently of the in-app APK updater.

### New0.10.0 source: explicit storage choices
Every UI download action (player, song menu or bulk selection) opens **Download in Dkord / Download to device**. In Dkord stores offline audio under internal app storage, not public Music. To device additionally publishes a copy to Music/Dkord (Android29+) or your selected SAF folder; Android26–28 asks for a real folder. A failed device save does not claim private-fallback success. Existing complete audio is reused; local-copy work can run offline. Device copies remain when an app-private download is removed. Old download URIs and queue intent survive the additive Room1→2 migration.

**Online Studio** searches real Songs with its own query/pagination/cancellation ownership. Selected accessible audio is staged privately, probed, then committed as a durable editable source; it does not create a Downloads row or public Music file. Existing phone/download imports, millisecond ranges, clip ordering, preview, snapshot export and sharing remain. Cancelling preparation cleans partial app-owned staging, not existing sources or the project.

### Native desktop development
See **[Desktop README](desktop/README.md)** for the actual implementation, OS requirements, build commands and acceptance gaps. **[Native preview validation](.github/workflows/validate-desktop.yml)** builds Windows x64, macOS x64/arm64 and Linux x64/arm64 packages with a matching bundled JS runtime and actual native widget/codec tests. Preview artifacts are not trusted signed/notarized releases. The updater has a separate signed desktop channel and refuses APKs, wrong OS/CPU, malformed packages and downgrades; production keys are intentionally unconfigured until an authorized, verified native release.

Discoverability terms describe the project—not measured search-volume claims: **open-source music player, YouTube Music client, offline music library, audio editor, mashup maker, Kotlin/Jetpack Compose, native Windows/macOS/Linux music app, Hindi and Choliwood music search**.

## Video (optional)
Audio stays the default. **Play video** opens a separate player and pauses background audio; downloads are unaffected. It selects a muxed progressive stream up to 720p, with subtitles when available, fullscreen/landscape and retry. YouTube often offers muxed streams only up to about 360p. Blocked/unavailable videos show an error rather than an invented stream. Device validation remains required.

## Signing in: unavailable
Cookie-copy WebView sign-in is removed. Signed-in YouTube Music library/personalization relies on private cookie-authenticated APIs; official Google OAuth does not provide that library access. The app states that sign-in is unavailable rather than faking it, and old stored sessions are cleared. Anonymous search, radio, playback, downloads, local playlists and lyrics remain available. No cookie-paste workflow or TLS/certificate bypass is included.

## Network/privacy
No analytics and no Dkord account server. The app contacts YouTube/Google for music/media, LRCLIB for lyrics, and GitHub for foreground app-update checks and explicit extractor-version checks. Only creating/joining a room starts ntfy room traffic; leaving cancels its jobs. TLS validation stays enabled. The room privacy limitations above apply even though their technical explanation is no longer displayed as a large paragraph on the main room screen.

## About the project
**Dkord by DeepuGupta** puts everyday listening, offline organization and practical audio creation together. Its priorities are visible controls, local-first data, genuine provider results and honest release status. No fake songs, popularity/search-volume figures or “complete desktop parity” claims are used to hide unfinished work.

Questions or bugs: [GitHub issues](https://github.com/DeepuExplainsAi/dkord/issues). New storage/native/update acceptance: [checklist](docs/PLATFORM_ACCEPTANCE.md). Exact source/run proof and known limitations: [HANDOFF](HANDOFF.md).

## Disclaimer and license
Not affiliated with YouTube or Google. Use the app in line with applicable laws and service terms. GPL-3.0; see [LICENSE](LICENSE).

## Published0.9.1/code13 — Listen Again and contextual related autoplay

The owner rejected the0.9 Shorts experience and requested complete removal, not a renamed/re-filtered video feed. The current source replaces it with **Listen** / **Listen Again**:

- Resume the actual current/saved song and queue at its position; entering the tab does not start audio, and opening a playing song does not toggle it off.
- Search real local listening history by title/artist/album, grouped Today/Yesterday/Earlier in the device timezone. Liked and completed-download filters work locally; no fake recommendations, play-count statistics or channel discovery.
- A history row plays just that chosen song first. **Play these songs** is a separate explicit whole-list action; normal song menus remain available.
- Manage one history entry or confirm clearing history without deleting songs, likes, playlists, downloaded/exported files or the current queue. History records a song only after it really starts playing.
- English/Hindi, larger fonts/real IME, saved filters/query/tab state and old0.9 tab migration. The legacy enum value is deserialization-only; all Shorts feed/controller/repository/DI/UI strings are removed. Ordinary opt-in manual video search/player stays.

Search/Home share anchored context-aware radio, and ordinary Home taps no longer silently queue mixed shelves; **Play all** stays explicit. Published source **`c18c92564ed740f7d670369cb043ff6e6d9b39d0`** passed [full Android validation42479865229](https://github.com/DeepuExplainsAi/dkord/actions/runs/42479865229): APK compile, **378 JVM tests +19 real Android emulator cases**, zero failures/errors/skips, all six mandatory native classes. **103 Python** guards pass. [Signed release42479860745](https://github.com/DeepuExplainsAi/dkord/actions/runs/42479860745) also passed every original signing/build/actual old-new APK package/certificate/increasing-version gate plus the added exact-head full-Android-validation gate before publication.

**v0.9.1/code13 is published**, with the official APK linked above, original app.dkord package/key and code12→13 binary update compatibility verified. Install over the old app **without uninstalling/resetting**. Earlier intermittent CI Window-focus failures did not recur in these later runs; that does not establish their underlying cause or a permanent flake repair. Physical-phone/OEM/live-provider similarity and phone update/data-retention acceptance remain unverified; the [checklist](docs/NEW_FEATURE_SMOKE.md) is not a phone-pass report. Exact source/job/asset/failure history is in HANDOFF.md. PR #7 was subsequently merged at `7d144b7`. New work is isolated in draft PR8; no new publication or merge is implied.

## Published0.9.0 / code12 — historical feature snapshot

The published release adds a single-owner keyboard/insets fix, a native Shorts video tab, and **Mashup Studio** (Library or a song menu).

- Shorts uses actual provider short-form metadata/creator tabs, a vertical player and an editable Songs lookup. Choose the matching full song explicitly; a clip is **not** treated as verified original-song attribution.
- Studio imports readable, non-DRM phone audio or completed Dkord downloads into persistent private projects. Select arbitrary valid millisecond start/end or duration ranges, reuse sources, reorder/remove clips and preview the arrangement.
- Merge creates one real AAC/M4A file on-device, with WorkManager progress/cancellation and a frozen input snapshot. Saved output is playable in Downloads, usable in playlists, shareable as audio and can be copied through the system file picker. Device codec/storage limits still apply.
- Generated local audio never falls through to a remote stream/radio/lyrics/video lookup or room metadata relay. Sharing grants access only to the finished audio, not private project inputs.

**[v0.9.0/code12](https://github.com/DeepuExplainsAi/dkord/releases/tag/v0.9.0) remains an immutable historical release**, not the latest0.9.1 APK linked above. [Signed release run42470269867](https://github.com/DeepuExplainsAi/dkord/actions/runs/42470269867) passed all original signing and actual old/new APK package/certificate/increasing-version checks. Exact released source `d70a857` also passed [validation42470275561](https://github.com/DeepuExplainsAi/dkord/actions/runs/42470275561): APK compile, **300 JVM tests and all9 real Android device tests**, zero failures/errors/skips; **88 Python** guards pass. Device tests include actual AAC decode/range/order, mixed source formats, cancellation, persistence, EN/HI larger-font real-IME layout and foreground saved-output registration. This is not full Search-screen/physical-phone/live-provider acceptance or a completed phone update smoke; the remaining checklist is [here](docs/NEW_FEATURE_SMOKE.md). PR #7 was subsequently merged at `7d144b7`. New work is isolated in draft PR8; no new publication or merge is implied. See `HANDOFF.md` for exact source/job/asset identities.
