package vn.abook.player

import androidx.work.WorkInfo
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** Soát a111: hết 6 giờ phải kết thúc HẲN việc (R1), `active` của tải sách không sống lại (R2), snapshot nối lại không hồi sinh lượt xong (R3). */
class A111WorkTest {
    private val timeout = WorkInfo.STOP_REASON_FOREGROUND_SERVICE_TIMEOUT

    // ---- R1 -------------------------------------------------------------------------------------------------------

    @Test fun a_timed_out_worker_is_ended_for_good_before_it_cleans_up() {
        assertTrue(Mp3Exports.mustEnd(35, timeout, stopped = true, alreadyEnded = false))
        assertFalse("đã có dấu kết thúc thì không ghi lại", Mp3Exports.mustEnd(35, timeout, stopped = true, alreadyEnded = true))
        assertFalse("chưa bị dừng", Mp3Exports.mustEnd(35, timeout, stopped = false, alreadyEnded = false))
        assertFalse("Android cũ không có lý do hết giờ", Mp3Exports.mustEnd(28, timeout, stopped = true, alreadyEnded = false))
    }

    @Test fun only_the_six_hour_timeout_ends_a_job_other_system_stops_still_retry() {
        for (reason in listOf(WorkInfo.STOP_REASON_UNKNOWN, WorkInfo.STOP_REASON_CONSTRAINT_CHARGING, WorkInfo.STOP_REASON_PREEMPT, WorkInfo.STOP_REASON_BACKGROUND_RESTRICTION)) {
            assertFalse("lý do $reason", Mp3Exports.mustEnd(35, reason, stopped = true, alreadyEnded = false))
            assertTrue("lý do $reason vẫn chạy lại", Mp3Exports.stoppedBySystem(35, reason, explicitlyCancelled = false))
        }
        assertFalse("sau khi có dấu kết thúc, hết giờ không còn là 'hệ thống dừng' để chạy lại", Mp3Exports.stoppedBySystem(35, timeout, explicitlyCancelled = true))
    }

    // ---- R2 -------------------------------------------------------------------------------------------------------

    @Test fun a_run_that_ended_between_the_snapshot_and_the_registration_is_not_registered() {
        val runs = ActiveRuns()
        assertTrue(runs.add("b1", "r1"))
        assertTrue(runs.end("b1", "r1"))
        assertFalse("start chụp danh sách rồi mới ghi: r1 đã kết thúc", runs.add("b1", "r1"))
        assertFalse("restore cũng vậy", runs.addIfAbsent("b1", "r1"))
        assertNull(runs.map["b1"])
    }

    @Test fun interleaved_start_and_leave_never_leave_a_dead_entry() {
        repeat(200) { round ->
            val runs = ActiveRuns()
            val run = "r$round"
            val gate = java.util.concurrent.CountDownLatch(1)
            val starter = Thread { gate.await(); runs.add("b", run) }
            val leaver = Thread { gate.await(); runs.end("b", run) }
            starter.start(); leaver.start(); gate.countDown(); starter.join(); leaver.join()
            // Mọi thứ tự: hoặc add rồi end (gỡ sạch), hoặc end rồi add (bị từ chối) - không bao giờ còn mục của việc đã kết thúc.
            assertNull("vòng $round", runs.map["b"])
        }
    }

    @Test fun a_newer_run_is_not_removed_by_an_older_runs_end() {
        val runs = ActiveRuns()
        runs.add("b", "r2")
        assertFalse(runs.end("b", "r1"))
        assertEquals("r2", runs.map["b"])
    }

    @Test fun only_a_live_work_state_counts_as_downloading() {
        assertFalse(ActiveRuns.alive(null))
        for (state in listOf(WorkInfo.State.SUCCEEDED, WorkInfo.State.FAILED, WorkInfo.State.CANCELLED)) assertFalse("$state", ActiveRuns.alive(state))
        for (state in listOf(WorkInfo.State.ENQUEUED, WorkInfo.State.RUNNING, WorkInfo.State.BLOCKED)) assertTrue("$state", ActiveRuns.alive(state))
    }

    // ---- R3 -------------------------------------------------------------------------------------------------------

    @Test fun a_run_that_reported_its_end_is_remembered_and_the_stale_work_snapshot_cannot_revive_it() {
        val live = ExportLive("mp3")
        live.note("b1", "w1", JSONObject().put("folder", "Music"))
        live.emit(JSONObject().put("bookId", "b1").put("run", "w1").put("done", 2).put("total", 3))
        assertFalse(live.isEnded("w1"))
        live.emit(JSONObject().put("bookId", "b1").put("run", "w1").put("finished", true))
        assertTrue(live.isEnded("w1"))
        assertTrue(live.running().isEmpty())
        val stale = listOf(ExportJobs.Work("mp3", "b1", "w1"), ExportJobs.Work("mp3", "b2", "w9"))
        val merged = ExportJobs.merge(live.running(), stale) { live.isEnded(it.run) }
        assertEquals(listOf("w9"), merged.map { it.optString("run") })
    }

    @Test fun an_error_or_stop_also_ends_the_run() {
        val live = ExportLive("m4b")
        live.emit(JSONObject().put("bookId", "b").put("run", "e").put("error", "hỏng"))
        live.emit(JSONObject().put("bookId", "b").put("run", "s").put("stopped", true))
        assertTrue(live.isEnded("e") && live.isEnded("s"))
    }
}
