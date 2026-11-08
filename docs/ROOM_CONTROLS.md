# Listen Together: creator and co-host controls (0.10.0 source)

**Unpublished Android feature.** Execution proof belongs to the exact source/run recorded in HANDOFF.md, not to a source-only test count. This feature is not implemented in the desktop preview.

## Use it

1. Update the creator and participating members to a build containing this feature. Open **Listen Together**, optionally enter a room display name, and create/join with the existing ten-character code.
2. The default is **Only me · room creator**. The creator opens **Playback control access** and ticks one, two or more joined members under **Selected members**, or chooses **Everyone · including new members**.
3. A co-host opens the ordinary app player. Deliberate in-app play/pause, song/queue changes and seeking are proposed to the creator, then broadcast as canonical room playback for listeners who opted into **Sync & play / Follow host**. Progress, buffering, autoplay updates, repeat/shuffle/speed preferences and remote sync are not new co-host commands. Headset/OS notification controls on a guest are local; use the app controls for co-host commands.
4. Untick an individual member to revoke that grant. **Only me** revokes every grant and clears selected choices. The original creator always retains playback controls and exclusive permission administration. A co-host cannot grant themselves or another member access.

**Grant/revoke never starts or stops audio by itself.** A member who has not enabled following is not silently opted in. If simultaneous authorized actions occur, the creator serializes accepted proposals; the latest accepted action wins. The creator must stay reachable. There is no offline host election/ownership takeover.

## Membership, lifecycle and compatibility

- Roster entries are recently active **updated** clients, identified by an ephemeral public-key fingerprint and optional shared display name, not verified accounts or a complete count of all listeners. Use the short ID to distinguish duplicate names. Names can be impersonated; do not treat them as verified identity.
- A retry/reconnect in the same room retains the member key, grants and explicit follow preference. A real Leave or joining a different room discards that identity, queued proposals and consent. Deferred remote MediaController callbacks are invalidated on leave/new room/Follow off; normal local playback commands and already playing audio are not stopped. Rejoining after Leave needs a new grant. Process death also ends the ephemeral session.
- Presence/policy heartbeat: 90 seconds; creator lease/frame freshness: 180 seconds; inactive roster pruning: five minutes. Selected grants are removed when their stale member is pruned. Queued control intents expire after ten seconds and carry the exact permission revision. Receivers reject controls older than ten seconds, allowing at most sixty seconds of forward clock skew; clock-based synchronization is approximate. UI liveness is refreshed periodically and on requests; this is not a network-presence guarantee.
- Old guests still read version-one playback JSON and choose Sync/Follow; they cannot obtain the new controls. An updated guest can listen to an old host one-way, with no co-host administration. Before a verified creator is discovered, legacy unsigned playback remains accepted for compatibility. Once pinned, unsigned/forged playback and replayed signed states are rejected. **Legacy rooms are not retroactively authenticated.**

## Wire and security boundary

- Playback: `dkord-<CODE>`, owner-only canonical writer in updated clients, version-one `RoomMessage` with optional signed `authority` ignored by legacy clients.
- Controls: separate `dkord-<CODE>-controls` topic; signed HELLO, POLICY and CONTROL frames. The public ntfy relay does not enforce these roles. Updated clients validate every signature/permission; old clients do not.
- Room-specific ephemeral P-256 keys and SHA256withECDSA; canonical sorted JSON, separate state/control signing domains, room/session binding, monotonic sender counters, exact permission revisions, bounded age and payloads. The creator code commits to the first **50 bits** of its public-key SHA-256 digest in the existing ten-character alphabet. This is a 50-bit invitation/owner-binding boundary, **not 128-bit room-code strength, a private backend or account authentication**. Member fingerprints use 128 bits. APK/release signing keys are unrelated and unchanged.
- Payloads are strictly below 4,000 UTF-8 bytes, queues at most ten entries, roster/grants at most 48 updated members; metadata is normalized **before** signing. No audio files, stream URLs, private Studio identifiers, cookies or account credentials are sent. Local Studio audio remains local.
- **Not end-to-end encrypted.** The relay can read room names, metadata, public keys and signatures. Anyone with a code can subscribe, publish junk or disrupt a public topic; crypto cannot prevent relay denial of service or secure a legacy listener. Share codes only with trusted people. Disconnecting the creator pauses shared-control coordination rather than transferring ownership.

## Regression/acceptance evidence

The added JVM suites exercise actual signing/codecs, selected/everyone/revoke policy, in-flight policy changes/revoked proposals, replay/forgery/session/revision/freshness rejection, reconnect identity, creator lease, private-audio exclusion, multi-client following and buffering/echo safety. `RoomCoHostTest` adds real Compose EN/HI checkboxes/radio buttons/large-font layout, Android JCE verification and Android room actors through an in-memory wire relay. Existing mandatory keyboard, audio, Studio, library, downloads and search/routing classes remain required.

These tests do not claim a live ntfy session, OEM background behavior, actual provider availability, audio drift accuracy or a multi-physical-phone listening acceptance. Those still need the checklist in PLATFORM_ACCEPTANCE.md / NEW_FEATURE_SMOKE.md. No release is published merely by pushing the feature branch.
