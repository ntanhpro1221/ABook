package vn.abook.player

import android.os.Looper
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], application = android.app.Application::class)
class PlaybackDestroyTest {
    private val controller = Robolectric.buildService(PlaybackService::class.java)
    private val voice = FakeExo()
    private fun field(name: String) = Playback::class.java.getDeclaredField(name).apply { isAccessible = true }

    @Before fun prepare() {
        controller.create().get().initialization.get(TestTime.seconds(5), TimeUnit.SECONDS)
        assertTrue(Playback.flushSaves(TestTime.ms(5_000)))
        BookEditsFixtures.useStoreRoot(BookEditsFixtures.tempDir("destroy-place"))
        val record = Store.activeRecord("destroy-book")
        Store.progress("destroy-book", 1, 12.0, 300.0, recordId = record)
        voice.item = androidx.media3.common.MediaItem.Builder().setMediaId("1").setTag(Playback.BookTag("destroy-book")).build()
        voice.position = 87_000
        voice.duration = 300_000
        Playback.player = voice.player
        field("bookId").set(Playback, "destroy-book")
        field("recordId").set(Playback, record)
        field("chapters").set(Playback, listOf(Playback.Chapter(1, "Test chapter", "1.mp3", 300.0)))
    }

    @After fun cleanup() {
        assertTrue(Playback.flushSaves(TestTime.ms(5_000)))
        field("bookId").set(Playback, "")
        field("recordId").set(Playback, "")
        field("chapters").set(Playback, emptyList<Playback.Chapter>())
        Playback.player = null
    }

    @Test fun destructionReturnsWhileBothWritersAreBlockedAndThePlaceStillLandsAfterwards() {
        assertSame(Looper.getMainLooper(), Looper.myLooper())
        val disk = BusyStore()
        try {
            DiskWrites.post("destroy-test") { Store.writeAtomic(java.io.File(Store.root, "queued.json"), "{}") }
            val start = System.nanoTime() // wallclock-ok: scaled lifecycle bound distinguishes returning from a blocked Store writer.
            controller.destroy()
            disk.assertStillHeld("onDestroy")
            val elapsedMs = (System.nanoTime() - start) / 1_000_000 // wallclock-ok: compared with TestTime.ms and a blocked-writer ceiling below.
            println("onDestroy with both writers blocked: ${elapsedMs}ms")
            assertTrue("onDestroy took $elapsedMs ms with Store blocked", elapsedMs < TestTime.ms(100, blockedMs = 4_000))
            assertNull(Playback.player)
            // This is already durable before the blocked writer can run, even though the service is gone.
            val journal = Store.root.listFiles()!!.single { it.name.startsWith(".final-place-") && it.extension == "json" }
            assertEquals(87_000L, org.json.JSONObject(journal.readText()).getLong("position"))
        } finally {
            disk.release()
        }
        assertTrue(Playback.flushSaves(TestTime.ms(5_000)))
        assertEquals(87.0, Store.state("destroy-book").getJSONObject("last").getDouble("seconds"), 0.001)
        assertTrue(Store.root.listFiles()!!.none { it.name.startsWith(".final-place-") })
        assertTrue(java.io.File(Store.root, "queued.json").isFile)
    }

    @Test fun closeJournalsThePlaceBeforeClearingTheBookAndDestroyingTheService() {
        val disk = BusyStore()
        try {
            controller.get().close()
            disk.assertStillHeld("close()")
            assertEquals("", Playback.bookId)
            controller.destroy()
            disk.assertStillHeld("onDestroy after close()")
            val journal = Store.root.listFiles()!!.single { it.name.startsWith(".final-place-") && it.extension == "json" }
            assertEquals(87_000L, org.json.JSONObject(journal.readText()).getLong("position"))
        } finally {
            disk.release()
        }
        assertTrue(Playback.flushSaves(TestTime.ms(5_000)))
        assertEquals(87.0, Store.state("destroy-book").getJSONObject("last").getDouble("seconds"), 0.001)
    }

    @Test fun aFlushTimeoutLeavesBothWritersAliveToFinishAfterTheServiceHasGone() {
        val disk = BusyStore()
        try {
            DiskWrites.post("destroy-test") { Store.writeAtomic(java.io.File(Store.root, "after-timeout.json"), "{}") }
            controller.destroy()
            disk.assertStillHeld("onDestroy")
            val start = System.nanoTime() // wallclock-ok: measures the explicitly shared flush timeout, not a performance target.
            assertFalse(Playback.flushSaves(100))
            val elapsedMs = (System.nanoTime() - start) / 1_000_000 // wallclock-ok: scaled upper bound remains below the blocked-writer duration.
            println("shared 100ms flush budget: ${elapsedMs}ms")
            assertTrue("flush exceeded its shared budget: $elapsedMs ms", elapsedMs < TestTime.ms(100, blockedMs = 200))
        } finally {
            disk.release()
        }
        assertTrue(Playback.flushSaves(TestTime.ms(5_000)))
        assertEquals(87.0, Store.state("destroy-book").getJSONObject("last").getDouble("seconds"), 0.001)
        assertTrue(java.io.File(Store.root, "after-timeout.json").isFile)
    }

    /**
     * A disk writer stuck inside Store's monitor, as on a slow phone. It gives the monitor up by itself after a bounded wait,
     * so a main-thread lifecycle call that wrongly waits for Store fails [assertStillHeld] instead of hanging the whole test JVM
     * (0.4.173 gate: close() -> SleepTimer.persist -> ListenPrefs read the prefs file under Store and the run never ended).
     */
    private class BusyStore {
        private val holding = CountDownLatch(1)
        private val release = CountDownLatch(1)
        @Volatile private var gaveUp = false
        private val thread = Thread {
            synchronized(Store) { holding.countDown(); gaveUp = !release.await(TestTime.seconds(10), TimeUnit.SECONDS) }
        }.apply { start() }

        init { assertTrue(holding.await(TestTime.seconds(5), TimeUnit.SECONDS)) }

        /** The call that just returned did so while the writer still held Store - it never waited for the disk. */
        fun assertStillHeld(what: String) {
            assertTrue("$what waited for Store while a disk writer held it", thread.isAlive && !gaveUp)
        }

        fun release() {
            release.countDown()
            thread.join(TestTime.ms(5_000))
        }
    }
}
