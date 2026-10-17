package vn.abook.player

import androidx.media3.common.Player
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.lang.reflect.Proxy

/**
 * Đoạn đang phát luồng (`abooklive`, độ dài chưa biết) làm ExoPlayer coi mục là TRỰC TIẾP suốt đời mục; phiên media (thông báo, màn khoá, xe) thấy thế thì bỏ lệnh tua và báo tốc độ 0.
 * Lớp phiên media ([PlaybackService.HeadsetSkips]) phải trả "không trực tiếp" khi đang ở chương chữ (uxfix60, soát a59p), còn chương audio thì như ExoPlayer.
 */
class LiveItemSessionTest {
    /** ExoPlayer giả: chỉ trả lời hai câu hỏi về mục trực tiếp (như lúc đang phát luồng một đoạn). */
    private val streaming = Proxy.newProxyInstance(Player::class.java.classLoader, arrayOf(Player::class.java)) { _, method, _ ->
        when (method.name) {
            "isCurrentMediaItemLive", "isCurrentMediaItemDynamic" -> true
            else -> throw UnsupportedOperationException(method.name)
        }
    } as Player

    @Test
    fun aStreamedParagraphIsNotLiveForTheMediaSession() {
        val session = PlaybackService.HeadsetSkips(streaming) { true }
        assertFalse(session.isCurrentMediaItemLive)
        assertFalse(session.isCurrentMediaItemDynamic)
    }

    @Test
    fun audioChaptersKeepWhatExoPlayerSays() {
        val session = PlaybackService.HeadsetSkips(streaming) { false }
        assertTrue(session.isCurrentMediaItemLive)
        assertTrue(session.isCurrentMediaItemDynamic)
    }
}
