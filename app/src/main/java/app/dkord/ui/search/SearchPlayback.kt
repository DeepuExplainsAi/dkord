package app.dkord.ui.search

import app.dkord.core.BrowseItem
import app.dkord.core.ItemKind
import app.dkord.core.Track

/** A search match is a choice, not a playlist of every alternative upload matching its title. */
internal fun searchPlaybackQueue(item: BrowseItem): List<Track> =
    if (item.kind == ItemKind.SONG) listOfNotNull(item.track) else emptyList()
