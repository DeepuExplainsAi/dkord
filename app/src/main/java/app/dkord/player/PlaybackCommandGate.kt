package app.dkord.player

/** Capture at enqueue time: remote commands stay silent and can expire before a lazy connection. */
internal class PlaybackCommandGate {
    data class Ticket(val report: Boolean, val isCurrent: () -> Boolean)
    private var depth = 0
    private var valid: () -> Boolean = { true }
    val report get() = depth == 0
    fun capture() = Ticket(report, valid)
    fun <T> remotely(isCurrent: () -> Boolean = { true }, block: () -> T): T {
        val previous = valid
        valid = { previous() && isCurrent() }
        depth++
        return try { block() } finally { depth--; valid = previous }
    }
}
