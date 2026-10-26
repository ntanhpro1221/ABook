package vn.abook.player.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertSame
import org.junit.Assert.assertTrue
import org.junit.Test
import vn.abook.player.ui.data.BookRow
import vn.abook.player.ui.data.CoverSampling
import vn.abook.player.ui.motion.Motion
import vn.abook.player.ui.motion.ScreenGeometry
import vn.abook.player.ui.nav.BackStack
import vn.abook.player.ui.nav.Destination
import vn.abook.player.ui.nav.Tab
import vn.abook.player.ui.screens.libraryColumns
import vn.abook.player.ui.theme.MotionMs

class NavTest {
    private fun book(id: String) = Destination.Book(BookRow(id, "Sách $id", "", null, 0L))

    @Test
    fun `pop undoes push`() {
        val root = BackStack()
        val one = root.push(book("a"))
        val two = one.push(book("b"))
        assertEquals(2, two.size)
        assertEquals(one, two.pop())
        assertEquals(root, one.pop())
        assertTrue(root.isEmpty)
    }

    @Test
    fun `pop on the root stays at the root`() {
        val root = BackStack()
        assertSame(root, root.pop())
    }

    @Test
    fun `entry keys never repeat so a layer keeps its state when it moves down`() {
        val s = BackStack().push(book("a")).push(book("b")).pop().push(book("c"))
        assertEquals(s.entries.size, s.entries.map { it.key }.toSet().size)
    }

    @Test
    fun `push and pop walk the same offsets in opposite order`() {
        val steps = 40
        val push = (0..steps).map { p(it, steps) }
        val pop = (steps downTo 0).map { p(it, steps) }
        for (i in 0..steps) {
            // Khung thứ i của Back là khung thứ (steps - i) của vào - cả hai màn, không lệch một điểm ảnh.
            assertEquals(ScreenGeometry.topFraction(push[steps - i]), ScreenGeometry.topFraction(pop[i]), 0f)
            assertEquals(ScreenGeometry.belowFraction(push[steps - i]), ScreenGeometry.belowFraction(pop[i]), 0f)
        }
    }

    private fun p(i: Int, steps: Int) = i.toFloat() / steps

    @Test
    fun `screen enters from the right edge and the one below recedes 30 percent`() {
        assertEquals(1f, ScreenGeometry.topFraction(0f), 0f)
        assertEquals(0f, ScreenGeometry.topFraction(1f), 0f)
        assertEquals(0f, ScreenGeometry.belowFraction(0f), 0f)
        assertEquals(-0.3f, ScreenGeometry.belowFraction(1f), 1e-6f)
    }

    @Test
    fun `predictive back drives the same geometry by progress`() {
        assertEquals(1f, ScreenGeometry.forBack(0f), 0f) // chưa kéo = màn đã vào hẳn
        assertEquals(0f, ScreenGeometry.forBack(1f), 0f) // kéo hết = màn ra hẳn
        for (back in listOf(0.1f, 0.25f, 0.5f, 0.9f)) {
            val progress = ScreenGeometry.forBack(back)
            // Kéo tới `back` đặt hai màn đúng chỗ của khung vào ở tiến trình (1 - back): màn trên đã đi `back` bề rộng.
            assertEquals(back, ScreenGeometry.topFraction(progress), 1e-6f)
            assertEquals(-ScreenGeometry.BELOW_SHIFT * (1f - back), ScreenGeometry.belowFraction(progress), 1e-6f)
        }
        assertEquals(1f, ScreenGeometry.forBack(-3f), 0f)
        assertEquals(0f, ScreenGeometry.forBack(7f), 0f)
    }

    @Test
    fun `motion tokens come from the design doc and exits are faster than entrances`() {
        assertEquals(300, MotionMs.SLOW)
        assertEquals(200, MotionMs.SLOW_OUT)
        assertTrue(MotionMs.SLOW_OUT < MotionMs.SLOW && MotionMs.MEDIUM_OUT < MotionMs.MEDIUM && MotionMs.FAST_OUT < MotionMs.FAST)
        assertEquals(0f, Motion.Decelerate.transform(0f), 1e-6f)
        assertEquals(1f, Motion.Decelerate.transform(1f), 1e-6f)
        assertEquals(1f, Motion.Accelerate.transform(1f), 1e-6f)
        // Không nảy, không vượt đích (DESIGN.md §5.2): mọi đường cong đơn điệu trong [0, 1].
        for (easing in listOf(Motion.Standard, Motion.Decelerate, Motion.Accelerate)) {
            var last = 0f
            for (i in 0..100) {
                val v = easing.transform(i / 100f)
                assertTrue(v in 0f..1.0001f && v >= last - 1e-5f)
                last = v
            }
        }
    }

    @Test
    fun `tabs slide by index`() {
        assertEquals(listOf("Thư viện", "Studio", "Cài đặt"), Tab.entries.map { it.label })
        assertEquals(listOf(0, 1, 2), Tab.entries.map { it.ordinal })
    }

    @Test
    fun `cover sampling keeps the decoded image at least as big as the cell`() {
        assertEquals(1, CoverSampling.sampleSize(300, 450, 290, 435))
        assertEquals(2, CoverSampling.sampleSize(600, 900, 290, 435))
        assertEquals(4, CoverSampling.sampleSize(1200, 1800, 290, 435))
        assertEquals(8, CoverSampling.sampleSize(4000, 6000, 290, 435))
        assertEquals(1, CoverSampling.sampleSize(0, 0, 290, 435))
        val sample = CoverSampling.sampleSize(1000, 1500, 290, 435)
        assertTrue(1000 / sample >= 290 && 1500 / sample >= 435)
    }

    @Test
    fun `cover cache is a sixteenth of the heap`() {
        assertEquals(32 * 1024 * 1024, CoverSampling.cacheBytes(512L * 1024 * 1024))
        assertEquals(1 shl 20, CoverSampling.cacheBytes(1L shl 20))
    }

    @Test
    fun `library grid has two to three phone columns`() {
        assertEquals(2, libraryColumns(320))
        assertEquals(3, libraryColumns(360))
        assertEquals(3, libraryColumns(412))
        assertFalse(libraryColumns(360) < 2)
    }
}
