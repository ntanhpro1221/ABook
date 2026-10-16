package vn.abook.player

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

/**
 * Hàng dựng nhạc theo cảnh (soát a47 mục 8): chương đang nghe dựng trước các chương kế dù xếp hàng sau, đổi cuốn thì bỏ việc chưa chạy của cuốn cũ - như `music_nnscene.Builder`.
 */
class SceneQueueTest {
    /** Giữ luồng bận bằng một việc chặn để mọi việc sau xếp hàng, rồi nhả; trả thứ tự chạy. */
    private fun run(setup: (SceneQueue, MutableList<String>) -> Unit): List<String> {
        val queue = SceneQueue("scene-queue-test")
        val order = java.util.Collections.synchronizedList(ArrayList<String>())
        val gate = CountDownLatch(1)
        val started = CountDownLatch(1)
        queue.submit("blocker", 0, 0) { started.countDown(); gate.await(5, TimeUnit.SECONDS) }
        assertTrue(started.await(5, TimeUnit.SECONDS))
        setup(queue, order)
        gate.countDown()
        // Việc cuối cùng của hàng: chờ nó là chờ mọi việc trước đã xong (cùng một luồng, nhỏ tới trước).
        queue.submit("end", 0, Int.MAX_VALUE) { order += "end" }.get(5, TimeUnit.SECONDS)
        return order.toList().filter { it != "end" }
    }

    @Test
    fun theChapterBeingListenedToBuildsBeforeQueuedLaterOnes() {
        val order = run { queue, order ->
            // Đang nghe chương 5: chương 6, 7, 8 xếp trước (khoảng cách 1, 2, 3)...
            queue.submit("b", 6, 1) { order += "6" }
            queue.submit("b", 7, 2) { order += "7" }
            queue.submit("b", 8, 3) { order += "8" }
            // ...rồi người nghe nhảy về chương 3: nó và chương kế (4) vào sau cùng, nhưng chương 3 đi đầu.
            queue.submit("b", 4, 1) { order += "4" }
            queue.submit("b", 3, 0) { order += "3" }
        }
        assertEquals(listOf("3", "6", "4", "7", "8"), order)
    }

    @Test
    fun sameDistanceKeepsFirstComeFirstServed() {
        val order = run { queue, order ->
            queue.submit("b", 1, 1) { order += "x" }
            queue.submit("b", 2, 1) { order += "y" }
            queue.submit("b", 3, 1) { order += "z" }
        }
        assertEquals(listOf("x", "y", "z"), order)
    }

    @Test
    fun anAlreadyQueuedChapterIsNotBuiltTwiceAndIsPulledForwardWhenItBecomesUrgent() {
        var ran = 0
        val order = run { queue, order ->
            queue.submit("b", 9, 3) { ran += 1; order += "9" }
            queue.submit("b", 8, 2) { order += "8" }
            // Người nghe tới chương 9: cùng việc, ưu tiên 0 - đi trước chương 8 và chỉ chạy một lần.
            val first = queue.submit("b", 9, 0) { ran += 1; order += "9-again" }
            val again = queue.submit("b", 9, 0) { ran += 1; order += "9-third" }
            assertTrue(first === again)
        }
        assertEquals(listOf("9", "8"), order)
        assertEquals(1, ran)
    }

    @Test
    fun switchingBookDropsTheOldBooksQueuedJobsAndAChapterOutOfReachIsDropped() {
        val order = run { queue, order ->
            queue.submit("old", 1, 0) { order += "old-1" }
            queue.submit("old", 2, 1) { order += "old-2" }
            queue.submit("new", 1, 1) { order += "new-1" }
            queue.submit("new", 7, 2) { order += "new-7" }
            queue.cancelOthers("new")
            queue.cancelOutside("new", listOf(1, 2, 3))
        }
        assertEquals("cuốn cũ bỏ hết; chương 7 ngoài tầm nghe bỏ", listOf("new-1"), order)
    }
}
