package vn.abook.player

import android.os.Build
import android.view.HapticFeedbackConstants

/**
 * Rung phản hồi của giao diện (DESIGN.md 5.4): chỉ dùng hằng số của hệ điều hành qua View.performHapticFeedback - tự theo cài đặt
 * rung của máy, không tự chế chuỗi rung. Giao diện gửi TÊN hằng số (shared/feedback.ts); máy cũ chưa có hằng số ấy thì lấy hằng
 * số cũ gần nhất, không có gì gần thì im.
 */
object Haptics {
    /** Tên -> hằng số theo mức API của máy; null = máy này không rung cho việc ấy. */
    fun constant(effect: String, sdk: Int = Build.VERSION.SDK_INT): Int? = when (effect) {
        "CONTEXT_CLICK" -> HapticFeedbackConstants.CONTEXT_CLICK
        "CLOCK_TICK" -> HapticFeedbackConstants.CLOCK_TICK
        "LONG_PRESS" -> HapticFeedbackConstants.LONG_PRESS
        "SEGMENT_TICK" -> if (sdk >= 34) HapticFeedbackConstants.SEGMENT_TICK else HapticFeedbackConstants.CLOCK_TICK
        "GESTURE_THRESHOLD_ACTIVATE" -> if (sdk >= 34) HapticFeedbackConstants.GESTURE_THRESHOLD_ACTIVATE else null
        "CONFIRM" -> if (sdk >= 30) HapticFeedbackConstants.CONFIRM else HapticFeedbackConstants.CONTEXT_CLICK
        "REJECT" -> if (sdk >= 30) HapticFeedbackConstants.REJECT else HapticFeedbackConstants.LONG_PRESS
        else -> null
    }
}
