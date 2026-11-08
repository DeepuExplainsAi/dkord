package app.dkord

import android.content.res.Configuration
import androidx.activity.ComponentActivity
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.*
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.unit.Density
import app.dkord.data.db.DownloadLocation
import app.dkord.ui.common.DownloadDestinationChoices
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import java.util.Locale

class DownloadDestinationTest {
    @get:Rule val rule = createAndroidComposeRule<ComponentActivity>()
    @Test fun explicit_private_choice_does_not_also_request_a_device_export() = choice(DownloadLocation.APP)
    @Test fun explicit_device_choice_is_not_silently_private_only() = choice(DownloadLocation.DEVICE)
    private fun choice(want: DownloadLocation) {
        val selected = mutableListOf<DownloadLocation>()
        rule.setContent { MaterialTheme { DownloadDestinationChoices({ selected += it }, {}) } }
        rule.onNodeWithTag(if (want == DownloadLocation.APP) "download-in-dkord" else "download-to-device").performScrollTo().performClick()
        rule.runOnIdle { assertEquals(listOf(want), selected) }
    }
    @Test fun hindi_large_font_cancel_queues_neither_destination() {
        val ctx = rule.activity.createConfigurationContext(Configuration(rule.activity.resources.configuration).apply { setLocale(Locale.forLanguageTag("hi")) })
        var chosen = 0; var cancelled = 0
        rule.setContent {
            val density = LocalDensity.current
            CompositionLocalProvider(LocalContext provides ctx, LocalDensity provides Density(density.density, 1.3f)) {
                MaterialTheme { DownloadDestinationChoices({ chosen++ }, { cancelled++ }) }
            }
        }
        // The selection buttons use the owner locale even though AlertDialog owns a separate window.
        rule.onNodeWithText(ctx.getString(R.string.download_in_dkord)).assertExists()
        rule.onNodeWithText(ctx.getString(R.string.cancel)).assertIsDisplayed().performClick()
        rule.runOnIdle { assertEquals(0, chosen); assertEquals(1, cancelled) }
    }
}
