package vn.abook.player.readaloud

import org.junit.Assert.assertEquals
import org.junit.Test

/** Bấm Phát (màn hình khoá / thông báo) sau khi đọc xong chương cuối: nghe lại từ đầu cuốn, ngay lần bấm đầu. */
class EndPlanTest {
    @Test
    fun theLastChapterEndedRestartsTheBookFromItsFirstChapter() {
        val spot = EndPlan.restartSpot(chapterIndex = 2, chapterCount = 3, positionMs = 95_000, durationMs = 95_400)
        assertEquals(0, spot.chapterIndex)
        assertEquals(0L, spot.offsetMs)
    }

    @Test
    fun aSingleChapterBookRestartsFromItsStart() {
        val spot = EndPlan.restartSpot(chapterIndex = 0, chapterCount = 1, positionMs = 40_000, durationMs = 40_000)
        assertEquals(0, spot.chapterIndex)
        assertEquals(0L, spot.offsetMs)
    }

    @Test
    fun aQueueThatRanDryInTheMiddleOfTheBookReadsAgainFromWhereItStands() {
        val spot = EndPlan.restartSpot(chapterIndex = 1, chapterCount = 3, positionMs = 12_500, durationMs = 60_000)
        assertEquals(1, spot.chapterIndex)
        assertEquals(12_500L, spot.offsetMs)
    }

    @Test
    fun aQueueThatRanDryInTheMiddleOfTheLastChapterIsNotTheEndOfTheBook() {
        val spot = EndPlan.restartSpot(chapterIndex = 2, chapterCount = 3, positionMs = 30_000, durationMs = 95_000)
        assertEquals(2, spot.chapterIndex)
        assertEquals(30_000L, spot.offsetMs)
    }
}
