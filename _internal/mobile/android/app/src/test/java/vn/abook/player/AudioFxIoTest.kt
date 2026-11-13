package vn.abook.player

import android.content.SharedPreferences
import android.os.Looper
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.lang.reflect.Proxy
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger
import java.util.concurrent.atomic.AtomicReference

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], application = android.app.Application::class)
class AudioFxIoTest {
    @Test fun toneChangesReturnWithoutWaitingForTheDiskQueueAndCommitAnOwnedSnapshotOffMain() {
        assertSame(Looper.getMainLooper(), Looper.myLooper())
        val mainThread = Thread.currentThread()
        assertTrue(DiskWrites.flush(TestTime.ms(5_000)))
        val holding = CountDownLatch(1)
        val release = CountDownLatch(1)
        val commits = AtomicInteger()
        val committed = AtomicReference<String>()
        val thread = AtomicReference<Thread>()
        val prefsField = AudioFx::class.java.getDeclaredField("prefs").apply { isAccessible = true }
        val oldPrefs = prefsField.get(AudioFx)
        val oldTones = AudioFx.tones.json().toString()
        val prefs = Proxy.newProxyInstance(javaClass.classLoader, arrayOf(SharedPreferences::class.java)) { _, method, _ ->
            if (method.name != "edit") null else {
                var tones: String? = null
                Proxy.newProxyInstance(javaClass.classLoader, arrayOf(SharedPreferences.Editor::class.java)) { editor, edit, args ->
                    when (edit.name) {
                        "putString" -> { if (args!![0] == "tones") tones = args[1] as String; editor }
                        "commit" -> { committed.set(tones); thread.set(Thread.currentThread()); commits.incrementAndGet(); true }
                        "apply" -> null
                        else -> editor
                    }
                }
            }
        }
        DiskWrites.post("tone-test") { holding.countDown(); release.await() }
        assertTrue(holding.await(TestTime.seconds(5), TimeUnit.SECONDS))
        try {
            prefsField.set(AudioFx, prefs)
            AudioFx.changeTone { it.select("off") }
            val offered = AudioFx.tones.json().toString()
            assertEquals("commit ran before the background writer was released", 0, commits.get())
            release.countDown()
            assertTrue(DiskWrites.flush(TestTime.ms(5_000)))
            assertEquals(offered, committed.get())
            assertNotSame(mainThread, thread.get())
        } finally {
            release.countDown()
            assertTrue(DiskWrites.flush(TestTime.ms(5_000)))
            prefsField.set(AudioFx, oldPrefs)
            AudioFx::class.java.getDeclaredField("tones").apply { isAccessible = true }
                .set(AudioFx, ToneLibrary.read(org.json.JSONObject(oldTones)))
        }
    }
}
