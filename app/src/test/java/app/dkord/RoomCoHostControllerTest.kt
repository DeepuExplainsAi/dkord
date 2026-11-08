package app.dkord

import app.dkord.data.room.*
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.*
import kotlinx.coroutines.flow.MutableStateFlow
import org.junit.Assert.*
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class RoomCoHostControllerTest {
    private val clock = 1_800_000_000_000L
    private data class Client(val controller: RoomController, val playback: ControllablePlayback)
    private fun TestScope.client(relay: RoomTransport, initial: RoomPlaybackState = RoomPlaybackState()): Client {
        val playback = ControllablePlayback(initial)
        return Client(RoomController(relay, playback, backgroundScope) { clock + testScheduler.currentTime }, playback)
    }
    @Test fun selected_two_can_play_pause_switch_and_seek_for_all_opted_in_listeners() = runTest {
        val relay = ControlRelay(); val host = client(relay, stateOf()); host.controller.create("Owner"); runCurrent()
        val guests = List(3) { client(relay) }
        guests.forEachIndexed { i, g -> g.controller.join(checkNotNull(host.controller.state.value.code), "Friend $i") }; runCurrent()
        assertTrue(guests.all { it.playback.applied.isEmpty() })
        host.controller.memberControl(guests[0].controller.state.value.access.selfId, true)
        host.controller.memberControl(guests[1].controller.state.value.access.selfId, true); runCurrent()
        assertEquals(listOf(true, true, false), guests.map { it.controller.state.value.access.canControl })
        assertTrue(guests.all { it.playback.applied.isEmpty() }) // A grant alone never plays.
        guests.forEach { it.controller.followAutomatically(true) }; runCurrent()
        guests[0].playback.manual(stateOf(roomNext, true, 2500)); runCurrent()
        assertEquals(roomNext.id, host.playback.applied.last().videoId)
        assertTrue(guests.all { it.playback.applied.last().videoId == roomNext.id && it.playback.applied.last().playing })
        guests[1].playback.manual(stateOf(roomNext, false, 8000)); runCurrent()
        assertTrue(host.controller.state.value.host?.playing == false)
        assertTrue(guests.all { !it.playback.applied.last().playing && it.playback.applied.last().positionMs == 8000L })
        val publications = relay.main.size
        guests[2].playback.manual(stateOf(roomSong, true)); runCurrent()
        assertEquals(publications, relay.main.size)
        assertEquals(roomNext.id, host.controller.state.value.host?.videoId)
        assertTrue(relay.main.all { RoomSignatures.verifyState(it.second, it.first) })
    }
    @Test fun everyone_includes_new_members_revoke_and_creator_reclaim_do_not_start_or_stop_audio() = runTest {
        val relay = ControlRelay(); val host = client(relay, stateOf()); host.controller.create(); runCurrent()
        host.controller.controlMode(RoomControlMode.EVERYONE); runCurrent()
        val friend = client(relay); friend.controller.join(checkNotNull(host.controller.state.value.code)); runCurrent()
        assertTrue(friend.controller.state.value.access.canControl); assertTrue(friend.playback.applied.isEmpty())
        friend.playback.manual(stateOf(roomNext, true)); runCurrent()
        val hostSyncs = host.playback.applied.size; val publications = relay.main.size
        host.controller.controlMode(RoomControlMode.HOST_ONLY); runCurrent()
        assertFalse(friend.controller.state.value.access.canControl)
        assertEquals(hostSyncs, host.playback.applied.size); assertEquals(publications, relay.main.size)
        friend.controller.controlMode(RoomControlMode.EVERYONE); friend.playback.manual(stateOf(roomSong, true)); runCurrent()
        assertEquals(publications, relay.main.size)
        host.playback.manual(stateOf(roomSong, false, 750)); runCurrent()
        assertEquals(roomSong.id, host.controller.state.value.host?.videoId)
    }
    @Test fun remote_sync_and_progress_never_echo_a_command_from_authorized_members() = runTest {
        val relay = ControlRelay(); val host = client(relay, stateOf()); host.controller.create(); runCurrent()
        val friends = List(3) { client(relay) }
        friends.forEach { it.controller.join(checkNotNull(host.controller.state.value.code)) }; runCurrent()
        host.controller.controlMode(RoomControlMode.EVERYONE); runCurrent()
        friends.forEach { it.controller.followAutomatically(true) }; runCurrent()
        assertTrue(relay.frames.none { it.kind == RoomControlKind.CONTROL })
        friends[0].playback.manual(stateOf(roomNext, true)); runCurrent()
        assertEquals(1, relay.frames.count { it.kind == RoomControlKind.CONTROL })
        friends.forEach { it.playback.states.value = it.playback.current().copy(positionMs = 600) }; runCurrent()
        assertEquals(1, relay.frames.count { it.kind == RoomControlKind.CONTROL })
        assertEquals(2, relay.main.size) // Initial host state + one accepted intention, not 3 guest echoes.
    }
    @Test fun stale_owner_buffering_cannot_replace_the_cohost_canonical_requested_song_or_play_intent() = runTest {
        val relay = ControlRelay(); val host = client(relay, stateOf()); host.playback.applyImmediately = false
        host.controller.create(); runCurrent()
        val friend = client(relay); friend.controller.join(checkNotNull(host.controller.state.value.code)); runCurrent()
        host.controller.controlMode(RoomControlMode.EVERYONE); runCurrent()
        val before = relay.main.size
        friend.playback.manual(stateOf(roomNext, true, 9000)); runCurrent()
        host.playback.states.value = stateOf(roomSong, false, 100); runCurrent()
        advanceTimeBy(15_000); runCurrent()
        val canonical = relay.main.drop(before).map { it.second }
        assertTrue(canonical.isNotEmpty())
        assertTrue(canonical.all { it.videoId == roomNext.id && it.playing })
        host.playback.manual(stateOf(roomSong, false, 300)); runCurrent()
        assertEquals(roomSong.id, relay.main.last().second.videoId) // A genuine creator action reclaims control.
    }
    @Test fun retry_preserves_grant_and_identity_real_leave_requires_new_grant_and_new_follow_consent() = runTest {
        val relay = ControlRelay(); val host = client(relay, stateOf()); host.controller.create(); runCurrent()
        val friend = client(relay); val code = checkNotNull(host.controller.state.value.code)
        friend.controller.join(code); runCurrent(); val id = friend.controller.state.value.access.selfId
        host.controller.memberControl(id, true); friend.controller.followAutomatically(true); runCurrent()
        friend.controller.retry(); host.controller.retry(); runCurrent()
        assertEquals(id, friend.controller.state.value.access.selfId); assertTrue(friend.controller.state.value.access.canControl)
        assertTrue(friend.controller.state.value.followAutomatically)
        friend.controller.leave(); friend.controller.join(code); runCurrent()
        assertNotEquals(id, friend.controller.state.value.access.selfId); assertFalse(friend.controller.state.value.access.canControl)
        assertFalse(friend.controller.state.value.followAutomatically); assertFalse(friend.controller.state.value.hasSynced)
    }
    @Test fun current_guest_can_follow_a_legacy_room_without_ever_becoming_a_cohost() = runTest {
        val relay = ControlRelay()
        val legacyTransport = object : RoomTransport by relay {}
        val host = client(legacyTransport, stateOf()); host.controller.create(); runCurrent()
        val friend = client(relay); friend.controller.join(checkNotNull(host.controller.state.value.code)); runCurrent()
        assertFalse(friend.controller.state.value.access.ownerKnown)
        assertTrue(friend.playback.applied.isEmpty())
        friend.controller.syncNow(); runCurrent()
        assertEquals(roomSong.id, friend.playback.applied.single().videoId)
        friend.playback.manual(stateOf(roomNext, true)); runCurrent()
        assertEquals(1, relay.main.size); assertTrue(relay.frames.none { it.kind == RoomControlKind.CONTROL })
    }
    private class DeferredPlayback : RoomPlayback {
        override val states = MutableStateFlow(stateOf(roomNext, true))
        private var generation = 0
        private val queued = mutableListOf<() -> Unit>()
        var applied = 0
        override fun current() = states.value
        override fun cancelSync() { generation++ }
        override suspend fun sync(message: RoomMessage, positionMs: Long) {
            val request = ++generation
            queued += { if (request == generation) applied++ }
        }
        fun connect() { queued.toList().also { queued.clear() }.forEach { it() } }
    }
    @Test fun leave_new_room_and_follow_off_invalidate_queued_remote_audio_without_stopping_local_playback() = runTest {
        val relay = ControlRelay(); val host = client(relay, stateOf()); host.controller.create(); runCurrent()
        val playback = DeferredPlayback(); val guest = RoomController(relay, playback, backgroundScope) { clock }
        val code = checkNotNull(host.controller.state.value.code)
        guest.join(code); runCurrent(); guest.followAutomatically(true); runCurrent()
        guest.followAutomatically(false); playback.connect(); assertEquals(0, playback.applied)
        guest.syncNow(); runCurrent(); guest.leave(); playback.connect(); assertEquals(0, playback.applied)
        guest.join(code); runCurrent(); guest.syncNow(); runCurrent()
        guest.join("ABCDEFGHJK"); runCurrent(); playback.connect(); assertEquals(0, playback.applied)
        assertEquals(roomNext.id, playback.current().current?.id); assertTrue(playback.current().playing)
    }
    @Test fun same_room_retry_keeps_the_already_consented_deferred_sync() = runTest {
        val relay = ControlRelay(); val host = client(relay, stateOf()); host.controller.create(); runCurrent()
        val playback = DeferredPlayback(); val guest = RoomController(relay, playback, backgroundScope) { clock }
        guest.join(checkNotNull(host.controller.state.value.code)); runCurrent()
        guest.followAutomatically(true); runCurrent(); guest.retry(); runCurrent()
        playback.connect(); assertEquals(1, playback.applied)
        assertTrue(guest.state.value.followAutomatically)
    }

}
