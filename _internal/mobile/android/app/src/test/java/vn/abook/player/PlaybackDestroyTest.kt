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
        val holding = CountDownLatch(1)
        val release = CountDownLatch(1)
        val disk = Thread {
            synchronized(Store) { holding.countDown(); release.await() }
        }.apply { start() }
        assertTrue(holding.await(TestTime.seconds(5), TimeUnit.SECONDS))
        try {
            DiskWrites.post("destroy-test") { Store.writeAtomic(java.io.File(Store.root, "queued.json"), "{}") }
            val start = System.nanoTime()
            controller.destroy()
            val elapsedMs = (System.nanoTime() - start) / 1_000_000
            println("onDestroy with both writers blocked: ${elapsedMs}ms")
            assertTrue("onDestroy took $elapsedMs ms with Store blocked", elapsedMs < TestTime.ms(100, blockedMs = 4_000))
            assertNull(Playback.player)
            // This is already durable before the blocked writer can run, even though the service is gone.
            val journal = Store.root.listFiles()!!.single { it.name.startsWith(".final-place-") && it.extension == "json" }
            assertEquals(87_000L, org.json.JSONObject(journal.readText()).getLong("position"))
        } finally {
            release.countDown()
            disk.join(TestTime.ms(5_000))
        }
        assertTrue(Playback.flushSaves(TestTime.ms(5_000)))
        assertEquals(87.0, Store.state("destroy-book").getJSONObject("last").getDouble("seconds"), 0.001)
        assertTrue(Store.root.listFiles()!!.none { it.name.startsWith(".final-place-") })
        assertTrue(java.io.File(Store.root, "queued.json").isFile)
    }

    @Test fun closeJournalsThePlaceBeforeClearingTheBookAndDestroyingTheService() {
        val holding = CountDownLatch(1)
        val release = CountDownLatch(1)
        val disk = Thread { synchronized(Store) { holding.countDown(); release.await() } }.apply { start() }
        assertTrue(holding.await(TestTime.seconds(5), TimeUnit.SECONDS))
        try {
            controller.get().close()
            assertEquals("", Playback.bookId)
            controller.destroy()
            val journal = Store.root.listFiles()!!.single { it.name.startsWith(".final-place-") && it.extension == "json" }
            assertEquals(87_000L, org.json.JSONObject(journal.readText()).getLong("position"))
        } finally {
            release.countDown()
            disk.join(TestTime.ms(5_000))
        }
        assertTrue(Playback.flushSaves(TestTime.ms(5_000)))
        assertEquals(87.0, Store.state("destroy-book").getJSONObject("last").getDouble("seconds"), 0.001)
    }

    @Test fun aFlushTimeoutLeavesBothWritersAliveToFinishAfterTheServiceHasGone() {
        val holding = CountDownLatch(1)
        val release = CountDownLatch(1)
        val disk = Thread { synchronized(Store) { holding.countDown(); release.await() } }.apply { start() }
        assertTrue(holding.await(TestTime.seconds(5), TimeUnit.SECONDS))
        try {
            DiskWrites.post("destroy-test") { Store.writeAtomic(java.io.File(Store.root, "after-timeout.json"), "{}") }
            controller.destroy()
            val start = System.nanoTime()
            assertFalse(Playback.flushSaves(100))
            val elapsedMs = (System.nanoTime() - start) / 1_000_000
            println("shared 100ms flush budget: ${elapsedMs}ms")
            assertTrue("flush exceeded its shared budget: $elapsedMs ms", elapsedMs < TestTime.ms(100, blockedMs = 200))
        } finally {
            release.countDown()
            disk.join(TestTime.ms(5_000))
        }
        assertTrue(Playback.flushSaves(TestTime.ms(5_000)))
        assertEquals(87.0, Store.state("destroy-book").getJSONObject("last").getDouble("seconds"), 0.001)
        assertTrue(java.io.File(Store.root, "after-timeout.json").isFile)
    }
}
