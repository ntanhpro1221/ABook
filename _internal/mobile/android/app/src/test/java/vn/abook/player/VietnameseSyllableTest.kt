package vn.abook.player

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test
import java.io.File
import java.text.Normalizer

/**
 * Bộ kiểm âm tiết tiếng Việt chặt (VietnameseSyllable.kt) trên bộ ví dụ DÙNG CHUNG với Python
 * (tests/fixtures/vietnamese_syllable/cases.json; test_vietnamese_syllable.py đọc cùng file): đúng phải qua, sai phải trượt, và mọi âm tiết
 * của lời Truyện Kiều (passage.txt, hết bản quyền) phải qua.
 */
class VietnameseSyllableTest {
    private val folder = File("../../../tests/fixtures/vietnamese_syllable").also {
        if (!it.isDirectory) fail("Không thấy bộ ví dụ dùng chung: ${it.absoluteFile}")
    }
    private val cases = JSONObject(File(folder, "cases.json").readText(Charsets.UTF_8))

    private fun list(key: String): List<String> = cases.getJSONArray(key).let { array: JSONArray -> (0 until array.length()).map { array.getString(it) } }

    @Test
    fun everySharedValidSyllablePasses() {
        val wrong = list("valid").filter { !VietnameseSyllable.validSyllable(it) }
        assertTrue("âm tiết đúng bị từ chối: $wrong", wrong.isEmpty())
    }

    @Test
    fun everySharedWrongSyllableFails() {
        val wrong = list("invalid").filter { VietnameseSyllable.validSyllable(it) }
        assertTrue("âm tiết sai được nhận: $wrong", wrong.isEmpty())
    }

    @Test
    fun spokenFormsFollowTheirPieces() {
        val rejected = list("spoken_valid").filter { !VietnameseSyllable.validSpokenForm(it) }
        assertTrue("cách đọc đúng bị từ chối: $rejected", rejected.isEmpty())
        val accepted = list("spoken_invalid").filter { VietnameseSyllable.validSpokenForm(it) }
        assertTrue("cách đọc sai được nhận: $accepted", accepted.isEmpty())
    }

    @Test
    fun everySyllableOfThePublicVietnameseTextPasses() {
        val text = Normalizer.normalize(File(folder, "passage.txt").readText(Charsets.UTF_8), Normalizer.Form.NFC)
        val words = Regex("[\\p{L}]+").findAll(text).map { it.value }.toList()
        assertTrue("văn bản quá ngắn", words.size > 150)
        val rejected = words.filter { !VietnameseSyllable.validSyllable(it) }.toSet()
        assertTrue("âm tiết Việt thật bị từ chối: $rejected", rejected.isEmpty())
    }

    @Test
    fun theFormsTheOldCheckLetThroughAreStopped() {
        for (wrong in listOf("Gen", "Mêch", "Got", "Ain", "Xớc")) {
            assertTrue("bộ cũ phải còn nhận $wrong", VietnameseReading.validSpokenForm("", wrong))
            assertFalse(wrong, VietnameseSyllable.validSpokenForm(wrong))
        }
        for (right in listOf("Ghen", "Mếch", "Gót", "Ai-nơ", "Xơ-cơ")) assertTrue(right, VietnameseSyllable.validSpokenForm(right))
    }

    @Test
    fun aToneSitsOnAVowelOnly() {
        assertFalse(VietnameseSyllable.validSyllable("mañ"))
        assertTrue(VietnameseSyllable.validSyllable("mãn"))
        assertTrue(VietnameseSyllable.validSyllable(Normalizer.normalize("nguyễn", Normalizer.Form.NFD)))
    }
}
