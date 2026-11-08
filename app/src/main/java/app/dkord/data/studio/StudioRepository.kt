package app.dkord.data.studio

import android.content.Context
import android.media.MediaExtractor
import android.media.MediaFormat
import android.media.MediaMetadataRetriever
import android.net.Uri
import android.provider.OpenableColumns
import android.util.AtomicFile
import androidx.work.ExistingWorkPolicy
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.workDataOf
import app.dkord.R
import app.dkord.core.Track
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import java.io.File
import java.util.UUID
import java.util.concurrent.ConcurrentHashMap

@Serializable
private data class StudioCatalog(val version: Int = 1, val projects: List<StudioProject> = emptyList())
@Serializable
internal data class StudioRenderRequest(val id: String, val project: StudioProject)
internal data class StudioLibrary(val loading: Boolean = true, val failed: Boolean = false, val projects: List<StudioProject> = emptyList())

/** Private, atomic project metadata and durable source copies; never stores provider URLs/credentials. */
internal class StudioRepository(private val context: Context) {
    val root = File(context.filesDir, "studio").apply { mkdirs() }
    private val sources = File(root, "sources").apply { mkdirs() }
    private val requests = File(root, "requests").apply { mkdirs() }
    val temporary = File(root, "temp").apply { mkdirs() }
    private val catalog = AtomicFile(File(root, "projects.json"))
    private val json = Json { ignoreUnknownKeys = true }
    private val mutex = Mutex()
    private val pendingImports = ConcurrentHashMap.newKeySet<String>()
    private val pendingCopies = ConcurrentHashMap.newKeySet<String>()
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val mutable = MutableStateFlow(StudioLibrary())
    val state: StateFlow<StudioLibrary> = mutable
    val work: WorkManager = WorkManager.getInstance(context)

    init { reload() }
    fun reload() { scope.launch { mutex.withLock {
        mutable.value = mutable.value.copy(loading = true, failed = false)
        try {
            val stored = if (catalog.baseFile.exists() || File(catalog.baseFile.path + ".bak").exists())
                json.decodeFromString<StudioCatalog>(catalog.readFully().decodeToString()) else StudioCatalog()
            require(stored.version == 1 && stored.projects.map { it.id }.distinct().size == stored.projects.size)
            stored.projects.forEach { it.validate() }
            mutable.value = StudioLibrary(loading = false, projects = stored.projects)
            cleanFinishedRequests()
        } catch (e: CancellationException) { throw e }
        catch (_: Exception) { mutable.value = mutable.value.copy(loading = false, failed = true) }
    } } }

    private fun write(file: AtomicFile, text: String) {
        val stream = file.startWrite()
        try { stream.write(text.toByteArray()); file.finishWrite(stream) }
        catch (e: Throwable) { file.failWrite(stream); throw e }
    }
    private fun persist(projects: List<StudioProject>) {
        write(catalog, json.encodeToString(StudioCatalog(projects = projects)))
        mutable.value = StudioLibrary(loading = false, projects = projects.sortedByDescending { it.updatedAt })
    }
    private fun ready() { check(!mutable.value.loading && !mutable.value.failed) }
    suspend fun create(name: String): String = withContext(Dispatchers.IO) { mutex.withLock {
        ready()
        val p = StudioProject(studioId(), name.trim().take(160), updatedAt = System.currentTimeMillis()).validate()
        persist(listOf(p) + mutable.value.projects); p.id
    } }
    suspend fun change(id: String, transform: (StudioProject) -> StudioProject) = withContext(Dispatchers.IO) { mutex.withLock {
        ready()
        val current = mutable.value.projects.first { it.id == id }
        val changed = transform(current).copy(updatedAt = System.currentTimeMillis()).validate()
        require(changed.id == id)
        persist(mutable.value.projects.map { if (it.id == id) changed else it })
        runCatching { cleanUnreferencedSources() }
    } }
    suspend fun delete(id: String) = withContext(Dispatchers.IO) { mutex.withLock {
        ready(); persist(mutable.value.projects.filterNot { it.id == id }); cleanUnreferencedSources()
    } }

    /** Copy while the picker grant is valid. Editing never modifies/deletes the user's original. */
    suspend fun importAudio(projectId: String, uri: Uri, displayName: String? = null) = withContext(Dispatchers.IO) {
        val id = studioId(); val file = File(temporary, "$id.import")
        var committed = false
        pendingImports.add(file.name)
        try {
            val name = displayName?.takeIf { it.isNotBlank() } ?: runCatching {
                context.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { cursor ->
                    if (cursor.moveToFirst()) cursor.getString(0) else null
                }
            }.getOrNull()?.takeIf { it.isNotBlank() } ?: context.getString(R.string.studio_audio_source)
            context.contentResolver.openInputStream(uri).use { input ->
                requireNotNull(input)
                file.outputStream().use { output ->
                    val buffer = ByteArray(64 * 1024)
                    while (true) {
                        currentCoroutineContext().ensureActive()
                        val count = input.read(buffer); if (count < 0) break
                        output.write(buffer, 0, count)
                    }
                }
            }
            val probe = probeAudio(file)
            val source = StudioSource(id, name.trim().take(240), "$id.audio", probe.durationMs, probe.mime)
            // Commit source + initial editable full-length clip together; no hidden 15/30s constraint.
            mutex.withLock {
                ready()
                val current = mutable.value.projects.first { it.id == projectId }
                val changed = current.copy(sources = current.sources + source, updatedAt = System.currentTimeMillis())
                    .withClip(id, 0, source.durationMs)
                val target = File(sources, source.fileName)
                check(file.renameTo(target))
                try {
                    persist(mutable.value.projects.map { if (it.id == projectId) changed else it })
                    committed = true
                } catch (e: Exception) { target.delete(); throw e }
            }
        } finally { if (!committed) file.delete(); pendingImports.remove(file.name) }
    }
    suspend fun copyAudio(source: Uri, destination: Uri) = withContext(Dispatchers.IO) {
        require(source != destination)
        // A SAF URI can alias a MediaStore file. Read fully before opening the destination for
        // truncation, otherwise Save a copy over the same path can destroy its own input.
        val staged = File(temporary, "${studioId()}.copy")
        pendingCopies.add(staged.name)
        try {
            requireNotNull(context.contentResolver.openInputStream(source)).use { input ->
                staged.outputStream().use { output ->
                    val buffer = ByteArray(64 * 1024)
                    while (true) {
                        currentCoroutineContext().ensureActive()
                        val count = input.read(buffer); if (count < 0) break
                        output.write(buffer, 0, count)
                    }
                }
            }
            currentCoroutineContext().ensureActive()
            // Once the user-selected destination is opened, finish this copy without a partial
            // cancellation. Never delete an arbitrary existing document selected by the user.
            withContext(NonCancellable + Dispatchers.IO) {
                requireNotNull(context.contentResolver.openOutputStream(destination, "wt")).use { output ->
                    staged.inputStream().use { it.copyTo(output) }
                }
            }
        } finally { staged.delete(); pendingCopies.remove(staged.name) }
    }
    fun sourceFile(source: StudioSource): File {
        require(source.fileName == "${source.id}.audio" && UUID.fromString(source.id).toString() == source.id)
        return File(sources, source.fileName).also { require(it.isFile && it.length() > 0) }
    }
    private fun requestFile(id: String): File {
        require(UUID.fromString(id).toString() == id)
        return File(requests, "$id.json")
    }
    fun readRequest(id: String): StudioRenderRequest {
        val request = json.decodeFromString<StudioRenderRequest>(AtomicFile(requestFile(id)).readFully().decodeToString())
        require(request.id == id); request.project.validate(requireClips = true)
        request.project.sources.forEach { sourceFile(it) }
        return request
    }
    suspend fun export(projectId: String): String = withContext(Dispatchers.IO) { mutex.withLock {
        ready()
        check(work.getWorkInfosForUniqueWork(WORK_NAME).get().none { !it.state.isFinished })
        val project = mutable.value.projects.first { it.id == projectId }.validate(requireClips = true)
        project.clips.map { clip -> project.sources.first { it.id == clip.sourceId } }.forEach { sourceFile(it) }
        val id = studioId()
        val snapshot = project.copy(sources = project.sources.filter { source -> project.clips.any { it.sourceId == source.id } })
        val request = OneTimeWorkRequestBuilder<StudioExportWorker>().setId(UUID.fromString(id))
            .setInputData(workDataOf("request" to id, "project" to projectId)).addTag(WORK_TAG).build()
        write(AtomicFile(requestFile(id)), json.encodeToString(StudioRenderRequest(id, snapshot)))
        try {
            persist(mutable.value.projects.map { if (it.id == projectId) it.copy(lastRequestId = id) else it })
            work.enqueueUniqueWork(WORK_NAME, ExistingWorkPolicy.KEEP, request).result.get()
        } catch (e: Exception) { AtomicFile(requestFile(id)).delete(); throw e }
        id
    } }
    fun cancelExport(id: String) { work.cancelWorkById(UUID.fromString(id)) }
    suspend fun completed(projectId: String, track: Track) {
        state.first { !it.loading }
        withContext(Dispatchers.IO) { mutex.withLock {
            ready()
            if (mutable.value.projects.any { it.id == projectId })
                persist(mutable.value.projects.map { if (it.id == projectId) it.copy(lastExport = track) else it })
        } }
    }
    suspend fun finishRequest(id: String) = withContext(Dispatchers.IO) { mutex.withLock {
        AtomicFile(requestFile(id)).delete(); cleanUnreferencedSources()
    } }
    private fun cleanFinishedRequests() {
        requests.listFiles()?.filter { it.extension == "json" }?.forEach { file ->
            val id = file.nameWithoutExtension
            val info = work.getWorkInfoById(UUID.fromString(id)).get()
            if (info == null || info.state.isFinished) { AtomicFile(file).delete(); File(temporary, "$id.m4a").delete() }
        }
        temporary.listFiles()?.filter {
            (it.extension == "import" && it.name !in pendingImports) || (it.extension == "copy" && it.name !in pendingCopies)
        }?.forEach(File::delete)
        cleanUnreferencedSources()
    }
    private fun cleanUnreferencedSources() {
        // Unknown/corrupt catalog != empty library. Never garbage-collect potentially recoverable audio.
        if (mutable.value.loading || mutable.value.failed) return
        // Render snapshots pin their inputs even if a project is changed/deleted while encoding.
        val pinned = requests.listFiles()?.filter { it.extension == "json" }?.flatMap {
            json.decodeFromString<StudioRenderRequest>(AtomicFile(it).readFully().decodeToString()).project.sources.map(StudioSource::fileName)
        }.orEmpty()
        val referenced = (mutable.value.projects.flatMap { it.sources.map(StudioSource::fileName) } + pinned).toSet()
        sources.listFiles()?.filter { it.name !in referenced }?.forEach(File::delete)
    }
    companion object { const val WORK_NAME = "dkord-studio-export"; const val WORK_TAG = "dkord-studio" }
}

internal data class AudioProbe(val durationMs: Long, val mime: String)
internal fun probeAudio(file: File): AudioProbe {
    val extractor = MediaExtractor()
    try {
        extractor.setDataSource(file.absolutePath)
        require(extractor.drmInitData == null)
        val audio = (0 until extractor.trackCount).map { extractor.getTrackFormat(it) }
            .firstOrNull { it.getString(MediaFormat.KEY_MIME)?.startsWith("audio/") == true }
        requireNotNull(audio)
        val retriever = MediaMetadataRetriever()
        val duration = try {
            retriever.setDataSource(file.absolutePath)
            retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_DURATION)?.toLongOrNull()
        } finally { retriever.release() }
        val ms = duration ?: if (audio.containsKey(MediaFormat.KEY_DURATION)) audio.getLong(MediaFormat.KEY_DURATION) / 1000 else 0
        require(ms > 0)
        return AudioProbe(ms, requireNotNull(audio.getString(MediaFormat.KEY_MIME)))
    } finally { extractor.release() }
}
