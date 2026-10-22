package vn.abook.player

import androidx.work.WorkInfo
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Xuất MP3 / M4B / sách nói bị dừng (soát a73, F4): chỉ người dùng bấm "Dừng" (hay xuất lại) mới là dừng hẳn - xoá file dở,
 * báo "Đã dừng". Hệ thống dừng việc (hết giờ chạy nền, thiếu bộ nhớ, mất điều kiện chạy) thì WorkManager chạy lại, file đích
 * còn nguyên. Ba worker dùng chung [Mp3Exports.stoppedBySystem]; phần Worker cần Context thật nên không chạy được trên JVM.
 */
class ExportStopTest {
    @Test
    fun only_the_listener_or_the_app_cancelling_is_a_real_stop() {
        assertFalse(Mp3Exports.stoppedBySystem(34, WorkInfo.STOP_REASON_CANCELLED_BY_APP))
        assertFalse("không rõ lý do: coi như người dùng dừng", Mp3Exports.stoppedBySystem(34, WorkInfo.STOP_REASON_UNKNOWN))
        for (reason in listOf(WorkInfo.STOP_REASON_TIMEOUT, WorkInfo.STOP_REASON_SYSTEM_PROCESSING, WorkInfo.STOP_REASON_QUOTA,
            WorkInfo.STOP_REASON_DEVICE_STATE, WorkInfo.STOP_REASON_PREEMPT)) {
            assertTrue("lý do $reason là hệ thống dừng", Mp3Exports.stoppedBySystem(31, reason))
        }
        assertFalse("Android 11 trở xuống không báo lý do", Mp3Exports.stoppedBySystem(30, WorkInfo.STOP_REASON_TIMEOUT))
    }
}
