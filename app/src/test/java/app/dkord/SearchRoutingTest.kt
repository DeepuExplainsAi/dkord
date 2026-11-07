package app.dkord

import app.dkord.data.yt.SearchFilter
import org.junit.Assert.*
import org.junit.Test
import org.schabi.newpipe.extractor.ServiceList
import org.schabi.newpipe.extractor.services.youtube.extractors.YoutubeMusicSearchExtractor
import org.schabi.newpipe.extractor.services.youtube.extractors.YoutubeSearchExtractor
import org.schabi.newpipe.extractor.services.youtube.linkHandler.YoutubeSearchQueryHandlerFactory as F

/** Real bundled NewPipe query handlers/extractor selection, no network or Android dependency. */
class SearchRoutingTest {
    @Test fun all_and_video_filters_use_normal_youtube_not_the_music_songs_catalogue() {
        for (filter in listOf(SearchFilter.ALL, SearchFilter.VIDEOS)) {
            val handler = ServiceList.YouTube.searchQHFactory.fromQuery("mashup sad love 1 hour", listOf(filter.id), "")
            assertTrue(handler.url.startsWith("https://www.youtube.com/results?search_query="))
            assertFalse(handler.url.contains("music.youtube.com"))
            assertTrue(ServiceList.YouTube.getSearchExtractor(handler) is YoutubeSearchExtractor)
        }
        assertEquals(F.ALL, SearchFilter.ALL.id)
        assertEquals(F.VIDEOS, SearchFilter.VIDEOS.id)
    }

    @Test fun explicit_music_filters_keep_the_original_music_extractor() {
        for (filter in listOf(SearchFilter.SONGS, SearchFilter.MUSIC_VIDEOS, SearchFilter.ALBUMS, SearchFilter.ARTISTS, SearchFilter.PLAYLISTS)) {
            val handler = ServiceList.YouTube.searchQHFactory.fromQuery("Any query", listOf(filter.id), "")
            assertTrue(handler.url.startsWith("https://music.youtube.com/search?q="))
            assertTrue(ServiceList.YouTube.getSearchExtractor(handler) is YoutubeMusicSearchExtractor)
        }
        assertEquals(F.MUSIC_SONGS, SearchFilter.SONGS.id)
        assertEquals(F.MUSIC_PLAYLISTS, SearchFilter.PLAYLISTS.id)
    }

    @Test fun queries_are_passed_through_without_music_suffixes_genre_whitelists_or_duration_changes() {
        for (query in listOf("mashup sad love 1 hour", "தமிழ் cover 2 hours", "भजन + ग़ज़ल live", "acoustic remix 90s nonstop", "science podcast")) {
            val handler = ServiceList.YouTube.searchQHFactory.fromQuery(query, listOf(SearchFilter.ALL.id), "")
            assertEquals(query, handler.searchString)
            assertEquals(listOf(F.ALL), handler.contentFilters)
        }
    }

    @Test fun all_scope_is_first_and_every_filter_has_a_distinct_backend_identity() {
        assertEquals(SearchFilter.ALL, SearchFilter.entries.first())
        assertEquals(SearchFilter.entries.size, SearchFilter.entries.map { it.id }.distinct().size)
    }
}
