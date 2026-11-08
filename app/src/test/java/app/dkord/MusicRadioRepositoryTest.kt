package app.dkord

import app.dkord.MusicRadioParserTest.Companion.panel
import app.dkord.MusicRadioParserTest.Companion.row
import app.dkord.core.Track
import app.dkord.data.auth.CookieSource
import app.dkord.data.net.Http
import app.dkord.data.net.NewPipeDownloader
import app.dkord.data.yt.InnerTubeClient
import app.dkord.data.yt.MusicRepository
import app.dkord.data.yt.at
import app.dkord.data.yt.lenientJson
import app.dkord.data.yt.str
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.add
import kotlinx.serialization.json.put
import okhttp3.OkHttpClient
import okhttp3.Protocol
import okhttp3.Request
import okhttp3.Response
import okhttp3.ResponseBody.Companion.toResponseBody
import okio.Buffer
import org.junit.Test
import org.schabi.newpipe.extractor.NewPipe
import org.schabi.newpipe.extractor.downloader.Downloader
import java.io.IOException
import java.util.concurrent.atomic.AtomicInteger

class MusicRadioRepositoryTest {
    @Test
    fun next_is_music_radio_without_reading_a_cookie_source() = runBlocking {
        var captured: Request? = null
        client(buildJsonObject {}) { captured = it }.next("seed")
        val request = checkNotNull(captured)
        check(request.url.host == "music.youtube.com")
        check(request.url.encodedPath == "/youtubei/v1/next")
        check(request.header("Cookie") == null)
        check(request.header("Authorization") == null)
        check(request.header("X-Goog-AuthUser") == null)
        val buffer = Buffer()
        checkNotNull(request.body).writeTo(buffer)
        val payload = lenientJson.parseToJsonElement(buffer.readUtf8())
        check(payload.at("videoId").str() == "seed")
        check(payload.at("playlistId").str() == "RDAMVMseed")
        check(payload.at("params").str() == "wAEB")
        check(payload.at("isAudioOnly") == JsonPrimitive(true))
        check(payload.at("enablePersistentPlaylistPanel") == JsonPrimitive(true))
        check(payload.at("context", "client", "clientName").str() == "WEB_REMIX")
    }

    @Test
    fun radio_metadata_is_a_bounded_anonymous_player_request_not_a_private_context_payload() = runBlocking {
        var captured: Request? = null
        client(buildJsonObject {}) { captured = it }.radioMetadata("Abcdefghij1")
        val request = checkNotNull(captured)
        check(request.url.host == "music.youtube.com")
        check(request.url.encodedPath == "/youtubei/v1/player")
        for (header in listOf("Cookie", "Authorization", "X-Goog-AuthUser", "X-Goog-Visitor-Id")) check(request.header(header) == null)
        val buffer = Buffer()
        checkNotNull(request.body).writeTo(buffer)
        val payload = lenientJson.parseToJsonElement(buffer.readUtf8())
        check(payload.at("videoId").str() == "Abcdefghij1")
        check(payload.at("context", "client", "clientName").str() == "WEB_REMIX")
        check(payload.at("query") == null)
        check(payload.at("radioHint") == null)
    }

    @Test
    fun related_keeps_radio_order_and_filters_current_duplicates_and_duration() = runBlocking {
        val result = MusicRepository(client(panel(
            row("seed", title = "Song seed"),
            row("second", title = "Song second", duration = "1:00"),
            row("first", title = "Song first", duration = ""),
            row("second", title = "Song second"),
            row("short", title = "Song short", duration = "0:59"),
            row("long", title = "Song long", duration = "12:01"),
            row("vlog", "MUSIC_VIDEO_TYPE_UGC", title = "Song vlog"),
        ))).related(Track("seed", "Seed song", "Artist"))
        check(result.map { it.id } == listOf("second", "first"))
    }

    @Test
    fun seed_only_radio_still_attempts_songs_search() = runBlocking {
        assertSearchFallback(panel(row("seed")))
    }

    @Test
    fun no_usable_radio_songs_still_attempts_songs_search() = runBlocking {
        assertSearchFallback(panel(
            row("short", duration = "0:59"),
            row("long", duration = "12:01"),
            row("vlog", "MUSIC_VIDEO_TYPE_UGC"),
        ))
    }

    @Test
    fun repository_uses_actual_provider_metadata_to_keep_hindi_sad_radio_and_rank_relevant_hits() = runBlocking {
        val seedId = "seedvideo01"
        val tags = mapOf(seedId to listOf("hindi", "sad"), "hindiniche1" to listOf("hindi", "sad"),
            "hindihit001" to listOf("hindi", "sad"), "englishhit1" to listOf("english", "sad"),
            "hindiparty1" to listOf("hindi", "party"), "oldhindi001" to listOf("hindi", "sad", "old classics"))
        val metadataCalls = AtomicInteger()
        val http = OkHttpClient.Builder().addInterceptor { chain ->
            val request = chain.request()
            check(request.header("Cookie") == null && request.header("Authorization") == null)
            val body = Buffer().also { checkNotNull(request.body).writeTo(it) }.readUtf8()
            val video = lenientJson.parseToJsonElement(body).at("videoId").str()!!
            val response = if (request.url.encodedPath.endsWith("/next")) panel(
                row("hindiniche1", title = "First melody"), row("englishhit1", title = "Foreign melody"),
                row("hindihit001", title = "Another melody"), row("hindiparty1", title = "Dance melody"),
                row("oldhindi001", title = "Vintage melody"),
            ) else {
                check(request.url.encodedPath.endsWith("/player"))
                metadataCalls.incrementAndGet()
                buildJsonObject { put("videoDetails", buildJsonObject {
                    put("videoId", video)
                    put("viewCount", if (video == "hindiniche1") "100" else "100000000")
                    put("keywords", buildJsonArray { tags.getValue(video).forEach { add(it) } })
                }) }
            }
            Response.Builder().request(request).protocol(Protocol.HTTP_1_1).code(200).message("OK")
                .body(response.toString().toResponseBody(Http.JSON)).build()
        }.build()
        val repo = MusicRepository(InnerTubeClient(CookieSource { error("No cookie/session reads") }, http))
        val seed = Track(seedId, "Selected melody", "Singer", durationSec = 180)
        val result = repo.related(seed, listOf(seed), "latest hindi sad songs")
        check(result.map { it.id } == listOf("hindihit001", "hindiniche1"))
        check(metadataCalls.get() == 6)
    }

    private suspend fun assertSearchFallback(radio: JsonElement) {
        // The downloader deliberately fails: verify backup is attempted, without real networking.
        val previous = runCatching { NewPipe.getDownloader() }.getOrNull()
        val attempts = AtomicInteger()
        NewPipe.init(object : Downloader() {
            override fun execute(request: org.schabi.newpipe.extractor.downloader.Request): org.schabi.newpipe.extractor.downloader.Response {
                attempts.incrementAndGet()
                throw IOException("Intentional offline songs-search failure")
            }
        })
        try {
            val result = MusicRepository(client(radio)).related(Track("seed", "Seed song", "Artist"))
            check(attempts.get() > 0) { "Songs-search fallback was skipped after filtering the radio" }
            check(result.isEmpty())
        } finally {
            NewPipe.init(previous ?: NewPipeDownloader())
        }
    }

    private fun client(response: JsonElement, capture: (Request) -> Unit = {}): InnerTubeClient {
        val http = OkHttpClient.Builder().addInterceptor { chain ->
            val request = chain.request()
            capture(request)
            Response.Builder()
                .request(request)
                .protocol(Protocol.HTTP_1_1)
                .code(200)
                .message("OK")
                .body(response.toString().toResponseBody(Http.JSON))
                .build()
        }.build()
        return InnerTubeClient(CookieSource { error("Radio must not read a login/cookie session") }, http)
    }
}
