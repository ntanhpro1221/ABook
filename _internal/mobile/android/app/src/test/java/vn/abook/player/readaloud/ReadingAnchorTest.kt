package vn.abook.player.readaloud

import org.json.JSONObject
import java.io.File
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import vn.abook.player.BookEditsFixtures

class ReadingAnchorTest {
    @Test
    fun text_anchor_survives_a_new_timeline_and_rejects_changed_text() {
        val paragraphs = listOf("Chương một", "😀 Một hai ba.", "Đoạn sau.")
        val type = Class.forName("vn.abook.player.readaloud.ReadingAnchor")
        val instance = type.getField("INSTANCE").get(null)
        val make = type.getDeclaredMethod("make", List::class.java, Int::class.javaPrimitiveType, Int::class.javaPrimitiveType)
        val restore = type.getDeclaredMethod("restore", List::class.java, JSONObject::class.java)
        val anchor = make.invoke(instance, paragraphs, 1, 2) as JSONObject
        assertEquals("fnv1a64:bb657205cfbee8a0", anchor.getString("textHash"))
        assertEquals(6, anchor.getInt("charOffset")) // code points: emoji chiếm một ký tự
        assertEquals(1 to 2, restore.invoke(instance, paragraphs, anchor))
        assertNull(restore.invoke(instance, listOf("Chương một", "😀 Một hai bốn.", "Đoạn sau."), anchor)) // chính đoạn đang nghe đã đổi
        assertEquals(1 to 2, restore.invoke(instance, paragraphs + "Nội dung mới", anchor)) // đổi ở đoạn khác thì giữ chỗ (soát a79 lỗi 5)
        assertNull(restore.invoke(instance, paragraphs, JSONObject(anchor.toString()).put("segment", 99)))
    }

    private fun strings(array: org.json.JSONArray) = (0 until array.length()).map { array.getString(it) }

    /** Bộ ví dụ dùng chung với listen/readingAnchor.test.ts và tests/test_reading_anchor.py (tests/fixtures/reading_anchor/restore.json). */
    private val fixture: JSONObject by lazy {
        JSONObject(File(BookEditsFixtures.dir.parentFile, "reading_anchor/restore.json").readText(Charsets.UTF_8))
    }

    @Test
    fun the_anchor_made_here_matches_the_shared_fixture_byte_for_byte() {
        val shared = fixture.getJSONObject("anchor")
        val made = ReadingAnchor.make(strings(shared.getJSONArray("paragraphs")), shared.getInt("segment"), shared.getInt("word"))!!
        val expect = shared.getJSONObject("expect")
        for (key in listOf("segment", "charOffset", "textHash", "paragraphHash")) assertEquals(key, expect.get(key), made.get(key))
        val kept = ReadingAnchor.validated(expect)!!
        for (key in listOf("segment", "charOffset", "textHash", "paragraphHash")) assertEquals("validated giữ $key", expect.get(key), kept.get(key))
    }

    @Test
    fun restoring_after_the_book_changed_follows_the_shared_cases() {
        val cases = fixture.getJSONArray("cases")
        for (i in 0 until cases.length()) {
            val item = cases.getJSONObject(i)
            val anchor = ReadingAnchor.make(strings(item.getJSONArray("before")), item.getInt("segment"), item.getInt("word"))!!
            val restored = ReadingAnchor.restore(strings(item.getJSONArray("after")), anchor)
            val expect = item.opt("expect") as? JSONObject
            assertEquals(item.getString("name"), expect?.let { it.getInt("segment") to it.getInt("word") }, restored)
        }
    }

    @Test
    fun an_anchor_with_a_malformed_paragraph_hash_is_dropped_and_an_old_one_still_validates() {
        val anchor = ReadingAnchor.make(listOf("một", "hai ba"), 1, 1)!!
        assertEquals(anchor.getString("paragraphHash"), ReadingAnchor.validated(anchor)!!.getString("paragraphHash"))
        assertNull(ReadingAnchor.validated(JSONObject(anchor.toString()).put("paragraphHash", "changed")))
        val old = JSONObject(anchor.toString()).also { it.remove("paragraphHash") }
        assertEquals(1 to 1, ReadingAnchor.restore(listOf("một", "hai ba"), old))
        assertNull(ReadingAnchor.restore(listOf("một", "hai ba", "bốn"), old))
    }
}
