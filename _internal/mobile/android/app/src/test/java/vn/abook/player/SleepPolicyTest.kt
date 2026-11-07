package vn.abook.player

import org.junit.Assert.*
import org.junit.Test

class SleepPolicyTest {
    private val hour = 3_600_000L
    private fun asleep() = SleepPolicy().apply { screen(false, 1000L) }
    private fun still(policy: SleepPolicy, end: Long) {
        repeat(4) { index ->
            val start = end - (4 - index) * SleepPolicy.WINDOW_MS
            policy.motionWindow(start, start + SleepPolicy.WINDOW_MS, 0.01)
        }
    }

    @Test fun usingAnotherAppWithTheScreenOnNeverArmsEvenAfterThreeHours() {
        val p = SleepPolicy()
        still(p, 3 * hour)
        assertFalse(p.allows(3 * hour, 2 * hour, true, 0))
        assertFalse(p.allows(3 * hour, 2 * hour, false, 0))
    }

    @Test fun safetyRequiresTheWholeIdleIntervalWithTheScreenOff() {
        val p = asleep()
        val now = 2 * hour + 1000
        still(p, now)
        assertFalse(p.allows(now - 1, 2 * hour, true, 0))
        assertTrue(p.allows(now, 2 * hour, true, 0))
        p.screen(true, now)
        p.screen(false, now + 1000)
        still(p, now + 121_000)
        assertFalse(p.allows(now + 121_000, 2 * hour, true, 0))
    }

    @Test fun missingSensorUsesScreenOffAndNoInteractionButMissingSamplesDoNotProveStillness() {
        val p = asleep()
        assertTrue(p.allows(2 * hour + 1000, 2 * hour, false, 0))
        assertFalse(p.allows(2 * hour + 1000, 2 * hour, true, 0))
        still(p, 2 * hour + 1000)
        assertFalse(p.allows(2 * hour + 40_000, 2 * hour, true, 0))
    }

    @Test fun nightScheduleWaitsForFourContinuousStillWindows() {
        val p = asleep()
        repeat(3) { i -> p.motionWindow(1000 + i * 30_000L, 31_000 + i * 30_000L, 0.01) }
        assertFalse(p.allows(121_000, SleepPolicy.NIGHT_IDLE_MS, true, 0))
        p.motionWindow(91_000, 121_000, 0.01)
        assertTrue(p.allows(121_000, SleepPolicy.NIGHT_IDLE_MS, true, 0))
        p.motionWindow(121_000, 151_000, 0.2)
        assertFalse(p.allows(151_000, SleepPolicy.NIGHT_IDLE_MS, true, 0))
    }

    @Test fun everyAwakeSignalResetsBothTheIdleBoundaryAndMotionEvidence() {
        for (source in listOf("screen-on", "unlock", "media", "bluetooth", "notification", "widget", "volume", "seek", "chapter", "shake", "remote")) {
            val p = asleep()
            val now = 3 * hour
            still(p, now)
            p.awake(now)
            assertFalse(source, p.allows(now + 1000, 2 * hour, false, 0))
            assertFalse(source, p.allows(now + 2 * hour, 2 * hour, true, 0))
        }
    }

    @Test fun sensorGapsClockRollbackAndDisabledSafetyNeverArm() {
        val p = asleep()
        still(p, 121_000)
        p.motionWindow(221_000, 251_000, 0.01)
        assertFalse(p.allows(251_000, 120_000, true, 0))
        assertFalse(p.allows(500, 120_000, false, 0))
        assertFalse(p.allows(3 * hour, 0, false, 0))
        assertFalse(p.allows(3 * hour, hour, false, 3 * hour - 1000))
    }
}
