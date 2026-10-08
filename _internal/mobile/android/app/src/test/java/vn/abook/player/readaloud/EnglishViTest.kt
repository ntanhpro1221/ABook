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
        assertEquals("Kết", EnglishVi.reading("Kate", phones))
        assertEquals("Mi-ke", EnglishVi.reading("Mike", phones, overrides = false))
        assertEquals("xờ-kiu", EnglishVi.reading("skill", phones, overrides = false))
        assertEquals("bót", EnglishVi.reading("boss", phones, overrides = false))
        assertEquals("víp", EnglishVi.reading("VIP", phones))
        assertEquals("Oa-xinh-tơn", EnglishVi.reading("Washington", phones))
        assertEquals("Goa-sinh-tơn", EnglishVi.reading("Washington", phones, overrides = false))
        assertEquals("guốt-tờ", EnglishVi.reading("water", phones, overrides = false))
        assertEquals("Guy-li-am", EnglishVi.reading("William", phones))
        assertEquals("Guyu", EnglishVi.reading("Will", phones, overrides = false))
        assertEquals("nây-sừn", EnglishVi.reading("nation", phones, overrides = false))
        assertEquals("Ét-pa-nha", EnglishVi.reading("España", emptyMap()))
        assertEquals("Xờ-cót-lừn", EnglishVi.reading("Scotland", phones, overrides = false))
        assertEquals("Pau", EnglishVi.reading("Paul", phones, overrides = false))
        assertEquals("Cấc", EnglishVi.reading("Kirk", phones, overrides = false))
        assertEquals("Gióc", EnglishVi.reading("George", phones, overrides = false))
        assertEquals("Ô-tin", EnglishVi.reading("Austin", phones, overrides = false))
        assertEquals("Rô-lừn", EnglishVi.reading("Roland", phones, overrides = false))
        assertEquals("cốp-ra", EnglishVi.reading("cobra", phones, overrides = false))
        assertEquals("beo", EnglishVi.reading("bell", phones, overrides = false))
        assertEquals("pha-dờ", EnglishVi.reading("father", phones, overrides = false))
        assertEquals("tắc-xi", EnglishVi.reading("taxi", phones))
        assertEquals("La-pờ-lây", EnglishVi.reading("Laplace", phones, overrides = false))
        assertEquals("Ca-ghe", EnglishVi.reading("Cage", phones, overrides = false))
        assertEquals("Đên", EnglishVi.reading("Dane", phones))
        assertEquals("Bờ-lếch", EnglishVi.reading("Blake", phones, overrides = false))
        assertEquals("Lai-ồ", EnglishVi.reading("Lyle", phones, overrides = false))
        assertEquals("tanh", EnglishVi.reading("tank", emptyMap(), overrides = false))
        assertEquals(EnglishVi.Reading("ranh", listOf("via:phonemes", "analogy:ank")), EnglishVi.readingWithFlags("rank", phones))
    }

    @Test
    fun theBenchRoundTenRulesHold() {
        // vòng 10 (bộ đo translit_bench); cùng ca với test_english_vi.py::test_reading_follows_the_convention
        val cases = mapOf(
            "Docora" to "Đo-co-ra", "Symphonia" to "Xim-phô-ni-a", "Jaxon" to "Giác-xơn", "Anton" to "An-tơn", "Astroa" to "Át-trô-a",
            "Lich" to "Lích", "March" to "Mách", "Axel" to "Ác-xồ", "Flag" to "Phờ-lác", "Rebecca" to "Re-béc-ca", "text" to "tếch",
            "Party" to "Pa-ti", "Arthur" to "A-thơ", "Silver" to "Xin-vờ", "Beatrice" to "Bi-a-trít", "Greyrat" to "Gờ-rây-rát",
            "Fire" to "Phai", "Note" to "Nốt", "video" to "vi-đê-ô", "café" to "cà-phê", "OK" to "ô-kê", "TV" to "ti-vi", "Lyle-kun" to "Lai-ồ cun",
        )
        for ((token, want) in cases) assertEquals(token, want, EnglishVi.reading(token, phones))
    }

    @Test
    fun withoutADictionaryTheSpellingRouteReads() {
        assertEquals(EnglishVi.Reading("Goa-sinh-tơn", listOf("via:spelling")), EnglishVi.readingWithFlags("Washington", emptyMap(), overrides = false))
        assertEquals("En-cờ-rít", EnglishVi.reading("Encrid", emptyMap()))
    }

    @Test
    fun whatItIsNotSureOfItDoesNotRead() {
        assertNull(EnglishVi.reading("NPC", phones))
        assertEquals("Ma-ri", EnglishVi.reading("MARY", phones)) // TOÀN HOA từ 4 chữ có trong từ điển đọc như tên (vòng 11); người gọi vẫn bỏ qua chữ TOÀN HOA
        assertNull(EnglishVi.reading("iPhone", phones))
        assertNull(EnglishVi.reading("O'Brien", phones))
        assertNull(EnglishVi.reading("", phones))
        assertTrue(EnglishVi.OPEN_CHOICES.isEmpty())
    }
}
