package vn.abook.player

import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test

class BedtimeLifecycleTest {
    private fun field(name: String) = Bedtime::class.java.getDeclaredField(name).also { it.isAccessible = true }

    @Before fun setup() {
        assertTrue(DiskWrites.flush(TestTime.ms(5_000)))
        BookEditsFixtures.useStoreRoot(BookEditsFixtures.tempDir("bedtime-lifecycle"))
        field("session").set(Bedtime, null)
        field("closed").set(Bedtime, null)
    }

    @After fun cleanup() {
        Bedtime.timerOff()
        assertTrue(DiskWrites.flush(TestTime.ms(5_000)))
        field("session").set(Bedtime, null)
        field("closed").set(Bedtime, null)
    }

    private fun saved(): org.json.JSONObject {
        assertTrue(DiskWrites.flush(TestTime.ms(5_000)))
        return Bedtime.all().single()
    }

    @Test fun stopAndCancelCloseTheNightAndIgnoreDaytimeEvents() {
        for (close in listOf<() -> Unit>({ Bedtime.stopped() }, { Bedtime.timerOff() })) {
            Bedtime.timerSet(30)
            close()
            val night = saved().toString()
            assertNull(field("session").get(Bedtime))
            repeat(3) {
                Bedtime.interaction("play")
                Bedtime.checkpoint()
                Bedtime.window(1_800_000_000_000L, 0.0)
            }
            assertEquals(night, saved().toString())
            assertTrue(saved().has("endedAt"))
        }
    }

    @Test fun anExplicitNewTimerReopensARecentlyClosedNight() {
        Bedtime.timerSet(30)
        val start = saved().getDouble("startedAt")
        Bedtime.stopped()
        Bedtime.timerSet(15)
        assertEquals(start, saved().getDouble("startedAt"), 0.0)
        assertFalse(saved().has("endedAt"))
        assertNotNull(field("session").get(Bedtime))
    }

    @Test fun eventsAreBoundedAndTheLatestEventIsKept() {
        Bedtime.timerSet(30)
        repeat(Bedtime.MAX_EVENTS + 5) { Bedtime.interaction("touch-$it") }
        val events = saved().getJSONArray("events")
        assertEquals(Bedtime.MAX_EVENTS, events.length())
        assertEquals("touch-${Bedtime.MAX_EVENTS + 4}", events.getJSONObject(events.length() - 1).getString("action"))
    }
}
