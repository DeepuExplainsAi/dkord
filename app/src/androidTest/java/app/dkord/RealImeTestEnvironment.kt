package app.dkord

import android.app.Activity
import android.app.KeyguardManager
import android.content.Context
import android.os.ParcelFileDescriptor
import android.os.PowerManager
import android.provider.Settings
import androidx.compose.ui.test.junit4.ComposeTestRule
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
        throw AssertionError("Real IME fixture window never focused: ${focusedWindowOwner()}; $detail", e)
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
        throw AssertionError("Real IME ${if (shown) "open" else "close"} timeout after ${timeoutMs}ms: ${focusedWindowOwner()}; $detail", e)
    }
}

/** Only on failure, outside the UI thread. Report the actual focus owner, not a guessed overlay. */
private fun focusedWindowOwner(): String = runCatching {
    val automation = InstrumentationRegistry.getInstrumentation().uiAutomation
    ParcelFileDescriptor.AutoCloseInputStream(automation.executeShellCommand("dumpsys window")).bufferedReader().use { reader ->
        reader.lineSequence().filter { "mCurrentFocus=" in it || "mFocusedApp=" in it }
            .take(2).joinToString("; ") { it.trim().take(150) }.ifEmpty { "window focus owner unavailable" }
    }
}.getOrDefault("window focus diagnostic unavailable")

private fun realImeState(activity: Activity): String {
    val decor = activity.window.decorView
    val insets = ViewCompat.getRootWindowInsets(decor)
    val resolver = activity.contentResolver
    val keyguard = activity.getSystemService(Context.KEYGUARD_SERVICE) as KeyguardManager
    return "focused=${activity.hasWindowFocus()}, attached=${decor.isAttachedToWindow}, shown=${decor.isShown}, " +
        "locked=${keyguard.isKeyguardLocked}/${keyguard.isDeviceLocked}, " +
        "interactive=${(activity.getSystemService(Context.POWER_SERVICE) as PowerManager).isInteractive}, " +
        "visible=${insets?.isVisible(WindowInsetsCompat.Type.ime())}, bottom=${insets?.getInsets(WindowInsetsCompat.Type.ime())?.bottom}, " +
        "showWithHardware=${Settings.Secure.getString(resolver, "show_ime_with_hard_keyboard")}, " +
        "defaultIme=${Settings.Secure.getString(resolver, Settings.Secure.DEFAULT_INPUT_METHOD)}, " +
        "flags=${activity.window.attributes.flags.toString(16)}, mode=${activity.window.attributes.softInputMode}"
}
