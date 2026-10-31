package vn.abook.player

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/** The media notification never says "by null". */
class FontScaleAndArtistTest {
    @Test
    fun theArtistIsTheNarratorThenTheBookTitleNeverEmpty() {
        assertEquals("Hoài My", mediaArtist("Hoài My", "Sách"))
        assertEquals("Sách", mediaArtist("", "Sách"))
        assertNull(mediaArtist(" ", ""))
    }
}
