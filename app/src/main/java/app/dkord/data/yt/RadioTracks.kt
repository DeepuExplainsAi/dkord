package app.dkord.data.yt

import app.dkord.core.isLocalAudioId

import app.dkord.core.Track
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import java.text.Normalizer
import java.util.Locale

internal const val MAX_AUTOPLAY_TRACKS = 15
private val versionWords = Regex("""\b(?:(?:super|ultra)\s+slowed|slowed(?:\s+down)?|reverb|sped\s+up|speed\s+up|nightcore|lo-?fi|remix|cover|instrumental|8d|bass\s+boosted|official|audio|video|lyrics?)\b""")
private val brackets = Regex("""[(\[].*?[)\]]""")
private val separators = Regex("""\s+(?:-|\|)\s+""")
private val nonTitle = Regex("""[^\p{L}\p{M}\p{N}]+""")
private val compilations = Regex("""\b(?:all|every)\s+versions?\b|\b(?:full|complete)\s+(?:album|discography)\b|\b\d+(?:\.\d+)?\s*(?:hours?|hrs?)\b""")

private fun foldedTitle(title: String) = Normalizer.normalize(title, Normalizer.Form.NFKC)
    .lowercase(Locale.ROOT).replace(Regex("[‐‑‒–—−]"), "-")

/** Radio-only identity. Manual search/queue actions may still select any version explicitly. */
internal fun songKey(title: String): String {
    val folded = foldedTitle(title)
    val parts = folded.replace(brackets, " ").split(separators).map { part ->
        part.replace(versionWords, " ").replace(nonTitle, " ").trim()
    }
    // "Artist - Song" and "Song - Slowed" must both retain the song, never an empty suffix.
    return parts.lastOrNull { it.isNotBlank() } ?: folded.replace(nonTitle, " ").trim()
}

/** Only automatic recommendations use these constraints; never mutate/filter the user's queue. */
internal class RadioTrackFilter(seed: Track, queue: List<Track>) {
    private val ids = (queue + seed).map { it.id }.toMutableSet()
    private val titles = (queue + seed).map { songKey(it.title) }.filter { it.isNotBlank() }.toMutableSet()

    fun accepts(track: Track): Boolean {
        val key = songKey(track.title)
        return track.id.isNotBlank() && track.title.isNotBlank() && key.isNotBlank() &&
            (track.durationSec == 0L || track.durationSec in 60..720) &&
            !compilations.containsMatchIn(foldedTitle(track.title)) &&
            track.id !in ids && key !in titles
    }

    fun select(candidates: List<Track>): List<Track> = candidates.filter { track ->
        accepts(track) && ids.add(track.id) && titles.add(songKey(track.title))
    }
}

/** Real anonymous music radio; bounded provider facts + context-scoped SONGS fallbacks. */
internal suspend fun musicRadioRecommendations(
    seed: Track,
    queue: List<Track>,
    fetchRadio: suspend () -> List<Track>,
    searchSongs: suspend (String) -> List<Track>,
    hint: String = "",
    factsSource: RadioFactsSource = RadioFactsSource { RadioFacts() },
): List<Track> {
    if (seed.id.isBlank() || isLocalAudioId(seed.id)) return emptyList()
    val filter = RadioTrackFilter(seed, queue)
    suspend fun facts(track: Track): RadioFacts {
        currentCoroutineContext().ensureActive()
        return try {
            factsSource.facts(track).also { currentCoroutineContext().ensureActive() }
        } catch (e: CancellationException) { throw e }
        catch (_: Exception) { currentCoroutineContext().ensureActive(); RadioFacts() }
    }
    val context = RadioContextPolicy(seed, radioTraits(seed, facts(seed), hint), hint)
    var profiled = 0
    suspend fun select(pool: List<Track>, scopedSearch: Boolean): List<Track> = coroutineScope {
        // Do not consume song identities before semantic filtering: a rejected English rendition
        // must not suppress a compatible Hindi rendition in a later pool.
        val eligible = pool.distinctBy { it.id }.filter(filter::accepts).take(minOf(18, 24 - profiled))
        val ranked = eligible.mapIndexed { index, track ->
            profiled++
            async {
                val score = context.score(track, facts(track), scopedSearch, index)
                score?.let { track to it }
            }
        }.awaitAll().filterNotNull().sortedByDescending { it.second }.map { it.first }
        filter.select(ranked).take(MAX_AUTOPLAY_TRACKS)
    }
    val radio = select(radioCandidates(fetchRadio), scopedSearch = false)
    if (radio.isNotEmpty()) return radio
    for (query in context.fallbackQueries()) {
        if (profiled >= 24) break // Never fill from uninspected candidates after exhausting the budget.
        val selected = select(radioCandidates { searchSongs(query) }, scopedSearch = true)
        if (selected.isNotEmpty()) return selected
    }
    return emptyList() // Safer than unrelated filler or the same song's other versions.
}

private suspend fun radioCandidates(fetch: suspend () -> List<Track>): List<Track> {
    currentCoroutineContext().ensureActive()
    return try {
        val tracks = fetch()
        // A blocking extractor/uncancellable transport may finish normally after cancellation.
        currentCoroutineContext().ensureActive()
        tracks
    } catch (e: CancellationException) {
        throw e
    } catch (_: Exception) {
        currentCoroutineContext().ensureActive()
        emptyList()
    }
}
