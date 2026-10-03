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
        assertEquals("Ki-u-su", Romanization.reading("Kyuushuu", "ja"))
        assertEquals("Xu-ba-xa", Romanization.reading("Tsubasa", "ja"))
        assertEquals("Hi-ra-ghi", Romanization.reading("Hiiragi", "ja"))
        assertEquals("O-ne-xan", Romanization.reading("Onee-san", "ja"))
        assertEquals("O-xa-ca", Romanization.reading("Osaka", "ja"))
        assertEquals("A-o-i", Romanization.reading("Aoi", "ja"))
        assertEquals("Nao", Romanization.reading("Nao", "ja"))
        assertEquals("O-ni-gi-ri", Romanization.reading("Onigiri", "ja"))
        assertEquals("Xu-ba-ru-cun", Romanization.reading("Subaru-kun", "ja"))
        assertEquals("Ha-ru-tô-cun", Romanization.reading("Haruto-kun", "ja"))
        assertEquals("Phu-cu-si-ma", Romanization.reading("Fukushima", "ja"))
        assertEquals("Xa-tô-xen-xây", Romanization.reading("Sato-sensei", "ja"))
        assertEquals("Gia-ma-tô", Romanization.reading("Yamato", "ja"))
        assertEquals("Ha-gi-me", Romanization.reading("Hajime", "ja"))
        assertEquals("Rây", Romanization.reading("Rei", "ja"))
        assertEquals("Pắc Cưn Hê", Romanization.reading("Park Geun-hye", "ko"))
        assertEquals("Li Mi-e-ong Bắc", Romanization.reading("Lee Myung-bak", "ko"))
        assertEquals("Xeo-un", Romanization.reading("Seoul", "ko"))
        assertEquals("Cang", Romanization.reading("Kang", "ko"))
        assertEquals("Gie-ong", Romanization.reading("Jeong", "ko"))
        assertEquals("Guôn", Romanization.reading("Won", "ko"))
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
        assertEquals(emptyList<String>(), Romanization.readingWithFlags("Yamato", "ja")?.flags) // ya Nhật đã chốt gi (chủ sách 04-10)
        assertEquals(listOf("analogy:y_gi"), Romanization.readingWithFlags("Yuki", "ja")?.flags)
        assertEquals(listOf("analogy:ao_split"), Romanization.readingWithFlags("Naoki", "ja")?.flags)
        assertEquals(listOf("analogy:ko_w_gu"), Romanization.readingWithFlags("Suwon", "ko")?.flags)
        assertEquals(emptyList<String>(), Romanization.readingWithFlags("Kwon", "ko")?.flags)
        assertEquals(setOf("ko_rare_vowels"), Romanization.OPEN_CHOICES.keys)
    }
}
