package vn.abook.player

import androidx.media3.common.Player
import org.junit.Assert.assertEquals
import org.junit.Test

/** Nhạc nền hiểu trạng thái giọng ra sao ([musicVoice]): đệm chương phát qua mạng là khựng, không phải dừng - như web và Qt. */
class MusicVoiceTest {
    @Test
    fun `buffering while the listener still wants to play keeps the music on`() {
        // Trước đây nhạc theo mốc dừng phụt mỗi lần chương phát qua mạng đệm (isPlaying = false), web và Qt thì chạy tiếp.
        assertEquals(MusicVoice(on = true, stopNow = false, ended = false), musicVoice(playing = false, starved = false, playWhenReady = true, state = Player.STATE_BUFFERING))
    }

    @Test
    fun `pausing during buffering stops the music at once`() {
        assertEquals(MusicVoice(on = false, stopNow = true, ended = false), musicVoice(playing = false, starved = false, playWhenReady = false, state = Player.STATE_BUFFERING))
    }

    @Test
    fun `the buffering guard giving up stops the voice without counting as the listener's pause`() {
        // BufferingGuard gọi stop(): IDLE, playWhenReady vẫn true - danh sách phát chờ PAUSE_GRACE_MS như khe nối, nhạc theo mốc dừng.
        assertEquals(MusicVoice(on = false, stopNow = false, ended = false), musicVoice(playing = false, starved = false, playWhenReady = true, state = Player.STATE_IDLE))
    }

    @Test
    fun `playing, a starved read-aloud queue and the end of the book keep their meaning`() {
        assertEquals(MusicVoice(on = true, stopNow = false, ended = false), musicVoice(playing = true, starved = false, playWhenReady = true, state = Player.STATE_READY))
        assertEquals(MusicVoice(on = true, stopNow = false, ended = false), musicVoice(playing = false, starved = true, playWhenReady = true, state = Player.STATE_ENDED))
        assertEquals(MusicVoice(on = false, stopNow = false, ended = true), musicVoice(playing = false, starved = false, playWhenReady = true, state = Player.STATE_ENDED))
        assertEquals(MusicVoice(on = false, stopNow = true, ended = false), musicVoice(playing = false, starved = false, playWhenReady = false, state = Player.STATE_READY))
    }

    @Test
    fun `no player yet counts as stopped by the listener`() {
        assertEquals(MusicVoice(on = false, stopNow = true, ended = false), musicVoice(playing = false, starved = false, playWhenReady = false, state = Player.STATE_IDLE))
    }
}
