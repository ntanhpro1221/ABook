package vn.abook.player.ui

import androidx.compose.animation.core.VectorConverter
import androidx.compose.animation.core.TargetBasedAnimation
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import vn.abook.player.ui.motion.BookMotion
import vn.abook.player.ui.theme.MotionMs

class BookMotionTest {
    @Test fun bothDirectionsUseTheSameDurationAndRetraceThePath() {
        val open = TargetBasedAnimation(BookMotion.spec(), Float.VectorConverter, 0f, 1f)
        val close = TargetBasedAnimation(BookMotion.spec(), Float.VectorConverter, 1f, 0f)
        assertEquals(350_000_000L, open.durationNanos)
        assertEquals(open.durationNanos, close.durationNanos)
        for (time in 0L..350L step 5) {
            val p = open.getValueFromNanos(time * 1_000_000L)
            val q = close.getValueFromNanos(time * 1_000_000L)
            assertEquals(1f, p + q, 0.0001f)
            assertTrue(BookMotion.libraryScale(p) in .985f..1f)
        }
    }

    @Test fun contentSettlesBeforeTheTransformSoBothEndsMoveOnlyCoverAndPage() {
        for (delay in listOf(0f, .06f, .12f)) {
            for (p in listOf(MotionMs.BOOK_REVEAL_END, .98f, 1f)) assertEquals(1f, BookMotion.reveal(p, delay), 0f)
            assertTrue(BookMotion.reveal(MotionMs.BOOK_REVEAL_END - .02f, delay) < 1f)
            assertEquals(0f, BookMotion.reveal(delay, delay), 0f)
        }
    }

    @Test fun cancelledGestureSettlesOnlyTheRemainingDistance() {
        val remaining = TargetBasedAnimation(BookMotion.spec(.4f), Float.VectorConverter, .6f, 1f)
        assertEquals(140_000_000L, remaining.durationNanos)
        assertEquals(1f, remaining.getValueFromNanos(remaining.durationNanos), 0f)
    }

    @Test fun stalledFramesCannotSkipMoreThanAQuarterOfTheCoverOrContent() {
        for (opening in listOf(true, false)) {
            val animation = TargetBasedAnimation(BookMotion.spec(), Float.VectorConverter, if (opening) 0f else 1f, if (opening) 1f else 0f)
            var previous = if (opening) 0f else 1f
            for (time in BookMotion.maxFrameNanos..animation.durationNanos step BookMotion.maxFrameNanos) {
                val next = animation.getValueFromNanos(time)
                assertTrue(kotlin.math.abs(next-previous) <= .25f)
                for (delay in listOf(0f, .06f, .12f)) {
                    val a = previous * BookMotion.reveal(previous, delay)
                    val b = next * BookMotion.reveal(next, delay)
                    assertTrue("opening=$opening time=$time delay=$delay", kotlin.math.abs(b-a) <= .25f)
                }
                previous = next
            }
        }
    }
}
