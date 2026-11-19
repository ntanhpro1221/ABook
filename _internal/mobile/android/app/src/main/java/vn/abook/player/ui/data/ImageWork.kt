package vn.abook.player.ui.data

import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.ProduceStateScope
import androidx.compose.runtime.State
import androidx.compose.runtime.produceState
import kotlinx.coroutines.CoroutineScope
import java.util.concurrent.atomic.AtomicInteger

/** Tracks the whole image producer, including publishing pixels back to Compose.
 * A Compose IdlingResource observes this in JVM snapshots; no dependency on test APIs in the app.
 * Enter before dispatching work, and leave on success, failure or cancellation.
 */
object ImageWork {
    private val pending = AtomicInteger()
    val isIdle: Boolean get() = pending.get() == 0
    val diagnostic: String get() = "${pending.get()} image producers still loading/decoding/publishing"

    suspend fun <T> track(block: suspend () -> T): T {
        pending.incrementAndGet()
        try { return block() } finally { pending.decrementAndGet() }
    }
}

/** Image effects must include their final state assignment inside the tracked scope. */
@Composable
fun ImageLaunchedEffect(vararg keys: Any?, block: suspend CoroutineScope.() -> Unit) {
    LaunchedEffect(*keys) { ImageWork.track { block() } }
}

@Composable
fun <T> produceImageState(initialValue: T, vararg keys: Any?, producer: suspend ProduceStateScope<T>.() -> Unit): State<T> =
    produceState(initialValue, *keys) { ImageWork.track { producer() } }
