package vn.abook.player

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test
import java.io.File

/**
 * Lớp chữ hoa / chữ thường (VietnameseLetters.kt) trên danh sách DÙNG CHUNG với Python (tests/fixtures/vietnamese_letters/letters.json;
 * test_vietnamese_letters.py đọc cùng file): hai bên phải là cùng một danh sách ký tự, và mỗi lớp chỉ nhận đúng cỡ chữ của nó.
 */
class VietnameseLettersTest {
    private val shared = File("../../../tests/fixtures/vietnamese_letters/letters.json").let {
        if (!it.isFile) fail("Không thấy danh sách dùng chung: ${it.absoluteFile}")
        JSONObject(it.readText(Charsets.UTF_8))
    }

    @Test
    fun theLettersMatchTheListSharedWithPython() {
        assertEquals(shared.getString("upper"), VietnameseLetters.UPPER)
        assertEquals(shared.getString("lower"), VietnameseLetters.LOWER)
    }

    @Test
    fun eachClassHoldsEveryLetterOfItsCaseAndNoneOfTheOther() {
        val upper = Regex(VietnameseLetters.UPPER_CLASS)
        val lower = Regex(VietnameseLetters.LOWER_CLASS)
        assertEquals(VietnameseLetters.UPPER.length, VietnameseLetters.LOWER.length)
        for ((index, small) in VietnameseLetters.LOWER.withIndex()) {
            val big = VietnameseLetters.UPPER[index]
            assertEquals(small.uppercaseChar(), big)
            assertTrue("$small", lower.matches("$small"))
            assertFalse("$small", upper.matches("$small"))
            assertTrue("$big", upper.matches("$big"))
            assertFalse("$big", lower.matches("$big"))
        }
    }
}
