package vn.abook.player

import android.content.ComponentName
import android.content.Intent
import android.os.Build
import android.os.Looper
import android.os.SystemClock
import android.util.Log
import android.view.MotionEvent
import androidx.media3.common.MediaItem
import androidx.media3.session.MediaBrowser
import androidx.media3.session.SessionToken
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.concurrent.TimeUnit
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

/** Real Media3 and service callbacks, wall-clock measurement, isolated emulator only. */
@RunWith(AndroidJUnit4::class)
class SleepKeepOnDeviceTest {
    private val instrumentation = InstrumentationRegistry.getInstrumentation()
    private val app = instrumentation.targetContext
    private fun <T> main(action: () -> T): T {
        var result: Result<T>? = null
        instrumentation.runOnMainSync { result = runCatching(action) }
        return result!!.getOrThrow()
    }
    private fun await(label: String, limit: Long, predicate: () -> Boolean) {
        val deadline = SystemClock.elapsedRealtime() + limit
        while (SystemClock.elapsedRealtime() < deadline) {
            if (main(predicate)) return
            Thread.sleep(40)
        }
        fail(label)
    }
    @Test fun twoRealMinuteCyclesKeepTheSelectedMode() {
        assertTrue("emulator only", Build.FINGERPRINT.contains("generic") || Build.MODEL.contains("sdk"))
        Store.init(app)
        val id = "sleepkeep0123456789abcdef"
        val dir = Store.bookDir(id)
        File(dir, "chapters").mkdirs()
        val samples = 16_000 * 190
        val wav = ByteBuffer.allocate(44 + samples * 2).order(ByteOrder.LITTLE_ENDIAN)
        wav.put("RIFF".toByteArray()).putInt(36 + samples * 2).put("WAVEfmt ".toByteArray()).putInt(16)
            .putShort(1).putShort(1).putInt(16_000).putInt(32_000).putShort(2).putShort(16)
            .put("data".toByteArray()).putInt(samples * 2)
        repeat(samples) { wav.putShort((if (it % 80 < 40) 200 else -200).toShort()) }
        File(dir, "chapters/1.wav").writeBytes(wav.array())
        val chapters = JSONArray().put(JSONObject().put("id", 1).put("fullTitle", "Chương thử")
            .put("available", true).put("file", "chapters/1.wav").put("duration", 190.0))
        Store.writeAtomic(File(dir, "book.json"), JSONObject().put("id", id).put("title", "Thử hẹn giờ ngủ")
            .put("narrator", "Âm thử").put("chapters", chapters).toString())
        val browser = MediaBrowser.Builder(app, SessionToken(app, ComponentName(app, PlaybackService::class.java)))
            .setApplicationLooper(Looper.getMainLooper()).buildAsync().get(30, TimeUnit.SECONDS)
        val oldSounds = Feedback.sounds
        try {
            main {
                Feedback.sounds = false
                SleepTimer.cancel()
                SleepTimer.schedule = null
                browser.setMediaItem(MediaItem.Builder().setMediaId("book/$id").build())
                browser.prepare()
                browser.play()
            }
            await("source starts", 15_000) { Playback.player?.isPlaying == true && Playback.bookId == id }
            main {
                SleepTimer.setMinutes(10, feedback = false)
                SleepTimer::class.java.getDeclaredField("remainingMs").also { it.isAccessible = true }.setLong(SleepTimer, 240_000)
                SleepTimer::class.java.getDeclaredField("runningSinceMs").also { it.isAccessible = true }.setLong(SleepTimer, 0)
                app.startActivity(Intent(app, vn.abook.player.ui.NativeActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
            }
            await("Activity resume resets four minutes to ten", 8_000) { SleepTimer.describe().getDouble("remaining") > 598 }
            instrumentation.waitForIdleSync()
            main {
                SleepTimer::class.java.getDeclaredField("remainingMs").also { it.isAccessible = true }.setLong(SleepTimer, 240_000)
                SleepTimer::class.java.getDeclaredField("runningSinceMs").also { it.isAccessible = true }.setLong(SleepTimer, 0)
            }
            val touchAt = SystemClock.uptimeMillis()
            instrumentation.sendPointerSync(MotionEvent.obtain(touchAt, touchAt, MotionEvent.ACTION_DOWN, 500f, 200f, 0))
            instrumentation.sendPointerSync(MotionEvent.obtain(touchAt, touchAt + 40, MotionEvent.ACTION_UP, 500f, 200f, 0))
            await("Activity touch resets four minutes to ten", 5_000) { SleepTimer.describe().getDouble("remaining") > 598 }
            Thread.sleep(500)
            val rows = JSONArray()
            repeat(2) { cycle ->
                main {
                    if (cycle == 0) SleepTimer.setMinutes(1, feedback = false) else browser.play()
                }
                await("cycle starts", 5_000) { Playback.player?.isPlaying == true }
                val started = SystemClock.elapsedRealtime()
                await("timer stops within 62 seconds", 62_000) { Playback.player?.playWhenReady == false }
                val elapsed = SystemClock.elapsedRealtime() - started
                assertTrue("cycle ${cycle + 1}: $elapsed ms", elapsed in 58_000..62_000)
                main {
                    assertEquals(SleepTimer.Mode.MINUTES, SleepTimer.mode)
                    assertEquals(60.0, SleepTimer.describe().getDouble("remaining"), 0.01)
                    assertFalse(SleepTimer.describe().getBoolean("counting"))
                }
                rows.put(JSONObject().put("cycle", cycle + 1).put("elapsedMs", elapsed))
                Log.i("SleepKeepTest", "CYCLE_${cycle + 1} elapsedMs=$elapsed retained=true remaining=60")
            }
            File(app.filesDir, "sleepkeep-measurement.json").writeText(JSONObject().put("cycles", rows)
                .put("activityResumeReset", true).put("activityTouchReset", true).toString())
        } finally {
            main { Feedback.sounds = oldSounds; browser.release() }
        }
    }
}
