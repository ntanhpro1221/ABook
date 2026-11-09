package vn.abook.player.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import vn.abook.player.ui.components.RangeTrack

/**
 * Máy dò "núm không bị xén": mọi thanh kéo (Âm thanh, Nhạc nền, thanh tua) vẽ núm qua [RangeTrack]. Ở 0 và ở tối đa núm phải nằm TRỌN trong ô của nó -
 * trước đây tâm núm ở đúng mép ô nên mép mờ / bo góc của bảng xén mất nửa núm. Chạm ở đâu thì núm tới đúng đó (cùng một phép đổi hai chiều).
 */
class RangeTrackTest {
    @Test fun theThumbStaysInsideItsBoxAtEveryValue() {
        for (width in listOf(120f, 600f, 1080f)) for (thumb in listOf(5f * 2.75f, 5f * 3f)) for (step in 0..20) {
            val x = RangeTrack.x(step / 20f, width, thumb)
            assertTrue("núm ló trái ở $step/20, rộng $width", x - thumb >= -0.001f)
            assertTrue("núm ló phải ở $step/20, rộng $width", x + thumb <= width + 0.001f)
        }
    }

    @Test fun aTouchLandsTheThumbUnderTheFinger() {
        val width = 900f
        val thumb = 15f
        for (step in 0..10) {
            val fraction = step / 10f
            assertEquals(fraction, RangeTrack.fraction(RangeTrack.x(fraction, width, thumb), width, thumb), 1e-4f)
        }
        assertEquals(0f, RangeTrack.fraction(0f, width, thumb), 0f)
        assertEquals(1f, RangeTrack.fraction(width, width, thumb), 0f)
    }
}
