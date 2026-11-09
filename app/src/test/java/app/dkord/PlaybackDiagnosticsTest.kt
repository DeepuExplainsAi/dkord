package app.dkord

import app.dkord.core.DebugLog
import app.dkord.data.stream.ExtractorHealth
import org.junit.After
import org.junit.Assert.*
import org.junit.Test

class PlaybackDiagnosticsTest {
    @After fun clean() { DebugLog.clear() }

    @Test fun local_report_removes_repository_addresses_and_secrets_before_copying() {
        DebugLog.clear()
        DebugLog.e("playback", "Request failed https://github.com/owner/repository/issues/new?sig=secret SID=private")
        val report = ExtractorHealth.reportBody("Android test device")
        assertTrue(report.contains("dKORD playback diagnostics"))
        assertTrue(report.contains("Request failed"))
        assertFalse(report.contains("https://"))
        assertFalse(report.contains("github.com"))
        assertFalse(report.contains("private"))
        assertFalse(report.contains("secret"))
    }

    @Test fun address_is_redacted_before_log_truncation_and_report_is_bounded() {
        DebugLog.clear()
        DebugLog.e("playback", "https://github.com/owner/" + "repository-path".repeat(600))
        val report = ExtractorHealth.reportBody("Android test device")
        assertFalse(report.contains("repository-path"))
        assertTrue(report.contains("[network address]"))
        assertTrue(report.length < 6400)
    }
}
