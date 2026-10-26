package vn.abook.player.ui.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/** Ca test của librarySort.test.ts và LibraryScreen (lọc, tìm, xếp, gom bộ) cho [Library]. */
class LibraryViewTest {
    private fun book(
        id: String,
        title: String = id,
        author: String = "",
        last: Double? = null,
        finished: Boolean = false,
        heard: Double = 0.0,
        addedAt: Double? = null,
        updatedAt: Double? = null,
        series: SeriesLink? = null,
        textOnly: Boolean = false,
    ) = ListenBook(
        id, title, author,
        updatedAt = updatedAt, addedAt = addedAt, textOnly = textOnly, series = series,
        state = ListenState(last = last?.let { Last(1, 10.0, it) }),
        progress = Progress.None.copy(finished = finished, heardSeconds = heard),
    )

    @Test
    fun `a book is finished listening or new`() {
        assertEquals(LibraryFilter.Finished, Library.stateOf(book("a", finished = true, last = 5.0)))
        assertEquals(LibraryFilter.Listening, Library.stateOf(book("a", last = 5.0)))
        assertEquals(LibraryFilter.Listening, Library.stateOf(book("a", heard = 30.0)))
        assertEquals(LibraryFilter.New, Library.stateOf(book("a")))
    }

    @Test
    fun `recent first puts the last heard book first then the most recently updated`() {
        val sorted = Library.recentFirst(listOf(book("old", last = 10.0), book("none"), book("new", last = 90.0), book("upd", updatedAt = 50.0)))
        assertEquals(listOf("new", "old", "upd", "none"), sorted.map { it.id })
    }

    @Test
    fun `names compare without marks and by number not by digits`() {
        assertTrue(Library.compareNames("Tập 2", "Tập 10") < 0)
        assertTrue(Library.compareNames("Ăn", "Bơ") < 0)
        assertTrue(Library.compareNames("Đức", "Dung") < 0)
        assertEquals(0, Library.compareNames("Tắt Đèn", "tat den"))
        assertTrue(Library.compareNames("a", "a1") < 0)
    }

    @Test
    fun `sort by title author and added`() {
        val books = listOf(
            book("c", "Tập 10", author = "Nam Cao", addedAt = 1.0),
            book("a", "Tập 2", author = "", addedAt = 3.0),
            book("b", "Bài", author = "Ngô Tất Tố", updatedAt = 2.0),
        )
        assertEquals(listOf("b", "a", "c"), Library.sort(books, LibrarySort.Title).map { it.id })
        assertEquals("sách không tác giả đứng sau", listOf("c", "b", "a"), Library.sort(books, LibrarySort.Author).map { it.id })
        assertEquals(listOf("a", "b", "c"), Library.sort(books, LibrarySort.Added).map { it.id })
        assertEquals(listOf("c", "a", "b"), Library.sort(books, LibrarySort.Recent).map { it.id })
    }

    @Test
    fun `volumes of one series become one tile at the first member and singles stay singles`() {
        val tiles = Library.tiles(listOf(book("l", "Lẻ"), book("a2", "Truyện · Tập 2"), book("a1", "Truyện · Tập 1")), emptySet())
        assertEquals(2, tiles.size)
        assertEquals("book:l", tiles[0].key)
        val series = tiles[1] as ShelfTile.Series
        assertEquals("title:Truyện", series.key)
        assertEquals("Truyện", series.label)
        assertEquals("tập", series.unit)
        assertEquals(listOf("a1", "a2"), series.books.map { it.id })
        assertEquals("a1", series.first.id)
        assertTrue(series.badges.isEmpty())
    }

    @Test
    fun `an unnumbered first part gets a badge and a twin is marked`() {
        val tiles = Library.tiles(listOf(book("n1", "Nageki"), book("n2", "Nageki · Phần 2")), emptySet())
        val series = tiles.single() as ShelfTile.Series
        assertEquals("Phần 1", series.badges["n1"])
        val twin = Library.tiles(listOf(book("t1", "Truyện Kiều"), book("t2", "truyen kieu")), setOf("t1", "t2"))
        assertTrue((twin[0] as ShelfTile.Single).twin)
    }

    @Test
    fun `a series with a book on another device knows it`() {
        val remote = ListenBook("r", "Bộ · Tập 1", remote = RemoteRef("máy tính"))
        val series = Library.tiles(listOf(remote, book("s", "Bộ · Tập 2")), emptySet()).single() as ShelfTile.Series
        assertTrue(series.hasRemote)
    }

    private val shelf = listOf(
        book("new", "Tắt đèn", author = "Ngô Tất Tố"),
        book("mid", "Chí Phèo", author = "Nam Cao", last = 100.0, heard = 60.0),
        book("done", "Số đỏ", author = "Vũ Trọng Phụng", last = 50.0, finished = true),
    )

    @Test
    fun `filter keeps only that state and the count is of the whole shelf`() {
        val view = Library.view(shelf, LibraryFilter.Listening, "", LibrarySort.Recent)
        assertEquals(listOf("book:mid"), view.tiles.map { it.key })
        assertEquals(1, view.shown)
        assertEquals(3, view.total)
        assertEquals(3, Library.view(shelf, LibraryFilter.All, "", LibrarySort.Recent).tiles.size)
        assertEquals("book:done", Library.view(shelf, LibraryFilter.Finished, "", LibrarySort.Recent).tiles.single().key)
    }

    @Test
    fun `search works without marks`() {
        val view = Library.view(shelf, LibraryFilter.New, "TAT DEN", LibrarySort.Recent)
        assertEquals(listOf("book:new"), view.tiles.map { it.key })
        assertTrue(Library.view(shelf, LibraryFilter.All, "không có", LibrarySort.Recent).tiles.isEmpty())
    }

    @Test
    fun `demo library is deterministic and has every shape of the grid`() {
        val a = DemoLibrary.books(30)
        val b = DemoLibrary.books(30)
        assertEquals(30, a.size)
        assertEquals(a.map { it.id }, b.map { it.id })
        assertEquals(a.map { it.title }, b.map { it.title })
        assertEquals(30, a.map { it.id }.toSet().size)
        val view = Library.view(a, LibraryFilter.All, "", LibrarySort.Recent)
        assertTrue("có bộ nhiều tập", view.tiles.any { it is ShelfTile.Series })
        assertTrue("có sách chỉ-chữ", a.any { it.textOnly })
        assertTrue("có sách trên máy khác", a.any { it.remote != null })
        assertTrue("có cuốn đã xong", a.any { it.progress.finished })
        assertTrue("có cuốn nghe dở", a.any { Library.stateOf(it) == LibraryFilter.Listening })
        assertTrue(DemoLibrary.books(0).isEmpty())
    }
}
