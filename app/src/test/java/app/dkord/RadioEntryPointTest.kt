package app.dkord

import app.dkord.core.BrowseItem
import app.dkord.core.ItemKind
import app.dkord.core.Shelf
import app.dkord.core.Track
import app.dkord.data.room.RoomCodec
import app.dkord.data.room.RoomMessage
import app.dkord.data.room.RoomTrack
import app.dkord.data.yt.radioTraits
import app.dkord.ui.screens.choliwoodShelfTitle
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import org.junit.Assert.*
import org.junit.Test

class RadioEntryPointTest {
    private val track = Track("Abcdefghij1", "Original title", "Original artist", "Album", 180)
    private val item = BrowseItem(ItemKind.SONG, track.id, track.title, track = track)

    @Test fun shelf_heading_localization_does_not_erase_the_provider_discovery_context() {
        val shelf = Shelf("Sad Songs", listOf(item), "hindi sad songs")
        val translated = shelf.copy(title = "दर्द भरे गाने")
        assertEquals("hindi sad songs", translated.radioHint)
        assertEquals(track, translated.items.single().track)
        assertEquals("hi", radioTraits(track, hint = translated.radioHint).language)
    }

    @Test fun choliwood_stays_the_visible_brand_while_internal_discovery_language_is_retained() {
        val shelf = Shelf("Bhojpuri hits", listOf(item), "popular bhojpuri songs")
        val branded = shelf.copy(title = choliwoodShelfTitle(shelf.title, "Choliwood"))
        assertEquals("Choliwood hits", branded.title)
        assertEquals("popular bhojpuri songs", branded.radioHint)
        assertEquals("bho", radioTraits(track, hint = branded.radioHint).language)
    }

    @Test fun discovery_and_search_intent_cannot_be_encoded_in_tracks_or_room_messages() {
        val shelf = Shelf("Heading", listOf(item), "private hindi sad listening query")
        val roomTrack = RoomTrack.fromTrack(shelf.items.single().track!!)
        val encoded = RoomCodec.encode(RoomMessage(track.id, track.title, track.artist,
            positionMs = 0, playing = true, timestamp = 1, queue = listOf(roomTrack)))
        val trackJson = Json.encodeToString(track)
        for (text in listOf(encoded, trackJson)) {
            assertFalse(text.contains(shelf.radioHint))
            for (name in listOf("radioHint", "contextHint", "language", "mood", "views")) assertFalse(text.contains("\"$name\""))
        }
        assertEquals(track.title, RoomCodec.decode(encoded)?.title)
    }
}
