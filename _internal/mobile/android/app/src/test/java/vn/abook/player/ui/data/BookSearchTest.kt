package vn.abook.player.ui.data

import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** "Tìm trong sách" (bê ca của findText.test.ts / bookSearch.test.ts): không dấu, không hoa thường, tô đúng chữ gốc, kết quả theo thứ tự chương. */
class BookSearchTest {
    private fun line(id: Int, text: Boolean = false) = ChapterLine(id, "Chương $id", 60.0, available = !text, textOnly = text, heard = 0f, done = false)

    @Test
    fun `query is folded and needs two characters`() {
        assertEquals("nguyen an", BookSearch.foldedQuery("  Nguyễn   An "))
        assertEquals("", BookSearch.foldedQuery("a"))
        assertEquals("dd", BookSearch.foldedQuery("Đđ"))
    }

    @Test
    fun `fold keeps one character per character for plain text`() {
        assertEquals("tieng viet co dau", BookSearch.fold("Tiếng Việt có dấu"))
        assertEquals("a b c", BookSearch.fold("a\nb\tc"))
    }

    @Test
    fun `span maps the folded match back onto the original text`() {
        val text = "Anh Đức Trí đến rồi"
        val folded = BookSearch.fold(text)
        val at = folded.indexOf("duc tri")
        val span = BookSearch.span(text, at, "duc tri".length)!!
        assertEquals("Đức Trí", text.substring(span[0], span[1]))
    }

    @Test
    fun `span keeps a combining mark that trails the last letter`() {
        // "e" + dấu sắc rời (NFD): dấu thuộc về chữ e.
        val text = "chén tra"
        val at = BookSearch.fold(text).indexOf("chen")
        val span = BookSearch.span(text, at, 4)!!
        assertEquals("chén", text.substring(span[0], span[1]))
    }

    @Test
    fun `span is null for an impossible match`() {
        assertNull(BookSearch.span("abc", 5, 2))
        assertNull(BookSearch.span("abc", 0, 0))
    }

    @Test
    fun `script passages skip scene breaks and keep the start time`() {
        val raw = """{"segments":[{"text":"Một","start":1.5},{"text":"***","sceneBreak":true},{"text":"Hai","start":null}]}"""
        val passages = BookSearch.scriptPassages(raw)!!
        assertEquals(listOf("Một", "Hai"), passages.map { it.text })
        assertEquals(1.5, passages[0].start!!, 0.0)
        assertNull(passages[1].start)
        assertNull(BookSearch.scriptPassages("không phải json"))
    }

    @Test
    fun `text passages split paragraphs into sentences`() {
        val passages = BookSearch.textPassages("Câu một. Câu hai!\n\nĐoạn mới… tiếp")
        assertEquals(listOf("Câu một.", "Câu hai!", "Đoạn mới…", "tiếp"), passages.map { it.text })
    }

    @Test
    fun `find gives the first match of each passage with the whole passage`() {
        val chapter = BookSearch.folded(listOf(Passage("Ông Đức Trí và Đức Trí", 3.0), Passage("không có"), Passage("ĐỨC TRÍ\nxuống dòng")))
        val hits = BookSearch.find(7, chapter, "duc tri")
        assertEquals(2, hits.size)
        assertEquals("Đức Trí", hits[0].text.substring(hits[0].matchStart, hits[0].matchEnd))
        assertEquals(4, hits[0].matchStart)
        assertEquals(3.0, hits[0].start!!, 0.0)
        assertEquals(2, hits[1].index)
        // Xuống dòng thành dấu cách, chỉ số ký tự giữ nguyên.
        assertEquals("ĐỨC TRÍ xuống dòng", hits[1].text)
    }

    @Test
    fun `run walks chapters in order, caches them and reports failures`() = runBlocking {
        val texts = mapOf(1 to listOf(Passage("sách hay")), 2 to null, 3 to listOf(Passage("Sách khác"), Passage("không")))
        val cache = HashMap<Int, FoldedChapter>()
        var loads = 0
        var last: FindProgress? = null
        val chapters = listOf(line(1), line(2), line(3))
        val load: suspend (List<ChapterLine>) -> Unit = { lot ->
            for (chapter in lot) {
                loads++
                val passages = texts[chapter.id]
                cache[chapter.id] = if (passages == null) FoldedChapter(emptyList(), emptyList(), failed = true) else BookSearch.folded(passages)
            }
        }
        BookSearch.run(chapters, "sach", cache, load) { last = it }
        val progress = last!!
        assertTrue(progress.done)
        assertEquals(2, progress.total)
        assertEquals(1, progress.failed)
        assertEquals(listOf(1, 3), progress.hits.map { it.chapterId })
        assertEquals(3, loads)
        // Gõ thêm chữ: không đọc lại chương đã có.
        BookSearch.run(chapters, "sach k", cache, load) { last = it }
        assertEquals(3, loads)
        assertEquals(1, last!!.total)
    }

    @Test
    fun `status speaks like the React dialog`() {
        assertTrue(BookSearch.status("", null).startsWith("Gõ chữ hay câu cần tìm"))
        assertEquals("Gõ ít nhất 2 ký tự.", BookSearch.status("a", null))
        assertEquals("Không thấy “xyz” trong sách.", BookSearch.status("xyz", FindProgress(emptyList(), 0, 3, 3, 0, done = true)))
        assertEquals(
            "Đang tìm - đã xem 1/3 chương, thấy 0 chỗ.",
            BookSearch.status("xyz", FindProgress(emptyList(), 0, 1, 3, 0, done = false)),
        )
    }
}
