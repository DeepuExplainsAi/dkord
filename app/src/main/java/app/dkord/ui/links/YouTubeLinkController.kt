package app.dkord.ui.links

import app.dkord.core.Track
import app.dkord.data.links.MAX_YOUTUBE_LINK_LENGTH
import app.dkord.data.links.YouTubeLinkException
import app.dkord.data.links.YouTubeLinkProblem
import app.dkord.data.links.YouTubeLinkSource
import app.dkord.data.links.YouTubeVideoLink
import app.dkord.data.links.youTubeLinkProblem
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class YouTubeLinkState(
    val input: String = "",
    val loading: Boolean = false,
    val track: Track? = null,
    val canonicalUrl: String? = null,
    val problem: YouTubeLinkProblem? = null,
)

/** Separate screen-lifetime work. No player, history, library or download mutations on paste/resolve. */
class YouTubeLinkController(private val source: YouTubeLinkSource, private val scope: CoroutineScope) {
    private val mutable = MutableStateFlow(YouTubeLinkState())
    val state = mutable.asStateFlow()
    private var request = 0L
    private var job: Job? = null

    fun typed(value: String) {
        // Keep the overflow sentinel: truncating to exactly the limit could turn a bad paste into a valid URL.
        val input = value.take(MAX_YOUTUBE_LINK_LENGTH + 1)
        if (input == state.value.input) return
        cancel()
        mutable.value = YouTubeLinkState(input = input)
    }

    fun open() {
        if (state.value.loading) return
        cancel()
        val input = state.value.input
        val link = try { YouTubeVideoLink.parse(input) } catch (e: YouTubeLinkException) {
            mutable.value = YouTubeLinkState(input = input, problem = e.problem)
            return
        }
        val owner = request
        mutable.value = YouTubeLinkState(input = input, loading = true)
        job = scope.launch {
            try {
                val track = source.resolve(link)
                currentCoroutineContext().ensureActive()
                if (track.id != link.videoId || track.title.isBlank() || track.durationSec < 0) {
                    throw YouTubeLinkException(YouTubeLinkProblem.UNAVAILABLE)
                }
                if (owner == request) mutable.value = YouTubeLinkState(input, track = track, canonicalUrl = link.url)
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                currentCoroutineContext().ensureActive()
                if (owner == request) mutable.value = YouTubeLinkState(input, problem = youTubeLinkProblem(e))
            } finally {
                if (owner == request && state.value.loading) mutable.value = state.value.copy(loading = false)
            }
        }
    }

    fun cancel() {
        request++
        job?.cancel(); job = null
        mutable.value = state.value.copy(loading = false)
    }
}
