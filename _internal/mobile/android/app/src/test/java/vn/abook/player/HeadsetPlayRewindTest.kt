package vn.abook.player

import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/** App, headset and media controller resumes must never seek backwards. */
class HeadsetPlayRewindTest {
    private val voice = FakeExo()

    @Before fun setup() {
        Playback.player = voice.player
        voice.position = 600_000
    }

    @After fun cleanup() {
        Playback.player = null
    }


    @Test fun sessionAndAppPlayKeepThePausedPosition() {
        Playback.pause()
        PlaybackService.HeadsetSkips(voice.player) { false }.play()
        assertEquals("resume holds the cursor", 600_000L, voice.position)
        assertTrue(voice.playWhenReady)
        voice.playWhenReady = false
        voice.position = 600_000
        Playback.pause()
        Playback.play() // nút trong app
        assertEquals(600_000L, voice.position)
    }

    @Test fun controllerPlayKeepsThePausedPosition() {
        Playback.pause()
        PlaybackService.HeadsetSkips(voice.player) { false }.playWhenReady = true
        assertEquals("controller holds the cursor", 600_000L, voice.position)
    }

    @Test fun pauseDoesNotSeek() {
        Playback.pause()
        PlaybackService.HeadsetSkips(voice.player) { false }.play()
        assertEquals(600_000L, voice.position)
        assertTrue(voice.playWhenReady)
    }

    @Test fun explicitSeekCanStillReplay() {
        Playback.seekTo(590.0)
        Playback.play()
        assertEquals(590_000L, voice.position)
    }
}
