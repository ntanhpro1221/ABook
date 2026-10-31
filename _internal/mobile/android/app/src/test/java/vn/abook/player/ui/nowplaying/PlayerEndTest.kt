package vn.abook.player.ui.nowplaying

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import vn.abook.player.ui.data.Last
import vn.abook.player.ui.data.ListenBook
import vn.abook.player.ui.data.ListenState
import vn.abook.player.ui.data.Progress
import vn.abook.player.ui.data.SeriesLink

/** Sau khi nghe hết: tập / phần kế của bộ, cuốn khác để mời, dòng phụ - cùng luật với web (model.ts, labels.ts). */
class PlayerEndTest {
    private fun book(id: String, title: String, available: Int = 3, heard: Double = 0.0, total: Double = 0.0, last: Double? = null,
                     finished: Boolean = false, text: Boolean = false, series: SeriesLink? = null, duration: Double = 3600.0) =
        ListenBook(id, title, duration = duration, chaptersTotal = 3, chaptersAvailable = available, textOnly = text, series = series,
            state = ListenState(last = last?.let { Last(1, 5.0, it) }),
            progress = Progress(heard, total, if (total > 0) (heard / total).toFloat() else 0f, 0, finished))

    @Test
    fun `next volume of the same series is the next number with audio`() {
        val books = listOf(book("a", "Bộ truyện · Tập 1"), book("b", "Bộ truyện · Tập 2"), book("c", "Bộ truyện · Tập 3"), book("d", "Truyện khác"))
        assertEquals("b", PlayerEnd.nextVolume(books, "a")?.id)
        assertEquals("c", PlayerEnd.nextVolume(books, "b")?.id)
        assertNull(PlayerEnd.nextVolume(books, "c"))
        assertNull("không đánh số thì không có tập kế", PlayerEnd.nextVolume(books, "d"))
        val gap = listOf(book("a", "Bộ · Tập 1"), book("b", "Bộ · Tập 2", available = 0), book("c", "Bộ · Tập 3"))
        assertEquals("tập chưa có audio bị bỏ qua", "c", PlayerEnd.nextVolume(gap, "a")?.id)
    }

    @Test
    fun `only a later part of the same book is played on without asking`() {
        val part = book("p2", "Tên · Phần 2", series = SeriesLink("p1", 2))
        val volume = book("v2", "Bộ · Tập 2")
        assertEquals("p2", PlayerEnd.continuingPart(part)?.id)
        assertNull("tập khác của một bộ chỉ được mời", PlayerEnd.continuingPart(volume))
        assertEquals("p2", PlayerEnd.continuingPart(book("p2", "Tên · Phần 2"))?.id)
        assertNull(PlayerEnd.continuingPart(null))
    }

    @Test
    fun `other books are unfinished, playable now, started ones first and newest first, at most three`() {
        val books = listOf(
            book("now", "Đang nghe"), book("done", "Xong", finished = true), book("none", "Chưa có audio", available = 0),
            book("old", "Nghe dở cũ", last = 100.0), book("new", "Nghe dở mới", last = 900.0),
            book("fresh", "Chưa nghe"), book("text", "Chỉ có chữ", available = 0, text = true), book("fresh2", "Chưa nghe 2"),
        )
        assertEquals(listOf("new", "old", "fresh"), PlayerEnd.others(books, "now", speaks = false).map { it.id })
        val spoken = PlayerEnd.others(books, "now", speaks = true, limit = 10).map { it.id }
        assertEquals("sách chỉ có chữ chỉ mời khi máy có giọng đọc", listOf("new", "old", "fresh", "text", "fresh2"), spoken)
        assertTrue(PlayerEnd.others(books, "now", speaks = false, skipId = "new").none { it.id == "new" })
    }

    @Test
    fun `line under an offered book`() {
        assertEquals("Đã nghe 25% cả cuốn · còn 45 phút", PlayerEnd.line(book("a", "t", heard = 900.0, total = 3600.0)))
        assertEquals("Chưa nghe · 1 giờ", PlayerEnd.line(book("a", "t", duration = 3600.0)))
        assertEquals("Chưa nghe · 3 chương", PlayerEnd.line(book("a", "t", duration = 0.0)))
    }

    @Test
    fun `next label is the series place or the whole title`() {
        assertEquals("Tập 17", PlayerEnd.nextLabel("Bộ truyện · Tập 17"))
        assertEquals("Phần 2", PlayerEnd.nextLabel("Tên · Phần 2"))
        assertEquals("Truyện không số", PlayerEnd.nextLabel("Truyện không số"))
    }

    @Test
    fun `choices bundle the next volume, whether it continues, and the others without repeating it`() {
        val books = listOf(book("a", "Tên"), book("b", "Tên · Phần 2", series = SeriesLink("a", 2)), book("c", "Truyện khác"))
        val choices = PlayerEnd.choices(books, "a", speaks = false)
        assertEquals("b", choices.next?.id)
        assertTrue(choices.continues)
        assertEquals(listOf("c"), choices.others.map { it.id })
    }
}
