package app.dkord.data.studio

import app.dkord.core.Track
import kotlinx.serialization.Serializable
import java.util.Locale
import java.util.UUID

internal fun studioId(): String = UUID.randomUUID().toString()
private val uuid = Regex("[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}")

@Serializable
internal data class StudioSource(val id: String, val title: String, val fileName: String, val durationMs: Long, val mime: String)
@Serializable
internal data class StudioClip(val id: String, val sourceId: String, val startMs: Long, val endMs: Long) {
    val durationMs get() = Math.subtractExact(endMs, startMs)
}
@Serializable
internal data class StudioProject(
    val id: String, val name: String, val sources: List<StudioSource> = emptyList(),
    val clips: List<StudioClip> = emptyList(), val updatedAt: Long = 0, val lastExport: Track? = null, val lastRequestId: String? = null,
) {
    val durationMs: Long get() = clips.fold(0L) { total, clip -> Math.addExact(total, clip.durationMs) }
    fun validate(requireClips: Boolean = false): StudioProject {
        require(uuid.matches(id) && name.isNotBlank() && name.length <= 160)
        require(lastRequestId == null || uuid.matches(lastRequestId))
        require(lastExport == null || app.dkord.core.isLocalAudioId(lastExport.id))
        require(sources.map { it.id }.distinct().size == sources.size)
        require(clips.map { it.id }.distinct().size == clips.size)
        sources.forEach { require(uuid.matches(it.id) && it.fileName == "${it.id}.audio" && it.durationMs > 0 && it.title.isNotBlank()) }
        val indexed = sources.associateBy { it.id }
        clips.forEach {
            val source = requireNotNull(indexed[it.sourceId])
            require(uuid.matches(it.id) && it.startMs >= 0 && it.endMs > it.startMs && it.endMs <= source.durationMs)
        }
        require(!requireClips || clips.isNotEmpty())
        require(durationMs >= 0)
        return this
    }
    fun withClip(sourceId: String, startMs: Long, endMs: Long, clipId: String = studioId()): StudioProject {
        val edited = StudioClip(clipId, sourceId, startMs, endMs)
        return copy(clips = if (clips.any { it.id == clipId }) clips.map { if (it.id == clipId) edited else it } else clips + edited).validate()
    }
    fun moveClip(id: String, delta: Int): StudioProject {
        val from = clips.indexOfFirst { it.id == id }
        val to = (from + delta).coerceIn(0, (clips.size - 1).coerceAtLeast(0))
        if (from < 0 || from == to) return this
        val result = clips.toMutableList(); result.add(to, result.removeAt(from))
        return copy(clips = result).validate()
    }
}

/** Seconds, mm:ss or hh:mm:ss, optionally .SSS; no arbitrary fixed clip/song duration limit. */
internal fun parseStudioTime(input: String): Long? = try {
    val parts = input.trim().split(':')
    if (parts.size !in 1..3 || parts.any { it.isBlank() } || parts.dropLast(1).any { !Regex("[0-9]+").matches(it) }) null else {
        val last = parts.last()
        if (!Regex("[0-9]+(?:\\.[0-9]{1,3})?").matches(last)) null else {
            val seconds = last.substringBefore('.').toLongOrNull()
            val minutes = if (parts.size >= 2) parts[parts.lastIndex - 1].toLongOrNull() else 0L
            val hours = if (parts.size == 3) parts[0].toLongOrNull() else 0L
            val fraction = if ('.' in last) last.substringAfter('.').padEnd(3, '0').toLong() else 0L
            if (seconds == null || minutes == null || hours == null || minutes < 0 || hours < 0 ||
                (parts.size >= 2 && seconds >= 60) || (parts.size == 3 && minutes >= 60)) null
            else Math.addExact(Math.multiplyExact(Math.addExact(Math.multiplyExact(hours, 3600), Math.addExact(Math.multiplyExact(minutes, 60), seconds)), 1000), fraction)
        }
    }
} catch (_: ArithmeticException) { null }

internal fun studioTime(ms: Long): String = String.format(Locale.ROOT, "%d:%02d:%02d.%03d", ms / 3_600_000, ms / 60_000 % 60, ms / 1000 % 60, ms % 1000)
