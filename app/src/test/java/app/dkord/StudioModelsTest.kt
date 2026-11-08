package app.dkord

import app.dkord.core.*
import app.dkord.data.room.*
import app.dkord.data.studio.*
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import org.junit.Assert.*
import org.junit.Test

class StudioModelsTest {
    private val source = StudioSource(studioId(), "One", "", 600_001, "audio/wav").let { it.copy(fileName = "${it.id}.audio") }
    private val other = StudioSource(studioId(), "Two", "", 7_200_000, "audio/mp4").let { it.copy(fileName = "${it.id}.audio") }
    private fun project() = StudioProject(studioId(), "My audio", listOf(source, other))
    @Test fun seconds_and_precise_colon_times_are_not_limited_to_short_fixed_presets() {
        assertEquals(1L, parseStudioTime("0.001"))
        assertEquals(12_345L, parseStudioTime("12.345"))
        assertEquals(62_100L, parseStudioTime("1:02.1"))
        assertEquals(7_200_001L, parseStudioTime("2:00:00.001"))
        assertEquals(600_000L, parseStudioTime("600"))
        assertEquals(7_200_001L, parseStudioTime(studioTime(7_200_001)))
    }
    @Test fun invalid_negative_fractional_overflow_and_bad_colon_input_is_rejected() {
        listOf("", "-1", "+1:00", "1:60", "1:60:00", "1:2:3:4", "NaN", "1e3", "0.0001", "9223372036854775807", "1:", ".").forEach { assertNull(it, parseStudioTime(it)) }
    }
    @Test fun multiple_arbitrary_ranges_from_one_or_more_sources_keep_millisecond_precision() {
        val p = project().withClip(source.id, 13, 117).withClip(other.id, 999, 7_199_999).withClip(source.id, 600_000, 600_001)
        assertEquals(listOf(104L, 7_199_000L, 1L), p.clips.map { it.durationMs })
        assertEquals(7_199_105L, p.durationMs)
    }
    @Test fun editing_a_range_replaces_that_occurrence_not_every_clip_of_the_song() {
        val p = project().withClip(source.id, 0, 100).withClip(source.id, 100, 300)
        val changed = p.withClip(source.id, 2, 52, p.clips.first().id)
        assertEquals(2, changed.clips.size); assertEquals(250L, changed.durationMs)
        assertEquals(p.clips[1], changed.clips[1])
    }
    @Test fun reorder_and_remove_preserve_the_remaining_source_ranges() {
        val p = project().withClip(source.id, 0, 10).withClip(other.id, 10, 30).withClip(source.id, 30, 60)
        val moved = p.moveClip(p.clips.last().id, -1)
        assertEquals(listOf(p.clips[0], p.clips[2], p.clips[1]), moved.clips)
        assertEquals(moved, moved.moveClip("missing", 1))
        assertEquals(40L, moved.copy(clips = moved.clips.filterNot { it.id == p.clips[1].id }).validate().durationMs)
    }
    @Test fun persisted_project_round_trip_includes_order_sources_and_saved_output_without_remote_urls() {
        val p = project().withClip(source.id, 1, 123).copy(lastExport = Track(LOCAL_STUDIO_PREFIX + studioId(), "Mine", "Studio"))
        val text = Json.encodeToString(p)
        assertEquals(p, Json.decodeFromString<StudioProject>(text))
        assertFalse(text.contains("https://")); assertFalse(text.contains("content://"))
    }
    @Test(expected = IllegalArgumentException::class) fun zero_length_clip_is_invalid() { project().withClip(source.id, 10, 10) }
    @Test(expected = IllegalArgumentException::class) fun reversed_clip_is_invalid() { project().withClip(source.id, 20, 10) }
    @Test(expected = IllegalArgumentException::class) fun negative_start_is_invalid() { project().withClip(source.id, -1, 10) }
    @Test(expected = IllegalArgumentException::class) fun past_end_is_invalid() { project().withClip(source.id, 0, source.durationMs + 1) }
    @Test(expected = IllegalArgumentException::class) fun missing_source_is_invalid() { project().withClip(studioId(), 0, 100) }
    @Test(expected = IllegalArgumentException::class) fun empty_export_is_invalid() { project().validate(requireClips = true) }
    @Test(expected = IllegalArgumentException::class) fun private_source_names_cannot_escape_the_source_directory() {
        project().copy(sources = listOf(source.copy(fileName = "../elsewhere"))).validate()
    }
    @Test(expected = ArithmeticException::class) fun total_duration_overflow_is_rejected_not_wrapped() {
        val huge = source.copy(durationMs = Long.MAX_VALUE)
        StudioProject(studioId(), "Huge", listOf(huge)).withClip(huge.id, 0, Long.MAX_VALUE).withClip(huge.id, 0, 1)
    }
    @Test fun local_sharing_does_not_fabricate_a_youtube_link() {
        val local = Track(LOCAL_STUDIO_PREFIX + studioId(), "Mine", "Studio")
        assertEquals("Mine - Studio", trackShareText(local))
        assertTrue(trackShareText(Track("abcdefghijk", "Song", "Artist")).contains("music.youtube.com/watch?v=abcdefghijk"))
    }
    @Test fun local_metadata_and_id_are_never_relayed_to_a_room() {
        val local = Track(LOCAL_STUDIO_PREFIX + studioId(), "Private title", "Studio")
        val remote = Track("abcdefghijk", "Song", "Artist")
        assertNull(roomMessage(RoomPlaybackState(current = local, queue = listOf(local, remote)), 123))
        val message = requireNotNull(roomMessage(RoomPlaybackState(current = remote, queue = listOf(remote, local, remote.copy(id = "bcdefghijkl"))), 123))
        assertEquals(listOf("bcdefghijkl"), message.queue.map { it.videoId })
    }
    @Test fun local_audio_radio_never_looks_up_its_title_or_id_remotely() = kotlinx.coroutines.test.runTest {
        var requests = 0
        val result = app.dkord.data.yt.musicRadioRecommendations(
            Track(LOCAL_STUDIO_PREFIX + studioId(), "Private", "Studio"), emptyList(),
            fetchRadio = { requests++; emptyList() }, searchSongs = { requests++; emptyList() })
        assertTrue(result.isEmpty()); assertEquals(0, requests)
    }
    @Test fun editor_destination_survives_back_stack_serialization_without_source_uris() {
        val dest: app.dkord.ui.Dest = app.dkord.ui.Dest.Studio(Track("abcdefghijk", "Chosen", "Creator"))
        assertEquals(dest, Json.decodeFromString<app.dkord.ui.Dest>(Json.encodeToString(dest)))
    }

}
