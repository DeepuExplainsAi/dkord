package app.dkord.data.links

import app.dkord.core.Track
import app.dkord.data.stream.StreamError
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.withContext
import org.schabi.newpipe.extractor.ServiceList
import org.schabi.newpipe.extractor.exceptions.AgeRestrictedContentException
import org.schabi.newpipe.extractor.exceptions.ContentNotAvailableException
import org.schabi.newpipe.extractor.exceptions.GeographicRestrictionException
import org.schabi.newpipe.extractor.exceptions.PrivateContentException
import org.schabi.newpipe.extractor.exceptions.ParsingException
import org.schabi.newpipe.extractor.exceptions.ReCaptchaException
import org.schabi.newpipe.extractor.exceptions.SignInConfirmNotBotException
import java.io.IOException

fun interface YouTubeLinkSource {
    suspend fun resolve(link: YouTubeVideoLink): Track
}

data class YouTubeLinkMetadata(
    val id: String,
    val title: String,
    val uploader: String,
    val durationSec: Long = 0,
    val thumbnail: String? = null,
)

/** Direct YouTube metadata, NOT YouTube Music search/radio. Streams still use the existing player. */
class NewPipeYouTubeLinkSource(
    private val extract: suspend (String) -> YouTubeLinkMetadata = { url ->
        withContext(Dispatchers.IO) {
            val extractor = ServiceList.YouTube.getStreamExtractor(url)
            extractor.fetchPage()
            currentCoroutineContext().ensureActive()
            // Optional metadata must not hide a real upload (e.g. a live stream without a duration).
            val uploader = try { extractor.uploaderName.orEmpty() } catch (_: ParsingException) { "" }
            val duration = try { extractor.length.coerceAtLeast(0) } catch (_: ParsingException) { 0L }
            val thumbnail = try { extractor.thumbnails.maxByOrNull { it.height }?.url } catch (_: ParsingException) { null }
            YouTubeLinkMetadata(extractor.id, extractor.name, uploader, duration, thumbnail)
        }
    },
) : YouTubeLinkSource {
    override suspend fun resolve(link: YouTubeVideoLink): Track = try {
        val metadata = extract(link.url)
        currentCoroutineContext().ensureActive()
        if (metadata.id != link.videoId || metadata.title.isBlank() || metadata.title.length > 2000 ||
            metadata.uploader.length > 2000 || metadata.durationSec < 0) {
            throw YouTubeLinkException(YouTubeLinkProblem.UNAVAILABLE)
        }
        // A flip, cover, short clip or long upload is an explicit user choice, not a radio candidate.
        Track(link.videoId, metadata.title, metadata.uploader, durationSec = metadata.durationSec, thumbnail = metadata.thumbnail)
    } catch (e: CancellationException) {
        throw e
    } catch (e: YouTubeLinkException) {
        throw e
    } catch (e: Exception) {
        throw YouTubeLinkException(youTubeLinkProblem(e))
    }
}

internal fun youTubeLinkProblem(error: Throwable): YouTubeLinkProblem = when (error) {
    is YouTubeLinkException -> error.problem
    is StreamError.BotCheck, is SignInConfirmNotBotException, is ReCaptchaException -> YouTubeLinkProblem.BOT_CHECK
    is StreamError.AgeRestricted, is AgeRestrictedContentException -> YouTubeLinkProblem.AGE_RESTRICTED
    is StreamError.Private, is PrivateContentException -> YouTubeLinkProblem.PRIVATE
    is StreamError.Geo, is GeographicRestrictionException -> YouTubeLinkProblem.GEO
    is StreamError.NoAudio -> YouTubeLinkProblem.NO_AUDIO
    is StreamError.Unavailable, is StreamError.MadeForKids, is ContentNotAvailableException -> YouTubeLinkProblem.UNAVAILABLE
    is IOException -> YouTubeLinkProblem.NETWORK
    else -> YouTubeLinkProblem.UNAVAILABLE
}
