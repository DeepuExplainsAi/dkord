package app.dkord.ui.studio

import android.net.Uri
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import app.dkord.R
import app.dkord.core.Track
import app.dkord.core.isLocalAudioId
import app.dkord.data.download.DownloadManager
import app.dkord.data.studio.StudioProject
import app.dkord.data.studio.StudioRepository
import app.dkord.data.studio.StudioOnlineImporter
import app.dkord.data.studio.StudioPreparation
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.launch
import java.io.FileNotFoundException

internal class StudioViewModel(val repo: StudioRepository, private val downloads: DownloadManager, private val online: StudioOnlineImporter) : ViewModel() {
    val busy = MutableStateFlow(false)
    val importing = MutableStateFlow(false)
    val preparation = MutableStateFlow<StudioPreparation?>(null)
    val messages = MutableSharedFlow<Int>(extraBufferCapacity = 4)
    private var operation: Job? = null
    private fun run(error: Int = R.string.studio_write_failed, block: suspend () -> Unit) {
        if (operation?.isActive == true) return
        operation = viewModelScope.launch {
            busy.value = true
            try { block() }
            catch (e: CancellationException) { throw e }
            catch (_: Exception) { messages.emit(error) }
            finally { importing.value = false; preparation.value = null; busy.value = false }
        }
    }
    fun create(name: String, selected: (String) -> Unit) = run { selected(repo.create(name)) }
    fun change(id: String, transform: (StudioProject) -> StudioProject) = run { repo.change(id, transform) }
    fun delete(id: String, done: () -> Unit) = run { repo.delete(id); done() }
    fun importAudio(id: String, uris: List<Uri>) = run(R.string.studio_import_failed) {
        importing.value = true
        uris.forEach { repo.importAudio(id, it) }
    }
    fun importDownload(id: String, track: Track) = run(R.string.studio_import_failed) {
        importing.value = true
        val uri = downloads.localUri(track.id) ?: throw FileNotFoundException()
        repo.importAudio(id, Uri.parse(uri), track.title)
    }
    fun useTrack(id: String, track: Track) = run(R.string.studio_import_failed) {
        importing.value = true
        val uri = downloads.localUri(track.id)
        if (uri != null) {
            repo.importAudio(id, Uri.parse(uri), track.title)
        } else {
            if (isLocalAudioId(track.id)) throw FileNotFoundException()
            preparation.value = StudioPreparation(0, 0)
            online.import(id, track) { preparation.value = it }
        }
    }
    fun export(id: String) = run(R.string.studio_export_failed) { repo.export(id) }
    fun cancelImport() { if (importing.value) operation?.cancel() }
    fun copyOutput(id: String, destination: Uri) = run(R.string.studio_copy_failed) {
        val uri = downloads.localUri(id) ?: throw FileNotFoundException()
        repo.copyAudio(Uri.parse(uri), destination)
        messages.emit(R.string.studio_copy_saved)
    }
}
