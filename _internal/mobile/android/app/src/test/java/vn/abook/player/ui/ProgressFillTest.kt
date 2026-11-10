package vn.abook.player.ui

import org.junit.Assert.assertEquals
import org.junit.Test
import vn.abook.player.ui.components.ProgressFill

/**
 * Soát 10-11 L13: thanh tiến độ gần 0 % vẽ một gạch hổ phách vài điểm ảnh dưới chữ "Đ" của "Đang nghe" - trông như lỗi.
 * Dưới 2 % thì không vẽ phần đã tô; từ 2 % trở lên giữ nguyên tỉ lệ. Cùng ngưỡng với web `progressFill` và Qt `Theme.progressFillMin`.
 */
class ProgressFillTest {
    @Test fun belowTwoPercentDrawsNoFill() {
        for (f in listOf(-1f, 0f, 0.001f, 0.01f, 0.0199f)) assertEquals("ở $f", 0f, ProgressFill.of(f), 0f)
    }

    @Test fun fromTwoPercentKeepsTheFraction() {
        for (f in listOf(0.02f, 0.4f, 0.995f, 1f)) assertEquals("ở $f", f, ProgressFill.of(f), 0f)
        assertEquals(1f, ProgressFill.of(3f), 0f)
    }
}
