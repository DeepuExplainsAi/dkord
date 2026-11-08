package app.dkord

import app.dkord.core.BrowseItem
import app.dkord.core.ItemKind
import app.dkord.core.Track
import app.dkord.player.AutoplayCoordinator
import app.dkord.player.AutoplaySnapshot
import app.dkord.ui.search.searchPlaybackQueue
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.delay
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.withContext
import org.junit.Assert.*
import org.junit.Test
import java.io.IOException

@OptIn(ExperimentalCoroutinesApi::class)
class AutoplayCoordinatorTest {
    private companion object {
        fun track(id: String, title: String = "Song $id", duration: Long = 180) = Track(id, title, "Creator", durationSec = duration)
    }
    private class Harness(scope: CoroutineScope) {
        var state: AutoplaySnapshot? = AutoplaySnapshot(listOf(track("seed")), 0)
        val calls = mutableListOf<Pair<Track, List<Track>>>()
        val appended = mutableListOf<Pair<List<Track>, Boolean>>()
        val hints = mutableListOf<String>()
        var fetch: suspend (Track, List<Track>) -> List<Track> = { _, _ -> listOf(track("next")) }
        var afterAppend: (() -> Unit)? = null
        val coordinator = AutoplayCoordinator(scope,
            source = { seed, queue, hint -> calls += seed to queue; hints += hint; fetch(seed, queue) },
            snapshot = { state },
            append = { fresh, resume ->
                appended += fresh to resume
                val current = checkNotNull(state)
                state = current.copy(queue = current.queue + fresh, ended = false)
                afterAppend?.invoke()
            },
        )
    }

    @Test fun a_search_selection_starts_with_that_exact_song_then_requests_different_related_music() = runTest {
        val h = Harness(backgroundScope)
        val chosen = track("chosen", "SEM CONTROLE (Slowed)")
        val matches = listOf(track("other-version", "SEM CONTROLE"), chosen, track("hour", "1 hour mix", 3600))
        h.state = AutoplaySnapshot(searchPlaybackQueue(BrowseItem(ItemKind.SONG, chosen.id, chosen.title, track = matches[1])), 0)
        h.fetch = { _, _ -> listOf(track("slowed", "SEM CONTROLE (Ultra Slowed)"), track("different")) }
        h.coordinator.update(); runCurrent()
        assertEquals(chosen, h.calls.single().first)
        assertEquals(listOf(chosen), h.calls.single().second)
        assertEquals(listOf("chosen", "different"), checkNotNull(h.state).queue.map { it.id })
    }

    @Test fun repeated_events_share_one_in_flight_request() = runTest {
        val h = Harness(backgroundScope)
        h.fetch = { _, _ -> delay(100); listOf(track("next")) }
        repeat(20) { h.coordinator.update() }; runCurrent()
        assertEquals(1, h.calls.size)
        advanceTimeBy(100); runCurrent()
        assertEquals(1, h.appended.size)
    }

    @Test fun replacing_a_queue_cancels_and_rejects_an_old_uncancellable_response() = runTest {
        val h = Harness(backgroundScope)
        h.fetch = { seed, _ ->
            withContext(NonCancellable) { delay(if (seed.id == "seed") 200 else 10) }
            listOf(track("${seed.id}-related"))
        }
        h.coordinator.update(); runCurrent()
        h.coordinator.invalidate()
        h.state = AutoplaySnapshot(listOf(track("new-choice")), 0)
        h.coordinator.update(); runCurrent(); advanceTimeBy(10); runCurrent()
        assertEquals(listOf("new-choice", "new-choice-related"), checkNotNull(h.state).queue.map { it.id })
        advanceTimeBy(190); runCurrent()
        assertEquals(listOf("new-choice", "new-choice-related"), checkNotNull(h.state).queue.map { it.id })
        assertEquals(1, h.appended.size)
    }

    @Test fun queue_replacement_detected_from_a_snapshot_also_rejects_old_results() = runTest {
        val h = Harness(backgroundScope)
        h.fetch = { seed, _ -> withContext(NonCancellable) { delay(100) }; listOf(track("${seed.id}-related")) }
        h.coordinator.update(); runCurrent()
        h.state = AutoplaySnapshot(listOf(track("new")), 0)
        h.coordinator.update(); runCurrent(); advanceTimeBy(100); runCurrent()
        assertEquals(listOf("new", "new-related"), checkNotNull(h.state).queue.map { it.id })
    }

    @Test fun disconnect_and_reconnect_with_the_same_seed_do_not_accept_the_previous_session() = runTest {
        val h = Harness(backgroundScope)
        h.fetch = { _, _ ->
            val call = h.calls.size
            withContext(NonCancellable) { delay(if (call == 1) 200 else 10) }
            listOf(track("session-$call"))
        }
        h.coordinator.update(); runCurrent()
        h.state = null; h.coordinator.invalidate()
        h.state = AutoplaySnapshot(listOf(track("seed")), 0)
        h.coordinator.update(); runCurrent(); advanceTimeBy(200); runCurrent()
        assertEquals(listOf("seed", "session-2"), checkNotNull(h.state).queue.map { it.id })
    }

    @Test fun turning_autoplay_off_during_a_request_never_appends_or_resumes() = runTest {
        val h = Harness(backgroundScope)
        h.fetch = { _, _ -> withContext(NonCancellable) { delay(100) }; listOf(track("next")) }
        h.coordinator.update(); runCurrent()
        h.state = checkNotNull(h.state).copy(enabled = false, ended = true)
        h.coordinator.update(); advanceTimeBy(100); runCurrent()
        assertTrue(h.appended.isEmpty())
    }

    @Test fun pause_or_end_of_track_sleep_while_a_request_is_pending_cannot_restart_playback() = runTest {
        val h = Harness(backgroundScope)
        h.fetch = { _, _ -> delay(100); listOf(track("next")) }
        h.coordinator.update(); runCurrent()
        // Check the result-time guard too: no separate update callback is required for safety.
        h.state = checkNotNull(h.state).copy(playWhenReady = false, ended = true)
        advanceTimeBy(100); runCurrent()
        assertTrue(h.appended.isEmpty())
    }

    @Test fun changing_repeat_mode_before_a_response_keeps_the_user_queue_untouched() = runTest {
        val h = Harness(backgroundScope)
        h.fetch = { _, _ -> delay(100); listOf(track("next")) }
        h.coordinator.update(); runCurrent()
        h.state = checkNotNull(h.state).copy(repeatOff = false)
        advanceTimeBy(100); runCurrent()
        assertTrue(h.appended.isEmpty())
    }

    @Test fun manual_queue_edits_are_detected_even_without_an_invalidate_callback() = runTest {
        val h = Harness(backgroundScope)
        h.fetch = { _, _ -> delay(100); listOf(track("next")) }
        h.coordinator.update(); runCurrent()
        h.state = checkNotNull(h.state).copy(queue = listOf(track("seed"), track("manual")))
        advanceTimeBy(100); runCurrent()
        assertTrue(h.appended.isEmpty())
        assertEquals(listOf("seed", "manual"), checkNotNull(h.state).queue.map { it.id })
    }

    @Test fun replacing_the_prefix_of_a_queue_with_the_same_tail_is_still_a_different_request() = runTest {
        val h = Harness(backgroundScope)
        h.state = AutoplaySnapshot(listOf(track("first"), track("tail")), 1)
        h.fetch = { _, _ -> delay(100); listOf(track("next")) }
        h.coordinator.update(); runCurrent()
        h.state = checkNotNull(h.state).copy(queue = listOf(track("replacement"), track("tail")))
        advanceTimeBy(100); runCurrent()
        assertTrue(h.appended.isEmpty())
    }

    @Test fun disabled_paused_restored_idle_repeating_and_invalid_snapshots_never_start_radio() = runTest {
        val h = Harness(backgroundScope)
        val playing = checkNotNull(h.state)
        for (state in listOf(playing.copy(enabled = false), playing.copy(playWhenReady = false), playing.copy(idle = true),
            playing.copy(repeatOff = false), playing.copy(index = -1), playing.copy(queue = emptyList()), null)) {
            h.state = state; h.coordinator.update(); runCurrent()
        }
        assertTrue(h.calls.isEmpty())
    }

    @Test fun an_explicit_album_or_playlist_is_not_extended_until_near_its_end() = runTest {
        val h = Harness(backgroundScope)
        h.state = AutoplaySnapshot((1..5).map { track("song$it") }, 0)
        h.coordinator.update(); runCurrent()
        assertTrue(h.calls.isEmpty())
        h.state = checkNotNull(h.state).copy(index = 3)
        h.coordinator.update(); runCurrent()
        assertEquals("song5", h.calls.single().first.id)
    }

    @Test fun a_running_request_can_complete_after_the_song_ends_without_duplicate_fetches() = runTest {
        val h = Harness(backgroundScope)
        h.fetch = { _, _ -> delay(100); listOf(track("next")) }
        h.coordinator.update(); runCurrent()
        h.state = checkNotNull(h.state).copy(ended = true)
        h.coordinator.update(); runCurrent(); advanceTimeBy(100); runCurrent()
        assertEquals(1, h.calls.size)
        assertTrue(h.appended.single().second)
    }

    @Test fun successful_prefetch_does_not_seek_or_restart_a_song_that_is_still_playing() = runTest {
        val h = Harness(backgroundScope)
        h.coordinator.update(); runCurrent()
        assertFalse(h.appended.single().second)
        assertEquals("seed", checkNotNull(h.state).queue.first().id)
    }

    @Test fun empty_or_failed_results_are_bounded_with_one_additional_attempt_at_queue_end() = runTest {
        val h = Harness(backgroundScope)
        h.fetch = { _, _ -> throw IOException("offline") }
        h.coordinator.update(); runCurrent()
        repeat(20) { h.coordinator.update(); runCurrent() }
        assertEquals(1, h.calls.size)
        h.state = checkNotNull(h.state).copy(ended = true)
        repeat(20) { h.coordinator.update(); runCurrent() }
        assertEquals(2, h.calls.size)
        assertTrue(h.appended.isEmpty())
    }

    @Test fun an_explicit_retry_after_failure_can_use_a_new_result() = runTest {
        val h = Harness(backgroundScope)
        h.fetch = { _, _ -> emptyList() }
        h.coordinator.update(); runCurrent()
        h.fetch = { _, _ -> listOf(track("retry-result")) }
        h.coordinator.invalidate(); h.coordinator.update(); runCurrent()
        assertEquals(listOf("retry-result"), h.appended.single().first.map { it.id })
    }

    @Test fun result_time_filtering_excludes_versions_and_long_mixes_and_caps_the_batch() = runTest {
        val h = Harness(backgroundScope)
        h.fetch = { _, _ -> listOf(track("version", "Song seed (Slowed)"), track("hour", "Unrequested mix", 3600)) +
            (1..40).map { track("different$it") } }
        h.coordinator.update(); runCurrent()
        assertEquals((1..15).map { "different$it" }, h.appended.single().first.map { it.id })
    }

    @Test fun reentrant_player_events_do_not_lose_ownership_of_the_next_cancellable_job() = runTest {
        val h = Harness(backgroundScope)
        var cancelled = false
        h.fetch = { seed, _ ->
            if (seed.id == "seed") listOf(track("second"))
            else try { delay(1000); listOf(track("third")) } finally { cancelled = true }
        }
        h.afterAppend = { h.coordinator.update() }
        h.coordinator.update(); runCurrent()
        assertEquals(2, h.calls.size)
        h.coordinator.invalidate(); runCurrent()
        assertTrue(cancelled)
        assertEquals(listOf("seed", "second"), checkNotNull(h.state).queue.map { it.id })
    }

    @Test fun consecutive_related_batches_keep_the_original_selection_anchor_not_the_queue_tail() = runTest {
        val h = Harness(backgroundScope)
        val selected = track("seed")
        h.state = AutoplaySnapshot(listOf(selected), 0, radioSeed = selected, radioHint = "hindi sad")
        h.fetch = { _, _ -> listOf(track("related-${h.calls.size}")) }
        repeat(4) {
            h.state = checkNotNull(h.state).let { it.copy(index = it.queue.lastIndex) }
            h.coordinator.update(); runCurrent()
        }
        assertEquals(List(4) { "seed" }, h.calls.map { it.first.id })
        assertEquals(List(4) { "hindi sad" }, h.hints)
        assertEquals(listOf("seed", "related-1", "related-2", "related-3", "related-4"), checkNotNull(h.state).queue.map { it.id })
    }

    @Test fun changed_context_for_the_same_song_and_queue_rejects_an_uncancellable_old_response() = runTest {
        val h = Harness(backgroundScope)
        val selected = track("seed")
        h.state = checkNotNull(h.state).copy(radioSeed = selected, radioHint = "hindi sad")
        h.fetch = { _, _ ->
            val call = h.calls.size
            withContext(NonCancellable) { delay(if (call == 1) 100 else 5) }
            listOf(track("result-$call"))
        }
        h.coordinator.update(); runCurrent()
        h.state = checkNotNull(h.state).copy(radioHint = "hindi party")
        h.coordinator.update(); runCurrent(); advanceTimeBy(100); runCurrent()
        assertEquals(listOf("hindi sad", "hindi party"), h.hints)
        assertEquals(listOf("seed", "result-2"), checkNotNull(h.state).queue.map { it.id })
    }

    @Test fun result_time_context_guard_works_without_a_separate_invalidation_event() = runTest {
        val h = Harness(backgroundScope)
        h.fetch = { _, _ -> delay(100); listOf(track("wrong-context")) }
        h.state = checkNotNull(h.state).copy(radioHint = "sad")
        h.coordinator.update(); runCurrent()
        h.state = checkNotNull(h.state).copy(radioHint = "party")
        advanceTimeBy(100); runCurrent()
        assertTrue(h.appended.isEmpty())
    }

    @Test fun changing_the_explicit_anchor_with_the_same_queue_invalidates_in_flight_context() = runTest {
        val h = Harness(backgroundScope)
        h.fetch = { _, _ -> delay(100); listOf(track("wrong-anchor")) }
        h.state = checkNotNull(h.state).copy(radioSeed = track("seed"))
        h.coordinator.update(); runCurrent()
        h.state = checkNotNull(h.state).copy(radioSeed = track("new-anchor"))
        advanceTimeBy(100); runCurrent()
        assertTrue(h.appended.isEmpty())
    }

    @Test fun pause_and_resume_keep_the_session_anchor_without_resuming_an_old_request() = runTest {
        val h = Harness(backgroundScope)
        val selected = track("seed")
        h.state = checkNotNull(h.state).copy(radioSeed = selected, radioHint = "hindi chill")
        h.coordinator.update(); runCurrent()
        h.coordinator.invalidate()
        h.state = checkNotNull(h.state).copy(playWhenReady = false)
        h.coordinator.update(); runCurrent()
        assertEquals(1, h.calls.size)
        h.state = checkNotNull(h.state).let { it.copy(playWhenReady = true, index = it.queue.lastIndex) }
        h.fetch = { _, _ -> listOf(track("third")) }
        h.coordinator.update(); runCurrent()
        assertEquals(listOf("seed", "seed"), h.calls.map { it.first.id })
        assertEquals(listOf("hindi chill", "hindi chill"), h.hints)
        assertFalse(h.appended.last().second)
    }

    @Test fun removing_the_anchor_from_the_visible_queue_does_not_reintroduce_it_or_its_versions() = runTest {
        val h = Harness(backgroundScope)
        val original = track("seed")
        h.state = AutoplaySnapshot(listOf(track("kept")), 0, radioSeed = original)
        h.fetch = { _, _ -> listOf(original, track("cover", "Song seed (Cover)"), track("fresh")) }
        h.coordinator.update(); runCurrent()
        assertEquals("seed", h.calls.single().first.id)
        assertEquals(listOf("kept", "fresh"), checkNotNull(h.state).queue.map { it.id })
    }

    @Test fun reentrant_events_with_a_pinned_anchor_still_own_the_next_cancellable_request() = runTest {
        val h = Harness(backgroundScope)
        var cancelled = false
        h.state = checkNotNull(h.state).copy(radioSeed = track("seed"))
        h.fetch = { _, _ ->
            if (h.calls.size == 1) listOf(track("second"))
            else try { delay(1000); listOf(track("third")) } finally { cancelled = true }
        }
        h.afterAppend = { h.coordinator.update() }
        h.coordinator.update(); runCurrent()
        assertEquals(2, h.calls.size)
        assertEquals(listOf("seed", "seed"), h.calls.map { it.first.id })
        h.coordinator.invalidate(); runCurrent()
        assertTrue(cancelled)
        assertEquals(listOf("seed", "second"), checkNotNull(h.state).queue.map { it.id })
    }

}
