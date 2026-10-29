package vn.abook.player.ui.nowplaying

import org.junit.Assert.assertEquals
import org.junit.Test
import vn.abook.player.ui.data.PlayerState

/** Danh sách giọng của tấm "Giọng đọc" chỉ có giọng chạy trên máy; giọng trực tuyến vào để lời báo lỗi gọi đúng tên giọng đang chọn. */
class NowPlayingVoiceTest {
    private val all = listOf(
        PlayerVoice("edge:vi-VN-HoaiMyNeural", "Hoài My (Edge)", "female", online = true),
        PlayerVoice("vieneu:nano/aihan", "Ái Hân (VieNeu)", "female"),
    )

    @Test
    fun `the sheet lists installed voices only and the chosen online voice is still named`() {
        val state = nowPlayingState(PlayerState(bookId = "b", chapterId = 1, voiceId = "edge:vi-VN-HoaiMyNeural"), all, false, 0)
        assertEquals(listOf("vieneu:nano/aihan"), state.voices.map { it.id })
        assertEquals("Hoài My (Edge)", state.voiceName)
    }

    @Test
    fun `an unknown chosen voice has no name yet`() {
        assertEquals("", nowPlayingState(PlayerState(bookId = "b", chapterId = 1, voiceId = "x"), all, false, 0).voiceName)
        assertEquals("", nowPlayingState(PlayerState(bookId = "b", chapterId = 1), emptyList(), false, 0).voiceName)
    }
}
