package app.dkord

import app.dkord.data.download.downloadFileName
import org.junit.Assert.*
import org.junit.Test

class DownloadFileNameTest {
    @Test fun ordinary_names_keep_the_existing_human_readable_format() {
        assertEquals("Artist - Song.m4a", downloadFileName("Artist", "Song", "m4a"))
        assertEquals("Artist - Song.webm", downloadFileName("Artist", "/Song\\?*", "webm"))
    }
    @Test fun long_hindi_and_emoji_names_fit_real_utf8_leaf_limits_without_broken_surrogates() {
        val title = "संगवारी 🎧 ".repeat(100)
        for ((artist, song) in listOf("गायक" to title, "" to "🎧".repeat(100))) {
            val name = downloadFileName(artist, song, "wav")
            assertTrue(name.toByteArray(Charsets.UTF_8).size <= 240)
            assertEquals(name, String(name.toByteArray(Charsets.UTF_8), Charsets.UTF_8))
            assertTrue(name.endsWith(".wav"))
        }
        assertEquals("संगवारी 🎧 ".repeat(100), title)
    }
    @Test fun blank_reserved_and_trailing_names_are_portable_but_original_metadata_is_not_changed() {
        assertEquals("track.m4a", downloadFileName("", "", "m4a"))
        assertEquals("Dkord CON.wav", downloadFileName("", "CON", "wav"))
        assertEquals("Artist - Song.m4a", downloadFileName("Artist", "Song. ", "m4a"))
    }
    @Test fun extensions_cannot_escape_the_selected_directory() {
        for (ext in listOf("../wav", "m4a/file", "", "longextension")) {
            assertThrows(IllegalArgumentException::class.java) { downloadFileName("Artist", "Song", ext) }
        }
    }
}
