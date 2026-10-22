package vn.abook.player

import androidx.work.WorkInfo
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Xuất MP3 / M4B / sách nói bị dừng (soát a73, F4): chỉ người dùng bấm "Dừng" (hay xuất lại) mới là dừng hẳn - xoá file dở,
 * báo "Đã dừng". Hệ thống dừng việc (hết giờ chạy nền, thiếu bộ nhớ, mất điều kiện chạy) thì WorkManager chạy lại, file đích
 * còn nguyên, kể cả API 24–30 và lý do UNKNOWN. Chỉ dấu huỷ đã ghi mới cho dọn. Ba worker dùng chung
 * [Mp3Exports.stoppedBySystem]; phần Worker/SAF/receiver cần Context thật nên không chạy được trên JVM.
 */
class ExportStopTest {
    @Test
    fun cancellation_is_sent_only_after_the_marker_is_durable() {
        val calls = mutableListOf<String>()
        ExportCancellation.markThenCancel({ calls.add("commit"); true }) { calls.add("cancel") }
        org.junit.Assert.assertEquals(listOf("commit", "cancel"), calls)
        calls.clear()
        val failed = runCatching {
            ExportCancellation.markThenCancel({ calls.add("commit failed"); false }) { calls.add("cancel") }
        }
        assertTrue(failed.isFailure)
        org.junit.Assert.assertEquals(listOf("commit failed"), calls)
    }

    @Test
    fun only_the_listener_or_the_app_cancelling_is_a_real_stop() {
        assertTrue(Mp3Exports.stoppedBySystem(34, WorkInfo.STOP_REASON_CANCELLED_BY_APP))
        assertTrue("không rõ lý do: giữ tài nguyên", Mp3Exports.stoppedBySystem(34, WorkInfo.STOP_REASON_UNKNOWN))
        for (reason in listOf(WorkInfo.STOP_REASON_TIMEOUT, WorkInfo.STOP_REASON_SYSTEM_PROCESSING, WorkInfo.STOP_REASON_QUOTA,
            WorkInfo.STOP_REASON_DEVICE_STATE, WorkInfo.STOP_REASON_PREEMPT)) {
            assertTrue("lý do $reason là hệ thống dừng", Mp3Exports.stoppedBySystem(31, reason))
        }
        assertTrue("Android 11 trở xuống không báo lý do", Mp3Exports.stoppedBySystem(30, WorkInfo.STOP_REASON_TIMEOUT))
        for (sdk in listOf(24, 30, 31, 34)) {
            for (reason in listOf(WorkInfo.STOP_REASON_UNKNOWN, WorkInfo.STOP_REASON_CANCELLED_BY_APP, WorkInfo.STOP_REASON_TIMEOUT)) {
                assertTrue(Mp3Exports.stoppedBySystem(sdk, reason, explicitlyCancelled = false))
                assertFalse("chỉ dấu Dừng mới cho dọn file: SDK $sdk, reason $reason",
                    Mp3Exports.stoppedBySystem(sdk, reason, explicitlyCancelled = true))
            }
        }
    }
}
