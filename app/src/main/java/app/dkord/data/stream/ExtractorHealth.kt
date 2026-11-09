package app.dkord.data.stream

import app.dkord.core.DebugLog
import app.dkord.data.net.Http
import app.dkord.data.yt.lenientJson
import app.dkord.data.yt.at
import app.dkord.data.yt.str
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.Request

/** Playback health checks and local-only, redacted diagnostics. Never launches a browser. */
object ExtractorHealth {
    const val BUNDLED_VERSION = "v0.26.5"
    const val RELEASES_API = "https://api.github.com/repos/TeamNewPipe/NewPipeExtractor/releases/latest"

    /** Latest upstream tag, or null when offline. Dkord ships the extractor inside the APK, so "update" means a new app build. */
    suspend fun latestUpstream(): String? = withContext(Dispatchers.IO) {
        runCatching {
            Http.client.newCall(Request.Builder().url(RELEASES_API).header("Accept", "application/vnd.github+json").build())
                .execute().use { lenientJson.parseToJsonElement(it.body.string()).at("tag_name").str() }
        }.onFailure { DebugLog.w("health", "update check failed: ${it.message}") }.getOrNull()
    }

    private val address = Regex("https?://[^\\s<>]+", RegexOption.IGNORE_CASE)

    fun reportBody(deviceInfo: String): String =
        "dKORD playback diagnostics\nPlayback engine: $BUNDLED_VERSION\nDevice: $deviceInfo\n\n${address.replace(DebugLog.dump(), "[network address]").takeLast(6000)}"
}
