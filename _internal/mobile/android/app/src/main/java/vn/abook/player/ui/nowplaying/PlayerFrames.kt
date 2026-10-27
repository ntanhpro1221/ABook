package vn.abook.player.ui.nowplaying

import android.view.Choreographer
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.repeatOnLifecycle
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.conflate
import kotlinx.coroutines.flow.distinctUntilChanged

/** Frame callbacks are needed only for smooth playback while the expanded player is visible. */
internal fun playerFrames(): Flow<Unit> = callbackFlow {
    val clock = Choreographer.getInstance()
    val callback = object : Choreographer.FrameCallback {
        override fun doFrame(frameTimeNanos: Long) {
            trySend(Unit)
            clock.postFrameCallback(this)
        }
    }
    clock.postFrameCallback(callback)
    awaitClose { clock.removeFrameCallback(callback) }
}.conflate()

internal suspend fun samplePlayerClock(
    lifecycle: Lifecycle,
    model: NowPlayingModel,
    expanded: Flow<Boolean>,
    frames: () -> Flow<Unit> = ::playerFrames,
) {
    lifecycle.repeatOnLifecycle(Lifecycle.State.STARTED) {
        combine(model.state, expanded) { state, open -> state.playing && open }
            .distinctUntilChanged().collectLatest { running ->
                model.position.sample()
                if (running) frames().collect { model.position.sample() }
            }
    }
}
