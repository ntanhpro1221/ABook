package vn.abook.player.ui.motion

import androidx.compose.animation.core.CubicBezierEasing
import androidx.compose.animation.core.tween
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.unit.dp
import vn.abook.player.ui.theme.Bezier
import vn.abook.player.ui.theme.MotionMs

/** A single reversible clock shared by navigation, cover and content layers. */
object BookMotion {
    // At least sixteen rendered steps, even on a stalled display. With the
    // emphasized curve, each cover/content step stays below the 25% cut gate.
    val maxFrameNanos = MotionMs.BOOK_TRANSFORM_MS * 1_000_000L / 16
    val Emphasized = CubicBezierEasing(Bezier.EMPHASIZED_X1, Bezier.EMPHASIZED_Y1, Bezier.EMPHASIZED_X2, Bezier.EMPHASIZED_Y2)
    fun spec(distance: Float = 1f, reduced: Boolean = false) = tween<Float>(
        ((if (reduced) MotionMs.REDUCED_FADE_MS else MotionMs.BOOK_TRANSFORM_MS) * distance.coerceIn(0f, 1f)).toInt().coerceAtLeast(1),
        easing = Emphasized,
    )
    fun reveal(p: Float, delay: Float): Float = ((p - delay) / (1f - delay)).coerceIn(0f, 1f)
    fun libraryScale(p: Float): Float = 1f - MotionMs.BOOK_RECEDE * p.coerceIn(0f, 1f)
}

/** Reads the clock in the draw phase; never relays out a list on animation frames. */
@Composable
fun Modifier.bookReveal(delay: Float, opacity: () -> Float = { 1f }): Modifier {
    val flight = LocalBookCoverFlight.current
    return graphicsLayer {
        val amount = if (flight?.isTopBook() == true) BookMotion.reveal(flight.progress(), delay) else 1f
        alpha = amount * opacity()
        translationY = if (flight?.reducedMotion() == true) 0f else MotionMs.BOOK_DRIFT.dp.toPx() * (1f - amount)
    }
}
