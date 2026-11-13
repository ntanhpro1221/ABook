package vn.abook.player

import android.os.Looper
import androidx.media3.common.MediaItem
import androidx.media3.session.CommandButton
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

/** Thẻ phát ở thanh thông báo: nút Đóng (X) ngay sau ba nút chính; bấm thì dừng, lưu chỗ, cất sách và tắt dịch vụ - thẻ biến mất. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], application = android.app.Application::class)
class NotificationCloseTest {
    private val service = Robolectric.buildService(PlaybackService::class.java)

    @After fun cleanup() {
        runCatching { service.destroy() }
        assertTrue(Playback.flushSaves(TestTime.ms(5_000)))
        Playback.player = null
    }

    /** Thẻ media Android 13+ / ColorOS chỉ vẽ năm ô: lùi · phát · tới + HAI nút đầu phần mở rộng - Đóng phải là một trong hai nút ấy. */
    @Test fun closeIsTheFirstExtraButtonWithItsOwnIcon() {
        val running = service.create().get()
        running.initialization.get(TestTime.seconds(5), java.util.concurrent.TimeUnit.SECONDS)
        val buttons = running.buttons()
        assertEquals(CommandButton.ICON_SKIP_BACK_15, buttons[0].icon)
        assertEquals(CommandButton.ICON_SKIP_FORWARD_15, buttons[1].icon)
        assertEquals(listOf(PlaybackService.CLOSE, PlaybackService.PREVIOUS_CHAPTER, PlaybackService.NEXT_CHAPTER),
            buttons.drop(2).map { it.sessionCommand })
        val close = buttons[2]
        assertEquals(R.drawable.ic_notification_close, close.iconResId)
        assertEquals(S.s_dong_5d54c2a1, close.displayName)
    }

    @Test fun closeStopsPlaybackEmptiesTheQueueAndStopsTheService() {
        BookEditsFixtures.useStoreRoot(BookEditsFixtures.tempDir("notification-close"))
        val running = service.create().get()
        running.initialization.get(TestTime.seconds(5), java.util.concurrent.TimeUnit.SECONDS)
        val player = Playback.player!!
        player.setMediaItems(listOf(MediaItem.Builder().setMediaId("ch1").setUri("file:///nothing.mp3").build()))
        player.playWhenReady = true
        var closed = 0
        val listener: (org.json.JSONObject) -> Unit = { if (it.optString("kind") == "closed") closed++ }
        Playback.addListener(listener)
        running.close()
        shadowOf(Looper.getMainLooper()).idle()
        Playback.removeListener(listener)
        assertFalse(player.playWhenReady)
        assertEquals(0, player.mediaItemCount) // hàng đợi rỗng: Media3 không giữ thẻ thông báo
        assertEquals(1, closed) // giao diện đang mở cũng cất sách như nút đóng trong app
        assertTrue(shadowOf(running).isStoppedBySelf)
    }
}
