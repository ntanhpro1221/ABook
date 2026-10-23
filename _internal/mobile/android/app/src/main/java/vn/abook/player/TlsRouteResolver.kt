package vn.abook.player

import java.util.concurrent.CompletableFuture
import java.util.concurrent.ExecutionException
import java.util.concurrent.ExecutorCompletionService
import java.util.concurrent.Executors
import java.util.concurrent.Future
import java.util.concurrent.TimeUnit

/** Single-flight by pinned identity. Two pending I/O jobs per peer, no shared DNS queue between peers. */
internal class TlsRouteResolver(private val probeMs: Long = 1500, private val failureMs: Long = 2000) {
    private class Peer {
        val pool = Executors.newFixedThreadPool(2) { task -> Thread(task, "peer-tls").apply { isDaemon = true } }
        val pending = mutableMapOf<Future<String?>, String>()
        var round: CompletableFuture<String?>? = null
        var failedAt = 0L
        var failedTargets = emptySet<String>()
        var failure: Throwable? = null
        var cursor = 0
    }
    private val lock = Any()
    private val peers = linkedMapOf<String, Peer>()

    fun invalidate(identity: String) = synchronized(lock) { peers[identity]?.failedAt = 0L }
    fun invalidateAll() = synchronized(lock) { peers.values.forEach { it.failedAt = 0L } }

    internal fun close() = synchronized(lock) {
        peers.values.forEach { it.pool.shutdown() }
        peers.clear()
    }

    fun resolve(identity: String, candidates: List<String>, probe: (String) -> Boolean): String? {
        val targets = PeerAddresses.candidates(candidates)
        if (targets.isEmpty()) return null
        val budget = probeMs * ((targets.size + 1) / 2) + (if (targets.size > 1) minOf(probeMs, 150L) else 0L)
        val peer: Peer
        val shared: CompletableFuture<String?>
        val leader: Boolean
        synchronized(lock) {
            if (!peers.containsKey(identity) && peers.size >= 32) {
                val idle = peers.entries.firstOrNull { it.value.round == null && it.value.pending.keys.all { job -> job.isDone } }
                    ?: throw java.io.IOException("Bộ chọn đường đang bận; bạn hãy thử lại")
                idle.value.pool.shutdown()
                peers.remove(idle.key)
            }
            peer = peers.getOrPut(identity) { Peer() }
            if (peer.failedAt != 0L && System.nanoTime() - peer.failedAt < TimeUnit.MILLISECONDS.toNanos(failureMs) && peer.failedTargets == targets.toSet()) {
                peer.failure?.let { throw it }
                return null
            }
            leader = peer.round == null
            shared = peer.round ?: CompletableFuture<String?>().also { peer.round = it }
        }
        if (!leader) return try { shared.get(budget + probeMs, TimeUnit.MILLISECONDS) }
            catch (error: ExecutionException) { throw error.cause ?: error }
        try {
            val result = select(peer, targets, budget, probe)
            synchronized(lock) {
                peer.failedAt = if (result == null) System.nanoTime() else 0L
                peer.failedTargets = targets.toSet()
                peer.failure = null
                peer.round = null
                shared.complete(result)
            }
            return result
        } catch (error: Throwable) {
            synchronized(lock) {
                peer.failedAt = System.nanoTime()
                peer.failedTargets = targets.toSet()
                peer.failure = error
                peer.round = null
                shared.completeExceptionally(error)
            }
            throw error
        }
    }

    private fun select(peer: Peer, targets: List<String>, budget: Long, probe: (String) -> Boolean): String? {
        val deadline = System.nanoTime() + TimeUnit.MILLISECONDS.toNanos(budget)
        var firstDeadline = System.nanoTime() + TimeUnit.MILLISECONDS.toNanos(minOf(probeMs, 150L))
        val start = peer.cursor % targets.size
        peer.pending.keys.removeAll { it.isDone }
        val remaining = (targets.drop(start) + targets.take(start)).filter { it !in peer.pending.values }.toMutableList()
        val completion = ExecutorCompletionService<String?>(peer.pool)
        val jobs = mutableSetOf<Future<String?>>()
        var mismatch: Throwable? = null
        fun submit() {
            val target = remaining.removeAt(0)
            val job = completion.submit(java.util.concurrent.Callable { if (probe(target)) target else null })
            jobs += job
            peer.pending[job] = target
            peer.cursor = (targets.indexOf(target) + 1) % targets.size
        }
        // Never cancel a running future: interruption cannot reliably stop DNS; keep its slot occupied.
        if (remaining.isNotEmpty() && peer.pending.size < 2) submit()
        while (jobs.isNotEmpty() || remaining.isNotEmpty()) {
            peer.pending.keys.removeAll { it.isDone && it !in jobs }
            val now = System.nanoTime()
            val preferred = jobs.size == 1 && remaining.size == targets.size - 1 && now < firstDeadline
            while (remaining.isNotEmpty() && peer.pending.size < (if (preferred) 1 else 2)) submit()
            if (jobs.isEmpty()) break
            val until = if (preferred) minOf(deadline, firstDeadline) else deadline
            val job = completion.poll((until - now).coerceAtLeast(0), TimeUnit.NANOSECONDS)
            if (job != null) {
                jobs.remove(job)
                peer.pending.remove(job)
                try {
                    job.get()?.let { peer.cursor = 0; return it }
                } catch (error: ExecutionException) {
                    val cause = error.cause
                    if (cause is Pin.ChangedException) mismatch = cause
                }
                firstDeadline = 0L
            }
            if (System.nanoTime() >= deadline) break
        }
        mismatch?.let { throw it }
        return null
    }
}
