package vn.abook.player

import org.junit.Assert.assertEquals
import org.junit.Test

class ChapterSleepTimeTest {
    @Test fun chapter_fades_over_real_listening_time_at_each_speed() {
        assertEquals(15_000L, ChapterSleepTime.remainingMs(60_000, 30_000, 2.0))
        assertEquals(60_000L, ChapterSleepTime.remainingMs(60_000, 30_000, 0.5))
        assertEquals(30_000L, ChapterSleepTime.remainingMs(60_000, 30_000, 1.0))
        assertEquals(120_000L, ChapterSleepTime.remainingMs(60_000, 30_000, 0.0))
        assertEquals(0L, ChapterSleepTime.remainingMs(60_000, 70_000, 2.0))
    }
}
