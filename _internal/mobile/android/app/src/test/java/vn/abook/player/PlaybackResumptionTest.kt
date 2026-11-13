package vn.abook.player

import android.os.Looper
import com.google.common.util.concurrent.ListenableFuture
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config
import java.io.File
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], application = android.app.Application::class)
class PlaybackResumptionTest {
    private val controller = Robolectric.buildService(PlaybackService::class.java)
    private val voice = FakeExo()
    private lateinit var service: PlaybackService

    @Before fun setup() {
        service = controller.create().get()
        assertTrue(Playback.flushSaves(TestTime.ms(5_000)))
        BookEditsFixtures.useStoreRoot(BookEditsFixtures.tempDir("playback-resumption"))
        BookEditsFixtures.copyBase(File(Store.root, "books/resume-book"))
        Store.progress("resume-book", 1, 7.5, 12.2)
        Playback.player = voice.player
        Playback::class.java.getDeclaredField("bookId").also { it.isAccessible = true }.set(Playback, "")
    }

    @After fun cleanup() {
        controller.destroy()
        Playback::class.java.getDeclaredField("pending").also { it.isAccessible = true }.set(Playback, null)
        Playback.player = null
    }

    private fun <T> awaitMain(future: ListenableFuture<T>): T {
        val deadline = System.nanoTime() + TimeUnit.MILLISECONDS.toNanos(TestTime.ms(5_000))
        while (!future.isDone && System.nanoTime() < deadline) {
            shadowOf(Looper.getMainLooper()).idle()
            Thread.sleep(5)
        }
        assertTrue("library preparation did not finish", future.isDone)
        return future.get()
    }

    @Test fun resumptionReturnsWhileStoreIsBusyAndMedia3SetsTheAudioQueueOnlyOnce() {
        val holding = CountDownLatch(1)
        val release = CountDownLatch(1)
        val disk = Thread { synchronized(Store) { holding.countDown(); release.await(TestTime.seconds(5), TimeUnit.SECONDS) } }.apply { start() }
        assertTrue(holding.await(TestTime.seconds(5), TimeUnit.SECONDS))
        val queue = try {
            service.resumeQueue(true).also { assertFalse(it.isDone) }
        } finally {
            release.countDown()
            disk.join(TestTime.ms(5_000))
        }
        val restored = awaitMain(queue)
        assertEquals(0, voice.calls.count { it == "setMediaItems" })
        assertEquals(7_500L, restored.startPositionMs)
        // Media3 owns this one queue installation after the callback future completes.
        voice.player.setMediaItems(restored.mediaItems, restored.startIndex, restored.startPositionMs)
        Playback.onQueueReplaced()
        assertEquals(1, voice.calls.count { it == "setMediaItems" })
        assertEquals("resume-book", Playback.bookId)
        assertEquals(7.5, Playback.positionSeconds, 0.001)
    }

    @Test fun aSystemResumeCardOnlyReadsMetadataWithoutLoadingOrPlaying() {
        val preview = awaitMain(service.resumeQueue(false))
        assertTrue(preview.mediaItems.isNotEmpty())
        assertEquals("", Playback.bookId)
        assertFalse(voice.calls.contains("setMediaItems"))
        assertFalse(voice.calls.contains("play"))
    }
}
