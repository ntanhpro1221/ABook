package vn.abook.player.ui.motion

import androidx.compose.animation.core.CubicBezierEasing
import androidx.compose.animation.core.tween
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.CompositingStrategy
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
    /**
     * Content settles at [MotionMs.BOOK_REVEAL_END], before the transform ends. The last and first few percent of the
     * clock then move only the cover and the page opacity, both linear in p, so opening and closing take the same time
     * to leave and to settle (the reversed stagger otherwise left rows fading after the cover had landed).
     */
    fun reveal(p: Float, delay: Float): Float = ((p - delay) / (MotionMs.BOOK_REVEAL_END - delay)).coerceIn(0f, 1f)
    fun libraryScale(p: Float): Float = 1f - MotionMs.BOOK_RECEDE * p.coerceIn(0f, 1f)

    /**
     * Page opacity while the entry is staged, before its first motion frame. One 8-bit step: invisible, yet every glyph,
     * icon path and cover texture is rasterized then rather than on the first moving frames. Without it the first
     * frames that showed the page took 23-26 ms of GPU and dropped a vsync in the recorded open (framestats, emulator).
     */
    const val PREDRAW_ALPHA = 1f / 255f
}

/** Reads the clock in the draw phase; never relays out a list on animation frames. */
@Composable
fun Modifier.bookReveal(delay: Float, opacity: () -> Float = { 1f }): Modifier {
    val flight = LocalBookCoverFlight.current
    return graphicsLayer {
        val amount = when {
            flight?.isTopBook() != true -> 1f
            // Fully drawn under the page's invisible predraw opacity (BookMotion.PREDRAW_ALPHA).
            flight.preparing() -> 1f
            else -> BookMotion.reveal(flight.progress(), delay)
        }
        alpha = amount * opacity()
        // Rows, title and actions fade per draw: no offscreen texture per row while the page transforms.
        compositingStrategy = CompositingStrategy.ModulateAlpha
        translationY = if (flight?.reducedMotion() == true) 0f else MotionMs.BOOK_DRIFT.dp.toPx() * (1f - amount)
    }
}
