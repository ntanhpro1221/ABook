package vn.abook.player.readaloud

/**
 * Thử lại một đoạn đọc hỏng vì lỗi thoáng qua của giọng trực tuyến (Edge cắt lượt / bận / chậm - [VoiceException.transient]): nghỉ lùi dần rồi đọc lại, ở luồng nền, để các đoạn đã nạp
 * vẫn phát và người nghe chỉ phải dừng khi hết lần thử (cùng luật với máy tính, listen/readAloud.ts). Lỗi khác (mất mạng, bị từ chối, khoá / giọng hỏng, lời cuối của [ClipReader]) và giọng
 * chạy trên máy: trả ngay như trước, không thử lại.
 */
object ClipRetry {
    /**
     * `attempt(willRetry)`: một lần đọc; `willRetry` bật ở mọi lần trừ lần cuối - [ClipReader.read] khi ấy ném lỗi thoáng qua lên nguyên vẹn thay vì cho giọng nghỉ / rơi sang giọng khác.
     * `sleep(ms)`: nghỉ, trả false nếu việc đã cũ (tua, đổi chương, đổi giọng) - dừng ngay. `record(ms)`: số đo thời gian lấy clip cho [ReadAheadPolicy] (lượt thành công, và lượt hỏng mà
     * đã chờ từ [ReadAheadPolicy.SLOW_MS]).
     */
    fun run(online: Boolean, delaysMs: LongArray, sleep: (Long) -> Boolean, record: (Long) -> Unit = {}, clock: () -> Long = System::nanoTime, attempt: (Boolean) -> Clip): Result<Clip> {
        var tries = 0
        while (true) {
            val began = clock()
            val outcome = runCatching { attempt(online && tries < delaysMs.size) }
            val spentMs = (clock() - began) / 1_000_000
            val error = outcome.exceptionOrNull() as? VoiceException
            if (online && (outcome.isSuccess || spentMs >= ReadAheadPolicy.SLOW_MS)) record(spentMs)
            if (error == null || !online || !error.transient || tries >= delaysMs.size) return outcome
            if (!sleep(delaysMs[tries])) return outcome
            tries += 1
        }
    }
}
