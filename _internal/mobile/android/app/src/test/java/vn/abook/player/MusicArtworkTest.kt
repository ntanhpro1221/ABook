package vn.abook.player

import org.json.JSONArray
import org.junit.Assert.*
import org.junit.Test
import java.io.File
import java.security.MessageDigest

class MusicArtworkTest {
    @Test fun canonicalBytesAndMetadataSeedsMatchWebAndQt() {
        val cases = JSONArray(File("../../../tests/fixtures/music_art/cases.json").readText())
        for (at in 0 until cases.length()) {
            val case = cases.getJSONObject(at)
            val seed = MusicArtwork.seed(case.getString("link"), case.getJSONObject("info"))
            assertEquals(case.getInt("seed"), seed)
            val bytes = MusicArtwork.rgb(seed)
            assertEquals(96 * 96 * 3, bytes.size)
            val sha = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
            assertEquals(case.getString("link"), case.getString("rgbSha256"), sha)
        }
        assertArrayEquals(MusicArtwork.rgb(42), MusicArtwork.rgb(42))
        assertFalse(MusicArtwork.rgb(42).contentEquals(MusicArtwork.rgb(43)))
    }
}
