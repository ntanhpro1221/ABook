package vn.abook.player

import android.os.Looper
import androidx.media3.common.MediaItem
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config
import java.io.File
import java.util.concurrent.CountDownLatch
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], application = android.app.Application::class)
class RecordSwitchIoTest {
    private fun field(name: String) = Playback::class.java.getDeclaredField(name).apply { isAccessible = true }

    @Test fun recordMutationRunsOffMainAndSavesTheOldPlaceBeforeLoadingTheNewProfile() {
        assertSame(Looper.getMainLooper(), Looper.myLooper())
        val mainThread = Thread.currentThread()
        val service = Robolectric.buildService(PlaybackService::class.java).create()
        service.get().initialization.get(TestTime.seconds(5), TimeUnit.SECONDS)
        BookEditsFixtures.useStoreRoot(BookEditsFixtures.tempDir("switch-record-io"))
        File(Store.bookDir("switch-book").apply { mkdirs() }, "1.mp3").writeBytes(byteArrayOf(1))
        val oldRecord = Store.activeRecord("switch-book")
        Store.progress("switch-book", 1, 12.0, 300.0, recordId = oldRecord)
        val voice = FakeExo().apply {
            item = MediaItem.Builder().setMediaId("1").setTag(Playback.BookTag("switch-book")).build()
            position = 87_000
            duration = 300_000
        }
        Playback.player = voice.player
        field("bookId").set(Playback, "switch-book")
        field("recordId").set(Playback, oldRecord)
        field("chapters").set(Playback, listOf(Playback.Chapter(1, "Test chapter", "1.mp3", 300.0)))
        val entered = CountDownLatch(1)
        val release = CountDownLatch(1)
        val thread = AtomicReference<Thread>()
        val worker = Executors.newSingleThreadExecutor()
        try {
            val switched = worker.submit {
                Playback.switchRecord("switch-book") {
                    thread.set(Thread.currentThread())
                    entered.countDown()
                    check(release.await(4, TimeUnit.SECONDS))
                    Store.createRecord("switch-book", "Test profile")
                }
            }
            // Let main capture/detach. A Store mutation submitted to main would block this idle call.
            val start = System.nanoTime()
            for (attempt in 0 until 1_000) {
                shadowOf(Looper.getMainLooper()).idle()
                if (entered.await(TestTime.ms(1), TimeUnit.MILLISECONDS)) break
            }
            val elapsedMs = (System.nanoTime() - start) / 1_000_000
            assertEquals(0L, entered.count)
            assertNotSame(mainThread, thread.get())
            assertTrue("main waited for the record mutation ($elapsedMs ms)", elapsedMs < TestTime.ms(100, blockedMs = 4_000))
            release.countDown()
            switched.get(TestTime.seconds(5), TimeUnit.SECONDS)
            shadowOf(Looper.getMainLooper()).idle()
            assertEquals("switch-book", Playback.bookId)
            assertNotEquals(oldRecord, Playback.recordId)
            assertEquals(0.0, Playback.positionSeconds, 0.001)
            val last = Store.readJson(File(Store.root, "state/$oldRecord.json"))!!.getJSONObject("last")
            assertEquals(87.0, last.getDouble("seconds"), 0.001)
        } finally {
            release.countDown()
            worker.shutdown()
            assertTrue(worker.awaitTermination(TestTime.seconds(5), TimeUnit.SECONDS))
            service.destroy()
            assertTrue(Playback.flushSaves(TestTime.ms(5_000)))
            field("bookId").set(Playback, "")
            field("recordId").set(Playback, "")
            field("chapters").set(Playback, emptyList<Playback.Chapter>())
            Playback.player = null
        }
    }
}
