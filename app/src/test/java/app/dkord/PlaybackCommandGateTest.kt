package app.dkord

import app.dkord.player.PlaybackCommandGate
import org.junit.Assert.*
import org.junit.Test

class PlaybackCommandGateTest {
    @Test fun explicit_commands_report_but_nested_remote_applications_do_not() {
        val gate = PlaybackCommandGate()
        assertTrue(gate.report)
        gate.remotely { assertFalse(gate.report); gate.remotely { assertFalse(gate.report) }; assertFalse(gate.report) }
        assertTrue(gate.report)
    }
    @Test fun remote_suppression_is_captured_before_a_lazy_controller_callback_is_queued() {
        val gate = PlaybackCommandGate(); val callbacks = mutableListOf<() -> Boolean>()
        fun enqueue() { val captured = gate.report; callbacks += { captured } }
        gate.remotely { enqueue() }; enqueue()
        assertFalse(callbacks[0]()); assertTrue(callbacks[1]())
    }
    @Test fun failed_remote_application_does_not_mute_later_manual_commands() {
        val gate = PlaybackCommandGate()
        try { gate.remotely { throw IllegalStateException("media not ready") } } catch (_: IllegalStateException) { }
        assertTrue(gate.report)
    }
    @Test fun deferred_remote_callbacks_expire_but_normal_local_commands_remain_valid() {
        val gate = PlaybackCommandGate(); var roomAlive = true
        val remote = gate.remotely(isCurrent = { roomAlive }) { gate.capture() }
        val local = gate.capture()
        assertTrue(remote.isCurrent()); assertFalse(remote.report)
        roomAlive = false
        assertFalse(remote.isCurrent()); assertTrue(local.isCurrent()); assertTrue(local.report)
    }
    @Test fun nested_remote_tokens_keep_parent_validity_after_scope_exit_and_failure() {
        val gate = PlaybackCommandGate(); var parentAlive = true
        val ticket = gate.remotely(isCurrent = { parentAlive }) {
            gate.remotely(isCurrent = { true }) { gate.capture() }
        }
        parentAlive = false
        assertFalse(ticket.isCurrent()); assertTrue(gate.capture().isCurrent())
    }

}
