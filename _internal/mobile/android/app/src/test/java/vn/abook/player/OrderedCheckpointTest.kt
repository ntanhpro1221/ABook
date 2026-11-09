package vn.abook.player

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.concurrent.Executor

class OrderedCheckpointTest {
    private class Queue : Executor {
        val tasks = mutableListOf<Runnable>()
        override fun execute(command: Runnable) { tasks += command }
        fun run() { tasks.removeAt(0).run() }
    }

    @Test fun eventSupersedesQueuedPeriodicPosition() {
        val queue = Queue()
        val writes = mutableListOf<Int>()
        val saver = OrderedCheckpoint<Int>(queue) { writes += it }
        saver.periodic(5) { _, _ -> }
        assertTrue(saver.immediate(9).isSuccess)
        queue.run()
        assertEquals(listOf(9), writes)
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
        saver.periodic(1) { _, result -> outcomes += result.isSuccess }
        queue.run()
        saver.periodic(2) { _, result -> outcomes += result.isSuccess }
        queue.run()
        assertEquals(listOf(false, true), outcomes)
    }

    @Test fun offeringAPeriodicPositionNeverWaitsForDisk() {
        val queue = Queue()
        val entered = java.util.concurrent.CountDownLatch(1)
        val release = java.util.concurrent.CountDownLatch(1)
        val offered = java.util.concurrent.CountDownLatch(1)
        val writes = java.util.Collections.synchronizedList(mutableListOf<Int>())
        val saver = OrderedCheckpoint<Int>(queue) {
            if (it == 1) { entered.countDown(); release.await() }
            writes += it
        }
        saver.periodic(1) { _, _ -> }
        val worker = Thread { queue.run() }.apply { start() }
        var producer: Thread? = null
        try {
            assertTrue(entered.await(5, java.util.concurrent.TimeUnit.SECONDS))
            producer = Thread { saver.periodic(2) { _, _ -> }; offered.countDown() }.apply { start() }
            assertTrue("offering a snapshot must not acquire the disk lock", offered.await(5, java.util.concurrent.TimeUnit.SECONDS))
        } finally {
            release.countDown()
            producer?.join(5000)
            worker.join(5000)
        }
        assertEquals(listOf(1, 2), writes)
    }

    @Test fun usesTheOwnerMonitorForPeriodicAndReentrantImmediateWrites() {
        val queue = Queue()
        val store = Any()
        val writes = mutableListOf<Int>()
        val saver = OrderedCheckpoint<Int>(queue, store) {
            assertTrue("the write must participate in Store's transaction monitor", Thread.holdsLock(store))
            writes += it
        }
        synchronized(store) {
            assertTrue(saver.immediate(1).isSuccess)
        }
        saver.periodic(2) { _, _ -> }
        queue.run()
        assertEquals(listOf(1, 2), writes)
    }
}
