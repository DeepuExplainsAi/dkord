package app.dkord.data.yt

import app.dkord.core.isLocalAudioId

import app.dkord.core.Track
import kotlinx.coroutines.CancellationException
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

    fun select(candidates: List<Track>): List<Track> = candidates.filter { track ->
        val key = songKey(track.title)
        track.id.isNotBlank() && track.title.isNotBlank() && key.isNotBlank() &&
            (track.durationSec == 0L || track.durationSec in 60..720) &&
            !compilations.containsMatchIn(foldedTitle(track.title)) &&
            track.id !in ids && key !in titles && ids.add(track.id) && titles.add(key)
    }
}

/** Real anonymous music radio first; music-only fallbacks, never arbitrary videos/long-mix queries. */
internal suspend fun musicRadioRecommendations(
    seed: Track,
    queue: List<Track>,
    fetchRadio: suspend () -> List<Track>,
    searchSongs: suspend (String) -> List<Track>,
): List<Track> {
    if (seed.id.isBlank() || isLocalAudioId(seed.id)) return emptyList()
    val filter = RadioTrackFilter(seed, queue)
    val radio = filter.select(radioCandidates(fetchRadio))
    if (radio.isNotEmpty()) return radio
    val query = "${seed.artist} ${seed.title}".trim()
    val matching = if (query.isBlank()) emptyList() else filter.select(radioCandidates { searchSongs(query) })
    if (matching.isNotEmpty()) return matching
    // If title search only returned versions of the seed, ask for other songs by its creator.
    val artist = seed.artist.trim()
    return if (artist.isNotBlank() && artist != query) filter.select(radioCandidates { searchSongs(artist) }) else emptyList()
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
