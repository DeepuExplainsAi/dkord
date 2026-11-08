package app.dkord

import app.dkord.core.*
import app.dkord.data.search.*
import app.dkord.data.yt.SearchFilter
import app.dkord.ui.studio.StudioSongSearch
import kotlinx.coroutines.*
import kotlinx.coroutines.test.*
import org.junit.Assert.*
import org.junit.Test
import java.io.IOException

@OptIn(ExperimentalCoroutinesApi::class)
class StudioSongSearchTest {
    private val a = Track("online00001", "संगवारी — Choliwood original", "Singer")
    private val b = Track("online00002", "संगवारी — remix", "Other singer")
    private fun item(t: Track) = BrowseItem(ItemKind.SONG, t.id, t.title, track = t)
    private object Next : SearchPageToken
    private class Source(
        val fetch: suspend (String, SearchFilter) -> SearchPage = { _, _ -> SearchPage(emptyList()) },
        val page: suspend (SearchPageToken) -> SearchPage = { SearchPage(emptyList()) },
    ) : SearchSource {
        override suspend fun suggestions(query: String): List<String> = error("No implicit suggestions/network")
        override suspend fun search(query: String, filter: SearchFilter) = fetch(query, filter)
        override suspend fun more(token: SearchPageToken) = page(token)
    }
    @Test fun typing_and_blank_submit_do_not_call_the_network_or_create_downloads() = runTest {
        var calls = 0
        val c = StudioSongSearch(Source(fetch = { _, _ -> calls++; SearchPage(emptyList()) }), backgroundScope)
        c.typed(" "); c.search(); runCurrent()
        assertEquals(0, calls); assertFalse(c.state.value.submitted)
        c.typed("Choliwood 2026"); runCurrent(); assertEquals(0, calls)
    }
    @Test fun unicode_query_is_normalized_and_uses_real_music_song_scope_only() = runTest {
        val queries = mutableListOf<Pair<String, SearchFilter>>()
        val c = StudioSongSearch(Source(fetch = { q, f ->
            queries += q to f
            SearchPage(listOf(item(a), BrowseItem(ItemKind.ALBUM, "album", "Album"), item(b), item(a)))
        }), backgroundScope)
        c.typed("  संगवारी \n Choliwood "); c.search(); runCurrent()
        assertEquals(listOf("संगवारी Choliwood" to SearchFilter.SONGS), queries)
        assertEquals(listOf(a, b), c.state.value.tracks)
    }
    @Test fun an_uncancellable_previous_query_cannot_replace_a_new_query_or_picker_session() = runTest {
        val c = StudioSongSearch(Source(fetch = { q, _ ->
            withContext(NonCancellable) { delay(if (q == "old") 100 else 5) }
            SearchPage(listOf(item(if (q == "old") a else b)))
        }), backgroundScope)
        c.typed("old"); c.search(); runCurrent()
        c.typed("new"); c.search(); runCurrent(); advanceTimeBy(100); runCurrent()
        assertEquals(listOf(b), c.state.value.tracks); assertEquals("new", c.state.value.query)
    }
    @Test fun editing_invalidates_old_results_and_opaque_pagination_ownership() = runTest {
        var pages = 0
        val c = StudioSongSearch(Source(fetch = { _, _ -> SearchPage(listOf(item(a)), Next) }, page = {
            pages++; SearchPage(listOf(item(b)))
        }), backgroundScope)
        c.typed("one"); c.search(); runCurrent(); assertTrue(c.state.value.hasMore)
        c.typed("two"); c.more(); runCurrent()
        assertEquals(0, pages); assertTrue(c.state.value.tracks.isEmpty()); assertFalse(c.state.value.hasMore)
    }
    @Test fun later_pages_deduplicate_ids_without_merging_distinct_song_versions() = runTest {
        val c = StudioSongSearch(Source(fetch = { _, _ -> SearchPage(listOf(item(a)), Next) }, page = {
            assertSame(Next, it); SearchPage(listOf(item(a), item(b)))
        }), backgroundScope)
        c.typed("song"); c.search(); runCurrent(); c.more(); c.more(); runCurrent()
        assertEquals(listOf(a, b), c.state.value.tracks); assertFalse(c.state.value.hasMore)
    }
    @Test fun failed_pagination_keeps_existing_results_and_retries_the_same_cursor() = runTest {
        var tries = 0
        val c = StudioSongSearch(Source(fetch = { _, _ -> SearchPage(listOf(item(a)), Next) }, page = {
            assertSame(Next, it); if (++tries == 1) throw IOException("offline")
            SearchPage(listOf(item(b)))
        }), backgroundScope)
        c.typed("song"); c.search(); runCurrent(); c.more(); runCurrent()
        assertTrue(c.state.value.moreFailed); assertEquals(listOf(a), c.state.value.tracks)
        c.more(); runCurrent(); assertEquals(listOf(a, b), c.state.value.tracks)
    }
    @Test fun failed_search_does_not_fabricate_results_and_explicit_retry_recovers() = runTest {
        var tries = 0
        val c = StudioSongSearch(Source(fetch = { _, _ ->
            if (++tries == 1) throw IOException("offline")
            SearchPage(listOf(item(a)))
        }), backgroundScope)
        c.typed("song"); c.search(); runCurrent()
        assertTrue(c.state.value.failed); assertTrue(c.state.value.tracks.isEmpty())
        c.search(); runCurrent(); assertFalse(c.state.value.failed); assertEquals(listOf(a), c.state.value.tracks)
    }
    @Test fun stale_pagination_failure_cannot_change_a_new_querys_loading_flags() = runTest {
        val c = StudioSongSearch(Source(fetch = { _, _ -> SearchPage(listOf(item(a)), Next) }, page = {
            withContext(NonCancellable) { delay(100) }; throw IOException("old page")
        }), backgroundScope)
        c.typed("one"); c.search(); runCurrent(); c.more(); runCurrent()
        c.typed("two"); c.search(); runCurrent(); advanceTimeBy(100); runCurrent()
        assertEquals("two", c.state.value.query); assertFalse(c.state.value.moreFailed); assertFalse(c.state.value.loading)
    }
}
