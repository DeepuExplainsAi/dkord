package app.dkord.data.links

import java.net.URI
import java.net.URLDecoder
import java.util.Locale

const val MAX_YOUTUBE_LINK_LENGTH = 4096

enum class YouTubeLinkProblem { INVALID_LINK, PLAYLIST_ONLY, NETWORK, PRIVATE, AGE_RESTRICTED, GEO, BOT_CHECK, NO_AUDIO, UNAVAILABLE }

/** Only fixed, localized reasons reach the UI; never a pasted URL or an extractor response. */
class YouTubeLinkException(val problem: YouTubeLinkProblem) : Exception(problem.name)

/** A manually chosen video, not a search query, playlist, redirect or stream URL. */
class YouTubeVideoLink private constructor(val videoId: String) {
    val url: String get() = "https://www.youtube.com/watch?v=$videoId"

    companion object {
        private val videoIdPattern = Regex("[A-Za-z0-9_-]{11}")
        private val videoHosts = setOf("youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com")
        private val shortHosts = setOf("youtu.be", "www.youtu.be")
        private val embedHosts = setOf("youtube-nocookie.com", "www.youtube-nocookie.com")
        private fun invalid(): Nothing = throw YouTubeLinkException(YouTubeLinkProblem.INVALID_LINK)

        /** No network I/O. The original authority, tracking, timestamp and playlist are never forwarded. */
        fun parse(input: String): YouTubeVideoLink {
            val text = input.trim()
            if (text.isEmpty() || text.length > MAX_YOUTUBE_LINK_LENGTH ||
                text.any { it.isWhitespace() || it.code < 32 || it.code == 127 || it == '\\' }) invalid()
            val uri = try {
                URI(when {
                    text.startsWith("//") -> "https:$text"
                    "://" in text -> text
                    else -> "https://$text"
                })
            } catch (_: Exception) { invalid() }
            val scheme = uri.scheme?.lowercase(Locale.ROOT)
            val host = uri.host?.lowercase(Locale.ROOT) ?: invalid()
            if (scheme !in setOf("https", "http") || host !in videoHosts + shortHosts + embedHosts || uri.rawUserInfo != null) invalid()
            val authority = uri.rawAuthority.lowercase(Locale.ROOT)
            val defaultPort = if (scheme == "https") 443 else 80
            if (authority != host && authority != "$host:$defaultPort") invalid()
            val path = uri.rawPath.orEmpty().removeSuffix("/")
            val query = try {
                uri.rawQuery.orEmpty().split('&').filter { it.isNotEmpty() }.map { part ->
                    val pair = part.split('=', limit = 2)
                    URLDecoder.decode(pair[0], "UTF-8") to URLDecoder.decode(pair.getOrElse(1) { "" }, "UTF-8")
                }
            } catch (_: Exception) { invalid() }
            val ids = query.filter { it.first == "v" }.map { it.second }
            if (host in videoHosts && (path == "/playlist" ||
                    (path in setOf("", "/watch") && ids.isEmpty() && query.any { it.first == "list" && it.second.isNotEmpty() }))) {
                throw YouTubeLinkException(YouTubeLinkProblem.PLAYLIST_ONLY)
            }
            val id = when {
                host in shortHosts -> path.removePrefix("/")
                host in videoHosts && path == "/watch" -> ids.singleOrNull() ?: invalid()
                host in videoHosts -> Regex("^/(?:shorts|live|embed|v)/([A-Za-z0-9_-]{11})$").matchEntire(path)?.groupValues?.get(1)
                host in embedHosts -> Regex("^/embed/([A-Za-z0-9_-]{11})$").matchEntire(path)?.groupValues?.get(1)
                else -> null
            } ?: invalid()
            if (!videoIdPattern.matches(id)) invalid()
            return YouTubeVideoLink(id)
        }
    }
}
