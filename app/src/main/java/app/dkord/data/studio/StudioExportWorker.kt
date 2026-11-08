package app.dkord.data.studio

import java.util.UUID

import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.ContentValues
import android.content.Context
import android.content.pm.ServiceInfo
import android.net.Uri
import android.os.Build
import android.provider.MediaStore
import android.provider.DocumentsContract
import androidx.core.app.NotificationCompat
import androidx.room.withTransaction
import androidx.work.*
import app.dkord.R
import app.dkord.core.LOCAL_STUDIO_PREFIX
import app.dkord.core.Track
import app.dkord.data.db.AppDatabase
import app.dkord.data.db.DownloadEntity
import app.dkord.data.db.DownloadState
import app.dkord.data.db.toEntity
import app.dkord.data.db.toTrack
import app.dkord.data.download.DownloadStorage
import app.dkord.data.settings.SettingsRepository
import kotlinx.coroutines.*
import org.koin.core.component.KoinComponent
import org.koin.core.component.inject
import java.io.File

internal class StudioExportWorker(context: Context, parameters: WorkerParameters) : CoroutineWorker(context, parameters), KoinComponent {
    private val repo: StudioRepository by inject()
    private val db: AppDatabase by inject()
    private val storage: DownloadStorage by inject()
    private val settings: SettingsRepository by inject()
    override suspend fun getForegroundInfo(): ForegroundInfo = foreground()

    override suspend fun doWork(): Result {
        val requestId = inputData.getString("request")?.takeIf { runCatching { UUID.fromString(it).toString() == it }.getOrDefault(false) }
            ?: return Result.failure()
        val temp = File(repo.temporary, "$requestId.m4a")
        var cancelled = false
        try {
            // A process may die after atomic publication/registration but before WorkManager records success.
            // Recover that same output instead of duplicating it or requiring a deleted render snapshot.
            val existing = withContext(Dispatchers.IO) {
                val trackId = LOCAL_STUDIO_PREFIX + requestId
                val row = db.downloads().get(trackId)
                if (row?.state == DownloadState.DONE && row.localUri?.let(storage::exists) == true) db.tracks().get(trackId)?.toTrack() else null
            }
            if (existing != null) {
                inputData.getString("project")?.let { runCatching { repo.completed(it, existing) } }
                return Result.success(workDataOf("track" to existing.id))
            }
            setForeground(foreground())
            val request = withContext(Dispatchers.IO) { repo.readRequest(requestId) }
            val result = StudioAudioExporter(applicationContext).render(request.project, repo::sourceFile, temp) {
                setProgressAsync(workDataOf("progress" to it))
            }
            currentCoroutineContext().ensureActive()
            // Publication + Room registration is one non-cancellable boundary; never publish half an AAC file.
            val track = withContext(NonCancellable + Dispatchers.IO) {
                val now = System.currentTimeMillis()
                val track = Track(LOCAL_STUDIO_PREFIX + requestId, request.project.name,
                    applicationContext.getString(R.string.studio_title), durationSec = (result.durationMs + 999) / 1000)
                val uri = publish(temp, requestId, request.project.name)
                try {
                    db.withTransaction {
                        db.tracks().upsert(track.toEntity())
                        db.downloads().upsert(DownloadEntity(track.id, DownloadState.DONE, bytes = temp.length(), total = temp.length(),
                            mime = "audio/mp4", localUri = uri.toString(), createdAt = now, updatedAt = now))
                    }
                } catch (e: Exception) { storage.delete(uri.toString()); throw e }
                // A recoverable project-metadata error must not delete a valid, registered output.
                runCatching { repo.completed(request.project.id, track) }
                track
            }
            setProgress(workDataOf("progress" to 100))
            return Result.success(workDataOf("track" to track.id))
        } catch (e: CancellationException) { cancelled = true; throw e }
        catch (_: Exception) { return Result.failure(workDataOf("error" to "export_failed")) }
        finally {
            withContext(NonCancellable + Dispatchers.IO) {
                temp.delete()
                // OS-stopped work can be rescheduled. Keep its immutable inputs; startup prunes finished/cancelled requests.
                if (!cancelled) runCatching { repo.finishRequest(requestId) }
            }
        }
    }
    private fun foreground(): ForegroundInfo {
        val manager = applicationContext.getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(NotificationChannel(CHANNEL, applicationContext.getString(R.string.studio_title), NotificationManager.IMPORTANCE_LOW))
        val notification = NotificationCompat.Builder(applicationContext, CHANNEL).setSmallIcon(R.drawable.ic_notification)
            .setContentTitle(applicationContext.getString(R.string.studio_exporting)).setOngoing(true).setSilent(true)
            .addAction(0, applicationContext.getString(R.string.cancel), WorkManager.getInstance(applicationContext).createCancelPendingIntent(id)).build()
        return if (Build.VERSION.SDK_INT >= 35) ForegroundInfo(4102, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROCESSING)
        else if (Build.VERSION.SDK_INT >= 29) ForegroundInfo(4102, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC)
        else ForegroundInfo(4102, notification)
    }
    private fun publish(input: File, id: String, title: String): Uri {
        val name = title.replace(Regex("[\\p{Cntrl}/\\\\:*?\"<>|]"), " ").trim().take(120).ifBlank { "Dkord" } + ".m4a"
        val tree = settings.settings.value.downloadTree
        if (!tree.isNullOrBlank()) {
            val picked = Uri.parse(tree)
            val parent = DocumentsContract.buildDocumentUriUsingTree(picked, DocumentsContract.getTreeDocumentId(picked))
            val uri = requireNotNull(DocumentsContract.createDocument(applicationContext.contentResolver, parent, "audio/mp4", name))
            try {
                requireNotNull(applicationContext.contentResolver.openOutputStream(uri, "w")).use { target -> input.inputStream().use { it.copyTo(target) } }
                return uri
            } catch (e: Exception) { storage.delete(uri.toString()); throw e }
        }
        if (Build.VERSION.SDK_INT >= 29) {
            val resolver = applicationContext.contentResolver
            val values = ContentValues().apply {
                put(MediaStore.Audio.Media.DISPLAY_NAME, name); put(MediaStore.Audio.Media.TITLE, title)
                put(MediaStore.Audio.Media.MIME_TYPE, "audio/mp4"); put(MediaStore.Audio.Media.RELATIVE_PATH, "Music/Dkord/Studio")
                put(MediaStore.Audio.Media.IS_PENDING, 1)
            }
            val uri = requireNotNull(resolver.insert(MediaStore.Audio.Media.EXTERNAL_CONTENT_URI, values))
            try {
                requireNotNull(resolver.openOutputStream(uri, "w")).use { output -> input.inputStream().use { it.copyTo(output) } }
                values.clear(); values.put(MediaStore.Audio.Media.IS_PENDING, 0); check(resolver.update(uri, values, null, null) == 1)
                return uri
            } catch (e: Exception) { resolver.delete(uri, null, null); throw e }
        }
        // Android 8/9: no broad storage permission. Export/share through the narrow FileProvider path.
        val target = File(File(repo.root, "exports").apply { mkdirs() }, "$id.m4a")
        try { input.copyTo(target, overwrite = true); return Uri.fromFile(target) }
        catch (e: Exception) { target.delete(); throw e }
    }
    companion object { private const val CHANNEL = "dkord-studio-export" }
}
