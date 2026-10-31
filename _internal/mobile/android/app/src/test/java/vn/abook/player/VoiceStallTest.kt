package vn.abook.player

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/** Giọng khựng quá `voiceStallFadeAfterSeconds` (music_mix.json, chung ba nền) thì nhạc mờ xuống; khe nối bình thường thì không. */
class VoiceStallTest {
    private val stall = VoiceStall { 10_000L }

    @Test fun `the position standing still while the voice is on counts only past the limit`() {
        assertFalse(stall.update(0, 12.0, on = true))
        assertFalse(stall.update(9_999, 12.0, on = true))
        assertTrue(stall.update(10_000, 12.0, on = true))
        assertTrue(stall.update(60_000, 12.0, on = true))
    }

    @Test fun `the voice moving again, a seek or a pause starts the count over`() {
        stall.update(0, 12.0, on = true)
        assertTrue(stall.update(10_000, 12.0, on = true))
        assertFalse("có tiếng lại", stall.update(10_500, 12.4, on = true))
        assertFalse(stall.update(20_499, 12.4, on = true))
        assertTrue(stall.update(20_500, 12.4, on = true))
        assertFalse("người nghe dừng: không phải khựng", stall.update(21_000, 12.4, on = false))
        assertFalse(stall.update(40_000, 12.4, on = true))
        assertFalse("tua", stall.update(45_000, 90.0, on = true))
        assertTrue(stall.update(55_000, 90.0, on = true))
    }

    @Test fun `the limit is the one in music_mix json and sits above the longest normal gap measured`() {
        val mix = MusicMix.parse(File("../../../abook/webui/assets/music_mix.json").readText())
        assertEquals(10_000L, mix.voiceStallMs)
        assertTrue("khe nối dài nhất đo được (Edge chưa có sẵn, 1 giờ): 8,8 s", mix.voiceStallMs > 8_800L)
    }
}
