package app.dkord.data.yt

import app.dkord.core.Track
import java.text.Normalizer
import java.util.Locale
import kotlin.math.ln

/** Provider facts/linguistic hints, not a song/artist whitelist or fabricated original-song metadata. */
internal data class RadioFacts(
    val language: String? = null,
    val tags: List<String> = emptyList(),
    val views: Long = 0,
    /** Only an explicit title/album year hint; never equate a re-upload date with release year. */
    val yearHint: Int? = null,
)

internal enum class RadioMood(val query: String) {
    SAD("sad"), ROMANTIC("romantic"), CHILL("chill"), PARTY("party dance"),
    DEVOTIONAL("devotional"), WORKOUT("workout"), INSTRUMENTAL("instrumental"),
}

internal data class RadioTraits(
    val language: String? = null,
    val moods: Set<RadioMood> = emptySet(),
    val classic: Boolean = false,
    val year: Int? = null,
    val terms: Set<String> = emptySet(),
)

private val languageWords = linkedMapOf(
    "hi" to listOf("hindi", "bollywood", "हिंदी", "हिन्दी"),
    "en" to listOf("english", "अंग्रेजी", "अंग्रेज़ी"),
    "bho" to listOf("bhojpuri", "choliwood", "भोजपुरी", "छॉलीवुड"),
    "pa" to listOf("punjabi", "पंजाबी", "ਪੰਜਾਬੀ"),
    "ta" to listOf("tamil", "तमिल", "தமிழ்"),
    "te" to listOf("telugu", "तेलुगु", "తెలుగు"),
    "bn" to listOf("bengali", "bangla", "बंगाली", "বাংলা"),
    "mr" to listOf("marathi", "मराठी"),
    "es" to listOf("spanish", "español"),
    "ko" to listOf("korean", "한국어"),
)
private val moodWords = mapOf(
    RadioMood.SAD to listOf("sad", "heartbreak", "heartbroken", "breakup", "melancholy", "emotional", "दर्द", "दर्दभरे", "दर्द भरे", "उदास", "विरह"),
    RadioMood.ROMANTIC to listOf("romantic", "romance", "love", "प्यार", "प्रेम", "रोमांटिक"),
    RadioMood.CHILL to listOf("chill", "lofi", "lo fi", "relaxing", "soothing", "calm"),
    RadioMood.PARTY to listOf("party", "dance", "club", "upbeat", "happy", "पार्टी", "नाच"),
    RadioMood.DEVOTIONAL to listOf("devotional", "bhajan", "prayer", "aarti", "भजन", "आरती", "भक्ति"),
    RadioMood.WORKOUT to listOf("workout", "gym", "fitness", "वर्कआउट"),
    RadioMood.INSTRUMENTAL to listOf("instrumental", "karaoke", "no vocals", "वाद्य"),
)
private val genericTerms = setOf("music", "song", "songs", "video", "audio", "official", "new", "latest", "youtube", "subscribe", "channel", "full", "hd", "lyrics", "lyrical", "hit", "hits", "best", "popular", "trending", "गाना", "गाने", "the", "and", "for", "you", "with", "feat", "from")
private val classicWords = listOf("old hindi", "old songs", "old song", "old is gold", "oldies", "classic", "classics", "retro", "evergreen", "पुराने गाने", "पुराना गाना", "पुराने हिंदी", "सदाबहार")

private fun contextText(text: String) = Normalizer.normalize(text, Normalizer.Form.NFKC).lowercase(Locale.ROOT)
    .replace(Regex("[^\\p{L}\\p{M}\\p{N}]+"), " ").trim()
private fun mentions(text: String, words: List<String>) = words.any { " ${contextText(it)} " in " $text " }

/** Unknown Latin spelling is NOT assumed English: romanized Hindi must remain valid. */
internal fun radioTraits(track: Track, facts: RadioFacts = RadioFacts(), hint: String = ""): RadioTraits {
    val title = contextText("${track.title} ${track.album.orEmpty()}")
    val metadata = contextText(facts.tags.joinToString(" "))
    val intent = contextText(hint.take(200))
    fun language(text: String) = languageWords.filterValues { mentions(text, it) }.keys.singleOrNull()
    val nativeLanguage = facts.language?.substringBefore('-')?.substringBefore('_')?.lowercase(Locale.ROOT)?.takeIf { it.isNotBlank() && it != "und" }
    val lang = nativeLanguage ?: language(title) ?: language(metadata) ?: language(intent)
    fun moods(text: String) = moodWords.filterValues { mentions(text, it) }.keys
    // A deliberate shelf/search mood is useful when a song title carries no genre label.
    val metadataMoods = moods(metadata).takeUnless { values ->
        values.size > 2 || (RadioMood.SAD in values && values.any { it == RadioMood.PARTY || it == RadioMood.WORKOUT })
    }.orEmpty()
    val selectedMoods = moods(title).ifEmpty { metadataMoods }.ifEmpty { moods(intent) }
    fun readYear(text: String): Int? = if ("remaster" in text) null else
        Regex("(?:^| )((?:19|20)\\d{2})(?= |$)").find(text)?.groupValues?.get(1)?.toIntOrNull()
    val year = facts.yearHint ?: readYear(title) ?: readYear(intent)
    val descriptors = (languageWords.values.flatten() + moodWords.values.flatten() + classicWords)
        .flatMap { contextText(it).split(' ') }.toSet()
    val terms = metadata.split(' ').filter { it.length >= 3 && it !in genericTerms && it !in descriptors && it.any(Char::isLetter) }.take(48).toSet()
    return RadioTraits(lang, selectedMoods, mentions(title, classicWords) || mentions(intent, classicWords) || mentions(metadata, classicWords), year, terms)
}

/** Session context is private in-memory intent; it is never added to Track/room payloads. */
internal class RadioContextPolicy(
    private val seed: Track,
    private val target: RadioTraits,
    private val hint: String = "",
) {
    val constrained = target.language != null || target.moods.isNotEmpty() || target.classic || target.year != null || target.terms.isNotEmpty()

    fun score(track: Track, facts: RadioFacts, scopedSearch: Boolean, providerIndex: Int): Double? {
        val candidate = radioTraits(track, facts)
        if (target.language != null && candidate.language != null && target.language != candidate.language) return null
        val sameArtist = contextText(seed.artist).isNotBlank() && contextText(seed.artist) == contextText(track.artist)
        // Unknown language is not silently guessed from Latin title spelling.
        if (target.language != null && candidate.language == null && !scopedSearch && !sameArtist) return null
        if (!target.classic && candidate.classic) return null
        if (target.classic && !candidate.classic && !scopedSearch && candidate.year == null) return null
        if (target.year != null && candidate.year != null && kotlin.math.abs(target.year - candidate.year) > 20) return null
        val overlap = target.moods.intersect(candidate.moods)
        val energetic = setOf(RadioMood.PARTY, RadioMood.WORKOUT)
        if (RadioMood.SAD in target.moods && candidate.moods.any { it in energetic } && RadioMood.SAD !in candidate.moods) return null
        if (target.moods.any { it in energetic } && RadioMood.SAD in candidate.moods && candidate.moods.none { it in energetic }) return null
        if (RadioMood.DEVOTIONAL in target.moods && candidate.moods.isNotEmpty() && RadioMood.DEVOTIONAL !in candidate.moods) return null
        if (RadioMood.INSTRUMENTAL in target.moods && candidate.moods.isNotEmpty() && RadioMood.INSTRUMENTAL !in candidate.moods) return null
        val sharedTerms = target.terms.intersect(candidate.terms).size
        if (target.moods.isNotEmpty() && overlap.isEmpty() && !scopedSearch && !sameArtist && sharedTerms < 2 &&
            !(candidate.moods.isEmpty() && target.language != null && target.language == candidate.language)) return null
        if (!constrained) return -providerIndex.toDouble() // Preserve native radio order when evidence is unknown.
        val language = if (target.language != null && target.language == candidate.language) 40.0 else 0.0
        val mood = overlap.size * 35.0
        val artist = if (sameArtist) 4.0 else 0.0
        val popularity = if (facts.views > 0) ln(1.0 + facts.views.toDouble()).coerceAtMost(24.0) * 0.15 else 0.0
        return language + mood + artist + sharedTerms.coerceAtMost(5) * 8.0 + popularity - providerIndex * 0.25
    }

    fun fallbackQueries(): List<String> {
        val language = target.language?.let { languageWords[it]?.firstOrNull() ?: Locale.forLanguageTag(it).getDisplayLanguage(Locale.ENGLISH).ifBlank { it } }.orEmpty()
        val mood = target.moods.joinToString(" ") { it.query }
        val era = if (target.classic) "classic" else target.year?.let { "$it" }.orEmpty()
        // Retain arbitrary provider shelf/search style intent, not a list of supported genres.
        val requested = radioTraits(seed.copy(title = "", album = null), hint = hint)
        val conflicts = (target.language != null && requested.language != null && target.language != requested.language) ||
            (target.moods.isNotEmpty() && requested.moods.isNotEmpty() && target.moods.intersect(requested.moods).isEmpty()) ||
            (!target.classic && requested.classic)
        val styleIntent = if (conflicts) "" else contextText(hint.take(200)).take(120)
        val context = listOf(language, mood, era, styleIntent).filter { it.isNotBlank() }.distinct().joinToString(" ")
        if (context.isBlank()) {
            val anchor = "${seed.artist} ${seed.title}".trim()
            return listOf(anchor, "$anchor similar songs").filter { it.isNotBlank() }.distinct()
        }
        // No unconstrained artist-only fallback after a Hindi/sad/classic selection.
        return listOf("popular $context songs", "${seed.artist} $context songs".trim()).distinct()
    }
}
