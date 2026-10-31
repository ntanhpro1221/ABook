package vn.abook.player

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import vn.abook.player.net.HostWait
import vn.abook.player.readaloud.ClipReader
import vn.abook.player.ui.voice.VoiceStuck

/** Chốt chặn đệm của trình phát: 215 giây chờ âm thanh thì báo lỗi, với đồng hồ giả. */
class BufferingGuardTest {
    private class Clock {
        var now = 0L
        private val tasks = mutableListOf<Pair<Long, Runnable>>()
        fun schedule(delay: Long, task: Runnable) { tasks += (now + delay) to task }
        fun cancel(task: Runnable) { tasks.removeAll { it.second === task } }
        val pending: Int get() = tasks.size
        fun advance(ms: Long) {
            now += ms
            val due = tasks.filter { it.first <= now }
            tasks.removeAll(due)
            due.forEach { it.second.run() }
        }
    }

    private fun guard(clock: Clock, onStall: () -> Unit) = BufferingGuard(schedule = clock::schedule, cancel = clock::cancel, onStall = onStall)

    @Test fun theLimitIsTwoSpeechAttemptsPlusFifteenSeconds() {
        assertEquals(215_000L, HostWait.STALL_MS)
    }

    @Test fun waitingTwoHundredFifteenSecondsRaisesTheError() {
        val clock = Clock()
        var stalls = 0
        val guard = guard(clock) { stalls++ }
        guard.observe(true)
        clock.advance(214_999)
        assertEquals(0, stalls)
        clock.advance(1)
        assertEquals(1, stalls)
        clock.advance(600_000)
        assertEquals("một lần, không lặp", 1, stalls)
    }

    @Test fun stateEventsWhileStillWaitingDoNotRestartTheClock() {
        val clock = Clock()
        var stalls = 0
        val guard = guard(clock) { stalls++ }
        guard.observe(true)
        repeat(20) { clock.advance(10_000); guard.observe(true) } // tick, state, state... 200 giây
        assertEquals(0, stalls)
        clock.advance(15_000)
        assertEquals(1, stalls)
    }

    @Test fun soundArrivingClearsTheClockAndTheNextWaitStartsFresh() {
        val clock = Clock()
        var stalls = 0
        val guard = guard(clock) { stalls++ }
        guard.observe(true)
        clock.advance(200_000)
        guard.observe(false)
        assertEquals("hạn đã gỡ", 0, clock.pending)
        clock.advance(100_000)
        assertEquals(0, stalls)
        guard.observe(true)
        clock.advance(214_000)
        assertEquals(0, stalls)
        clock.advance(1_000)
        assertEquals(1, stalls)
    }

    @Test fun afterAFiredStallTheNextWaitIsGuardedAgain() {
        val clock = Clock()
        var stalls = 0
        val guard = guard(clock) { stalls++ }
        guard.observe(true)
        clock.advance(215_000)
        guard.observe(false) // báo lỗi, đã dừng
        guard.observe(true) // người nghe bấm "Thử lại"
        clock.advance(215_000)
        assertEquals(2, stalls)
    }

    @Test fun theErrorReadsLikeTheFailedSourceOfTheSameKind() {
        val reading = BufferingGuard.message(inText = true, streamed = false, holder = "")
        assertEquals(ClipReader.NO_USABLE_VOICE, reading)
        assertTrue("giao diện nhận ra là giọng bị kẹt, kèm nút đổi giọng", VoiceStuck.isStuck(reading))
        val streamed = BufferingGuard.message(inText = false, streamed = true, holder = "máy tính Lecoo")
        assertEquals(NetErrors.message(NetErrors.Kind.TIMEOUT, "máy tính Lecoo"), streamed)
        assertEquals(BufferingGuard.PLAY_FAILED, BufferingGuard.message(inText = false, streamed = false, holder = ""))
    }
}
