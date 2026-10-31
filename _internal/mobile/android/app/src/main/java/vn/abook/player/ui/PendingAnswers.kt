package vn.abook.player.ui

/**
 * Câu trả lời một hộp của hệ thống (chọn thư mục, tạo file, xin quyền) đang được đợi. Nằm ở Application chứ KHÔNG ở Activity: hộp hệ thống mở trong lúc Activity bị huỷ
 * (thiếu RAM, "Không giữ hoạt động") thì câu trả lời tới Activity mới - nơi hỏi (màn Xuất...) vẫn đang đợi, không được treo mãi vì Activity mới không biết ai hỏi.
 */
class PendingAnswer<T> {
    @Volatile private var waiting: ((T) -> Unit)? = null

    /** Nơi hỏi đăng ký chỗ nhận; lần hỏi sau đè lần trước (hệ thống chỉ mở một hộp mỗi lúc). */
    fun expect(callback: (T) -> Unit) {
        waiting = callback
    }

    /** Câu trả lời tới: giao một lần cho nơi đã hỏi; không ai đợi thì bỏ. */
    fun deliver(value: T) {
        val callback = waiting
        waiting = null
        callback?.invoke(value)
    }
}

/** Các hộp hệ thống của [NativeActivity] có nơi đang đợi. */
class PendingAnswers {
    /** Địa chỉ thư mục MP3 vừa chọn, null khi bạn huỷ. */
    val folder = PendingAnswer<String?>()

    /** Địa chỉ file vừa tạo (M4B, sách nói), null khi bạn huỷ. */
    val file = PendingAnswer<String?>()

    /** Được cấp quyền "Thiết bị ở gần" hay không. */
    val nearby = PendingAnswer<Boolean>()

    /** Hộp xin quyền thông báo đã đóng (cấp hay từ chối đều đi tiếp). */
    val notifications = PendingAnswer<Unit>()
}
