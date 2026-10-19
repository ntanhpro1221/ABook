package vn.abook.player

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/** a67: the WebView follows a system font scale change without the activity being recreated; the media notification never says "by null". */
class FontScaleAndArtistTest {
    @Test
    fun textZoomFollowsTheSystemFontScale() {
        assertEquals(100, textZoomFor(1.0f))
        assertEquals(130, textZoomFor(1.3f))
        assertEquals(200, textZoomFor(2.0f))
        assertEquals(50, textZoomFor(0.1f))
    }

    @Test
    fun theArtistIsTheNarratorThenTheBookTitleNeverEmpty() {
        assertEquals("Hoài My", mediaArtist("Hoài My", "Sách"))
        assertEquals("Sách", mediaArtist("", "Sách"))
        assertNull(mediaArtist(" ", ""))
    }
}
