package vn.abook.player.ui.nowplaying

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.TimeZone

/** Chữ hẹn giờ ngủ ngoài nhãn nút: đúng câu của bản web (PlayerViews.tsx SleepMenu / FadingNotice). */
class SleepTextTest {
    private val minutes = PlayerSleep(SleepKind.Minutes, 30, counting = true)

    @Test
    fun `heading and grid heading follow the mode`() {
        assertEquals("Dừng khi", SleepText.heading(SleepKind.Chapter))
        assertEquals("Tắt sau", SleepText.heading(SleepKind.Minutes))
        assertEquals("Đặt lại", SleepText.gridHeading(true))
        assertEquals("Dừng phát sau", SleepText.gridHeading(false))
    }

    @Test
    fun `note names fade seconds and extend minutes, and the morning card only for a listener who has one`() {
        val options = SleepOptions(fadeSeconds = 60, extendMinutes = 5)
        assertEquals("Tiếng nhỏ dần 60 giây trước khi dừng. Lúc đó lắc máy hoặc bấm “Nghe thêm” trên thông báo để nghe thêm 5 phút.", SleepText.note(options, false))
        assertTrue(SleepText.note(options, true).endsWith("Sáng hôm sau, thẻ “Tối qua” giúp tìm lại đoạn còn nhớ."))
    }

    @Test
    fun `a stop is recent for thirty minutes only`() {
        val stopped = PlayerSleep(SleepKind.Off, stoppedAtMs = 1_000_000)
        assertTrue(SleepText.recentlyStopped(stopped, 1_000_000 + 29 * 60_000))
        assertFalse(SleepText.recentlyStopped(stopped, 1_000_000 + 30 * 60_000))
        assertFalse(SleepText.recentlyStopped(PlayerSleep(SleepKind.Minutes, 15, true, stoppedAtMs = 1_000_000), 1_000_001))
        assertFalse(SleepText.recentlyStopped(PlayerSleep(SleepKind.Off), 5))
    }

    @Test
    fun `stopped line shows the clock in 24 hour form`() {
        val utc = TimeZone.getTimeZone("UTC")
        assertEquals("Hẹn giờ đã tắt tiếng lúc 22:05.", SleepText.stoppedAt(22 * 3_600_000L + 5 * 60_000L, utc))
        assertEquals("Bật lại 30 phút", SleepText.restart(30))
    }

    @Test
    fun `fading only while a running timer is inside the fade window`() {
        val options = SleepOptions(30, 10)
        assertTrue(SleepText.fading(minutes, 29_000, playing = true, options))
        assertFalse(SleepText.fading(minutes, 31_000, playing = true, options))
        assertFalse(SleepText.fading(minutes, 10_000, playing = false, options))
        assertFalse(SleepText.fading(minutes, 0, playing = true, options))
        assertFalse(SleepText.fading(PlayerSleep(), 10_000, playing = true, options))
        assertFalse(SleepText.fading(minutes.copy(counting = false), 10_000, playing = true, options))
        assertTrue(SleepText.fading(PlayerSleep(SleepKind.Chapter), 20_000, playing = true, options))
    }

    @Test
    fun `fading line promises the extend gesture and the minutes`() {
        assertEquals("Sắp tắt · lắc máy hoặc bấm “Nghe thêm” trên thông báo để nghe thêm 10 phút", SleepText.fadingLine(SleepOptions(30, 10)))
        assertEquals("+10 phút", SleepText.extendLabel(10))
    }
}
