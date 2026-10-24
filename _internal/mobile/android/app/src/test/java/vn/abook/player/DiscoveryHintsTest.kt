package vn.abook.player

import org.junit.Assert.*
import org.junit.Test
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger

class DiscoveryHintsTest {
    @Test fun slowPinnedHintsCannotConsumeTheReceiveWindowOfANewPeer() {
        val verified = mutableListOf<String>()
        val hints = DiscoveryHints { hint -> verified += hint.host }
        assertTrue(hints.add("192.168.1.1", 47630, "known-pin"))
        assertTrue(hints.add("192.168.1.2", 47630, "known-pin"))
        assertTrue(hints.add("192.168.1.3", 47630, "new-pin"))
        assertEquals("No TLS or other verifier I/O before the UDP receive window closes", emptyList<String>(), verified)
    }

    @Test fun twoStalledVerifiersHaveBoundedAdmissionAndDoNotLoseNewDiscovery() {
        DiscoveryAdmission().use { admission ->
            val started = CountDownLatch(2)
            val release = CountDownLatch(1)
            val third = CountDownLatch(1)
            val hints = DiscoveryHints(admission) { hint ->
                if (hint.host.endsWith(".3")) third.countDown()
                else { started.countDown(); release.await(2, TimeUnit.SECONDS) }
            }
            try {
                for (i in 1..3) assertTrue(hints.add("192.168.1.$i", 47630, "pin"))
                assertEquals(2L, started.count) // no TLS while UDP collection is open
                hints.finish()
                assertTrue(started.await(1, TimeUnit.SECONDS))
                assertEquals(1L, third.count)
                release.countDown()
                assertTrue(third.await(1, TimeUnit.SECONDS))
                hints.finish() // idempotent
                assertFalse(hints.add("192.168.1.4", 47630, "pin"))
            } finally { release.countDown() }
        }
    }

    @Test fun floodHasAtMostTwoRunningIoJobsAndSixteenQueued() {
        DiscoveryAdmission().use { admission ->
            val started = CountDownLatch(2)
            val release = CountDownLatch(1)
            val done = CountDownLatch(18)
            val active = AtomicInteger()
            val peak = AtomicInteger()
            val task = {
                val count = active.incrementAndGet()
                peak.accumulateAndGet(count, ::maxOf)
                started.countDown()
                try { release.await(2, TimeUnit.SECONDS) }
                finally { active.decrementAndGet(); done.countDown() }
                Unit
            }
            try {
                repeat(2) { assertTrue(admission.submit(task)) }
                assertTrue(started.await(1, TimeUnit.SECONDS))
                repeat(16) { assertTrue(admission.submit(task)) }
                repeat(100) { assertFalse(admission.submit(task)) }
                assertEquals(2, peak.get())
                release.countDown()
                assertTrue(done.await(1, TimeUnit.SECONDS))
                assertTrue(peak.get() <= 2)
            } finally { release.countDown() }
        }
    }

    @Test fun udpHintCollectionIsCappedAndDeduplicated() {
        val hints = DiscoveryHints { fail("must not verify while receiving") }
        repeat(64) { assertTrue(hints.add("10.0.0.${it + 1}", 47630, "pin")) }
        assertFalse(hints.add("10.0.0.1", 47630, "pin"))
        assertFalse(hints.add("10.0.0.65", 47630, "pin"))
    }
}
