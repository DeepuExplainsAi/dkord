package app.dkord

import app.dkord.core.BrowseItem
import app.dkord.core.ItemKind
import app.dkord.core.Track
import app.dkord.data.search.*
import app.dkord.data.yt.SearchFilter
import app.dkord.ui.common.Load
import app.dkord.ui.search.SearchController
import app.dkord.ui.search.MAX_REMOTE_SUGGESTIONS
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.delay
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.withContext
import org.junit.Assert.*
import org.junit.Test
import java.io.IOException

@OptIn(ExperimentalCoroutinesApi::class)
class SearchControllerTest {
    private data class Token(val name: String) : SearchPageToken
    private class Source : SearchSource {
        val searches = mutableListOf<Pair<String, SearchFilter>>()
        val suggested = mutableListOf<String>()
        val pages = mutableListOf<SearchPageToken>()
        var suggest: suspend (String) -> List<String> = { listOf("$it suggestion") }
        var find: suspend (String, SearchFilter) -> SearchPage = { query, _ -> SearchPage(listOf(song(query))) }
        var next: suspend (SearchPageToken) -> SearchPage = { SearchPage(emptyList()) }
        override suspend fun suggestions(query: String): List<String> { suggested += query; return suggest(query) }
        override suspend fun search(query: String, filter: SearchFilter): SearchPage { searches += query to filter; return find(query, filter) }
        override suspend fun more(token: SearchPageToken): SearchPage { pages += token; return next(token) }
    }
    private data class Fixture(val source: Source, val storage: MemorySearchStorage, val history: SearchHistoryRepository, val controller: SearchController)
    private fun TestScope.fixture(seed: List<SavedSearch> = emptyList()): Fixture {
        val source = Source()
        val storage = MemorySearchStorage(seed)
        val history = SearchHistoryRepository(storage, backgroundScope)
        return Fixture(source, storage, history, SearchController(source, history, backgroundScope))
    }
    private fun SearchController.ids() = (results.value as Load.Ok).value.map { it.id }
    private companion object {
        fun song(id: String) = BrowseItem(ItemKind.SONG, id, id, track = Track(id, id, "Artist"))
    }

    @Test fun typing_is_debounced_and_never_records_a_search() = runTest {
        val f = fixture()
        f.controller.typed("ar"); runCurrent(); advanceTimeBy(200)
        f.controller.typed("ari"); runCurrent(); advanceTimeBy(249); runCurrent()
        assertTrue(f.source.suggested.isEmpty())
        advanceTimeBy(1); runCurrent()
        assertEquals(listOf("ari"), f.source.suggested)
        assertTrue(f.source.searches.isEmpty())
        assertEquals(0, f.storage.writes)
        assertTrue(f.history.state.value.entries.isEmpty())
    }

    @Test fun submission_normalizes_and_records_once_not_on_result_completion() = runTest {
        val f = fixture()
        f.controller.typed("  Arijit   Singh  "); f.controller.search(); runCurrent()
        assertEquals("Arijit Singh", f.controller.query.value)
        assertEquals(listOf("Arijit Singh" to SearchFilter.SONGS), f.source.searches)
        assertEquals(listOf("Arijit Singh"), f.controller.ids())
        assertEquals(listOf(SavedSearch("Arijit Singh", SearchFilter.SONGS)), f.history.state.value.entries)
        assertEquals(1, f.storage.writes)
        advanceTimeBy(1000); runCurrent()
        assertTrue(f.source.suggested.isEmpty())
        assertEquals(1, f.storage.writes)
    }

    @Test fun repeat_uses_the_saved_query_and_original_filter_and_preserves_its_pin() = runTest {
        val entry = SavedSearch("Collection", SearchFilter.PLAYLISTS, true)
        val f = fixture(listOf(entry))
        f.controller.repeat(entry); runCurrent()
        assertEquals("Collection", f.controller.query.value)
        assertEquals(SearchFilter.PLAYLISTS, f.controller.filter.value)
        assertEquals(listOf("Collection" to SearchFilter.PLAYLISTS), f.source.searches)
        assertEquals(listOf(entry), f.history.state.value.entries)
    }

    @Test fun edit_prefills_without_a_search_or_recency_write() = runTest {
        val entries = listOf(SavedSearch("New", SearchFilter.SONGS), SavedSearch("Old", SearchFilter.ALBUMS, true))
        val f = fixture(entries)
        f.controller.edit(entries.last()); runCurrent()
        assertEquals("Old", f.controller.query.value)
        assertEquals(SearchFilter.ALBUMS, f.controller.filter.value)
        assertNull(f.controller.results.value)
        advanceTimeBy(250); runCurrent()
        assertEquals(listOf("Old"), f.source.suggested)
        assertTrue(f.source.searches.isEmpty())
        assertEquals(0, f.storage.writes)
        assertEquals(entries, f.history.state.value.entries)
    }

    @Test fun filter_changes_search_only_if_the_current_query_was_submitted() = runTest {
        val f = fixture()
        f.controller.typed("Artist"); f.controller.setFilter(SearchFilter.ALBUMS); runCurrent()
        assertTrue(f.source.searches.isEmpty())
        assertTrue(f.history.state.value.entries.isEmpty())
        f.controller.search(); runCurrent()
        f.controller.setFilter(SearchFilter.ARTISTS); runCurrent()
        assertEquals(listOf("Artist" to SearchFilter.ALBUMS, "Artist" to SearchFilter.ARTISTS), f.source.searches)
        assertEquals(listOf(SearchFilter.ARTISTS, SearchFilter.ALBUMS), f.history.state.value.entries.map { it.filter })
    }

    @Test fun repeated_submit_during_loading_does_not_duplicate_requests_or_writes() = runTest {
        val f = fixture()
        f.source.find = { query, _ -> delay(100); SearchPage(listOf(song(query))) }
        f.controller.search("Same"); f.controller.search("Same"); runCurrent()
        assertEquals(Load.Loading, f.controller.results.value)
        assertEquals(1, f.source.searches.size)
        assertEquals(1, f.storage.writes)
        advanceTimeBy(100); runCurrent()
        assertEquals(listOf("Same"), f.controller.ids())
    }

    @Test fun old_uncancellable_search_cannot_replace_a_newer_query_or_filter() = runTest {
        val f = fixture()
        f.source.find = { _, filter ->
            withContext(NonCancellable) { delay(if (filter == SearchFilter.SONGS) 100 else 10) }
            SearchPage(listOf(song(filter.name)))
        }
        f.controller.search("Artist"); runCurrent()
        f.controller.setFilter(SearchFilter.ALBUMS); runCurrent()
        advanceTimeBy(10); runCurrent()
        assertEquals(listOf("ALBUMS"), f.controller.ids())
        advanceTimeBy(90); runCurrent()
        assertEquals(listOf("ALBUMS"), f.controller.ids())
        assertEquals(SearchFilter.ALBUMS, f.controller.filter.value)
    }

    @Test fun late_suggestions_cannot_replace_newer_normalized_deduplicated_suggestions() = runTest {
        val f = fixture()
        f.source.suggest = { query ->
            if (query == "old") { withContext(NonCancellable) { delay(1000) }; listOf("Stale") }
            else { delay(1); listOf(" New ", "new", " ", "Other", "other") }
        }
        f.controller.typed("old"); runCurrent(); advanceTimeBy(250); runCurrent()
        f.controller.typed("new"); runCurrent(); advanceTimeBy(250); runCurrent()
        advanceTimeBy(1); runCurrent()
        assertEquals(listOf("New", "Other"), f.controller.suggestions.value)
        advanceTimeBy(749); runCurrent()
        assertEquals(listOf("New", "Other"), f.controller.suggestions.value)
        assertEquals(0, f.storage.writes)
    }

    @Test fun remote_suggestions_are_bounded() = runTest {
        val f = fixture()
        f.source.suggest = { (0..30).map { "Suggestion $it" } }
        f.controller.typed("s"); runCurrent(); advanceTimeBy(250); runCurrent()
        assertEquals(MAX_REMOTE_SUGGESTIONS, f.controller.suggestions.value.size)
    }

    @Test fun clearing_input_cancels_late_results_but_does_not_delete_saved_history() = runTest {
        val f = fixture()
        f.source.find = { query, _ -> withContext(NonCancellable) { delay(100) }; SearchPage(listOf(song(query))) }
        f.controller.search("Slow"); runCurrent()
        f.controller.clear(); runCurrent(); advanceTimeBy(100); runCurrent()
        assertEquals("", f.controller.query.value)
        assertNull(f.controller.results.value)
        assertTrue(f.controller.suggestions.value.isEmpty())
        assertFalse(f.controller.loadingMore.value)
        assertEquals(listOf("Slow"), f.history.state.value.entries.map { it.query })
    }

    @Test fun editing_a_submitted_query_replaces_results_with_suggestions_without_saving_keystrokes() = runTest {
        val f = fixture()
        f.controller.search("First"); runCurrent()
        f.controller.typed("Changed"); runCurrent()
        assertNull(f.controller.results.value)
        assertEquals(listOf("First"), f.history.state.value.entries.map { it.query })
        assertEquals(1, f.source.searches.size)
    }

    @Test fun pagination_deduplicates_by_kind_and_id_and_does_not_change_history() = runTest {
        val f = fixture()
        val first = Token("first"); val second = Token("second")
        f.source.find = { _, _ -> SearchPage(listOf(song("one"), song("one"), BrowseItem(ItemKind.ALBUM, "one", "Album")), first) }
        f.source.next = { token -> delay(10); if (token == first) SearchPage(listOf(song("one"), song("two")), second) else SearchPage(listOf(song("three"))) }
        f.controller.search("Query"); runCurrent()
        assertEquals(listOf("one", "one"), f.controller.ids())
        f.controller.loadMore(); f.controller.loadMore(); runCurrent()
        assertTrue(f.controller.loadingMore.value)
        assertEquals(1, f.source.pages.size)
        advanceTimeBy(10); runCurrent()
        assertEquals(listOf("one", "one", "two"), f.controller.ids())
        f.controller.loadMore(); runCurrent(); advanceTimeBy(10); runCurrent()
        f.controller.loadMore(); runCurrent()
        assertEquals(listOf("one", "one", "two", "three"), f.controller.ids())
        assertEquals(2, f.source.pages.size)
        assertEquals(1, f.storage.writes)
    }

    @Test fun an_empty_page_keeps_a_valid_continuation_available_for_manual_loading() = runTest {
        val f = fixture()
        val first = Token("first"); val second = Token("second")
        f.source.find = { _, _ -> SearchPage(listOf(song("one")), first) }
        f.source.next = { if (it == first) SearchPage(emptyList(), second) else SearchPage(listOf(song("two"))) }
        f.controller.search("Query"); runCurrent()
        f.controller.loadMore(); runCurrent()
        assertEquals(listOf("one"), f.controller.ids())
        assertTrue(f.controller.hasMore.value)
        f.controller.loadMore(); runCurrent()
        assertEquals(listOf("one", "two"), f.controller.ids())
        assertFalse(f.controller.hasMore.value)
    }

    @Test fun a_reused_identical_page_token_stops_pagination() = runTest {
        val f = fixture()
        val token = Token("same")
        f.source.find = { _, _ -> SearchPage(listOf(song("one")), token) }
        f.source.next = { SearchPage(listOf(song("two")), token) }
        f.controller.search("Query"); runCurrent()
        f.controller.loadMore(); runCurrent()
        assertFalse(f.controller.hasMore.value)
        f.controller.loadMore(); runCurrent()
        assertEquals(1, f.source.pages.size)
    }

    @Test fun failed_pagination_keeps_rows_and_cursor_and_requires_explicit_retry() = runTest {
        val f = fixture()
        f.source.find = { _, _ -> SearchPage(listOf(song("one")), Token("next")) }
        f.source.next = { if (f.source.pages.size == 1) throw IOException("offline"); SearchPage(listOf(song("two"))) }
        f.controller.search("Query"); runCurrent()
        f.controller.loadMore(); runCurrent()
        assertEquals(listOf("one"), f.controller.ids())
        assertTrue(f.controller.moreFailed.value)
        assertFalse(f.controller.loadingMore.value)
        repeat(5) { f.controller.loadMore() }; runCurrent()
        assertEquals(1, f.source.pages.size)
        f.controller.loadMore(retry = true); runCurrent()
        assertEquals(listOf("one", "two"), f.controller.ids())
        assertFalse(f.controller.moreFailed.value)
        assertEquals(2, f.source.pages.size)
        assertEquals(1, f.storage.writes)
    }

    @Test fun stale_pagination_cannot_append_to_or_clear_loading_for_a_new_search() = runTest {
        val f = fixture()
        val old = Token("old"); val fresh = Token("new")
        f.source.find = { query, _ -> SearchPage(listOf(song(query)), if (query == "old") old else fresh) }
        f.source.next = { token ->
            withContext(NonCancellable) { delay(if (token == old) 100 else 200) }
            SearchPage(listOf(song(if (token == old) "stale" else "new-page")))
        }
        f.controller.search("old"); runCurrent(); f.controller.loadMore(); runCurrent()
        f.controller.search("new"); runCurrent(); f.controller.loadMore(); runCurrent()
        advanceTimeBy(100); runCurrent()
        assertEquals(listOf("new"), f.controller.ids())
        assertTrue(f.controller.loadingMore.value)
        advanceTimeBy(100); runCurrent()
        assertEquals(listOf("new", "new-page"), f.controller.ids())
        assertFalse(f.controller.loadingMore.value)
        assertFalse(f.controller.moreFailed.value)
    }

    @Test fun suggestion_failure_is_retryable_and_failed_submitted_search_is_still_saved() = runTest {
        val f = fixture()
        f.source.suggest = { throw IOException("offline") }
        f.source.find = { _, _ -> throw IOException("offline") }
        f.controller.typed("Offline"); runCurrent(); advanceTimeBy(250); runCurrent()
        assertTrue(f.controller.suggestions.value.isEmpty())
        assertTrue(f.controller.suggestionsFailed.value)
        assertFalse(f.controller.suggestionsLoading.value)
        assertNull(f.controller.results.value)
        f.controller.search(); runCurrent()
        assertTrue(f.controller.results.value is Load.Failed)
        assertEquals(listOf("Offline"), f.history.state.value.entries.map { it.query })
        f.source.find = { query, _ -> SearchPage(listOf(song(query))) }
        f.controller.search(); runCurrent()
        assertEquals(listOf("Offline"), f.controller.ids())
        assertEquals(1, f.history.state.value.entries.size)
    }

    @Test fun clearing_history_during_search_is_not_undone_when_results_arrive() = runTest {
        val f = fixture()
        f.source.find = { query, _ -> delay(100); SearchPage(listOf(song(query))) }
        f.controller.search("Slow"); runCurrent()
        f.history.clearAll(); runCurrent()
        assertTrue(f.history.state.value.entries.isEmpty())
        advanceTimeBy(100); runCurrent()
        assertEquals(listOf("Slow"), f.controller.ids())
        assertTrue(f.history.state.value.entries.isEmpty())
    }

    @Test fun new_searches_default_to_songs_and_arbitrary_queries_are_not_rewritten() = runTest {
        val f = fixture()
        assertEquals(SearchFilter.SONGS, f.controller.filter.value)
        for (query in listOf("mashup sad love 1 hour", "Tamil cover unplugged", "भजन nonstop 3 hours", "podcast live remix",
            "Teri meri kahani instrumental", "Teri meri kahani instumental", "Teri meri kahani Instagram version",
            "Teri meri kahani cover by another creator", "karaoke no vocals piano", "slowed reverb 8D remix")) {
            f.controller.search(query); runCurrent()
            assertEquals(query to SearchFilter.SONGS, f.source.searches.last())
            assertEquals(listOf(query), f.controller.ids())
        }
    }

    @Test fun manual_results_keep_short_and_multi_hour_tracks_in_provider_order() = runTest {
        val f = fixture()
        val items = listOf(3600L, 20L, 10800L).mapIndexed { index, duration ->
            val id = "video$index"
            BrowseItem(ItemKind.SONG, id, "Result $index", track = Track(id, "Result $index", "Creator", durationSec = duration))
        }
        f.source.find = { _, _ -> SearchPage(items) }
        f.controller.search("any long mix query"); runCurrent()
        assertEquals(items, (f.controller.results.value as Load.Ok).value)
        assertEquals(listOf("video0", "video1", "video2"), f.controller.ids())
    }

    @Test fun clearing_a_narrow_query_resets_songs_for_the_next_search_without_erasing_history() = runTest {
        val f = fixture()
        f.controller.search("Old", SearchFilter.SONGS); runCurrent()
        f.controller.clear(); runCurrent()
        assertEquals(SearchFilter.SONGS, f.controller.filter.value)
        assertEquals(listOf(SavedSearch("Old", SearchFilter.SONGS)), f.history.state.value.entries)
        f.controller.search("New long mix"); runCurrent()
        assertEquals("New long mix" to SearchFilter.SONGS, f.source.searches.last())
    }

    @Test fun broadening_a_music_query_keeps_exact_text_and_saves_both_explicit_scopes() = runTest {
        val f = fixture()
        f.controller.search("lofi 2 hours", SearchFilter.SONGS); runCurrent()
        f.controller.setFilter(SearchFilter.ALL); runCurrent()
        assertEquals(listOf("lofi 2 hours" to SearchFilter.SONGS, "lofi 2 hours" to SearchFilter.ALL), f.source.searches)
        assertEquals(listOf(SearchFilter.ALL, SearchFilter.SONGS), f.history.state.value.entries.map { it.filter })
    }

    @Test fun video_and_music_video_searches_remain_distinct_and_replayable() = runTest {
        val f = fixture()
        f.controller.search("live cover", SearchFilter.VIDEOS); runCurrent()
        f.controller.setFilter(SearchFilter.MUSIC_VIDEOS); runCurrent()
        val video = f.history.state.value.entries.last()
        f.controller.repeat(video); runCurrent()
        assertEquals(SearchFilter.VIDEOS, f.controller.filter.value)
        assertEquals(listOf(SearchFilter.VIDEOS, SearchFilter.MUSIC_VIDEOS, SearchFilter.VIDEOS), f.source.searches.map { it.second })
    }

    @Test fun suggestion_retry_is_immediate_and_never_submits_or_records_the_query() = runTest {
        val f = fixture()
        f.source.suggest = { throw IOException("offline") }
        f.controller.typed("sad mix"); runCurrent(); advanceTimeBy(250); runCurrent()
        assertTrue(f.controller.suggestionsFailed.value)
        f.source.suggest = { listOf("sad mix 1 hour", "sad mix nonstop") }
        f.controller.retrySuggestions(); f.controller.retrySuggestions(); runCurrent()
        assertEquals(listOf("sad mix", "sad mix"), f.source.suggested)
        assertEquals(listOf("sad mix 1 hour", "sad mix nonstop"), f.controller.suggestions.value)
        assertFalse(f.controller.suggestionsFailed.value)
        assertFalse(f.controller.suggestionsLoading.value)
        assertTrue(f.source.searches.isEmpty())
        assertEquals(0, f.storage.writes)
    }

    @Test fun stale_suggestion_completion_cannot_hide_loading_for_a_newer_query() = runTest {
        val f = fixture()
        f.source.suggest = { query ->
            withContext(NonCancellable) { delay(if (query == "old") 400 else 500) }
            listOf(query)
        }
        f.controller.typed("old"); runCurrent(); advanceTimeBy(250); runCurrent()
        f.controller.typed("new"); runCurrent(); advanceTimeBy(250); runCurrent()
        advanceTimeBy(150); runCurrent() // Old finishes at 650; new is still running until 1000.
        assertTrue(f.controller.suggestionsLoading.value)
        advanceTimeBy(350); runCurrent()
        assertEquals(listOf("new"), f.controller.suggestions.value)
        assertFalse(f.controller.suggestionsFailed.value)
        assertFalse(f.controller.suggestionsLoading.value)
    }

    @Test fun clearing_or_submitting_hides_suggestion_status_and_disables_suggestion_retry() = runTest {
        val f = fixture()
        f.source.suggest = { throw IOException("offline") }
        f.controller.typed("a"); runCurrent(); advanceTimeBy(250); runCurrent()
        f.controller.clear(); f.controller.retrySuggestions(); runCurrent()
        assertFalse(f.controller.suggestionsFailed.value)
        assertFalse(f.controller.suggestionsLoading.value)
        assertEquals(1, f.source.suggested.size)
        f.controller.search("Submitted"); f.controller.retrySuggestions(); runCurrent()
        assertEquals(1, f.source.suggested.size)
        assertEquals(listOf("Submitted"), f.controller.ids())
    }

    @Test fun server_suggestion_order_is_preserved_after_whitespace_and_duplicate_cleanup() = runTest {
        val f = fixture()
        f.source.suggest = { listOf(" z mix ", "A mix", "Z MIX", "  ", "B mix") }
        f.controller.typed("mix"); runCurrent(); advanceTimeBy(250); runCurrent()
        assertEquals(listOf("z mix", "A mix", "B mix"), f.controller.suggestions.value)
    }

    @Test fun provider_correction_is_shown_without_silently_rewriting_user_input_or_history() = runTest {
        val f = fixture()
        f.source.find = { _, _ -> SearchPage(listOf(song("result")), correction = SearchCorrection("sad love mashup", corrected = true)) }
        f.controller.search("sad lov mashp"); runCurrent()
        assertEquals("sad lov mashp", f.controller.query.value)
        assertEquals(SearchCorrection("sad love mashup", true), f.controller.correction.value)
        assertEquals("sad lov mashp", f.history.state.value.entries.single().query)
        f.controller.search(checkNotNull(f.controller.correction.value).query); runCurrent()
        assertEquals(listOf("sad love mashup", "sad lov mashp"), f.history.state.value.entries.map { it.query })
        assertNull(f.controller.correction.value)
    }

    @Test fun did_you_mean_is_not_auto_correction_and_survives_pagination() = runTest {
        val f = fixture()
        f.source.find = { _, _ -> SearchPage(listOf(song("one")), Token("next"), SearchCorrection("correct term")) }
        f.source.next = { SearchPage(listOf(song("two"))) }
        f.controller.search("typed term"); runCurrent()
        f.controller.loadMore(); runCurrent()
        assertEquals(listOf("one", "two"), f.controller.ids())
        assertEquals(SearchCorrection("correct term", false), f.controller.correction.value)
        f.controller.typed("edited"); runCurrent()
        assertNull(f.controller.correction.value)
    }

    @Test fun empty_or_equivalent_provider_corrections_are_not_displayed() = runTest {
        val f = fixture()
        for (correction in listOf(" ", "  SAD  Mix ")) {
            f.source.find = { _, _ -> SearchPage(listOf(song("one")), correction = SearchCorrection(correction)) }
            f.controller.search("Sad Mix"); runCurrent()
            assertNull(f.controller.correction.value)
        }
    }

    @Test fun stale_search_correction_does_not_leak_into_a_new_search() = runTest {
        val f = fixture()
        f.source.find = { query, _ ->
            withContext(NonCancellable) { delay(if (query == "old") 100 else 10) }
            SearchPage(listOf(song(query)), correction = SearchCorrection("$query correction"))
        }
        f.controller.search("old"); runCurrent()
        f.controller.search("new"); runCurrent()
        advanceTimeBy(10); runCurrent()
        assertEquals("new correction", f.controller.correction.value?.query)
        advanceTimeBy(90); runCurrent()
        assertEquals("new correction", f.controller.correction.value?.query)
    }

    @Test fun same_title_versions_are_deduplicated_by_video_identity_not_title_or_creator_across_pages() = runTest {
        val f = fixture()
        fun version(id: String, creator: String, duration: Long) = BrowseItem(
            ItemKind.SONG, id, "Teri meri kahani", creator,
            track = Track(id, "Teri meri kahani", creator, durationSec = duration),
        )
        val original = version("original", "Original artist", 240)
        val cover = version("cover-one", "Cover creator", 200)
        val instrumental = version("instrumental", "Piano creator", 3600)
        val otherCover = version("cover-two", "Cover creator", 180)
        val reelVersion = version("reel-version", "Reel creator", 20)
        f.source.find = { _, _ -> SearchPage(listOf(original, cover, instrumental), Token("versions")) }
        f.source.next = { SearchPage(listOf(cover, otherCover, reelVersion)) }
        f.controller.search("Teri meri kahani"); runCurrent()
        f.controller.loadMore(); runCurrent()
        assertEquals(listOf(original, cover, instrumental, otherCover, reelVersion), (f.controller.results.value as Load.Ok).value)
        assertEquals(1, f.storage.writes)
    }

    @Test fun an_old_pinned_songs_search_with_some_results_can_still_broaden_to_creator_uploads() = runTest {
        val query = "Teri meri kahani instumental"
        val pinned = SavedSearch(query, SearchFilter.SONGS, pinned = true)
        val f = fixture(listOf(pinned))
        f.source.find = { _, filter -> SearchPage(listOf(song(if (filter == SearchFilter.ALL) "creator-version" else "catalogue-song"))) }
        f.controller.repeat(pinned); runCurrent()
        assertEquals(listOf("catalogue-song"), f.controller.ids())
        f.controller.setFilter(SearchFilter.ALL); runCurrent()
        assertEquals(listOf(query to SearchFilter.SONGS, query to SearchFilter.ALL), f.source.searches)
        assertEquals(listOf("creator-version"), f.controller.ids())
        assertEquals(pinned, f.history.state.value.entries.single { it.filter == SearchFilter.SONGS })
        assertEquals(SavedSearch(query, SearchFilter.ALL), f.history.state.value.entries.first())
    }

    @Test fun broadening_while_editing_keeps_spelling_and_fetches_suggestions_without_submitting() = runTest {
        val f = fixture()
        val query = "Teri meri kahani instumental"
        f.controller.edit(SavedSearch(query, SearchFilter.SONGS)); runCurrent(); advanceTimeBy(100)
        f.controller.setFilter(SearchFilter.ALL); runCurrent(); advanceTimeBy(250); runCurrent()
        assertEquals(query, f.controller.query.value)
        assertEquals(SearchFilter.ALL, f.controller.filter.value)
        assertEquals(listOf(query), f.source.suggested)
        assertNull(f.controller.results.value)
        assertTrue(f.source.searches.isEmpty())
        assertEquals(0, f.storage.writes)
    }

    @Test fun misspelled_instrumental_query_is_not_locally_replaced_or_recorded_as_the_provider_correction() = runTest {
        val f = fixture()
        val typed = "Teri meri kahani instumental"
        val suggested = "Teri meri kahani instrumental"
        f.source.find = { _, _ -> SearchPage(listOf(song("instrumental-upload")), correction = SearchCorrection(suggested)) }
        f.controller.search(typed); runCurrent()
        assertEquals(typed, f.controller.query.value)
        assertEquals(typed to SearchFilter.SONGS, f.source.searches.single())
        assertEquals(listOf(SavedSearch(typed, SearchFilter.SONGS)), f.history.state.value.entries)
        assertEquals(SearchCorrection(suggested), f.controller.correction.value)
        f.controller.search(suggested); runCurrent()
        assertEquals(suggested to SearchFilter.SONGS, f.source.searches.last())
        assertEquals(listOf(suggested, typed), f.history.state.value.entries.map { it.query })
    }

    @Test fun an_empty_provider_response_never_invents_instrumental_cover_or_reel_suggestions() = runTest {
        val f = fixture()
        f.source.suggest = { emptyList() }
        f.controller.typed("any song"); runCurrent(); advanceTimeBy(250); runCurrent()
        assertTrue(f.controller.suggestions.value.isEmpty())
        assertFalse(f.controller.suggestionsFailed.value)
        assertFalse(f.controller.suggestionsLoading.value)
        assertTrue(f.source.searches.isEmpty())
        assertEquals(0, f.storage.writes)
    }

    @Test fun blank_searches_are_ignored_and_long_input_is_bounded_before_network_and_storage() = runTest {
        val f = fixture()
        f.controller.search(" \t\n"); runCurrent()
        assertTrue(f.source.searches.isEmpty())
        assertEquals(0, f.storage.writes)
        f.controller.typed("x".repeat(1000))
        assertEquals(MAX_SEARCH_LENGTH, f.controller.query.value.length)
        f.controller.search(); runCurrent()
        assertEquals(MAX_SEARCH_LENGTH, f.source.searches.single().first.length)
        assertEquals(MAX_SEARCH_LENGTH, f.history.state.value.entries.single().query.length)
    }
}
