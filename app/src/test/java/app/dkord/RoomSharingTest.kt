package app.dkord

import app.dkord.core.Track
import app.dkord.data.room.*
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.*
import kotlinx.coroutines.flow.*
import org.junit.Assert.*
import org.junit.Test
import java.io.IOException

@OptIn(ExperimentalCoroutinesApi::class)
class RoomSharingTest {
    private val clock = 1_800_000_000_000L
    private class Rig(val relay: ControlRelay, val host: RoomSharing, val guests: List<RoomSharing>, val accepted: MutableList<RoomMessage>)
    private fun TestScope.room(count: Int = 2): Rig {
        val relay = ControlRelay(); val accepted = mutableListOf<RoomMessage>()
        val host = RoomSharing(relay, backgroundScope, true, name = "Creator", now = { clock + testScheduler.currentTime }, onControl = { accepted += it })
        host.start()
        val guests = List(count) { index -> RoomSharing(relay, backgroundScope, false, host.code, "Friend $index", { clock + testScheduler.currentTime }, {}) }
        guests.forEach { it.start() }
        return Rig(relay, host, guests, accepted)
    }
    @Test fun default_is_host_only_and_guest_cannot_change_permissions_or_submit_controls() = runTest {
        val r = room(); runCurrent()
        assertEquals(2, r.host.state.value.members.size)
        assertTrue(r.host.state.value.canControl)
        for (guest in r.guests) {
            assertTrue(guest.state.value.ownerKnown); assertFalse(guest.state.value.canControl)
            guest.setMode(RoomControlMode.EVERYONE); guest.setMember(guest.state.value.selfId, true)
            guest.request(stateOf(roomNext, true))
        }
        runCurrent()
        assertEquals(RoomControlMode.HOST_ONLY, r.host.state.value.mode)
        assertTrue(r.accepted.isEmpty())
        assertTrue(r.relay.frames.none { it.kind == RoomControlKind.CONTROL })
    }
    @Test fun creator_selects_one_then_two_members_and_revokes_individually_or_all() = runTest {
        val r = room(3); runCurrent()
        val ids = r.guests.map { it.state.value.selfId }
        r.host.setMember(ids[0], true); runCurrent()
        assertEquals(listOf(true, false, false), r.guests.map { it.state.value.canControl })
        r.host.setMember(ids[1], true); runCurrent()
        assertEquals(listOf(true, true, false), r.guests.map { it.state.value.canControl })
        r.guests[1].request(stateOf(roomNext, true)); runCurrent()
        assertEquals(roomNext.id, r.accepted.single().videoId)
        r.host.setMember(ids[0], false); runCurrent()
        assertEquals(listOf(false, true, false), r.guests.map { it.state.value.canControl })
        r.host.setMode(RoomControlMode.HOST_ONLY); runCurrent()
        assertTrue(r.host.state.value.selected.isEmpty())
        assertTrue(r.guests.none { it.state.value.canControl })
        assertTrue(r.host.state.value.canControl)
    }
    @Test fun everyone_includes_late_joiners_without_granting_permission_administration() = runTest {
        val r = room(1); runCurrent()
        r.host.setMode(RoomControlMode.EVERYONE); runCurrent()
        val late = RoomSharing(r.relay, backgroundScope, false, r.host.code, "Late friend", { clock }, {})
        late.start(); runCurrent()
        assertTrue(late.state.value.canControl)
        late.setMode(RoomControlMode.HOST_ONLY); runCurrent()
        assertEquals(RoomControlMode.EVERYONE, r.host.state.value.mode)
        late.request(stateOf(roomNext, true, 5000)); runCurrent()
        assertEquals(5000L, r.accepted.single().positionMs)
    }
    @Test fun policy_changed_during_inflight_http_is_published_immediately_not_lost_until_heartbeat() = runTest {
        val relay = ControlRelay(); val held = CompletableDeferred<Unit>(); var first = true
        relay.beforeControl = { if (it.kind == RoomControlKind.POLICY && first) { first = false; held.await() } }
        val host = RoomSharing(relay, backgroundScope, true, now = { clock }, onControl = {})
        host.start(); runCurrent()
        host.setMode(RoomControlMode.EVERYONE); runCurrent()
        assertTrue(relay.frames.isEmpty())
        held.complete(Unit); runCurrent()
        val policies = relay.frames.filter { it.kind == RoomControlKind.POLICY }
        assertEquals(listOf(1L, 2L), policies.map { it.revision })
        assertEquals(RoomControlMode.EVERYONE, policies.last().mode)
    }
    @Test fun revoked_inflight_control_and_replayed_policy_cannot_restore_permission_or_change_audio() = runTest {
        val r = room(1); runCurrent(); val guest = r.guests.single()
        r.host.setMember(guest.state.value.selfId, true); runCurrent()
        val oldPolicy = r.relay.frames.last { it.kind == RoomControlKind.POLICY }
        val held = CompletableDeferred<Unit>()
        r.relay.beforeControl = { if (it.kind == RoomControlKind.CONTROL) held.await() }
        guest.request(stateOf(roomNext, true)); runCurrent()
        r.host.setMember(guest.state.value.selfId, false); runCurrent()
        assertFalse(guest.state.value.canControl)
        held.complete(Unit); runCurrent()
        r.relay.inject(oldPolicy); runCurrent()
        assertTrue(r.accepted.isEmpty()); assertFalse(guest.state.value.canControl)
    }
    @Test fun valid_control_is_applied_once_and_stale_or_wrong_revision_controls_are_rejected() = runTest {
        val r = room(1); runCurrent()
        r.host.setMode(RoomControlMode.EVERYONE); runCurrent()
        val stranger = RoomIdentity.generate(); val policy = r.relay.frames.last { it.kind == RoomControlKind.POLICY }
        fun control(time: Long = clock, rev: Long = policy.revision, session: String = policy.session) = stranger.sign(RoomControlMessage(
            r.host.code, RoomControlKind.CONTROL, stranger.publicKey, time, 1, session,
            revision = rev, snapshot = RoomMessage(roomNext.id, roomNext.title, roomNext.artist, positionMs = 0, playing = true, timestamp = time)))
        val valid = control(); r.relay.inject(valid); r.relay.inject(valid); runCurrent()
        assertEquals(1, r.accepted.size) // Everyone can recover even if HELLO was lost.
        r.relay.inject(control(clock - 10_001)); r.relay.inject(control(rev = policy.revision + 1))
        r.relay.inject(control(session = RoomIdentity.generate().session)); runCurrent()
        assertEquals(1, r.accepted.size)
    }
    @Test fun retry_keeps_member_identity_and_grants_but_a_new_room_identity_gets_no_old_grant() = runTest {
        val r = room(1); runCurrent(); val guest = r.guests.single(); val id = guest.state.value.selfId
        r.host.setMember(id, true); runCurrent()
        guest.stop(); guest.start(); r.host.stop(); r.host.start(); runCurrent()
        assertEquals(id, guest.state.value.selfId); assertTrue(guest.state.value.canControl)
        val replacement = RoomSharing(r.relay, backgroundScope, false, r.host.code, now = { clock }, onControl = {})
        replacement.start(); runCurrent()
        assertNotEquals(id, replacement.state.value.selfId); assertFalse(replacement.state.value.canControl)
    }
    @Test fun transient_publish_failure_retries_fresh_intent_and_stop_discards_unsent_intent() = runTest {
        val r = room(1); runCurrent(); val guest = r.guests.single()
        r.host.setMode(RoomControlMode.EVERYONE); runCurrent()
        var failures = 1
        r.relay.beforeControl = { if (it.kind == RoomControlKind.CONTROL && failures-- > 0) throw IOException("offline") }
        guest.request(stateOf(roomNext, true)); runCurrent()
        assertEquals(RoomSharingError.NETWORK, guest.state.value.error)
        advanceTimeBy(5000); runCurrent()
        assertEquals(1, r.accepted.size)
        r.relay.beforeControl = { if (it.kind == RoomControlKind.CONTROL) throw IOException("offline") }
        guest.request(stateOf(roomSong, true)); runCurrent(); guest.stop()
        r.relay.beforeControl = null; guest.start(); advanceTimeBy(5000); runCurrent()
        assertEquals(1, r.accepted.size)
    }
    @Test fun creator_offline_lease_blocks_new_intent_and_local_studio_audio_never_leaves_device() = runTest {
        val r = room(1); runCurrent(); val guest = r.guests.single()
        r.host.setMode(RoomControlMode.EVERYONE); runCurrent()
        guest.request(stateOf(Track("local-studio-private", "Private mix", "Me"), true)); runCurrent()
        assertEquals(RoomSharingError.LOCAL_AUDIO, guest.state.value.error); assertTrue(r.accepted.isEmpty())
        r.host.stop(); advanceTimeBy(180_001); runCurrent()
        guest.request(stateOf(roomNext, true)); runCurrent()
        assertFalse(guest.state.value.canControl); assertEquals(RoomSharingError.OWNER_OFFLINE, guest.state.value.error)
        assertTrue(r.accepted.isEmpty())
    }
    @Test fun signed_owner_is_pinned_unsigned_downgrade_other_key_and_replays_fail() = runTest {
        val r = room(1); runCurrent(); val guest = r.guests.single()
        val song = RoomMessage(roomSong.id, roomSong.title, roomSong.artist, positionMs = 0, playing = false, timestamp = clock)
        val signed = r.host.signedState(song)
        assertTrue(guest.acceptState(signed)); assertFalse(guest.acceptState(signed))
        assertFalse(guest.acceptState(song)); assertFalse(guest.acceptState(RoomIdentity.generate().signState(song)))
        assertFalse(guest.acceptState(signed.copy(title = "Forged")))
        val legacy = RoomSharing(r.relay, backgroundScope, false, "ABCDEFGHJK", now = { clock }, onControl = {})
        assertTrue(legacy.acceptState(song)) // Compatibility before any verified creator is available.
        assertFalse(legacy.state.value.canControl)
    }
    @Test fun reconnect_refreshes_presence_and_permissions_without_waiting_for_ninety_second_heartbeat() = runTest {
        val r = room(0); runCurrent(); r.host.setMode(RoomControlMode.EVERYONE); runCurrent()
        var streams = 0
        val flaky = object : RoomControlTransport by r.relay {
            override fun subscribeControls(code: String, after: String?) = flow {
                if (++streams == 1) throw IOException("disconnected")
                emitAll(r.relay.subscribeControls(code, after))
            }
        }
        val guest = RoomSharing(flaky, backgroundScope, false, r.host.code, now = { clock + testScheduler.currentTime }, onControl = {})
        guest.start(); runCurrent(); advanceTimeBy(5000); runCurrent()
        assertEquals(2, streams)
        assertTrue(guest.state.value.canControl)
        assertEquals(2, r.relay.frames.count { it.kind == RoomControlKind.HELLO && RoomSignatures.memberId(it.publicKey) == guest.state.value.selfId })
    }

    @Test fun inflight_presence_refresh_cannot_consume_a_pending_manual_intent_it_did_not_publish() = runTest {
        val r = room(0); runCurrent(); r.host.setMode(RoomControlMode.EVERYONE); runCurrent()
        val bootstrap = r.relay.frames.last { it.kind == RoomControlKind.POLICY }
        val disconnect = CompletableDeferred<Unit>(); var streams = 0
        val flaky = object : RoomControlTransport by r.relay {
            override fun subscribeControls(code: String, after: String?) = flow {
                if (++streams == 1) {
                    emit(RoomControlEvent(bootstrap)); disconnect.await(); throw IOException("closed")
                }
                emitAll(r.relay.subscribeControls(code, after))
            }
        }
        val guest = RoomSharing(flaky, backgroundScope, false, r.host.code, now = { clock + testScheduler.currentTime }, onControl = {})
        guest.start(); runCurrent(); assertTrue(guest.state.value.canControl)
        val held = CompletableDeferred<Unit>(); var blocked = false
        r.relay.beforeControl = { if (it.kind == RoomControlKind.HELLO) { blocked = true; held.await() } }
        advanceTimeBy(90_000)
        guest.request(stateOf(roomNext, true)); runCurrent(); assertTrue(blocked)
        disconnect.complete(Unit); runCurrent(); advanceTimeBy(5000); runCurrent()
        held.complete(Unit); runCurrent()
        assertEquals(roomNext.id, r.accepted.single().videoId)
    }

}
