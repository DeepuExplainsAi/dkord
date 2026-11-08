package app.dkord.data.shorts

import app.dkord.data.yt.mapItem
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.schabi.newpipe.extractor.ServiceList
import org.schabi.newpipe.extractor.search.SearchInfo
import org.schabi.newpipe.extractor.services.youtube.linkHandler.YoutubeSearchQueryHandlerFactory
import org.schabi.newpipe.extractor.stream.StreamInfoItem
import org.schabi.newpipe.extractor.stream.StreamType

internal data class MusicClip(val id: String, val title: String, val creator: String, val thumbnail: String?, val durationSec: Long)
internal interface ShortsCursor
internal data class ShortsPage(val clips: List<MusicClip>, val next: ShortsCursor? = null)
internal fun interface ShortsSource { suspend fun load(query: String, cursor: ShortsCursor?): ShortsPage }
private class NativeCursor(val query: String, val page: org.schabi.newpipe.extractor.Page) : ShortsCursor

/** Native short-form metadata, not arbitrary long videos relabeled/clipped as Shorts. Guest/provider order. */
internal class ShortsRepository : ShortsSource {
    override suspend fun load(query: String, cursor: ShortsCursor?): ShortsPage = withContext(Dispatchers.IO) {
        val service = ServiceList.YouTube
        val handler = service.searchQHFactory.fromQuery(query, listOf(YoutubeSearchQueryHandlerFactory.ALL), "")
        val items: List<org.schabi.newpipe.extractor.InfoItem>
        val next: org.schabi.newpipe.extractor.Page?
        if (cursor == null) {
            val info = SearchInfo.getInfo(service, handler)
            items = info.relatedItems; next = info.nextPage
        } else {
            val native = cursor as? NativeCursor ?: error("Invalid shorts cursor")
            require(native.query == query)
            val page = SearchInfo.getMoreItems(service, handler, native.page)
            items = page.items; next = page.nextPage
        }
        val clips = items.filterIsInstance<StreamInfoItem>().mapNotNull { item ->
            if (!item.isShortFormContent || item.streamType != StreamType.VIDEO_STREAM) return@mapNotNull null
            val track = mapItem(item)?.track ?: return@mapNotNull null
            MusicClip(track.id, track.title, track.artist, track.thumbnail, track.durationSec)
        }
        ShortsPage(uniqueClips(emptyList(), clips), next?.let { NativeCursor(query, it) })
    }
}

internal fun uniqueClips(existing: List<MusicClip>, candidates: List<MusicClip>): List<MusicClip> {
    val ids = existing.map { it.id }.toMutableSet()
    return candidates.filter { it.id.isNotBlank() && it.title.isNotBlank() && it.durationSec in 0..180 && ids.add(it.id) }
}

/** Only an editable lookup hint, NEVER a claimed original-song attribution or auto-played guess. */
internal fun fullSongQuery(clip: MusicClip): String = clip.title.replace(Regex("#[\\p{L}\\p{M}\\p{N}_]+"), " ")
    .replace(Regex("\\s+"), " ").trim().ifBlank { clip.title }.take(200)
