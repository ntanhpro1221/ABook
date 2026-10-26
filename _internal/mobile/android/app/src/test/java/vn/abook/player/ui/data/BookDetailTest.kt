package vn.abook.player.ui.data

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** Trang sách: hàng chương từ gói sách + chỗ nghe, và chữ của trang (labels.ts `primaryListenLabel`, BookScreen.tsx). */
class BookDetailTest {
    private fun manifest(vararg chapters: JSONObject, complete: Boolean = true) = JSONObject()
        .put("id", "b1").put("title", "Truyện · Tập 3").put("author", "Tác giả").put("narrator", "Hoài My")
        .put("complete", complete).put("chaptersTotal", chapters.size).put("chapters", JSONArray(chapters.toList()))

    private fun audio(id: Int, duration: Double = 600.0) =
        JSONObject().put("id", id).put("fullTitle", "Chương $id").put("file", "audio/$id.m4a").put("available", true).put("duration", duration)

    private fun state(vararg chapters: Pair<Int, JSONObject>, last: JSONObject? = null) = JSONObject().apply {
        put("chapters", JSONObject().apply { for ((id, record) in chapters) put(id.toString(), record) })
        if (last != null) put("last", last)
    }

    @Test
    fun `every chapter of the package becomes a row, including chapters without audio`() {
        val missing = JSONObject().put("id", 3).put("fullTitle", "Chương 3").put("available", false)
        val text = JSONObject().put("id", 4).put("fullTitle", "Chương 4").put("state", "text")
        val detail = BookDetail.of(manifest(audio(1), audio(2), missing, text), null, { null })
        assertEquals(listOf(1, 2, 3, 4), detail.chapters.map { it.id })
        assertTrue(detail.chapters[0].playable)
        assertFalse(detail.chapters[2].playable)
        assertTrue(detail.chapters[3].textOnly)
        assertEquals("texts/4.txt", detail.chapters[3].textPath)
        assertEquals(0.0, detail.chapters[3].duration, 0.0)
    }

    @Test
    fun `heard fraction, done and the seconds a tap resumes at`() {
        val st = state(
            1 to JSONObject().put("heard", 600.0).put("done", true),
            2 to JSONObject().put("heard", 150.0).put("done", false),
        )
        val rows = BookDetail.of(manifest(audio(1), audio(2), audio(3)), st, { null }).chapters
        assertTrue(rows[0].done)
        assertEquals(0.0, rows[0].resumeAt, 0.0)
        assertEquals(0.25f, rows[1].heard, 0.001f)
        assertEquals(150.0, rows[1].resumeAt, 0.0)
        assertEquals(0f, rows[2].heard, 0f)
    }

    @Test
    fun `primary label follows the React rules`() {
        val spot = ResumeSpot(4, "Chương 4", 120.0)
        assertEquals("Tạm dừng", BookPage.primaryLabel(playingHere = true, finished = false, resume = spot, heardSeconds = 10.0))
        assertEquals("Nghe lại từ đầu", BookPage.primaryLabel(false, finished = true, resume = spot, heardSeconds = 10.0))
        assertEquals("Nghe tiếp · Chương 4", BookPage.primaryLabel(false, false, spot, 10.0))
        assertEquals("Nghe", BookPage.primaryLabel(false, false, ResumeSpot(1, "Chương 1", 0.0), 0.0))
        assertEquals("Nghe tiếp", BookPage.primaryLabel(false, false, null, 30.0))
    }

    @Test
    fun `meta, status and progress lines`() {
        val book = BookDetail.of(manifest(audio(1), audio(2), complete = false).put("chaptersTotal", 5), null, { null }).book
        assertEquals("Tác giả · Giọng Hoài My · 2/5 chương có audio · 20 phút", BookPage.metaLine(book))
        assertEquals("Sách này có 2/5 chương đã thu - các chương sau chưa có audio", BookPage.statusLine(book))
        assertEquals("Chưa nghe · 20 phút", BookPage.progressLine(book))
        val heard = BookDetail.of(manifest(audio(1), audio(2)), state(1 to JSONObject().put("heard", 600.0).put("done", true)), { null }).book
        assertNull(BookPage.statusLine(heard))
        assertEquals("Đã nghe 10 phút · còn 10 phút chưa nghe", BookPage.progressLine(heard))
    }

    @Test
    fun `chapter line shows the length and the share heard`() {
        fun row(heard: Float, done: Boolean = false, playable: Boolean = true) =
            ChapterLine(1, "Chương 1", if (playable) 1500.0 else 0.0, available = playable, textOnly = false, heard = heard, done = done)
        assertEquals("25 phút", BookPage.chapterLine(row(0f)))
        assertEquals("25 phút · đã nghe 40%", BookPage.chapterLine(row(0.4f)))
        assertEquals("25 phút · đã nghe 1%", BookPage.chapterLine(row(0.001f)))
        assertEquals("25 phút · đã nghe 99%", BookPage.chapterLine(row(0.999f)))
        assertEquals("25 phút · đã nghe hết", BookPage.chapterLine(row(1f, done = true)))
        assertEquals("Chưa có audio", BookPage.chapterLine(row(0f, playable = false)))
    }

    @Test
    fun `current chapter is the player's when it holds this book`() {
        val book = BookDetail.of(manifest(audio(1), audio(2)), state(last = JSONObject().put("chapterId", 2).put("seconds", 30.0).put("at", 1.0)), { null }).book
        assertEquals(2, BookPage.currentChapter(book, PlayerState.Empty))
        assertEquals(1, BookPage.currentChapter(book, PlayerState(bookId = "b1", chapterId = 1)))
        assertEquals(2, BookPage.currentChapter(book, PlayerState(bookId = "khác", chapterId = 1)))
    }

    @Test
    fun `a tapped chapter loads the book starting there at the book's speed`() {
        val st = JSONObject().put("rate", 1.5)
        val request = PlayPlan.at(manifest(audio(1), audio(2)), st, chapterId = 2, seconds = 42.0)!!
        assertEquals(2, request.startChapterId)
        assertEquals(42.0, request.startSeconds, 0.0)
        assertEquals(1.5, request.rate, 0.0)
        assertEquals(2, request.chapters.size)
        // Chương không nghe được (không có trong hàng của trình phát): không nạp gì.
        assertNull(PlayPlan.at(manifest(audio(1)), st, chapterId = 9, seconds = 0.0))
        assertEquals(0.0, PlayPlan.at(manifest(audio(1)), null, chapterId = 1, seconds = -3.0)!!.startSeconds, 0.0)
    }
}
