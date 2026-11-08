package app.dkord

import androidx.media3.common.Player
import app.dkord.player.resumeExistingQueue
import org.junit.Assert.*
import org.junit.Test
import java.lang.reflect.Proxy

class ResumePlaybackTest {
    private fun calls(state: Int, items: Int = 2): List<String> {
        val calls = mutableListOf<String>()
        val player = Proxy.newProxyInstance(Player::class.java.classLoader, arrayOf(Player::class.java)) { _, method, _ ->
            when (method.name) {
                "getMediaItemCount" -> items
                "getPlaybackState" -> state
                "prepare", "play", "seekToDefaultPosition" -> { calls += method.name; null }
                else -> error("Resume must not replace the queue, seek a paused song or pause playback: ${method.name}")
            }
        } as Player
        resumeExistingQueue(player)
        return calls
    }
    @Test fun paused_ready_queue_keeps_position_and_only_resumes() = assertEquals(listOf("play"), calls(Player.STATE_READY))
    @Test fun cold_restored_queue_prepares_only_after_explicit_resume() = assertEquals(listOf("prepare", "play"), calls(Player.STATE_IDLE))
    @Test fun ended_song_restarts_deliberately_without_rebuilding_queue() = assertEquals(listOf("seekToDefaultPosition", "play"), calls(Player.STATE_ENDED))
    @Test fun buffering_resume_never_seeks_or_toggles_off() = assertEquals(listOf("play"), calls(Player.STATE_BUFFERING))
    @Test fun empty_queue_cannot_start_or_prepare_anything() = assertTrue(calls(Player.STATE_IDLE, 0).isEmpty())
}
