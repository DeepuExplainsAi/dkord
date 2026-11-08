package app.dkord

import android.content.res.Configuration
import androidx.activity.ComponentActivity
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.unit.Density
import app.dkord.core.Track
import app.dkord.data.room.*
import app.dkord.ui.screens.RoomControlsPanel
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import java.util.Locale

/** Real Compose callbacks and Android JCE/room actors; not a claim of live ntfy/two-phone streaming. */
class RoomCoHostTest {
    @get:Rule val rule = createAndroidComposeRule<ComponentActivity>()
    private val firstId = "1".repeat(32)
    private val secondId = "2".repeat(32)
    private fun access() = RoomAccessState(available = true, selfId = "a".repeat(32), ownerKnown = true,
        canControl = true, connected = true, members = listOf(RoomMember(firstId, "Asha", 1), RoomMember(secondId, "रवि 🎵", 1)))
    private fun member(id: String) = rule.onNodeWithTag("room-member-$id")
    private fun mode(value: RoomControlMode) = rule.onNodeWithTag("room-mode-${value.name}")

    @Test fun creator_can_choose_one_two_and_revoke_using_actual_checkbox_rows() {
        val state = mutableStateOf(access()); val changes = mutableListOf<Pair<String, Boolean>>()
        rule.setContent { MaterialTheme { Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState())) {
            RoomControlsPanel(state.value, true, { state.value = state.value.copy(mode = it) }, { id, allow ->
                changes += id to allow
                state.value = state.value.copy(mode = RoomControlMode.SELECTED,
                    selected = if (allow) state.value.selected + id else state.value.selected - id)
            })
        } } }
        mode(RoomControlMode.HOST_ONLY).assertIsSelected()
        member(firstId).performScrollTo().assertIsOff().performClick()
        member(firstId).assertIsOn(); mode(RoomControlMode.SELECTED).performScrollTo().assertIsSelected()
        member(secondId).performScrollTo().performClick()
        member(firstId).assertIsOn(); member(secondId).assertIsOn()
        member(firstId).performScrollTo().performClick()
        member(firstId).assertIsOff(); member(secondId).assertIsOn()
        rule.runOnIdle { assertEquals(listOf(firstId to true, secondId to true, firstId to false), changes) }
    }
    @Test fun everyone_and_host_only_are_explicit_and_everyone_does_not_offer_fake_individual_revokes() {
        val state = mutableStateOf(access())
        rule.setContent { MaterialTheme { Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState())) {
            RoomControlsPanel(state.value, true, { state.value = state.value.copy(mode = it,
                selected = if (it == RoomControlMode.HOST_ONLY) emptySet() else state.value.selected) }, { _, _ -> fail("Everyone checkboxes must not emit grants") })
        } } }
        mode(RoomControlMode.EVERYONE).performScrollTo().performClick().assertIsSelected()
        member(firstId).performScrollTo().assertIsOn().assertIsNotEnabled()
        member(secondId).performScrollTo().assertIsOn().assertIsNotEnabled()
        mode(RoomControlMode.HOST_ONLY).performScrollTo().performClick().assertIsSelected()
        member(firstId).performScrollTo().assertIsOff().assertIsEnabled()
        rule.runOnIdle { assertTrue(state.value.canControl) }
    }
    @Test fun guests_cannot_see_permission_actions_and_no_content_callback_grants_or_plays() {
        var callbacks = 0
        rule.setContent { MaterialTheme { Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState())) {
            RoomControlsPanel(access().copy(canControl = false), false, { callbacks++ }, { _, _ -> callbacks++ })
        } } }
        mode(RoomControlMode.EVERYONE).assertDoesNotExist(); member(firstId).assertDoesNotExist()
        rule.onNodeWithText(rule.activity.getString(R.string.room_controls_listen_only)).assertIsDisplayed()
        rule.onNodeWithText(rule.activity.getString(R.string.room_controls_consent)).performScrollTo().assertIsDisplayed()
        rule.runOnIdle { assertEquals(0, callbacks) }
    }
    @Test fun hindi_larger_font_permission_rows_are_reachable_with_real_touch_targets_and_wrapping() {
        val ctx = rule.activity.createConfigurationContext(Configuration(rule.activity.resources.configuration).apply { setLocale(Locale.forLanguageTag("hi")) })
        val state = mutableStateOf(access().copy(members = listOf(RoomMember(firstId, "बहुत लंबा सदस्य नाम 🎵 ".repeat(3), 1))))
        rule.setContent {
            val density = LocalDensity.current
            CompositionLocalProvider(LocalContext provides ctx, LocalConfiguration provides ctx.resources.configuration,
                LocalDensity provides Density(density.density, 1.35f)) {
                MaterialTheme { Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState())) {
                    RoomControlsPanel(state.value, true, { state.value = state.value.copy(mode = it) }, { id, allow ->
                        state.value = state.value.copy(mode = RoomControlMode.SELECTED, selected = if (allow) setOf(id) else emptySet())
                    })
                } }
            }
        }
        mode(RoomControlMode.SELECTED).performScrollTo().performClick().assertIsSelected()
        member(firstId).performScrollTo().performClick().assertIsOn()
        val density = rule.activity.resources.displayMetrics.density
        assertTrue(member(firstId).fetchSemanticsNode().boundsInRoot.height >= 48 * density - 1)
        rule.onNodeWithText(ctx.getString(R.string.room_controls_consent)).performScrollTo().assertIsDisplayed()
    }
    @Test fun android_crypto_provider_round_trips_owner_bound_policy_and_rejects_forgery() {
        val owner = RoomIdentity.generate(); val guest = RoomIdentity.generate(); val clock = System.currentTimeMillis()
        val policy = owner.sign(RoomControlMessage(owner.roomCode, RoomControlKind.POLICY, owner.publicKey, clock, 1,
            owner.session, mode = RoomControlMode.EVERYONE, revision = 2))
        assertEquals(policy, RoomControlCodec.decode(RoomControlCodec.encode(policy)))
        assertFalse(RoomControlCodec.verify(guest.sign(policy), owner.roomCode))
        val message = RoomMessage("abcdefghijk", "गाना 🎵", "Artist", positionMs = 1000, playing = true, timestamp = clock)
        val signed = owner.signState(message)
        assertTrue(RoomSignatures.verifyState(checkNotNull(RoomCodec.decode(RoomCodec.encode(signed))), owner.roomCode))
        assertFalse(RoomSignatures.verifyState(signed.copy(playing = false), owner.roomCode))
    }
    @Test fun android_room_actors_deliver_selected_member_intent_to_followers_without_echo_or_autoplay_on_grant() = runBlocking {
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
        val relay = NativeRelay(); val song = Track("abcdefghijk", "First", "Artist")
        val next = Track("lmnopqrstuv", "Second", "Singer")
        val players = List(3) { NativePlayback() }; players[0].states.value = RoomPlaybackState(song, listOf(song))
        val clients = players.map { RoomController(relay, it, scope) }
        try {
            withContext(Dispatchers.Main.immediate) { clients[0].create("Creator") }
            val code = checkNotNull(clients[0].state.value.code)
            withContext(Dispatchers.Main.immediate) { clients.drop(1).forEach { it.join(code) } }
            withTimeout(10_000) { clients[0].state.first { it.access.members.size == 2 } }
            withContext(Dispatchers.Main.immediate) { clients[0].memberControl(clients[1].state.value.access.selfId, true) }
            withTimeout(10_000) { clients[1].state.first { it.access.canControl } }
            assertTrue(players.drop(1).all { it.applied == 0 })
            assertFalse(clients[2].state.value.access.canControl)
            withContext(Dispatchers.Main.immediate) { clients.drop(1).forEach { it.followAutomatically(true) } }
            withTimeout(10_000) { players[2].states.first { it.current?.id == song.id } }
            withContext(Dispatchers.Main.immediate) { players[1].manual(RoomPlaybackState(next, listOf(next), positionMs = 7000, playing = true)) }
            withTimeout(10_000) { players[2].states.first { it.current?.id == next.id && it.playing } }
            withContext(Dispatchers.Main.immediate) {
                yield()
                assertEquals(next.id, clients[0].state.value.host?.videoId)
                assertEquals(1, relay.controls.count { it.kind == RoomControlKind.CONTROL })
                clients[0].controlMode(RoomControlMode.HOST_ONLY)
            }
            withTimeout(10_000) { clients[1].state.first { !it.access.canControl } }
            withContext(Dispatchers.Main.immediate) {
                val count = relay.main.size
                players[1].manual(RoomPlaybackState(song, listOf(song), playing = true)); yield()
                assertEquals(count, relay.main.size)
                assertTrue(relay.main.all { RoomSignatures.verifyState(it, code) })
            }
        } finally {
            withContext(Dispatchers.Main.immediate) { clients.forEach { it.leave() }; scope.cancel() }
        }
    }

    private class NativePlayback : RoomPlayback {
        override val states = MutableStateFlow(RoomPlaybackState())
        override val controls = MutableSharedFlow<RoomPlaybackState>(extraBufferCapacity = 8)
        var applied = 0
        override fun current() = states.value
        suspend fun manual(value: RoomPlaybackState) { states.value = value; controls.emit(value) }
        override suspend fun sync(message: RoomMessage, positionMs: Long) {
            applied++
            val tracks = listOf(RoomTrack(message.videoId, message.title, message.artist, message.thumbnail).toTrack()) + message.queue.map { it.toTrack() }
            states.value = RoomPlaybackState(tracks.first(), tracks, 0, positionMs, message.playing)
        }
    }
    private class NativeRelay : RoomTransport, RoomControlTransport {
        val main = mutableListOf<RoomMessage>(); val controls = mutableListOf<RoomControlMessage>()
        private val playback = MutableSharedFlow<RoomEvent>(replay = 32, extraBufferCapacity = 32)
        private val sharing = MutableSharedFlow<RoomControlEvent>(replay = 32, extraBufferCapacity = 32)
        override suspend fun publish(code: String, message: RoomMessage) {
            val wire = checkNotNull(RoomCodec.decode(RoomCodec.encode(message))); main += wire; playback.emit(RoomEvent(wire))
        }
        override suspend fun latest(code: String) = main.lastOrNull()?.let { RoomEvent(it) }
        override fun subscribe(code: String, after: String?) = playback
        override suspend fun publishControl(code: String, message: RoomControlMessage) {
            val wire = checkNotNull(RoomControlCodec.decode(RoomControlCodec.encode(message))); controls += wire; sharing.emit(RoomControlEvent(wire))
        }
        override fun subscribeControls(code: String, after: String?) = sharing
    }
}
