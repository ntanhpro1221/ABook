package vn.abook.player

import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/** Soát a77 #8: bấm Phát ở thông báo / tai nghe / xe (phiên media) phải tự lùi giống nút trong app - cùng một đường "người nghe bấm phát tiếp". */
class HeadsetPlayRewindTest {
    private val voice = FakeExo()
    private fun field(name: String) = Playback::class.java.getDeclaredField(name).also { it.isAccessible = true }

    @Before fun setup() {
        Playback.player = voice.player
        Playback.configure(true)
        voice.position = 600_000
    }

    @After fun cleanup() {
        Playback.player = null
        field("pausedAtMs").setLong(Playback, 0L)
    }

    private fun pausedFor(ms: Long) = field("pausedAtMs").setLong(Playback, System.currentTimeMillis() - ms)

    @Test fun playFromTheMediaSessionRewindsLikeThePlayButtonInTheApp() {
        pausedFor(11 * 60_000L)
        PlaybackService.HeadsetSkips(voice.player) { false }.play()
        assertEquals("nghỉ hơn 10 phút: lùi 10 giây", 590_000L, voice.position)
        assertTrue(voice.playWhenReady)
        voice.playWhenReady = false
        voice.position = 600_000
        pausedFor(11 * 60_000L)
        Playback.play() // nút trong app
        assertEquals(590_000L, voice.position)
    }

    @Test fun setPlayWhenReadyTrueFromAControllerRewindsToo() {
        pausedFor(2 * 60_000L)
        PlaybackService.HeadsetSkips(voice.player) { false }.playWhenReady = true
        assertEquals("nghỉ dưới 10 phút: lùi 5 giây", 595_000L, voice.position)
    }

    @Test fun aShortPauseDoesNotRewind() {
        pausedFor(5_000L)
        PlaybackService.HeadsetSkips(voice.player) { false }.play()
        assertEquals(600_000L, voice.position)
        assertTrue(voice.playWhenReady)
    }

    @Test fun autoRewindOffMeansNoRewindFromAnyButton() {
        Playback.configure(false)
        pausedFor(11 * 60_000L)
        PlaybackService.HeadsetSkips(voice.player) { false }.play()
        assertEquals(600_000L, voice.position)
    }
}
