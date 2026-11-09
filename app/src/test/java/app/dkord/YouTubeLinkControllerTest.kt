package app.dkord

import app.dkord.core.Track
import app.dkord.data.links.*
import app.dkord.ui.links.YouTubeLinkController
import kotlinx.coroutines.CancellationException
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
class YouTubeLinkControllerTest {
    private class Source : YouTubeLinkSource {
        val calls = mutableListOf<String>()
        var find: suspend (YouTubeVideoLink) -> Track = { Track(it.videoId, "Exact upload", "Uploader") }
        override suspend fun resolve(link: YouTubeVideoLink): Track { calls += link.url; return find(link) }
    }
    private data class Fixture(val source: Source, val controller: YouTubeLinkController)
    private fun TestScope.fixture(): Fixture {
        val source = Source()
        return Fixture(source, YouTubeLinkController(source, backgroundScope))
    }
    private val first = "https://youtu.be/AbCdEf012_-"
    private val second = "https://youtube.com/shorts/ZyXwVu987_-"

    @Test fun typing_paste_and_clear_make_no_provider_call_or_hidden_search() = runTest {
        val f = fixture(); f.controller.typed(first); runCurrent(); advanceTimeBy(1000); runCurrent()
        assertEquals(first, f.controller.state.value.input)
        assertTrue(f.source.calls.isEmpty()); assertNull(f.controller.state.value.track)
        f.controller.typed(""); runCurrent(); assertTrue(f.source.calls.isEmpty())
    }

    @Test fun only_explicit_open_produces_the_exact_upload_preview() = runTest {
        val f = fixture(); f.controller.typed(first + "?list=not-a-queue&si=share"); f.controller.open(); runCurrent()
        val state = f.controller.state.value
        assertEquals(listOf("https://www.youtube.com/watch?v=AbCdEf012_-"), f.source.calls)
        assertEquals("AbCdEf012_-", state.track?.id); assertFalse(state.loading); assertNull(state.problem)
        assertEquals("https://www.youtube.com/watch?v=AbCdEf012_-", state.canonicalUrl)
    }

    @Test fun invalid_or_playlist_only_input_fails_before_any_provider_request() = runTest {
        val f = fixture()
        for ((input, problem) in listOf("https://untrusted.test/watch?v=AbCdEf012_-" to YouTubeLinkProblem.INVALID_LINK,
            "https://youtube.com/playlist?list=PL_list" to YouTubeLinkProblem.PLAYLIST_ONLY)) {
            f.controller.typed(input); f.controller.open(); runCurrent()
            assertEquals(problem, f.controller.state.value.problem); assertFalse(f.controller.state.value.loading)
        }
        assertTrue(f.source.calls.isEmpty())
    }

    @Test fun repeat_submit_during_loading_does_not_duplicate_metadata_requests() = runTest {
        val f = fixture(); f.source.find = { delay(100); Track(it.videoId, "Exact", "Uploader") }
        f.controller.typed(first); f.controller.open(); f.controller.open(); runCurrent()
        assertTrue(f.controller.state.value.loading); assertEquals(1, f.source.calls.size)
        advanceTimeBy(100); runCurrent(); assertEquals("AbCdEf012_-", f.controller.state.value.track?.id)
    }

    @Test fun editing_immediately_removes_the_old_preview_and_its_actions() = runTest {
        val f = fixture(); f.controller.typed(first); f.controller.open(); runCurrent()
        assertNotNull(f.controller.state.value.track)
        f.controller.typed(second)
        assertNull(f.controller.state.value.track); assertNull(f.controller.state.value.canonicalUrl)
        assertNull(f.controller.state.value.problem); assertEquals(1, f.source.calls.size)
    }

    @Test fun a_slow_uncancellable_old_lookup_cannot_replace_the_newer_exact_upload() = runTest {
        val f = fixture(); f.source.find = { link ->
            withContext(NonCancellable) { delay(if (link.videoId == "AbCdEf012_-") 100 else 10) }
            Track(link.videoId, "Chosen ${link.videoId}", "Uploader")
        }
        f.controller.typed(first); f.controller.open(); runCurrent()
        f.controller.typed(second); f.controller.open(); runCurrent(); advanceTimeBy(10); runCurrent()
        assertEquals("ZyXwVu987_-", f.controller.state.value.track?.id)
        advanceTimeBy(100); runCurrent()
        assertEquals("ZyXwVu987_-", f.controller.state.value.track?.id); assertNull(f.controller.state.value.problem)
    }

    @Test fun cancelling_or_leaving_the_page_ignores_late_success_without_erasing_the_input() = runTest {
        val f = fixture(); f.source.find = { link -> withContext(NonCancellable) { delay(100) }; Track(link.videoId, "Old", "Uploader") }
        f.controller.typed(first); f.controller.open(); runCurrent(); f.controller.cancel()
        assertEquals(first, f.controller.state.value.input); assertFalse(f.controller.state.value.loading)
        advanceTimeBy(100); runCurrent(); assertNull(f.controller.state.value.track); assertNull(f.controller.state.value.problem)
    }

    @Test fun a_cancelled_late_failure_cannot_replace_new_input_with_an_error() = runTest {
        val f = fixture(); f.source.find = { withContext(NonCancellable) { delay(100) }; throw IOException("stale") }
        f.controller.typed(first); f.controller.open(); runCurrent(); f.controller.typed(second)
        advanceTimeBy(100); runCurrent()
        assertEquals(second, f.controller.state.value.input); assertNull(f.controller.state.value.problem); assertFalse(f.controller.state.value.loading)
    }

    @Test fun provider_failure_has_no_fake_result_and_can_be_retried_without_a_search_fallback() = runTest {
        val f = fixture(); f.source.find = { throw YouTubeLinkException(YouTubeLinkProblem.PRIVATE) }
        f.controller.typed(first); f.controller.open(); runCurrent()
        assertEquals(YouTubeLinkProblem.PRIVATE, f.controller.state.value.problem); assertNull(f.controller.state.value.track)
        f.source.find = { Track(it.videoId, "Now available", "Uploader") }; f.controller.open(); runCurrent()
        assertEquals(2, f.source.calls.size); assertNotNull(f.controller.state.value.track); assertNull(f.controller.state.value.problem)
    }

    @Test fun a_source_returning_another_video_is_never_exposed_as_success() = runTest {
        val f = fixture(); f.source.find = { Track("ZyXwVu987_-", "Substitute", "Uploader") }
        f.controller.typed(first); f.controller.open(); runCurrent()
        assertEquals(YouTubeLinkProblem.UNAVAILABLE, f.controller.state.value.problem); assertNull(f.controller.state.value.track)
    }

    @Test fun oversized_pastes_retain_an_invalid_overflow_sentinel_instead_of_becoming_valid() = runTest {
        val f = fixture(); f.controller.typed(first + "?si=" + "x".repeat(MAX_YOUTUBE_LINK_LENGTH * 2))
        assertEquals(MAX_YOUTUBE_LINK_LENGTH + 1, f.controller.state.value.input.length)
        f.controller.open(); runCurrent(); assertEquals(YouTubeLinkProblem.INVALID_LINK, f.controller.state.value.problem)
        assertTrue(f.source.calls.isEmpty())
    }

    @Test fun a_source_cancellation_does_not_create_a_user_facing_failure() = runTest {
        val f = fixture(); f.source.find = { throw CancellationException("cancelled") }
        f.controller.typed(first); f.controller.open(); runCurrent()
        assertNull(f.controller.state.value.problem); assertNull(f.controller.state.value.track); assertFalse(f.controller.state.value.loading)
    }
}
