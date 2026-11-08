package app.dkord

import app.dkord.core.Track
import app.dkord.data.yt.RadioContextPolicy
import app.dkord.data.yt.RadioFacts
import app.dkord.data.yt.RadioFactsSource
import app.dkord.data.yt.RadioMood
import app.dkord.data.yt.musicRadioRecommendations
import app.dkord.data.yt.radioTraits
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.withContext
import org.junit.Assert.*
import org.junit.Test
import java.io.IOException

@OptIn(ExperimentalCoroutinesApi::class)
class RadioContextTest {
    private val seed = Track("seed", "Quiet Rain", "Singer", durationSec = 200)
    private fun song(id: String, title: String = "Track $id", artist: String = "Other") = Track(id, title, artist, durationSec = 180)
    private fun policy(facts: RadioFacts = RadioFacts("hi", listOf("sad")), hint: String = "") =
        RadioContextPolicy(seed, radioTraits(seed, facts, hint), hint)
    private fun score(facts: RadioFacts, title: String = "A different song", scoped: Boolean = false) =
        policy().score(song("other", title), facts, scoped, 0)

    @Test fun romanized_titles_are_not_assumed_english_and_unknown_language_stays_unknown() {
        assertNull(radioTraits(song("id", "Tum Mere Saath")).language)
        assertNull(radioTraits(song("id", "A Quiet Evening")).language)
        assertEquals("hi", radioTraits(seed, hint = "हिंदी दर्द भरे गाने").language)
        assertEquals(setOf(RadioMood.SAD), radioTraits(seed, hint = "हिंदी दर्द भरे गाने").moods)
    }

    @Test fun original_audio_language_and_song_metadata_override_a_broad_search_hint() {
        val traits = radioTraits(seed, RadioFacts("en-US", listOf("party")), "hindi sad songs")
        assertEquals("en", traits.language)
        assertEquals(setOf(RadioMood.PARTY), traits.moods)
        val queries = RadioContextPolicy(seed, traits, "hindi sad songs").fallbackQueries()
        assertTrue(queries.all { "english" in it && "party" in it && "hindi" !in it && "sad" !in it })
    }

    @Test fun language_conflict_is_rejected_even_for_a_hugely_popular_song_or_scoped_search() {
        assertNull(score(RadioFacts("en", listOf("sad"), Long.MAX_VALUE)))
        assertNull(score(RadioFacts("en", listOf("sad"), Long.MAX_VALUE), scoped = true))
        assertNotNull(score(RadioFacts("hi", listOf("sad"), 10)))
    }

    @Test fun sad_does_not_turn_into_party_workout_or_happy_even_in_music_fallback() {
        for (mood in listOf("party", "workout", "happy dance")) {
            assertNull(score(RadioFacts("hi", listOf(mood)), scoped = true))
        }
        assertNotNull(score(RadioFacts("hi", listOf("sad romantic"))))
    }

    @Test fun party_does_not_become_sad_and_devotional_or_instrumental_intent_is_respected() {
        for ((hint, wrong) in listOf("hindi party" to "sad", "hindi devotional" to "party", "hindi instrumental" to "party")) {
            val p = policy(RadioFacts(), hint)
            assertNull(p.score(song("other"), RadioFacts("hi", listOf(wrong)), true, 0))
        }
    }

    @Test fun known_language_with_unknown_mood_can_retain_native_music_radio_evidence() {
        assertNotNull(score(RadioFacts("hi")))
        assertNull(score(RadioFacts())) // Unknown language from unrelated uploader is not guessed Hindi.
        assertNotNull(score(RadioFacts(), scoped = true)) // Hindi/sad SONGS query is additional provider evidence.
    }

    @Test fun a_same_artist_unknown_profile_does_not_override_a_known_conflict() {
        val p = policy()
        assertNotNull(p.score(song("same", artist = seed.artist), RadioFacts(), false, 0))
        assertNull(p.score(song("same", artist = seed.artist), RadioFacts("en", listOf("party")), false, 0))
    }

    @Test fun contemporary_selection_rejects_explicit_retro_and_distant_known_song_years() {
        assertNull(score(RadioFacts("hi", listOf("sad", "old classics"))))
        val p = policy(RadioFacts("hi", listOf("sad"), yearHint = 2021))
        assertNull(p.score(song("old"), RadioFacts("hi", listOf("sad"), yearHint = 1965), false, 0))
        assertNotNull(p.score(song("near"), RadioFacts("hi", listOf("sad"), yearHint = 2019), false, 0))
    }

    @Test fun deliberate_classics_selection_is_not_forced_into_modern_pop() {
        val p = policy(RadioFacts("hi", listOf("sad"), yearHint = 1965), "old hindi classics")
        assertNotNull(p.score(song("old"), RadioFacts("hi", listOf("sad", "classic"), yearHint = 1968), false, 0))
        assertNull(p.score(song("modern"), RadioFacts("hi", listOf("sad"), yearHint = 2023), false, 0))
        assertTrue(p.fallbackQueries().all { "hindi" in it && "classic" in it })
    }

    @Test fun remaster_year_is_not_claimed_as_original_song_release_year() {
        assertNull(radioTraits(song("id", "A Song Remastered 2025")).year)
        assertEquals(2019, radioTraits(song("id", "A Song 2019")).year)
    }

    @Test fun relevant_real_view_counts_rank_popular_songs_after_semantic_compatibility() = runTest {
        val tracks = listOf(song("niche"), song("hit"), song("english"))
        val result = musicRadioRecommendations(seed, listOf(seed), { tracks }, { emptyList() },
            factsSource = RadioFactsSource { track -> when (track.id) {
                "seed" -> RadioFacts("hi", listOf("sad"))
                "niche" -> RadioFacts("hi", listOf("sad"), 100)
                "hit" -> RadioFacts("hi", listOf("sad"), 100_000_000)
                else -> RadioFacts("en", listOf("party"), Long.MAX_VALUE)
            } })
        assertEquals(listOf("hit", "niche"), result.map { it.id })
    }

    @Test fun matching_provider_style_terms_outrank_an_unrelated_popularity_advantage() {
        val p = policy(RadioFacts("hi", listOf("ambient", "synthpop")))
        val close = p.score(song("close"), RadioFacts("hi", listOf("ambient", "synthpop"), 10), false, 1)!!
        val different = p.score(song("different"), RadioFacts("hi", listOf("metal"), 100_000_000), false, 0)!!
        assertTrue(close > different)
    }

    @Test fun unknown_facts_preserve_provider_order_instead_of_inventing_popularity_or_genres() = runTest {
        val tracks = listOf(song("first"), song("second"))
        val result = musicRadioRecommendations(seed, emptyList(), { tracks }, { emptyList() })
        assertEquals(tracks, result)
        assertTrue(policy(RadioFacts()).fallbackQueries().none { it == seed.artist })
    }

    @Test fun fallback_queries_keep_language_mood_and_arbitrary_style_intent_not_artist_only() = runTest {
        val queries = mutableListOf<String>()
        val result = musicRadioRecommendations(seed, listOf(seed), { listOf(song("unverified")) }, { query ->
            queries += query
            if (queries.size == 1) emptyList() else listOf(song("fresh"))
        }, hint = "hindi sad ambient music", factsSource = RadioFactsSource { RadioFacts() })
        assertEquals(listOf("fresh"), result.map { it.id })
        assertEquals(2, queries.size)
        assertTrue(queries.all { "hindi" in it && "sad" in it && "ambient" in it && it != seed.artist })
    }

    @Test fun rejecting_a_wrong_language_does_not_poison_the_base_song_identity_for_fallback() = runTest {
        val result = musicRadioRecommendations(seed, listOf(seed), { listOf(song("wrong", "Another Melody")) },
            { listOf(song("right", "Another Melody")) }, hint = "hindi sad",
            factsSource = RadioFactsSource { if (it.id == "wrong") RadioFacts("en") else RadioFacts("hi", listOf("sad")) })
        assertEquals(listOf("right"), result.map { it.id })
    }

    @Test fun contextual_ranking_keeps_every_existing_seed_version_mix_and_queue_repeat_exclusion() = runTest {
        val queued = song("queued", "Already Heard")
        val result = musicRadioRecommendations(seed, listOf(seed, queued), { listOf(
            song("variant", "Quiet Rain (Slowed)"), song("cover", "Already Heard (Cover)"),
            song("mix", "A full album"), song("fresh"), song("duplicate", "Track fresh (Remix)"),
        ) }, { emptyList() }, factsSource = RadioFactsSource { RadioFacts("hi", listOf("sad"), 1000) })
        assertEquals(listOf("fresh"), result.map { it.id })
    }

    @Test fun metadata_failure_never_creates_tracks_and_fallback_is_still_music_context_scoped() = runTest {
        val queries = mutableListOf<String>()
        val result = musicRadioRecommendations(seed, emptyList(), { emptyList() }, { queries += it; emptyList() },
            hint = "hindi sad", factsSource = RadioFactsSource { throw IOException("offline") })
        assertTrue(result.isEmpty())
        assertTrue(queries.all { "hindi" in it && "sad" in it })
    }

    @Test fun cancelled_uncancellable_metadata_cannot_launch_radio_or_fallback_after_return() = runTest {
        var radio = false
        var search = false
        val job = backgroundScope.launch {
            musicRadioRecommendations(seed, emptyList(), { radio = true; emptyList() }, { search = true; emptyList() },
                factsSource = RadioFactsSource { withContext(NonCancellable) { delay(100) }; RadioFacts("hi") })
        }
        runCurrent(); job.cancel(); advanceTimeBy(100); runCurrent()
        assertFalse(radio); assertFalse(search); assertTrue(job.isCancelled)
    }

    @Test fun candidate_inspection_and_returned_batch_are_bounded() = runTest {
        var profiled = 0
        val result = musicRadioRecommendations(seed, emptyList(), { (1..1000).map { song("song$it") } }, { emptyList() },
            factsSource = RadioFactsSource { profiled++; RadioFacts("hi", listOf("sad")) })
        assertEquals(15, result.size)
        assertTrue(profiled <= 25)
    }
}
