package app.dkord.player

/** Capture at enqueue time: a remote command must remain silent after a lazy controller connects. */
internal class PlaybackCommandGate {
    private var depth = 0
    val report get() = depth == 0
    fun <T> remotely(block: () -> T): T {
        depth++
        return try { block() } finally { depth-- }
    }
}
