package app.dkord.data.yt

import app.dkord.core.Track
import app.dkord.core.isLocalAudioId
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.Semaphore
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.sync.withPermit
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonPrimitive
import org.schabi.newpipe.extractor.services.youtube.YoutubeParsingHelper
import org.schabi.newpipe.extractor.stream.AudioTrackType
import java.util.Locale

internal fun interface RadioFactsSource { suspend fun facts(track: Track): RadioFacts }

/** Bounded memory/concurrency; short circuit after provider failure rather than a metadata storm. */
internal class CachedRadioFacts(
    private val load: suspend (Track) -> RadioFacts,
    private val now: () -> Long = { System.nanoTime() / 1_000_000 },
) : RadioFactsSource {
    private data class Entry(val facts: RadioFacts, val at: Long)
    private val cache = LinkedHashMap<String, Entry>()
    private val mutex = Mutex()
    private val fetches = Semaphore(3)
    private var blockedUntil = 0L

    override suspend fun facts(track: Track): RadioFacts {
        if (isLocalAudioId(track.id) || !Regex("[A-Za-z0-9_-]{11}").matches(track.id)) return RadioFacts()
        suspend fun cached(): RadioFacts? = mutex.withLock {
            cache[track.id]?.takeIf { now() - it.at in 0 until 6 * 60 * 60_000L }?.facts
                ?: RadioFacts().takeIf { now() < blockedUntil }
        }
        cached()?.let { return it }
        return fetches.withPermit {
            currentCoroutineContext().ensureActive()
            cached()?.let { return@withPermit it }
            val facts = try { load(track) }
            catch (e: CancellationException) { throw e }
            catch (_: Exception) {
                currentCoroutineContext().ensureActive()
                mutex.withLock { blockedUntil = now() + 15_000 }
                return@withPermit RadioFacts()
            }
            currentCoroutineContext().ensureActive()
            mutex.withLock {
                cache.remove(track.id)
                cache[track.id] = Entry(facts, now())
                while (cache.size > 192) cache.remove(cache.keys.first())
            }
            facts
        }
    }
}

/** Read provider facts only; never captions/UI locale, upload date or a dubbed default track. */
internal fun parseRadioFacts(root: JsonElement, expectedId: String): RadioFacts {
    val details = root.at("videoDetails")
    if (details.at("videoId").str() != expectedId) return RadioFacts()
    val formats = root.at("streamingData", "adaptiveFormats").list().filter {
        it.at("mimeType").str()?.startsWith("audio/") == true
    }.map { format ->
        val type = runCatching { YoutubeParsingHelper.extractAudioTrackType(format.at("xtags").str()) }.getOrNull()
        type to format.at("audioTrack", "id").str()?.substringBefore('.')?.let { Locale.forLanguageTag(it).language }
    }
    val original = formats.filter { it.first == AudioTrackType.ORIGINAL }
    val language = original.mapNotNull { it.second }.filter { it.isNotBlank() && it != "und" }.distinct().singleOrNull()
    val tags = details.at("keywords").list().mapNotNull { it.str()?.take(120) }.take(60)
    val views = (details.at("viewCount") as? JsonPrimitive)?.content?.toLongOrNull()?.coerceAtLeast(0) ?: 0
    return RadioFacts(language, tags, views)
}
