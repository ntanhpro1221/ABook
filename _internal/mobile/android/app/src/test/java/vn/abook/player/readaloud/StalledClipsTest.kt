package vn.abook.player.readaloud

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** Đoạn hỏng vì dịch vụ trục trặc mà người nghe chưa tới: lượt đọc kế là lần hỏi mới, và hỏi lại cách nhau một nhịp (a46). */
class StalledClipsTest {
    private var nowMs = 0L
    private val stalled = StalledClips { nowMs * 1_000_000 }

    @Test
    fun onlyServiceTroubleCounts() {
        assertTrue(StalledClips.isServiceTrouble(VoiceException("bận", reason = "service")))
        assertTrue(StalledClips.isServiceTrouble(VoiceException("chậm", reason = "timeout")))
        // lời cuối của ClipReader (đã thử hết giọng) vẫn là dịch vụ trục trặc: hỏi lại sau được
        assertTrue(StalledClips.isServiceTrouble(VoiceException(ClipReader.NO_USABLE_VOICE, reason = "service", final = true)))
        assertFalse(StalledClips.isServiceTrouble(VoiceException("Không có mạng", offline = true)))
        assertFalse(StalledClips.isServiceTrouble(VoiceException("từ chối", reason = "rejected")))
        assertFalse(StalledClips.isServiceTrouble(VoiceException("khoá sai", reason = "auth")))
        assertFalse(StalledClips.isServiceTrouble(IllegalStateException("lạ")))
        assertFalse(StalledClips.isServiceTrouble(null))
    }

    @Test
    fun theNextReadOfThatSegmentIsFreshExactlyOnce() {
        assertFalse(stalled.takeFresh(0, 4))
        stalled.failed(0, 4)
        assertFalse("đoạn khác thì không", stalled.takeFresh(0, 5))
        assertFalse(stalled.takeFresh(1, 4))
        assertTrue(stalled.takeFresh(0, 4))
        assertFalse("một lần rồi quên", stalled.takeFresh(0, 4))
    }

    @Test
    fun reaskingWaitsOneBeatWhileTheListenerStillHasAudio() {
        stalled.failed(2, 7)
        assertEquals(StalledClips.REASK_MS, stalled.cooldownMs(2, 7))
        assertEquals("đoạn khác không phải chờ", 0L, stalled.cooldownMs(2, 8))
        nowMs += 4_000
        assertEquals(StalledClips.REASK_MS - 4_000, stalled.cooldownMs(2, 7))
        nowMs += StalledClips.REASK_MS
        assertEquals(0L, stalled.cooldownMs(2, 7))
        // lần hỏi mới lại hỏng: nghỉ lại từ đầu
        assertTrue(stalled.takeFresh(2, 7))
        assertEquals("đang hỏi thì không chờ", 0L, stalled.cooldownMs(2, 7))
        stalled.failed(2, 7)
        assertEquals(StalledClips.REASK_MS, stalled.cooldownMs(2, 7))
    }

    @Test
    fun aDifferentSegmentFailingReplacesTheOldOne() {
        stalled.failed(0, 3)
        stalled.failed(0, 6)
        assertFalse(stalled.takeFresh(0, 3))
        assertTrue(stalled.takeFresh(0, 6))
        stalled.failed(0, 6)
        stalled.clear()
        assertFalse(stalled.takeFresh(0, 6))
        assertEquals(0L, stalled.cooldownMs(0, 6))
    }
}
