package vn.abook.player

import java.util.concurrent.Executors

/**
 * Luồng ghi nền tuần tự (`abook-disk`) cho những lần ghi nhỏ của lõi phát mà luồng chính không được chờ: hẹn giờ ngủ ([SleepTimer.persist]),
 * phiên nghe ([Playback] khi dừng), nhật ký đêm ([Bedtime]). Các lần ghi ấy đi qua [Store.writeAtomic] (khoá Store + fsync): trên luồng chính
 * chúng đứng chờ mỗi khi luồng khác giữ khoá Store (nhập lại một .abook, đồng bộ) - bấm dừng trên tai nghe là giật / ANR (soát Android 12-11 mục 3).
 *
 * Người gọi chụp dữ liệu trên luồng của mình rồi giao một việc ghi không đụng trạng thái chung; các việc chạy đúng thứ tự giao. Lỗi ghi chỉ vào nhật ký:
 * bản cũ trên đĩa còn nguyên (ghi nguyên tử), lần ghi kế ghi lại cả bản. Chỗ nghe có hàng riêng ([OrderedCheckpoint], `abook-place`).
 */
internal object DiskWrites {
    private val executor = Executors.newSingleThreadExecutor { task -> Thread(task, "abook-disk").apply { isDaemon = true } }
    private val lock = Object()
    private var pending = 0

    fun post(tag: String, write: () -> Unit) {
        synchronized(lock) { pending += 1 }
        executor.execute {
            try {
                runCatching(write).onFailure { error -> runCatching { AppLog.w(tag, S.s_ghi_nen_chua_xong_0_9b2f61d4(error.javaClass.simpleName), error) } }
            } finally {
                synchronized(lock) {
                    pending -= 1
                    lock.notifyAll()
                }
            }
        }
    }

    /** Chờ mọi việc đã giao ghi xong (đọc lại file vừa ghi, dịch vụ tắt, test). Không gọi trên luồng chính hay khi đang giữ khoá Store. false khi quá [timeoutMs]. */
    fun flush(timeoutMs: Long = 2_000): Boolean {
        val deadline = System.nanoTime() + timeoutMs * 1_000_000
        synchronized(lock) {
            while (pending > 0) {
                val left = (deadline - System.nanoTime()) / 1_000_000
                if (left <= 0) return false
                lock.wait(left)
            }
        }
        return true
    }
}
