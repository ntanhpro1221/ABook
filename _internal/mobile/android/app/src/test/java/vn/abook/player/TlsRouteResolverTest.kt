package vn.abook.player

import org.junit.Assert.*
import org.junit.Test
import java.util.Collections
import java.util.concurrent.CountDownLatch
import java.util.concurrent.CyclicBarrier
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger

class TlsRouteResolverTest {
    private val targets = (1..8).map { "10.39.1.$it:47630" }

    @Test fun theEighthLiveRouteIsReachedAfterSevenSlowFailures() {
        val resolver = TlsRouteResolver()
        val attempted = Collections.synchronizedList(mutableListOf<String>())
        try {
            assertEquals(targets.last(), resolver.resolve("last-route", targets) {
                attempted += it
                if (it == targets.last()) true else { Thread.sleep(1200); false }
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
        val resolver = TlsRouteResolver()
        val callers = Executors.newFixedThreadPool(3)
        val start = CyclicBarrier(3)
        val attempts = AtomicInteger()
        try {
            val jobs = (1..3).map {
                callers.submit(java.util.concurrent.Callable {
                    start.await(2, TimeUnit.SECONDS)
                    resolver.resolve("offline", targets) { attempts.incrementAndGet(); Thread.sleep(20); false }
                })
            }
            jobs.forEach { assertNull(it.get(3, TimeUnit.SECONDS)) }
            assertNull(resolver.resolve("offline", targets) { fail("negative cache bypassed"); true })
            assertEquals(8, attempts.get())
        } finally { callers.shutdownNow(); resolver.close() }
    }

    @Test fun slowDnsForOnePeerDoesNotTakeAnotherPeersSlots() {
        val resolver = TlsRouteResolver(probeMs = 100)
        val callers = Executors.newSingleThreadExecutor()
        val started = CountDownLatch(2)
        val release = CountDownLatch(1)
        try {
            val slow = callers.submit(java.util.concurrent.Callable {
                resolver.resolve("slow", targets.take(2)) {
                    started.countDown()
                    release.await(2, TimeUnit.SECONDS)
                    false
                }
            })
            assertTrue(started.await(1, TimeUnit.SECONDS))
            assertEquals(targets.last(), resolver.resolve("healthy", listOf(targets.last())) { true })
            release.countDown()
            assertNull(slow.get(1, TimeUnit.SECONDS))
        } finally { release.countDown(); callers.shutdownNow(); resolver.close() }
    }

    @Test fun stuckDnsCannotAccumulateJobsOrDuplicateTheSameProbe() {
        val resolver = TlsRouteResolver(probeMs = 20, failureMs = 0)
        val release = CountDownLatch(1)
        val attempts = AtomicInteger()
        try {
            repeat(3) {
                assertNull(resolver.resolve("stuck", targets) {
                    attempts.incrementAndGet()
                    release.await(2, TimeUnit.SECONDS)
                    false
                })
            }
            assertEquals(2, attempts.get())
        } finally { release.countDown(); resolver.close() }
    }

    @Test fun networkDiscoveryAndNewCandidatesInvalidateNegativeCache() {
        val resolver = TlsRouteResolver(probeMs = 20)
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

    @Test fun aPinFailureIsSharedAndDoesNotBecomeAnOrdinaryOfflineResult() {
        val resolver = TlsRouteResolver(probeMs = 20)
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
        val resolver = TlsRouteResolver(probeMs = 100)
        val caller = Executors.newSingleThreadExecutor()
        val entered = CountDownLatch(1)
        val release = CountDownLatch(1)
        val attempts = AtomicInteger()
        val probe: (String) -> Boolean = {
            attempts.incrementAndGet()
            entered.countDown()
            release.await(1, TimeUnit.SECONDS)
            true
        }
        try {
            val first = caller.submit(java.util.concurrent.Callable { resolver.resolve("waiter-success", targets.take(1), probe) })
            assertTrue(entered.await(1, TimeUnit.SECONDS))
            // The waiter runs on main; a short releaser is the fourth and last test thread.
            val releaser = Thread { Thread.sleep(10); release.countDown() }
            releaser.start()
            try {
                assertEquals(targets.first(), resolver.resolve("waiter-success", targets.take(1), probe))
                assertEquals(targets.first(), first.get(1, TimeUnit.SECONDS))
                assertEquals(1, attempts.get())
            } finally { releaser.join(1000) }
        } finally { release.countDown(); caller.shutdownNow(); resolver.close() }
    }

}
