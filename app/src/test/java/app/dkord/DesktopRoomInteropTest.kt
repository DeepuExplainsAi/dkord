package app.dkord

import app.dkord.data.room.RoomCodec
import app.dkord.data.room.RoomControlCodec
import app.dkord.data.room.RoomControlMode
import app.dkord.data.room.RoomSignatures
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.*
import org.junit.Test
import java.util.Base64

/** PUBLIC native-generated test vectors; no live relay or production signing keys. */
class DesktopRoomInteropTest {
    private val vector = javaClass.getResourceAsStream("/desktop-room-vectors.json")!!.bufferedReader().use {
        Json.parseToJsonElement(it.readText()).jsonObject
    }
    private val code get() = vector.getValue("code").jsonPrimitive.content

    @Test fun androidVerifiesNativeSignedUnicodeQueueAndIdenticalCanonicalBytes() {
        val state = requireNotNull(RoomCodec.decode(vector.getValue("state").toString()))
        assertTrue(RoomSignatures.verifyState(state, code))
        assertEquals("Song \"संगवारी\" 🎵", state.title)
        assertEquals("lmnopqrstuv", state.queue.single().videoId)
        assertEquals(12345L, state.positionMs)
        assertEquals(vector.getValue("stateSigningBase64").jsonPrimitive.content,
            Base64.getEncoder().encodeToString(RoomSignatures.stateBytes(state)))
        assertFalse(RoomSignatures.verifyState(state.copy(positionMs = state.positionMs + 1), code))
        assertEquals(code, RoomSignatures.ownerCode(state.authority!!.publicKey))
        assertEquals(vector.getValue("memberId").jsonPrimitive.content, RoomSignatures.memberId(state.authority!!.publicKey))
    }

    @Test fun androidVerifiesNativeSelectedTwoMemberGrantAndRejectsPolicyTampering() {
        val policy = requireNotNull(RoomControlCodec.decode(vector.getValue("policy").toString()))
        assertTrue(RoomControlCodec.verify(policy, code))
        assertEquals(RoomControlMode.SELECTED, policy.mode)
        assertEquals(2, policy.selected.size)
        assertEquals("PC संगवारी 🎵", policy.name)
        assertEquals(vector.getValue("policySigningBase64").jsonPrimitive.content,
            Base64.getEncoder().encodeToString(RoomControlCodec.signingBytes(policy)))
        assertFalse(RoomControlCodec.verify(policy.copy(mode = RoomControlMode.EVERYONE), code))
    }
}
