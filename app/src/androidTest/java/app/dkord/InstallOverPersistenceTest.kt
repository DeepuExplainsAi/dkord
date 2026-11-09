package app.dkord

import android.content.Context
import android.net.Uri
import android.os.Build
import androidx.room.Room
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import app.dkord.core.Track
import app.dkord.data.db.*
import app.dkord.data.download.DownloadStorage
import app.dkord.data.settings.SettingsRepository
import app.dkord.data.settings.ThemeMode
import app.dkord.data.studio.StudioRepository
import app.dkord.player.QueueStore
import app.dkord.player.SavedQueue
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest
import java.util.Properties
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

/**
 * Default PR execution: isolated in-memory Room + generated-file round trip.
 * Release-only seed/verify phases: SAME test APK runs first against published
 * code14 and then code15, across a real adb install -r, using the actual app DB,
 * preferences, queue, private offline copy, MediaStore export and Studio catalog.
 * These phases refuse physical hardware and never uninstall/clear app data.
 */
@RunWith(AndroidJUnit4::class)
class InstallOverPersistenceTest {
    @Test fun real_store_and_owned_audio_are_preserved() = runBlocking {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val phase = InstrumentationRegistry.getArguments().getString("dkordUpgradePhase")
        require(phase == null || phase in setOf("seed", "verify"))
        val persistent = phase != null
        if (persistent) require(Build.HARDWARE in setOf("ranchu", "goldfish")) { "Release fixture requires an isolated emulator" }
        val root = if (persistent) context.filesDir else File(context.cacheDir, "upgrade-roundtrip-${System.nanoTime()}").apply { mkdirs() }
        val marker = File(root, "dkord-install-over-fixture.properties")
        val db = if (persistent) AppDatabase.build(context) else Room.inMemoryDatabaseBuilder(context, AppDatabase::class.java).build()
        val expected = Track("upgrade0001", "अपडेट — generated CI fixture", "Generated tone", durationSec = 2)
        val properties = Properties()
        try {
            if (phase == "verify") {
                check(marker.isFile) { "Original private fixture was lost" }
                marker.inputStream().use { properties.load(it) }
            } else {
                check(!marker.exists()) { "Never replace a prior upgrade fixture" }
                assertNull(db.tracks().get(expected.id))
                val original = File(root, "ci-generated-upgrade.wav").apply { writeBytes(waveBytes()) }
                val privateUri: String
                val deviceUri: String
                if (persistent) {
                    val storage = DownloadStorage(context)
                    val exportInput = File(root, "ci-device-export-input.wav").apply { original.copyTo(this) }
                    deviceUri = storage.publishToDevice(exportInput, "CI-upgrade-generated.wav", "audio/wav", null)
                    privateUri = storage.publishPrivate(original, "CI-upgrade-generated.wav")
                    assertTrue(storage.isPrivate(privateUri))
                } else {
                    privateUri = Uri.fromFile(original).toString()
                    deviceUri = Uri.fromFile(File(root, "independent-device.wav").apply { original.copyTo(this) }).toString()
                }
                db.tracks().upsert(expected.toEntity())
                db.library().like(LikedEntity(expected.id, 1234))
                db.library().played(HistoryEntity(expected.id, 2345))
                val playlist = db.playlists().insert(PlaylistEntity(name = "CI install-over fixture", createdAt = 1234, updatedAt = 1234))
                db.playlists().insertItems(listOf(PlaylistItemEntity(playlistId = playlist, trackId = expected.id, position = 0)))
                db.downloads().upsert(DownloadEntity(expected.id, DownloadState.DONE, bytes = waveBytes().size.toLong(), total = waveBytes().size.toLong(), mime = "audio/wav", localUri = privateUri, createdAt = 1234, updatedAt = 1234, location = DownloadLocation.APP, deviceUri = deviceUri))
                properties["playlist"] = playlist.toString()
                properties["private"] = privateUri
                properties["device"] = deviceUri
                properties["audioHash"] = hash(waveBytes())
                if (persistent) {
                    val settings = SettingsRepository(context)
                    settings.setTheme(ThemeMode.AMOLED); settings.setAutoplay(false)
                    withTimeout(10_000) { settings.settings.first { it.theme == ThemeMode.AMOLED && !it.autoplay } }
                    QueueStore(context).save(SavedQueue(listOf(expected), 0, 375))
                    // commit waits for the actual QueueStore's pending apply write.
                    assertTrue(context.getSharedPreferences("dkord_player", Context.MODE_PRIVATE).edit().commit())
                    val studio = StudioRepository(context)
                    withTimeout(10_000) { studio.state.first { !it.loading } }; assertFalse(studio.state.value.failed)
                    val project = studio.create("CI install-over Studio")
                    studio.importAudio(project, Uri.parse(privateUri), "Generated CI tone")
                    studio.change(project) { it.copy(clips = listOf(it.clips.single().copy(startMs = 125, endMs = 1750))) }
                    properties["studio"] = project
                    val source = studio.state.value.projects.first { it.id == project }.sources.single()
                    properties["studioHash"] = hash(File(studio.root, "sources/${source.fileName}").readBytes())
                }
                marker.outputStream().use { properties.store(it, "Isolated CI installer fixture; no real user data") }
            }
            assertEquals(2, db.openHelper.readableDatabase.version)
            assertEquals(expected, db.tracks().get(expected.id)?.toTrack())
            assertTrue(db.library().observeLikedIds().first().contains(expected.id))
            assertTrue(db.library().observeRecent(20).first().any { it.id == expected.id })
            val playlist = properties.getProperty("playlist").toLong()
            assertEquals("CI install-over fixture", db.playlists().get(playlist)?.name)
            assertEquals(listOf(expected.id), db.playlists().items(playlist).map { it.trackId })
            val download = requireNotNull(db.downloads().get(expected.id))
            assertEquals(DownloadState.DONE, download.state); assertEquals(DownloadLocation.APP, download.location)
            assertEquals(properties.getProperty("private"), download.localUri); assertEquals(properties.getProperty("device"), download.deviceUri)
            for (uri in listOf(download.localUri, download.deviceUri)) {
                val bytes = context.contentResolver.openInputStream(Uri.parse(requireNotNull(uri)))!!.use { it.readBytes() }
                assertEquals(properties.getProperty("audioHash"), hash(bytes))
            }
            if (persistent) {
                val settings = SettingsRepository(context).settings.value
                assertEquals(ThemeMode.AMOLED, settings.theme); assertFalse(settings.autoplay)
                assertEquals(SavedQueue(listOf(expected), 0, 375), QueueStore(context).load())
                val studio = StudioRepository(context)
                withTimeout(10_000) { studio.state.first { !it.loading } }; assertFalse(studio.state.value.failed)
                val project = studio.state.value.projects.first { it.id == properties.getProperty("studio") }
                assertEquals(125L, project.clips.single().startMs); assertEquals(1750L, project.clips.single().endMs)
                val source = project.sources.single()
                assertEquals(properties.getProperty("studioHash"), hash(File(studio.root, "sources/${source.fileName}").readBytes()))
            }
        } finally {
            db.close()
            if (!persistent) root.deleteRecursively() // only this test's unique cache directory
        }
    }

    private fun hash(bytes: ByteArray) = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it.toInt() and 255) }
    private fun waveBytes(): ByteArray {
        val samples = 16_000
        return ByteBuffer.allocate(44 + samples * 2).order(ByteOrder.LITTLE_ENDIAN).apply {
            put("RIFF".toByteArray()); putInt(36 + samples * 2); put("WAVEfmt ".toByteArray()); putInt(16)
            putShort(1); putShort(1); putInt(8000); putInt(16000); putShort(2); putShort(16)
            put("data".toByteArray()); putInt(samples * 2)
            repeat(samples) { putShort((2000 * kotlin.math.sin(2 * Math.PI * 440 * it / 8000)).toInt().toShort()) }
        }.array()
    }
}
