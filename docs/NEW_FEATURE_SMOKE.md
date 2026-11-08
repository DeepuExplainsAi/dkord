# v0.9.1 phone/live acceptance checks — unexecuted; not a pass report

The historicalv0.9.1/code13 APK remains [published and unchanged](https://github.com/DeepuExplainsAi/dkord/releases/tag/v0.9.1); current Androidv0.10.0/code14 is [now published](https://github.com/DeepuExplainsAi/dkord/releases/tag/v0.10.0), with [exact execution/publication proof](releases/v0.10.0-publication.md). CI and phone/live-provider checks are different. Exact completed run proof is in `HANDOFF.md`; this checklist is **not** a record of phone passes. Never uninstall/reset data to test an update; official APKs must use the existing package/key and a fresh greater version code.

## Search keyboard / navigation
- English and explicitly selected Hindi; narrow portrait, landscape and larger system fonts.
- Focus search: keyboard opens, navigation/mini-player no longer reserve a second keyboard-sized gap. Suggestions/history can scroll to the real keyboard boundary; no mid-row clipping hidden behind a black region.
- Test clear, history/edit, both visible submit and IME Search, every native scope, correction/retry and full-width Load more. Songs remains default; All YouTube remains opt-in. Switch tabs while typing and dismiss the keyboard.

## Context-aware related autoplay — Search AND Home
- Pick a Hindi sad song through Search, then an ordinary Home song card. The exact chosen ID/version plays first, with no implicit whole-search/mixed-shelf queue. Next automatic songs should be distinct and context-compatible, including relevant popular music rather than an unrelated English/party/retro hit.
- Exercise a romanized Hindi title (not assumed English), known original vs dubbed audio, contemporary vs explicit classic selections, sad/party/chill/devotional/instrumental intent and arbitrary provider genres/styles. Verify several batches: the user selection remains the session seed, not the last recommendation. Native metadata and provider results can be missing/wrong; check actual live songs instead of claiming subjective similarity from fixture tests alone.
- Compare two compatible songs with real provider popularity; relevance must win over raw views. Song/re-upload dates must not be mislabeled as release years. Empty/failed metadata must not invent tracks, view counts, language or mood; retries/candidate inspections must stay bounded and no broad artist-only filler should appear.
- Home ordinary shelves/recent cards use single-song radio; **Play all** must deliberately preserve all shelf songs from index0. Album/playlist/explicit category/New Releases queue/order and collapsed release windows remain intact. Check native Home chips and progressive curated shelves, including visible Choliwood branding and original internal discovery intent, EN/HI and1.3+ font scale.
- Rapidly choose another song/query or the same song with a new context while radio is pending; pause, sleep, Autoplay-off, repeat, disconnect/reconnect, reorder/remove/manual-add and explicit queue replacement. No stale append, same-song/version loop, accidental seek/restart or forced resume is allowed. Manual queue edits/versions/long uploads must stay deliberate and unfiltered.
- Query typing/loading/cancelled results must not provide radio intent; only a completed submitted result (or actually applied provider correction) does. Pagination keeps its submission context. Non-song Search/Home tiles still navigate, song menus retain metadata, and raw private intent must not enter room messages or persisted Track/MediaItem metadata.
- Check slow/offline/rate-limited live provider behavior and resource use. Metadata is one bounded anonymous request per inspected video, not audio decoding or full extractor fanout. The app's interface language does not force the music language. Process restart may reconstruct an anchor from restored current song; session-only private intent is deliberately not persisted.

## Listen Again; Shorts removed
- No Shorts/Reels navigation item, vertical-video feed, background clip player or channel-discovery request remains. Existing opt-in manual video search/player is intentionally preserved.
- Open Listen: no audio starts automatically. With an existing saved/current song, Continue resumes its actual queue/position; opening a currently playing song does not pause it. Re-enter after Activity/process recreation without resetting data.
- Check real locally played songs grouped Today/Yesterday/Earlier in device timezone. Search title/artist/album, Hindi and English, filter liked/completed-download history, clear filters and explicit Play these songs. An individual row must play only the chosen song first, not silently queue all history.
- Verify large-font Hindi/English on narrow screens, scrolling, actual IME, accessible actions, state restoration and the old0.9 saved tab mapping directly to Listen (never re-opening a clip player).
- Manage: remove one history entry, cancel and then confirm Clear history. Likes, tracks, playlists, source/export/download files and the current queue must remain. A missing externally removed download still fails locally under existing playback handling; a completed-download record is not a current file-permission guarantee.
- Empty history offers real Search; local read/write failure offers Retry/error without clearing storage or fabricating recent tracks. Playback/source errors must never be misreported as successful listening.

## Real Mashup Studio
- **Older0.9.1:** open Library → Mashup Studio or a song menu → Use in Mashup Studio. Its online songs require a completed/readable download first. **Published Android0.10.0:** choose an ordinary online song directly; preparation is private and must not add a Downloads/public Music entry. See [new-platform/storage acceptance](PLATFORM_ACCEPTANCE.md) for explicit destinations, migration, cancellation and desktop/update checks.
- Import multiple accessible phone/downloaded formats, plus a deliberately unsupported/unreadable source. Originals must not be edited/deleted. Errors must preserve previously committed projects/sources.
- Choose different millisecond start/end or start/duration ranges, including multiple occurrences from one song. Test boundaries, zero/reversed/past-end/overflow rejection, long valid durations, reorder/remove and preview of both clip and arrangement. No silent fixed 15/30-second preset limit.
- Preview pauses normal audio, stops on leaving/backgrounding, and uses the selected ranges/order. Large-font Hindi fields remain scrollable with a visible Save action while the real IME is open.
- Merge must encode **one actual AAC/M4A file**, not rename a playlist or concatenate encoded file bytes. Verify playback/seek, approximately summed duration (AAC framing can add a small amount), and audible source/range/order.
- Exercise progress, explicit cancel after encoding starts, codec/storage/permission failure, app recreation and a background export. Partial app-owned output must be cleaned, project retained, only one export active. Edits during export affect the next export, not its immutable snapshot.
- Output appears in Downloads, plays, can be liked/added to a playlist, shares as an audio file with temporary read permission, and supports Save a copy. Check system picker recreation and missing/revoked output permissions. Private source/project files are not FileProvider-shareable.
- Delete a generated output outside the app, then try playing/sharing it: fail locally and allow re-export, with **no** provider stream/radio/lyrics/video/link/room metadata fallback. Test project deletion without deleting existing exported songs or original imported files.

## Preserve existing app behavior
- Exact selected-song playback from two unrelated user queries, then genuinely different related radio songs; pause/off/repeat/sleep and rapid queue changes still invalidate stale autoplay.
- Existing Home categories/release windows, collapsed New Releases, downloads, explicit whole-shelf/playlist playback, settings, language choice, Choliwood spelling and metadata-only rooms remain intact.
- No replacement signing key, version/tag reuse, release deletion, widened FileProvider root, credentials in logs, cloud audio processing or unauthorized release/PR merge.

Android 35 emulator checks do not establish physical-phone/provider behavior or every Android 8–14 storage/foreground-service edge case. Record actual observations separately before authorizing a fresh signed release.


## Android co-host rooms (published0.10.0, physical checks still unexecuted)
Exact5ca30b1 source earned [Android432 JVM +38 device](https://github.com/DeepuExplainsAi/dkord/actions/runs/42496445156), all mandatory classes/zero skips. This is protocol/widget/Android-crypto actor proof, not the physical checks below.

- [ ] Three real updated phones: default host-only, one selected co-host, two selected, Everyone and a late joiner; unauthorized local commands never change the room.
- [ ] Opt into Sync/Follow on listeners, then have each permitted co-host play/pause/change songs/seek from the app player. Confirm creator administration/revocation and that grant/revoke itself never starts audio.
- [ ] Duplicate names/short member IDs, EN/HI/large font, creator buffering/provider failure, concurrent intents, grant/revoke during delayed network publication, creator offline/reconnect, real Leave/new identity and old/new client combinations.
- [ ] Confirm headset/notification controls on a guest remain local in this version; no false desktop room or E2EE/private-account claims. Full bounds/compatibility: [ROOM_CONTROLS.md](ROOM_CONTROLS.md).
