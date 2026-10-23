package vn.abook.player

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test
import java.util.UUID
import java.util.concurrent.atomic.AtomicInteger

/**
 * Giao diện mở lại giữa lúc việc xuất / tải nền vẫn chạy (soát a107 F1, F2): việc nền phải nói được "đang chạy gì" ([ExportLive], [ExportJobs]) và
 * hàng đợi tải chạy mỗi lần một cuốn, dừng được ngay khi còn xếp hàng ([BookDownloads]). Phần WorkManager thật cần Context nên không chạy được trên JVM.
 */
class ExportRejoinTest {
    private fun event(book: String, run: String) = JSONObject().put("bookId", book).put("run", run)

    @Test
    fun theLastEventOfARunningExportIsWhatTheNewScreenAsksFor() {
        val live = ExportLive("mp3")
        live.note("b1", "w1", JSONObject().put("folder", "Music/Sách").put("music", true))
        live.emit(event("b1", "w1").put("done", 3).put("total", 10))
        live.emit(event("b1", "w1").put("done", 4).put("total", 10))
        val jobs = live.running()
        assertEquals(1, jobs.size)
        val job = jobs.single()
        assertEquals("mp3", job.getString("kind"))
        assertEquals(4, job.getInt("done"))
        assertEquals("Music/Sách", job.getString("folder"))
        assertTrue(job.getBoolean("music"))
    }

    @Test
    fun aRunThatJustStartedAlreadyShowsUpBeforeItsFirstProgress() {
        val live = ExportLive("m4b")
        live.note("b1", "w1", JSONObject())
        val job = live.running().single()
        assertEquals("w1", job.getString("run"))
        assertFalse(job.has("done"))
    }

    @Test
    fun aFinishedStoppedOrFailedRunIsNoLongerRunning() {
        for (last in listOf(JSONObject().put("finished", true), JSONObject().put("stopped", true), JSONObject().put("error", "hết chỗ"))) {
            val live = ExportLive("audiobook")
            live.note("b1", "w1", JSONObject())
            live.emit(event("b1", "w1").put("done", 1).put("total", 2))
            val end = event("b1", "w1")
            last.keys().forEach { key -> end.put(key, last.get(key)) }
            live.emit(end)
            assertTrue(live.running().isEmpty())
            assertTrue(live.books().isEmpty())
        }
    }

    @Test
    fun aLateEventOfTheReplacedRunDoesNotTouchTheNewRun() {
        val live = ExportLive("mp3")
        live.note("b1", "old", JSONObject())
        live.note("b1", "new", JSONObject().put("folder", "Music/Sách"))
        live.emit(event("b1", "new").put("done", 1).put("total", 5))
        live.emit(event("b1", "old").put("done", 4).put("total", 5)) // tin muộn của lượt cũ
        live.emit(event("b1", "old").put("stopped", true))
        val job = live.running().single()
        assertEquals("new", job.getString("run"))
        assertEquals(1, job.getInt("done"))
    }

    @Test
    fun workManagerTagsRoundTripAndFillTheGapAfterTheProcessWasKilled() {
        val tags = ExportJobs.tags("m4b", "sách:1")
        val id = UUID.randomUUID()
        val work = ExportJobs.work(tags, id)!!
        assertEquals("m4b", work.kind)
        assertEquals("sách:1", work.bookId)
        assertEquals(id.toString(), work.run)
        assertEquals(null, ExportJobs.work(setOf("export-kind:m4b"), id))
        // Tiến trình mới chưa có tin nào: vẫn thấy việc WorkManager còn giữ; cuốn đã có tin thì không thêm bản trùng.
        val known = JSONObject().put("kind", "mp3").put("bookId", "b1").put("run", "w1").put("done", 2)
        val merged = ExportJobs.merge(listOf(known), listOf(ExportJobs.Work("mp3", "b1", "w1"), ExportJobs.Work("m4b", "b2", "w2"), ExportJobs.Work("m4b", "b2", "w3")))
        assertEquals(2, merged.size)
        assertEquals(setOf("mp3" to "b1", "m4b" to "b2"), merged.map { it.getString("kind") to it.getString("bookId") }.toSet())
        assertEquals("w2", merged.single { it.getString("kind") == "m4b" }.getString("run"))
    }

    @Test
    fun downloadsRunOneBookAtATimeAndAQueuedOneCanBeCancelled() {
        val inside = AtomicInteger()
        val most = AtomicInteger()
        val gate = BookDownloads.Gate()
        val threads = (1..3).map {
            Thread {
                BookDownloads.inTurn(gate) {
                    most.accumulateAndGet(inside.incrementAndGet()) { a, b -> maxOf(a, b) }
                    Thread.sleep(40)
                    inside.decrementAndGet()
                }
            }.apply { start() }
        }
        threads.forEach { it.join() }
        assertEquals(1, most.get())

        // Việc đứng chờ tới lượt mà bị dừng (Huỷ, hay hệ thống dừng) thì thôi chờ ngay, không chạy.
        val stop = java.util.concurrent.atomic.AtomicBoolean(false)
        val holder = Thread { BookDownloads.inTurn(gate) { Thread.sleep(900) } }.apply { start() }
        Thread.sleep(100)
        val waiting = BookDownloads.Gate("w") { stop.get() }
        stop.set(true)
        try {
            BookDownloads.inTurn(waiting) { fail("không được chạy khi đã bị dừng") }
            fail("phải ném")
        } catch (expected: BookDownloads.Interrupted) {
        }
        holder.join()
    }

    @Test
    fun theDownloadGateTellsACancelFromASystemStop() {
        val gate = BookDownloads.Gate("r1") { false }
        gate.check() // không sao
        val stopped = BookDownloads.Gate("r2") { true }
        try {
            stopped.check()
            fail("phải ném")
        } catch (expected: BookDownloads.Interrupted) {
        }
    }
}
