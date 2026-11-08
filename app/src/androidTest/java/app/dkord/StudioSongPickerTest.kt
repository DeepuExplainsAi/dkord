package app.dkord

import android.content.res.Configuration
import android.view.View
import android.view.inspector.WindowInspector
import androidx.activity.ComponentActivity
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.*
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.unit.Density
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import app.dkord.core.*
import app.dkord.data.search.*
import app.dkord.data.yt.SearchFilter
import app.dkord.ui.studio.*
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import java.util.Locale
import kotlin.math.abs

/** Uses the dialog's own real Window/IME, not the activity's now-unfocused insets. API35 CI fixture. */
class StudioSongPickerTest {
    @get:Rule val rule = createAndroidComposeRule<ComponentActivity>()
    @Test fun english_online_picker_accepts_real_ime_search_and_selected_song_without_download_queue() = verify(Locale.ENGLISH, 1f)
    @Test fun hindi_large_font_online_picker_keeps_single_ime_inset_and_visible_actions() = verify(Locale.forLanguageTag("hi"), 1.3f)
    private fun verify(locale: Locale, scale: Float) {
        prepareRealImeTest()
        val context = rule.activity.createConfigurationContext(Configuration(rule.activity.resources.configuration).apply { setLocale(locale) })
        val track = Track("online00001", "संगवारी — Choliwood", "Singer")
        val requests = mutableListOf<Pair<String, SearchFilter>>()
        var selected: Track? = null
        val source = object : SearchSource {
            override suspend fun suggestions(query: String): List<String> = error("No implicit network")
            override suspend fun search(query: String, filter: SearchFilter): SearchPage {
                requests += query to filter
                return SearchPage(listOf(BrowseItem(ItemKind.SONG, track.id, track.title, track = track)))
            }
            override suspend fun more(token: SearchPageToken): SearchPage = error("No cursor")
        }
        rule.setContent {
            val density = LocalDensity.current
            val scope = rememberCoroutineScope()
            val controller = remember { StudioSongSearch(source, scope) }
            CompositionLocalProvider(LocalContext provides context, LocalDensity provides Density(density.density, scale)) {
                MaterialTheme { StudioSongPickerContent(controller, { selected = it }, {}) }
            }
        }
        var dialog: View? = null
        rule.waitUntil(10_000) {
            rule.runOnUiThread {
                dialog = WindowInspector.getGlobalWindowViews().firstOrNull {
                    it !== rule.activity.window.decorView && it.hasWindowFocus() && it.isShown
                }
            }
            dialog != null
        }
        rule.onNodeWithTag("studio-song-query").performClick().performTextInput("संगवारी Choliwood")
        rule.waitUntil(10_000) {
            var shown = false
            rule.runOnUiThread { shown = ViewCompat.getRootWindowInsets(requireNotNull(dialog))?.isVisible(WindowInsetsCompat.Type.ime()) == true }
            shown
        }
        rule.onNodeWithText(context.getString(R.string.close)).assertIsDisplayed()
        var visibleBottom = 0f
        rule.runOnUiThread {
            val root = requireNotNull(dialog)
            visibleBottom = root.height - (ViewCompat.getRootWindowInsets(root)?.getInsets(WindowInsetsCompat.Type.ime())?.bottom ?: 0).toFloat()
        }
        val bottom = rule.onNodeWithTag("studio-song-results").fetchSemanticsNode().boundsInRoot.bottom
        assertTrue("Single own-window IME inset: visible=$visibleBottom content=$bottom", abs(visibleBottom - bottom) < 36 * rule.activity.resources.displayMetrics.density)
        rule.onNodeWithTag("studio-song-query").performImeAction()
        rule.waitUntil(8_000) {
            var shown = true
            rule.runOnUiThread { shown = ViewCompat.getRootWindowInsets(requireNotNull(dialog))?.isVisible(WindowInsetsCompat.Type.ime()) == true }
            !shown
        }
        rule.onNodeWithTag("studio-song-${track.id}").assertIsDisplayed().performClick()
        rule.runOnIdle {
            assertEquals(listOf("संगवारी Choliwood" to SearchFilter.SONGS), requests)
            assertEquals(track, selected)
        }
    }
}
