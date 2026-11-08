package app.dkord.player

import app.dkord.core.Track
import app.dkord.data.yt.MAX_AUTOPLAY_TRACKS
import app.dkord.data.yt.RadioTrackFilter
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Job
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.launch

/** Main-dispatcher snapshot; no Android types, so real async queue policy can be tested offline. */
internal data class AutoplaySnapshot(
    val queue: List<Track>,
    val index: Int,
    val enabled: Boolean = true,
    val playWhenReady: Boolean = true,
    val repeatOff: Boolean = true,
    val idle: Boolean = false,
    val ended: Boolean = false,
    val radioSeed: Track? = null,
    val radioHint: String = "",
) {
    val eligible: Boolean get() = enabled && playWhenReady && repeatOff && !idle &&
        queue.isNotEmpty() && index in queue.indices && (ended || index >= queue.size - 2)
}

/** No response from an old selection/session may change or resume a newer queue. UI dispatcher only. */
internal class AutoplayCoordinator(
    private val scope: CoroutineScope,
    private val source: suspend (Track, List<Track>, String) -> List<Track>,
    private val snapshot: () -> AutoplaySnapshot?,
    private val append: (tracks: List<Track>, resumeEnded: Boolean) -> Unit,
) {
    private data class Attempt(val revision: Long, val ids: List<String>, val ended: Boolean, val seedId: String, val hint: String)
    private var revision = 0L
    private var attempted: Attempt? = null
    private var active: Attempt? = null
    private var job: Job? = null

    fun invalidate() {
        revision++
        active = null
        attempted = null
        val old = job
        job = null
        old?.cancel()
    }

    fun update() {
        val before = snapshot()
        if (before == null || !before.eligible) {
            if (active != null || attempted != null) invalidate()
            return
        }
        val queue = before.queue.toList()
        val ids = queue.map { it.id }
        val seed = before.radioSeed ?: queue.last()
        val running = active
        if (running != null && running.revision == revision && running.ids == ids && running.seedId == seed.id && running.hint == before.radioHint) return
        if (running != null) invalidate()
        val request = Attempt(revision, ids, before.ended, seed.id, before.radioHint)
        if (attempted == request) return // No event-driven request storm after an empty/failing response.
        attempted = request
        active = request
        val launched = scope.launch(start = CoroutineStart.LAZY) {
            try {
                val candidates = source(seed, queue, request.hint)
                currentCoroutineContext().ensureActive()
                val now = snapshot()
                if (active !== request || revision != request.revision || now == null || !now.eligible ||
                    now.queue.map { it.id } != request.ids ||
                    (now.radioSeed ?: now.queue.last()).id != request.seedId || now.radioHint != request.hint) return@launch
                val fresh = RadioTrackFilter(seed, now.queue).select(candidates).take(MAX_AUTOPLAY_TRACKS)
                if (fresh.isEmpty()) return@launch
                active = null // Host append may synchronously trigger another player event.
                append(fresh, now.ended && now.playWhenReady)
            } catch (e: CancellationException) {
                throw e
            } catch (_: Exception) {
                // Leave the queue intact. A new selection/resume or reaching ENDED permits a retry.
            } finally {
                if (active === request) active = null
                if (attempted === request) job = null
            }
        }
        job = launched
        launched.start()
    }
}
