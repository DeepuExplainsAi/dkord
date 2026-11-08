package app.dkord.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Text
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import app.dkord.R
import app.dkord.core.BrowseItem
import app.dkord.core.Chip
import app.dkord.core.Shelf
import app.dkord.data.yt.MusicRepository
import app.dkord.ui.common.ErrorBox
import app.dkord.ui.common.Load
import app.dkord.ui.common.Loading
import app.dkord.ui.home.HomePageController
import app.dkord.ui.common.ShelfRow
import app.dkord.ui.common.koinVm
import app.dkord.data.yt.SearchFilter
import app.dkord.core.ItemKind
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import org.koin.compose.koinInject

class HomeViewModel(private val repo: MusicRepository) : ViewModel() {
    private val controller = HomePageController(repo::home, viewModelScope)
    val page = controller.page
    val refreshing = controller.refreshing
    val chip = controller.chip

    private val _extra = MutableStateFlow<List<Shelf>>(emptyList())
    /** Curated shelves (search based), filled in progressively so the page is scrollable even for guests. */
    val extra: StateFlow<List<Shelf>> = _extra

    init { load(); loadExtra() }

    private fun loadExtra() {
        viewModelScope.launch {
            val sections = CURATED.map { (title, query) ->
                async { runCatching { Shelf(title, repo.search(query, SearchFilter.SONGS).items.take(15), radioHint = query) }.getOrNull() }
            }
            val out = mutableListOf<Shelf>()
            // Keep the declared order, show each shelf as soon as everything before it is ready.
            for (d in sections) { d.await()?.takeIf { it.items.isNotEmpty() }?.let { out += it; _extra.value = out.toList() } }
        }
    }

    fun select(c: Chip?) = controller.select(c)
    fun load(refresh: Boolean = false) = controller.load(refresh)
}

private val CHOLIWOOD_WORD = Regex("\\bbhojpuri\\b|भोजपुरी", RegexOption.IGNORE_CASE)

/** Home section/chip branding only; never rewrites a song title, artist, or search query. */
internal fun choliwoodShelfTitle(title: String, brand: String): String = title.replace(CHOLIWOOD_WORD, brand)

private val CURATED = listOf(
    "Bollywood Hits" to "latest bollywood hit songs",
    "dkord:choliwood:popular" to "popular bhojpuri songs",
    "dkord:choliwood:latest" to "new bhojpuri songs",
    "Trending Punjabi" to "trending punjabi songs",
    "Romantic Hindi" to "romantic hindi songs",
    "Arijit Singh" to "arijit singh best songs",
    "Lo-fi & Chill" to "hindi lofi chill songs",
    "Workout Energy" to "gym workout songs",
    "Devotional" to "bhajan devotional songs",
    "Old Is Gold" to "old hindi classic songs kishore rafi",
    "English Pop" to "top english pop songs",
    "Hip-Hop & Rap" to "indian hip hop rap songs",
    "Sad Songs" to "hindi sad songs",
    "Party Mix" to "party dance songs hindi",
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(
    onItem: (BrowseItem) -> Unit,
    onPlay: (List<app.dkord.core.Track>, Int) -> Unit,
    modifier: Modifier = Modifier,
    onRelated: (app.dkord.core.Track, String) -> Unit = { track, _ -> onPlay(listOf(track), 0) },
) {
    val repo: MusicRepository = koinInject()
    val vm = koinVm { HomeViewModel(repo) }
    val page by vm.page.collectAsState()
    val refreshing by vm.refreshing.collectAsState()
    val selected by vm.chip.collectAsState()
    val choliwoodName = stringResource(R.string.choliwood_name)
    val extraShelves by vm.extra.collectAsState()
    val extra = extraShelves.map { shelf ->
        shelf.copy(title = when (shelf.title) {
            "dkord:choliwood:popular" -> stringResource(R.string.choliwood_popular)
            "dkord:choliwood:latest" -> stringResource(R.string.choliwood_latest)
            else -> choliwoodShelfTitle(shelf.title, choliwoodName)
        })
    }
    val library: app.dkord.data.library.LibraryRepository = koinInject()
    val recent by remember { library.recent(15) }.collectAsState(emptyList())
    val recentShelf = recent.takeIf { it.isNotEmpty() }?.let { l ->
        Shelf(stringResource(R.string.recently_played), l.map { BrowseItem(ItemKind.SONG, it.id, it.title, it.artist, it.thumbnail, track = it) })
    }

    PullToRefreshBox(refreshing, { vm.load(refresh = true) }, modifier.fillMaxSize()) {
        when (val p = page) {
            Load.Loading -> Loading()
            is Load.Failed -> LazyColumn(contentPadding = PaddingValues(vertical = 8.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                if (extra.isEmpty()) item("home_error") { ErrorBox(p.error, { vm.load() }, Modifier.padding(8.dp)) }
                item("new_releases") { NewReleasesSection(onItem, onPlay) }
                if (recentShelf != null) item("recent") { ShelfRow(recentShelf, onItem, onPlay, onRelated = onRelated) }
                items(extra) { ShelfRow(it, onItem, onPlay, onRelated = onRelated) }
            }
            is Load.Ok -> LazyColumn(contentPadding = PaddingValues(bottom = 16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                if (p.value.chips.isNotEmpty()) item("chips") {
                    LazyRow(contentPadding = PaddingValues(horizontal = 16.dp, vertical = 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        items(p.value.chips) { c -> FilterChip(selected == c, { vm.select(c) }, { Text(choliwoodShelfTitle(c.title, choliwoodName)) }) }
                    }
                }
                if (selected == null) item("new_releases") { NewReleasesSection(onItem, onPlay) }
                if (recentShelf != null && selected == null) item("recent") { ShelfRow(recentShelf, onItem, onPlay, onRelated = onRelated) }
                items(p.value.shelves) { shelf ->
                    ShelfRow(shelf.copy(title = choliwoodShelfTitle(shelf.title, choliwoodName),
                        radioHint = listOfNotNull(selected?.title, shelf.radioHint).filter { it.isNotBlank() }.joinToString(" ")),
                        onItem, onPlay, onRelated = onRelated)
                }
                if (selected == null) items(extra) { ShelfRow(it, onItem, onPlay, onRelated = onRelated) }
                if (p.value.shelves.isEmpty() && extra.isEmpty()) item("empty") { Text(stringResource(R.string.nothing_here), Modifier.padding(32.dp)) }
            }
        }
    }
}
