package app.dkord

import app.dkord.data.links.MAX_YOUTUBE_LINK_LENGTH
import app.dkord.data.links.YouTubeLinkException
import app.dkord.data.links.YouTubeLinkProblem
import app.dkord.data.links.YouTubeVideoLink
import app.dkord.ui.Dest
import kotlinx.serialization.builtins.ListSerializer
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.*
import org.junit.Test

/** The native PC parser consumes this exact same offline corpus. */
class YouTubeLinkParserTest {
    private val fixtures = Json.parseToJsonElement(javaClass.getResourceAsStream("/youtube-links.json")!!.bufferedReader().use { it.readText() }).jsonObject

    @Test fun all_common_video_link_forms_preserve_the_exact_case_sensitive_video_identity() {
        val values = fixtures.getValue("valid").jsonArray
        assertTrue(values.size >= 29)
        for (value in values) {
            val item = value.jsonObject
            val input = item.getValue("input").jsonPrimitive.content
            val id = item.getValue("id").jsonPrimitive.content
            val result = YouTubeVideoLink.parse(input)
            assertEquals(input, id, result.videoId)
            assertEquals(input, "https://www.youtube.com/watch?v=$id", result.url)
        }
    }

    @Test fun arbitrary_hosts_credentials_redirects_bad_ids_and_playlist_only_links_fail_before_network() {
        val values = fixtures.getValue("invalid").jsonArray
        assertTrue(values.size >= 46)
        for (value in values) {
            val item = value.jsonObject
            val input = item.getValue("input").jsonPrimitive.content
            val expected = YouTubeLinkProblem.valueOf(item.getValue("problem").jsonPrimitive.content.uppercase())
            val error = assertThrows(input, YouTubeLinkException::class.java) { YouTubeVideoLink.parse(input) }
            assertEquals(input, expected, error.problem)
            assertFalse(error.message.orEmpty().contains("http"))
        }
    }

    @Test fun oversized_input_is_not_silently_reinterpreted_as_a_shorter_valid_link() {
        val prefix = "https://youtu.be/AbCdEf012_-?si="
        val atLimit = prefix + "x".repeat(MAX_YOUTUBE_LINK_LENGTH - prefix.length)
        assertEquals("AbCdEf012_-", YouTubeVideoLink.parse(atLimit).videoId)
        assertEquals(YouTubeLinkProblem.INVALID_LINK,
            assertThrows(YouTubeLinkException::class.java) { YouTubeVideoLink.parse(atLimit + "x") }.problem)
    }

    @Test fun a_video_with_a_playlist_or_timestamp_never_turns_into_an_implicit_playlist_queue() {
        val link = YouTubeVideoLink.parse("https://music.youtube.com/watch?v=AbCdEf012_-&list=RDAMVMotherId&index=9&t=40")
        assertEquals("https://www.youtube.com/watch?v=AbCdEf012_-", link.url)
        assertFalse(link.url.contains("list=")); assertFalse(link.url.contains("t="))
    }

    @Test fun the_additive_destination_preserves_old_serialized_navigation_and_roundtrips_the_new_page() {
        val json = Json { classDiscriminator = "t" }
        val serializer = ListSerializer(Dest.serializer())
        val old = """[{"t":"app.dkord.ui.Dest.Playlist","id":42},{"t":"app.dkord.ui.Dest.Settings"},{"t":"app.dkord.ui.Dest.ListenTogether"}]"""
        val stack = listOf(Dest.Playlist(42), Dest.Settings, Dest.ListenTogether)
        assertEquals(stack, json.decodeFromString(serializer, old))
        assertEquals(stack + Dest.YouTubeLink, json.decodeFromString(serializer, json.encodeToString(serializer, stack + Dest.YouTubeLink)))
    }
}
