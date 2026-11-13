package vn.abook.player

import java.util.concurrent.Executor

/**
 * Ordered place writer. Callers hand over an owned snapshot and never wait for the disk: event snapshots
 * (pause, seek, chapter, record handoff) are written in the order they were offered, and a periodic snapshot only
 * waits while nothing newer is queued - any newer snapshot makes it obsolete. One drain runs at a time on [executor].
 */
internal class OrderedCheckpoint<T>(private val executor: Executor, private val writeLock: Any = Any(), private val write: (T) -> Unit) {
    private class Work<T>(val value: T, val periodic: Boolean, val completed: (T, Result<Unit>) -> Unit)
    private val stateLock = Object()
    private val queue = ArrayDeque<Work<T>>()
    private var scheduled = false

    fun periodic(value: T, completed: (T, Result<Unit>) -> Unit) = offer(Work(value, true, completed))

    /** An event snapshot: always written, after every snapshot offered before it. */
    fun immediate(value: T, completed: (T, Result<Unit>) -> Unit) = offer(Work(value, false, completed))

    private fun offer(work: Work<T>) {
        synchronized(stateLock) {
            queue.removeAll { it.periodic }
            queue.addLast(work)
            if (scheduled) return
            scheduled = true
        }
        executor.execute(::drain)
    }

    private fun drain() {
        while (true) {
            val next = synchronized(stateLock) {
                queue.removeFirstOrNull() ?: run {
                    scheduled = false
                    stateLock.notifyAll()
                    return
                }
            }
            val outcome = synchronized(writeLock) { runCatching { write(next.value) } }
            next.completed(next.value, outcome)
        }
    }

    /**
     * Waits until every snapshot offered before the call is written (background callers, tests). Never call on main or while
     * holding [writeLock]: the writer needs that monitor. Returns false when [timeoutMs] passes first.
     */
    fun flush(timeoutMs: Long): Boolean {
        val deadline = System.nanoTime() + timeoutMs * 1_000_000
        synchronized(stateLock) {
            while (scheduled) {
                val left = (deadline - System.nanoTime()) / 1_000_000
                if (left <= 0) return false
                stateLock.wait(left)
            }
        }
        return true
    }
}
