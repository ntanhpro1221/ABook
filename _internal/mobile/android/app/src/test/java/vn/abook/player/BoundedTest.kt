package vn.abook.player

import java.util.concurrent.atomic.AtomicInteger
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** Việc song song có giới hạn (soát a101 F2): thứ tự, mức song song, trần thời gian. */
class BoundedTest {
    @Test
    fun results_keep_the_order_of_the_items_whatever_finishes_first() {
        val out = Bounded.map(listOf(40L, 5L, 20L, 1L), 4, 10_000) { delay, _ ->
            Thread.sleep(delay)
            delay
        }
        assertEquals(listOf(40L, 5L, 20L, 1L), out)
    }

    @Test
    fun never_more_than_the_limit_at_once_and_faster_than_one_after_another() {
        val running = AtomicInteger()
        val peak = AtomicInteger()
        val started = System.nanoTime()
        Bounded.map((1..8).toList(), 4, 10_000) { _, _ ->
            peak.accumulateAndGet(running.incrementAndGet(), ::maxOf)
            Thread.sleep(100)
            running.decrementAndGet()
        }
        val tookMs = (System.nanoTime() - started) / 1_000_000
        assertTrue("peak ${peak.get()}", peak.get() in 2..4)
        assertTrue("took $tookMs ms: 8 x 100 ms in one line would be 800", tookMs < 600)
    }

    @Test
    fun past_the_budget_the_remaining_items_are_told_not_to_use_the_network() {
        val asked = AtomicInteger()
        val out = Bounded.map((1..6).toList(), 1, 120) { _, expired ->
            if (!expired()) {
                asked.incrementAndGet()
                Thread.sleep(80)
            }
            expired()
        }
        assertEquals("every item still answers", 6, out.size)
        assertTrue("the first ones ran, the last ones were cut: ${asked.get()}", asked.get() in 2..4)
        assertFalse(out.first())
        assertTrue(out.last())
    }

    @Test
    fun an_error_in_one_item_surfaces_as_that_error() {
        val error = runCatching { Bounded.map(listOf(1, 2, 3), 3, 1000) { item, _ -> if (item == 2) throw IllegalStateException("hai") else item } }.exceptionOrNull()
        assertTrue(error is IllegalStateException)
        assertEquals("hai", error!!.message)
    }

    @Test
    fun an_empty_list_answers_at_once() {
        assertEquals(emptyList<Int>(), Bounded.map(emptyList<Int>(), 4, 1000) { item, _ -> item })
    }
}
