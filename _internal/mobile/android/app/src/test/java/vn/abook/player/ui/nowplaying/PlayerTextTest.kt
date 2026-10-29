package vn.abook.player.ui.nowplaying

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import vn.abook.player.ui.data.PlayerChapter

/** Chữ thuần của Đang nghe (nhãn nút phát / chương sau, dòng tiến độ cả cuốn, "máy khác đã nghe xa hơn") - cùng ca với web labels.ts / model.ts. */
class PlayerTextTest {
    @Test
    fun `play button says what it waits for`() {
        assertEquals("Phát", PlayerText.toggleLabel(playing = false, buffering = false, speaking = false))
        assertEquals("Phát", PlayerText.toggleLabel(playing = false, buffering = true, speaking = true))
        assertEquals("Tạm dừng", PlayerText.toggleLabel(playing = true, buffering = false, speaking = false))
        assertEquals("Đang tải âm thanh", PlayerText.toggleLabel(playing = true, buffering = true, speaking = false))
        assertEquals("Đang chuẩn bị giọng đọc", PlayerText.toggleLabel(playing = true, buffering = true, speaking = true))
    }

    @Test
    fun `next chapter button names the last chapter and the missing audio`() {
        assertEquals("Đây là chương cuối", PlayerText.nextLabel(hasNext = false, hasLater = false))
        assertEquals("Chương sau", PlayerText.nextLabel(hasNext = true, hasLater = true))
        assertEquals("Chương sau chưa có audio", PlayerText.nextLabel(hasNext = false, hasLater = true))
    }

    @Test
    fun `has next looks at the loaded queue`() {
        val queue = listOf(PlayerChapter(1, "a", 1000), PlayerChapter(2, "b", 1000))
        assertTrue(PlayerText.hasNext(queue, 1))
        assertFalse(PlayerText.hasNext(queue, 2))
        assertFalse(PlayerText.hasNext(queue, 9))
        assertFalse(PlayerText.hasNext(queue, null))
    }

    @Test
    fun `heard base counts only audio chapters and finds the playing one before skipping text ones`() {
        val queue = listOf(PlayerChapter(1, "a", 600_000), PlayerChapter(2, "b", 600_000, "t/2.txt"), PlayerChapter(3, "c", 300_000))
        val atThree = PlayerText.heardBase(queue, 3)
        assertEquals(600.0, atThree.before, 0.0)
        assertEquals(900.0, atThree.total, 0.0)
        assertTrue(atThree.inside)
        // Chương chỉ có chữ đang đọc: đồng hồ của nó không cộng vào, và chương sau nó không bị tính là đã nghe.
        val atText = PlayerText.heardBase(queue, 2)
        assertEquals(600.0, atText.before, 0.0)
        assertFalse(atText.inside)
    }

    @Test
    fun `book progress line`() {
        assertEquals("Đã nghe 10% cả cuốn · còn 54 phút", PlayerText.bookProgress(true, 360.0, 3600.0, 1.0, false))
        assertEquals("Đã nghe 10% phần đã có · còn khoảng 36 phút ở tốc độ 1,5×", PlayerText.bookProgress(false, 360.0, 3600.0, 1.5, false))
        assertEquals("Đã nghe hết cả cuốn", PlayerText.bookProgress(true, 3590.0, 3600.0, 1.0, true))
        // Còn chừng một phút: không "khoảng ... ở tốc độ" cho vài chục giây.
        assertEquals("Đã nghe 99% cả cuốn · còn 1 phút", PlayerText.bookProgress(true, 3570.0, 3600.0, 2.0, false))
    }

    @Test
    fun `percent never rounds up to done or down to nothing`() {
        assertEquals("<1%", PlayerText.percent(0.004))
        assertEquals("0%", PlayerText.percent(0.0))
        assertEquals("42%", PlayerText.percent(0.4299))
        assertEquals("99%", PlayerText.percent(0.995))
        assertEquals("100%", PlayerText.percent(1.0))
    }

    @Test
    fun `another device place is only offered when it is newer and far`() {
        // Nạp lúc 100_000 ms; máy khác ghi lúc 200 giây.
        assertTrue(PlayerText.newerElsewhere(5, 300.0, 200.0, 100_000, hereChapter = 2, hereSeconds = 10.0))
        // Cũ hơn lúc nạp, hay ghi trong vòng 1 giây sau nạp: của chính máy này.
        assertFalse(PlayerText.newerElsewhere(5, 300.0, 90.0, 100_000, 2, 10.0))
        assertFalse(PlayerText.newerElsewhere(5, 300.0, 100.5, 100_000, 2, 10.0))
        // Cùng chương, lệch dưới 30 giây: cùng chỗ.
        assertFalse(PlayerText.newerElsewhere(2, 25.0, 200.0, 100_000, 2, 10.0))
        assertTrue(PlayerText.newerElsewhere(2, 45.0, 200.0, 100_000, 2, 10.0))
    }

    @Test
    fun `toast lines`() {
        assertEquals("Máy khác đã nghe tới Chương 5 · 12:04", PlayerText.elsewhereLine("Chương 5", 724.0))
        assertEquals("Nghe tiếp Phần 2", PlayerText.continueLine("Tên truyện · Phần 2"))
        assertEquals("Nghe tiếp Tên chẳng đánh số", PlayerText.continueLine("Tên chẳng đánh số"))
    }
}
