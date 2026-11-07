package app.dkord

import app.dkord.core.ItemKind
import app.dkord.data.yt.mapItem
import app.dkord.data.yt.searchVideoId
import org.junit.Assert.*
import org.junit.Test
import org.schabi.newpipe.extractor.channel.ChannelInfoItem
import org.schabi.newpipe.extractor.playlist.PlaylistInfoItem
import org.schabi.newpipe.extractor.stream.StreamInfoItem
import org.schabi.newpipe.extractor.stream.StreamType

class SearchItemsTest {
    private val id = "AbCdEf123_-"
    private fun video(title: String, duration: Long) = StreamInfoItem(0, "https://www.youtube.com/watch?v=$id", title, StreamType.VIDEO_STREAM).apply {
        this.duration = duration
        uploaderName = "Creator - Topic"
    }

    @Test fun long_mashups_and_short_covers_are_not_removed_by_manual_search() {
        for (duration in listOf(0L, 20L, 59L, 721L, 3600L, 10800L, 43200L)) {
            val result = checkNotNull(mapItem(video("Any title $duration", duration)))
            assertEquals(ItemKind.SONG, result.kind)
            assertEquals(duration, checkNotNull(result.track).durationSec)
            assertEquals("Any title $duration", result.title)
        }
    }

    @Test fun results_retain_provider_order_instead_of_app_specific_genre_or_duration_ranking() {
        val items = listOf(video("mashup sad love 1 hour", 3600), video("Live cover", 45), video("Podcast", 7200))
        assertEquals(listOf("mashup sad love 1 hour", "Live cover", "Podcast"), items.mapNotNull(::mapItem).map { it.title })
    }

    @Test fun watch_short_shorts_live_and_embed_urls_keep_the_same_playable_video_identity() {
        for (url in listOf("https://www.youtube.com/watch?v=$id", "https://music.youtube.com/watch?v=$id&list=RDAMVM$id",
            "https://youtu.be/$id?t=20", "https://www.youtube.com/shorts/$id", "https://www.youtube.com/live/$id", "https://www.youtube.com/embed/$id")) {
            assertEquals(id, searchVideoId(url))
            assertEquals(id, mapItem(StreamInfoItem(0, url, "Video", StreamType.VIDEO_STREAM))?.track?.id)
        }
    }

    @Test fun invalid_non_youtube_and_non_video_urls_are_not_turned_into_playable_ids() {
        for (url in listOf("broken", "https://example.test/watch?v=$id", "https://www.youtube.com/watch?v=short", "https://www.youtube.com/playlist?list=PL123")) {
            assertNull(url, searchVideoId(url))
        }
    }

    @Test fun same_title_covers_and_instrumentals_from_different_creators_keep_distinct_video_ids() {
        val creators = listOf("Original artist - Topic", "Independent cover creator", "Instrumental channel")
        val ids = listOf("Cover000001", "Cover000002", "Inst0000001")
        val items = ids.mapIndexed { index, videoId ->
            StreamInfoItem(0, "https://www.youtube.com/watch?v=$videoId", "Teri meri kahani", StreamType.VIDEO_STREAM).apply {
                uploaderName = creators[index]
                duration = 200L + index
            }
        }.mapNotNull(::mapItem)
        assertEquals(ids, items.map { it.id })
        assertEquals(listOf("Original artist", "Independent cover creator", "Instrumental channel"), items.map { it.subtitle })
        assertEquals(ids, items.map { it.track?.id })
        assertEquals(listOf(200L, 201L, 202L), items.map { it.track?.durationSec })
    }

    @Test fun existing_uploader_and_track_mapping_are_preserved() {
        val mapped = checkNotNull(mapItem(video("Song title", 200)))
        assertEquals("Creator", mapped.subtitle)
        assertEquals("Creator", mapped.track?.artist)
        assertEquals(id, mapped.id)
        assertEquals("Song title", mapped.track?.title)
    }

    @Test fun albums_playlists_and_artists_keep_the_existing_navigation_ids() {
        assertEquals("VLOLAK5uyAlbum", mapItem(PlaylistInfoItem(0, "https://www.youtube.com/playlist?list=OLAK5uyAlbum", "Album"))?.id)
        assertEquals(ItemKind.ALBUM, mapItem(PlaylistInfoItem(0, "https://www.youtube.com/playlist?list=OLAK5uyAlbum", "Album"))?.kind)
        assertEquals("VLPL123", mapItem(PlaylistInfoItem(0, "https://www.youtube.com/playlist?list=PL123", "Playlist"))?.id)
        assertEquals("UCcreator", mapItem(ChannelInfoItem(0, "https://www.youtube.com/channel/UCcreator", "Creator"))?.id)
    }
}
