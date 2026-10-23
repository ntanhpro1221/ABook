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

    // ---- Soát a88: V6 tin "tạm dừng vì pin" và T4 dừng khác sập ----

    @Test
    fun aBookPausedForTheBatteryIsReportedWhenTheMachineWasNotOnBatteryBefore() {
        val notes = StudioAlerts.alerts(book(running = true, paused = "battery", held = false),
            snapshot(running = true, paused = "", held = false), machineOnBattery = false)
        assertEquals(listOf("b1:battery"), notes.map { it.key })
        assertEquals("Chạy pin: Sách thử", notes[0].title)
    }

    @Test
    fun aMachineAlreadyReportedOnBatteryDoesNotRepeatItPerBook() {
        val notes = StudioAlerts.alerts(book(running = true, paused = "battery", held = false),
            snapshot(running = true, paused = "", held = false), machineOnBattery = true)
        assertEquals(emptyList<String>(), notes.map { it.key })
    }

    private fun reply(onBattery: Boolean, book: JSONObject): JSONObject = JSONObject()
        .put("name", "Máy thử").put("onBattery", onBattery).put("books", org.json.JSONArray().put(book))

    @Test
    fun unplugAndPauseSeenInTheSamePollGiveBothAlertsOnceAndNoRepeatLater() {
        // Lần hỏi trước: cắm sạc, sách đang chạy. Chuỗi này sai khi onBattery bị ghi trước rồi mới đọc lại (tin của cuốn không bao giờ tới).
        val first = StudioAlerts.evaluate(reply(false, book(running = true, paused = null, held = false)), JSONObject(), seeded = false, wasOnBattery = false)
        assertEquals(emptyList<String>(), first.alerts.map { it.key })
        assertEquals(false, first.onBattery)

        val second = StudioAlerts.evaluate(reply(true, book(running = true, paused = "battery", held = false)),
            first.snapshot, seeded = true, wasOnBattery = first.onBattery)
        assertEquals(listOf("machine:battery", "b1:battery"), second.alerts.map { it.key })
        assertEquals(true, second.onBattery)

        val third = StudioAlerts.evaluate(reply(true, book(running = true, paused = "battery", held = false)),
            second.snapshot, seeded = true, wasOnBattery = second.onBattery)
        assertEquals(emptyList<String>(), third.alerts.map { it.key })
    }

    private fun ended(end: String?, detail: String = ""): JSONObject = book(running = false, paused = null, held = false).apply {
        if (end != null) put("end", end).put("endDetail", detail)
    }

    @Test
    fun aStopYouPressedAndACrashAreToldApart() {
        val old = snapshot(running = true, paused = "", held = false)
        val stopped = StudioAlerts.alerts(ended("stopped"), old, machineOnBattery = false)
        assertEquals(listOf("b1:stopped"), stopped.map { it.key })
        assertEquals("Đã dừng: Sách thử", stopped[0].title)

        val crashed = StudioAlerts.alerts(ended("failed", "worker thoát với exit code 3221225477"), old, machineOnBattery = false)
        assertEquals(listOf("b1:crashed"), crashed.map { it.key })
        assertEquals("Sự cố: Sách thử", crashed[0].title)
        assertEquals("Làm sách gặp sự cố · 0/10 chương — bạn mở Studio.", crashed[0].text)

        val lost = StudioAlerts.alerts(ended("lost"), old, machineOnBattery = false)
        assertEquals(listOf("b1:crashed"), lost.map { it.key })
        assertEquals(true, lost[0].text.contains("bị ngắt đột ngột"))
    }
}
