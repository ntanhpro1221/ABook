package vn.abook.player.ui

import androidx.compose.runtime.BroadcastFrameClock
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.yield
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import vn.abook.player.ui.data.ListenBook
import vn.abook.player.ui.nav.Destination
import vn.abook.player.ui.nav.NavState

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class BookBackInterruptionTest {
    @Test fun systemBackDuringASlowOpeningKeepsTheReturnVisible() = runBlocking {
        val clock = BroadcastFrameClock()
        val scope = CoroutineScope(coroutineContext + clock)
        val nav = NavState(scope)
        var now = 1_000_000_000L
        suspend fun frame() {
            yield()
            now += 100_000_000L
            clock.sendFrame(now)
            yield()
        }
        nav.push(Destination.Book(ListenBook("a", "A book")))
        yield()
        nav.entryReady(nav.stack.top!!.key)
        repeat(7) { frame() }
        val departure = nav.progress.value
        assertTrue("partway through the slow opening: $departure", departure in .1f.. .9f)
        // A button Back has no drag events to stop the entering animation.
        // Both animations must still use the same rendered-time domain.
        scope.launch { nav.commitBack() }
        frame()
        assertEquals("Back must retain its page for the return path", 1, nav.stack.size)
        assertTrue("the return must not spend its duration in one frame", nav.progress.value > .01f)
        val positions = mutableListOf(departure)
        repeat(30) {
            frame()
            if (!nav.stack.isEmpty) positions += nav.progress.value
        }
        assertTrue("visible return frames: $positions", positions.count { it in .01f..(departure-.01f) } >= 3)
        assertTrue("continuous return: $positions", positions.zipWithNext().all { (a, b) -> kotlin.math.abs(b-a) < .25f })
        assertTrue(nav.stack.isEmpty)
    }
}
