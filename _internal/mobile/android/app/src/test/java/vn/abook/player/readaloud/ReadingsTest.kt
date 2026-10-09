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
                val (said, slots) = Readings.spokenLayout(text, readings)
                assertEquals("$text ($voice): chữ đem đọc", it, said)
                assertEquals("$text ($voice): bảng chữ hiện -> chữ đem đọc", case.getJSONArray("spokenSlots").let { array -> (0 until array.length()).map { i -> if (array.isNull(i)) null else array.getInt(i) } }, slots)
                assertEquals("số chữ đem đọc = số chữ hiện còn lại", slots.count { slot -> slot != null }, WordTokens.count(it))
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

    @Test
    fun a_phrase_key_is_one_to_six_words_with_single_spaces() {
        assertTrue(Readings.isKey("Haruto") && Readings.isKey("Hạ Vy") && Readings.isKey("a b c d e f"))
        assertFalse(Readings.isKey("a b c d e f g") || Readings.isKey("Hạ  Vy") || Readings.isKey(" Hạ Vy") || Readings.isKey("Hạ Vy "))
        assertFalse(Readings.isKey("Hạ, Vy") || Readings.isKey("Hạ\tVy") || Readings.isKey("") || Readings.isKey("Tôkyô Vy"))
    }

    @Test
    fun a_phrase_matches_whole_words_without_punctuation_between() {
        val table = mapOf("Hạ Vy" to "Hà Vi", "Hạ" to "Há")
        assertEquals("“Hà Vi,” Há, Vy và hạ vy; Hà  Vi\nHà\nVi", Readings.spokenText("“Hạ Vy,” Hạ, Vy và hạ vy; Hạ  Vy\nHạ\nVy", table))
        assertEquals("Há Vy", Readings.spokenText("Hạ Vy", mapOf("Hạ" to "Há")))
        assertEquals("Hà Vi…", Readings.spokenText("Hạ Vy…", mapOf("Hạ Vy" to "Hà Vi")))
        assertEquals("Hạ —Vy", Readings.spokenText("Hạ —Vy", mapOf("Hạ Vy" to "Hà Vi")))
        assertEquals(listOf("Hạ Vy", "Hạ"), Readings.applicable("Hạ Vy gặp Hạ rồi Hạ Vy", table).map { it.first })
        assertTrue(Readings.tag("Hạ, Vy", table) != Readings.tag("Hạ Vy", table) && Readings.tag("hạ vy", table) == "")
    }

    @Test
    fun the_spoken_words_are_shared_out_over_the_shown_words() {
        fun said(text: String, key: String, value: String): List<String> {
            val toks = WordTokens.tokens(text).map { text.substring(it.first, it.last + 1) }
            val out = toks.toMutableList()
            Readings.applyTokens(toks, out, mapOf(key to value))
            return out
        }
        assertEquals(listOf("Hà", "Vi"), said("Hạ Vy", "Hạ Vy", "Hà Vi"))
        assertEquals(listOf("Hà-Vi", "Anh"), said("Hạ Vy", "Hạ Vy", "Hà Vi Anh"))
        assertEquals(listOf("x-y", "z", "t"), said("a b c", "a b c", "x y z t"))
        assertEquals(listOf("Hà", ""), said("Hạ Vy", "Hạ Vy", "Hà"))
        assertEquals(listOf("x", "", ""), said("a b c", "a b c", "x"))
        assertEquals(listOf("“Tứ,”", ""), said("“ông Tư,”", "ông Tư", "Tứ"))
    }

    @Test
    fun a_shown_word_with_nothing_to_say_leaves_the_text_and_keeps_its_timing_slot() {
        val (said, slots) = Readings.spokenLayout("Anh gọi ông Tư!\nVâng.", mapOf("ông Tư" to "Tứ"))
        assertEquals("Anh gọi Tứ!\nVâng.", said)
        assertEquals(listOf(0, 1, 2, null, 3), slots)
        val words = listOf(Span(0, 10), Span(10, 20), Span(20, 30), Span(30, 40))
        assertEquals(listOf(Span(0, 10), Span(10, 20), Span(20, 30), Span(30, 30), Span(30, 40)), Readings.expandWords(words, slots))
        assertEquals("Anh gọi ông Tư!" to listOf(0, 1, 2, 3), Readings.spokenLayout("Anh gọi ông Tư!", null))
    }
}
