package vn.abook.player

import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], application = android.app.Application::class)
class PlaybackStartupIoTest {
    @Test fun creatingAndDestroyingAColdServiceNeverWaitsForStoreRecoveryOnMain() {
        val controller = Robolectric.buildService(PlaybackService::class.java)
        val holding = CountDownLatch(1)
        val release = CountDownLatch(1)
        val disk = Thread { synchronized(Store) {
            holding.countDown()
            // A broken implementation returns only when this deadline releases the Store monitor.
            release.await(4, TimeUnit.SECONDS)
        } }.apply { start() }
        assertTrue(holding.await(TestTime.seconds(5), TimeUnit.SECONDS))
        try {
            val start = System.nanoTime()
            val service = controller.create().get()
            assertFalse(service.initialization.isDone)
            controller.destroy()
            val elapsedMs = (System.nanoTime() - start) / 1_000_000
            println("cold service create/destroy with Store blocked: ${elapsedMs}ms")
            assertTrue("service lifecycle waited for Store ($elapsedMs ms)", elapsedMs < TestTime.ms(100, blockedMs = 4_000))
            release.countDown()
            service.initialization.get(TestTime.seconds(5), TimeUnit.SECONDS)
        } finally {
            release.countDown()
            disk.join(TestTime.ms(5_000))
            assertTrue(Playback.flushSaves(TestTime.ms(5_000)))
            Playback.player = null
        }
    }
}
