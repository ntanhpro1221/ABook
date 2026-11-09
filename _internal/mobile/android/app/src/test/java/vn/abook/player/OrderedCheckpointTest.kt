package vn.abook.player

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.concurrent.CountDownLatch
import java.util.concurrent.Executor
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

class OrderedCheckpointTest {
    private class Queue : Executor {
        val tasks = mutableListOf<Runnable>()
        override fun execute(command: Runnable) { tasks += command }
        fun run() { tasks.removeAt(0).run() }
    }

    @Test fun anEventNeverWritesOnTheCallingThread() {
        val queue = Queue()
        val writes = mutableListOf<Int>()
        val saver = OrderedCheckpoint<Int>(queue) { writes += it }
        saver.immediate(9) { _, _ -> }
        assertEquals("pause/seek hand the snapshot over; the main thread does no disk work", emptyList<Int>(), writes)
        queue.run()
        assertEquals(listOf(9), writes)
    }

    @Test fun eventSupersedesQueuedPeriodicPosition() {
        val queue = Queue()
        val writes = mutableListOf<Int>()
        val saver = OrderedCheckpoint<Int>(queue) { writes += it }
        saver.periodic(5) { _, _ -> }
        saver.immediate(9) { _, _ -> }
        queue.run()
        assertEquals(listOf(9), writes)
    }

    @Test fun eventsAreWrittenInOrderAndNoneIsDropped() {
        val queue = Queue()
        val writes = mutableListOf<Int>()
        val saver = OrderedCheckpoint<Int>(queue) { writes += it }
        saver.immediate(1) { _, _ -> }
        saver.immediate(2) { _, _ -> }
        saver.periodic(3) { _, _ -> }
        saver.immediate(4) { _, _ -> }
        saver.periodic(5) { _, _ -> }
        assertEquals(1, queue.tasks.size)
        queue.run()
        assertEquals(listOf(1, 2, 4, 5), writes)
    }

    @Test fun slowDiskCoalescesWithoutAnUnboundedQueueAndReschedulesAfterDrain() {
        val queue = Queue()
        val writes = mutableListOf<Int>()
        val saver = OrderedCheckpoint<Int>(queue) { writes += it }
        repeat(100) { saver.periodic(it) { _, _ -> } }
        assertEquals(1, queue.tasks.size)
        queue.run()
        assertEquals(listOf(99), writes)
        saver.periodic(101) { _, _ -> }
        queue.run()
        assertEquals(listOf(99, 101), writes)
    }

    @Test fun failureIsReportedAndTheNextCheckpointStillRuns() {
        val queue = Queue()
        val outcomes = mutableListOf<Boolean>()
        val saver = OrderedCheckpoint<Int>(queue) { check(it != 1) }
        saver.immediate(1) { _, result -> outcomes += result.isSuccess }
        queue.run()
        saver.periodic(2) { _, result -> outcomes += result.isSuccess }
        queue.run()
        assertEquals(listOf(false, true), outcomes)
    }

    @Test fun offeringNeverWaitsForDisk() {
        val queue = Queue()
        val entered = CountDownLatch(1)
        val release = CountDownLatch(1)
        val offered = CountDownLatch(2)
        val writes = java.util.Collections.synchronizedList(mutableListOf<Int>())
        val store = Any()
        val saver = OrderedCheckpoint<Int>(queue, store) {
            if (it == 1) { entered.countDown(); release.await() }
            writes += it
        }
        saver.periodic(1) { _, _ -> }
        val worker = Thread { queue.run() }.apply { start() }
        var producer: Thread? = null
        try {
            assertTrue(entered.await(5, TimeUnit.SECONDS))
            producer = Thread {
                saver.periodic(2) { _, _ -> }
                offered.countDown()
                saver.immediate(3) { _, _ -> }
                offered.countDown()
            }.apply { start() }
            assertTrue("offering a snapshot must not acquire the disk lock", offered.await(5, TimeUnit.SECONDS))
        } finally {
            release.countDown()
            producer?.join(5000)
            worker.join(5000)
        }
        assertEquals(listOf(1, 3), writes)
    }

    @Test fun writesHoldTheOwnerMonitorAndAnOfferUnderItDoesNotWriteInline() {
        val queue = Queue()
        val store = Any()
        val writes = mutableListOf<Int>()
        val saver = OrderedCheckpoint<Int>(queue, store) {
            assertTrue("the write must participate in Store's transaction monitor", Thread.holdsLock(store))
            writes += it
        }
        synchronized(store) { saver.immediate(1) { _, _ -> } }
        assertEquals(emptyList<Int>(), writes)
        saver.periodic(2) { _, _ -> }
        queue.run()
        assertEquals(listOf(1, 2), writes)
    }

    @Test fun flushWaitsForEveryOfferedEventAndTimesOutOnAStuckDisk() {
        val pool = Executors.newSingleThreadExecutor()
        try {
            val release = CountDownLatch(1)
            val writes = java.util.Collections.synchronizedList(mutableListOf<Int>())
            val saver = OrderedCheckpoint<Int>(pool) {
                if (it == 1) release.await()
                writes += it
            }
            saver.immediate(1) { _, _ -> }
            saver.immediate(2) { _, _ -> }
            assertFalse(saver.flush(50))
            release.countDown()
            assertTrue(saver.flush(5_000))
            assertEquals(listOf(1, 2), writes)
        } finally {
            pool.shutdownNow()
        }
    }
}
