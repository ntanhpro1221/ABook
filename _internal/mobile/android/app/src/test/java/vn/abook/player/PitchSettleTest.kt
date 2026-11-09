package vn.abook.player

import android.os.Handler
import androidx.media3.common.MediaItem
import androidx.media3.common.PlaybackException
import androidx.media3.common.Player
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * Kéo Cao độ nhanh làm giọng đứng mãi (BUFFERING) trong khi nhạc nền vẫn chạy: mỗi lần đổi cao độ, ExoPlayer xả hết bộ xử lý tiếng rồi mới đổi.
 * Kéo chỉ áp giá trị cuối; lỗi thì nạp lại đúng chỗ; Về mặc định gỡ được giọng đang kẹt.
 */
class PitchSettleTest {
    private val voice = FakeExo()
    private fun sets() = voice.calls.count { it == "setPlaybackParameters" }

    @Before fun setup() {
        Handler.reset()
        Playback.reloads.clear()
        Playback.player = voice.player
        AudioFx.update(AudioFxSettings())
        voice.calls.clear()
    }

    @After fun cleanup() {
        AudioFx.update(AudioFxSettings())
        Playback.player = null
        Playback.clearError()
        Handler.reset()
    }

    @Test fun aDragReachesThePlayerOnlyOnceWithTheLastValue() {
        for (i in 0..40) {
            AudioFx.update(AudioFx.current.copy(pitch = -6.0 + i * .3), AudioFx.DRAG_SETTLE_MS)
            Handler.advance(30)
        }
        assertEquals(0, sets())
        AudioFx.update(AudioFx.current.copy(pitch = -4.5)) // thả tay
        Handler.advance(5_000)
        assertEquals(1, sets())
        assertEquals(AudioFx.pitchRatio(), voice.pitch, 0f)
        assertEquals(.7711054f, voice.pitch, 1e-6f)
    }

    @Test fun aHandRestingMidDragIsHeard() {
        AudioFx.update(AudioFx.current.copy(pitch = 2.0), AudioFx.DRAG_SETTLE_MS)
        Handler.advance(AudioFx.DRAG_SETTLE_MS)
        assertEquals(1, sets())
        assertEquals(AudioFx.pitchRatio(), voice.pitch, 0f)
    }

    @Test fun aLocalChapterThatFailsIsReloadedWhereItWas() {
        voice.item = MediaItem.Builder().setMediaId("ch1").build()
        voice.position = 42_000
        voice.playWhenReady = true
        val stuck = PlaybackException("stuck", null, PlaybackException.ERROR_CODE_UNSPECIFIED)
        Playback.onError(stuck)
        assertEquals(1, voice.calls.count { it == "prepare" })
        assertEquals(42_000, voice.position)
        assertTrue(voice.playWhenReady)
        assertEquals("", Playback.lastError)
        Playback.onError(stuck)
        Playback.onError(stuck) // lần thứ ba trong một phút: file hỏng thật, báo người nghe
        assertEquals(2, voice.calls.count { it == "prepare" })
        assertEquals(BufferingGuard.PLAY_FAILED, Playback.lastError)
        Handler.advance(61_000)
        Playback.onError(stuck)
        assertEquals(3, voice.calls.count { it == "prepare" })
    }

    @Test fun resetRestoresEverySettingAndFreesAStuckVoice() {
        voice.item = MediaItem.Builder().setMediaId("ch1").build()
        voice.position = 9_000
        AudioFx.update(AudioFxSettings(enabled = true, preset = 2, bands = listOf(4.0, 2.0, 0.0, -1.0, -2.0), boost = 6.0, pitch = -4.5,
            volume = .4, speed = 1.5, mono = true, balance = .5, skipSilence = true))
        voice.state = Player.STATE_BUFFERING
        voice.playWhenReady = true
        voice.calls.clear()
        AudioFx.reset()
        assertEquals(AudioFxSettings(speed = 1.5), AudioFx.current)
        assertEquals(1f, voice.pitch, 0f)
        assertEquals(1.5f, voice.speed, 0f)
        assertTrue(voice.calls.contains("seekTo"))
        assertEquals(9_000, voice.position)
    }

    @Test fun resetReloadsAVoiceThatAlreadyStopped() {
        voice.item = MediaItem.Builder().setMediaId("ch1").build()
        voice.state = Player.STATE_IDLE
        // a plain JVM test cannot build ExoPlaybackException (its message needs android.text); the player only checks it is there
        val unsafeClass = Class.forName("sun.misc.Unsafe")
        val unsafe = unsafeClass.getDeclaredField("theUnsafe").apply { isAccessible = true }.get(null)
        voice.error = unsafeClass.getMethod("allocateInstance", Class::class.java)
            .invoke(unsafe, androidx.media3.exoplayer.ExoPlaybackException::class.java) as androidx.media3.exoplayer.ExoPlaybackException
        AudioFx.reset()
        assertEquals(1, voice.calls.count { it == "prepare" })
    }
}
