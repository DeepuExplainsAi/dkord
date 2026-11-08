package app.dkord.data.studio

import app.dkord.core.Track
import app.dkord.core.isLocalAudioId
import app.dkord.data.download.TrackDownloader
import app.dkord.data.stream.AudioQuality

internal data class StudioPreparation(val bytes: Long, val total: Long) {
    val fraction: Float? get() = total.takeIf { it > 0 }?.let { (bytes.toFloat() / it).coerceIn(0f, 1f) }
}

/** Fetches a user-selected accessible audio source only into a private project staging lease. */
internal class StudioOnlineImporter(
    private val repo: StudioRepository,
    private val downloader: TrackDownloader,
    private val quality: () -> AudioQuality,
) {
    suspend fun import(projectId: String, track: Track, progress: (StudioPreparation) -> Unit = {}) {
        require(!isLocalAudioId(track.id) && Regex("[A-Za-z0-9_-]{11}").matches(track.id))
        repo.importPreparedAudio(projectId, track.title) { file ->
            downloader.fetch(track.id, quality(), file, null) { bytes, total, _ ->
                require(bytes <= MAX_BYTES && total <= MAX_BYTES) { "Source exceeds the private preparation limit" }
                progress(StudioPreparation(bytes, total))
            }
        }
    }
    companion object { const val MAX_BYTES = 512L * 1024 * 1024 }
}
