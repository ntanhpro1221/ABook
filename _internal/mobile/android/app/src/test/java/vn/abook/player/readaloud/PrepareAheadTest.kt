package vn.abook.player.readaloud

import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import java.nio.file.Files

/** "Làm trước": chọn chương vừa bộ đệm, điều kiện chạy, ước thời gian, vòng làm (bỏ qua đoạn đã có, nhường người nghe, dừng khi giọng mạng hỏng). */
class PrepareAheadTest {
    private val dir: File = Files.createTempDirectory("prepare").toFile()

    @After
    fun cleanUp() {
        dir.deleteRecursively()
    }

    private fun chapter(id: Int, paragraphs: Int, chars: Int) = PrepareChapter(id, "Chương $id", paragraphs, chars)

    private fun job(chapters: List<PrepareChapter>, voice: String = "edge:vi-VN-HoaiMyNeural", chargingOnly: Boolean = true) =
        PrepareJob("j1", "book", voice, "3 chương tới", PreparePlan.online(voice), chapters, chapters.size, chapters.sumOf { it.paragraphs }, chargingOnly, 0L)

    // ---- chọn -------------------------------------------------------------------------------------------------------

    @Test
    fun onlineVoicesNeedTheNetworkLocalOnesDoNot() {
        assertTrue(PreparePlan.online("edge:vi-VN-HoaiMyNeural"))
        assertTrue(PreparePlan.online("azure:vi-VN-NamMinhNeural"))
        assertFalse(PreparePlan.online("device:vi-vn-x-gft-local"))
        assertFalse(PreparePlan.online("vieneu:turbo/Ngọc"))
    }

    @Test
    fun cacheBytesFollowTheVoicesFileFormat() {
        assertEquals(6_000, PreparePlan.bytesPerSecond("edge:vi-VN-HoaiMyNeural"))
        assertEquals(96_000, PreparePlan.bytesPerSecond("vieneu:turbo/Ngọc"))
        assertEquals(48_000, PreparePlan.bytesPerSecond("vieneu:nano/Ngọc"))
        assertEquals(48_000, PreparePlan.bytesPerSecond("device:x"))
        // 14 ký tự một giây nghe: 1400 ký tự = 100 giây.
        assertEquals(600_000, PreparePlan.bytesOf(1400, 6_000))
    }

    @Test
    fun acceptTakesWholeChaptersInOrderWhileTheyFitAndAlwaysAtLeastOne() {
        val chapters = listOf(chapter(1, 10, 1400), chapter(2, 0, 0), chapter(3, 10, 1400), chapter(4, 10, 1400))
        // Mỗi chương 100 giây x 1000 B = 100 kB.
        assertEquals(listOf(1, 3), PreparePlan.accept(chapters, 1000, 250_000).map { it.id })
        assertEquals("chương rỗng bị bỏ", listOf(1, 3, 4), PreparePlan.accept(chapters, 1000, 10_000_000).map { it.id })
        assertEquals("chương đầu quá lớn vẫn nhận", listOf(1), PreparePlan.accept(chapters, 1000, 10).map { it.id })
        // Phần bộ đệm dành cho làm trước: 60% của 300 MB.
        assertEquals(0.6, PreparePlan.SHARE, 0.0)
    }

    // ---- điều kiện -------------------------------------------------------------------------------------------------

    @Test
    fun constraintsAskForChargingOnlyWhenChosenAndWifiOnlyForOnlineVoices() {
        assertEquals(PreparePlan.Needs(charging = true, unmetered = true, batteryNotLow = true), PreparePlan.needs(online = true, chargingOnly = true))
        assertEquals(PreparePlan.Needs(charging = false, unmetered = false, batteryNotLow = true), PreparePlan.needs(online = false, chargingOnly = false))
    }

    @Test
    fun waitingForSaysWhatTheListenerCanFix() {
        val online = job(listOf(chapter(1, 2, 20)))
        assertEquals("charging", PreparePlan.waitingFor(online, working = false, live = false, charging = false, unmetered = true, batteryLow = false))
        assertEquals("wifi", PreparePlan.waitingFor(online, working = false, live = false, charging = true, unmetered = false, batteryLow = false))
        assertEquals("battery", PreparePlan.waitingFor(online, working = false, live = false, charging = true, unmetered = true, batteryLow = true))
        assertNull(PreparePlan.waitingFor(online, working = false, live = false, charging = true, unmetered = true, batteryLow = false))
        assertEquals("listening", PreparePlan.waitingFor(online, working = true, live = true, charging = true, unmetered = true, batteryLow = false))
        assertNull(PreparePlan.waitingFor(online, working = true, live = false, charging = false, unmetered = false, batteryLow = false))
        val local = job(listOf(chapter(1, 2, 20)), voice = "vieneu:turbo/Ngọc", chargingOnly = false)
        assertNull("giọng trên máy không cần Wi-Fi, không chọn chỉ khi sạc", PreparePlan.waitingFor(local, false, false, false, false, false))
        online.state = "done"
        assertNull(PreparePlan.waitingFor(online, false, false, false, false, true))
    }

    // ---- lưu / trạng thái ------------------------------------------------------------------------------------------

    @Test
    fun aJobSurvivesARoundTripThroughItsFile() {
        val before = job(listOf(chapter(1, 3, 42), chapter(2, 4, 56)))
        before.chapters[0].done = 3
        before.seconds = 12.5
        before.charsTimed = 30
        before.charsDone = 42
        val after = PrepareJob.fromJson(JSONObject(before.toJson().toString()))
        assertEquals(before.toJson().toString(), after.toJson().toString())
        assertTrue(after.chapters[0].ready)
        assertFalse(after.chapters[1].ready)
    }

    @Test
    fun statusEstimatesFromThisJobsSpeedThenFromTheVoicesMeasuredSpeed() {
        val running = job(listOf(chapter(1, 2, 1400), chapter(2, 2, 1400)))
        running.chapters[0].done = 2
        running.charsDone = 1400
        // Chưa tự đo: dùng tốc độ đã đo của giọng (0,1 giây mỗi ký tự).
        var status = running.status(0.1, "charging")
        assertEquals(140L, status.getLong("secondsLeft"))
        assertEquals("charging", status.getString("waitingFor"))
        assertEquals(200L, status.getLong("audioSeconds"))
        assertEquals(1, (0 until status.getJSONArray("chapters").length()).count { status.getJSONArray("chapters").getJSONObject(it).getBoolean("ready") })
        assertEquals(2, status.getInt("done"))
        assertEquals(4, status.getInt("total"))
        // Đã đo trong việc này: 0,05 giây mỗi ký tự thắng số cũ.
        running.charsTimed = 1000
        running.seconds = 50.0
        status = running.status(0.1, null)
        assertEquals(70L, status.getLong("secondsLeft"))
        assertTrue(status.isNull("waitingFor"))
        assertTrue("chưa đo bao giờ thì không đoán", job(listOf(chapter(1, 1, 10))).status(null, null).isNull("secondsLeft"))
    }

    @Test
    fun voiceSpeedsAreRememberedAndRecentMeasurementsWin() {
        val file = File(dir, "speeds.json")
        val speeds = VoiceSpeeds(file)
        assertNull(speeds.secondsPerChar("edge:a"))
        speeds.record("edge:a", 100, 10.0)
        assertEquals(0.1, VoiceSpeeds(file).secondsPerChar("edge:a")!!, 1e-9)
        repeat(10) { speeds.record("edge:a", 5000, 1000.0) } // máy chậm hẳn đi: 0,2 giây mỗi ký tự
        assertTrue(speeds.secondsPerChar("edge:a")!! > 0.19)
        assertNull(speeds.secondsPerChar("edge:b"))
    }

    // ---- vòng làm -----------------------------------------------------------------------------------------------------

    private class Harness(val texts: Map<Int, List<String>>) {
        val cache = HashSet<String>()
        val made = ArrayList<String>()
        val pinned = HashSet<String>()
        val saves = ArrayList<String>()
        var now = 0L
        var liveFor = 0
        var stopAfter = Int.MAX_VALUE
        var failOn: String? = null
        var failure: VoiceException? = null

        fun runner(slice: Long = Long.MAX_VALUE, full: () -> Boolean = { false }) = PrepareRunner(
            texts = { texts[it.id] },
            cached = { it in cache },
            make = { text ->
                if (text == failOn) throw failure!!
                now += 2000
                made += text
                cache += text
            },
            pin = { pinned += it },
            live = { (liveFor-- > 0) },
            stopped = { made.size >= stopAfter },
            save = { saves += it.toJson().toString() },
            full = full,
            clock = { now },
            sleep = { now += it },
            sliceMs = slice,
        )
    }

    private fun bookJob(harness: Harness) =
        job(harness.texts.map { (id, list) -> PrepareChapter(id, "Chương $id", list.size, list.sumOf { it.length }) })

    @Test
    fun itMakesEveryMissingParagraphInOrderSkipsCachedOnesAndPinsThemAll() {
        val harness = Harness(linkedMapOf(1 to listOf("a1", "a2"), 2 to listOf("b1", "b2")))
        harness.cache += "a2"
        val job = bookJob(harness)
        assertEquals(PrepareRunner.Outcome.DONE, harness.runner().run(job))
        assertEquals(listOf("a1", "b1", "b2"), harness.made)
        assertEquals(setOf("a1", "a2", "b1", "b2"), harness.pinned)
        assertEquals("done", job.state)
        assertTrue(job.chapters.all { it.ready })
        assertEquals(4, job.done)
        // Mỗi đoạn lưu một lần (+ lần đếm đầu + lần xong): app chết lúc nào cũng mất nhiều nhất một đoạn.
        assertEquals(5, harness.saves.size)
        assertEquals(6.0, job.seconds, 1e-9)
        assertEquals(6L, job.charsTimed)
    }

    @Test
    fun runningAgainIsIdempotentAndResumesWhereItStopped() {
        val harness = Harness(linkedMapOf(1 to listOf("a1", "a2"), 2 to listOf("b1")))
        harness.stopAfter = 1
        val first = bookJob(harness)
        assertEquals(PrepareRunner.Outcome.STOPPED, harness.runner().run(first))
        assertEquals("running", first.state)
        // Sau khi app chết: việc đọc lại từ file, đếm lại từ bộ đệm.
        val resumed = PrepareJob.fromJson(JSONObject(harness.saves.last()))
        harness.stopAfter = Int.MAX_VALUE
        assertEquals(PrepareRunner.Outcome.DONE, harness.runner().run(resumed))
        assertEquals(listOf("a1", "a2", "b1"), harness.made)
        assertEquals(PrepareRunner.Outcome.DONE, harness.runner().run(PrepareJob.fromJson(JSONObject(harness.saves.last()))))
        assertEquals("lần chạy thứ ba không đọc lại gì", 3, harness.made.size)
    }

    @Test
    fun theListenerGoesFirst() {
        val harness = Harness(linkedMapOf(1 to listOf("a1")))
        harness.liveFor = 5
        val job = bookJob(harness)
        harness.runner().run(job)
        assertEquals(listOf("a1"), harness.made)
        // Chờ năm lượt 200 ms rồi mới đọc (2 giây): thời gian chờ không tính vào tốc độ.
        assertEquals(5 * PrepareRunner.LIVE_POLL_MS + 2000, harness.now)
        assertEquals(2.0, job.seconds, 1e-9)
    }

    @Test
    fun anOnlineVoiceGoingOfflineStopsAndSaysSoWithoutFallingBack() {
        val harness = Harness(linkedMapOf(1 to listOf("a1"), 2 to listOf("b1", "b2")))
        harness.failOn = "b2"
        harness.failure = VoiceException("Không có mạng", offline = true)
        val job = bookJob(harness)
        assertEquals(PrepareRunner.Outcome.ERROR, harness.runner().run(job))
        assertEquals("error", job.state)
        assertEquals(listOf("a1", "b1"), harness.made)
        assertTrue(job.error, job.error.startsWith("Mất mạng nên đã dừng làm trước ở “Chương 2”."))
        assertTrue(job.error, job.error.contains("Đã sẵn sàng 1/2 chương"))
    }

    @Test
    fun aParagraphTheVoiceCannotSayIsSkippedNotFatal() {
        val harness = Harness(linkedMapOf(1 to listOf("***", "a")))
        harness.failOn = "***"
        harness.failure = VoiceException("Không có gì để đọc", reason = "empty")
        val job = bookJob(harness)
        assertEquals(PrepareRunner.Outcome.DONE, harness.runner().run(job))
        assertTrue(job.chapters[0].ready)
    }

    @Test
    fun aLongJobRunsInSlicesAndStopsWhenItsCacheShareIsFull() {
        val harness = Harness(linkedMapOf(1 to listOf("a1", "a2", "a3")))
        assertEquals(PrepareRunner.Outcome.SLICE, harness.runner(slice = 3000).run(bookJob(harness)))
        assertEquals(listOf("a1", "a2"), harness.made)
        val job = bookJob(harness)
        assertEquals(PrepareRunner.Outcome.DONE, harness.runner(full = { true }).run(job))
        assertTrue(job.full)
        assertEquals("done", job.state)
        assertEquals(2, harness.made.size)
    }

    @Test
    fun aChapterWhoseTextIsGoneStopsWithAPlainReason() {
        val harness = Harness(linkedMapOf(1 to listOf("a")))
        val job = job(listOf(chapter(1, 1, 1), chapter(9, 1, 1)))
        assertEquals(PrepareRunner.Outcome.ERROR, harness.runner().run(job))
        assertTrue(job.error.contains("Chương 9"))
    }
}
