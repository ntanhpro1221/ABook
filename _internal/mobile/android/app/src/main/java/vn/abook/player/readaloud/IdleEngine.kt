package vn.abook.player.readaloud

import android.os.SystemClock
import java.util.concurrent.Executors
import java.util.concurrent.ScheduledExecutorService
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger

/**
 * Lets go of an on-device voice engine (a few hundred MB of ONNX sessions) once nobody has read with it for [IDLE_MS] (desktop
 * `service.IDLE_SECONDS`, same number; review a69: Supertonic kept the native heap at ~450 MB through an hour of Edge). The next read loads it again.
 *
 * The owner ([SupertonicVoices], [vn.abook.player.vieneu.VieneuVoices]) calls [used] under its own [lock] after loading or reading; the check runs
 * under the same lock, so an engine is never dropped in the middle of a read. Background voice work ([holding]: "Làm trước", audiobook export) keeps
 * every engine, even while it waits for the listener between paragraphs. [later] schedules the check (tests run it by hand).
 */
class IdleEngine(
    private val lock: Any,
    private val release: () -> Unit,
    private val clock: () -> Long = { SystemClock.elapsedRealtime() },
    private val later: (Long, () -> Unit) -> Unit = ::schedule,
) {
    private var last = -1L // when the engine was last used; -1: nothing loaded
    private var pending = false

    /** Under [lock]: the engine was just loaded or read with. */
    fun used() {
        last = clock()
        if (!pending) {
            pending = true
            later(IDLE_MS) { check() }
        }
    }

    /** Under [lock]: the owner dropped the engine itself (module changed, out of memory). */
    fun dropped() {
        last = -1
    }

    internal fun check() {
        synchronized(lock) {
            pending = false
            if (last < 0) return
            val left = IDLE_MS - (clock() - last)
            if (left <= 0 && holds.get() == 0) {
                last = -1
                release()
                return
            }
            pending = true
            later(maxOf(left, IDLE_MS / 6)) { check() }
        }
    }

    companion object {
        const val IDLE_MS = 180_000L
        private val holds = AtomicInteger()
        private val timer: ScheduledExecutorService by lazy {
            Executors.newSingleThreadScheduledExecutor { task -> Thread(task, "abook-engine-idle").apply { isDaemon = true } }
        }

        /** Background voice work: no engine is let go while [block] runs. */
        fun <T> holding(block: () -> T): T {
            holds.incrementAndGet()
            try {
                return block()
            } finally {
                holds.decrementAndGet()
            }
        }

        private fun schedule(delayMs: Long, task: () -> Unit) {
            timer.schedule({ runCatching(task) }, delayMs, TimeUnit.MILLISECONDS)
        }
    }
}
