package vn.abook.player.readaloud

import org.junit.Assert.assertEquals
import org.junit.Test

/** Giọng trên máy nhả model sau 3 phút không đọc (soát a69), như máy tính `service.release_idle`. */
class IdleEngineTest {
    private class Rig {
        var now = 1_000L
        var released = 0
        val tasks = ArrayList<Pair<Long, () -> Unit>>()
        val idle = IdleEngine(this, { released++ }, { now }, { delay, task -> tasks.add(now + delay to task) })

        /** Run every check that is due by [at]. */
        fun runUntil(at: Long) {
            now = at
            while (true) {
                val due = tasks.filter { it.first <= now }.minByOrNull { it.first } ?: return
                tasks.remove(due)
                due.second()
            }
        }
    }

    @Test
    fun releasesAfterThreeIdleMinutesOnly() {
        val rig = Rig()
        rig.idle.used()
        rig.runUntil(1_000L + IdleEngine.IDLE_MS / 2)
        rig.idle.used() // read again halfway
        rig.runUntil(1_000L + IdleEngine.IDLE_MS + 1)
        assertEquals("used again: not yet", 0, rig.released)
        rig.runUntil(1_000L + IdleEngine.IDLE_MS / 2 + IdleEngine.IDLE_MS)
        assertEquals(1, rig.released)
        rig.runUntil(rig.now + 10 * IdleEngine.IDLE_MS)
        assertEquals("released once, no more checks", 1, rig.released)
        assertEquals(0, rig.tasks.size)
    }

    @Test
    fun backgroundWorkKeepsTheEngine() {
        val rig = Rig()
        rig.idle.used()
        IdleEngine.holding { rig.runUntil(rig.now + 5 * IdleEngine.IDLE_MS) }
        assertEquals(0, rig.released)
        rig.runUntil(rig.now + IdleEngine.IDLE_MS)
        assertEquals(1, rig.released)
    }

    @Test
    fun anEngineDroppedByItsOwnerIsNotReleasedAgain() {
        val rig = Rig()
        rig.idle.used()
        rig.idle.dropped()
        rig.runUntil(rig.now + 2 * IdleEngine.IDLE_MS)
        assertEquals(0, rig.released)
    }
}
