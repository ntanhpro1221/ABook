package vn.abook.player.ui.data

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** Gói sách + trạng thái nghe (JSON thật của lõi) -> [ListenBook] và lệnh nạp [PlayPlan]. org.json thật chạy trên JVM. */
class BookJsonTest {
    private val audio = JSONObject(
        """
        {"id":"b1","title":"Tắt đèn","author":"Ngô Tất Tố","narrator":"Đức Trí","complete":true,"chaptersTotal":2,
         "series":{"root":"b0","part":2},
         "chapters":[
           {"id":1,"fullTitle":"Chương 1","file":"audio/1.mp3","available":true,"duration":600.0},
           {"id":2,"fullTitle":"Chương 2","file":"audio/2.mp3","available":true,"duration":300.0}]}
        """.trimIndent(),
    )

    private val heard = JSONObject(
        """
        {"last":{"chapterId":1,"seconds":120.0,"at":1700000000.0,"rev":{"counter":3,"node":"n","epoch":"e"}},
         "chapters":{"1":{"heard":120.0,"done":false},"2":{"heard":0.0,"done":false,"duration":300.0}},
         "rate":1.5,"finished":false,"updatedAt":1700000001.0}
        """.trimIndent(),
    )

    @Test
    fun `state reads the listening record`() {
        val state = BookJson.state(heard)
        assertEquals(Last(1, 120.0, 1700000000.0, Rev(3, "n", "e")), state.last)
        assertEquals(ChapterRecord(120.0, false, null), state.chapters[1])
        assertEquals(300.0, state.chapters[2]?.duration)
        assertEquals(1.5, state.rate)
        assertFalse(state.finished)
        assertEquals(1700000001.0, state.updatedAt)
    }

    @Test
    fun `state of nothing or of an empty record is empty`() {
        assertNull(BookJson.state(null).last)
        val empty = BookJson.state(JSONObject("{}"))
        assertNull(empty.last)
        assertTrue(empty.chapters.isEmpty())
        assertNull(empty.rate)
    }

    @Test
    fun `finished carries its own revision and a revision without a node is dropped`() {
        val state = BookJson.state(JSONObject("""{"finished":true,"finishedAt":5.0,"_fieldRevs":{"finished":{"counter":2,"node":"m"}},"last":{"chapterId":1,"seconds":1,"at":2,"rev":{"counter":0,"node":""}}}"""))
        assertTrue(state.finished)
        assertEquals(Rev(2, "m", null), state.finishedRev)
        assertNull(state.last?.rev)
    }

    @Test
    fun `an audio book carries progress resume series and cover`() {
        val book = BookJson.book(audio, heard, { CoverRef("/c/b1.jpg", 7) }, addedAt = 99.0)
        assertEquals("b1", book.id)
        assertEquals("Tắt đèn", book.title)
        assertEquals("Ngô Tất Tố", book.author)
        assertEquals("Đức Trí", book.narrator)
        assertEquals(900.0, book.duration, 0.0)
        assertEquals(2, book.chaptersAvailable)
        assertEquals(2, book.chaptersTotal)
        assertFalse(book.textOnly)
        assertEquals(120.0, book.progress.heardSeconds, 1e-9)
        assertEquals(120f / 900f, book.progress.fraction, 1e-6f)
        assertEquals(ResumeSpot(1, "Chương 1", 120.0), book.resume)
        assertEquals("Chương 1", book.lastChapterTitle)
        assertEquals(SeriesLink("b0", 2), book.series)
        assertEquals(2, book.part)
        assertEquals(CoverRef("/c/b1.jpg", 7), book.cover)
        assertEquals(99.0, book.addedAt)
        assertNull(book.remote)
    }

    @Test
    fun `null authors and a missing record give a clean new book`() {
        val manifest = JSONObject(audio.toString()).put("author", JSONObject.NULL).put("narrator", JSONObject.NULL)
        manifest.remove("series")
        val book = BookJson.book(manifest, null, { null })
        assertEquals("", book.author)
        assertEquals("", book.narrator)
        assertNull(book.series)
        assertNull(book.cover)
        assertEquals(0.0, book.progress.heardSeconds, 0.0)
        assertEquals(ResumeSpot(1, "Chương 1", 0.0), book.resume)
    }

    @Test
    fun `a book of text chapters only is read aloud and counted by chapter`() {
        val text = JSONObject(
            """{"id":"t1","title":"Chí Phèo","chaptersTotal":2,"chapters":[
               {"id":1,"fullTitle":"Một","state":"text","text":"texts/1.txt"},
               {"id":2,"fullTitle":"Hai","state":"text"}]}""",
        )
        val state = JSONObject("""{"chapters":{"1":{"heard":10.0,"done":true}},"last":{"chapterId":1,"seconds":10.0,"at":3.0}}""")
        val book = BookJson.book(text, state, { null })
        assertTrue(book.textOnly)
        assertEquals(0, book.chaptersAvailable)
        assertEquals(0.5f, book.progress.fraction, 1e-6f)
        assertEquals(1, book.progress.chaptersDone)
        // Chương chữ chưa có độ dài đã biết: chưa thể nói "gần hết", nên nghe tiếp đúng chỗ đã dừng.
        assertEquals(ResumeSpot(1, "Một", 10.0), book.resume)
    }

    @Test
    fun `a book still being made keeps its chapters made so far`() {
        val partial = JSONObject(audio.toString()).put("complete", false).put("chaptersTotal", 9)
        val book = BookJson.book(partial, null, { null })
        assertFalse(book.complete)
        assertEquals(9, book.chaptersTotal)
        assertEquals("2/9 chương", ListenLogic.progressText(book))
    }

    @Test
    fun `chapters of the manifest tell audio from text`() {
        val mixed = JSONObject(
            """{"id":"m","chapters":[
               {"id":1,"fullTitle":"A","file":"a.mp3","available":true,"duration":10.0},
               {"id":2,"fullTitle":"B","state":"text","text":"t.txt"},
               {"id":3,"fullTitle":"C","available":false}]}""",
        )
        val chapters = BookJson.chapters(mixed)
        assertEquals(listOf(1, 2), chapters.map { it.id })
        assertTrue(chapters[0].available)
        assertTrue(chapters[1].textOnly)
    }

    @Test
    fun `play plan resumes the chapter and second the listener left at and keeps the rate`() {
        val plan = PlayPlan.of(audio, heard)!!
        assertEquals("b1", plan.id)
        assertEquals("Tắt đèn", plan.title)
        assertEquals("Đức Trí", plan.narrator)
        assertEquals(2, plan.chapters.size)
        assertEquals(1, plan.startChapterId)
        assertEquals(120.0, plan.startSeconds, 0.0)
        assertEquals(1.5, plan.rate, 0.0)
    }

    @Test
    fun `play plan of an unheard book starts at the first chapter at normal rate`() {
        val plan = PlayPlan.of(audio, null)!!
        assertEquals(1, plan.startChapterId)
        assertEquals(0.0, plan.startSeconds, 0.0)
        assertEquals(1.0, plan.rate, 0.0)
    }

    @Test
    fun `play plan moves on when the chapter was nearly done`() {
        val near = JSONObject("""{"last":{"chapterId":1,"seconds":595.0,"at":1.0}}""")
        assertEquals(2, PlayPlan.of(audio, near)!!.startChapterId)
    }

    @Test
    fun `play plan of a book with nothing to play is null`() {
        assertNull(PlayPlan.of(JSONObject("""{"id":"x","chapters":[{"id":1,"fullTitle":"A","available":false}]}"""), null))
        assertNull(PlayPlan.of(JSONObject("""{"id":"x"}"""), null))
    }
}
