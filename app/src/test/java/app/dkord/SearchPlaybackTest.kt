package app.dkord

import app.dkord.core.BrowseItem
import app.dkord.core.ItemKind
import app.dkord.core.Track
import app.dkord.ui.search.searchPlaybackQueue
import org.junit.Assert.*
import org.junit.Test

class SearchPlaybackTest {
    private fun row(id: String, duration: Long = 180) = BrowseItem(ItemKind.SONG, id, "Same song", track = Track(id, "Same song", "Creator", durationSec = duration))

    @Test fun tapping_a_later_match_plays_that_exact_upload_not_the_first_search_result() {
        val results = listOf(row("original"), row("chosen-cover"), row("slowed"))
        assertEquals(listOf(results[1].track), searchPlaybackQueue(results[1]))
    }

    @Test fun matching_versions_and_an_unrequested_hour_mix_do_not_become_the_play_queue() {
        val results = listOf(row("chosen"), row("slowed"), row("hour-mix", 3600))
        assertEquals(listOf("chosen"), searchPlaybackQueue(results[0]).map { it.id })
    }

    @Test fun an_explicitly_chosen_long_mix_is_still_playable_without_a_manual_search_duration_filter() {
        val chosen = row("requested-hour-mix", 3600)
        assertEquals(listOf(chosen.track), searchPlaybackQueue(chosen))
    }

    @Test fun album_playlist_and_artist_rows_keep_navigation_not_song_playback() {
        for (kind in listOf(ItemKind.ALBUM, ItemKind.PLAYLIST, ItemKind.ARTIST)) {
            assertTrue(searchPlaybackQueue(BrowseItem(kind, "id", "Title")).isEmpty())
        }
    }

    @Test fun a_missing_track_cannot_silently_fall_back_to_another_result() {
        assertTrue(searchPlaybackQueue(BrowseItem(ItemKind.SONG, "id", "Missing metadata")).isEmpty())
    }
}
