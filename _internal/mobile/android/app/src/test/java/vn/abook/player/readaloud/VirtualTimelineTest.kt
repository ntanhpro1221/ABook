package vn.abook.player.readaloud

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class VirtualTimelineTest {
    /** Ba đoạn 140, 280, 70 ký tự: ước 10 s, 20 s, 5 s ở 14 ký tự mỗi giây. */
    private fun timeline() = VirtualTimeline(intArrayOf(140, 280, 70))

    @Test
    fun estimatesFromCharacterCountUntilTheClipIsKnown() {
        val t = timeline()
        assertEquals(10_000, t.durationOf(0))
        assertEquals(0, t.startOf(0))
        assertEquals(10_000, t.startOf(1))
        assertEquals(30_000, t.startOf(2))
        assertEquals(35_000, t.totalMs())
        assertFalse(t.isKnown(1))
    }

    @Test
    fun aRealDurationReplacesTheEstimateAndShiftsOnlyWhatComesAfter() {
        val t = timeline()
        val before = t.startOf(1)
        t.setDuration(1, 18_000)
        t.setDuration(2, 4_000)
        assertEquals("mốc đầu đoạn chỉ phụ thuộc đoạn trước nó", before, t.startOf(1))
        assertEquals(28_000, t.startOf(2))
        assertEquals(32_000, t.totalMs())
        assertTrue(t.isKnown(1))
        assertEquals(2, t.knownCount())
    }

    @Test
    fun correctingAnEarlierSegmentMovesTheLaterStarts() {
        val t = timeline()
        t.setDuration(0, 12_500)
        assertEquals(12_500, t.startOf(1))
        assertEquals(32_500, t.startOf(2))
    }

    @Test
    fun seekFindsTheSegmentContainingTheTime() {
        val t = timeline()
        t.setDuration(0, 9_000)
        assertEquals(0, t.segmentAt(0))
        assertEquals(0, t.segmentAt(8_999))
        assertEquals(1, t.segmentAt(9_000))
        assertEquals(1, t.segmentAt(28_999))
        assertEquals(2, t.segmentAt(29_000))
        assertEquals(2, t.segmentAt(1_000_000))
        assertEquals(0, t.segmentAt(-5))
    }

    @Test
    fun aVeryShortParagraphStillTakesSomeTime() {
        val t = VirtualTimeline(intArrayOf(1, 140))
        assertEquals(VirtualTimeline.MIN_ESTIMATE_MS, t.durationOf(0))
        assertEquals(VirtualTimeline.MIN_ESTIMATE_MS, t.startOf(1))
    }

    @Test
    fun anEmptyChapterIsSafe() {
        val t = VirtualTimeline(IntArray(0))
        assertEquals(0, t.totalMs())
        assertEquals(0, t.segmentAt(1234))
    }

    @Test
    fun endOfASegmentIsTheStartOfTheNext() {
        val t = timeline()
        t.setDuration(1, 15_000)
        assertEquals(t.startOf(2), t.endOf(1))
    }
}
