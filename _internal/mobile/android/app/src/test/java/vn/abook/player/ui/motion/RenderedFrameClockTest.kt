package vn.abook.player.ui.motion

import androidx.compose.animation.core.Animatable
import androidx.compose.runtime.MonotonicFrameClock
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class RenderedFrameClockTest {
    private class SlowFrames : MonotonicFrameClock {
        private var now = 0L
        override suspend fun <R> withFrameNanos(onFrame: (Long) -> R): R {
            now += 1_000_000_000L
            return onFrame(now)
        }
    }

    @Test fun secondLongFrameGapsCannotSpendTheWholeOpeningOrClosingPath() = runBlocking {
        for (opening in listOf(true, false)) {
            val progress = Animatable(if (opening) 0f else 1f)
            val positions = mutableListOf<Float>()
            withContext(RenderedFrameClock(SlowFrames())) {
                progress.animateTo(if (opening) 1f else 0f, if (opening) Motion.PushIn else Motion.popOut(1f)) {
                    positions += value
                }
            }
            assertEquals(if (opening) 1f else 0f, progress.value, 0f)
            assertTrue(positions.count { it > .05f && it < .95f } >= 4)
            assertTrue("opening=$opening positions=$positions", positions.zipWithNext().all { (a, b) -> kotlin.math.abs(b - a) <= .5f })
        }
    }

    @Test fun normalFrameTimesArePreserved() = runBlocking {
        var now = 1_000_000_000L
        val upstream = object : MonotonicFrameClock {
            override suspend fun <R> withFrameNanos(onFrame: (Long) -> R): R {
                now += 8_333_333L
                return onFrame(now)
            }
        }
        val clock = RenderedFrameClock(upstream)
        repeat(40) { clock.withFrameNanos { assertEquals(now, it) } }
    }
}
