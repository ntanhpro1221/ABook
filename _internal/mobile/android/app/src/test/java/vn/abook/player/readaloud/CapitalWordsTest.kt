package vn.abook.player.readaloud

import java.io.File
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import vn.abook.player.vieneu.VieneuUnits

/** Tên / từ bị hét viết HOA cả ("YUI!", "KAEL!") đọc như chính từ ấy, viết tắt thật vẫn đánh vần. Bộ ví dụ chung với `tests/test_readaloud_capitals.py`. */
class CapitalWordsTest {
    private val cases = JSONObject(File("../../../tests/fixtures/readaloud/capitals/cases.json").readText(Charsets.UTF_8))

    @Test fun sharedCapitalWords() {
        val spoken = cases.getJSONArray("spoken")
        assertTrue(spoken.length() >= 30)
        for (i in 0 until spoken.length()) {
            val c = spoken.getJSONObject(i)
            val origin = if (c.isNull("origin")) null else c.getString("origin")
            val readings = c.optJSONObject("readings")?.let { o -> o.keys().asSequence().associateWith { o.getString(it) } }
            assertEquals("${c.getString("text")} | $origin | $readings", c.getString("said"),
                VieneuUnits.spokenTokens(c.getString("text").split(" "), origin, readings = readings, directEnglish = true).joinToString(" "))
        }
    }

    @Test fun sharedCapitalNamesOfABook() {
        val books = cases.getJSONArray("books")
        for (i in 0 until books.length()) {
            val c = books.getJSONObject(i)
            val origin = if (c.isNull("origin")) null else c.getString("origin")
            val texts = c.getJSONArray("texts").let { a -> (0 until a.length()).map { a.getString(it) } }
            val characters = c.getJSONArray("characters").let { a -> (0 until a.length()).map { a.getString(it) } }
            val readings = c.getJSONObject("readings").let { o -> o.keys().asSequence().associateWith { o.getString(it) } }
            assertEquals(c.getString("note"), readings, JapanesePolicy.bookNameReadings(texts.asSequence(), characters, origin))
        }
    }

    @Test fun onlyTheCapitalizedSpellingIsProof() {
        assertTrue(Abbreviations.provesName("KAEL", "Kael"))
        assertFalse(Abbreviations.provesName("KAEL", "Ca-en"))
        assertFalse(Abbreviations.provesName("Kael", "Kael"))
        assertNull(Abbreviations.capitalWords(listOf("Rồi", "đến."), "ja", null))
    }
}
