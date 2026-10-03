package vn.abook.player.readaloud

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test
import java.io.File

/**
 * Luật Việt hoá từ tiếng Anh (EnglishVi.kt) trên bộ ví dụ DÙNG CHUNG với Python (tests/fixtures/english_vi/cases.json, sinh bằng
 * scripts/build_english_vi_fixture.py; test_english_vi.py đọc cùng file): mỗi ca cùng cách đọc và cùng cờ, có và không có từ điển phát âm.
 */
class EnglishViTest {
    private val file: File = File("../../../tests/fixtures/english_vi/cases.json").also {
        if (!it.isFile) fail("Không thấy bộ ví dụ dùng chung: ${it.absoluteFile}")
    }
    private val phones: Map<String, String> by lazy {
        val dictionary = File("../../../abook/assets/english_phones.txt.gz")
        if (!dictionary.isFile) fail("Không thấy từ điển phát âm gọn: ${dictionary.absoluteFile}")
        EnglishVi.loadPhones(dictionary)
    }

    private fun cases() = JSONObject(file.readText(Charsets.UTF_8)).getJSONArray("cases").let { array ->
        (0 until array.length()).map { array.getJSONObject(it) }
    }

    private fun strings(case: JSONObject, key: String) = case.getJSONArray(key).let { f -> (0 until f.length()).map { f.getString(it) } }

    @Test
    fun everySharedCaseReadsTheSameAsPython() {
        val all = cases()
        assertTrue("thiếu ví dụ", all.size > 450)
        val wrong = ArrayList<String>()
        for (case in all) {
            val token = case.getString("token")
            val runs = mutableListOf(Triple(phones, true, "reading" to "flags"), Triple(emptyMap<String, String>(), true, "reading_nodict" to "flags_nodict"))
            if (case.has("rule")) runs.add(Triple(phones, false, "rule" to "rule_flags"))
            for ((dictionary, overrides, keys) in runs) {
                val want = if (case.isNull(keys.first)) null else case.getString(keys.first)
                val wantFlags = strings(case, keys.second)
                val got = EnglishVi.readingWithFlags(token, dictionary, overrides)
                if (got?.text != want || (got?.flags ?: emptyList<String>()) != wantFlags) {
                    wrong.add("${case.getString("group")} $token [${keys.first}]: Kotlin ${got?.text} ${got?.flags}, Python $want $wantFlags")
                }
            }
        }
        assertTrue("${wrong.size} ca lệch:\n" + wrong.take(15).joinToString("\n"), wrong.isEmpty())
    }

    @Test
    fun theOwnerRulingsHold() {
        assertEquals("ghêm", EnglishVi.reading("game", phones))
        assertEquals("le-vồ", EnglishVi.reading("level", phones))
        assertEquals("máp-pồ", EnglishVi.reading("maple", phones))
        assertEquals("Mai-cồ", EnglishVi.reading("Michael", phones))
        assertEquals("Ca-tê", EnglishVi.reading("Kate", phones))
        assertEquals("Mi-ke", EnglishVi.reading("Mike", phones, overrides = false))
        assertEquals("xờ-kiu", EnglishVi.reading("skill", phones, overrides = false))
        assertEquals("bót", EnglishVi.reading("boss", phones, overrides = false))
        assertEquals("víp", EnglishVi.reading("VIP", phones))
        assertEquals("Oa-sinh-tơn", EnglishVi.reading("Washington", phones))
    }

    @Test
    fun withoutADictionaryTheSpellingRouteReads() {
        assertEquals(EnglishVi.Reading("Oa-sinh-tôn", listOf("via:spelling")), EnglishVi.readingWithFlags("Washington", emptyMap()))
        assertEquals("En-cơ-rít", EnglishVi.reading("Encrid", emptyMap()))
    }

    @Test
    fun whatItIsNotSureOfItDoesNotRead() {
        assertNull(EnglishVi.reading("MARY", phones))
        assertNull(EnglishVi.reading("iPhone", phones))
        assertNull(EnglishVi.reading("O'Brien", phones))
        assertNull(EnglishVi.reading("", phones))
        assertEquals(setOf("short_silent_e", "er_final", "epenthesis"), EnglishVi.OPEN_CHOICES.keys)
    }
}
