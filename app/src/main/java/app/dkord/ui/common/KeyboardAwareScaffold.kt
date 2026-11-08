package app.dkord.ui.common

import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.ime
import androidx.compose.foundation.layout.imePadding
import androidx.compose.material3.Scaffold
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity

/**
 * The app shell is the ONE owner of the IME inset. Destinations must consume scaffold padding,
 * not add imePadding again: nested scaffolds previously clipped Search halfway down a suggestion
 * and reserved a keyboard-sized black region above the actual keyboard.
 * Top bars and the navigation bar own their respective system-bar insets.
 */
@Composable
internal fun KeyboardAwareScaffold(
    bottomBar: @Composable () -> Unit,
    snackbarHost: @Composable () -> Unit = {},
    content: @Composable (PaddingValues) -> Unit,
) {
    val keyboardVisible = WindowInsets.ime.getBottom(LocalDensity.current) > 0
    Scaffold(
        modifier = Modifier.fillMaxSize().imePadding(),
        contentWindowInsets = WindowInsets(0, 0, 0, 0),
        bottomBar = { if (!keyboardVisible) bottomBar() },
        snackbarHost = snackbarHost,
        content = content,
    )
}
