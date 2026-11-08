package app.dkord.core

import java.text.Normalizer
import java.time.Instant
import java.time.ZoneId
import java.util.Locale

/** Real on-device play history, not recommendations or inferred listening statistics. */
data class ListeningEntry(val track: Track, val playedAtMs: Long)

enum class ListeningFilter { ALL, LIKED, DOWNLOADED }
internal enum class ListeningDay { TODAY, YESTERDAY, EARLIER }

internal fun listeningHistory(
    entries: List<ListeningEntry>,
    query: String,
    filter: ListeningFilter,
    likedIds: Set<String>,
    downloadedIds: Set<String>,
): List<ListeningEntry> {
    val words = historyText(query).split(Regex("[\\s\\p{Z}]+")).filter { it.isNotBlank() }
    return entries.sortedWith(compareByDescending<ListeningEntry> { it.playedAtMs }.thenBy { it.track.id })
        .filter { it.track.id.isNotBlank() && it.track.title.isNotBlank() }.distinctBy { it.track.id }
        .filter { entry ->
            val allowed = when (filter) {
                ListeningFilter.ALL -> true
                ListeningFilter.LIKED -> entry.track.id in likedIds
                ListeningFilter.DOWNLOADED -> entry.track.id in downloadedIds
            }
            val text = historyText("${entry.track.title} ${entry.track.artist} ${entry.track.album.orEmpty()}")
            allowed && words.all(text::contains)
        }
}

private fun historyText(text: String) = Normalizer.normalize(text, Normalizer.Form.NFKC).lowercase(Locale.ROOT).trim()

/** Calendar dates, not an inaccurate 24-hour subtraction across daylight-saving changes. */
internal fun listeningDay(playedAtMs: Long, nowMs: Long, zone: ZoneId): ListeningDay {
    val date = Instant.ofEpochMilli(playedAtMs).atZone(zone).toLocalDate()
    val today = Instant.ofEpochMilli(nowMs).atZone(zone).toLocalDate()
    return when (date) {
        today -> ListeningDay.TODAY
        today.minusDays(1) -> ListeningDay.YESTERDAY
        else -> ListeningDay.EARLIER
    }
}

internal fun listeningProgress(positionMs: Long, durationMs: Long): Float =
    if (durationMs <= 0) 0f else (positionMs.coerceAtLeast(0).toDouble() / durationMs).coerceIn(0.0, 1.0).toFloat()
