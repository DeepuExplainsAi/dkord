package app.dkord.ui.listen

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import app.dkord.core.ListeningEntry
import app.dkord.data.db.DownloadState
import app.dkord.data.download.DownloadManager
import app.dkord.data.library.LibraryRepository
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.launch

internal data class ListeningData(
    val entries: List<ListeningEntry> = emptyList(),
    val likedIds: Set<String> = emptySet(),
    val downloadedIds: Set<String> = emptySet(),
    val loading: Boolean = true,
    val failed: Boolean = false,
    val changing: Boolean = false,
)

/** Local Room observations only: opening the tab never searches a provider or starts playback. */
internal class ListenAgainViewModel(private val library: LibraryRepository, private val downloads: DownloadManager) : ViewModel() {
    private val mutable = MutableStateFlow(ListeningData())
    val state = mutable.asStateFlow()
    private val mutableErrors = MutableSharedFlow<Unit>(extraBufferCapacity = 1)
    val errors = mutableErrors.asSharedFlow()
    private var observation: Job? = null

    init { retry() }

    fun retry() {
        observation?.cancel()
        mutable.value = mutable.value.copy(loading = true, failed = false)
        observation = viewModelScope.launch {
            try {
                combine(library.history(), library.likedIds(), downloads.downloads()) { history, liked, files ->
                    ListeningData(history, liked, files.filter {
                        it.download.state == DownloadState.DONE && !it.download.localUri.isNullOrBlank()
                    }.map { it.track.id }.toSet(), loading = false)
                }.collect { mutable.value = it.copy(changing = mutable.value.changing) }
            } catch (e: CancellationException) { throw e }
            catch (e: Exception) { mutable.value = mutable.value.copy(loading = false, failed = true) }
        }
    }

    fun remove(id: String) = change { library.removeFromHistory(id) }
    fun clear() = change { library.clearHistory() }

    private fun change(action: suspend () -> Unit) {
        if (mutable.value.changing) return
        mutable.value = mutable.value.copy(changing = true)
        viewModelScope.launch {
            try { action() }
            catch (e: CancellationException) { throw e }
            catch (e: Exception) { mutableErrors.emit(Unit) }
            finally { mutable.value = mutable.value.copy(changing = false) }
        }
    }
}
