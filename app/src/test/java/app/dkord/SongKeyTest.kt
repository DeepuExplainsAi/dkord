package app.dkord

import app.dkord.data.yt.songKey
import org.junit.Assert.*
import org.junit.Test

class SongKeyTest {
    @Test fun variantsShareKey() {
        val key = songKey("SEM CONTROLE")
        listOf("SEM CONTROLE (Slowed)", "SEM CONTROLE (Ultra Slowed)", "nightfxrce - SEM CONTROLE (Super Slowed)",
            "SEM CONTROLE - Slowed", "SEM CONTROLE | Official Audio", "SEM CONTROLE — Ultra Slowed")
            .forEach { assertEquals(it, key, songKey(it)) }
    }

    @Test fun case_whitespace_and_compatibility_unicode_do_not_create_a_new_song() {
        assertEquals(songKey("Song Name"), songKey("  SONG   NAME (LYRICS) "))
        assertEquals(songKey("Song Name"), songKey("Ｓｏｎｇ Ｎａｍｅ"))
    }

    @Test fun hindi_and_tamil_vowel_marks_are_preserved_not_collapsed_into_false_duplicates() {
        assertNotEquals(songKey("दिल"), songKey("दल"))
        assertNotEquals(songKey("கால்"), songKey("கல்"))
    }

    @Test fun meaningful_super_and_ultra_words_are_not_removed_from_unrelated_song_titles() {
        assertNotEquals(songKey("Super Bass"), songKey("Bass"))
        assertNotEquals(songKey("Ultra Love"), songKey("Love"))
    }

    @Test fun a_title_made_of_version_words_never_gets_a_shared_empty_identity() {
        assertTrue(songKey("Cover").isNotBlank())
        assertNotEquals(songKey("Cover"), songKey("Instrumental"))
    }
}
