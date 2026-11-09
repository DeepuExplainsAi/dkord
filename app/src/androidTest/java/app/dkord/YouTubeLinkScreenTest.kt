package app.dkord

import android.content.ClipData
import android.content.ClipboardManager
import android.content.res.Configuration
import androidx.activity.ComponentActivity
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.unit.Density
import app.dkord.core.Track
import app.dkord.data.links.YouTubeLinkException
import app.dkord.data.links.YouTubeLinkProblem
import app.dkord.data.links.YouTubeLinkSource
import app.dkord.data.links.YouTubeVideoLink
import app.dkord.ui.links.YouTubeLinkController
import app.dkord.ui.screens.YouTubeLinkEntry
import app.dkord.ui.screens.YouTubeLinkPage
import kotlinx.coroutines.awaitCancellation
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import java.util.Locale

/** Actual production composables and Android clipboard. Metadata is an explicit offline fixture. */
class YouTubeLinkScreenTest {
    @get:Rule val rule = createAndroidComposeRule<ComponentActivity>()
    private val raw = "https://music.youtube.com/watch?v=AbCdEf012_-&list=PL_playlist&si=share"
    private val fixture = Track("AbCdEf012_-", "Rare upload — audio flip (offline fixture)", "Original uploader", durationSec = 19)
    private val calls = mutableListOf<String>()
    private val messages = mutableListOf<String>()
    private var played: Pair<List<Track>, Int>? = null
    private var menu: Track? = null
    private var backs = 0
    private lateinit var controller: YouTubeLinkController

    private fun page(hindi: Boolean = false, find: suspend (YouTubeVideoLink) -> Track = { fixture.copy(id = it.videoId) }) {
        val context = if (hindi) rule.activity.createConfigurationContext(Configuration(rule.activity.resources.configuration).apply {
            setLocale(Locale.forLanguageTag("hi"))
        }) else rule.activity
        rule.setContent {
            val density = LocalDensity.current
            val scope = rememberCoroutineScope()
            controller = remember { YouTubeLinkController(YouTubeLinkSource { calls += it.url; find(it) }, scope) }
            CompositionLocalProvider(LocalContext provides context, LocalConfiguration provides context.resources.configuration,
                LocalDensity provides Density(density.density, if (hindi) 1.3f else density.fontScale)) {
                MaterialTheme { YouTubeLinkPage(controller, { backs++ }, { tracks, index -> played = tracks to index }, { menu = it }, { messages += it }) }
            }
        }
    }

    private fun submit(input: String = raw) {
        val field = rule.onNodeWithTag("youtube-link-input")
        field.performTextReplacement(input)
        field.performImeAction()
        rule.waitForIdle()
    }

    @Test fun labelled_entry_is_separate_and_does_not_change_search_or_play_anything() {
        var opened = 0
        rule.setContent { MaterialTheme { YouTubeLinkEntry({ opened++ }) } }
        rule.onNodeWithTag("open-youtube-link").assertIsDisplayed().performClick()
        rule.runOnIdle { assertEquals(1, opened); assertNull(played); assertTrue(calls.isEmpty()) }
    }

    @Test fun clipboard_paste_preview_and_play_are_three_deliberate_actions_using_the_exact_upload() {
        rule.activity.getSystemService(ClipboardManager::class.java).setPrimaryClip(ClipData.newPlainText("Link", raw))
        page()
        rule.runOnIdle { assertEquals("", controller.state.value.input); assertTrue(calls.isEmpty()); assertNull(played) }
        rule.onNodeWithTag("youtube-link-paste").assertIsDisplayed().performClick()
        rule.onNodeWithTag("youtube-link-input").assertTextContains(raw)
        rule.runOnIdle { assertTrue(calls.isEmpty()); assertNull(controller.state.value.track); assertNull(played) }
        rule.onNodeWithTag("youtube-link-resolve").performClick()
        rule.onNodeWithTag("youtube-link-preview").performScrollTo().assertIsDisplayed()
        rule.onNodeWithText(fixture.title).assertIsDisplayed()
        rule.runOnIdle { assertEquals(listOf("https://www.youtube.com/watch?v=AbCdEf012_-"), calls); assertNull(played) }
        rule.onNodeWithContentDescription(rule.activity.getString(R.string.more)).performScrollTo().performClick()
        rule.runOnIdle { assertEquals(fixture, menu); assertNull(played) }
        rule.onNodeWithTag("youtube-link-play").performScrollTo().performClick()
        rule.runOnIdle { assertEquals(listOf(fixture) to 0, played) }
    }

    @Test fun malformed_and_playlist_only_links_show_real_errors_without_provider_requests() {
        page(); submit("https://untrusted.test/watch?v=AbCdEf012_-")
        rule.onNodeWithTag("youtube-link-error").assertTextEquals(rule.activity.getString(R.string.youtube_link_invalid))
        rule.runOnIdle { assertTrue(calls.isEmpty()); assertNull(played) }
        submit("https://youtube.com/playlist?list=PL_playlist")
        rule.onNodeWithTag("youtube-link-error").assertTextEquals(rule.activity.getString(R.string.youtube_link_playlist_only))
        rule.onNodeWithTag("youtube-link-preview").assertDoesNotExist()
        rule.runOnIdle { assertTrue(calls.isEmpty()); assertNull(played) }
    }

    @Test fun unavailable_upload_does_not_create_a_fake_preview_or_issue_a_play_command() {
        page(find = { throw YouTubeLinkException(YouTubeLinkProblem.PRIVATE) }); submit()
        rule.onNodeWithTag("youtube-link-error").assertTextEquals(rule.activity.getString(R.string.err_private))
        rule.onNodeWithTag("youtube-link-play").assertDoesNotExist(); rule.onNodeWithTag("youtube-link-preview").assertDoesNotExist()
        rule.runOnIdle { assertEquals(1, calls.size); assertNull(played); assertNull(menu) }
        rule.onNodeWithContentDescription(rule.activity.getString(R.string.back)).performClick()
        rule.runOnIdle { assertEquals(1, backs) }
    }

    @Test fun editing_a_preview_removes_stale_play_and_menu_actions_without_resolving_again() {
        page(); submit()
        rule.onNodeWithTag("youtube-link-preview").assertExists()
        rule.onNodeWithTag("youtube-link-input").performScrollTo().performTextReplacement("https://youtu.be/ZyXwVu987_-")
        rule.onNodeWithTag("youtube-link-preview").assertDoesNotExist(); rule.onNodeWithTag("youtube-link-play").assertDoesNotExist()
        rule.runOnIdle { assertEquals(1, calls.size); assertNull(played); assertNull(menu) }
    }

    @Test fun loading_can_be_cancelled_without_a_failure_or_implicit_playback() {
        page(find = { awaitCancellation() }); submit()
        rule.onNodeWithTag("youtube-link-cancel").performScrollTo().assertIsDisplayed().performClick()
        rule.onNodeWithTag("youtube-link-resolve").assertIsEnabled()
        rule.onNodeWithTag("youtube-link-error").assertDoesNotExist(); rule.onNodeWithTag("youtube-link-preview").assertDoesNotExist()
        rule.runOnIdle { assertFalse(controller.state.value.loading); assertEquals(raw, controller.state.value.input); assertNull(played) }
    }

    @Test fun hindi_larger_font_form_and_exact_preview_remain_scrollable_with_the_same_actions() {
        page(hindi = true)
        rule.onNodeWithText("लिंक पेस्ट करें").assertIsDisplayed()
        rule.onNodeWithText("वीडियो दिखाएँ").assertIsDisplayed()
        submit("https://youtube.com/shorts/AbCdEf012_-?si=share")
        rule.onNodeWithTag("youtube-link-play").performScrollTo().assertIsDisplayed()
        rule.onNodeWithText("चलाएँ").assertIsDisplayed().performClick()
        rule.runOnIdle { assertEquals(listOf(fixture) to 0, played); assertEquals(listOf("https://www.youtube.com/watch?v=AbCdEf012_-"), calls) }
    }
}
