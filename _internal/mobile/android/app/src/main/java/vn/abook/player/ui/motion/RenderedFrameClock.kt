package vn.abook.player.ui.motion

import androidx.compose.runtime.MonotonicFrameClock

/** Keep the path visible when layout or rendering misses a frame. A delayed
 * callback consumes a bounded interval (one 60 Hz frame by default). At normal
 * frame rates the design duration is unchanged; under sustained load it stretches.
 */
internal class RenderedFrameClock(
    private val upstream: MonotonicFrameClock,
    private val maxStepNanos: Long = 16_666_667L,
) : MonotonicFrameClock {
    private var previous: Long? = null
    private var animationTime = 0L

    override suspend fun <R> withFrameNanos(onFrame: (Long) -> R): R = upstream.withFrameNanos { now ->
        // Keep the debt from a brief hitch. Subsequent frames can catch up
        // within the same bounded step instead of permanently stretching only
        // the more expensive entrance. Sustained stalls still slow the path.
        animationTime = previous?.let { animationTime + (now - animationTime).coerceIn(0L, maxStepNanos) } ?: now
        previous = now
        onFrame(animationTime)
    }

}
