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

    // ---- a50: lỗi của đoạn chưa tới ---------------------------------------------------------------------------------------

    private val verdict = StalledClips.Companion::verdict

    @Test
    fun anyVoiceErrorOfALaterParagraphIsDeferredWhileTheListenerStillHasAudio() {
        val errors = listOf(
            VoiceException("bận", reason = "service"), VoiceException("chậm", reason = "timeout"),
            VoiceException("Không có mạng", offline = true), VoiceException("từ chối", reason = "rejected"), VoiceException("khoá sai", reason = "auth"), VoiceException("hết hạn mức", reason = "quota"),
        )
        for (error in errors) assertEquals(error.reason, StalledClips.Verdict.DEFER, verdict(error, true, true, false))
    }

    @Test
    fun onceTheQueueRunsDryTheSameErrorsStopTheListening() {
        for (error in listOf(VoiceException("bận", reason = "service"), VoiceException("Không có mạng", offline = true), VoiceException("từ chối", reason = "rejected"))) {
            assertEquals(error.reason, StalledClips.Verdict.FAIL, verdict(error, true, false, false))
        }
    }

    @Test
    fun aPausedListenerHearsNothingAboutServiceTroubleButStillSeesOtherErrors() {
        assertEquals(StalledClips.Verdict.QUIET, verdict(VoiceException("bận", reason = "service"), false, true, false))
        assertEquals(StalledClips.Verdict.QUIET, verdict(VoiceException("chậm", reason = "timeout"), false, false, false))
        assertEquals("trước a50 cũng báo", StalledClips.Verdict.FAIL, verdict(VoiceException("từ chối", reason = "rejected"), false, true, false))
    }

    @Test
    fun anErrorThatIsNotAVoiceErrorStillStops() {
        assertEquals(StalledClips.Verdict.FAIL, verdict(IllegalStateException("lạ"), true, true, false))
    }

    @Test
    fun aFailedProbeNeverStopsTheListening() {
        for (error in listOf(VoiceException("bận", reason = "service"), VoiceException("Không có mạng", offline = true), IllegalStateException("lạ"))) {
            assertEquals(StalledClips.Verdict.DEFER, verdict(error, true, true, true))
            // hàng đợi cạn trong lúc hỏi thăm: vẫn không dừng - pump hỏi lại thật (có thử lại) ngay
            assertEquals(StalledClips.Verdict.DEFER, verdict(error, true, false, true))
            assertEquals(StalledClips.Verdict.QUIET, verdict(error, false, true, true))
        }
    }

    // ---- a50: hỏi thăm = một lượt, không thử lại, không giữ khoá --------------------------------------------------------------

    @Test
    fun onlyAFreshAskWhileTheListenerHasAudioIsAProbe() {
        assertTrue(StalledClips.isProbe(fresh = true, listenerHasAudio = true))
        assertFalse("người nghe tới nơi: hỏi thật", StalledClips.isProbe(fresh = true, listenerHasAudio = false))
        assertFalse("đoạn bình thường", StalledClips.isProbe(fresh = false, listenerHasAudio = true))
    }

    @Test
    fun aProbeAsksOnceWithoutRetriesWhereARealAskRetriesTwice() {
        val normal = longArrayOf(2_000L, 5_000L)
        for ((probe, expectedAttempts) in listOf(true to 1, false to 3)) {
            val willRetryOn = ArrayList<Boolean>()
            val slept = ArrayList<Long>()
            val result = ClipRetry.run(true, StalledClips.delaysFor(probe, normal), sleep = { slept += it; true }) { willRetry ->
                willRetryOn += willRetry
                throw VoiceException("bận", reason = "service")
            }
            assertTrue(result.isFailure)
            assertEquals("probe=$probe", expectedAttempts, willRetryOn.size)
            assertEquals("lần cuối không còn thử lại", if (probe) listOf(false) else listOf(true, true, false), willRetryOn)
            assertEquals(if (probe) emptyList<Long>() else normal.toList(), slept)
        }
    }

    @Test
    fun theWakeLockIsHeldOnlyForOnlineReadsTheListenerWaitsOn() {
        assertTrue(StalledClips.holdsWake(online = true, listenerWants = true, probe = false))
        assertFalse(StalledClips.holdsWake(online = true, listenerWants = true, probe = true))
        assertFalse(StalledClips.holdsWake(online = true, listenerWants = false, probe = false))
        assertFalse(StalledClips.holdsWake(online = false, listenerWants = true, probe = false))
    }

    // ---- a50: hẹn hỏi lại không sống qua lần nhảy ---------------------------------------------------------------------------

    private class FakeLooper {
        val posted = ArrayList<Pair<Runnable, Long>>()
        val removed = ArrayList<Runnable>()
        val reminder = Reminder({ task, ms -> posted += task to ms }, { task -> removed += task; posted.removeAll { it.first === task } })
    }

    @Test
    fun oneReminderAtATime() {
        val looper = FakeLooper()
        var ran = 0
        looper.reminder.schedule(60) { ran += 1 }
        looper.reminder.schedule(60) { ran += 10 } // đã có hẹn: bỏ qua
        assertEquals(1, looper.posted.size)
        looper.posted[0].first.run()
        assertEquals(1, ran)
        looper.reminder.schedule(60) { ran += 100 } // hẹn cũ đã nổ: hẹn mới được
        assertEquals(2, looper.posted.size)
    }

    @Test
    fun aJumpCancelsTheReminderSoTheNewParagraphCanSetItsOwn() {
        val looper = FakeLooper()
        var oldRuns = 0
        var newRuns = 0
        looper.reminder.schedule(10_000) { oldRuns += 1 }
        val old = looper.posted[0].first
        looper.reminder.cancel() // tua / đổi chương (bumpGeneration)
        assertTrue("hẹn cũ bị gỡ khỏi hàng đợi", old in looper.removed)
        assertTrue(looper.posted.isEmpty())
        looper.reminder.schedule(10_000) { newRuns += 1 } // trước a50: cờ "đang hẹn" còn bật nên hẹn này bị nuốt
        assertEquals(1, looper.posted.size)
        looper.posted[0].first.run()
        assertEquals(0, oldRuns)
        assertEquals(1, newRuns)
        looper.reminder.cancel() // không có hẹn: không làm gì
    }
}
