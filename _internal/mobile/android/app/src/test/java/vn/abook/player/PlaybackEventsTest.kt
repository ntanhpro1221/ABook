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
    fun listenersGetEventsAndRemovalDetachesTheUi() {
        val ui = mutableListOf<JSONObject>()
        val service = mutableListOf<String>()
        val uiListener: (JSONObject) -> Unit = { ui += it }
        val serviceListener: (JSONObject) -> Unit = { service += it.optString("kind") }
        Playback.addListener(uiListener)
        Playback.addListener(serviceListener)
        try {
            Playback.emit("tick")
            Playback.emit("record")
            assertEquals(listOf("tick", "record"), ui.map { it.optString("kind") })
            assertEquals(listOf("tick", "record"), service)
            assertTrue(ui.first().has("position"))
            assertTrue(ui.first().has("sleep"))
            Playback.removeListener(uiListener)
            Playback.emit("tick")
            Playback.emit("record")
            assertEquals(2, ui.size)
            assertEquals(listOf("tick", "record", "tick", "record"), service)
        } finally {
            Playback.removeListener(uiListener)
            Playback.removeListener(serviceListener)
        }
    }
}
