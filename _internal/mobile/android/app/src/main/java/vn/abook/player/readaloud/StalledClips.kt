package vn.abook.player.readaloud

/**
 * Đoạn đọc hỏng vì dịch vụ trục trặc (Edge cắt lượt / bận / chậm - reason "service" / "timeout", kể cả lời cuối `final` của [ClipReader]) sau khi hết lần thử lại ([ClipRetry]) mà người nghe
 * CHƯA tới đoạn ấy: không dừng, nhưng cũng không bỏ cuộc vĩnh viễn như trước (soát a46 trên máy tính: Edge sống lại sau 28 giây, người nghe tới đoạn hỏng lúc 39,5 giây mà vẫn bị dừng vì chưa ai
 * hỏi lại - bấm "Thử lại" là xong ngay). Luật chung với máy tính (listen/readAloud.ts `gaveUp` / `probe`):
 *  - lượt đọc kế của đúng đoạn ấy là lần hỏi MỚI ([takeFresh] -> `ClipReader.read(fresh = true)`: quên lệnh nghỉ của giọng, quỹ thử lại tính lại);
 *  - trong lúc người nghe còn âm thanh để nghe, cứ [REASK_MS] mới hỏi lại một lần ([cooldownMs]) - mất mạng dài không thành bão lượt gọi;
 *  - hàng đợi cạn (người nghe tới nơi) thì hỏi ngay, không chờ nhịp ([ReadAloud.pump]); lần hỏi mới ấy hỏng nữa mới dừng và báo.
 */
class StalledClips(private val clock: () -> Long = System::nanoTime) {
    companion object {
        /** Hỏi lại một đoạn đã hết lần thử cách nhau ít nhất chừng này (ms) khi người nghe còn âm thanh. */
        const val REASK_MS = 10_000L

        /** Lỗi thuộc loại "dịch vụ trục trặc" (không tính mất mạng / bị từ chối / khoá hỏng: hỏi lại cũng vô ích hay đã có đường riêng). */
        fun isServiceTrouble(error: Throwable?): Boolean = error is VoiceException && error.reason in VoiceException.TRANSIENT_REASONS
    }

    private var chapter = -1
    private var segment = -1
    private var failedAt = 0L

    /** Ghi nhớ đoạn (`chapter`, `segment`) vừa hỏng vì dịch vụ trục trặc. Một đoạn một lúc: đoạn khác hỏng thì quên đoạn cũ (đọc theo thứ tự nên chỉ có một đoạn đang chờ nạp). */
    fun failed(chapter: Int, segment: Int) {
        this.chapter = chapter
        this.segment = segment
        failedAt = clock()
    }

    /** Đoạn này vừa hỏng vì dịch vụ trục trặc? Có thì lượt đọc kế là lần hỏi mới - trả true một lần rồi quên. */
    fun takeFresh(chapter: Int, segment: Int): Boolean {
        if (chapter != this.chapter || segment != this.segment) return false
        this.chapter = -1
        this.segment = -1
        return true
    }

    /** Còn bao nhiêu ms nữa mới được hỏi lại đoạn này (0 = được ngay, hoặc đoạn này không vừa hỏng). */
    fun cooldownMs(chapter: Int, segment: Int): Long {
        if (chapter != this.chapter || segment != this.segment) return 0L
        return (REASK_MS - (clock() - failedAt) / 1_000_000).coerceIn(0L, REASK_MS)
    }

    fun clear() {
        chapter = -1
        segment = -1
    }
}
