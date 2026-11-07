package app.dkord.ui.search

import app.dkord.core.BrowseItem
import app.dkord.ui.common.formatTime

/** Presentation only: keep the provider's creator and show a known duration; never filter results. */
internal fun searchResultSupportingText(item: BrowseItem): String {
    val duration = item.track?.durationSec
        ?.takeIf { it > 0 && it <= Long.MAX_VALUE / 1000 }
        ?.let { formatTime(it * 1000) }
    return listOfNotNull(item.subtitle.takeIf { it.isNotBlank() }, duration).joinToString(" • ")
}
