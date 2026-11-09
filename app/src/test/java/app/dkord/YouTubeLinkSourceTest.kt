package app.dkord

import app.dkord.data.links.*
import app.dkord.data.stream.StreamError
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.test.runTest
import org.junit.Assert.*
import org.junit.Test
import java.io.IOException

/** Real source adapter and identity/metadata/error policy with an injected, offline extractor. */
class YouTubeLinkSourceTest {
    private val link = YouTubeVideoLink.parse("https://youtu.be/AbCdEf012_-?si=not-forwarded&list=not-a-queue")

    @Test fun metadata_is_requested_by_canonical_id_without_a_music_search_or_category_gate() = runTest {
        val calls = mutableListOf<String>()
        val source = NewPipeYouTubeLinkSource { url ->
            calls += url
            YouTubeLinkMetadata(link.videoId, "Unlisted flip / instrumental cover — fixture", "Original uploader", 19)
        }
        val track = source.resolve(link)
        assertEquals(listOf(link.url), calls)
        assertEquals(link.videoId, track.id)
        assertEquals("Unlisted flip / instrumental cover — fixture", track.title)
        assertEquals("Original uploader", track.artist); assertEquals(19L, track.durationSec)
    }

    @Test fun explicit_long_uploads_and_unknown_duration_metadata_are_not_filtered_as_radio() = runTest {
        for (duration in listOf(0L, 2L, 7200L)) {
            val source = NewPipeYouTubeLinkSource { YouTubeLinkMetadata(link.videoId, "Rare upload", "", duration) }
            assertEquals(duration, source.resolve(link).durationSec)
        }
    }

    @Test fun no_title_search_substitute_or_empty_provider_metadata_can_be_shown_as_the_linked_video() = runTest {
        val invalid = listOf(
            YouTubeLinkMetadata("ZyXwVu987_-", "Wrong upload", "Uploader"),
            YouTubeLinkMetadata(link.videoId, " ", "Uploader"),
            YouTubeLinkMetadata(link.videoId, "Title", "Uploader", -1),
        )
        for (metadata in invalid) {
            val error = runCatching { NewPipeYouTubeLinkSource { metadata }.resolve(link) }.exceptionOrNull()
            assertEquals(YouTubeLinkProblem.UNAVAILABLE, (error as YouTubeLinkException).problem)
        }
    }

    @Test fun known_provider_restrictions_and_network_failures_are_fixed_localizable_reasons() = runTest {
        val errors = listOf(
            StreamError.Private() to YouTubeLinkProblem.PRIVATE,
            StreamError.AgeRestricted() to YouTubeLinkProblem.AGE_RESTRICTED,
            StreamError.Geo() to YouTubeLinkProblem.GEO,
            StreamError.BotCheck() to YouTubeLinkProblem.BOT_CHECK,
            StreamError.NoAudio() to YouTubeLinkProblem.NO_AUDIO,
            StreamError.Unavailable("secret https://provider.test/?token=hidden") to YouTubeLinkProblem.UNAVAILABLE,
            IOException("secret https://provider.test/?token=hidden") to YouTubeLinkProblem.NETWORK,
        )
        for ((error, expected) in errors) {
            val failure = runCatching { NewPipeYouTubeLinkSource { throw error }.resolve(link) }.exceptionOrNull() as YouTubeLinkException
            assertEquals(expected, failure.problem); assertFalse(failure.message.orEmpty().contains("secret"))
        }
    }

    @Test fun cancellation_is_not_misreported_as_an_unavailable_video() = runTest {
        val cancelled = CancellationException("leaving page")
        val failure = runCatching { NewPipeYouTubeLinkSource { throw cancelled }.resolve(link) }.exceptionOrNull()
        assertSame(cancelled, failure)
    }
}
