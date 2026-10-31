package vn.abook.player

import vn.abook.player.net.HostWait
import vn.abook.player.readaloud.ClipReader

/**
 * Chốt chặn cuối của trình phát (bản cho máy tính: listen/player.tsx `startStall`): người nghe muốn phát mà chưa có âm thanh suốt [limitMs] (mặc định [HostWait.STALL_MS] = 215 giây,
 * dài hơn cả hai lượt gửi của lời gọi giọng đọc) thì lời gọi nào đó đã lọt khỏi hạn chờ riêng của nó - [onStall] biến việc chờ thành lời báo lỗi như một nguồn hỏng, kèm "Thử lại".
 * Không phụ thuộc đồng hồ máy: hẹn giờ do người dùng lớp này đưa vào (`schedule` = Handler.postDelayed, bài thử đưa đồng hồ giả). Luồng chính.
 */
internal class BufferingGuard(
    private val limitMs: Long = HostWait.STALL_MS,
    private val schedule: (delayMs: Long, task: Runnable) -> Unit,
    private val cancel: (task: Runnable) -> Unit,
    private val onStall: () -> Unit,
) {
    private var armed = false
    private val fire = Runnable {
        armed = false
        onStall()
    }

    /** Gọi mỗi khi trạng thái phát đổi: `waiting` = người nghe muốn phát mà chưa có âm thanh. Bắt đầu chờ thì đặt hạn; hết chờ (có tiếng, dừng, hỏng) thì gỡ hạn. */
    @Synchronized
    fun observe(waiting: Boolean) {
        if (waiting && !armed) {
            armed = true
            schedule(limitMs, fire)
        } else if (!waiting && armed) {
            armed = false
            cancel(fire)
        }
    }

    companion object {
        const val PLAY_FAILED = "Chưa phát được chương này - file có thể đã bị xoá hoặc đang được ghi lại."

        /**
         * Lời báo khi chờ quá hạn, cùng câu với nguồn hỏng cùng loại: chương đọc to thì giọng ([ClipReader.NO_USABLE_VOICE], giao diện thay tên giọng); nghe thẳng từ máy khác thì hết giờ chờ máy
         * ấy ([NetErrors.Kind.TIMEOUT]); còn lại là file ([PLAY_FAILED]).
         */
        fun message(inText: Boolean, streamed: Boolean, holder: String): String = when {
            inText -> ClipReader.NO_USABLE_VOICE
            streamed -> NetErrors.message(NetErrors.Kind.TIMEOUT, holder)
            else -> PLAY_FAILED
        }
    }
}
