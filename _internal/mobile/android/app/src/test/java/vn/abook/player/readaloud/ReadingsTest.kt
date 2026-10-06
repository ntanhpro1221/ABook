package vn.abook.player.readaloud

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import vn.abook.player.BookEditsFixtures
import vn.abook.player.vieneu.VieneuUnits

/**
 * Cách đọc riêng của một cuốn chỉ có chữ ([Readings]): cùng bộ ví dụ với pytest (tests/fixtures/book_edits/readings/speech.json, sinh từ
 * abook/readaloud/readings.py) - cùng chữ hiện ra cùng chữ đem đọc và cùng khoá bộ đệm clip ở hai bên.
 */
class ReadingsTest {
    private fun table(json: JSONObject): Map<String, String> = json.keys().asSequence().associateWith { json.getString(it) }

    private fun strings(value: Any?): List<String>? =
        (value as? org.json.JSONArray)?.let { array -> (0 until array.length()).map { array.getString(it) } }

    @Test
    fun the_shared_speech_cases_give_what_python_gave() {
        val golden = BookEditsFixtures.obj("readings/speech.json")
        val readings = table(golden.getJSONObject("readings"))
        val cases = golden.getJSONArray("cases")
        assertTrue(cases.length() >= 8)
        for (index in 0 until cases.length()) {
            val case = cases.getJSONObject(index)
            val voice = case.getString("voice")
            val text = case.getString("text")
            val origin = case.opt("origin") as? String
            val tokens = WordTokens.tokens(text).map { text.substring(it.first, it.last + 1) }
            assertEquals("$text: chữ hiện", strings(case.get("tokens")), tokens)
            strings(case.opt("spokenTokens"))?.let { assertEquals("$text ($voice): chữ đem đọc", it, VieneuUnits.spokenTokens(tokens, origin, readings)) }
            (case.opt("spokenText") as? String)?.let {
                assertEquals("$text ($voice): chữ đem đọc", it, Readings.spokenText(text, readings))
                assertEquals("số chữ đem đọc = số chữ hiện", tokens.size, WordTokens.count(it))
            }
            assertEquals("$text: dấu cách đọc", case.getString("tag"), Readings.tag(text, readings))
            val (provider, native) = ClipCache.split(voice)
            assertEquals("$text ($voice, $origin): khoá clip", case.getString("key"),
                ClipCache.key(provider, native, text, ClipCache.reading(voice, text, origin, readings)))
        }
    }

    @Test
    fun only_whole_words_match_and_case_counts() {
        val table = mapOf("Haruto" to "Ha ru tô")
        assertEquals("“Ha-ru-tô!” haruto Harutoo Haruto-kun", Readings.spokenText("“Haruto!” haruto Harutoo Haruto-kun", table))
        assertEquals("", Readings.tag("haruto Harutoo", table))
        assertEquals("a\n  Ha-ru-tô\tb", Readings.spokenText("a\n  Haruto\tb", table))
        assertTrue(Readings.isWord("Haruto") && Readings.isWord("Haruto-kun"))
        assertFalse(Readings.isWord("Hai kes") || Readings.isWord("Haruto,") || Readings.isWord("") || Readings.isWord("Tôkyô"))
    }

    @Test
    fun a_paragraph_without_the_word_keeps_its_old_clip() {
        val text = "Trời mưa."
        assertEquals(ClipCache.key("edge", "vi-VN-HoaiMyNeural", text),
            ClipCache.key("edge", "vi-VN-HoaiMyNeural", text, ClipCache.reading("edge:vi-VN-HoaiMyNeural", text, null, mapOf("Haruto" to "Ha-ru-tô"))))
    }
}
