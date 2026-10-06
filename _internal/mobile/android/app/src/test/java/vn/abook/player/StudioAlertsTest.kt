package vn.abook.player

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Test

/** So trạng thái một cuốn với ảnh chụp lần trước (StudioAlerts.alerts): tin "Sẵn sàng duyệt" khi máy giữ cuốn chờ duyệt. */
class StudioAlertsTest {
    private fun book(running: Boolean, paused: String?, held: Boolean): JSONObject = JSONObject()
        .put("id", "b1").put("title", "Sách thử").put("phase", "tts").put("statusLabel", "Đang thu")
        .put("running", running).put("paused", paused ?: JSONObject.NULL)
        .put("precast", JSONObject().put("ready", true).put("held", held))
        .put("chapters", JSONObject().put("completed", 0).put("total", 10))
        .put("work", 0)

    private fun snapshot(running: Boolean, paused: String, held: Boolean): JSONObject = JSONObject()
        .put("phase", "tts").put("running", running).put("paused", paused).put("held", held).put("work", 0)

    @Test
    fun aBookHeldForReviewGivesExactlyOneReadyToReviewAlert() {
        val notes = StudioAlerts.alerts(book(running = true, paused = "listener", held = true),
            snapshot(running = true, paused = "", held = false), machineOnBattery = false)
        assertEquals(listOf("b1:precast"), notes.map { it.key })
        assertEquals("Sẵn sàng duyệt: Sách thử", notes[0].title)
        assertEquals("/#/studio/b1?tab=precast", notes[0].path)
    }

    @Test
    fun aHeldBookThatAlsoStoppedRunningIsNotReportedAsStopped() {
        val notes = StudioAlerts.alerts(book(running = false, paused = "listener", held = true),
            snapshot(running = true, paused = "", held = false), machineOnBattery = false)
        assertEquals(listOf("b1:precast"), notes.map { it.key })
        val later = StudioAlerts.alerts(book(running = false, paused = "listener", held = true),
            snapshot(running = true, paused = "listener", held = true), machineOnBattery = false)
        assertEquals("vẫn giữ: không báo lại, không thành \"Đã dừng\"", emptyList<String>(), later.map { it.key })
    }

    @Test
    fun aComputerWithoutThePrecastFieldNeverAlertsReview() {
        val old = book(running = true, paused = null, held = false).apply { remove("precast") }
        val notes = StudioAlerts.alerts(old, snapshot(running = true, paused = "", held = false), machineOnBattery = false)
        assertEquals(emptyList<String>(), notes.map { it.key })
    }

    @Test
    fun stoppingWithoutAHoldIsStillReportedAsStopped() {
        val notes = StudioAlerts.alerts(book(running = false, paused = null, held = false),
            snapshot(running = true, paused = "", held = false), machineOnBattery = false)
        assertEquals(listOf("b1:stopped"), notes.map { it.key })
    }
}
