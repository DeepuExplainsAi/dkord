@file:OptIn(UnstableApi::class)

package app.dkord.player

import app.dkord.core.isLocalAudioId

import android.content.ComponentName
import android.content.Context
import androidx.media3.common.Player
import androidx.media3.common.util.UnstableApi
import androidx.media3.session.MediaController
import androidx.media3.session.SessionToken
import app.dkord.core.DebugLog
import app.dkord.core.Track
import com.google.common.util.concurrent.MoreExecutors
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.launch

data class PlayerUiState(
    val connected: Boolean = false,
    val current: Track? = null,
    val isPlaying: Boolean = false,
    val isBuffering: Boolean = false,
    val positionMs: Long = 0,
    val durationMs: Long = 0,
    val bufferedMs: Long = 0,
    val shuffle: Boolean = false,
    val repeatMode: Int = Player.REPEAT_MODE_OFF,
    val speed: Float = 1f,
    val queue: List<Track> = emptyList(),
    val queueIndex: Int = -1,
    val hasNext: Boolean = false,
    val hasPrevious: Boolean = false,
)

/**
 * UI-side handle to the playback service. Safe to create anywhere: it connects lazily, reconnects
 * if the service dies, and survives Activity recreation because it is an app-level singleton.
 */
class PlayerController(
    private val context: Context,
    private val sleepTimer: SleepTimer,
    private val music: app.dkord.data.yt.MusicRepository,
    private val settings: app.dkord.data.settings.SettingsRepository,
) {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
    private val _state = MutableStateFlow(PlayerUiState())
    val state: StateFlow<PlayerUiState> = _state
    private val commandGate = PlaybackCommandGate()
    private val commandEvents = MutableSharedFlow<PlayerUiState>(extraBufferCapacity = 8, onBufferOverflow = BufferOverflow.DROP_OLDEST)
    /** Explicit in-app commands only: buffering, focus, progress and remote sync are not co-host intent. */
    val commands: kotlinx.coroutines.flow.SharedFlow<PlayerUiState> = commandEvents
    fun withoutRoomCommands(block: () -> Unit) = commandGate.remotely(block)
    val sleep: StateFlow<SleepState> get() = sleepTimer.state

    private var controller: MediaController? = null
    private var connecting = false
    private val pending = ArrayDeque<(MediaController) -> Unit>()
    // Session-only recommendation intent; never serialized into MediaItems, Track or rooms.
    private var radioSeed: Track? = null
    private var radioHint = ""
    private val autoplay = AutoplayCoordinator(scope,
        source = { track, queue, hint -> music.related(track, queue, hint) },
        snapshot = ::autoplaySnapshot,
        append = ::appendAutoplay,
    )

    fun connect() {
        if (controller != null || connecting) return
        connecting = true
        val token = SessionToken(context, ComponentName(context, PlaybackService::class.java))
        val future = MediaController.Builder(context, token)
            .setListener(object : MediaController.Listener {
                override fun onDisconnected(controller: MediaController) {
                    DebugLog.w("controller", "service disconnected")
                    autoplay.invalidate()
                    radioSeed = null; radioHint = ""
                    this@PlayerController.controller = null
                    _state.value = PlayerUiState()
                }
            })
            .buildAsync()
        future.addListener({
            connecting = false
            runCatching { future.get() }
                .onSuccess { c ->
                    autoplay.invalidate()
                    controller = c
                    c.addListener(listener)
                    refresh(c)
                    while (pending.isNotEmpty()) pending.removeFirst().invoke(c)
                }
                .onFailure { DebugLog.e("controller", "connect failed", it) }
        }, MoreExecutors.directExecutor())
    }

    private inline fun withController(crossinline block: (MediaController) -> Unit) {
        val report = commandGate.report
        val execute: (MediaController) -> Unit = { value ->
            block(value)
            if (report && commandEvents.subscriptionCount.value > 0) {
                // playWhenReady is the user's intent even while media is still buffering.
                commandEvents.tryEmit(snapshot(value).copy(isPlaying = value.playWhenReady))
            }
        }
        val c = controller
        if (c != null) execute(c) else { pending.addLast(execute); connect() }
    }

    // ---- commands ----

    /** Replaces the queue and starts playing [tracks][startIndex]. */
    fun play(tracks: List<Track>, startIndex: Int = 0, contextHint: String = "") = withController { c ->
        if (tracks.isEmpty()) return@withController
        autoplay.invalidate()
        // Explicit album/playlist/Play all keeps every chosen item; extend its tail only afterwards.
        radioSeed = tracks.last()
        radioHint = contextHint.take(200)
        c.setMediaItems(tracks.map { it.toMediaItem() }, startIndex.coerceIn(0, tracks.lastIndex), 0)
        c.prepare(); c.play()
    }

    fun playTrack(track: Track) = play(listOf(track))
    fun playRelated(track: Track, contextHint: String = "") = play(listOf(track), contextHint = contextHint)

    fun playNext(track: Track) = withController { c ->
        autoplay.invalidate()
        if (c.mediaItemCount == 0) { radioSeed = track; radioHint = "" }
        val at = if (c.mediaItemCount == 0) 0 else c.currentMediaItemIndex + 1
        c.addMediaItem(at, track.toMediaItem())
        if (c.mediaItemCount == 1) { c.prepare(); c.play() }
    }

    fun addToQueue(track: Track) = withController { c ->
        autoplay.invalidate()
        if (c.mediaItemCount == 0) { radioSeed = track; radioHint = "" }
        c.addMediaItem(track.toMediaItem())
        if (c.mediaItemCount == 1) { c.prepare(); c.play() }
    }

    fun removeFromQueue(index: Int) = withController {
        if (index in 0 until it.mediaItemCount) {
            autoplay.invalidate()
            if (it.mediaItemCount == 1) { radioSeed = null; radioHint = "" }
            it.removeMediaItem(index)
        }
    }
    fun moveInQueue(from: Int, to: Int) = withController {
        if (from != to && from in 0 until it.mediaItemCount && to in 0 until it.mediaItemCount) {
            autoplay.invalidate(); it.moveMediaItem(from, to)
        }
    }
    fun skipTo(index: Int) = withController {
        if (index in 0 until it.mediaItemCount) {
            autoplay.invalidate()
            radioSeed = it.getMediaItemAt(index).toTrack(); radioHint = ""
            it.seekToDefaultPosition(index); it.play()
        }
    }

    fun togglePlay() = withController {
        if (it.playWhenReady) { autoplay.invalidate(); it.pause() }
        else { if (it.playbackState == Player.STATE_IDLE) it.prepare(); it.play() }
    }
    fun resume() = withController { resumeExistingQueue(it) }
    fun pause() = withController { autoplay.invalidate(); it.pause() }
    fun next() = withController {
        if (it.hasNextMediaItem()) it.seekToNextMediaItem()
        else { autoplay.invalidate(); autoplay.update() }
    }
    /** Like every music app: restart the track if it is past 3s, otherwise go to the previous one. */
    fun previous() = withController { if (it.currentPosition > 3_000 || !it.hasPreviousMediaItem()) it.seekTo(0) else it.seekToPreviousMediaItem() }
    fun seekTo(ms: Long) = withController { it.seekTo(ms) }
    fun setShuffle(on: Boolean) = withController { it.shuffleModeEnabled = on }
    fun toggleShuffle() = withController { it.shuffleModeEnabled = !it.shuffleModeEnabled }
    fun cycleRepeat() = withController {
        autoplay.invalidate()
        it.repeatMode = when (it.repeatMode) {
            Player.REPEAT_MODE_OFF -> Player.REPEAT_MODE_ALL
            Player.REPEAT_MODE_ALL -> Player.REPEAT_MODE_ONE
            else -> Player.REPEAT_MODE_OFF
        }
    }
    fun setSpeed(speed: Float) = withController { it.setPlaybackSpeed(speed.coerceIn(0.25f, 3f)) }
    fun stop() = withController { autoplay.invalidate(); radioSeed = null; radioHint = ""; it.stop(); it.clearMediaItems() }

    // Sleep timer runs in the app process on the main thread, next to the service's player.
    fun sleepIn(minutes: Int) = sleepTimer.start(minutes)
    fun sleepAtEndOfTrack() = sleepTimer.startEndOfTrack()
    fun cancelSleep() = sleepTimer.cancel()

    // ---- state ----

    private val listener = object : Player.Listener {
        override fun onEvents(player: Player, events: Player.Events) {
            val current = controller ?: return
            refresh(current)
            autoplay.update()
        }
    }

    private fun autoplaySnapshot(): AutoplaySnapshot? = controller?.let { c ->
        AutoplaySnapshot(
            queue = (0 until c.mediaItemCount).map { c.getMediaItemAt(it).toTrack() },
            index = c.currentMediaItemIndex,
            enabled = settings.settings.value.autoplay && c.currentMediaItem?.mediaId?.let { !isLocalAudioId(it) } == true,
            playWhenReady = c.playWhenReady,
            repeatOff = c.repeatMode == Player.REPEAT_MODE_OFF,
            idle = c.playbackState == Player.STATE_IDLE,
            ended = c.playbackState == Player.STATE_ENDED,
            radioSeed = radioSeed ?: c.currentMediaItem?.toTrack(),
            radioHint = radioHint,
        )
    }

    private fun appendAutoplay(tracks: List<Track>, resumeEnded: Boolean) {
        val c = controller ?: return
        val firstNew = c.mediaItemCount
        c.addMediaItems(tracks.map { it.toMediaItem() })
        // Never undo Pause, Autoplay-off or an end-of-track sleep timer during an async fetch.
        if (resumeEnded && c.playWhenReady && settings.settings.value.autoplay) {
            c.seekToDefaultPosition(firstNew); c.prepare(); c.play()
        }
    }

    private fun refresh(p: Player) {
        if (radioSeed == null && p.mediaItemCount > 0) radioSeed = p.currentMediaItem?.toTrack()
        _state.value = snapshot(p)
    }

    private fun snapshot(p: Player): PlayerUiState {
        val queue = (0 until p.mediaItemCount).map { p.getMediaItemAt(it).toTrack() }
        return PlayerUiState(
            connected = true,
            current = p.currentMediaItem?.toTrack(),
            isPlaying = p.isPlaying,
            isBuffering = p.playbackState == Player.STATE_BUFFERING,
            positionMs = p.currentPosition.coerceAtLeast(0),
            durationMs = p.duration.takeIf { it > 0 } ?: (p.currentMediaItem?.mediaMetadata?.durationMs ?: 0),
            bufferedMs = p.bufferedPosition,
            shuffle = p.shuffleModeEnabled,
            repeatMode = p.repeatMode,
            speed = p.playbackParameters.speed,
            queue = queue,
            queueIndex = p.currentMediaItemIndex,
            hasNext = p.hasNextMediaItem(),
            hasPrevious = p.hasPreviousMediaItem(),
        )
    }

    init {
        scope.launch {
            settings.settings.map { it.autoplay }.distinctUntilChanged().collect { enabled ->
                if (enabled) autoplay.update() else autoplay.invalidate()
            }
        }
        // The seek bar needs a steady position; events alone only fire on state changes.
        scope.launch {
            while (true) {
                delay(500)
                val c = controller ?: continue
                if (c.isPlaying) _state.update { it.copy(positionMs = c.currentPosition.coerceAtLeast(0), bufferedMs = c.bufferedPosition) }
            }
        }
    }

}
