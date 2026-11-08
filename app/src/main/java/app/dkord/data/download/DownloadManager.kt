package app.dkord.data.download

import app.dkord.core.isLocalAudioId

import android.content.Context
import androidx.work.Constraints
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import app.dkord.core.Track
import app.dkord.data.db.AppDatabase
import app.dkord.data.db.DownloadLocation
import app.dkord.data.db.DownloadEntity
import app.dkord.data.db.DownloadState
import app.dkord.data.db.DownloadWithTrack
import app.dkord.data.db.toEntity
import kotlinx.coroutines.Job
import kotlinx.coroutines.cancelAndJoin
import androidx.work.workDataOf
import kotlinx.coroutines.flow.Flow
import java.util.concurrent.ConcurrentHashMap
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

/** UI-facing API for downloads. The work itself runs in [DownloadWorker] so it survives app kill. */
class DownloadManager(
    private val context: Context,
    private val db: AppDatabase,
    private val storage: DownloadStorage,
    private val schedule: (() -> Unit)? = null,
) {
    private val dao = db.downloads()

    /** Jobs of the downloads currently running, so pause/cancel can stop them immediately. */
    internal val active = ConcurrentHashMap<String, Job>()

    fun downloads(): Flow<List<DownloadWithTrack>> = dao.observeAll()

    internal val publicationLock = Mutex()

    suspend fun enqueue(tracks: List<Track>, location: DownloadLocation = DownloadLocation.APP, deviceTree: String? = null) {
        require(location != DownloadLocation.LEGACY)
        publicationLock.withLock {
            val now = System.currentTimeMillis()
            for (t in tracks.distinctBy { it.id }) {
                if (isLocalAudioId(t.id)) continue
                val existing = dao.get(t.id)
                val sourceExists = existing?.localUri?.let(storage::exists) == true
                val privateExists = sourceExists && storage.isPrivate(requireNotNull(existing?.localUri))
                val deviceExists = existing?.deviceUri?.let(storage::exists) == true
                if (existing?.state == DownloadState.DONE && privateExists &&
                    (location == DownloadLocation.APP || deviceExists)) continue
                if (existing != null && privateExists && location == DownloadLocation.APP &&
                    existing.state !in setOf(DownloadState.RUNNING, DownloadState.QUEUED)) {
                    dao.setLocation(t.id, DownloadLocation.APP)
                    dao.done(t.id, requireNotNull(existing.localUri), existing.bytes, existing.mime ?: "audio/mp4", now)
                    continue
                }
                if (existing != null) {
                    // APP does not undo an already requested DEVICE save; choices never delete exports.
                    val target = if (existing.location == DownloadLocation.DEVICE) existing.location else location
                    dao.setLocation(t.id, target, if (location == DownloadLocation.DEVICE) deviceTree else existing.deviceTree)
                    if (existing.state != DownloadState.QUEUED && existing.state != DownloadState.RUNNING)
                        dao.setState(t.id, DownloadState.QUEUED, null, now)
                    continue
                }
                db.tracks().upsert(t.toEntity())
                dao.upsert(DownloadEntity(t.id, DownloadState.QUEUED, createdAt = now, updatedAt = now, location = location, deviceTree = deviceTree))
            }
        }
        kick()
    }

    suspend fun pause(id: String) {
        dao.setState(id, DownloadState.PAUSED, null, System.currentTimeMillis())
        active[id]?.cancel()
    }

    suspend fun resume(id: String) {
        if (isLocalAudioId(id)) return
        dao.setState(id, DownloadState.QUEUED, null, System.currentTimeMillis())
        kick()
    }

    suspend fun pauseAll() {
        dao.pauseAll(System.currentTimeMillis())
        active.values.forEach { it.cancel() }
    }

    suspend fun resumeAll() {
        val now = System.currentTimeMillis()
        dao.resumeAll(now); dao.requeueFailed(now)
        kick()
    }

    /** Cancels a running/queued download, or deletes a finished one (file included). */
    suspend fun remove(id: String) {
        // Never hold publicationLock while joining: a finishing worker needs it to commit.
        while (true) {
            val running = publicationLock.withLock {
                val job = active[id]
                if (job == null || job.isCompleted) {
                    if (job != null) active.remove(id, job)
                    val row = dao.get(id)
                    dao.delete(id)
                    storage.partFile(id).delete()
                    row?.localUri?.let(storage::delete)
                    // Explicit user-owned device copies are intentionally retained.
                    return
                }
                job
            }
            running.cancelAndJoin()
        }
    }

    /** The playable uri of a finished download, or null if it was never downloaded or the file is gone. */
    suspend fun localUri(id: String): String? {
        val uri = dao.localUri(id) ?: return null
        if (storage.exists(uri)) return uri
        if (dao.get(id)?.state == DownloadState.DONE) dao.delete(id) // do not delete a live retry intent
        return null
    }

    fun kick() {
        schedule?.let { it(); return }
        val request = OneTimeWorkRequestBuilder<DownloadWorker>()
            .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
            .build()
        // Append: a worker that is just finishing its loop must not strand a newly queued item.
        val work = WorkManager.getInstance(context)
        work.enqueueUniqueWork(WORK_NAME, ExistingWorkPolicy.APPEND_OR_REPLACE, request)
        // A completed private/public source needs no network. Do not strand local copies behind
        // a connected-network-constrained remote queue. Both workers share claim/publication ownership.
        val copy = OneTimeWorkRequestBuilder<DownloadWorker>()
            .setInputData(workDataOf(LOCAL_ONLY to true)).build()
        work.enqueueUniqueWork("$WORK_NAME-local-copies", ExistingWorkPolicy.APPEND_OR_REPLACE, copy)
    }

    companion object { const val WORK_NAME = "downloads"; const val LOCAL_ONLY = "local-only" }
}
