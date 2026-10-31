package vn.abook.player

import android.os.Handler
import androidx.media3.common.Player
import org.junit.After
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/** Chương phát qua mạng đang đệm: nhịp đồng hồ của Playback (kéo MusicBed lặp, nối vòng, đổi mốc) vẫn chạy; chờ quá lâu (IDLE) hay người nghe dừng thì nhịp ngừng. */
class BufferingMusicTickTest {
    private val voice = FakeExo()
    private fun field(name: String) = Playback::class.java.getDeclaredField(name).also { it.isAccessible = true }
    private val ticking get() = field("ticking").getBoolean(Playback)

    @Before fun setup() {
        Handler.reset()
        Playback.player = voice.player
        field("isPlaying").setBoolean(Playback, false)
        voice.playWhenReady = true
        voice.playing = false
        voice.state = Player.STATE_BUFFERING
    }

    @After fun cleanup() {
        Playback.player = null
        field("ticking").setBoolean(Playback, false)
        Handler.reset()
    }

    @Test fun bufferingStartsTheClockAndKeepsItRunning() {
        Playback.onWantsChanged() // ExoPlayer vào BUFFERING (PlaybackService.onPlaybackStateChanged)
        assertTrue(ticking)
        Handler.advance(2_000)
        assertTrue("đệm vẫn là đang nghe", ticking)
        voice.state = Player.STATE_IDLE // BufferingGuard thôi chờ: stop()
        Playback.onWantsChanged()
        Handler.advance(1_000)
        assertFalse(ticking)
    }

    @Test fun pausingDuringBufferingStopsTheClock() {
        Playback.onWantsChanged()
        voice.playWhenReady = false
        Playback.onWantsChanged()
        Handler.advance(1_000)
        assertFalse(ticking)
    }

    @Test fun aPausedPlayerDoesNotStartTheClock() {
        voice.playWhenReady = false
        Playback.onWantsChanged()
        assertFalse(ticking)
    }
}
