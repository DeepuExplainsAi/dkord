package app.dkord

import app.dkord.core.Track
import app.dkord.data.room.*
import kotlinx.coroutines.flow.*

/** Deterministic in-memory relay, with the real bounded wire codecs at both publish boundaries. */
internal class ControlRelay : RoomTransport, RoomControlTransport {
    val main = mutableListOf<Pair<String, RoomMessage>>()
    val frames = mutableListOf<RoomControlMessage>()
    private val mainEvents = MutableSharedFlow<Pair<String, RoomEvent>>(replay = 128, extraBufferCapacity = 128)
    private val controlEvents = MutableSharedFlow<Pair<String, RoomControlEvent>>(replay = 128, extraBufferCapacity = 128)
    var beforeControl: (suspend (RoomControlMessage) -> Unit)? = null
    override suspend fun publish(code: String, message: RoomMessage) {
        val decoded = checkNotNull(RoomCodec.decode(RoomCodec.encode(message)))
        main += code to decoded
        mainEvents.emit(code to RoomEvent(decoded, "main${main.size}"))
    }
    override suspend fun latest(code: String) = main.lastOrNull { it.first == code }?.let { RoomEvent(it.second, "cached") }
    override fun subscribe(code: String, after: String?) = mainEvents.filter { it.first == code }.map { it.second }
    override suspend fun publishControl(code: String, message: RoomControlMessage) {
        beforeControl?.invoke(message)
        val decoded = checkNotNull(RoomControlCodec.decode(RoomControlCodec.encode(message)))
        check(decoded.room == code)
        frames += decoded
        controlEvents.emit(code to RoomControlEvent(decoded, "control${frames.size}"))
    }
    override fun subscribeControls(code: String, after: String?) = controlEvents.filter { it.first == code }.map { it.second }
    suspend fun inject(frame: RoomControlMessage) { controlEvents.emit(frame.room to RoomControlEvent(frame)) }
}

internal class ControllablePlayback(initial: RoomPlaybackState = RoomPlaybackState()) : RoomPlayback {
    override val states = MutableStateFlow(initial)
    override val controls = MutableSharedFlow<RoomPlaybackState>(extraBufferCapacity = 16)
    val applied = mutableListOf<RoomMessage>()
    var applyImmediately = true
    override fun current() = states.value
    suspend fun manual(value: RoomPlaybackState) { states.value = value; controls.emit(value) }
    override suspend fun sync(message: RoomMessage, positionMs: Long) {
        applied += message.copy(positionMs = positionMs)
        if (applyImmediately) {
            val tracks = listOf(RoomTrack(message.videoId, message.title, message.artist, message.thumbnail).toTrack()) + message.queue.map { it.toTrack() }
            states.value = RoomPlaybackState(tracks.first(), tracks, 0, positionMs, message.playing)
        }
        // Deliberately never emits controls: playback listeners are not manual user actions.
    }
}
internal val roomSong = Track("abcdefghijk", "First song", "Artist")
internal val roomNext = Track("lmnopqrstuv", "Next song", "Singer")
internal fun stateOf(track: Track = roomSong, playing: Boolean = false, position: Long = 0) =
    RoomPlaybackState(track, listOf(track), 0, position, playing)
