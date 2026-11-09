package app.dkord

import android.content.res.Configuration
import androidx.activity.ComponentActivity
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.unit.Density
import app.dkord.ui.screens.AboutSection
import app.dkord.ui.screens.ListenTogetherLibrarySection
import app.dkord.ui.screens.PlaybackDiagnosticsItem
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import java.util.Locale

/** Real native UI semantics/taps, not screenshot or source-string-only acceptance. */
class AppPresentationTest {
    @get:Rule val rule = createAndroidComposeRule<ComponentActivity>()

    @Test fun library_has_one_global_room_section_without_selecting_a_song() {
        var opens = 0
        rule.setContent { MaterialTheme { Column { ListenTogetherLibrarySection { opens++ } } } }
        rule.onNodeWithText(rule.activity.getString(R.string.listen_together)).assertIsDisplayed()
        rule.onNodeWithTag("library-listen-together").assertHasClickAction().performClick()
        rule.runOnIdle { assertEquals(1, opens) }
    }

    @Test fun diagnostics_is_an_explicit_local_copy_action_not_a_repository_link() {
        var copies = 0
        rule.setContent { MaterialTheme { PlaybackDiagnosticsItem { copies++ } } }
        rule.onNodeWithTag("copy-playback-diagnostics").performClick()
        rule.runOnIdle { assertEquals(1, copies) }
        rule.onAllNodes(hasText("GitHub", substring = true, ignoreCase = true)).assertCountEquals(0)
        rule.onAllNodes(hasText("http", substring = true, ignoreCase = true)).assertCountEquals(0)
    }

    @Test fun about_is_short_non_clickable_professional_product_copy_with_copyright() {
        rule.setContent { MaterialTheme { Column { AboutSection() } } }
        rule.onNodeWithTag("about-dkord").assertIsDisplayed().assertHasNoClickAction()
        rule.onNodeWithText("© 2026 dKORD", substring = true).assertIsDisplayed()
        rule.onAllNodes(hasText("GitHub", substring = true, ignoreCase = true)).assertCountEquals(0)
        assertTrue(rule.activity.getString(R.string.about_text).length < 200)
    }

    @Test fun hindi_large_font_room_and_about_sections_wrap_and_remain_reachable() {
        val context = rule.activity.createConfigurationContext(Configuration(rule.activity.resources.configuration).apply {
            setLocale(Locale.forLanguageTag("hi"))
        })
        var opens = 0
        rule.setContent {
            val density = LocalDensity.current
            CompositionLocalProvider(LocalContext provides context, LocalConfiguration provides context.resources.configuration,
                LocalDensity provides Density(density.density, 1.35f)) {
                MaterialTheme { Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState())) {
                    ListenTogetherLibrarySection { opens++ }
                    AboutSection()
                } }
            }
        }
        rule.onNodeWithTag("library-listen-together").performScrollTo().assertIsDisplayed().performClick()
        rule.onNodeWithTag("about-dkord").performScrollTo().assertIsDisplayed()
        rule.onNodeWithText("© 2026 dKORD", substring = true).assertIsDisplayed()
        rule.runOnIdle { assertEquals(1, opens) }
    }
}
