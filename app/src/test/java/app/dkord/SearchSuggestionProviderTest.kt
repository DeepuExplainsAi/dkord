package app.dkord

import app.dkord.data.auth.CookieSource
import app.dkord.data.yt.InnerTubeClient
import app.dkord.data.yt.MusicRepository
import kotlinx.coroutines.runBlocking
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.OkHttpClient
import org.junit.Assert.*
import org.junit.Test
import org.schabi.newpipe.extractor.NewPipe
import org.schabi.newpipe.extractor.downloader.Downloader
import org.schabi.newpipe.extractor.downloader.Request
import org.schabi.newpipe.extractor.downloader.Response
import org.schabi.newpipe.extractor.exceptions.ExtractionException
import org.schabi.newpipe.extractor.localization.ContentCountry
import org.schabi.newpipe.extractor.localization.Localization

/** Exercise the real NewPipe suggestion parser behind a deterministic, non-network downloader. */
class SearchSuggestionProviderTest {
    private class Provider(var contentType: String = "application/json") : Downloader() {
        val requests = mutableListOf<Request>()
        override fun execute(request: Request): Response {
            requests += request
            return Response(200, "OK", mapOf("Content-Type" to listOf(contentType)),
                """["query",[["sad love mashup 1 hour",0],["sad love mix",0],["अरिजीत मिक्स",0]]]""", request.url())
        }
    }
    private val repository get() = MusicRepository(InnerTubeClient(
        CookieSource { error("Search suggestions must not read credentials") },
        OkHttpClient.Builder().addInterceptor { error("Suggestions must not call the music browse API") }.build(),
    ))
    private fun <T> withProvider(provider: Provider, action: () -> T): T {
        val previous = NewPipe.getDownloader()
        val locale = NewPipe.getPreferredLocalization()
        val country = NewPipe.getPreferredContentCountry()
        NewPipe.init(provider, Localization("en", "IN"), ContentCountry("IN"))
        try { return action() }
        finally { NewPipe.init(previous, locale, country) }
    }

    @Test fun actual_youtube_provider_keeps_its_order_and_receives_the_exact_query_and_region() = withProvider(Provider()) {
        runBlocking {
            val query = "sad love + अरिजीत 1 hour"
            val suggestions = repository.suggestions(query)
            assertEquals(listOf("sad love mashup 1 hour", "sad love mix", "अरिजीत मिक्स"), suggestions)
            val request = checkNotNull(NewPipe.getDownloader() as? Provider).requests.single()
            val url = request.url().toHttpUrl()
            assertEquals("suggestqueries-clients6.youtube.com", url.host)
            assertEquals(query, url.queryParameter("q"))
            assertEquals("yt", url.queryParameter("ds"))
            assertEquals("IN", url.queryParameter("gl"))
            assertTrue(request.headers().keys.none { it.equals("Cookie", true) || it.equals("Authorization", true) })
        }
    }

    @Test fun a_bad_provider_response_is_an_error_not_an_empty_or_fabricated_success() = withProvider(Provider("text/html")) {
        runBlocking {
            try { repository.suggestions("any query"); fail("HTML suggestions accepted") }
            catch (_: ExtractionException) { }
        }
    }

    @Test fun blank_input_never_contacts_the_suggestion_provider() {
        val provider = Provider()
        withProvider(provider) {
            runBlocking { assertTrue(repository.suggestions(" \t").isEmpty()) }
            assertTrue(provider.requests.isEmpty())
        }
    }
}
