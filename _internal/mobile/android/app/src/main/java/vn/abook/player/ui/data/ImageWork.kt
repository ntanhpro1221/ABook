package vn.abook.player.ui.data

import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.ProduceStateScope
import androidx.compose.runtime.RememberObserver
import androidx.compose.runtime.State
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import kotlinx.coroutines.CoroutineScope
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.atomic.AtomicBoolean

/** Tracks image producers, including publishing pixels back to Compose.
 * A Compose IdlingResource observes this in JVM snapshots; no dependency on test APIs in the app.
 * Every ticket is released exactly once: on success, failure, cancellation, or synchronously when its composition
 * forgets the producer. The last one matters because a cancelled coroutine runs its `finally` only when its
 * dispatcher resumes it, and a disposed host (a finished test, a destroyed activity) may never do that.
 */
object ImageWork {
    class Ticket internal constructor(val source: String) {
        private val open = AtomicBoolean(true)
        fun release() { if (open.compareAndSet(true, false)) live.remove(this) }
    }

    private val live = ConcurrentHashMap<Ticket, String>()
    /** Tests name each producer by its call site; production never pays for a stack trace. */
    @Volatile var traceSources = false

    val isIdle: Boolean get() = live.isEmpty()
    val pendingSources: List<String> get() = live.values.sorted()
    val diagnostic: String get() = "${live.size} image producers still loading/decoding/publishing: $pendingSources"

    fun begin(source: String): Ticket = Ticket(source).also { live[it] = source }

    /** Releases every open ticket and returns their sources: a test host proves nothing leaked into the next test. */
    fun drain(): List<String> = live.keys.toList().map { ticket -> ticket.source.also { ticket.release() } }.sorted()

    fun callerSource(): String = if (!traceSources) "image producer" else
        Throwable().stackTrace.firstOrNull { it.className.startsWith("vn.abook.") && it.fileName != "ImageWork.kt" }
            ?.let { "${it.fileName}:${it.lineNumber}" } ?: "image producer"
}

/** One producer's work, owned by the composition: forgetting it releases whatever is still open. */
class ImageWorkScope(private val source: String) : RememberObserver {
    private val open = ConcurrentHashMap.newKeySet<ImageWork.Ticket>()
    @Volatile private var closed = false

    suspend fun <T> track(block: suspend () -> T): T {
        val ticket = ImageWork.begin(source)
        open += ticket
        if (closed) ticket.release()
        try { return block() } finally { ticket.release(); open -= ticket }
    }

    override fun onRemembered() {}
    override fun onForgotten() = close()
    override fun onAbandoned() = close()
    private fun close() { closed = true; open.forEach { it.release() }; open.clear() }
}

/** Finite image requests inside a long-lived collector: `rememberImageWork().track { load() }` around each request. */
@Composable
fun rememberImageWork(vararg keys: Any?): ImageWorkScope = remember(*keys) { ImageWorkScope(ImageWork.callerSource()) }

/** Image effects must include their final state assignment inside the tracked scope. */
@Composable
fun ImageLaunchedEffect(vararg keys: Any?, block: suspend CoroutineScope.() -> Unit) {
    val work = remember(*keys) { ImageWorkScope(ImageWork.callerSource()) }
    LaunchedEffect(work) { work.track { block() } }
}

@Composable
fun <T> produceImageState(initialValue: T, vararg keys: Any?, producer: suspend ProduceStateScope<T>.() -> Unit): State<T> {
    val work = remember(*keys) { ImageWorkScope(ImageWork.callerSource()) }
    return produceState(initialValue, work) { work.track { producer() } }
}
