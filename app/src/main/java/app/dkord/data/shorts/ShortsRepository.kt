package app.dkord.data.shorts

import app.dkord.data.yt.mapItem
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.withContext
import org.schabi.newpipe.extractor.InfoItem
import org.schabi.newpipe.extractor.ServiceList
import org.schabi.newpipe.extractor.channel.ChannelInfo
import org.schabi.newpipe.extractor.channel.ChannelInfoItem
import org.schabi.newpipe.extractor.channel.tabs.ChannelTabInfo
import org.schabi.newpipe.extractor.channel.tabs.ChannelTabs
import org.schabi.newpipe.extractor.linkhandler.ListLinkHandler
import org.schabi.newpipe.extractor.search.SearchInfo
import org.schabi.newpipe.extractor.services.youtube.linkHandler.YoutubeSearchQueryHandlerFactory
import org.schabi.newpipe.extractor.stream.StreamInfoItem
import org.schabi.newpipe.extractor.stream.StreamType

internal data class MusicClip(val id: String, val title: String, val creator: String, val thumbnail: String?, val durationSec: Long)
internal interface ShortsCursor
internal data class ShortsPage(val clips: List<MusicClip>, val next: ShortsCursor? = null, val fromCreators: Boolean = false)
internal fun interface ShortsSource { suspend fun load(query: String, cursor: ShortsCursor?): ShortsPage }
private class NativeCursor(val query: String, val page: org.schabi.newpipe.extractor.Page) : ShortsCursor
private sealed interface CreatorTask
private class DiscoverCreator(val url: String) : CreatorTask
private class MoreCreator(val handler: ListLinkHandler, val page: org.schabi.newpipe.extractor.Page, val creator: String) : CreatorTask
private class CreatorCursor(val query: String, val tasks: List<CreatorTask>) : ShortsCursor

/** Native short-form IDs, not arbitrary videos relabeled/clipped as Shorts. Guest/provider order. */
internal class ShortsRepository : ShortsSource {
    override suspend fun load(query: String, cursor: ShortsCursor?): ShortsPage = withContext(Dispatchers.IO) {
        if (cursor is CreatorCursor) {
            require(cursor.query == query)
            return@withContext creatorPage(query, cursor.tasks)
        }
        val service = ServiceList.YouTube
        val handler = service.searchQHFactory.fromQuery(query, listOf(YoutubeSearchQueryHandlerFactory.ALL), "")
        val items: List<InfoItem>
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
        val clips = nativeClips(items)
        if (cursor == null && clips.isEmpty()) {
            // Pinned extractor does not collect desktop reelShelfRenderer. Discover real creator
            // Shorts tabs through native channel search/metadata instead of returning fabricated clips.
            val channels = SearchInfo.getInfo(service, service.searchQHFactory.fromQuery(query,
                listOf(YoutubeSearchQueryHandlerFactory.CHANNELS), ""))
            val tasks = channels.relatedItems.filterIsInstance<ChannelInfoItem>().map { it.url }.distinct().take(3).map(::DiscoverCreator)
            return@withContext creatorPage(query, tasks)
        }
        ShortsPage(clips, next?.takeIf { org.schabi.newpipe.extractor.Page.isValid(it) }?.let { NativeCursor(query, it) })
    }
    private suspend fun creatorPage(query: String, tasks: List<CreatorTask>): ShortsPage {
        val service = ServiceList.YouTube
        val pending = tasks.toMutableList()
        var lastError: Exception? = null
        while (pending.isNotEmpty()) {
            currentCoroutineContext().ensureActive()
            val task = pending.removeAt(0)
            try {
                val handler: ListLinkHandler
                val creator: String
                val items: List<InfoItem>
                val next: org.schabi.newpipe.extractor.Page?
                when (task) {
                    is DiscoverCreator -> {
                        val channel = ChannelInfo.getInfo(service, task.url)
                        creator = channel.name
                        handler = channel.tabs.firstOrNull { ChannelTabs.SHORTS in it.contentFilters } ?: continue
                        val page = ChannelTabInfo.getInfo(service, handler)
                        items = page.relatedItems; next = page.nextPage
                    }
                    is MoreCreator -> {
                        handler = task.handler; creator = task.creator
                        val page = ChannelTabInfo.getMoreItems(service, handler, task.page)
                        items = page.items; next = page.nextPage
                    }
                }
                // Round-robin creator pages rather than consuming one creator forever.
                if (org.schabi.newpipe.extractor.Page.isValid(next)) pending.add(MoreCreator(handler, requireNotNull(next), creator))
                return ShortsPage(nativeClips(items, creator), pending.takeIf { it.isNotEmpty() }?.let { CreatorCursor(query, it.toList()) }, fromCreators = true)
            } catch (e: CancellationException) { throw e }
            catch (e: Exception) { lastError = e }
        }
        lastError?.let { throw it }
        return ShortsPage(emptyList(), fromCreators = true)
    }
}

internal fun nativeClips(items: List<InfoItem>, knownCreator: String = ""): List<MusicClip> = uniqueClips(emptyList(), items.filterIsInstance<StreamInfoItem>().mapNotNull { item ->
    if (!item.isShortFormContent || item.streamType != StreamType.VIDEO_STREAM) return@mapNotNull null
    val track = mapItem(item)?.track ?: return@mapNotNull null
    // Native Shorts-tab items may have unknown duration (-1). Zero is the unknown sentinel, not a made-up length.
    MusicClip(track.id, track.title, track.artist.ifBlank { knownCreator }, track.thumbnail, track.durationSec.coerceAtLeast(0))
})

internal fun uniqueClips(existing: List<MusicClip>, candidates: List<MusicClip>): List<MusicClip> {
    val ids = existing.map { it.id }.toMutableSet()
    return candidates.filter { it.id.isNotBlank() && it.title.isNotBlank() && it.durationSec in 0..180 && ids.add(it.id) }
}

/** Only an editable lookup hint, NEVER a claimed original-song attribution or auto-played guess. */
internal fun fullSongQuery(clip: MusicClip): String = clip.title.replace(Regex("#[\\p{L}\\p{M}\\p{N}_]+"), " ")
    .replace(Regex("\\s+"), " ").trim().ifBlank { clip.title }.take(200)
