package vn.abook.player

import android.os.Handler
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import vn.abook.player.ui.nowplaying.SleepText

/**
 * "Nghe thêm" không bao giờ cộng dồn (chủ sách 05-11): hẹn 10 phút thì lắc bao nhiêu lần cũng chỉ về lại 10 phút. Hẹn theo chương hay vừa tự dừng thì về
 * "Mỗi lần nghe thêm". Lắc, nút trên thông báo và nút trong app cùng đi qua [SleepTimer.extend].
 */
class SleepExtendTest {
    private val voice = FakeExo()
    private fun field(name: String) = SleepTimer::class.java.getDeclaredField(name).also { it.isAccessible = true }
    private fun left() = SleepTimer.describe().getDouble("remaining")

    /** Đặt thẳng trạng thái "hẹn `picked` phút, còn `leftMin` phút, đang dừng" (setMinutes đụng cảm biến / nhật ký đêm - cần Android thật). */
    private fun timer(picked: Int, leftMin: Double) {
        field("mode").set(SleepTimer, SleepTimer.Mode.MINUTES)
        field("minutes").setInt(SleepTimer, picked)
        field("remainingMs").setLong(SleepTimer, (leftMin * 60_000).toLong())
        field("runningSinceMs").setLong(SleepTimer, 0L)
    }

    @Before fun setup() {
        Handler.reset()
        BookEditsFixtures.useStoreRoot(BookEditsFixtures.tempDir("sleep-extend"))
        Playback.player = voice.player
        SleepTimer.extendMinutes = 10
        SleepTimer.shakeEnabled = true
        field("mode").set(SleepTimer, SleepTimer.Mode.OFF)
        field("stoppedAtMs").setLong(SleepTimer, 0L)
    }

    @After fun cleanup() {
        field("mode").set(SleepTimer, SleepTimer.Mode.OFF)
        field("stoppedAtMs").setLong(SleepTimer, 0L)
        SleepTimer.extendMinutes = 10
        Playback.player = null
        Handler.reset()
    }

    @Test fun shakingThreeTimesAtSevenMinutesLeftGoesBackToTenNotThirtySeven() {
        timer(picked = 10, leftMin = 7.0)
        repeat(3) { assertTrue(SleepTimer.applyShake(System.currentTimeMillis())) }
        assertEquals(SleepTimer.Mode.MINUTES, SleepTimer.mode)
        assertEquals(10 * 60.0, left(), 1.0)
        assertEquals("số đã chọn không đổi", 10, SleepTimer.describe().getInt("minutes"))
    }

    @Test fun shakingAtFullTimeChangesNothing() {
        timer(picked = 10, leftMin = 10.0)
        SleepTimer.applyShake(System.currentTimeMillis())
        assertEquals(10 * 60.0, left(), 1.0)
    }

    @Test fun aRunningClockIsPutBackToo() {
        field("mode").set(SleepTimer, SleepTimer.Mode.MINUTES)
        field("minutes").setInt(SleepTimer, 10)
        field("remainingMs").setLong(SleepTimer, 10 * 60_000L)
        field("runningSinceMs").setLong(SleepTimer, System.currentTimeMillis() - 3 * 60_000L) // đang phát, đã chạy 3 phút: còn 7
        assertEquals(7 * 60.0, left(), 2.0)
        SleepTimer.extend()
        SleepTimer.extend()
        assertEquals(10 * 60.0, left(), 2.0)
        assertTrue("đồng hồ vẫn chạy theo trạng thái phát", field("runningSinceMs").getLong(SleepTimer) >= 0L)
    }

    @Test fun theMinutesPickedNotTheSettingsStepRuleATimerInMinutesMode() {
        SleepTimer.extendMinutes = 5 // "Mỗi lần nghe thêm" = 5 không kéo hẹn 30 phút về 5
        timer(picked = 30, leftMin = 12.0)
        SleepTimer.extend()
        assertEquals(30 * 60.0, left(), 1.0)
        assertEquals(30, SleepTimer.extendTarget())
        assertEquals("nhãn nút thông báo", "Hẹn lại 30 phút", SleepText.extendLabel(SleepTimer.extendTarget()))
    }

    @Test fun chapterModeGoesToTheSettingsStepAndThenStaysThere() {
        SleepTimer.extendMinutes = 15
        field("mode").set(SleepTimer, SleepTimer.Mode.CHAPTER)
        assertEquals(15, SleepTimer.extendTarget())
        assertTrue(SleepTimer.applyShake(System.currentTimeMillis()))
        assertEquals(SleepTimer.Mode.MINUTES, SleepTimer.mode)
        assertEquals(15 * 60.0, left(), 1.0)
        repeat(2) { SleepTimer.applyShake(System.currentTimeMillis()) }
        assertEquals("lắc tiếp không cộng dồn", 15 * 60.0, left(), 1.0)
        assertEquals(15, SleepTimer.describe().getInt("minutes"))
    }

    @Test fun anOffTimerIgnoresTheNotificationButtonAndAnOldShake() {
        assertFalse(SleepTimer.applyShake(System.currentTimeMillis()))
        SleepTimer.extend()
        assertEquals(SleepTimer.Mode.OFF, SleepTimer.mode)
        assertFalse("tắt quá 2 phút thì lắc không còn nghe", run {
            field("stoppedAtMs").setLong(SleepTimer, 1_000L)
            SleepTimer.applyShake(1_000L + 125_000L)
        })
    }

    /** setMinutes cần cảm biến (Motion) và nhật ký đêm: cho Motion coi như đang chạy và dựng ngữ cảnh chỉ có thư mục files. */
    private fun withSensors(body: () -> Unit) {
        val fixture = ColdStoreFixture() // chụp rồi bỏ trạng thái kho; dựng lại kho thử ngay dưới
        val context = fixture.contextFor(BookEditsFixtures.tempDir("sleep-extend-context"))
        BookEditsFixtures.useStoreRoot(BookEditsFixtures.tempDir("sleep-extend-store"))
        val running = Motion::class.java.getDeclaredField("running").also { it.isAccessible = true }
        Playback::class.java.getDeclaredField("appContext").also { it.isAccessible = true }.set(Playback, context)
        running.setBoolean(Motion, true)
        try {
            body()
        } finally {
            fixture.restore()
            running.setBoolean(Motion, false)
        }
    }

    @Test fun aShakeJustAfterTheTimerStoppedStartsExtendMinutesFresh() = withSensors {
        SleepTimer.extendMinutes = 15
        field("stoppedAtMs").setLong(SleepTimer, 1_000_000L)
        assertTrue(SleepTimer.applyShake(1_000_000L + 60_000L))
        assertEquals(SleepTimer.Mode.MINUTES, SleepTimer.mode)
        assertEquals(15 * 60.0, left(), 1.0)
        assertEquals(15, SleepTimer.describe().getInt("minutes"))
    }

    @Test fun theSafetyNetKeepsItsOneMinuteButAgainMeansTheSettingsStep() = withSensors {
        SleepTimer.extendMinutes = 15
        SleepTimer.safetyStopHours = 2.0
        voice.playing = true
        SleepTimer.maybeSafetyStop(0L) // không ai chạm máy từ thuở nào
        assertEquals(SleepTimer.Mode.MINUTES, SleepTimer.mode)
        assertEquals("đếm ngược vẫn 1 phút", 60.0, left(), 2.0)
        assertEquals("không ai chọn số phút", 0, SleepTimer.describe().getInt("minutes"))
        assertEquals(15, SleepTimer.extendTarget())
        assertEquals("Hẹn lại 15 phút", SleepText.extendLabel(SleepTimer.extendTarget()))
        SleepTimer.extend()
        SleepTimer.extend()
        assertEquals("người thức lắc thì không bị tắt lại sau 1 phút", 15 * 60.0, left(), 2.0)
        assertEquals(15, SleepTimer.describe().getInt("minutes"))
    }
}
