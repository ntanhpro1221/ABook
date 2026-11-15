package vn.abook.player.ui

import androidx.compose.runtime.BroadcastFrameClock
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.yield
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import vn.abook.player.ui.data.ListenBook
import vn.abook.player.ui.motion.BookMotion
import vn.abook.player.ui.nav.Destination
import vn.abook.player.ui.nav.NavState

/**
 * The staged page is drawn once at an invisible opacity before it moves, so its first rasterization never lands on a
 * moving frame. Opening and closing then advance through the same number of 60 Hz frames.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class BookPredrawTest {
    @Test fun stagedPageIsPreparedOnlyUntilItsTransitionStarts() = runBlocking {
        val clock = BroadcastFrameClock()
        val scope = CoroutineScope(coroutineContext + clock)
        val nav = NavState(scope)
        var now = 1_000_000_000L
        suspend fun frame() {
            yield(); now += 16_666_667L; clock.sendFrame(now); yield()
        }
        assertFalse(nav.preparing)
        nav.push(Destination.Book(ListenBook("a", "A book")))
        yield()
        assertTrue("composed and laid out, not yet moving", nav.preparing)
        assertEquals(0f, nav.progress.value)
        frame()
        assertTrue("still waiting for its layout acknowledgment", nav.preparing)
        nav.entryReady(nav.stack.top!!.key)
        val opening = mutableListOf<Float>()
        repeat(40) {
            frame()
            assertFalse("the predraw opacity never overlaps motion", nav.preparing && nav.progress.value > 0f)
            opening += nav.progress.value
        }
        assertFalse(nav.preparing)
        val closing = mutableListOf<Float>()
        scope.launch { nav.pop() }
        repeat(40) {
            frame()
            if (!nav.stack.isEmpty) closing += nav.progress.value
        }
        assertTrue(nav.stack.isEmpty)
        val openFrames = opening.count { it > 0f && it < 1f }
        val closeFrames = closing.count { it > 0f && it < 1f }
        assertTrue("open $openFrames / close $closeFrames frames", kotlin.math.abs(openFrames - closeFrames) <= 1)
        assertTrue(BookMotion.PREDRAW_ALPHA * 255f in .99f..1.01f)
    }
}
