package app.dkord

import android.content.ContextWrapper
import android.database.sqlite.SQLiteDatabase
import android.net.Uri
import android.provider.MediaStore
import androidx.room.Room
import androidx.test.platform.app.InstrumentationRegistry
import app.dkord.core.Track
import app.dkord.data.db.*
import app.dkord.data.download.*
import app.dkord.data.stream.*
import app.dkord.data.studio.*
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.first
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.*
import org.junit.Test
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder

class OnlineStudioAndStorageTest {
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private fun isolated(dir: File) = object : ContextWrapper(context) { override fun getFilesDir(): File = dir }
    private suspend fun ready(repo: StudioRepository) = withTimeout(10_000) { repo.state.first { !it.loading }.also { assertFalse(it.failed) } }
    private val track = Track("online00001", "संगवारी — Studio fixture", "Test singer")
    private fun wave(): ByteArray {
        val samples = 44100
        return ByteBuffer.allocate(44 + samples * 2).order(ByteOrder.LITTLE_ENDIAN).apply {
            put("RIFF".toByteArray()); putInt(36 + samples * 2); put("WAVEfmt ".toByteArray())
            putInt(16); putShort(1); putShort(1); putInt(44100); putInt(88200); putShort(2); putShort(16)
            put("data".toByteArray()); putInt(samples * 2)
            repeat(samples) { putShort(if (it % 100 < 50) 1200 else -1200) }
        }.array()
    }
    private fun downloader(bytes: ByteArray) = TrackDownloader(object : StreamResolver {
        override val name = "in-memory fixture, no external network"
        override suspend fun resolve(videoId: String, quality: AudioQuality, preferM4a: Boolean) =
            ResolvedStream(videoId, "https://audio.fixture.invalid/song?itag=fixture", "audio/wav", 88200,
                bytes.size.toLong(), System.currentTimeMillis() + 3_600_000, null, name)
    }, OkHttpClient.Builder().addInterceptor { chain ->
        Response.Builder().request(chain.request()).protocol(Protocol.HTTP_1_1).code(200).message("OK")
            .body(bytes.toResponseBody("audio/wav".toMediaType())).build()
    }.build(), {})

    @Test fun version_one_migration_preserves_every_table_public_uri_pause_state_and_unrelated_files() = runBlocking {
        val name = "migration-${studioId()}.db"
        val path = context.getDatabasePath(name).apply { parentFile?.mkdirs() }
        val untouched = File(context.cacheDir, "legacy-${studioId()}.audio").apply { writeBytes(wave()) }
        var upgraded: AppDatabase? = null
        try {
            SQLiteDatabase.openOrCreateDatabase(path, null).use { old ->
                old.execSQL("CREATE TABLE tracks (id TEXT NOT NULL PRIMARY KEY, title TEXT NOT NULL, artist TEXT NOT NULL, album TEXT, durationSec INTEGER NOT NULL, thumbnail TEXT)")
                old.execSQL("CREATE TABLE playlists (id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, name TEXT NOT NULL, createdAt INTEGER NOT NULL, updatedAt INTEGER NOT NULL)")
                old.execSQL("CREATE TABLE playlist_items (id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, playlistId INTEGER NOT NULL, trackId TEXT NOT NULL, position INTEGER NOT NULL, FOREIGN KEY(playlistId) REFERENCES playlists(id) ON DELETE CASCADE, FOREIGN KEY(trackId) REFERENCES tracks(id) ON DELETE CASCADE)")
                old.execSQL("CREATE INDEX index_playlist_items_playlistId ON playlist_items(playlistId)")
                old.execSQL("CREATE INDEX index_playlist_items_trackId ON playlist_items(trackId)")
                old.execSQL("CREATE TABLE liked (trackId TEXT NOT NULL PRIMARY KEY, likedAt INTEGER NOT NULL, FOREIGN KEY(trackId) REFERENCES tracks(id) ON DELETE CASCADE)")
                old.execSQL("CREATE TABLE history (trackId TEXT NOT NULL PRIMARY KEY, playedAt INTEGER NOT NULL, FOREIGN KEY(trackId) REFERENCES tracks(id) ON DELETE CASCADE)")
                old.execSQL("CREATE TABLE downloads (trackId TEXT NOT NULL PRIMARY KEY, state TEXT NOT NULL, bytes INTEGER NOT NULL, total INTEGER NOT NULL, mime TEXT, localUri TEXT, error TEXT, createdAt INTEGER NOT NULL, updatedAt INTEGER NOT NULL, FOREIGN KEY(trackId) REFERENCES tracks(id) ON DELETE CASCADE)")
                old.execSQL("CREATE INDEX index_downloads_state ON downloads(state)")
                old.execSQL("INSERT INTO tracks VALUES ('legacy00001','My music','Artist','Album',42,NULL)")
                old.execSQL("INSERT INTO tracks VALUES ('legacy00002','Paused song','Artist',NULL,180,NULL)")
                old.execSQL("INSERT INTO playlists VALUES (1,'Saved playlist',11,22)")
                old.execSQL("INSERT INTO playlist_items VALUES (1,1,'legacy00001',7)")
                old.execSQL("INSERT INTO liked VALUES ('legacy00001',123)")
                old.execSQL("INSERT INTO history VALUES ('legacy00001',456)")
                old.execSQL("INSERT INTO downloads VALUES ('legacy00001','DONE',88244,88244,'audio/wav',?,NULL,100,200)", arrayOf(Uri.fromFile(untouched).toString()))
                old.execSQL("INSERT INTO downloads VALUES ('legacy00002','PAUSED',123,999,'audio/mp4#140',NULL,NULL,300,400)")
                old.version = 1
            }
            upgraded = Room.databaseBuilder(context, AppDatabase::class.java, name).addMigrations(AppDatabase.MIGRATION_1_2).build()
            // Opening and reading actually executes Room's schema validation, not just SQL string checks.
            val saved = requireNotNull(upgraded.downloads().get("legacy00001"))
            assertEquals(DownloadLocation.LEGACY, saved.location); assertNull(saved.deviceUri); assertNull(saved.deviceTree)
            assertEquals(Uri.fromFile(untouched).toString(), saved.localUri); assertEquals(DownloadState.DONE, saved.state)
            val paused = requireNotNull(upgraded.downloads().get("legacy00002"))
            assertEquals(DownloadState.PAUSED, paused.state); assertEquals(123L, paused.bytes); assertEquals("audio/mp4#140", paused.mime)
            val db = upgraded.openHelper.writableDatabase
            for ((table, count) in mapOf("tracks" to 2, "playlists" to 1, "playlist_items" to 1, "liked" to 1, "history" to 1, "downloads" to 2))
                db.query("SELECT COUNT(*) FROM $table").use { assertTrue(it.moveToFirst()); assertEquals(table, count, it.getInt(0)) }
            db.query("SELECT position FROM playlist_items WHERE id=1").use { assertTrue(it.moveToFirst()); assertEquals(7, it.getInt(0)) }
            db.query("SELECT playedAt FROM history").use { assertTrue(it.moveToFirst()); assertEquals(456L, it.getLong(0)) }
            assertArrayEquals(wave(), untouched.readBytes())
        } finally { upgraded?.close(); context.deleteDatabase(name); untouched.delete() }
    }
    @Test fun private_audio_and_explicit_device_copy_are_distinct_and_removing_private_keeps_device_copy() {
        val dir = File(context.cacheDir, "storage-${studioId()}").apply { mkdirs() }
        val storage = DownloadStorage(isolated(dir))
        var device: String? = null
        try {
            val bytes = wave(); val name = "Dkord-test-${studioId()}.wav"
            val part = File(dir, "part").apply { writeBytes(bytes) }
            val private = storage.publishPrivate(part, name)
            assertTrue(storage.isPrivate(private)); assertTrue(storage.exists(private)); assertFalse(part.exists())
            context.contentResolver.query(MediaStore.Audio.Media.EXTERNAL_CONTENT_URI, arrayOf(MediaStore.Audio.Media._ID),
                "${MediaStore.Audio.Media.DISPLAY_NAME} = ?", arrayOf(name), null).use { assertNotNull(it); assertEquals(0, it!!.count) }
            val copy = File(dir, "copy"); storage.stageCopy(private, copy)
            device = storage.publishToDevice(copy, name, "audio/wav", null)
            assertEquals("content", Uri.parse(device).scheme); assertFalse(storage.isPrivate(device!!)); assertNotEquals(private, device)
            storage.delete(private)
            assertTrue(storage.exists(device!!))
            context.contentResolver.openInputStream(Uri.parse(device)).use { assertArrayEquals(bytes, it!!.readBytes()) }
        } finally { device?.let(storage::delete); dir.deleteRecursively() }
    }
    @Test fun inaccessible_device_folder_fails_without_private_or_public_fallback_or_source_deletion() {
        val dir = File(context.cacheDir, "strict-save-${studioId()}").apply { mkdirs() }
        try {
            val storage = DownloadStorage(isolated(dir)); val part = File(dir, "part").apply { writeBytes(wave()) }
            try {
                storage.publishToDevice(part, "${studioId()}.wav", "audio/wav", "content://invalid.dkord.provider/tree/no-access")
                fail("Explicit device save must not claim private-fallback success")
            } catch (_: Exception) { }
            assertArrayEquals(wave(), part.readBytes())
            assertEquals(0, File(dir, "offline").listFiles().orEmpty().size)
        } finally { dir.deleteRecursively() }
    }
    @Test fun online_source_becomes_a_durable_editable_project_without_a_download_entry_or_persisted_url() = runBlocking {
        val dir = File(context.cacheDir, "online-import-${studioId()}").apply { mkdirs() }
        val db = AppDatabase.build(context)
        try {
            assertNull(db.downloads().get(track.id))
            val repo = StudioRepository(isolated(dir)); ready(repo); val id = repo.create("Online project")
            val progress = mutableListOf<StudioPreparation>()
            StudioOnlineImporter(repo, downloader(wave())) { AudioQuality.HIGH }.import(id, track) { progress += it }
            val project = repo.state.value.projects.single()
            assertEquals(1, project.sources.size); assertEquals(1, project.clips.size); assertTrue(project.durationMs >= 900)
            assertTrue(repo.sourceFile(project.sources.single()).isFile)
            assertTrue(progress.any { it.bytes > 0 }); assertTrue(repo.temporary.listFiles().orEmpty().isEmpty())
            assertNull(db.downloads().get(track.id))
            assertFalse(File(repo.root, "projects.json").readText().contains("https://"))
            val reopened = StudioRepository(isolated(dir)); ready(reopened)
            assertEquals(project, reopened.state.value.projects.single()); assertTrue(reopened.sourceFile(project.sources.single()).isFile)
        } finally { db.close(); dir.deleteRecursively() }
    }
    @Test fun cancelled_or_invalid_online_audio_leaves_no_partial_source_clip_or_staging_file() = runBlocking {
        val dir = File(context.cacheDir, "online-cancel-${studioId()}").apply { mkdirs() }
        try {
            val repo = StudioRepository(isolated(dir)); ready(repo); val id = repo.create("Kept project")
            try {
                StudioOnlineImporter(repo, downloader(wave())) { AudioQuality.HIGH }.import(id, track) { throw CancellationException("user cancelled") }
                fail("Cancellation must propagate")
            } catch (_: CancellationException) { }
            assertTrue(repo.state.value.projects.single().sources.isEmpty()); assertTrue(repo.state.value.projects.single().clips.isEmpty())
            assertTrue(repo.temporary.listFiles().orEmpty().isEmpty())
            try {
                StudioOnlineImporter(repo, downloader("not audio".toByteArray())) { AudioQuality.HIGH }.import(id, track)
                fail("Unprobeable source must not be committed")
            } catch (_: Exception) { }
            assertTrue(repo.state.value.projects.single().sources.isEmpty()); assertTrue(repo.temporary.listFiles().orEmpty().isEmpty())
            val abandoned = File(repo.temporary, "${studioId()}.online").apply { writeText("interrupted process") }
            val reopened = StudioRepository(isolated(dir)); ready(reopened)
            assertFalse(abandoned.exists()); assertEquals(id, reopened.state.value.projects.single().id)
        } finally { dir.deleteRecursively() }
    }
    @Test fun completed_private_source_reuses_bytes_and_keeps_explicit_device_intent_through_pause_and_worker_recovery() = runBlocking {
        val dir = File(context.cacheDir, "download-intent-${studioId()}").apply { mkdirs() }
        val db = Room.inMemoryDatabaseBuilder(context, AppDatabase::class.java).build()
        try {
            val storage = DownloadStorage(isolated(dir))
            val part = File(dir, "part").apply { writeBytes(wave()) }
            val uri = storage.publishPrivate(part, "source.wav")
            db.tracks().upsert(track.toEntity())
            db.downloads().upsert(DownloadEntity(track.id, DownloadState.DONE, wave().size.toLong(), wave().size.toLong(), "audio/wav", uri,
                createdAt = 1, updatedAt = 1, location = DownloadLocation.APP))
            var scheduled = 0
            val manager = DownloadManager(context, db, storage) { scheduled++ }
            val tree = "content://chosen.example/tree/a"
            manager.enqueue(listOf(track), DownloadLocation.DEVICE, tree)
            assertTrue(scheduled > 0)
            var saved = requireNotNull(db.downloads().get(track.id))
            assertEquals(DownloadState.QUEUED, saved.state); assertEquals(DownloadLocation.DEVICE, saved.location)
            assertEquals(uri, saved.localUri); assertEquals(tree, saved.deviceTree)
            manager.enqueue(listOf(track), DownloadLocation.APP)
            assertEquals(DownloadLocation.DEVICE, db.downloads().get(track.id)!!.location)
            manager.pause(track.id); manager.resume(track.id)
            saved = requireNotNull(db.downloads().get(track.id))
            assertEquals(tree, saved.deviceTree); assertEquals(uri, db.downloads().localUri(track.id))
            assertArrayEquals(wave(), File(Uri.parse(uri).path!!).readBytes())
            assertEquals(track.id, db.downloads().nextQueued(localOnly = true)!!.track.id)
            assertNull(db.downloads().nextQueued(localOnly = true, activeIds = listOf(track.id)))
            db.downloads().markRunning(track.id, 2)
            db.downloads().resetRunning(3, listOf(track.id))
            assertEquals(DownloadState.RUNNING, db.downloads().get(track.id)!!.state)
            db.downloads().resetRunning(4)
            assertEquals(DownloadState.QUEUED, db.downloads().get(track.id)!!.state)
        } finally { db.close(); dir.deleteRecursively() }
    }
    @Test fun changing_failed_device_copy_to_private_retains_audio_and_existing_device_export() = runBlocking {
        val dir = File(context.cacheDir, "private-recovery-${studioId()}").apply { mkdirs() }
        val db = Room.inMemoryDatabaseBuilder(context, AppDatabase::class.java).build()
        try {
            val storage = DownloadStorage(isolated(dir))
            val uri = storage.publishPrivate(File(dir, "part").apply { writeBytes(wave()) }, "source.wav")
            val previous = File(dir, "device-copy.wav").apply { writeBytes(wave()) }
            db.tracks().upsert(track.toEntity())
            db.downloads().upsert(DownloadEntity(track.id, DownloadState.FAILED, wave().size.toLong(), wave().size.toLong(), "audio/wav", uri,
                createdAt = 1, updatedAt = 1, location = DownloadLocation.DEVICE, deviceUri = Uri.fromFile(previous).toString()))
            val manager = DownloadManager(context, db, storage) {}
            manager.enqueue(listOf(track), DownloadLocation.APP)
            assertEquals(DownloadState.DONE, db.downloads().get(track.id)!!.state)
            assertEquals(DownloadLocation.APP, db.downloads().get(track.id)!!.location)
            manager.remove(track.id)
            assertNull(db.downloads().get(track.id)); assertFalse(storage.exists(uri)); assertTrue(previous.exists())
        } finally { db.close(); dir.deleteRecursively() }
    }
    @Test fun large_picker_batches_survive_recreation_via_small_token_not_activity_saved_song_payloads() {
        val dir = File(context.cacheDir, "download-picker-${studioId()}").apply { mkdirs() }
        try {
            val songs = (0 until 2000).map { track.copy(id = "song-$it", title = "Saved song $it") }
            val token = DownloadSelectionStorage(isolated(dir)).save(songs)
            assertTrue(token.length < 50)
            assertEquals(songs, DownloadSelectionStorage(isolated(dir)).take(token))
            assertTrue(File(dir, "download-selections").listFiles().orEmpty().isEmpty())
        } finally { dir.deleteRecursively() }
    }
}
