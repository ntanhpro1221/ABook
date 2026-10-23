package vn.abook.player

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/** Trần điểm ảnh của bìa - cùng số và cùng cách tính với `covers.render_cover` (tests/test_webui_covers.py). */
class CoverPixelsTest {
    @Test
    fun a_jpeg_is_counted_after_the_decoder_shrinks_it_like_pil_draft() {
        assertEquals(2000L * 1500, Covers.decodedPixels(8000, 6000, jpeg = true)) // 1/4: min(8000/1400, 6000/1400) = 4
        assertEquals(1400L * 1400, Covers.decodedPixels(2800, 2800, jpeg = true)) // 1/2
        assertEquals(1500L * 1000, Covers.decodedPixels(1500, 1000, jpeg = true)) // a side under 1400: full size
        assertEquals(0L, Covers.decodedPixels(0, 0, jpeg = true))
    }

    @Test
    fun any_other_format_is_decoded_at_full_size() {
        assertEquals(8000L * 8000, Covers.decodedPixels(8000, 8000, jpeg = false))
        assertTrue(Covers.decodedPixels(8000, 8000, jpeg = false) > Covers.MAX_PIXELS)
        assertTrue("a 108 MP phone photo (JPEG) is still fine", Covers.decodedPixels(12000, 9000, jpeg = true) <= Covers.MAX_PIXELS)
    }

    @Test
    fun the_refusal_says_the_same_words_as_the_computer() {
        assertEquals("Ảnh vượt 40 triệu điểm ảnh — bạn thu nhỏ rồi thử lại.", Covers.tooManyPixels().message)
    }
}
