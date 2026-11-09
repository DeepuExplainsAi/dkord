# Current 0.10.1 acceptance gates

The checks below retain historical receipts/physical checklists. For the new
release, executable gates now require **121 cases across13 native classes**, all
six genuine OS/CPU profiles and no skips/failures, Android unit +43 emulator
regressions (including the two JVM room interop vectors), current frozen Win32
screenshots and real install-over fixture execution. Counts must come from actual
JUnit reports, not this document. Signing is the original published Android
identity; its format2 domain-separated manifest is independent of OS
Authenticode/Developer ID/notarization, which remain unconfigured.

Every native host must install the immutable Preview2 package, then install the
new package **over** it and have its installed frozen executable verify/restore
standard-path seeded library/settings/queue/download/Studio bytes. Both Linux
package kinds are tested. The release-only Android emulator seeds the actual
original-key code14 app, installs code15 with `-r`, and reads the real Room,
preferences, queue, private+MediaStore audio and Studio sources through the new
app with the same package UID. These virtual-host fixtures do not tick any
physical-device, heard-audio or live-provider box below. The initial old empty-root
PC preview still needs a one-time manual install-over; subsequent common releases
can be attested to the pinned original identity. No replacement key/data reset.

**Published proof:** [v0.10.1 receipt](releases/v0.10.1-publication.md), released
source `e0e925a674f106f6291731f5b143d3800a476cd3`. All six121-case native suites,
436 JVM/43 Android regressions, actual native install-over and original-key
Android app code14→15 persistence passed. Finalization42588462082 checked every original
uploaded byte/ID and actual-client signature plan before and after public/latest
publication. These results do not mark physical/live-provider boxes below.

---

# Historical0.10.0 context and remaining physical-device acceptance

Android0.10.0/code14 and its [historical publication receipt](releases/v0.10.0-publication.md) remain preserved; its desktop assets were explicitly development previews. Current0.10.1 executed virtual-host/emulator proof and configured update identity are recorded above, separately from this real-device checklist. Do **not** uninstall, reset, clear data or replace the original signing key to test an upgrade. Record actual device/OS/version/results; CI fixtures are not OEM/heard-audio/live-provider or OS signing/notarization acceptance.

## Android existing data and destination intent
- Before an authorized signed upgrade, record real playlists/likes/history/queue/position, downloaded primary URIs/file hashes, public Music copies, settings and Studio source/projects/exports. Install over the existing original-key package, without uninstalling. Verify old records/file hashes/access remain, including legacy DONE/public and PAUSED partial rows.
- Download menu/player/bulk actions must show **Download in Dkord / Download to device**. Cancel must enqueue neither destination or show a false success. Private offline audio still uses disk; it must not create a public Music row.
- To device must create an accessible independent copy in the captured folder/Music/Dkord, retaining the private offline source. Android26–28 must request a real SAF folder. Revoked/full/unwritable destinations fail visibly, not silently fall back to private and claim device success.
- Already-private audio → To device must reuse bytes, including fully offline with another remote download waiting for connectivity. Pause/resume/retry/remove while both native worker queues are active; no double claim, stranded row, stale process-recovery reset or late recreated deleted download.
- Changing Settings folder after enqueue must not move an already-captured intent. Explicitly selecting a new destination can bind a new request. Retry of a failed device copy retains complete private audio and does not re-fetch it.
- Remove an app-private download: independently saved device copies must remain. Upgrade alone must not move/delete old public files. Check picker rotation/process recreation and large bulk batches (small saved-state token, no oversized Activity song bundle).

## Android online Studio
- From a normal Search/Home song menu or inside a selected Studio project, choose a song not in Downloads. No manual download/wait/return step. Verify real audio becomes a durable editable project source, with no added Downloads row/public Music entry.
- Query Hindi/Choliwood, different versions, no-results, retry and pagination; song identity stays distinct by ID. Test slow/stale/cancelled responses, query edits, leaving/reopening, EN/HI1.3+ fonts and real IME. The separate picker must own one safe inset without breaking the original clip editor or root Search keyboard.
- Cancel while resolving/transferring/probing/copying; disconnect/network restriction/unsupported/DRM/full-storage failures must preserve the project and original files, remove incomplete staging and not fabricate a source. Project sources survive restart without depending on provider URLs.
- Re-test device/offline imports, arbitrary valid millisecond ranges, order/reuse/removal, clip/arrangement preview, actual different-rate AAC export, cancel/background snapshot behavior, generated playback/seek/share/Save a copy. Existing six-class radio/history/IME/export behavior must remain intact.

## Real native desktop, all supported targets — physical acceptance
- Verify actual target/CPU from the package manifest, launch/install the actual Windows exe, Intel/Apple-Silicon macOS pkg, Linux deb/AppImage—not just a browser view or test source. Compare artifact SHA with CI proof. Do not call ad-hoc/unsigned packages trusted signed/notarized releases or disable OS security to fake acceptance.
- Validate native widget input/Unicode/large fonts, resizable PC layout, queue controls, audio start/pause/seek/repeat/shuffle/speed/sleep, saved-position resume without forced startup playback, real local history/likes/playlists and Android JSON round trip. Provider restrictions must produce actionable errors, not fake songs.
- Private/device destinations must behave honestly on each filesystem. Test offline local reuse, failed-public-copy retry, low space, removable/unmounted folders and deletion independence. The managed folder is per-user, not an Android UID sandbox against same-user apps.
- Online/device/offline Studio sources, accurate clip editing/preview/order, real heterogeneous-source AAC rendering, cancellation, project deletion during a pinned snapshot and original/export preservation must work in the packaged binary.
- Exercise the implemented native Listen Together hub, recommendation context, optional video, timed lyrics and EN/HI controls on actual devices alongside Android. Source/fixture coverage does not establish full live-provider/ranking, OS media integration or physical cross-device equivalence. Account sign-in is intentionally unavailable on both clients, not a supported feature to fake.

## Genuine Windows32 x86 and screenshot acceptance
- CI runs Python32/Qt5.15.2/Node22ia32 and freshly source-built FFmpeg+ffprobe8.1.3. Actual application/Node/FFmpeg/ffprobe PEheaders must be x86 and real execution/codec/frozen smoke must succeed. Source/archive/license/config/binary receipts are mandatory; do not substitute old imageioFFmpeg4.2.2 or rename an x64 package. Five other targets retain Qt6/PyAV. The suite now also captures actual source-window pixels on every target, isolated/no network/no original-file overwrite, then captures the frozen x86 app on Windows itself; Historical Preview2 had36 cases/all3classes; the released0.10.1 proof requires and passed121 cases/all13classes perhost/no skips.
- [ ] Install on **physical Windows10 32-bit** with a32-bit CPU/OS, plus WoW64 separately. Record Windows build, architecture, prerequisites, cold-launch, heard playback/output device/seek/volume and a real mixed-rate Studio export. Windows7/8 are unsupported; a32-bit process on an x64 CI runner is not this physical32-bit OS result.
- [ ] Install x86 beside the original x64 build on WoW64; verify separate `Dkord-x86` payload/ID and **Dkord (32-bit)** shortcuts without overwriting Qt6 files/shortcuts. Both retain the stable per-user library/lock, not concurrent writers. Record unchanged original user-file hashes/projects/downloads, including installer/update-over and interrupted installer cases; never uninstall/reset to pass.
- [x] [Published0.10.1 actual frozen-window PNGs and source/runtime/hash receipt](releases/v0.10.1-publication.md#genuine-computer-app-captures) for the requested computer-app preview. Fixtures are clearly marked generated offline audio; do not invent live provider results, reuse phone images or substitute an AI/mock browser render. PNG evidence is not a claim of heard sound, live-provider or physical installation acceptance.
- [ ] Real signed future `windows-x86` updates must stay x86 even when WoW64 reports hostAMD64. Wrong/missing x86 artifacts must fail rather than fall back tox64. Released0.10.1 verifies all eight current installer plans against the pinned original Android identity; future physical update execution remains unchecked. OS publisher signing remains unconfigured.

## Desktop updates and data retention (manifest identity configured; physical acceptance open)
- Preview with empty installed key set must refuse untrusted updates. It must never offer Android APK latest, an incompatible CPU/OS, wrong package type/size/SHA, unknown-key/tampered/duplicate-field manifest, older/equal version or mutable forged plan.
- Released0.10.1 pins the original APK public identity; its format2 desktop manifest was actually signed and verified for all eight native packages. Windows Authenticode / Apple Developer ID + notarization remain unconfigured and are separate from that manifest. Never put private signing material/passwords in chat/Git. PR validation workflows remain read-only, with no release secrets/writes.
- With real authorized releases, check/download/verify/install from the app after consent. Windows gets Windows; Intel Mac gets Intel and Apple Silicon gets arm64; Linux deb/AppImage stays appropriate to the installed distribution. No repeated release-page browsing. Skipped versions and ready-file replacement must remain safe.
- Record user-data directory and audio/database/settings hashes before/after installing over a real previous desktop version. No installer/uninstaller path should delete that directory. Handle app close, interrupted update download, readonly AppImage location, invalid packages and OS permission prompts without losing media/projects.
- There is no automatic phone-to-PC/cloud audio synchronization. JSON moves metadata, not audio; do not record cross-device sync as passed.


## Room co-host controls (Android + PC0.10.1; physical acceptance still unchecked)
- [ ] On at least three real updated devices, creator selects exactly one, then two members; each can play/pause/change song/seek for all opted-in followers. Non-selected member controls remain local.
- [ ] Everyone also admits a newly joined updated member; co-hosts cannot administer permissions. Creator unticks one, reclaims all with Only me, and continues controlling playback.
- [ ] Grant/revoke never opts listeners into audio; verify Sync & play/Follow off, explicit consent, Hindi/large font, duplicate nicknames/IDs and narrow-screen scrolling.
- [ ] Test creator buffering/provider failure, simultaneous controls, delayed/replayed messages, revoke while an intent is in flight, loss/reconnect/429, background/Doze, creator departure, same-room retry and real Leave/rejoin.
- [ ] Updated/old host/guest combinations retain one-way listening; unsigned state cannot downgrade a pinned updated creator. Public relay is not E2EE or a verified-account/private-room server.
- [ ] Test actual lazy MediaController/remote commands for no echo, notification/headset local-only guest behavior, no local Studio/private metadata leak and no stale audio after leaving a room.

JVM and emulator actor/widget cases are executable regressions, not substitutes for these physical/live-provider checks. Protocol: [ROOM_CONTROLS.md](ROOM_CONTROLS.md).
