package vn.abook.player.readaloud

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test
import java.io.File

/**
 * Luật đọc romaji Nhật / RR Hàn (Romanization.kt) trên bộ ví dụ DÙNG CHUNG với Python (tests/fixtures/romanization/cases.json,
 * sinh bằng scripts/build_romanization_fixture.py; test_romanization.py đọc cùng file): mỗi ca cùng cách đọc và cùng cờ.
 */
class RomanizationTest {
    private val file: File = File("../../../tests/fixtures/romanization/cases.json").also {
        if (!it.isFile) fail("Không thấy bộ ví dụ dùng chung: ${it.absoluteFile}")
    }

    private fun cases() = JSONObject(file.readText(Charsets.UTF_8)).getJSONArray("cases").let { array ->
        (0 until array.length()).map { array.getJSONObject(it) }
    }

    @Test
    fun everySharedCaseReadsTheSameAsPython() {
        val all = cases()
        assertTrue("thiếu ví dụ", all.size > 300)
        val wrong = ArrayList<String>()
        for (case in all) {
            val origin = if (case.isNull("origin")) null else case.getString("origin")
            val want = if (case.isNull("reading")) null else case.getString("reading")
            val wantFlags = case.getJSONArray("flags").let { f -> (0 until f.length()).map { f.getString(it) } }
            val got = Romanization.readingWithFlags(case.getString("token"), origin)
            if (got?.text != want || (got?.flags ?: emptyList<String>()) != wantFlags) {
                wrong.add("${case.getString("group")} ${case.getString("token")} ($origin): Kotlin ${got?.text} ${got?.flags}, Python $want $wantFlags")
            }
        }
        assertTrue("${wrong.size} ca lệch:\n" + wrong.take(15).joinToString("\n"), wrong.isEmpty())
    }

    @Test
    fun theConventionsHoldOnSmallCases() {
        assertEquals("Xáp-pô-rô", Romanization.reading("Sapporo", "ja"))
        assertEquals("Hốc-cai-đô", Romanization.reading("Hokkaido", "ja"))
        assertEquals("Kiu-xiu", Romanization.reading("Kyuushuu", "ja"))
        assertEquals("Xu-ba-ru-cun", Romanization.reading("Subaru-kun", "ja"))
        assertEquals("Ha-ru-tô-cun", Romanization.reading("Haruto-kun", "ja"))
        assertEquals("Phu-cu-si-ma", Romanization.reading("Fukushima", "ja"))
        assertEquals("Xa-tô-xen-xay", Romanization.reading("Sato-sensei", "ja"))
        assertEquals("Pắc Cưn Hê", Romanization.reading("Park Geun-hye", "ko"))
        assertEquals("Li Miêng Bắc", Romanization.reading("Lee Myung-bak", "ko"))
        assertEquals("Sơ-un", Romanization.reading("Seoul", "ko"))
    }

    @Test
    fun whatItIsNotSureOfItDoesNotRead() {
        assertNull(Romanization.reading("Cale", "ja"))
        assertNull(Romanization.reading("IZUMO", "ja"))
        assertNull(Romanization.reading("Yongin", "ko"))
        assertNull(Romanization.reading("Hajime", null))
    }

    @Test
    fun openChoicesAreFlagged() {
        assertEquals(listOf("open:y_initial"), Romanization.readingWithFlags("Yamato", "ja")?.flags)
        assertEquals(setOf("y_initial", "ko_aspirated", "ko_rare_vowels"), Romanization.OPEN_CHOICES.keys)
    }
}
