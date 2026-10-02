package vn.abook.player

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** Cây duyệt cho Android Auto (LibraryTree): cuốn nghe gần nhất đầu tiên, chỉ chương có audio, bấm là nghe tiếp đúng chỗ. */
class LibraryTreeTest {
    private fun book(id: String, title: String, vararg chapters: Pair<Int, Boolean>) = JSONObject()
        .put("id", id).put("title", title)
        .put("chapters", JSONArray().also { list ->
            for ((chapter, available) in chapters) {
                list.put(JSONObject().put("id", chapter).put("fullTitle", "Chương $chapter").put("available", available)
                    .put("file", if (available) "chapters/$chapter.mp3" else JSONObject.NULL).put("duration", 900.0))
            }
        })

    private fun state(chapter: Int? = null, seconds: Double = 0.0, at: Double = 0.0, done: Int? = null) = JSONObject()
        .also { if (chapter != null) it.put("last", JSONObject().put("chapterId", chapter).put("seconds", seconds).put("at", at)) }
        .put("chapters", JSONObject().also { if (done != null) it.put(done.toString(), JSONObject().put("done", true)) })

    @Test
    fun the_book_heard_last_comes_first_and_books_without_audio_stay_out() {
        val nodes = LibraryTree.books(listOf(
            book("a", "An") to state(),
            book("b", "Bình", 1 to true) to state(1, 30.0, at = 100.0),
            book("c", "Cúc", 1 to true, 2 to true) to state(),
            book("d", "Dung", 1 to false) to state(),
            book("e", "Én", 1 to true) to state(1, 5.0, at = 200.0),
        ))
        assertEquals(listOf("book/e", "book/b", "book/c"), nodes.map { it.id })
        assertEquals("Nghe tiếp: Chương 1", nodes[0].subtitle)
        assertEquals("2 chương", nodes[2].subtitle)
        assertTrue(nodes.all { it.playable && it.browsable })
    }

    @Test
    fun chapters_say_which_one_is_under_way_and_which_are_heard() {
        val manifest = book("QzpcU8OhY2g_-", "Sách", 1 to true, 2 to true, 3 to false, 4 to true)
        val nodes = LibraryTree.chapterNodes(manifest, state(2, 61.0, done = 1))
        assertEquals(listOf("chapter/QzpcU8OhY2g_-/1", "chapter/QzpcU8OhY2g_-/2", "chapter/QzpcU8OhY2g_-/4"), nodes.map { it.id })
        assertEquals(listOf("Đã nghe", "Đang nghe dở", "15 phút"), nodes.map { it.subtitle })
        assertEquals("QzpcU8OhY2g_-", LibraryTree.bookOf(nodes[0].id))
    }

    @Test
    fun choosing_a_book_resumes_and_choosing_a_chapter_starts_it() {
        val manifest = book("b1", "Sách", 1 to true, 2 to true, 3 to true)
        val listening = state(2, 61.5)
        assertEquals(LibraryTree.Start("b1", 2, 61.5), LibraryTree.start("book/b1", manifest, listening))
        assertEquals(LibraryTree.Start("b1", 1, 0.0), LibraryTree.start("book/b1", manifest, state()))
        assertEquals(LibraryTree.Start("b1", 2, 61.5), LibraryTree.start("chapter/b1/2", manifest, listening))
        assertEquals(LibraryTree.Start("b1", 3, 0.0), LibraryTree.start("chapter/b1/3", manifest, listening))
        assertNull("chương không còn trên máy", LibraryTree.start("chapter/b1/9", manifest, listening))
        assertNull("gói của cuốn khác", LibraryTree.start("book/khac", manifest, listening))
        assertNull(LibraryTree.start(LibraryTree.ROOT, manifest, listening))
    }
}
