package app.dkord.ui.studio

import app.dkord.core.Track
import app.dkord.data.search.SearchPageToken
import app.dkord.data.search.SearchSource
import app.dkord.data.search.normalizeSearchQuery
import app.dkord.data.yt.SearchFilter
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow

internal data class StudioSongResults(
    val query: String = "", val submitted: Boolean = false, val loading: Boolean = false,
    val tracks: List<Track> = emptyList(), val failed: Boolean = false,
    val more: Boolean = false, val hasMore: Boolean = false, val moreFailed: Boolean = false,
)

/** Separate source-picker ownership. Never invokes playback, downloads or the main Search session. */
internal class StudioSongSearch(private val source: SearchSource, private val scope: CoroutineScope) {
    private val mutable = MutableStateFlow(StudioSongResults())
    val state = mutable.asStateFlow()
    private var epoch = 0L
    private var job: Job? = null
    private var cursor: SearchPageToken? = null
    fun typed(text: String) {
        if (text == state.value.query) return
        epoch++; job?.cancel(); cursor = null
        mutable.value = StudioSongResults(query = text.take(500))
    }
    fun search() {
        val query = normalizeSearchQuery(state.value.query)
        if (query.isBlank() || state.value.loading) return
        epoch++; job?.cancel(); cursor = null
        val owner = epoch
        mutable.value = StudioSongResults(query, submitted = true, loading = true)
        job = scope.launch {
            try {
                val result = source.search(query, SearchFilter.SONGS)
                currentCoroutineContext().ensureActive()
                if (epoch == owner) {
                    cursor = result.next
                    mutable.value = mutable.value.copy(loading = false,
                        tracks = result.items.mapNotNull { it.track }.distinctBy { it.id }, hasMore = cursor != null)
                }
            } catch (e: CancellationException) { throw e }
            catch (_: Exception) { if (epoch == owner) mutable.value = mutable.value.copy(loading = false, failed = true) }
        }
    }
    fun more() {
        val token = cursor ?: return
        if (state.value.more) return
        val owner = epoch
        mutable.value = mutable.value.copy(more = true, moreFailed = false)
        job = scope.launch {
            try {
                val result = source.more(token)
                currentCoroutineContext().ensureActive()
                if (epoch == owner) {
                    cursor = result.next
                    mutable.value = mutable.value.copy(more = false, hasMore = cursor != null,
                        tracks = (mutable.value.tracks + result.items.mapNotNull { it.track }).distinctBy { it.id })
                }
            } catch (e: CancellationException) { throw e }
            catch (_: Exception) { if (epoch == owner) mutable.value = mutable.value.copy(more = false, moreFailed = true) }
        }
    }
}
