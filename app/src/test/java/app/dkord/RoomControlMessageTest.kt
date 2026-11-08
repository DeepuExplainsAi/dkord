package app.dkord

import app.dkord.data.room.*
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.*
import org.junit.Assert.*
import org.junit.Test

class RoomControlMessageTest {
    private val clock = 1_800_000_000_000L
    private fun song() = RoomMessage("abcdefghijk", "Song", "Artist", positionMs = 1200, playing = true, timestamp = clock)
    private fun hello(id: RoomIdentity, code: String = id.roomCode) = id.sign(RoomControlMessage(code,
        RoomControlKind.HELLO, id.publicKey, clock, 1, name = "आशा 🎵"))
    private fun policy(id: RoomIdentity, mode: RoomControlMode = RoomControlMode.SELECTED) = id.sign(RoomControlMessage(id.roomCode,
        RoomControlKind.POLICY, id.publicKey, clock, 1, session = id.session, mode = mode, revision = 3,
        selected = listOf(RoomIdentity.generate().id, RoomIdentity.generate().id)))

    @Test fun creator_code_commits_to_public_key_and_retains_ten_character_format() {
        val a = RoomIdentity.generate(); val b = RoomIdentity.generate()
        assertEquals(a.roomCode, RoomSignatures.ownerCode(a.publicKey))
        assertEquals(a.roomCode, RoomCode.normalize(a.roomCode))
        assertEquals(10, a.roomCode.length)
        assertNotEquals(a.roomCode, b.roomCode)
        assertEquals(32, a.id.length)
        assertNotEquals(a.id, b.id)
    }
    @Test fun signed_hello_policy_and_control_round_trip() {
        val host = RoomIdentity.generate(); val member = RoomIdentity.generate()
        val control = member.sign(RoomControlMessage(host.roomCode, RoomControlKind.CONTROL, member.publicKey, clock,
            1, host.session, revision = 3, snapshot = song()))
        for (frame in listOf(hello(member, host.roomCode), policy(host), control)) {
            assertTrue(RoomControlCodec.verify(frame, host.roomCode))
            assertEquals(frame, RoomControlCodec.decode(RoomControlCodec.encode(frame)))
        }
    }
    @Test fun changing_permissions_name_room_session_or_playback_breaks_signature() {
        val host = RoomIdentity.generate(); val signed = policy(host)
        for (bad in listOf(signed.copy(mode = RoomControlMode.EVERYONE), signed.copy(name = "Someone else"),
            signed.copy(room = RoomIdentity.generate().roomCode), signed.copy(revision = 99),
            signed.copy(session = RoomIdentity.generate().session), signed.copy(selected = emptyList()))) {
            assertFalse(RoomControlCodec.verify(bad, bad.room))
        }
        val control = host.sign(RoomControlMessage(host.roomCode, RoomControlKind.CONTROL, host.publicKey, clock,
            1, host.session, revision = 3, snapshot = song()))
        assertFalse(RoomControlCodec.verify(control.copy(snapshot = song().copy(playing = false)), host.roomCode))
    }
    @Test fun another_member_cannot_sign_a_policy_for_the_creator_room() {
        val host = RoomIdentity.generate(); val other = RoomIdentity.generate()
        val forged = other.sign(policy(host).copy(publicKey = other.publicKey, mode = RoomControlMode.EVERYONE))
        assertFalse(RoomControlCodec.verify(forged, host.roomCode))
    }
    @Test fun signed_main_state_round_trips_and_tampering_or_other_owner_fails() {
        val host = RoomIdentity.generate(); val signed = host.signState(song())
        val decoded = checkNotNull(RoomCodec.decode(RoomCodec.encode(signed)))
        assertTrue(RoomSignatures.verifyState(decoded, host.roomCode))
        assertFalse(RoomSignatures.verifyState(decoded.copy(positionMs = 500), host.roomCode))
        assertFalse(RoomSignatures.verifyState(decoded.copy(playing = false), host.roomCode))
        assertFalse(RoomSignatures.verifyState(decoded, RoomIdentity.generate().roomCode))
        assertFalse(RoomSignatures.verifyState(song(), host.roomCode))
    }
    @Test fun signed_state_normalizes_before_signing_not_after_and_fits_utf8_budget() {
        val host = RoomIdentity.generate()
        val heavy = song().copy(title = "गाना 🎧".repeat(100), artist = "कलाकार".repeat(100),
            thumbnail = "https://i.ytimg.com/" + "a".repeat(480),
            queue = (1..20).map { RoomTrack("q" + it.toString().padStart(10, '0'), "गीत 🎵".repeat(100), "कलाकार".repeat(100)) })
        val signed = host.signState(heavy)
        val text = RoomCodec.encode(signed)
        assertTrue(text.toByteArray(Charsets.UTF_8).size < 4000)
        assertEquals(signed, RoomCodec.decode(text))
        assertTrue(RoomSignatures.verifyState(checkNotNull(RoomCodec.decode(text)), host.roomCode))
        assertTrue(signed.queue.isNotEmpty())
    }
    @Test fun old_listener_ignores_authority_and_still_reads_version_one_playback() {
        val host = RoomIdentity.generate(); val signed = host.signState(song())
        val old = Json { ignoreUnknownKeys = true }.decodeFromString<LegacyPlayback>(RoomCodec.encode(signed))
        assertEquals(song().videoId, old.videoId); assertEquals(song().playing, old.playing)
        assertEquals(1, old.version); assertEquals(song().positionMs, old.positionMs)
        assertNull(RoomCodec.decode(RoomCodec.encode(song()))!!.authority)
    }
    @Serializable private data class LegacyPlayback(val videoId: String, val title: String, val artist: String,
        val positionMs: Long, val playing: Boolean, val timestamp: Long, val version: Int = 1)

    @Test fun counters_increase_across_control_and_state_domains() {
        val id = RoomIdentity.generate()
        val first = hello(id).sequence; val second = checkNotNull(id.signState(song()).authority).sequence
        assertTrue(first > 0); assertTrue(second > first); assertTrue(hello(id).sequence > second)
    }
    @Test fun malicious_keys_signatures_version_and_unbounded_names_are_rejected() {
        val id = RoomIdentity.generate(); val frame = hello(id)
        for (bad in listOf(frame.copy(publicKey = "x".repeat(123)), frame.copy(signature = "bad"),
            frame.copy(signature = "x".repeat(2000)), frame.copy(version = 2), frame.copy(sequence = 0),
            frame.copy(name = "x".repeat(49)), frame.copy(timestamp = 0))) {
            assertFalse(RoomControlCodec.verify(bad, id.roomCode))
        }
    }
    @Test fun roster_policy_is_bounded_and_cannot_have_duplicate_or_invalid_member_ids() {
        val id = RoomIdentity.generate(); val frame = policy(id)
        for (selected in listOf(listOf("bad"), listOf(frame.selected.first(), frame.selected.first()),
            (1..49).map { it.toString(16).padStart(32, '0') })) {
            assertFalse(RoomControlCodec.verify(id.sign(frame.copy(selected = selected)), id.roomCode))
        }
        val maximum = id.sign(frame.copy(selected = (1..48).map { it.toString(16).padStart(32, '0') }))
        assertTrue(RoomControlCodec.encode(maximum).toByteArray(Charsets.UTF_8).size < 4000)
    }
    @Test fun names_remove_controls_and_bidi_overrides_without_cutting_surrogates() {
        assertEquals("आशा 🎵", RoomControlCodec.displayName(" \u202eआशा\n 🎵\u0000 "))
        val name = RoomControlCodec.displayName("a".repeat(47) + "🎵")
        assertEquals(47, name.length); assertFalse(name.last().isHighSurrogate())
    }
    @Test fun relay_parser_bounds_lines_ignores_keepalives_and_sanitizes_cursors() {
        val signed = hello(RoomIdentity.generate())
        fun line(cursor: String) = buildJsonObject {
            put("event", "message"); put("id", cursor); put("message", RoomControlCodec.encode(signed))
        }.toString()
        assertEquals("c1", RoomControlCodec.decodeRelayLine(line("c1"))?.cursor)
        assertEquals(signed, RoomControlCodec.decodeRelayLine(line("c1"))?.message)
        assertNull(RoomControlCodec.decodeRelayLine(line("../bad"))?.cursor)
        assertNull(RoomControlCodec.decodeRelayLine("{\"event\":\"keepalive\"}"))
        assertNull(RoomControlCodec.decodeRelayLine("x".repeat(16_385)))
        assertNull(RoomControlCodec.decode("x".repeat(4000)))
    }
    @Test fun a_control_frame_cannot_nest_authority_local_audio_or_mismatched_timestamp() {
        val host = RoomIdentity.generate(); val base = RoomControlMessage(host.roomCode, RoomControlKind.CONTROL,
            host.publicKey, clock, 1, host.session, revision = 1, snapshot = song())
        for (snapshot in listOf(host.signState(song()), song().copy(videoId = "local-studio-private"), song().copy(timestamp = clock - 1))) {
            assertFalse(RoomControlCodec.verify(host.sign(base.copy(snapshot = snapshot)), host.roomCode))
        }
    }
}
