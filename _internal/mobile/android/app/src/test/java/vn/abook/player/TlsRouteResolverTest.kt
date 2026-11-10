package vn.abook.player

import org.junit.Assert.*
import org.junit.Test
import java.util.Collections
import java.util.concurrent.CountDownLatch
import java.util.concurrent.CyclicBarrier
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger
import java.util.concurrent.atomic.AtomicLong

class TlsRouteResolverTest {
    private val targets = (1..8).map { "10.39.1.$it:47630" }

    /** Đồng hồ giả: hạn chỉ hết khi bài thử vặn kim, máy bận làm luồng chạy trễ bao lâu cũng không đổi kết quả. */
    private class Clock {
        private val nanos = AtomicLong(1_000_000_000_000L)
        fun now() = nanos.get()
        fun advanceMs(ms: Long) { nanos.addAndGet(TimeUnit.MILLISECONDS.toNanos(ms)) }
    }

    @Test fun theEighthLiveRouteIsReachedAfterSevenSlowFailures() {
        val clock = Clock()
        val resolver = TlsRouteResolver(nanoTime = clock::now)
        val attempted = Collections.synchronizedList(mutableListOf<String>())
        try {
            assertEquals(targets.last(), resolver.resolve("last-route", targets) {
                attempted += it
                if (it == targets.last()) true else { clock.advanceMs(600); false } // hai cuộc thử song song, mỗi cuộc treo 1,2 giây
            })
            assertTrue(attempted.contains(targets.last()))
        } finally { resolver.close() }
    }

    @Test fun aTcpKnownLiveLastRouteIsPrioritizedButStillCheckedWithTls() {
        val identity = "tcp-priority-test"
        targets.forEach(Route::markDown)
        Route.markUp(targets.last())
        val attempted = mutableListOf<String>()
        assertEquals(targets.last(), Route.resolve(targets, identity) { attempted += it; it == targets.last() })
        assertEquals(listOf(targets.last()), attempted)
        Route.markDown(targets.last())
    }

    @Test fun concurrentCallersAndImmediateRetryShareOneFailedRound() {
        val resolver = TlsRouteResolver(nanoTime = Clock()::now)
        val callers = Executors.newFixedThreadPool(3)
        val start = CyclicBarrier(3)
        val attempts = AtomicInteger()
        try {
            val jobs = (1..3).map {
                callers.submit(java.util.concurrent.Callable {
                    start.await(30, TimeUnit.SECONDS)
                    resolver.resolve("offline", targets) { attempts.incrementAndGet(); false }
                })
            }
            jobs.forEach { assertNull(it.get(30, TimeUnit.SECONDS)) }
            assertNull(resolver.resolve("offline", targets) { fail("negative cache bypassed"); true })
            assertEquals(8, attempts.get())
        } finally { callers.shutdownNow(); resolver.close() }
    }

    @Test fun slowDnsForOnePeerDoesNotTakeAnotherPeersSlots() {
        val resolver = TlsRouteResolver(probeMs = 30_000)
        val callers = Executors.newSingleThreadExecutor()
        val started = CountDownLatch(2)
        val release = CountDownLatch(1)
        try {
            val slow = callers.submit(java.util.concurrent.Callable {
                resolver.resolve("slow", targets.take(2)) {
                    started.countDown()
                    release.await(30, TimeUnit.SECONDS)
                    false
                }
            })
            assertTrue(started.await(30, TimeUnit.SECONDS))
            assertEquals(targets.last(), resolver.resolve("healthy", listOf(targets.last())) { true })
            release.countDown()
            assertNull(slow.get(30, TimeUnit.SECONDS))
        } finally { release.countDown(); callers.shutdownNow(); resolver.close() }
    }

    @Test fun stuckDnsCannotAccumulateJobsOrDuplicateTheSameProbe() {
        val resolver = TlsRouteResolver(probeMs = 20, failureMs = 0)
        val release = CountDownLatch(1)
        val started = CountDownLatch(2)
        val attempts = AtomicInteger()
        try {
            repeat(3) {
                assertNull(resolver.resolve("stuck", targets) {
                    attempts.incrementAndGet()
                    started.countDown()
                    release.await(60, TimeUnit.SECONDS)
                    false
                })
            }
            assertTrue(started.await(30, TimeUnit.SECONDS)) // hết hạn trước khi luồng kịp chạy thì job vẫn giữ chỗ, chỉ là chưa đếm
            assertEquals(2, attempts.get())
        } finally { release.countDown(); resolver.close() }
    }

    @Test fun networkDiscoveryAndNewCandidatesInvalidateNegativeCache() {
        val resolver = TlsRouteResolver(probeMs = 20, nanoTime = Clock()::now)
        val attempts = AtomicInteger()
        val dead: (String) -> Boolean = { attempts.incrementAndGet(); false }
        try {
            assertNull(resolver.resolve("offline", targets.take(1), dead))
            assertNull(resolver.resolve("offline", targets.take(1), dead))
            assertEquals(1, attempts.get())
            resolver.invalidateAll() // network change
            assertNull(resolver.resolve("offline", targets.take(1), dead))
            assertEquals(2, attempts.get())
            resolver.invalidate("offline") // authenticated discovery
            assertNull(resolver.resolve("offline", targets.take(1), dead))
            assertEquals(3, attempts.get())
            assertNull(resolver.resolve("offline", targets.take(2), dead))
            assertEquals(5, attempts.get())
        } finally { resolver.close() }
    }

    @Test fun theNegativeCacheEndsExactlyWhenItsTimeIsUp() {
        val clock = Clock()
        val resolver = TlsRouteResolver(failureMs = 2000, nanoTime = clock::now)
        val attempts = AtomicInteger()
        val dead: (String) -> Boolean = { attempts.incrementAndGet(); false }
        try {
            assertNull(resolver.resolve("offline", targets.take(1), dead))
            clock.advanceMs(1999)
            assertNull(resolver.resolve("offline", targets.take(1), dead))
            assertEquals(1, attempts.get())
            clock.advanceMs(1)
            assertNull(resolver.resolve("offline", targets.take(1), dead))
            assertEquals(2, attempts.get())
        } finally { resolver.close() }
    }

    @Test fun aPinFailureIsSharedAndDoesNotBecomeAnOrdinaryOfflineResult() {
        val resolver = TlsRouteResolver(probeMs = 20, nanoTime = Clock()::now)
        try {
            repeat(2) {
                try {
                    resolver.resolve("changed-pin", targets.take(1)) { throw Pin.ChangedException(IllegalStateException("wrong pin")) }
                    fail("pin change hidden")
                } catch (_: Pin.ChangedException) { }
            }
        } finally { resolver.close() }
    }

    @Test fun aSuccessfulWaiterGetsTheAddressWithoutCallingAnotherProbe() {
        val resolver = TlsRouteResolver(probeMs = 30_000)
        val caller = Executors.newSingleThreadExecutor()
        val entered = CountDownLatch(1)
        val release = CountDownLatch(1)
        val attempts = AtomicInteger()
        val probe: (String) -> Boolean = {
            attempts.incrementAndGet()
            entered.countDown()
            release.await(30, TimeUnit.SECONDS)
            true
        }
        try {
            val first = caller.submit(java.util.concurrent.Callable { resolver.resolve("waiter-success", targets.take(1), probe) })
            assertTrue(entered.await(30, TimeUnit.SECONDS))
            // The waiter runs on main; release only once it is parked on the shared round, else it would lead a new one.
            val waiter = Thread.currentThread()
            val releaser = Thread {
                while (release.count > 0 && waiter.state != Thread.State.TIMED_WAITING) Thread.yield()
                release.countDown()
            }.apply { isDaemon = true }
            releaser.start()
            try {
                assertEquals(targets.first(), resolver.resolve("waiter-success", targets.take(1), probe))
                assertEquals(targets.first(), first.get(30, TimeUnit.SECONDS))
                assertEquals(1, attempts.get())
            } finally { release.countDown(); releaser.join(TimeUnit.SECONDS.toMillis(30)) }
        } finally { release.countDown(); caller.shutdownNow(); resolver.close() }
    }

}
