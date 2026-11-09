package vn.abook.player

import java.util.concurrent.Executor

/** One pending periodic snapshot; a synchronous event can never be overwritten by older work. */
internal class OrderedCheckpoint<T>(private val executor: Executor, private val writeLock: Any = Any(), private val write: (T) -> Unit) {
    private class Work<T>(val sequence: Long, val value: T, val completed: (T, Result<Unit>) -> Unit)
    private val stateLock = Any()
    private var sequence = 0L
    private var barrier = 0L
    private var pending: Work<T>? = null
    private var scheduled = false

    fun periodic(value: T, completed: (T, Result<Unit>) -> Unit) {
        synchronized(stateLock) {
            pending = Work(++sequence, value, completed)
            if (scheduled) return
            scheduled = true
        }
        executor.execute {
            while (true) {
                val next = synchronized(stateLock) {
                    val next = pending
                    pending = null
                    if (next == null) {
                        scheduled = false
                        return@execute
                    }
                    next
                }
                val outcome = synchronized(writeLock) {
                    if (synchronized(stateLock) { next.sequence > barrier }) runCatching { write(next.value) } else null
                }
                if (outcome != null) next.completed(next.value, outcome)
            }
        }
    }

    /** Pause, seek, chapter and record handoffs keep the existing durable return contract. */
    fun immediate(value: T): Result<Unit> = synchronized(writeLock) {
        synchronized(stateLock) {
            barrier = ++sequence
            pending = null
        }
        runCatching { write(value) }
    }
}
