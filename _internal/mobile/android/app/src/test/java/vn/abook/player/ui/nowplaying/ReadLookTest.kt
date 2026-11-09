package vn.abook.player.ui.nowplaying

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/** Dáng chữ của Đọc theo, lời nhắc ở đầu chữ, và chạm chữ nào thì nghe từ đâu - cùng ca với web (ReaderScreen, labels.ts `readerHint`). */
class ReadLookTest {
    @Test
    fun `defaults match the web reader and any value in the picker range is taken`() {
        val look = ReadLook()
        assertEquals(20, look.size)
        assertEquals(1.7, look.leading, 0.0)
        assertEquals(34f, look.lineHeight, 0.01f)
        // Bộ chọn giá trị: mọi cỡ 12-40, mọi giãn dòng 1,2-2,4 bước 0,05 (ValueSpecs); ngoài miền / lệch lưới bị bỏ.
        assertEquals(24, look.sized(24).size)
        assertEquals(21, look.sized(21).size)
        assertEquals("cỡ ngoài miền bị bỏ", 20, look.sized(41).size)
        assertEquals(1.9, look.spaced(1.9).leading, 0.0)
        assertEquals(1.75, look.spaced(1.75).leading, 0.0)
        assertEquals("số đọc lại từ Float vẫn đúng lưới", 1.7, look.spaced(1.7f.toDouble()).leading, 0.0)
        assertEquals("lệch lưới bị bỏ", 1.7, look.spaced(1.73).leading, 0.0)
        assertEquals("ngoài miền bị bỏ", 1.7, look.spaced(2.5).leading, 0.0)
    }

    @Test
    fun `leading is written with a comma`() {
        assertEquals("1,5", ReadLook.leadingLabel(1.5))
        assertEquals("1,7", ReadLook.leadingLabel(1.7))
        assertEquals("20 · giãn dòng 1,7", ReadLook().summary)
    }

    @Test
    fun `hint follows the kind of chapter`() {
        // Chương đọc to bằng giọng máy.
        assertEquals(ReadHint.NO_VOICE, ReadHint.of(speaking = true, canSpeak = false, timed = true, tapped = false))
        assertEquals(ReadHint.TAP, ReadHint.of(speaking = true, canSpeak = true, timed = true, tapped = false))
        assertEquals("Nghe bằng giọng đọc.", ReadHint.of(speaking = true, canSpeak = true, timed = true, tapped = true))
        // Chương audio thu sẵn.
        assertEquals(ReadHint.UNTIMED, ReadHint.of(speaking = false, canSpeak = true, timed = false, tapped = true))
        assertEquals(ReadHint.TAP, ReadHint.of(speaking = false, canSpeak = false, timed = true, tapped = false))
        assertNull("đã chạm một lần thì thôi nhắc", ReadHint.of(speaking = false, canSpeak = false, timed = true, tapped = true))
    }

    @Test
    fun `touching a word listens from that word`() {
        val words = listOf(WordTiming(1000, 1400, 0, 4), WordTiming(1400, 1900, 5, 9), WordTiming(1900, 2500, 10, 14))
        val paragraph = ReadParagraph(0, "abcd efgh ijkl", 900, 2600, true, words)
        assertEquals(1000, ReadTap.startAt(paragraph, 2))
        assertEquals(1400, ReadTap.startAt(paragraph, 5))
        assertEquals("chạm khoảng trắng thì tới từ kế", 1400, ReadTap.startAt(paragraph, 4))
        assertEquals("quá cuối thì từ cuối", 1900, ReadTap.startAt(paragraph, 99))
        assertEquals("không có từ thì đầu đoạn", 900, ReadTap.startAt(paragraph.copy(words = emptyList()), 3))
    }
}
