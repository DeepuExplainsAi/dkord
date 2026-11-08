package app.dkord.data.room

import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.*
import java.security.KeyFactory
import java.security.KeyPair
import java.security.KeyPairGenerator
import java.security.MessageDigest
import java.security.Signature
import java.security.interfaces.ECPublicKey
import java.security.spec.ECGenParameterSpec
import java.security.spec.X509EncodedKeySpec
import java.util.Base64
import java.util.UUID
import java.util.concurrent.atomic.AtomicLong

@Serializable
enum class RoomControlMode { HOST_ONLY, SELECTED, EVERYONE }

/** Optional v1 extension; old listeners ignore it and keep their existing one-way behavior. */
@Serializable
data class RoomAuthority(val room: String, val publicKey: String, val session: String, val sequence: Long, val signature: String = "")

@Serializable
enum class RoomControlKind { HELLO, POLICY, CONTROL }

/** Never an audio URL, audio byte stream, account or privileged server credential. */
@Serializable
data class RoomControlMessage(
    val room: String,
    val kind: RoomControlKind,
    val publicKey: String,
    val timestamp: Long,
    val sequence: Long,
    val session: String = "",
    val name: String = "",
    val mode: RoomControlMode = RoomControlMode.HOST_ONLY,
    val revision: Long = 0,
    val selected: List<String> = emptyList(),
    val snapshot: RoomMessage? = null,
    val signature: String = "",
    val version: Int = 1,
)

data class RoomControlEvent(val message: RoomControlMessage, val cursor: String? = null)

/** Per-room ephemeral P-256 key, unrelated to the Android APK or desktop release signing keys. */
class RoomIdentity private constructor(private val keys: KeyPair) {
    val publicKey: String = RoomSignatures.encode(keys.public.encoded)
    val id: String = RoomSignatures.memberId(publicKey)
    val roomCode: String = RoomSignatures.ownerCode(publicKey)
    val session: String = UUID.randomUUID().toString().replace("-", "")
    private val sequence = AtomicLong()
    private fun next() = sequence.incrementAndGet().also { check(it > 0) }
    private fun sign(bytes: ByteArray): String = Signature.getInstance("SHA256withECDSA").run {
        initSign(keys.private); update(bytes); RoomSignatures.encode(sign())
    }
    fun sign(message: RoomControlMessage): RoomControlMessage {
        val unsigned = message.copy(publicKey = publicKey, sequence = next(), signature = "")
        return unsigned.copy(signature = sign(RoomControlCodec.signingBytes(unsigned)))
    }
    fun signState(message: RoomMessage): RoomMessage {
        // Reserve signature/authority overhead before signing; encoding must not trim signed fields.
        val clean = requireNotNull(RoomCodec.decode(RoomCodec.encode(message.copy(authority = null), 3000)))
        val unsigned = clean.copy(authority = RoomAuthority(roomCode, publicKey, session, next()))
        return unsigned.copy(authority = unsigned.authority!!.copy(signature = sign(RoomSignatures.stateBytes(unsigned))))
    }
    companion object {
        fun generate() = RoomIdentity(KeyPairGenerator.getInstance("EC").run {
            initialize(ECGenParameterSpec("secp256r1")); generateKeyPair()
        })
    }
}

object RoomSignatures {
    private val base64 = Base64.getUrlEncoder().withoutPadding()
    private val decoder = Base64.getUrlDecoder()
    private val token = Regex("[A-Za-z0-9_-]+")
    private val nonce = Regex("[a-f0-9]{32}")
    private val order = "ffffffff00000000ffffffffffffffffbce6faada7179e84f3b9cac2fc632551"
    internal val json = Json { ignoreUnknownKeys = true; encodeDefaults = true }
    fun encode(bytes: ByteArray): String = base64.encodeToString(bytes)
    private fun bytes(value: String) = decoder.decode(value)
    private fun parsePublicKey(value: String): ECPublicKey {
        require(value.length in 120..128 && token.matches(value))
        val key = KeyFactory.getInstance("EC").generatePublic(X509EncodedKeySpec(bytes(value))) as ECPublicKey
        require(key.params.curve.field.fieldSize == 256 && key.params.order.toString(16) == order)
        return key
    }
    fun memberId(publicKey: String): String = MessageDigest.getInstance("SHA-256").digest(bytes(publicKey))
        .take(16).joinToString("") { "%02x".format(it.toInt() and 255) }
    /** Same 10-character alphabet/entropy as legacy codes, now commits to the creator's public key. */
    fun ownerCode(publicKey: String): String {
        val hash = MessageDigest.getInstance("SHA-256").digest(bytes(publicKey))
        var accumulator = 0; var bits = 0
        return buildString {
            for (byte in hash) {
                accumulator = (accumulator shl 8) or (byte.toInt() and 255); bits += 8
                while (bits >= 5 && length < RoomCode.LENGTH) {
                    bits -= 5; append(RoomCode.ALPHABET[(accumulator ushr bits) and 31])
                }
                if (length == RoomCode.LENGTH) break
            }
        }
    }
    fun validSession(value: String) = nonce.matches(value)
    fun validMemberId(value: String) = nonce.matches(value)
    fun verify(publicKey: String, signature: String, content: ByteArray): Boolean = runCatching {
        require(signature.length in 86..104 && token.matches(signature))
        Signature.getInstance("SHA256withECDSA").run { initVerify(parsePublicKey(publicKey)); update(content); verify(bytes(signature)) }
    }.getOrDefault(false)
    internal fun canonical(value: JsonElement): String = when (value) {
        is JsonObject -> value.keys.sorted().joinToString(",", "{", "}") { JsonPrimitive(it).toString() + ":" + canonical(value.getValue(it)) }
        is JsonArray -> value.joinToString(",", "[", "]", transform = ::canonical)
        else -> value.toString()
    }
    fun stateBytes(message: RoomMessage): ByteArray = ("dkord-room-state-v1\n" + canonical(json.encodeToJsonElement(
        message.copy(authority = message.authority?.copy(signature = ""))))).toByteArray(Charsets.UTF_8)
    fun verifyState(message: RoomMessage, code: String): Boolean = runCatching {
        val authority = requireNotNull(message.authority)
        authority.room == code && authority.sequence > 0 && validSession(authority.session) &&
            ownerCode(authority.publicKey) == code && verify(authority.publicKey, authority.signature, stateBytes(message))
    }.getOrDefault(false)
}

object RoomControlCodec {
    const val MAX_MEMBERS = 48
    private val json get() = RoomSignatures.json
    fun displayName(value: String): String = value.filter { !it.isISOControl() && it !in '\u202a'..'\u202e' && it !in '\u2066'..'\u2069' }
        .trim().take(48).let { if (it.lastOrNull()?.isHighSurrogate() == true) it.dropLast(1) else it }
    fun signingBytes(message: RoomControlMessage) = ("dkord-room-controls-v1\n" + RoomSignatures.canonical(
        json.encodeToJsonElement(message.copy(signature = "")))).toByteArray(Charsets.UTF_8)
    fun verify(message: RoomControlMessage, code: String): Boolean = runCatching {
        require(message.version == 1 && message.publicKey.length in 120..128)
        require(RoomCode.normalize(code) == code && message.room == code && message.timestamp > 0 && message.sequence > 0)
        require(message.name == displayName(message.name) && message.selected.size <= MAX_MEMBERS &&
            message.selected.distinct().size == message.selected.size && message.selected.all(RoomSignatures::validMemberId))
        when (message.kind) {
            RoomControlKind.HELLO -> require(message.snapshot == null && (message.session.isEmpty() || RoomSignatures.validSession(message.session)))
            RoomControlKind.POLICY -> require(message.snapshot == null && message.revision > 0 && RoomSignatures.validSession(message.session) && RoomSignatures.ownerCode(message.publicKey) == code)
            RoomControlKind.CONTROL -> require(message.revision > 0 && RoomSignatures.validSession(message.session) &&
                message.snapshot != null && message.snapshot.authority == null && message.snapshot.timestamp == message.timestamp && RoomCodec.decode(RoomCodec.encode(message.snapshot, 2200)) == message.snapshot)
        }
        require(RoomSignatures.verify(message.publicKey, message.signature, signingBytes(message)))
        require(json.encodeToString(message).toByteArray(Charsets.UTF_8).size < RoomCodec.MAX_BYTES)
        true
    }.getOrDefault(false)
    fun encode(message: RoomControlMessage): String {
        require(verify(message, message.room)) { "Invalid room control message" }
        return json.encodeToString(message)
    }
    fun decode(text: String): RoomControlMessage? = runCatching {
        require(text.toByteArray(Charsets.UTF_8).size < RoomCodec.MAX_BYTES)
        json.decodeFromString<RoomControlMessage>(text).takeIf { verify(it, it.room) }
    }.getOrNull()
    fun decodeRelayLine(line: String): RoomControlEvent? = runCatching {
        require(line.toByteArray(Charsets.UTF_8).size <= 16_384)
        val data = json.parseToJsonElement(line).jsonObject
        if (data["event"]?.jsonPrimitive?.content != "message") null
        else decode(data.getValue("message").jsonPrimitive.content)?.let {
            RoomControlEvent(it, data["id"]?.jsonPrimitive?.content?.takeIf { value -> value.matches(Regex("[A-Za-z0-9_-]{1,64}")) })
        }
    }.getOrNull()
}
