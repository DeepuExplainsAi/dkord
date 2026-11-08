# 0.9.0 development acceptance checks — not a published APK

CI and phone/live-provider checks are different. Exact completed run proof is in `HANDOFF.md`; this checklist is **not** a record of phone passes. Never uninstall/reset data to test an update; future official APKs must use the existing package/key and a fresh greater version code.

## Search keyboard / navigation
- English and explicitly selected Hindi; narrow portrait, landscape and larger system fonts.
- Focus search: keyboard opens, navigation/mini-player no longer reserve a second keyboard-sized gap. Suggestions/history can scroll to the real keyboard boundary; no mid-row clipping hidden behind a black region.
- Test clear, history/edit, both visible submit and IME Search, every native scope, correction/retry and full-width Load more. Songs remains default; All YouTube remains opt-in. Switch tabs while typing and dismiss the keyboard.

## Genuine Shorts and full-song selection
- On a real provider connection, search a chosen song/creator (not a production hardcoded example). Videos must be actual native Shorts/upload IDs; an empty all-search can discover actual matching creator Shorts tabs, labeled accordingly.
- Swipe several pages; only the settled/frontmost video has a player. Confirm page retry, duplicate removal and continued paging, including an unknown provider duration.
- Start an audio song, enter a clip, open Settings/another destination, background the app, unplug headphones and return. No two audible players or outgoing-animation interruption of a newly chosen song.
- Find full song opens an editable native Songs lookup. Choose the matching title/artist explicitly. A guessed first result is never played or presented as verified original audio. The chosen full song continues even if feed pagination completes.
- Check light/dark setting readability. No claims that provider metadata always identifies original audio or that every provider video is available.

## Real Mashup Studio
- Open Library → Mashup Studio, or a song menu → Use in Mashup Studio. Online sources use normal Dkord download first; choose only completed/readable sources.
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
