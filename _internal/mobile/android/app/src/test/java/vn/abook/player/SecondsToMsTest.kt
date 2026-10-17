package vn.abook.player

import org.junit.Assert.assertEquals
import org.junit.Test

/** Giây -> ms của lõi phát ([msOf], uxfix60 soát a59p): làm tròn, không cắt - "Nghe từ đây" theo câu ở mốc 1001 ms không rơi về đoạn trước. */
class SecondsToMsTest {
    @Test
    fun aSentenceStartJustAfterAWholeSecondStaysInItsOwnParagraph() {
        assertEquals("cách cũ (cắt) rơi về ms trước", 1_000L, (1.001 * 1000).toLong())
        assertEquals(1_001L, msOf(1.001))
        assertEquals(1_001L, msOf(1001 / 1000.0))
    }

    @Test
    fun everyMillisecondSurvivesTheTripThroughSeconds() {
        for (ms in 0L..200_000L) assertEquals(ms, msOf(ms / 1000.0))
    }

    @Test
    fun negativeSecondsBecomeZero() {
        assertEquals(0L, msOf(-0.4))
        assertEquals(0L, msOf(-12.0))
    }
}
