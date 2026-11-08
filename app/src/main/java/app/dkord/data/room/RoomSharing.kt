package app.dkord.data.room

import kotlinx.coroutines.*
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update

/** Recently active updated clients, not a claim that a public relay exposes all legacy listeners. */
data class RoomMember(val id: String, val name: String, val lastSeen: Long, val canControl: Boolean = false)
enum class RoomSharingError { NETWORK, RATE_LIMIT, LOCAL_AUDIO, OWNER_OFFLINE }
data class RoomAccessState(
    val available: Boolean = false,
    val selfId: String = "",
    val selfName: String = "",
    val mode: RoomControlMode = RoomControlMode.HOST_ONLY,
    val selected: Set<String> = emptySet(),
    val members: List<RoomMember> = emptyList(),
    val canControl: Boolean = false,
    val connected: Boolean = false,
    val ownerKnown: Boolean = false,
    val error: RoomSharingError? = null,
)

/** Creator is the sole permissions administrator and canonical playback broadcaster.
 * Guests submit authenticated intents on a different topic; no grant/revoke starts audio.
 * Keys/member IDs are ephemeral to this room, kept across network retry, cleared on real leave.
 */
internal class RoomSharing(
    private val transport: RoomControlTransport,
    private val scope: CoroutineScope,
    val owner: Boolean,
    code: String? = null,
    name: String = "",
    private val now: () -> Long,
    private val onControl: (RoomMessage) -> Unit,
) {
    private val identity = RoomIdentity.generate()
    val code = if (owner) identity.roomCode else requireNotNull(RoomCode.normalize(requireNotNull(code)))
    private val ownName = RoomControlCodec.displayName(name).ifBlank { (if (owner) "Host " else "Listener ") + identity.id.take(6) }
    private val mutable = MutableStateFlow(RoomAccessState(available = true, selfId = identity.id, selfName = ownName, canControl = owner, ownerKnown = owner))
    val state: StateFlow<RoomAccessState> = mutable
    private var ownerKey: String? = if (owner) identity.publicKey else null
    private var ownerSession: String? = if (owner) identity.session else null
    private var revision = if (owner) 1L else 0L
    private var lastPolicySequence = 0L
    private var lastStateSequence = 0L
    private var ownerSeen = if (owner) now() else 0L
    private val members = linkedMapOf<String, RoomMember>()
    private val received = mutableMapOf<String, Long>()
    private var mode = RoomControlMode.HOST_ONLY
    private val selected = linkedSetOf<String>()
    private data class Pending(val snapshot: RoomMessage, val revision: Long)
    private var pending: Pending? = null
    private var hello = !owner
    private var policy = owner
    private var job: Job? = null
    private var generation = 0L
    private var wake = Channel<Unit>(Channel.CONFLATED)
    private var cursor: String? = null

    fun start() {
        stop()
        val epoch = generation
        wake = Channel(Channel.CONFLATED); hello = !owner; policy = owner
        job = scope.launch {
            coroutineScope {
                launch { sendLoop(epoch) }
                launch { receiveLoop(epoch) }
                launch {
                    while (isActive && active(epoch)) {
                        delay(90_000)
                        if (owner) { prune(); policy = true } else hello = true
                        refresh(); wake.trySend(Unit)
                    }
                }
                wake.trySend(Unit)
            }
        }
    }
    /** Cancels both blocking HTTP paths, never transfers an old pending intent to a retry/new room. */
    fun stop() {
        generation++; job?.cancel(); job = null; wake.close(); pending = null
        mutable.update { it.copy(connected = false, canControl = owner) }
    }
    private fun active(epoch: Long) = generation == epoch
    fun setMode(value: RoomControlMode) {
        if (!owner || mode == value) return
        mode = value
        if (value == RoomControlMode.HOST_ONLY) selected.clear()
        revision++; policy = true; refresh(); wake.trySend(Unit)
    }
    fun setMember(id: String, allow: Boolean) {
        if (!owner || id !in members || (mode == RoomControlMode.SELECTED && (id in selected) == allow)) return
        if (allow) selected += id else selected -= id
        // Ticking a person explicitly selects co-host mode; host-only revokes all remembered grants.
        mode = RoomControlMode.SELECTED; revision++; policy = true; refresh(); wake.trySend(Unit)
    }
    fun signedState(message: RoomMessage): RoomMessage = identity.signState(message)
    fun acceptState(message: RoomMessage): Boolean {
        val authority = message.authority
        if (authority == null) return ownerKey == null // legacy one-way room, before a verified creator is known
        if (!RoomSignatures.verifyState(message, code)) return false
        if (ownerKey != null && (ownerKey != authority.publicKey || ownerSession != authority.session)) return false
        if (authority.sequence <= lastStateSequence) return false
        ownerKey = authority.publicKey; ownerSession = authority.session; lastStateSequence = authority.sequence
        ownerSeen = now(); refresh(); return true
    }
    fun request(value: RoomPlaybackState) {
        refresh()
        if (owner || !state.value.canControl) return
        val message = roomMessage(value, now())
        if (message == null) {
            pending = null; mutable.update { it.copy(error = RoomSharingError.LOCAL_AUDIO) }; return
        }
        val clean = runCatching { RoomCodec.decode(RoomCodec.encode(message, 2200)) }.getOrNull() ?: return
        pending = Pending(clean, revision); wake.trySend(Unit)
    }
    private fun allowed(id: String) = mode == RoomControlMode.EVERYONE || (mode == RoomControlMode.SELECTED && id in selected)
    private fun leaseValid() = owner || (ownerSeen > 0 && now() - ownerSeen <= 180_000)
    private fun refresh() {
        val lease = leaseValid()
        mutable.update { old -> old.copy(mode = mode, selected = selected.toSet(),
            members = members.values.map { it.copy(canControl = allowed(it.id)) }, ownerKnown = ownerKey != null,
            canControl = owner || (revision > 0 && lease && old.connected && allowed(identity.id)),
            error = if (!owner && revision > 0 && !lease) RoomSharingError.OWNER_OFFLINE else old.error) }
    }
    private fun prune() {
        val expired = members.values.filter { now() - it.lastSeen > 5 * 60_000 }.map { it.id }
        expired.forEach { members.remove(it); received.remove(it) }
        if (selected.removeAll(expired.toSet())) { revision++; policy = true; wake.trySend(Unit) }
    }
    private fun accept(frame: RoomControlMessage) {
        if (!RoomControlCodec.verify(frame, code) || frame.publicKey == identity.publicKey ||
            frame.timestamp > now() + 60_000 || frame.timestamp < now() - 180_000) return
        val id = RoomSignatures.memberId(frame.publicKey)
        if (owner) {
            if (frame.kind == RoomControlKind.POLICY || (frame.session.isNotEmpty() && frame.session != ownerSession) ||
                frame.sequence <= (received[id] ?: 0)) return
            prune()
            if (frame.kind == RoomControlKind.HELLO) {
                if (id !in members && members.size >= RoomControlCodec.MAX_MEMBERS) return
                received[id] = frame.sequence
                members[id] = RoomMember(id, frame.name.ifBlank { "Listener " + id.take(6) }, now())
                policy = true; refresh(); wake.trySend(Unit)
            } else if (frame.kind == RoomControlKind.CONTROL && frame.revision == revision && allowed(id) &&
                frame.timestamp >= now() - 10_000) {
                // Everyone mode also admits a signed fresh controller whose HELLO was lost in transit.
                if (id !in members && (mode != RoomControlMode.EVERYONE || members.size >= RoomControlCodec.MAX_MEMBERS)) return
                received[id] = frame.sequence
                members[id] = RoomMember(id, frame.name.ifBlank { "Listener " + id.take(6) }, now())
                refresh(); onControl(requireNotNull(frame.snapshot))
            }
        } else if (frame.kind == RoomControlKind.POLICY) {
            if ((ownerKey != null && (frame.publicKey != ownerKey || frame.session != ownerSession)) ||
                frame.sequence <= lastPolicySequence || frame.revision < revision) return
            ownerKey = frame.publicKey; ownerSession = frame.session; lastPolicySequence = frame.sequence; ownerSeen = now()
            if (frame.revision != revision) pending = null
            revision = frame.revision; mode = frame.mode; selected.clear(); selected += frame.selected
            mutable.update { it.copy(connected = true, error = null) }; refresh()
        }
    }
    private suspend fun receiveLoop(epoch: Long) {
        while (currentCoroutineContext().isActive && active(epoch)) {
            try {
                transport.subscribeControls(code, cursor).collect { event ->
                    currentCoroutineContext().ensureActive()
                    if (active(epoch)) {
                        event.cursor?.let { cursor = it }
                        accept(event.message)
                    }
                }
                throw RoomTransportException(false, "Controls stream closed")
            } catch (error: CancellationException) { throw error }
            catch (error: Exception) {
                currentCoroutineContext().ensureActive()
                if (active(epoch)) connectionError(error)
                delay(retryDelay(error))
            }
        }
    }
    private suspend fun sendLoop(epoch: Long) {
        for (ignored in wake) {
            while (active(epoch) && currentCoroutineContext().isActive) {
                val sendHello = hello
                val sendPolicy = owner && policy
                val control = pending?.takeIf { !owner && it.revision == revision && leaseValid() && allowed(identity.id) && now() - it.snapshot.timestamp <= 10_000 }
                if (!sendHello && !sendPolicy && control == null) { pending = null; break }
                val unsigned = when {
                    sendHello -> RoomControlMessage(code, RoomControlKind.HELLO, identity.publicKey, now(), 1, session = ownerSession.orEmpty(), name = ownName)
                    sendPolicy -> RoomControlMessage(code, RoomControlKind.POLICY, identity.publicKey, now(), 1, identity.session, ownName, mode, revision, selected.sorted())
                    else -> RoomControlMessage(code, RoomControlKind.CONTROL, identity.publicKey, checkNotNull(control).snapshot.timestamp, 1,
                        checkNotNull(ownerSession), ownName, revision = control.revision, snapshot = control.snapshot)
                }
                try {
                    transport.publishControl(code, identity.sign(unsigned))
                    currentCoroutineContext().ensureActive()
                    if (!active(epoch)) return
                    if (sendHello) hello = false
                    else if (sendPolicy && unsigned.revision == revision) policy = false
                    else if (pending === control) pending = null
                    mutable.update { it.copy(connected = true, error = null) }; refresh()
                } catch (error: CancellationException) { throw error }
                catch (error: Exception) {
                    currentCoroutineContext().ensureActive()
                    if (active(epoch)) connectionError(error)
                    delay(retryDelay(error))
                }
            }
        }
    }
    private fun retryDelay(error: Exception) = if (error is RoomTransportException && error.rateLimited) 60_000L else 5_000L
    private fun connectionError(error: Exception) {
        mutable.update { it.copy(connected = false, error = if (error is RoomTransportException && error.rateLimited) RoomSharingError.RATE_LIMIT else RoomSharingError.NETWORK) }
        refresh()
    }
}
