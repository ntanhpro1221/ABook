package vn.abook.player.ui

import java.io.File
import java.util.concurrent.Executor
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import vn.abook.player.ui.components.CoverFit

/** Bộ nhớ cỡ chữ đã vừa của bìa tự vẽ: ghi ra tệp, đọc lại ở lần chạy sau, tên sách có tab / xuống dòng / gạch chéo vẫn đúng, không phình vô hạn. */
class CoverFitTest {
    private val now = Executor { it.run() }
    private val backslash = 92.toChar().toString()

    private fun tempFile(): File = File.createTempFile("cover_fit", ".tsv").also { it.delete(); it.deleteOnExit() }

    @Test
    fun sizesSurviveAProcessRestart() {
        val file = tempFile()
        val awkward = "with" + 9.toChar() + "tab" + 10.toChar() + "newline" + backslash + "slash|Đêm trắng"
        val first = CoverFit(file, now)
        assertNull(first.get("k"))
        first.put("k", 13.25f)
        first.put(awkward, 7.5f)
        val second = CoverFit(file, now)
        assertEquals(13.25f, second.get("k"))
        assertEquals(7.5f, second.get(awkward))
        file.delete()
    }

    @Test
    fun escapeRoundTripsEveryControlCharacter() {
        val samples = listOf("", "a", backslash, backslash + "n", "" + 10.toChar() + 9.toChar() + 13.toChar() + backslash, "t|115.6|2.6|1.0|false|Tên" + 10.toChar() + "dài")
        for (text in samples) {
            val escaped = CoverFit.escape(text)
            assertEquals(text, CoverFit.unescape(escaped))
            assertTrue("còn xuống dòng / tab thật: $escaped", 10.toChar() !in escaped && 9.toChar() !in escaped && 13.toChar() !in escaped)
        }
    }

    @Test
    fun withoutAFileItStillRemembersInMemoryAndStaysBounded() {
        val memory = CoverFit(null, now)
        for (i in 0 until 3000) memory.put("k$i", i.toFloat())
        assertNull("mục cũ nhất phải bị bỏ", memory.get("k0"))
        assertEquals(2999f, memory.get("k2999"))
    }
}
