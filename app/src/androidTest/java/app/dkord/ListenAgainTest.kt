@file:OptIn(androidx.media3.common.util.UnstableApi::class)

package app.dkord

import android.content.res.Configuration
import android.net.Uri
import android.view.WindowManager
import androidx.activity.ComponentActivity
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.*
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.unit.Density
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.media3.common.MediaItem
import androidx.media3.common.Player
import androidx.media3.exoplayer.ExoPlayer
import androidx.room.Room
import app.dkord.core.ListeningEntry
import app.dkord.core.Track
import app.dkord.data.db.*
import app.dkord.data.library.LibraryRepository
import app.dkord.player.PlayerUiState
import app.dkord.player.resumeExistingQueue
import app.dkord.ui.common.KeyboardAwareScaffold
import app.dkord.ui.listen.ListeningData
import app.dkord.ui.screens.ListenAgainContent
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.Locale

class ListenAgainTest {
    @get:Rule val rule = createAndroidComposeRule<ComponentActivity>()

    private fun scrollTo(tag: String) {
        rule.onNodeWithTag("listen-list").performScrollToNode(hasTestTag(tag))
    }

    @Test fun english_resume_and_history_actions_are_explicit_and_preserve_selected_identity() {
        val a = Track("a", "Evening song", "Singer")
        val b = Track("b", "Second song", "Another singer")
        val entries = listOf(ListeningEntry(a, 2000), ListeningEntry(b, 1000))
        var plays = emptyList<String>()
        var resume = 0
        var clear = 0
        var opened = 0
        rule.setContent { MaterialTheme {
            ListenAgainContent(ListeningData(entries, loading = false),
                PlayerUiState(connected = true, current = a, positionMs = 1234, durationMs = 10000),
                onPlay = { plays = listOf(it.id) }, onPlayAll = { plays = it.map { t -> t.id } }, onMenu = {},
                onResume = { resume++ }, onOpenPlayer = { opened++ }, onSearch = {}, onRemove = {}, onClear = { clear++ }, onRetry = {})
        } }
        rule.runOnIdle { assertTrue(plays.isEmpty()); assertEquals(0, resume); assertEquals(0, clear) }
        scrollTo("listen-resume"); rule.onNodeWithTag("listen-resume").assertIsDisplayed().performClick()
        rule.runOnIdle { assertEquals(1, resume); assertEquals(0, opened) }
        scrollTo("listen-track-b"); rule.onNodeWithTag("listen-track-b").performClick()
        rule.runOnIdle { assertEquals(listOf("b"), plays) }
        scrollTo("listen-play-all"); rule.onNodeWithTag("listen-play-all").performClick()
        rule.runOnIdle { assertEquals(listOf("a", "b"), plays) }
        scrollTo("listen-manage"); rule.onNodeWithTag("listen-manage").performClick()
        scrollTo("listen-clear-history"); rule.onNodeWithTag("listen-clear-history").performClick()
        rule.onNodeWithText(rule.activity.getString(R.string.listen_clear_title)).assertIsDisplayed()
        rule.onNodeWithText(rule.activity.getString(R.string.cancel)).performClick()
        rule.runOnIdle { assertEquals(0, clear) }
        rule.onNodeWithTag("listen-clear-history").performClick()
        rule.onNodeWithTag("listen-confirm-clear").performClick()
        rule.runOnIdle { assertEquals(1, clear) }
    }

    @Test fun hindi_larger_font_local_history_search_and_filters_work_with_real_ime() {
        rule.activityRule.scenario.onActivity {
            it.enableEdgeToEdge()
            it.window.setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE)
        }
        val ctx = rule.activity.createConfigurationContext(Configuration(rule.activity.resources.configuration).apply { setLocale(Locale.forLanguageTag("hi")) })
        val one = Track("one", "तेरी मेरी कहानी", "गायक")
        val two = Track("two", "अन्य गीत", "दूसरा गायक")
        var played: String? = null
        rule.setContent {
            val density = LocalDensity.current
            CompositionLocalProvider(LocalContext provides ctx, LocalDensity provides Density(density.density, 1.3f)) {
                MaterialTheme {
                    KeyboardAwareScaffold(bottomBar = {}) { pad ->
                        ListenAgainContent(ListeningData(listOf(ListeningEntry(one, 2000), ListeningEntry(two, 1000)), likedIds = setOf(one.id), loading = false),
                            PlayerUiState(), onPlay = { played = it.id }, onPlayAll = {}, onMenu = {}, onResume = {}, onOpenPlayer = {}, onSearch = {}, onRemove = {}, onClear = {}, onRetry = {},
                            modifier = Modifier.padding(pad).consumeWindowInsets(pad))
                    }
                }
            }
        }
        scrollTo("listen-search")
        rule.onNodeWithTag("listen-search").assertIsDisplayed().performClick()
        rule.waitUntil(10_000) { ViewCompat.getRootWindowInsets(rule.activity.window.decorView)?.isVisible(WindowInsetsCompat.Type.ime()) == true }
        rule.onNodeWithTag("listen-search").performTextInput("कहानी")
        scrollTo("listen-filters"); rule.onNodeWithTag("listen-filter-LIKED").assertIsDisplayed().performClick()
        scrollTo("listen-track-one"); rule.onNodeWithTag("listen-track-one").assertIsDisplayed().performClick()
        rule.onNodeWithTag("listen-track-two").assertDoesNotExist()
        rule.runOnIdle { assertEquals("one", played) }
    }

    @Test fun real_room_history_management_keeps_tracks_likes_playlists_downloads_and_files() = runBlocking {
        val db = Room.inMemoryDatabaseBuilder(rule.activity, AppDatabase::class.java).build()
        val file = File.createTempFile("listen-history-", ".owned", rule.activity.cacheDir).apply { writeText("owned test input") }
        try {
            val repo = LibraryRepository(db)
            val a = Track("isolated-a", "First", "Artist")
            val b = Track("isolated-b", "Second", "Artist")
            repo.recordPlayed(a); repo.recordPlayed(b)
            db.library().played(HistoryEntity(a.id, 1000)); db.library().played(HistoryEntity(b.id, 2000))
            repo.setLiked(a, true)
            val playlist = repo.create("Isolated test playlist"); repo.add(playlist, listOf(a, b))
            db.downloads().upsert(DownloadEntity(a.id, DownloadState.DONE, localUri = Uri.fromFile(file).toString(), createdAt = 1, updatedAt = 1))
            assertEquals(listOf(b.id, a.id), repo.history().first().map { it.track.id })
            assertEquals(2000L, repo.history().first().first().playedAtMs)
            repo.removeFromHistory(a.id)
            assertEquals(listOf(b.id), repo.history().first().map { it.track.id })
            repo.clearHistory(); assertTrue(repo.history().first().isEmpty())
            assertNotNull(db.tracks().get(a.id)); assertNotNull(db.tracks().get(b.id))
            assertEquals(setOf(a.id), repo.likedIds().first())
            assertEquals(listOf(a.id, b.id), repo.tracks(playlist).first().map { it.id })
            assertEquals(DownloadState.DONE, db.downloads().get(a.id)?.state)
            assertEquals("owned test input", file.readText())
        } finally { db.close(); file.delete() }
    }

    @Test fun actual_player_resumes_private_audio_at_its_position_without_rebuilding_queue() {
        val file = File.createTempFile("listen-resume-", ".wav", rule.activity.cacheDir)
        val rate = 8000; val samples = rate * 4; val bytes = samples * 2
        val wave = ByteBuffer.allocate(44 + bytes).order(ByteOrder.LITTLE_ENDIAN)
        wave.put("RIFF".toByteArray()).putInt(36 + bytes).put("WAVEfmt ".toByteArray()).putInt(16).putShort(1).putShort(1)
            .putInt(rate).putInt(rate * 2).putShort(2).putShort(16).put("data".toByteArray()).putInt(bytes)
        repeat(samples) { wave.putShort(0) }
        file.writeBytes(wave.array())
        var player: ExoPlayer? = null
        try {
            rule.runOnUiThread {
                player = ExoPlayer.Builder(rule.activity).build().apply {
                    volume = 0f
                    setMediaItem(MediaItem.Builder().setMediaId("isolated-resume").setUri(Uri.fromFile(file)).build())
                    prepare()
                }
            }
            rule.waitUntil(15_000) { var ready = false; rule.runOnUiThread { ready = player?.playbackState == Player.STATE_READY }; ready }
            rule.runOnUiThread { player!!.seekTo(1200) }
            rule.waitUntil(10_000) { var ready = false; rule.runOnUiThread { ready = player!!.playbackState == Player.STATE_READY && player!!.currentPosition >= 1100 }; ready }
            rule.runOnUiThread { resumeExistingQueue(player!!) }
            rule.waitUntil(10_000) { var playing = false; rule.runOnUiThread { playing = player!!.isPlaying }; playing }
            rule.runOnUiThread {
                player!!.pause()
                assertTrue(player!!.currentPosition >= 1100)
                assertEquals(1, player!!.mediaItemCount)
                assertEquals("isolated-resume", player!!.currentMediaItem?.mediaId)
            }
        } finally { rule.runOnUiThread { player?.release() }; file.delete() }
    }
}
