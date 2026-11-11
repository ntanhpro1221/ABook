package vn.abook.player.ui.motion

import androidx.compose.runtime.MonotonicFrameClock

/** Keep the path visible when layout or rendering misses a frame. A delayed
 * callback may consume at most one 60 Hz frame of animation time. At normal
 * frame rates the design duration is unchanged; under load it stretches.
 */
internal class RenderedFrameClock(private val upstream: MonotonicFrameClock) : MonotonicFrameClock {
    private var previous: Long? = null
    private var animationTime = 0L

    override suspend fun <R> withFrameNanos(onFrame: (Long) -> R): R = upstream.withFrameNanos { now ->
        animationTime = previous?.let { animationTime + (now - it).coerceIn(0L, MAX_STEP_NANOS) } ?: now
        previous = now
        onFrame(animationTime)
    }

    private companion object {
        const val MAX_STEP_NANOS = 16_666_667L
    }
}
