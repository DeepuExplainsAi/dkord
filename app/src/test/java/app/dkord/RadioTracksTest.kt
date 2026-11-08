package app.dkord

import app.dkord.core.Track
import app.dkord.data.yt.RadioTrackFilter
import app.dkord.data.yt.musicRadioRecommendations
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.withContext
import kotlinx.coroutines.test.runTest
import org.junit.Assert.*
import org.junit.Test
import java.io.IOException

@OptIn(ExperimentalCoroutinesApi::class)
class RadioTracksTest {
    private val seed = Track("seed", "SEM CONTROLE (Slowed)", "nightfxrce", durationSec = 106)
    private fun track(id: String, title: String = "Different song $id", duration: Long = 180) = Track(id, title, "Creator", durationSec = duration)

    @Test fun automatic_candidates_exclude_the_seed_and_its_versions_regardless_of_uploader() {
        val candidates = listOf(track("other-id", "SEM CONTROLE (SLOWED)"), track("ultra", "SEM CONTROLE (Ultra Slowed)"),
            track("prefix", "nightfxrce - SEM CONTROLE (Super Slowed)"), track("suffix", "SEM CONTROLE - Slowed"), track("next"))
        assertEquals(listOf("next"), RadioTrackFilter(seed, emptyList()).select(candidates).map { it.id })
    }

    @Test fun provider_order_is_retained_while_duplicate_ids_and_base_titles_are_removed() {
        val result = RadioTrackFilter(seed, emptyList()).select(listOf(track("z"), track("a"), track("z"), track("cover", "Different song a (Cover)"), track("b")))
        assertEquals(listOf("z", "a", "b"), result.map { it.id })
    }

    @Test fun already_queued_ids_and_other_versions_of_queued_songs_are_not_appended() {
        val queued = listOf(track("queued", "Another song"))
        val result = RadioTrackFilter(seed, queued).select(listOf(track("queued", "Changed metadata"), track("version", "Another song (Remix)"), track("fresh")))
        assertEquals(listOf("fresh"), result.map { it.id })
    }

    @Test fun radio_keeps_the_existing_short_long_and_unknown_duration_policy() {
        val result = RadioTrackFilter(seed, emptyList()).select(listOf(track("short", duration = 59), track("min", duration = 60),
            track("max", duration = 720), track("long", duration = 721), track("hour", duration = 3600), track("unknown", duration = 0)))
        assertEquals(listOf("min", "max", "unknown"), result.map { it.id })
    }

    @Test fun unknown_duration_does_not_allow_explicit_hour_loops_or_every_version_compilations() {
        val result = RadioTrackFilter(seed, emptyList()).select(listOf(track("hour", "Phonk 1 hour mix", 0),
            track("versions", "SEM CONTROLE I (EVERY VERSION)", 300), track("album", "Full album", 0), track("next")))
        assertEquals(listOf("next"), result.map { it.id })
    }

    @Test fun invalid_rows_do_not_block_later_valid_candidates() {
        val result = RadioTrackFilter(seed, emptyList()).select(listOf(track("", "No id"), track("blank", " "), track("punctuation", "..."), track("valid")))
        assertEquals(listOf("valid"), result.map { it.id })
    }

    @Test fun genuine_radio_is_used_without_a_search_when_it_has_different_songs() = runTest {
        val searches = mutableListOf<String>()
        val result = musicRadioRecommendations(seed, emptyList(), { listOf(track("second"), track("first")) }, { searches += it; emptyList() })
        assertEquals(listOf("second", "first"), result.map { it.id })
        assertTrue(searches.isEmpty())
    }

    @Test fun title_search_containing_only_versions_falls_back_to_other_songs_by_the_creator() = runTest {
        val searches = mutableListOf<String>()
        val result = musicRadioRecommendations(seed, emptyList(), { listOf(track("variant", "SEM CONTROLE (Ultra Slowed)")) }, { query ->
            searches += query
            if (query == seed.artist) listOf(track("different")) else listOf(track("cover", "SEM CONTROLE (Cover)"))
        })
        assertEquals(listOf("${seed.artist} ${seed.title}", seed.artist), searches)
        assertEquals(listOf("different"), result.map { it.id })
    }

    @Test fun network_failure_can_use_music_search_but_never_invents_tracks() = runTest {
        val searches = mutableListOf<String>()
        val result = musicRadioRecommendations(seed, emptyList(), { throw IOException("offline") }, { searches += it; throw IOException("offline") })
        assertTrue(result.isEmpty())
        assertEquals(2, searches.size)
    }

    @Test fun cancellation_is_not_swallowed_into_more_search_requests() = runTest {
        var searched = false
        try {
            musicRadioRecommendations(seed, emptyList(), { throw CancellationException("cancelled") }, { searched = true; emptyList() })
            fail("Cancellation swallowed")
        } catch (_: CancellationException) { }
        assertFalse(searched)
    }

    @Test fun cancelled_blocking_radio_cannot_start_fallback_search_after_returning_normally() = runTest {
        var searched = false
        var finished = false
        val job = backgroundScope.launch {
            try {
                musicRadioRecommendations(seed, emptyList(), {
                    withContext(NonCancellable) { delay(100); emptyList() }
                }, { searched = true; listOf(track("unwanted-fallback")) })
            } finally { finished = true }
        }
        runCurrent(); job.cancel(); advanceTimeBy(100); runCurrent()
        assertTrue(finished)
        assertFalse(searched)
        assertTrue(job.isCancelled)
    }

    @Test fun blank_seed_id_never_starts_online_radio() = runTest {
        var requested = false
        val result = musicRadioRecommendations(seed.copy(id = ""), emptyList(), { requested = true; emptyList() }, { requested = true; emptyList() })
        assertTrue(result.isEmpty()); assertFalse(requested)
    }
}
