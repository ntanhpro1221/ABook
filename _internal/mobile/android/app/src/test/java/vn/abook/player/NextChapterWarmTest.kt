package vn.abook.player

import org.junit.Assert.assertEquals
import org.junit.Test

/** Tải sẵn bài đầu chương kế khi chương còn <= 120 giây - cùng các ca với musicBed.test.ts "NextChapterWarm". */
class NextChapterWarmTest {
    private val music = NextChapterWarm.Answer(pending = false, unavailable = false, first = "https://x/n.mp3")

    @Test
    fun asksOnlyInsideTheWindowThenWarmsTheFirstCueOnce() {
        val asked = mutableListOf<Int>()
        val warmed = mutableListOf<String>()
        val watch = NextChapterWarm({ id, answer -> asked += id; answer(music) }, { warmed += it }, { 0L })
        watch.update("1:1", 2, NextChapterWarm.WARM_SECONDS + 1)
        watch.update("1:1", 2, 0.0)
        watch.update("1:1", 2, -5.0)
        watch.update("1:1", null, 30.0)
        assertEquals(emptyList<Int>(), asked)
        watch.update("1:1", 2, NextChapterWarm.WARM_SECONDS)
        assertEquals(listOf(2), asked)
        assertEquals(listOf("https://x/n.mp3"), warmed)
        watch.update("1:1", 2, 100.0)
        assertEquals(listOf(2), asked)
    }

    @Test
    fun pendingOrFailedAsksAgainAfterFifteenSecondsSilentChapterStops() {
        var clock = 1_000L
        val answers = listOf(NextChapterWarm.Answer(pending = true, unavailable = false, first = null), null, music)
        val warmed = mutableListOf<String>()
        var asks = 0
        val watch = NextChapterWarm({ _, answer -> answer(answers[asks++]) }, { warmed += it }, { clock })
        watch.update("1:1", 2, 100.0)
        assertEquals(1, asks)
        watch.update("1:1", 2, 99.0)
        assertEquals(1, asks) // chưa tới hạn hỏi lại
        clock += NextChapterWarm.RETRY_MS
        watch.update("1:1", 2, 80.0)
        assertEquals(2, asks)
        clock += NextChapterWarm.RETRY_MS
        watch.update("1:1", 2, 60.0)
        assertEquals(3, asks)
        assertEquals(listOf("https://x/n.mp3"), warmed)

        var silentAsks = 0
        val silent = NextChapterWarm({ _, answer -> silentAsks += 1; answer(NextChapterWarm.Answer(pending = false, unavailable = false, first = null)) }, { warmed += it }, { clock })
        silent.update("1:1", 3, 60.0)
        silent.update("1:1", 3, 59.0)
        assertEquals(1, silentAsks)
        assertEquals(listOf("https://x/n.mp3"), warmed)
    }

    @Test
    fun noCatalogYetAsksAgainLater() {
        var clock = 0L
        var asks = 0
        val watch = NextChapterWarm({ _, answer -> asks += 1; answer(NextChapterWarm.Answer(pending = false, unavailable = true, first = null)) }, {}, { clock })
        watch.update("1:1", 2, 50.0)
        clock += NextChapterWarm.RETRY_MS - 1
        watch.update("1:1", 2, 40.0)
        assertEquals(1, asks)
        clock += 1
        watch.update("1:1", 2, 30.0)
        assertEquals(2, asks)
    }

    @Test
    fun oneAskAtATimeAndANewChapterIsANewTicket() {
        val pendingAnswers = mutableListOf<(NextChapterWarm.Answer?) -> Unit>()
        val asked = mutableListOf<Int>()
        val warmed = mutableListOf<String>()
        val watch = NextChapterWarm({ id, answer -> asked += id; pendingAnswers += answer }, { warmed += it }, { 0L })
        watch.update("1:1", 2, 100.0)
        watch.update("1:1", 2, 99.0)
        watch.update("1:2", 3, 90.0)
        assertEquals(listOf(2), asked) // lời hỏi trước chưa về: không hỏi chồng
        pendingAnswers.removeAt(0)(music)
        watch.update("1:2", 3, 90.0)
        assertEquals(listOf(2, 3), asked)
        pendingAnswers.removeAt(0)(NextChapterWarm.Answer(pending = false, unavailable = false, first = "https://x/m.mp3"))
        assertEquals(listOf("https://x/n.mp3", "https://x/m.mp3"), warmed)
    }
}
