package app.dkord.data.yt

import app.dkord.core.isLocalAudioId

import app.dkord.core.BrowseItem
import app.dkord.core.Page
import app.dkord.core.Track
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.schabi.newpipe.extractor.ServiceList
import org.schabi.newpipe.extractor.search.SearchInfo
import org.schabi.newpipe.extractor.services.youtube.linkHandler.YoutubeSearchQueryHandlerFactory as F

enum class SearchFilter(internal val id: String) {
    SONGS(F.MUSIC_SONGS), ALBUMS(F.MUSIC_ALBUMS), ARTISTS(F.MUSIC_ARTISTS), PLAYLISTS(F.MUSIC_PLAYLISTS),
    MUSIC_VIDEOS(F.MUSIC_VIDEOS), VIDEOS(F.VIDEOS), ALL(F.ALL)
}

/** Opaque handle for the next search page. */
class SearchCursor internal constructor(internal val query: String, internal val filter: SearchFilter, internal val page: org.schabi.newpipe.extractor.Page)

class SearchResult(
    val items: List<BrowseItem>,
    val next: SearchCursor?,
    val suggestedQuery: String = "",
    val corrected: Boolean = false,
)

class MusicRepository(private val client: InnerTubeClient) {

    // ---- Search & suggestions: NewPipeExtractor (no auth, no PO token needed) ----

    suspend fun suggestions(query: String): List<String> = withContext(Dispatchers.IO) {
        if (query.isBlank()) emptyList() else ServiceList.YouTube.suggestionExtractor.suggestionList(query)
    }

    suspend fun search(query: String, filter: SearchFilter): SearchResult = withContext(Dispatchers.IO) {
        val yt = ServiceList.YouTube
        val info = SearchInfo.getInfo(yt, yt.searchQHFactory.fromQuery(query, listOf(filter.id), ""))
        SearchResult(info.relatedItems.mapNotNull(::mapItem), info.nextPage?.let { SearchCursor(query, filter, it) },
            info.searchSuggestion.orEmpty(), info.isCorrectedSearch)
    }

    suspend fun searchMore(cursor: SearchCursor): SearchResult = withContext(Dispatchers.IO) {
        val yt = ServiceList.YouTube
        val page = SearchInfo.getMoreItems(yt, yt.searchQHFactory.fromQuery(cursor.query, listOf(cursor.filter.id), ""), cursor.page)
        SearchResult(page.items.mapNotNull(::mapItem), page.nextPage?.let { SearchCursor(cursor.query, cursor.filter, it) })
    }

    /**
     * Autoplay: anonymous YouTube Music Radio for [track], preserving its recommendation order.
     * Falls back to the YouTube Music "songs" search if no usable radio songs remain after filtering.
     * The plain youtube.com watch-page related list is NOT used (it returns vlogs/normal videos).
     */
    suspend fun related(track: Track, queue: List<Track> = emptyList()): List<Track> = withContext(Dispatchers.IO) {
        if (isLocalAudioId(track.id)) return@withContext emptyList()
        musicRadioRecommendations(track, queue,
            fetchRadio = { MusicParser.parseWatchNext(client.next(track.id)) },
            searchSongs = { query -> search(query, SearchFilter.SONGS).items.mapNotNull { it.track } },
        )
    }

    // ---- Browse: InnerTube WEB_REMIX (personalised when signed in) ----

    suspend fun home(chip: app.dkord.core.Chip? = null): Page =
        MusicParser.parsePage(client.browse(chip?.browseId ?: "FEmusic_home", chip?.params))

    suspend fun homeMore(token: String): Page = MusicParser.parseContinuation(client.browse(continuation = token))

    suspend fun explore(): Page = MusicParser.parsePage(client.browse("FEmusic_explore"))
    suspend fun newReleases(): Page = MusicParser.parsePage(client.browse("FEmusic_new_releases"))
    suspend fun charts(): Page = MusicParser.parsePage(client.browse("FEmusic_charts"))
    suspend fun moodsAndGenres(): Page = MusicParser.parsePage(client.browse("FEmusic_moods_and_genres"))
    suspend fun moodPage(item: BrowseItem): Page = MusicParser.parsePage(client.browse(item.id, item.params))

    suspend fun album(browseId: String): Page = MusicParser.parsePage(client.browse(browseId), albumPage = true)
    suspend fun artist(browseId: String): Page = MusicParser.parsePage(client.browse(browseId))
    suspend fun playlist(browseId: String): Page = MusicParser.parsePage(client.browse(browseId))
    suspend fun more(token: String): Page = MusicParser.parseContinuation(client.browse(continuation = token))

    // ---- Library (requires login) ----

    suspend fun likedSongs(): Page = MusicParser.parsePage(client.browse("FEmusic_liked_videos"))
    suspend fun libraryPlaylists(): Page = MusicParser.parsePage(client.browse("FEmusic_liked_playlists"))
    suspend fun libraryAlbums(): Page = MusicParser.parsePage(client.browse("FEmusic_liked_albums"))
    suspend fun libraryArtists(): Page = MusicParser.parsePage(client.browse("FEmusic_library_corpus_track_artists"))
    suspend fun history(): Page = MusicParser.parsePage(client.browse("FEmusic_history"))

    /** Display name and avatar of the signed-in account, or null. */
    suspend fun account(): Pair<String, String?>? {
        val h = client.accountMenu().find("activeAccountHeaderRenderer") ?: return null
        val name = h.at("accountName").runsText().ifBlank { return null }
        return name to h.at("accountPhoto").lastThumbnail()
    }

}
