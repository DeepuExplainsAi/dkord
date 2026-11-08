package app.dkord.ui.shorts

import app.dkord.data.shorts.MusicClip
import app.dkord.data.shorts.ShortsCursor
import app.dkord.data.shorts.ShortsSource
import app.dkord.data.shorts.uniqueClips
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

internal data class ShortsState(
    val query: String = "music shorts",
    val clips: List<MusicClip> = emptyList(),
    val loading: Boolean = false,
    val failed: Boolean = false,
    val next: ShortsCursor? = null,
    val initialized: Boolean = false,
)

internal class ShortsController(private val source: ShortsSource, private val scope: CoroutineScope) {
    private val mutable = MutableStateFlow(ShortsState())
    val state: StateFlow<ShortsState> = mutable
    private var revision = 0L
    private var job: Job? = null

    fun initial() { if (!mutable.value.initialized) search(mutable.value.query) }
    fun search(text: String) {
        val query = text.trim().take(200)
        if (query.isBlank()) return
        job?.cancel(); revision++
        mutable.value = ShortsState(query = query, loading = true, initialized = true)
        fetch(null, revision)
    }
    fun more() {
        val s = mutable.value
        if (!s.loading && s.next != null) {
            mutable.value = s.copy(loading = true, failed = false)
            fetch(s.next, revision)
        }
    }
    fun retry() { if (mutable.value.next != null) more() else search(mutable.value.query) }
    private fun fetch(cursor: ShortsCursor?, generation: Long) {
        val query = mutable.value.query
        job = scope.launch {
            try {
                val page = source.load(query, cursor)
                currentCoroutineContext().ensureActive()
                if (generation != revision) return@launch
                val s = mutable.value
                mutable.value = s.copy(clips = s.clips + uniqueClips(s.clips, page.clips), next = page.next, loading = false, failed = false)
            } catch (e: CancellationException) { throw e }
            catch (_: Exception) { if (generation == revision) mutable.value = mutable.value.copy(loading = false, failed = true) }
        }
    }
}
