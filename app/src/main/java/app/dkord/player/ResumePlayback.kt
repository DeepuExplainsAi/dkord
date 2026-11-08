package app.dkord.player

import androidx.media3.common.Player

/** Resume the existing queue/position; never reconstruct it from history or toggle a playing song off. */
internal fun resumeExistingQueue(player: Player) {
    if (player.mediaItemCount == 0) return
    if (player.playbackState == Player.STATE_ENDED) player.seekToDefaultPosition()
    if (player.playbackState == Player.STATE_IDLE) player.prepare()
    player.play()
}
