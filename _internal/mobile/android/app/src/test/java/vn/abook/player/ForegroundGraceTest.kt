package vn.abook.player

import android.os.Looper
import androidx.media3.common.MediaItem
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config

/**
 * Soát Android 12-11 mục 1: dừng rồi dịch vụ phát còn giữ tiền cảnh đủ lâu cho các đường phát tiếp từ nền (lắc sau khi hẹn giờ tự dừng, lật máy,
 * lệnh từ máy tính); Android vẫn từ chối lên lại tiền cảnh thì dừng đúng chỗ, không phát chui không có dịch vụ tiền cảnh.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], application = android.app.Application::class)
class ForegroundGraceTest {
    private val service = Robolectric.buildService(PlaybackService::class.java)

    @After fun cleanup() {
        runCatching { service.destroy() }
        Playback.player = null
    }

    @Test fun graceCoversTheShakeWindowAndTheFlipWindow() {
        assertTrue(PlaybackService.foregroundGraceMs(flipEnabled = false) >= SleepTimer.SHAKE_RESUME_MS)
        assertTrue(SleepTimer.SHAKE_RESUME_MS >= 125_000L) // lắc trong 2 phút sau khi tự dừng ([SleepTimer.applyShake] 120 s)
        assertEquals(10 * 60_000L, PlaybackService.foregroundGraceMs(flipEnabled = true))
        assertEquals(Motion.FLIP_RESUME_MS, PlaybackService.foregroundGraceMs(flipEnabled = true))
    }

    @Test fun refusedForegroundPausesInsteadOfPlayingWithoutAForegroundService() {
        BookEditsFixtures.useStoreRoot(BookEditsFixtures.tempDir("foreground-refused"))
        val running = service.create().get()
        val player = Playback.player!!
        player.setMediaItems(listOf(MediaItem.Builder().setMediaId("ch1").setUri("file:///nothing.mp3").build()))
        player.playWhenReady = true
        running.foregroundRefused()
        shadowOf(Looper.getMainLooper()).idle()
        assertFalse(player.playWhenReady)
        assertEquals(1, player.mediaItemCount) // sách còn nạp: nút Phát trên thông báo nghe tiếp đúng chỗ
    }
}
