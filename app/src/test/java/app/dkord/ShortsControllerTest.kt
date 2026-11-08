package app.dkord

import app.dkord.data.shorts.*
import app.dkord.ui.shorts.ShortsController
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.delay
import kotlinx.coroutines.test.*
import kotlinx.coroutines.withContext
import org.junit.Assert.*
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class ShortsControllerTest {
    private fun clip(id: String, title: String = "Clip $id", duration: Long = 30) = MusicClip(id, title, "Creator", null, duration)
    @Test fun identities_are_upload_ids_and_native_short_duration_policy_does_not_affect_manual_search() {
        val a = clip("a", "Same"); val b = clip("b", "Same")
        assertEquals(listOf(a, b), uniqueClips(emptyList(), listOf(a, a, b, clip("long", duration = 3600))))
        assertEquals(listOf(b), uniqueClips(listOf(a), listOf(a, b)))
    }
    @Test fun full_song_hint_removes_hashtags_but_never_claims_or_fabricates_a_song_id() {
        assertEquals("A real title", fullSongQuery(clip("a", "A real title #shorts #संगीत")))
        assertTrue(fullSongQuery(clip("a", "#shorts")).isNotBlank())
    }
    @Test fun new_search_rejects_a_stale_uncancellable_provider_page() = runTest {
        val source = ShortsSource { query, _ ->
            withContext(NonCancellable) { delay(if (query == "old") 100 else 10) }
            ShortsPage(listOf(clip(query)))
        }
        val controller = ShortsController(source, backgroundScope)
        controller.search("old"); runCurrent(); controller.search("new"); runCurrent()
        advanceTimeBy(100); runCurrent()
        assertEquals(listOf("new"), controller.state.value.clips.map { it.id })
    }
    @Test fun empty_and_error_pages_offer_retry_without_fabricated_clips() = runTest {
        var failed = true
        val c = ShortsController(ShortsSource { _, _ -> if (failed) error("offline") else ShortsPage(emptyList()) }, backgroundScope)
        c.initial(); runCurrent(); assertTrue(c.state.value.failed); assertTrue(c.state.value.clips.isEmpty())
        failed = false; c.retry(); runCurrent(); assertFalse(c.state.value.failed); assertTrue(c.state.value.clips.isEmpty())
    }
    @Test fun pagination_is_coalesced_and_deduplicated_in_provider_order() = runTest {
        val cursor = object : ShortsCursor { }
        var calls = 0
        val c = ShortsController(ShortsSource { _, next ->
            calls++; delay(10)
            if (next == null) ShortsPage(listOf(clip("a")), cursor) else ShortsPage(listOf(clip("a"), clip("b")))
        }, backgroundScope)
        c.initial(); runCurrent(); advanceTimeBy(10); runCurrent()
        repeat(10) { c.more() }; runCurrent(); advanceTimeBy(10); runCurrent()
        assertEquals(2, calls); assertEquals(listOf("a", "b"), c.state.value.clips.map { it.id })
    }
}
