package app.dkord

import android.net.Uri
import androidx.activity.ComponentActivity
import androidx.core.content.FileProvider
import androidx.test.ext.junit.rules.ActivityScenarioRule
import androidx.test.platform.app.InstrumentationRegistry
import app.dkord.core.LOCAL_STUDIO_PREFIX
import app.dkord.data.db.AppDatabase
import app.dkord.data.db.DownloadState
import app.dkord.data.download.DownloadManager
import app.dkord.data.library.LibraryRepository
import app.dkord.data.studio.*
import androidx.work.WorkInfo
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.koin.core.context.GlobalContext
import java.io.File
import java.util.UUID

class StudioExportPublicationTest {
    @get:Rule val foreground = ActivityScenarioRule(ComponentActivity::class.java)
    @Test fun real_foreground_work_exports_registers_playable_audio_and_playlist_and_scopes_file_sharing() = runBlocking {
        val ctx = InstrumentationRegistry.getInstrumentation().targetContext
        val koin = GlobalContext.get()
        val repo = koin.get<StudioRepository>(); val db = koin.get<AppDatabase>()
        val downloads = koin.get<DownloadManager>(); val library = koin.get<LibraryRepository>()
        val dir = File(ctx.cacheDir, "studio-publish-test-${studioId()}").apply { mkdirs() }
        var projectId: String? = null; var playlistId: Long? = null; var trackId: String? = null
        var privateExport: File? = null; var workId: String? = null
        try {
            assertFalse(withTimeout(10_000) { repo.state.first { !it.loading } }.failed)
            val input = File(dir, "sample.wav")
            val rate = 44_100; val data = ByteArray(rate * 2)
            val header = java.nio.ByteBuffer.allocate(44).order(java.nio.ByteOrder.LITTLE_ENDIAN).apply {
                put("RIFF".toByteArray()); putInt(data.size + 36); put("WAVEfmt ".toByteArray()); putInt(16)
                putShort(1); putShort(1); putInt(rate); putInt(rate * 2); putShort(2); putShort(16)
                put("data".toByteArray()); putInt(data.size)
            }.array()
            input.outputStream().use { it.write(header); it.write(data) }
            val id = repo.create("CI audio ${studioId()}"); projectId = id
            repo.importAudio(id, Uri.fromFile(input), "PCM")
            val request = repo.export(id); workId = request; trackId = LOCAL_STUDIO_PREFIX + request
            val finished = withTimeout(120_000) { repo.work.getWorkInfoByIdFlow(UUID.fromString(request)).first { it?.state?.isFinished == true } }
            assertEquals("Real WorkManager publication must succeed", WorkInfo.State.SUCCEEDED, finished?.state)
            assertEquals(trackId, finished?.outputData?.getString("track"))
            val row = requireNotNull(db.downloads().get(requireNotNull(trackId)))
            assertEquals(DownloadState.DONE, row.state); assertTrue(row.bytes > 0)
            val local = requireNotNull(downloads.localUri(requireNotNull(trackId)))
            val readback = File(dir, "readback.m4a")
            requireNotNull(ctx.contentResolver.openInputStream(Uri.parse(local))).use { source -> readback.outputStream().use { source.copyTo(it) } }
            assertEquals("audio/mp4a-latm", probeAudio(readback).mime)
            val track = requireNotNull(repo.state.value.projects.first { it.id == id }.lastExport)
            val playlist = library.create("CI playlist ${studioId()}"); playlistId = playlist
            assertEquals(1, library.add(playlist, listOf(track)))
            assertEquals(track.id, db.playlists().observeEntries(playlist).first().single().track.id)
            val privateFile = File(File(repo.root, "exports").apply { mkdirs() }, "${studioId()}.m4a"); privateExport = privateFile
            readback.copyTo(privateFile)
            val share = FileProvider.getUriForFile(ctx, ctx.packageName + ".files", privateFile)
            assertEquals("content", share.scheme)
            assertNotNull(ctx.contentResolver.openFileDescriptor(share, "r")?.use { it.statSize })
            val source = repo.state.value.projects.first { it.id == id }.sources.single()
            try { FileProvider.getUriForFile(ctx, ctx.packageName + ".files", repo.sourceFile(source)); fail("Never expose private project inputs") }
            catch (_: IllegalArgumentException) { }
        } finally {
            workId?.let(repo::cancelExport)
            playlistId?.let { library.delete(it) }
            trackId?.let { downloads.remove(it) }
            projectId?.let { repo.delete(it) }
            privateExport?.delete(); dir.deleteRecursively()
        }
    }
}
