package app.dkord

import android.content.res.Configuration
import androidx.activity.ComponentActivity
import androidx.compose.foundation.layout.Column
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.unit.Density
import app.dkord.core.BrowseItem
import app.dkord.core.ItemKind
import app.dkord.core.Shelf
import app.dkord.core.Track
import app.dkord.ui.common.ShelfRow
import app.dkord.ui.screens.SearchPlaybackRow
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import java.util.Locale

/** Actual production Home shelf/Search row routing, offline: no mock live-recommendation claim. */
class RelatedPlaybackRoutingTest {
    @get:Rule val rule = createAndroidComposeRule<ComponentActivity>()
    private val first = Track("one", "First song", "First artist", "Album one", 180)
    private val chosen = Track("two", "Chosen song", "Second artist", "Album two", 200)
    private fun item(track: Track) = BrowseItem(ItemKind.SONG, track.id, track.title, track.artist, track = track)

    @Test fun home_song_tap_is_exactly_one_selected_song_and_play_all_is_a_separate_explicit_action() {
        val shelf = Shelf("Sad Songs", listOf(item(first), item(chosen)), "hindi sad songs")
        var related: Pair<Track, String>? = null
        var whole: Pair<List<Track>, Int>? = null
        var opened = 0
        rule.setContent { MaterialTheme {
            ShelfRow(shelf, { opened++ }, { tracks, index -> whole = tracks to index }, { track, hint -> related = track to hint })
        } }
        rule.runOnIdle { assertNull(related); assertNull(whole) }
        rule.onNodeWithText(chosen.title).assertIsDisplayed().performClick()
        rule.runOnIdle { assertEquals(chosen to "hindi sad songs", related); assertNull(whole); assertEquals(0, opened) }
        val description = rule.activity.getString(R.string.shelf_play_all_description, shelf.title)
        rule.onNodeWithContentDescription(description).assertIsDisplayed().assertIsEnabled().performClick()
        rule.runOnIdle { assertEquals(listOf(first, chosen) to 0, whole) }
    }

    @Test fun hindi_larger_font_home_action_is_visible_and_preserves_internal_choliwood_context() {
        val ctx = rule.activity.createConfigurationContext(Configuration(rule.activity.resources.configuration).apply { setLocale(Locale.forLanguageTag("hi")) })
        val shelf = Shelf("छॉलीवुड के गाने", listOf(item(first), item(chosen)), "popular bhojpuri songs")
        var related: Pair<Track, String>? = null
        var whole: List<Track>? = null
        rule.setContent {
            val density = LocalDensity.current
            CompositionLocalProvider(LocalContext provides ctx, LocalConfiguration provides ctx.resources.configuration,
                LocalDensity provides Density(density.density, 1.3f)) {
                MaterialTheme { ShelfRow(shelf, {}, { tracks, _ -> whole = tracks }, { track, hint -> related = track to hint }) }
            }
        }
        rule.onNodeWithText(chosen.title).assertIsDisplayed().performClick()
        rule.runOnIdle { assertEquals(chosen to shelf.radioHint, related); assertNull(whole) }
        val description = ctx.getString(R.string.shelf_play_all_description, shelf.title)
        rule.onNodeWithContentDescription(description).assertIsDisplayed().assertIsEnabled()
        val labelHeight = rule.onNodeWithText(ctx.getString(R.string.shelf_play_all), useUnmergedTree = true).fetchSemanticsNode().boundsInRoot.height
        assertTrue("Hindi action must inherit larger font", labelHeight >= 20 * rule.activity.resources.displayMetrics.density * 1.3f * 0.85f)
        rule.onNodeWithContentDescription(description).performClick()
        rule.runOnIdle { assertEquals(listOf(first, chosen), whole) }
    }

    @Test fun explicit_album_playlist_or_release_category_shelf_keeps_its_full_queue_and_selected_index() {
        val shelf = Shelf("Explicit category", listOf(item(first), item(chosen)))
        var result: Pair<List<Track>, Int>? = null
        rule.setContent { MaterialTheme { ShelfRow(shelf, {}, { tracks, index -> result = tracks to index }) } }
        rule.onNodeWithText(chosen.title).assertIsDisplayed().performClick()
        rule.runOnIdle { assertEquals(listOf(first, chosen) to 1, result) }
        rule.onNodeWithText(rule.activity.getString(R.string.shelf_play_all)).assertDoesNotExist()
    }

    @Test fun search_row_preserves_chosen_metadata_and_submitted_radio_context_without_queuing_results() {
        var related: Pair<Track, String>? = null
        var genericPlay = 0
        var opened = 0
        var menu: Track? = null
        rule.setContent { MaterialTheme {
            SearchPlaybackRow(item(chosen), "hindi sad ambient", { opened++ }, { _, _ -> genericPlay++ },
                { menu = it }, { track, hint -> related = track to hint })
        } }
        rule.onNodeWithText(chosen.title).assertIsDisplayed().performClick()
        rule.runOnIdle { assertEquals(chosen to "hindi sad ambient", related); assertEquals(0, genericPlay); assertEquals(0, opened) }
        rule.onNodeWithContentDescription(rule.activity.getString(R.string.more)).performClick()
        rule.runOnIdle { assertEquals(chosen, menu); assertEquals(chosen to "hindi sad ambient", related) }
    }

    @Test fun non_song_search_results_still_navigate_without_starting_radio_or_fake_playback() {
        val items = listOf(ItemKind.ALBUM, ItemKind.ARTIST, ItemKind.PLAYLIST, ItemKind.MOOD).map {
            BrowseItem(it, "browse-${it.name}", "Browse ${it.name}")
        }
        val opened = mutableListOf<BrowseItem>()
        var plays = 0
        rule.setContent { MaterialTheme { Column {
            items.forEach { entry -> SearchPlaybackRow(entry, "hindi sad", { opened += it }, { _, _ -> plays++ }, {}, { _, _ -> plays++ }) }
        } } }
        items.forEach { rule.onNodeWithText(it.title).assertIsDisplayed().performClick() }
        rule.runOnIdle { assertEquals(items, opened); assertEquals(0, plays) }
    }

    @Test fun search_without_a_context_callback_still_starts_only_the_chosen_song() {
        var played: Pair<List<Track>, Int>? = null
        rule.setContent { MaterialTheme {
            SearchPlaybackRow(item(chosen), "hindi sad", {}, { tracks, index -> played = tracks to index }, {})
        } }
        rule.onNodeWithText(chosen.title).performClick()
        rule.runOnIdle { assertEquals(listOf(chosen) to 0, played) }
    }
}
