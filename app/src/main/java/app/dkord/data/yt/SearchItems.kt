package app.dkord.data.yt

import app.dkord.core.BrowseItem
import app.dkord.core.ItemKind
import app.dkord.core.Track
import org.schabi.newpipe.extractor.InfoItem
import org.schabi.newpipe.extractor.channel.ChannelInfoItem
import org.schabi.newpipe.extractor.playlist.PlaylistInfoItem
import org.schabi.newpipe.extractor.services.youtube.linkHandler.YoutubeStreamLinkHandlerFactory
import org.schabi.newpipe.extractor.stream.StreamInfoItem

/** Map provider results in provider order. Manual search has no genre, title or duration whitelist. */
internal fun mapItem(i: InfoItem): BrowseItem? {
    val thumb = i.thumbnails.maxByOrNull { it.height }?.url
    return when (i) {
        is StreamInfoItem -> {
            val id = searchVideoId(i.url) ?: return null
            val artist = i.uploaderName.orEmpty().removeSuffix(" - Topic")
            BrowseItem(ItemKind.SONG, id, i.name, artist, thumb, track = Track(id, i.name, artist, null, i.duration, thumb))
        }
        is PlaylistInfoItem -> {
            val list = Regex("[?&]list=([^&]+)").find(i.url)?.groupValues?.get(1) ?: return null
            val kind = if (list.startsWith("OLAK5uy")) ItemKind.ALBUM else ItemKind.PLAYLIST
            BrowseItem(kind, "VL$list", i.name, i.uploaderName.orEmpty(), thumb)
        }
        is ChannelInfoItem -> BrowseItem(ItemKind.ARTIST, i.url.substringAfterLast('/'), i.name, "", thumb)
        else -> null
    }
}

/** Supports watch, short, Shorts, live and embed links instead of silently dropping non-watch URLs. */
internal fun searchVideoId(url: String): String? = try {
    // NewPipe treats watch?v=...&list=... as a playlist before extracting the video id.
    // A StreamInfoItem is explicitly a video, so discard only that playlist context.
    val base = url.substringBefore('#')
    val query = base.substringAfter('?', "")
    val videoUrl = if (query.isEmpty()) base else base.substringBefore('?') + "?" +
        query.split('&').filterNot { it.substringBefore('=') == "list" }.joinToString("&")
    YoutubeStreamLinkHandlerFactory.getInstance().getId(videoUrl)
} catch (_: Exception) {
    null
}
