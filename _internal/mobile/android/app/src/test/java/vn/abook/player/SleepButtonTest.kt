package vn.abook.player

import android.os.Handler
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/** Soát a77 #10: nút "Nghe thêm" của thông báo không phụ thuộc giao diện còn sống, và bấm nút cũ sau khi hẹn giờ đã hết thì không dựng hẹn giờ ngoài ý. */
class SleepButtonTest {
    private val voice = FakeExo()
    private fun field(name: String) = SleepTimer::class.java.getDeclaredField(name).also { it.isAccessible = true }

    @Before fun setup() {
        Handler.reset()
        BookEditsFixtures.useStoreRoot(BookEditsFixtures.tempDir("sleep-button"))
        Playback.player = voice.player
        field("mode").set(SleepTimer, SleepTimer.Mode.OFF)
    }

    @After fun cleanup() {
        field("mode").set(SleepTimer, SleepTimer.Mode.OFF)
        Playback.player = null
        Handler.reset()
    }

    @Test fun extendingAfterTheTimerEndedDoesNotStartANewOne() {
        assertEquals(SleepTimer.Mode.OFF, SleepTimer.mode)
        SleepTimer.extend() // nút "+10 phút" cũ còn trên thông báo
        assertEquals(SleepTimer.Mode.OFF, SleepTimer.mode)
        assertEquals("off", SleepTimer.describe().getString("mode"))
    }

    @Test fun extendingARunningTimerStillAddsTime() {
        // Đặt thẳng trạng thái "đang hẹn 5 phút" (setMinutes đụng cảm biến / nhật ký đêm - cần Android thật).
        field("mode").set(SleepTimer, SleepTimer.Mode.MINUTES)
        field("remainingMs").setLong(SleepTimer, 5 * 60_000L)
        field("minutes").setInt(SleepTimer, 5)
        SleepTimer.extend(10)
        assertEquals(SleepTimer.Mode.MINUTES, SleepTimer.mode)
        assertEquals(15 * 60.0, SleepTimer.describe().getDouble("remaining"), 1.0)
    }

    @Test fun theServiceOwnsTheListenerThatKeepsTheNotificationButtonsInStep() {
        var refreshed = 0
        val listener = SleepTimer.buttonsListener { refreshed += 1 }
        Playback.addListener(listener)
        Playback.emit("tick")
        Playback.emit("state")
        assertEquals(0, refreshed)
        Playback.emit("sleep") // lịch đêm / giao diện / lắc máy: mọi đổi hẹn giờ phát "sleep"
        assertEquals(1, refreshed)
        Playback.removeListener(listener) // PlaybackService.onDestroy
        Playback.emit("sleep")
        assertEquals(1, refreshed)
    }
}
