package vn.abook.player

import android.os.Handler
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import vn.abook.player.ui.nowplaying.SleepText

/**
 * Soát Android 12-11 mục 2: hẹn giờ đứng vì tạm dừng tới 30 phút ([SleepText.PAUSED_EXPIRES_MS]) thì tự bỏ - tối mai bấm phát cùng cuốn không bị hẹn giờ
 * cũ nhỏ dần rồi tắt tiếng. Lúc đứng thì vòng đếm 250 ms ngừng. Cùng hạn với web (sleep.ts) và Qt (playerlogic.h).
 */
class SleepPausedExpiryTest {
    private val voice = FakeExo()
    private fun field(name: String) = SleepTimer::class.java.getDeclaredField(name).also { it.isAccessible = true }
    private val paused get() = field("pausedAtMs").getLong(SleepTimer)

    private fun timer(picked: Int, leftMin: Double) {
        field("mode").set(SleepTimer, SleepTimer.Mode.MINUTES)
        field("minutes").setInt(SleepTimer, picked)
        field("remainingMs").setLong(SleepTimer, (leftMin * 60_000).toLong())
        field("runningSinceMs").setLong(SleepTimer, 0L)
        field("ownerBook").set(SleepTimer, Playback.bookId)
        field("ownerRecord").set(SleepTimer, Playback.recordId)
    }

    private fun reset() {
        field("mode").set(SleepTimer, SleepTimer.Mode.OFF)
        field("automaticReason").set(SleepTimer, "")
        field("stoppedAtMs").setLong(SleepTimer, 0L)
        field("pausedAtMs").setLong(SleepTimer, 0L)
        field("ticking").setBoolean(SleepTimer, false)
    }

    @Before fun setup() {
        Handler.reset()
        BookEditsFixtures.useStoreRoot(BookEditsFixtures.tempDir("sleep-paused-expiry"))
        Playback.player = voice.player
        voice.playing = false
        reset()
    }

    @After fun cleanup() {
        assertTrue(DiskWrites.flush(TestTime.ms(5_000)))
        reset()
        Playback.player = null
        Handler.reset()
    }

    @Test fun theLimitIsThirtyMinutesLikeWebAndQt() {
        assertEquals(30 * 60_000L, SleepText.PAUSED_EXPIRES_MS)
        assertEquals("Đang tạm dừng - đồng hồ cũng dừng. Dừng quá 30 phút thì hẹn giờ tự tắt.", SleepText.pausedNote)
    }

    @Test fun repeatedPausedSavesDoNotRenewTheRestoredTimerLifetime() {
        timer(picked = 30, leftMin = 20.0)
        SleepTimer.onPlaying(false)
        val since = paused
        SleepTimer.persist(since + 10 * 60_000L)
        assertTrue(DiskWrites.flush(TestTime.ms(5_000)))
        val saved = JSONObject(java.io.File(Store.root, "listen-prefs.json").readText()).getJSONObject("timer")
        assertEquals(since, saved.getLong("savedAt"))
        reset()
        SleepTimer.restore(saved, since + SleepText.PAUSED_EXPIRES_MS)
        assertEquals(SleepTimer.Mode.OFF, SleepTimer.mode)
    }

    @Test fun aPausedTimerExpiresAfterThirtyMinutesAndIsForgotten() {
        timer(picked = 30, leftMin = 20.0)
        SleepTimer.onPlaying(false)
        val since = paused
        assertTrue(since > 0)
        assertFalse(SleepTimer.expireIfPausedTooLong(since + SleepText.PAUSED_EXPIRES_MS - 1))
        assertEquals(SleepTimer.Mode.MINUTES, SleepTimer.mode)
        assertTrue(SleepTimer.expireIfPausedTooLong(since + SleepText.PAUSED_EXPIRES_MS))
        assertEquals(SleepTimer.Mode.OFF, SleepTimer.mode)
        assertEquals(0L, SleepTimer.describe().optLong("stoppedAt", 0L)) // không phải "Hẹn giờ đã tắt tiếng lúc ..."
        ListenPrefs.load() // tiến trình chết rồi dậy cũng không có lại
        assertEquals(SleepTimer.Mode.OFF, SleepTimer.mode)
    }

    @Test fun playingAgainAfterTheLimitDoesNotRunLastNightsTimer() {
        timer(picked = 30, leftMin = 20.0)
        field("pausedAtMs").setLong(SleepTimer, System.currentTimeMillis() - SleepText.PAUSED_EXPIRES_MS - 1)
        voice.playing = true
        SleepTimer.onPlaying(true)
        assertEquals(SleepTimer.Mode.OFF, SleepTimer.mode)
    }

    @Test fun playingAgainBeforeTheLimitKeepsTheTimerAndRestartsTheLoop() {
        timer(picked = 30, leftMin = 20.0)
        field("pausedAtMs").setLong(SleepTimer, System.currentTimeMillis() - 10 * 60_000L)
        voice.playing = true
        SleepTimer.onPlaying(true)
        assertEquals(SleepTimer.Mode.MINUTES, SleepTimer.mode)
        assertEquals(0L, paused)
        assertTrue(field("ticking").getBoolean(SleepTimer))
    }

    @Test fun theQueuedCheckTurnsTheTimerOffWhilePaused() {
        timer(picked = 30, leftMin = 20.0)
        field("pausedAtMs").setLong(SleepTimer, System.currentTimeMillis() - SleepText.PAUSED_EXPIRES_MS - 1)
        SleepTimer.onPlaying(false) // dừng lại lần nữa: giữ mốc cũ, lần xét tới hạn ngay
        Handler.advance(0)
        assertEquals(SleepTimer.Mode.OFF, SleepTimer.mode)
    }

    @Test fun anEndOfChapterTimerExpiresToo() {
        field("mode").set(SleepTimer, SleepTimer.Mode.CHAPTER)
        field("ownerBook").set(SleepTimer, Playback.bookId)
        field("ownerRecord").set(SleepTimer, Playback.recordId)
        SleepTimer.onPlaying(false)
        assertTrue(SleepTimer.expireIfPausedTooLong(paused + SleepText.PAUSED_EXPIRES_MS))
        assertEquals(SleepTimer.Mode.OFF, SleepTimer.mode)
    }

    @Test fun theTickLoopStopsWhilePaused() {
        timer(picked = 30, leftMin = 20.0)
        SleepTimer.extend(feedback = false) // dựng vòng đếm khi đang dừng
        Handler.advance(1_000)
        assertFalse(field("ticking").getBoolean(SleepTimer))
        assertEquals(SleepTimer.Mode.MINUTES, SleepTimer.mode)
    }

    @Test fun aSnapshotSavedWhilePausedIsNotRestoredAfterTheLimit() {
        val now = 1_000_000_000L
        val snapshot = { savedAt: Long -> JSONObject().put("source", "manual").put("bookId", "a").put("recordId", "r")
            .put("savedAt", savedAt).put("minutes", 30).put("remainingMs", 600_000L) }
        SleepTimer.restore(snapshot(now - SleepText.PAUSED_EXPIRES_MS), now)
        assertEquals(SleepTimer.Mode.OFF, SleepTimer.mode)
        SleepTimer.restore(snapshot(now - 29 * 60_000L), now)
        assertEquals(SleepTimer.Mode.MINUTES, SleepTimer.mode)
        assertEquals("đồng hồ đứng từ lúc dừng đã ghi, không từ lúc dậy", now - 29 * 60_000L, paused)
    }
}
