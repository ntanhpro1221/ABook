package vn.abook.player

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class PlaybackEventsTest {
    @Test
    fun uiGetsClockWhileServiceStillGetsStateChangesAndRemovalDetachesBoth() {
        val ui = mutableListOf<JSONObject>()
        val service = mutableListOf<String>()
        val uiListener: (JSONObject) -> Unit = { ui += it }
        val serviceListener: (JSONObject) -> Unit = { service += it.optString("kind") }
        Playback.addListener(uiListener)
        Playback.addListener(serviceListener, ticks = false)
        try {
            Playback.emit("tick")
            Playback.emit("record")
            assertEquals(listOf("tick", "record"), ui.map { it.optString("kind") })
            assertEquals(listOf("record"), service)
            assertTrue(ui.first().has("position"))
            assertTrue(ui.first().has("sleep"))
            Playback.removeListener(uiListener)
            Playback.emit("tick")
            Playback.emit("record")
            assertEquals(2, ui.size)
            assertEquals(listOf("record", "record"), service)
        } finally {
            Playback.removeListener(uiListener)
            Playback.removeListener(serviceListener)
        }
    }
}
