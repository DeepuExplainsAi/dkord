package app.dkord.ui

import androidx.compose.runtime.saveable.Saver
import app.dkord.core.BrowseItem
import app.dkord.core.ItemKind
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json

@Serializable
enum class Tab {
    HOME, SEARCH, LISTEN, LIBRARY, DOWNLOADS,
    // Deserialization-only compatibility with old Java-enum saved state. Never displayed as a tab.
    REELS,
}

internal fun restoredTab(value: Any): Tab = when (value) {
    is Tab -> if (value == Tab.REELS) Tab.LISTEN else value
    is String -> Tab.entries.firstOrNull { it.name == value }?.let(::restoredTab) ?: Tab.HOME
    else -> Tab.HOME
}

/** New saves use stable names; old serialized enum values safely map to the audio-only replacement. */
val TabSaver = Saver<Tab, Any>(save = { restoredTab(it).name }, restore = ::restoredTab)

/** Screens above the tabs. Serializable so the back stack survives rotation and process death. */
@Serializable
sealed interface Dest {
    @Serializable data class Detail(val kind: ItemKind, val id: String, val title: String, val thumb: String?, val params: String?) : Dest
    @Serializable data class Playlist(val id: Long) : Dest
    @Serializable data object Liked : Dest
    @Serializable data object Recent : Dest
    @Serializable data object Settings : Dest
    @Serializable data object ListenTogether : Dest
    @Serializable data object YouTubeLink : Dest
    @Serializable data class Studio(val track: app.dkord.core.Track? = null) : Dest
    @Serializable data object Logs : Dest
    @Serializable data class Video(val id: String, val title: String) : Dest
}

fun BrowseItem.toDest() = Dest.Detail(kind, id, title, thumbnail, params)
fun Dest.Detail.toItem() = BrowseItem(kind, id, title, thumbnail = thumb, params = params)

private val json = Json { classDiscriminator = "t" }

/** Saves the stack as one JSON string, which rememberSaveable can put in a Bundle. */
val BackStackSaver = Saver<List<Dest>, String>(
    save = { json.encodeToString(kotlinx.serialization.builtins.ListSerializer(Dest.serializer()), it) },
    restore = { runCatching { json.decodeFromString(kotlinx.serialization.builtins.ListSerializer(Dest.serializer()), it) }.getOrDefault(emptyList()) },
)

/** Direction follows stack depth, so popping a nested screen never animates like a push. */
internal enum class NavigationDirection { FORWARD, BACK, FADE }
internal fun navigationDirection(fromDepth: Int, toDepth: Int): NavigationDirection = when {
    toDepth > fromDepth -> NavigationDirection.FORWARD
    toDepth < fromDepth -> NavigationDirection.BACK
    else -> NavigationDirection.FADE
}
