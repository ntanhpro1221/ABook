package vn.abook.player.ui.nowplaying

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import vn.abook.player.ui.data.PlayerChapter
import vn.abook.player.ui.data.PreparePlan
import vn.abook.player.ui.data.PrepareStatus
import vn.abook.player.ui.data.PreparedChapter

/** Chữ của "Làm trước" - cùng ca với web prepareAhead.ts. */
class PrepareTextTest {
    @Test
    fun `only voices that run on the device are offered`() {
        assertTrue(PrepareText.canPrepare("vieneu:a"))
        assertTrue(PrepareText.canPrepare("supertonic:b"))
        assertFalse(PrepareText.canPrepare("device:vi-VN"))
        assertFalse(PrepareText.canPrepare(""))
    }

    @Test
    fun `upcoming are the text chapters after the current one, at most five`() {
        val chapters = listOf(PlayerChapter(1, "a", 1000)) + (2..9).map { PlayerChapter(it, "c$it", 0, "t/$it.txt") }
        assertEquals(listOf(2, 3, 4, 5, 6), PrepareText.upcoming(chapters, 1).map { it.id })
        assertEquals(listOf(8, 9), PrepareText.upcoming(chapters, 7).map { it.id })
        assertTrue(PrepareText.upcoming(chapters, 9).isEmpty())
        val mixed = listOf(PlayerChapter(1, "a", 1000), PlayerChapter(2, "b", 1000), PlayerChapter(3, "c", 0, "t"))
        assertEquals("chương đã có audio thì khỏi làm trước", listOf(3), PrepareText.upcoming(mixed, 1).map { it.id })
    }

    @Test
    fun `button and job names`() {
        assertEquals("Làm trước chương sau", PrepareText.startLabel(1))
        assertEquals("Làm trước 3 chương", PrepareText.startLabel(3))
        assertEquals("Chương 2", PrepareText.jobLabel(listOf(PlayerChapter(2, "Chương 2", 0, "t"))))
        assertEquals("2 chương tới", PrepareText.jobLabel(listOf(PlayerChapter(2, "x", 0, "t"), PlayerChapter(3, "y", 0, "t"))))
    }

    @Test
    fun `spoken duration`() {
        assertEquals("dưới 1 phút", PrepareText.spokenDuration(20))
        assertEquals("khoảng 12 phút", PrepareText.spokenDuration(720))
        assertEquals("khoảng 1 giờ", PrepareText.spokenDuration(3600))
        assertEquals("khoảng 1 giờ 20 phút", PrepareText.spokenDuration(4800))
    }

    @Test
    fun `plan sentence`() {
        assertEquals("2 giờ nghe · máy cần khoảng 1 giờ 50 phút.", PrepareText.planLabel(PreparePlan(3, 3, 7200, 6600)))
        assertEquals("30 phút nghe.", PrepareText.planLabel(PreparePlan(2, 2, 1800, null)))
        assertEquals("Vừa chỗ trống cho 2 chương: 30 phút nghe.", PrepareText.planLabel(PreparePlan(2, 5, 1800, null)))
        assertEquals("", PrepareText.planLabel(PreparePlan()))
    }

    @Test
    fun `progress sentences`() {
        val chapters = listOf(PreparedChapter(2, "b", 10, 10, true), PreparedChapter(3, "c", 10, 2, false))
        assertEquals("Đã sẵn sàng 1/2 chương · chờ cắm sạc", PrepareText.label(PrepareStatus("running", chapters = chapters, waitingFor = "charging")))
        assertEquals("Đã sẵn sàng 1/2 chương · còn khoảng 5 phút", PrepareText.label(PrepareStatus("running", chapters = chapters, secondsLeft = 300)))
        assertEquals("Đã sẵn sàng 1/2 chương - phần còn lại làm tiếp khi bạn nghe tới.", PrepareText.label(PrepareStatus("done", chapters = chapters)))
        assertEquals("Đã dừng làm trước (đã sẵn sàng 1/2 chương).", PrepareText.label(PrepareStatus("cancelled", chapters = chapters)))
        assertEquals("Đang làm trước 2 chương tới (30 phút nghe): 4/20 đoạn, còn khoảng 3 phút.",
            PrepareText.label(PrepareStatus("running", label = "2 chương tới", total = 20, done = 4, audioSeconds = 1800, secondsLeft = 180)))
        assertEquals("Đã làm trước các chương tới: nghe liền mạch, không cần chờ.", PrepareText.label(PrepareStatus("done")))
        assertEquals("Làm trước bị dừng.", PrepareText.label(PrepareStatus("error")))
        assertEquals("Hết chỗ", PrepareText.label(PrepareStatus("error", error = "Hết chỗ")))
        assertEquals("", PrepareText.label(PrepareStatus()))
    }

    @Test
    fun `a job is mine when voice and book are the same`() {
        val status = PrepareStatus("running", "vieneu:a", bookId = "b")
        assertTrue(PrepareText.mine(status, "vieneu:a", "b"))
        assertFalse(PrepareText.mine(status, "vieneu:z", "b"))
        assertFalse(PrepareText.mine(status, "vieneu:a", "other"))
        assertFalse(PrepareText.mine(PrepareStatus(), "vieneu:a", "b"))
    }
}
