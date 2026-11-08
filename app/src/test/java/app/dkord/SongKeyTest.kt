package app.dkord

import app.dkord.data.yt.songKey
import org.junit.Assert.assertEquals
import org.junit.Test

class SongKeyTest {
    @Test fun variantsShareKey() {
        val k = songKey("SEM CONTROLE")
        listOf("SEM CONTROLE (Slowed)", "SEM CONTROLE (Ultra Slowed)", "nightfxrce - SEM CONTROLE (Super Slowed)")
            .forEach { assertEquals(k, songKey(it)) }
    }
}
