package vn.abook.player.ui.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** Ca test của model.test.ts (bộ sách, chỗ nghe tiếp, "Đang nghe", sách cùng tên, tìm) và progress.test.ts, viết lại cho [ListenLogic]. */
class ListenLogicTest {
    private class Item(override val id: String, override val title: String, override val series: SeriesLink? = null, override val isText: Boolean = false) : SeriesItem

    private fun book(id: String, title: String = id, last: Last? = null, finished: Boolean = false, author: String = "", narrator: String = "") =
        ListenBook(id, title, author, narrator, state = ListenState(last = last), progress = Progress.None.copy(finished = finished))

    // ---- seriesOf / seriesIndex / volumeBadge ----

    @Test
    fun `seriesOf reads the volume and the word the book uses for it`() {
        assertEquals(SeriesPlace("title:Throne of Magical Arcana", "Throne of Magical Arcana", 16, "tập"), ListenLogic.seriesOf("Throne of Magical Arcana · Tập 16"))
        assertEquals(SeriesPlace("title:Truyện", "Truyện", 4, "quyển"), ListenLogic.seriesOf("Truyện - Quyển 4"))
        assertEquals(SeriesPlace("title:Nageki", "Nageki", 2, "phần"), ListenLogic.seriesOf("Nageki · Phần 2"))
        assertEquals(3, ListenLogic.seriesOf("Book: Vol. 3").volume)
    }

    @Test
    fun `seriesOf leaves a title without a volume alone`() {
        assertEquals(SeriesPlace("title:Sách lẻ", "Sách lẻ", null, "tập"), ListenLogic.seriesOf("Sách lẻ"))
        assertNull("hậu tố không có dấu ngăn", ListenLogic.seriesOf("Truyện (phần 2)").volume)
    }

    @Test
    fun `seriesOf is case insensitive on accented words`() {
        assertEquals(2, ListenLogic.seriesOf("Nageki · PHẦN 2").volume)
        assertEquals(7, ListenLogic.seriesOf("Truyện · tập 7").volume)
    }

    private val nageki = listOf(Item("a", "Nageki"), Item("b", "Nageki · Phần 2"), Item("c", "Nageki · Phần 3"), Item("d", "Sách lẻ"))

    @Test
    fun `the unnumbered first part of a continued book is part 1`() {
        val places = ListenLogic.seriesIndex(nageki)
        assertEquals(SeriesPlace("title:Nageki", "Nageki", 1, "phần"), places["a"])
        assertEquals(3, places["c"]?.volume)
    }

    @Test
    fun `a book with no numbered sibling is not numbered`() {
        assertNull(ListenLogic.seriesIndex(nageki)["d"]?.volume)
        assertNull(ListenLogic.seriesIndex(listOf(Item("x", "Nageki")))["x"]?.volume)
    }

    @Test
    fun `no guess of volume 1 among look-alike unnumbered copies`() {
        val places = ListenLogic.seriesIndex(listOf(Item("a", "Chuyến phà"), Item("b", "Chuyến phà"), Item("c", "Chuyến phà · Tập 2")))
        assertNull(places["a"]?.volume)
        assertNull(places["b"]?.volume)
        assertEquals(2, places["c"]?.volume)
    }

    @Test
    fun `volume 1 goes to the audiobook not its text-only copy`() {
        val places = ListenLogic.seriesIndex(listOf(Item("text", "Chuyến phà", isText = true), Item("audio", "Chuyến phà"), Item("two", "Chuyến phà · Tập 2")))
        assertEquals(1, places["audio"]?.volume)
        assertNull(places["text"]?.volume)
        assertEquals(places["audio"]?.key, places["two"]?.key)
    }

    @Test
    fun `a lone text-only book is volume 1 when nothing else claims it`() {
        val places = ListenLogic.seriesIndex(listOf(Item("text", "Chuyến phà", isText = true), Item("two", "Chuyến phà · Tập 2")))
        assertEquals(1, places["text"]?.volume)
    }

    @Test
    fun `two audiobooks of one title are not picked between even with a text copy`() {
        val places = ListenLogic.seriesIndex(
            listOf(Item("x", "Chuyến phà"), Item("y", "Chuyến phà"), Item("text", "Chuyến phà", isText = true), Item("two", "Chuyến phà · Tập 2")),
        )
        assertEquals(listOf<Int?>(null, null, null), listOf("x", "y", "text").map { places[it]?.volume })
    }

    @Test
    fun `a renamed part keeps its book and a look-alike title stays out`() {
        val places = ListenLogic.seriesIndex(
            listOf(Item("p1", "lo18"), Item("p2", "Ma pháp thần toạ", SeriesLink("p1", 2)), Item("stray", "lo18 · Phần 2")),
        )
        assertEquals(SeriesPlace("chain:p1", "lo18", 2, "phần"), places["p2"])
        assertEquals(SeriesPlace("chain:p1", "lo18", 1, "phần"), places["p1"])
        assertEquals("title:lo18", places["stray"]?.key)
    }

    @Test
    fun `volumeBadge labels an unnumbered volume and nothing the cover already labels`() {
        assertEquals("Tập 1", ListenLogic.volumeBadge("Chuyến phà", null, 1, "tập"))
        assertEquals("Phần 1", ListenLogic.volumeBadge("Nageki", null, 1, "phần"))
        assertNull(ListenLogic.volumeBadge("Chuyến phà · Tập 2", null, 2, "tập"))
        assertNull(ListenLogic.volumeBadge("Phần đã đổi tên", SeriesLink("p1", 2), 2, "phần"))
        assertNull(ListenLogic.volumeBadge("Sách lẻ", null, null, "tập"))
    }

    // ---- resumePoint ----

    private val chapters = listOf(
        ChapterInfo(1, "Chương 1", 600.0, true),
        ChapterInfo(2, "Chương 2", 600.0, true),
        ChapterInfo(3, "Chương 3", 0.0, false),
    )

    private fun st(last: Last? = null, done: List<Int> = emptyList(), heard: Map<Int, Double> = emptyMap()) = ListenState(
        last = last,
        chapters = done.associateWith { ChapterRecord(600.0, true) } + heard.mapValues { ChapterRecord(it.value, false) },
    )

    private fun spot(id: Int, at: Double) = ResumeSpot(id, "Chương $id", at)

    @Test
    fun `resumes where the listener stopped`() {
        assertEquals(spot(1, 120.0), ListenLogic.resumePoint(st(Last(1, 120.0, 1.0)), true, chapters))
    }

    @Test
    fun `moves on when the chapter was nearly finished`() {
        assertEquals(spot(2, 0.0), ListenLogic.resumePoint(st(Last(1, 590.0, 1.0)), true, chapters))
    }

    @Test
    fun `stays at the end of the last chapter made so far while the book is still being made`() {
        assertEquals(spot(2, 595.0), ListenLogic.resumePoint(st(Last(2, 595.0, 1.0)), false, chapters))
    }

    @Test
    fun `starts with the first chapter not heard to the end`() {
        assertEquals(spot(2, 0.0), ListenLogic.resumePoint(st(done = listOf(1)), true, chapters))
    }

    @Test
    fun `moves on into the next chapter where it was heard to`() {
        assertEquals(spot(2, 111.0), ListenLogic.resumePoint(st(Last(1, 590.0, 1.0), heard = mapOf(2 to 111.0)), true, chapters))
        assertEquals(spot(1, 0.0), ListenLogic.resumePoint(st(heard = mapOf(2 to 111.0)), true, chapters))
        assertEquals("chương kế cũng đã gần hết: từ đầu", spot(2, 0.0), ListenLogic.resumePoint(st(Last(1, 590.0, 1.0), heard = mapOf(2 to 595.0)), true, chapters))
    }

    @Test
    fun `no playable chapter gives no spot and a text chapter plays`() {
        assertNull(ListenLogic.resumePoint(ListenState.Empty, true, listOf(ChapterInfo(1, "a", 0.0, false))))
        assertEquals(ResumeSpot(1, "a", 0.0), ListenLogic.resumePoint(ListenState.Empty, true, listOf(ChapterInfo(1, "a", 0.0, false, textOnly = true))))
    }

    @Test
    fun `a text chapter uses the duration the player recorded`() {
        val text = listOf(ChapterInfo(1, "t1", 0.0, false, textOnly = true), ChapterInfo(2, "t2", 0.0, false, textOnly = true))
        val state = ListenState(last = Last(1, 395.0, 1.0), chapters = mapOf(1 to ChapterRecord(395.0, false, duration = 400.0)))
        assertEquals(ResumeSpot(2, "t2", 0.0), ListenLogic.resumePoint(state, true, text))
    }

    @Test
    fun `newer compares revisions then falls back to time`() {
        assertTrue(ListenLogic.newer(Rev(5, "a"), 1.0, Rev(4, "z"), 9.0))
        assertFalse(ListenLogic.newer(Rev(4, "a"), 1.0, Rev(4, "a"), 1.0))
        assertTrue(ListenLogic.newer(Rev(4, "b"), 1.0, Rev(4, "a"), 1.0))
        assertTrue(ListenLogic.newer(null, 5.0, null, 4.0))
        assertTrue(ListenLogic.newer(Rev(1, "a", "1"), 0.0, Rev(9, "a"), 0.0))
    }

    // ---- bookProgress / textBookProgress (progress.test.ts) ----

    private val two = listOf(ChapterInfo(1, "1", 600.0, true), ChapterInfo(2, "2", 600.0, true))
    private val allDone = mapOf(1 to ChapterRecord(600.0, true), 2 to ChapterRecord(600.0, true))

    @Test
    fun `heard everything then went back to chapter 1 is listening again`() {
        val again = ListenLogic.bookProgress(ListenState(chapters = allDone, last = Last(1, 164.8, 500.0)), two)
        assertFalse(again.finished)
        assertTrue(again.rewound)
        assertEquals(164.8, again.heardSeconds, 1e-9)
        val partial = ListenLogic.bookProgress(ListenState(chapters = allDone, last = Last(2, 300.0, 500.0)), two, complete = false)
        assertEquals(900.0, partial.heardSeconds, 1e-9)
        assertFalse(partial.caughtUp)
    }

    @Test
    fun `stopping at the tail of the last chapter or marking finished after is finished`() {
        assertTrue(ListenLogic.bookProgress(ListenState(chapters = allDone, last = Last(2, 595.0, 500.0)), two).finished)
        assertTrue(ListenLogic.bookProgress(ListenState(chapters = allDone, last = Last(1, 30.0, 500.0), finished = true, finishedAt = 600.0), two).finished)
        assertFalse(ListenLogic.bookProgress(ListenState(chapters = allDone, last = Last(1, 30.0, 500.0), finished = true, finishedAt = 400.0), two).finished)
    }

    @Test
    fun `a book still being made that was heard to the end has caught up`() {
        val p = ListenLogic.bookProgress(ListenState(chapters = allDone, last = Last(2, 595.0, 1.0)), two, complete = false)
        assertTrue(p.caughtUp)
        assertFalse(p.finished)
        assertEquals(1f, p.fraction, 1e-6f)
    }

    @Test
    fun `a partly heard chapter counts what was heard and not more than its length`() {
        val p = ListenLogic.bookProgress(ListenState(chapters = mapOf(1 to ChapterRecord(900.0, false))), two)
        assertEquals(600.0, p.heardSeconds, 1e-9)
        assertEquals(0.5f, p.fraction, 1e-6f)
    }

    private val text4 = (1..4).map { ChapterInfo(it, "$it", 0.0, false, textOnly = true) }

    @Test
    fun `text book progress follows chapters`() {
        assertEquals(0f, ListenLogic.textBookProgress(ListenState.Empty, text4).fraction, 0f)
        val some = ListenLogic.textBookProgress(
            ListenState(chapters = mapOf(1 to ChapterRecord(300.0, true), 2 to ChapterRecord(100.0, false, 400.0))), text4,
        )
        assertEquals((1 + 0.25f) / 4, some.fraction, 1e-6f)
        assertEquals(1, some.chaptersDone)
        assertFalse(some.finished)
    }

    @Test
    fun `text book is full when all done or marked and never above 1`() {
        val all = text4.associate { it.id to ChapterRecord(10.0, true) }
        assertTrue(ListenLogic.textBookProgress(ListenState(chapters = all), text4).let { it.fraction == 1f && it.finished })
        assertTrue(ListenLogic.textBookProgress(ListenState(finished = true), text4).let { it.fraction == 1f && it.finished })
        assertEquals(0.25f, ListenLogic.textBookProgress(ListenState(chapters = mapOf(1 to ChapterRecord(900.0, false, 400.0))), text4).fraction, 1e-6f)
    }

    // ---- listeningBook ----

    private val shelf = listOf(
        book("a", last = Last(1, 5.0, 100.0)), book("b", last = Last(1, 5.0, 300.0)), book("c"), book("d", last = Last(1, 5.0, 900.0), finished = true),
    )

    @Test
    fun `listening book is the most recently heard unfinished one`() {
        assertEquals("b", ListenLogic.listeningBook(shelf, null)?.id)
        assertNull(ListenLogic.listeningBook(listOf(book("c")), null))
    }

    @Test
    fun `listening book follows the book in the player before the library knows its spot`() {
        assertEquals("c", ListenLogic.listeningBook(shelf, "c")?.id)
        assertEquals("a", ListenLogic.listeningBook(shelf, "a")?.id)
    }

    @Test
    fun `a playing book that is finished or not on the shelf is ignored`() {
        assertEquals("b", ListenLogic.listeningBook(shelf, "d")?.id)
        assertEquals("b", ListenLogic.listeningBook(shelf, "zzz")?.id)
    }

    // ---- tìm / sách cùng tên ----

    @Test
    fun `fold removes Vietnamese marks and case`() {
        assertEquals("duc tri · tap 16", ListenLogic.fold("Đức Trí · Tập 16"))
        assertEquals("dd", ListenLogic.fold("Đđ"))
    }

    @Test
    fun `a book matches by title author or narrator without marks or case`() {
        val tatDen = book("1", "Tắt đèn", author = "Ngô Tất Tố", narrator = "Đức Trí")
        for (query in listOf("tat den", "NGO TAT TO", "duc tri", "")) assertTrue(query, ListenLogic.matches(tatDen, ListenLogic.fold(query.trim())))
        assertFalse(ListenLogic.matches(tatDen, ListenLogic.fold("nguyen")))
        assertTrue(ListenLogic.matches(book("2", "Sống mãi", author = "Nguyễn Huy Thiệp"), ListenLogic.fold("nguyen huy")))
        assertFalse(ListenLogic.matches(book("3", "Chí Phèo"), ListenLogic.fold("nguyễn")))
    }

    @Test
    fun `twins share a title ignoring case accents and spacing`() {
        val twins = ListenLogic.twinIds(listOf(book("a", "Truyện Kiều"), book("b", "truyen  kieu"), book("c", "Tắt đèn")))
        assertEquals(setOf("a", "b"), twins)
        assertTrue(ListenLogic.twinIds(emptyList()).isEmpty())
    }

    // ---- dòng trạng thái ----

    @Test
    fun `status line of a text book names the author and chapters`() {
        assertEquals("Nguyễn Nhật Ánh · 3 chương", ListenLogic.progressText(ListenBook("x", "t", author = "Nguyễn Nhật Ánh", chaptersTotal = 3, textOnly = true)))
        assertEquals("3 chương", ListenLogic.progressText(ListenBook("x", "t", chaptersTotal = 3, textOnly = true)))
        assertEquals("3 chương", ListenLogic.progressText(ListenBook("x", "t", author = "  ", chaptersTotal = 3, textOnly = true)))
    }

    @Test
    fun `status line of an audio book`() {
        val whole = ListenBook("x", "t", duration = 7500.0, chaptersTotal = 5, chaptersAvailable = 5)
        assertEquals("2 giờ 5 phút", ListenLogic.progressText(whole))
        val half = ListenBook("x", "t", duration = 7200.0, chaptersTotal = 5, chaptersAvailable = 5, progress = Progress.None.copy(heardSeconds = 3600.0, fraction = 0.5f))
        assertEquals("Còn 1 giờ", ListenLogic.progressText(half))
        val fast = ListenBook(
            "x", "t", duration = 7200.0, chaptersTotal = 5, chaptersAvailable = 5,
            state = ListenState(rate = 2.0), progress = Progress.None.copy(heardSeconds = 3600.0),
        )
        assertEquals("Còn 30 phút", ListenLogic.progressText(fast))
        assertEquals("Đã nghe xong", ListenLogic.progressText(ListenBook("x", "t", progress = Progress.None.copy(finished = true))))
        assertEquals("3/9 chương", ListenLogic.progressText(ListenBook("x", "t", chaptersTotal = 9, chaptersAvailable = 3, complete = false)))
        assertEquals(
            "Đã nghe hết phần đã có · 3/9 chương",
            ListenLogic.progressText(ListenBook("x", "t", chaptersTotal = 9, chaptersAvailable = 3, complete = false, progress = Progress.None.copy(caughtUp = true))),
        )
    }

    @Test
    fun `remote place names the device`() {
        assertEquals("Trên máy tính", ListenLogic.remotePlace(ListenBook("x", "t", remote = RemoteRef("máy tính"))))
        assertEquals("Trên Máy A", ListenLogic.remotePlace(ListenBook("x", "t", remote = RemoteRef("Máy A"))))
    }
}
