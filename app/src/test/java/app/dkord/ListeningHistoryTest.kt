package app.dkord

import app.dkord.core.*
import org.junit.Assert.*
import org.junit.Test
import java.time.Instant
import java.time.ZoneId
import java.util.Locale

class ListeningHistoryTest {
    private fun entry(id: String, time: Long, title: String = "Song $id", artist: String = "Artist", album: String? = null) =
        ListeningEntry(Track(id, title, artist, album), time)
    private fun result(entries: List<ListeningEntry>, query: String = "", filter: ListeningFilter = ListeningFilter.ALL,
                       liked: Set<String> = emptySet(), downloaded: Set<String> = emptySet()) =
        listeningHistory(entries, query, filter, liked, downloaded).map { it.track.id }

    @Test fun newest_real_play_wins_and_same_title_different_uploads_are_preserved() {
        val rows = listOf(entry("a", 10, "Same"), entry("b", 20, "Same"), entry("a", 30, "Same"))
        assertEquals(listOf("a", "b"), result(rows))
    }
    @Test fun timestamp_ties_have_stable_id_order() {
        assertEquals(listOf("a", "b"), result(listOf(entry("b", 10), entry("a", 10))))
    }
    @Test fun blank_ids_or_titles_are_not_fabricated_into_tracks() {
        assertEquals(listOf("ok"), result(listOf(entry("", 10), entry("empty", 10, " "), entry("ok", 1))))
    }
    @Test fun local_search_matches_all_words_across_title_artist_and_album() {
        val rows = listOf(entry("a", 3, "Evening Song", "Real Singer", "Piano sessions"), entry("b", 4, "Evening", "Other"))
        assertEquals(listOf("a"), result(rows, "  piano  SINGER\tevening "))
        assertTrue(result(rows, "piano missing").isEmpty())
    }
    @Test fun hindi_vowel_and_combining_marks_are_preserved() {
        val rows = listOf(entry("a", 10, "तेरी मेरी कहानी", "गायक"), entry("b", 20, "अन्य गीत"))
        assertEquals(listOf("a"), result(rows, "मेरी गायक"))
    }
    @Test fun unicode_compatibility_spaces_and_case_do_not_break_local_search() {
        assertEquals(listOf("a"), result(listOf(entry("a", 1, "ＦＵＬＬ Song", "Artist")), "full\u00a0SONG"))
    }
    @Test fun search_is_independent_of_phone_turkish_case_rules() {
        val old = Locale.getDefault()
        try {
            Locale.setDefault(Locale.forLanguageTag("tr-TR"))
            assertEquals(listOf("a"), result(listOf(entry("a", 1, "INDIGO")), "indigo"))
        } finally { Locale.setDefault(old) }
    }
    @Test fun filters_use_real_liked_and_completed_download_ids_without_reordering() {
        val rows = listOf(entry("a", 20), entry("b", 10), entry("c", 30))
        assertEquals(listOf("c", "b"), result(rows, filter = ListeningFilter.LIKED, liked = setOf("b", "c", "absent")))
        assertEquals(listOf("a"), result(rows, filter = ListeningFilter.DOWNLOADED, downloaded = setOf("a")))
    }
    @Test fun unknown_or_missing_downloads_do_not_become_offline_results() {
        assertTrue(result(listOf(entry("a", 10)), filter = ListeningFilter.DOWNLOADED).isEmpty())
    }
    @Test fun generated_local_audio_stays_visible_and_is_never_rewritten_to_a_provider_id() {
        val id = LOCAL_STUDIO_PREFIX + "real-local-project"
        assertEquals(listOf(id), result(listOf(entry(id, 10, "My saved mix"))))
    }
    @Test fun empty_history_and_no_match_stay_empty() {
        assertTrue(result(emptyList()).isEmpty())
        assertTrue(result(listOf(entry("a", 10)), "unmatched").isEmpty())
    }
    @Test fun calendar_groups_follow_device_zone_not_utc() {
        val now = Instant.parse("2026-11-07T20:00:00Z").toEpochMilli()
        val played = Instant.parse("2026-11-07T17:00:00Z").toEpochMilli()
        assertEquals(ListeningDay.YESTERDAY, listeningDay(played, now, ZoneId.of("Asia/Kolkata")))
        assertEquals(ListeningDay.TODAY, listeningDay(played, now, ZoneId.of("UTC")))
    }
    @Test fun yesterday_is_calendar_based_across_dst_not_a_24hour_bucket() {
        val now = Instant.parse("2026-03-09T04:30:00Z").toEpochMilli()
        val played = Instant.parse("2026-03-08T06:30:00Z").toEpochMilli()
        assertEquals(ListeningDay.YESTERDAY, listeningDay(played, now, ZoneId.of("America/New_York")))
    }
    @Test fun older_dates_are_earlier_without_inventing_play_counts() {
        assertEquals(ListeningDay.EARLIER, listeningDay(1, Instant.parse("2026-11-07T12:00:00Z").toEpochMilli(), ZoneId.of("UTC")))
    }
    @Test fun progress_is_finite_clamped_and_handles_unknown_or_bad_duration() {
        assertEquals(0.5f, listeningProgress(50, 100), 0.0001f)
        assertEquals(0f, listeningProgress(10, 0), 0.0001f)
        assertEquals(0f, listeningProgress(-10, 100), 0.0001f)
        assertEquals(1f, listeningProgress(Long.MAX_VALUE, 100), 0.0001f)
    }
}
