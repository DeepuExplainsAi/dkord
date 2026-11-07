package app.dkord

import app.dkord.core.BrowseItem
import app.dkord.core.ItemKind
import app.dkord.core.Track
import app.dkord.ui.search.searchResultSupportingText
import org.junit.Assert.*
import org.junit.Test

class SearchResultPresentationTest {
    private fun item(creator: String = "Cover creator", duration: Long = 225) = BrowseItem(
        ItemKind.SONG, "AbCdEf123_-", "The same song title", creator,
        track = Track("AbCdEf123_-", "The same song title", creator, durationSec = duration),
    )

    @Test fun search_supporting_text_keeps_the_creator_and_shows_the_known_duration() {
        assertEquals("Cover creator • 3:45", searchResultSupportingText(item()))
    }

    @Test fun short_clips_and_multi_hour_instrumentals_are_displayed_not_classified_or_hidden() {
        assertEquals("Cover creator • 0:20", searchResultSupportingText(item(duration = 20)))
        assertEquals("Cover creator • 1:00:00", searchResultSupportingText(item(duration = 3600)))
        assertEquals("Cover creator • 3:00:01", searchResultSupportingText(item(duration = 10801)))
    }

    @Test fun unknown_or_invalid_durations_do_not_fabricate_zero_time_or_live_labels() {
        for (duration in listOf(0L, -1L, Long.MIN_VALUE, Long.MAX_VALUE)) {
            assertEquals("Cover creator", searchResultSupportingText(item(duration = duration)))
        }
    }

    @Test fun missing_creator_does_not_add_a_leading_separator() {
        assertEquals("3:45", searchResultSupportingText(item(creator = "")))
        assertEquals("", searchResultSupportingText(item(creator = " ", duration = 0)))
    }

    @Test fun album_playlist_and_channel_metadata_are_not_changed_by_audio_duration_presentation() {
        for (kind in listOf(ItemKind.ALBUM, ItemKind.PLAYLIST, ItemKind.ARTIST)) {
            assertEquals("Creator", searchResultSupportingText(BrowseItem(kind, "id", "Title", "Creator")))
        }
    }
}
