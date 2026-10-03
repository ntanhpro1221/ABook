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
    fun text_chapters_are_heard_too_and_resume_from_the_saved_virtual_seconds() {
        // Sách chỉ-có-chữ (TextBook.kt / textbook.py): `state` "text", `text` = mục chữ, không file, không thời lượng - giọng máy đọc to (ReadAloud).
        val manifest = JSONObject().put("id", "t1").put("title", "Chữ").put("chapters", JSONArray()
            .put(JSONObject().put("id", 1).put("fullTitle", "Một").put("available", false).put("state", "text").put("text", "texts/1.txt").put("duration", 0))
            .put(JSONObject().put("id", 2).put("fullTitle", "Hai").put("available", false).put("state", "text").put("text", "texts/2.txt").put("duration", 0))
            .put(JSONObject().put("id", 3).put("fullTitle", "Ba").put("available", true).put("file", "chapters/3.mp3").put("duration", 600.0))
            .put(JSONObject().put("id", 4).put("fullTitle", "Bốn").put("available", false).put("file", JSONObject.NULL)))
        val chapters = LibraryTree.chapters(manifest)
        assertEquals(listOf(1, 2, 3), chapters.map { it.id })
        assertEquals(listOf("texts/1.txt", "texts/2.txt", ""), chapters.map { it.text })
        assertEquals(listOf(true, true, false), chapters.map { it.isText })
        val listening = state(2, 42.5, at = 10.0)
        assertEquals(listOf("book/t1"), LibraryTree.books(listOf(manifest to listening)).map { it.id })
        assertEquals(LibraryTree.Start("t1", 2, 42.5), LibraryTree.start("book/t1", manifest, listening))
        assertEquals(listOf("Giọng máy đọc", "Đang nghe dở", "10 phút"), LibraryTree.chapterNodes(manifest, listening).map { it.subtitle })
    }

    @Test
    fun the_player_load_call_and_the_book_agree_on_what_a_text_chapter_is() {
        // Lệnh `load` của giao diện (nativeEngine.ts) chỉ gửi `text` + `file` rỗng; gói sách gửi `state` "text".
        assertEquals("texts/5.txt", LibraryTree.textEntry(JSONObject().put("id", 5).put("file", "").put("text", "texts/5.txt")))
        assertEquals("texts/7.txt", LibraryTree.textEntry(JSONObject().put("id", 7).put("state", "text")))
        assertEquals("", LibraryTree.textEntry(JSONObject().put("id", 8).put("file", "chapters/8.mp3").put("text", "texts/8.txt")))
        assertEquals("", LibraryTree.textEntry(JSONObject().put("id", 9).put("file", "chapters/9.mp3")))
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

    @Test
    fun a_chapter_of_a_whole_series_file_says_which_part_it_belongs_to() {
        val manifest = JSONObject().put("id", "s1").put("title", "Truyện X")
            .put("parts", JSONArray().put(JSONObject().put("part", 1)).put(JSONObject().put("part", 2)))
            .put("chapters", JSONArray()
                .put(chapter(100001, 1, "chapters/1/a.mp3")).put(chapter(200001, 2, "chapters/2/a.mp3")))
        val nodes = LibraryTree.chapterNodes(manifest, state(200001, 12.0))
        assertEquals(listOf("chapter/s1/100001", "chapter/s1/200001"), nodes.map { it.id })
        assertEquals(listOf("Phần 1 · 15 phút", "Phần 2 · Đang nghe dở"), nodes.map { it.subtitle })
        assertEquals(LibraryTree.Start("s1", 200001, 12.0), LibraryTree.start("chapter/s1/200001", manifest, state(200001, 12.0)))
        assertEquals("chương ở thư mục phần vẫn nghe được", "chapters/2/a.mp3", LibraryTree.chapters(manifest)[1].file)
        // Sách một phần (hay file chỉ có một phần) không thêm gì vào dòng phụ.
        val single = JSONObject().put("id", "s2").put("parts", JSONArray().put(JSONObject().put("part", 1)))
            .put("chapters", JSONArray().put(chapter(100001, 1, "chapters/1/a.mp3")))
        assertEquals(listOf("15 phút"), LibraryTree.chapterNodes(single, state()).map { it.subtitle })
    }

    private fun chapter(id: Int, part: Int, file: String) = JSONObject().put("id", id).put("part", part)
        .put("fullTitle", "Chương $id").put("available", true).put("file", file).put("duration", 900.0)
}
