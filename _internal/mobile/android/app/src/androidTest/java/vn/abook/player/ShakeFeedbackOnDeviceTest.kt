package vn.abook.player

import android.content.Context
import android.media.AudioAttributes
import android.media.AudioManager
import android.os.PowerManager
import android.os.SystemClock
import android.util.Log
import android.view.View
import androidx.media3.common.MediaItem
import androidx.media3.common.Player
import androidx.media3.exoplayer.ExoPlayer
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import kotlin.math.PI
import kotlin.math.sin
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

/** Only run on an isolated emulator. The host injects acceleration after READY_SENSOR_SHAKE.
 * No Activity, no phone, no network/model, and the screen stays off throughout the sensor test.
 */
@RunWith(AndroidJUnit4::class)
class ShakeFeedbackOnDeviceTest {
    private val instrumentation = InstrumentationRegistry.getInstrumentation()
    private val app = instrumentation.targetContext
    private fun main(action: () -> Unit) = instrumentation.runOnMainSync(action)
    private fun context() {
        Store.init(app)
        Playback::class.java.getDeclaredField("appContext").apply { isAccessible = true }.set(Playback, app)
    }

    private fun source(): File {
        val rate = 16_000
        val count = rate * 5
        val bytes = ByteBuffer.allocate(44 + count * 2).order(ByteOrder.LITTLE_ENDIAN)
        bytes.put("RIFF".toByteArray()).putInt(36 + count * 2).put("WAVEfmt ".toByteArray()).putInt(16)
            .putShort(1).putShort(1).putInt(rate).putInt(rate * 2).putShort(2).putShort(16)
            .put("data".toByteArray()).putInt(count * 2)
        repeat(count) { bytes.putShort((1000 * sin(2 * PI * 440 * it / rate)).toInt().toShort()) }
        return File(app.cacheDir, "shake-feedback-source.wav").apply { writeBytes(bytes.array()) }
    }

    @Test fun sensorShakeConfirmsWhilePlayingWithTheScreenOff() {
        assertTrue("emulator only", android.os.Build.FINGERPRINT.contains("generic") || android.os.Build.MODEL.contains("sdk"))
        val power = app.getSystemService(Context.POWER_SERVICE) as PowerManager
        assertFalse("host must turn off this emulator screen before starting", power.isInteractive)
        val wake = power.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "ABook:ShakeFeedbackTest")
        wake.acquire(30_000L)
        val native = Feedback.output
        val received = CountDownLatch(1)
        var soundCount = 0
        var hapticCount = 0
        var playedAt = 0L
        var hapticAt = 0L
        var voice: ExoPlayer? = null
        try {
            context()
            val file = source()
            main {
                voice = ExoPlayer.Builder(app).build().also {
                    it.setAudioAttributes(androidx.media3.common.AudioAttributes.Builder().setUsage(androidx.media3.common.C.USAGE_MEDIA).build(), false)
                    it.setMediaItem(MediaItem.fromUri(file.toURI().toString()))
                    it.repeatMode = Player.REPEAT_MODE_ONE
                    it.volume = 0.1f
                    Playback.player = it
                    it.prepare(); it.play()
                }
            }
            val deadline = SystemClock.elapsedRealtime() + 8000L
            var playing = false
            while (!playing && SystemClock.elapsedRealtime() < deadline) {
                main { playing = voice!!.isPlaying }
                Thread.sleep(50)
            }
            assertTrue("actual Media3 source is playing", playing)
            main {
                Feedback.sounds = true; Feedback.haptics = true
                SleepTimer.shakeEnabled = true
                SleepTimer.setMinutes(5, feedback = false)
                Feedback.output = object : Feedback.Output {
                    override fun sound(notes: List<Feedback.Note>, context: Context?) {
                        assertEquals(Feedback.notes("sleepExtend"), notes)
                        native.sound(notes, context)
                        playedAt = SystemClock.elapsedRealtimeNanos()
                        soundCount++
                    }
                    override fun haptic(effect: String, view: View?, context: Context?) {
                        assertEquals("CONFIRM", effect)
                        hapticAt = SystemClock.elapsedRealtimeNanos()
                        native.haptic(effect, view, context)
                        hapticCount++
                        received.countDown()
                    }
                }
            }
            Log.i("ShakeSfxTest", "READY_SENSOR_SHAKE")
            assertTrue("host must inject two acceleration peaks", received.await(15, TimeUnit.SECONDS))
            assertEquals(1, soundCount); assertEquals(1, hapticCount)
            val deltaMs = (hapticAt - playedAt) / 1_000_000.0
            assertTrue("same dispatch after AudioTrack.play: $deltaMs ms", deltaMs in 0.0..50.0)
            val audio = app.getSystemService(Context.AUDIO_SERVICE) as AudioManager
            assertTrue("real active sonification track", audio.activePlaybackConfigurations.any {
                it.audioAttributes.usage == AudioAttributes.USAGE_ASSISTANCE_SONIFICATION
            })
            assertFalse("no Activity or screen wake", power.isInteractive)
            main {
                assertTrue(voice!!.isPlaying)
                assertEquals(300.0, SleepTimer.describe().getDouble("remaining"), 2.0)
            }
            Log.i("ShakeSfxTest", "SENSOR_OK sound=$soundCount haptic=$hapticCount dispatchDeltaMs=$deltaMs usage=13 screenOff=true")
        } finally {
            main {
                Feedback.output = native
                Feedback.sounds = true; Feedback.haptics = true
                SleepTimer.cancel(); Motion.stop()
                Playback.player = null
                voice?.release()
            }
            wake.release()
        }
    }

    @Test fun soundAndHapticSwitchesAreIndependentWithoutAnActivity() {
        val native = Feedback.output
        var sounds = 0; var haptics = 0
        try {
            context()
            main {
                Playback.player = null
                SleepTimer.setMinutes(5, feedback = false)
                Feedback.output = object : Feedback.Output {
                    override fun sound(notes: List<Feedback.Note>, context: Context?) { sounds++ }
                    override fun haptic(effect: String, view: View?, context: Context?) { haptics++ }
                }
                ListenPrefs.apply(JSONObject().put("touchSounds", false).put("haptics", true), startup = true)
                SleepTimer.onShake()
                assertEquals(0, sounds); assertEquals(1, haptics)
                ListenPrefs.apply(JSONObject().put("touchSounds", true).put("haptics", false), startup = true)
                SleepTimer.onShake()
                assertEquals(1, sounds); assertEquals(1, haptics)
                ListenPrefs.apply(JSONObject().put("touchSounds", false).put("haptics", false), startup = true)
                SleepTimer.onShake()
                assertEquals(1, sounds); assertEquals(1, haptics)
            }
        } finally {
            main {
                Feedback.output = native
                Feedback.sounds = true; Feedback.haptics = true
                SleepTimer.cancel(); Motion.stop()
            }
        }
    }
}
