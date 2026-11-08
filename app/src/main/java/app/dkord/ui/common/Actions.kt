package app.dkord.ui.common

import app.dkord.core.Track
import app.dkord.data.download.DownloadManager
import app.dkord.data.library.LibraryRepository
import app.dkord.player.PlayerController
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import java.util.UUID

/** One place for "do something with a track" so every screen's menu behaves the same. Runs in an app-lifetime scope. */
class Actions(val player: PlayerController, val library: LibraryRepository, val downloads: DownloadManager) {
    val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)

    fun like(t: Track, liked: Boolean) { scope.launch { library.setLiked(t, liked) } }
    private val mutableDownloadRequest = MutableStateFlow<DownloadRequest?>(null)
    val downloadRequest = mutableDownloadRequest.asStateFlow()
    fun download(tracks: List<Track>) {
        val chosen = tracks.distinctBy { it.id }.filterNot { app.dkord.core.isLocalAudioId(it.id) }
        if (chosen.isNotEmpty()) mutableDownloadRequest.value = DownloadRequest(UUID.randomUUID().toString(), chosen)
    }
    fun dismissDownload(id: String) {
        mutableDownloadRequest.compareAndSet(mutableDownloadRequest.value?.takeIf { it.id == id }, null)
    }
    fun addToPlaylist(id: Long, tracks: List<Track>, done: (Int) -> Unit = {}) { scope.launch { done(library.add(id, tracks)) } }
    fun createPlaylist(name: String, tracks: List<Track> = emptyList(), done: (Long) -> Unit = {}) {
        scope.launch { val id = library.create(name); if (tracks.isNotEmpty()) library.add(id, tracks); done(id) }
    }
}

data class DownloadRequest(val id: String, val tracks: List<Track>)
