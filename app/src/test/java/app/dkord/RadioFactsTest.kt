package app.dkord

import app.dkord.core.Track
import app.dkord.data.yt.CachedRadioFacts
import app.dkord.data.yt.RadioFacts
import app.dkord.data.yt.lenientJson
import app.dkord.data.yt.parseRadioFacts
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.delay
import kotlinx.coroutines.test.runTest
import org.junit.Assert.*
import org.junit.Test
import java.io.IOException
import java.util.Base64

@OptIn(ExperimentalCoroutinesApi::class)
class RadioFactsTest {
    private val id = "Abcdefghij1"
    private fun track(value: String = id) = Track(value, "Title", "Artist")
    private fun root(formats: String = "[]", details: String = "") = lenientJson.parseToJsonElement("""
        {"videoDetails":{"videoId":"$id","keywords":["hindi","sad"],"viewCount":"123456"$details},
         "streamingData":{"adaptiveFormats":$formats},
         "microformat":{"playerMicroformatRenderer":{"uploadDate":"2026-11-01"}},
         "captions":{"playerCaptionsTracklistRenderer":{"captionTracks":[{"languageCode":"en"}]}}}
    """.trimIndent())
    // Same documented XTags protobuf wire format as pinned NewPipe; not a mocked language classifier.
    private fun xtags(type: String): String {
        val pair = byteArrayOf(10, 5) + "acont".toByteArray() + byteArrayOf(18, type.length.toByte()) + type.toByteArray()
        return Base64.getUrlEncoder().withoutPadding().encodeToString(byteArrayOf(10, pair.size.toByte()) + pair)
    }
    private fun audio(lang: String, type: String?) = """{"mimeType":"audio/mp4","audioTrack":{"id":"$lang.4"}${type?.let { ",\"xtags\":\"${xtags(it)}\"" }.orEmpty()}}"""

    @Test fun only_original_audio_locale_counts_not_dubbed_default_or_unknown_alternate_track() {
        val formats = "[${audio("en", "dubbed-auto")},${audio("hi", "original")},${audio("es", null)}]"
        val facts = parseRadioFacts(root(formats), id)
        assertEquals("hi", facts.language)
        assertEquals(listOf("hindi", "sad"), facts.tags)
        assertEquals(123456L, facts.views)
    }

    @Test fun captions_upload_date_and_dubbed_only_or_missing_track_type_do_not_invent_song_facts() {
        for (formats in listOf("[]", "[${audio("en", "dubbed")}]", "[${audio("en", null)}]")) {
            val facts = parseRadioFacts(root(formats), id)
            assertNull(facts.language)
            assertNull(facts.yearHint)
        }
    }

    @Test fun conflicting_original_locales_are_unknown_and_foreign_response_metadata_is_ignored() {
        assertNull(parseRadioFacts(root("[${audio("hi", "original")},${audio("en", "original")}]"), id).language)
        assertEquals(RadioFacts(), parseRadioFacts(root(), "Different01"))
    }

    @Test fun invalid_or_unavailable_view_counts_are_not_fabricated() {
        val value = lenientJson.parseToJsonElement("""{"videoDetails":{"videoId":"$id","viewCount":"not-a-number"}}""")
        assertEquals(0L, parseRadioFacts(value, id).views)
    }

    @Test fun metadata_cache_preserves_facts_and_expires_without_a_persistent_search_profile() = runTest {
        var calls = 0
        var clock = 0L
        val facts = RadioFacts("hi", listOf("sad"), 100)
        val cache = CachedRadioFacts(load = { calls++; facts }, now = { clock })
        assertEquals(facts, cache.facts(track()))
        assertEquals(facts, cache.facts(track()))
        assertEquals(1, calls)
        clock += 6 * 60 * 60_000L
        assertEquals(facts, cache.facts(track()))
        assertEquals(2, calls)
    }

    @Test fun invalid_and_generated_audio_ids_never_make_metadata_requests() = runTest {
        var calls = 0
        val cache = CachedRadioFacts({ calls++; RadioFacts("hi") })
        for (value in listOf("", "short", "local-studio-project", "https://watch/id")) assertEquals(RadioFacts(), cache.facts(track(value)))
        assertEquals(0, calls)
    }

    @Test fun a_metadata_failure_short_circuits_other_candidates_but_can_retry_later() = runTest {
        var calls = 0
        var clock = 0L
        val cache = CachedRadioFacts(load = { calls++; if (calls == 1) throw IOException("offline") else RadioFacts("hi") }, now = { clock })
        assertEquals(RadioFacts(), cache.facts(track()))
        assertEquals(RadioFacts(), cache.facts(track("Abcdefghij2")))
        assertEquals(1, calls)
        clock = 15_000
        assertEquals(RadioFacts("hi"), cache.facts(track()))
        assertEquals(2, calls)
    }

    @Test fun cancellation_is_not_negative_cached_or_swallowed_into_provider_retry() = runTest {
        var calls = 0
        val cache = CachedRadioFacts({ calls++; if (calls == 1) throw CancellationException("cancel") else RadioFacts("hi") })
        try { cache.facts(track()); fail("Cancellation swallowed") } catch (_: CancellationException) { }
        assertEquals(RadioFacts("hi"), cache.facts(track()))
        assertEquals(2, calls)
    }

    @Test fun metadata_concurrency_is_limited_to_three_including_parallel_candidate_batches() = runTest {
        var active = 0
        var maximum = 0
        val cache = CachedRadioFacts({ active++; maximum = maxOf(maximum, active); delay(10); active--; RadioFacts("hi") })
        (1..30).map { index -> async { cache.facts(track("%011d".format(index))) } }.awaitAll()
        assertEquals(3, maximum)
        assertEquals(0, active)
    }

    @Test fun memory_cache_is_bounded_and_evicted_tracks_can_be_loaded_again() = runTest {
        var calls = 0
        val cache = CachedRadioFacts({ calls++; RadioFacts("hi") })
        for (index in 1..193) cache.facts(track("%011d".format(index)))
        cache.facts(track("%011d".format(1)))
        assertEquals(194, calls)
    }
}
