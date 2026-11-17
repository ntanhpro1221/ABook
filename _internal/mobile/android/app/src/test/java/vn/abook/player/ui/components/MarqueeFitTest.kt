package vn.abook.player.ui.components

import org.junit.Assert.assertEquals
import org.junit.Test

/** Luật ô tên một dòng cố định: cùng ca với web `MarqueeLine.test.ts` và Qt `tst_mini.qml` test_marqueeFitsThenScrolls. */
class MarqueeFitTest {
    // Chữ rộng tỉ lệ với cỡ: 10 px chữ mỗi 1 sp
    private val measure: (Float) -> Int = { sp -> (sp * 10).toInt() }

    @Test
    fun fitsThenShrinksThenScrollsAtTheFloor() {
        assertEquals(MarqueeFit.One to 16f, marqueeFit(200, 16f, measure))
        assertEquals(MarqueeFit.Shrunk to 14f, marqueeFit(140, 16f, measure))
        assertEquals(MarqueeFit.Scroll to 16f * OneLineFit.MIN_SCALE, marqueeFit(100, 16f, measure))
    }

    @Test
    fun exactFloorIsMeasuredBetweenHalfPointSteps() {
        val base = 15.6f
        val floor = base * OneLineFit.MIN_SCALE
        assertEquals(MarqueeFit.Shrunk to floor, marqueeFit(117, base) { if (it <= floor) 117 else 118 })
        assertEquals(MarqueeFit.Scroll to floor, marqueeFit(116, base) { if (it <= floor) 117 else 118 })
    }
}
