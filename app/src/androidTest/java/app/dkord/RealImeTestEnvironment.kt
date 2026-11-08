package app.dkord

import android.app.Activity
import android.content.Context
import android.os.ParcelFileDescriptor
import android.os.PowerManager
import android.provider.Settings
import androidx.compose.ui.test.ComposeTestRule
import androidx.compose.ui.test.ComposeTimeoutException
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.test.platform.app.InstrumentationRegistry

/** Emulator fixture readiness, not a fake keyboard or a production inset/timeout workaround. */
internal fun prepareRealImeTest() {
    val automation = InstrumentationRegistry.getInstrumentation().uiAutomation
    for (command in listOf("input keyevent KEYCODE_WAKEUP", "wm dismiss-keyguard",
        "settings put secure show_ime_with_hard_keyboard 1")) {
        ParcelFileDescriptor.AutoCloseInputStream(automation.executeShellCommand(command)).use { it.readBytes() }
    }
}

internal fun ComposeTestRule.awaitFocusedImeWindow(activity: Activity) {
    try {
        waitUntil(10_000) {
            var focused = false
            runOnUiThread { focused = activity.hasWindowFocus() }
            focused
        }
    } catch (e: ComposeTimeoutException) {
        var detail = ""
        runOnUiThread { detail = realImeState(activity) }
        throw AssertionError("Real IME fixture window never focused: $detail", e)
    }
}

internal fun ComposeTestRule.awaitActualIme(activity: Activity, shown: Boolean, timeoutMs: Long, extra: () -> Boolean = { true }) {
    try {
        waitUntil(timeoutMs) {
            var visible = false
            runOnUiThread { visible = ViewCompat.getRootWindowInsets(activity.window.decorView)?.isVisible(WindowInsetsCompat.Type.ime()) == true }
            visible == shown && extra()
        }
    } catch (e: ComposeTimeoutException) {
        var detail = ""
        runOnUiThread { detail = realImeState(activity) }
        throw AssertionError("Real IME ${if (shown) "open" else "close"} timeout after ${timeoutMs}ms: $detail", e)
    }
}

private fun realImeState(activity: Activity): String {
    val insets = ViewCompat.getRootWindowInsets(activity.window.decorView)
    val resolver = activity.contentResolver
    return "focused=${activity.hasWindowFocus()}, interactive=${(activity.getSystemService(Context.POWER_SERVICE) as PowerManager).isInteractive}, " +
        "visible=${insets?.isVisible(WindowInsetsCompat.Type.ime())}, bottom=${insets?.getInsets(WindowInsetsCompat.Type.ime())?.bottom}, " +
        "showWithHardware=${Settings.Secure.getString(resolver, "show_ime_with_hard_keyboard")}, " +
        "defaultIme=${Settings.Secure.getString(resolver, Settings.Secure.DEFAULT_INPUT_METHOD)}, mode=${activity.window.attributes.softInputMode}"
}
