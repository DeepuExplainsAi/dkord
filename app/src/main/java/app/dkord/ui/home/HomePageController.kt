package app.dkord.ui.home

import app.dkord.core.Chip
import app.dkord.core.Page
import app.dkord.ui.common.Load
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/** A shelf and its selected-chip radio intent must belong to the same completed Home request. */
internal class HomePageController(private val source: suspend (Chip?) -> Page, private val scope: CoroutineScope) {
    private val mutablePage = MutableStateFlow<Load<Page>>(Load.Loading)
    private val mutableRefreshing = MutableStateFlow(false)
    private val mutableChip = MutableStateFlow<Chip?>(null)
    val page = mutablePage.asStateFlow()
    val refreshing = mutableRefreshing.asStateFlow()
    val chip = mutableChip.asStateFlow()
    private var request = 0L
    private var job: Job? = null

    fun select(value: Chip?) {
        mutableChip.value = if (mutableChip.value == value) null else value
        load()
    }

    fun load(refresh: Boolean = false) {
        job?.cancel()
        val id = ++request
        val selected = chip.value
        mutableRefreshing.value = refresh
        if (!refresh) mutablePage.value = Load.Loading
        job = scope.launch {
            try {
                val result = source(selected)
                currentCoroutineContext().ensureActive()
                if (id == request) mutablePage.value = Load.Ok(result)
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                currentCoroutineContext().ensureActive()
                if (id == request) mutablePage.value = Load.Failed(e)
            } finally {
                if (id == request) mutableRefreshing.value = false
            }
        }
    }
}
