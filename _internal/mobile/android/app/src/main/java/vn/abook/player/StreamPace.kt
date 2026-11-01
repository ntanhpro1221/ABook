package vn.abook.player

/**
 * Tốc độ tải của một bài nhạc stream từ máy kia (http, [Streaming.chapterUri]): ExoPlayer phát dần như `<audio src>` của web và bài đang tải dở
 * của bản Qt (musicmixer.cpp `keepsUp`) - bài vào mà tải không kịp thì đệm cạn giữa bài, tiếng tắt phụt rồi bật phụt. Đo bằng trung bình trượt
 * [WINDOW_MS] của phần đã đệm (giây bài tải được mỗi giây đồng hồ); đợt dồn [BURST_MS] đầu (phần bộ đệm đĩa / máy chủ đã có sẵn) gộp vào mốc gốc.
 * Kịp = tải trọn bài, hay tốc độ chia lề [MARGIN] vẫn >= tốc độ phát (1 giây bài mỗi giây).
 */
internal class StreamPace {
    private val samples = ArrayDeque<Pair<Long, Long>>()
    private var began = -1L

    fun add(nowMs: Long, bufferedMs: Long) {
        if (began < 0) began = nowMs
        if (nowMs - began < BURST_MS) samples.clear()
        samples.addLast(nowMs to bufferedMs)
        while (samples.size > 2 && nowMs - samples[1].first > WINDOW_MS) samples.removeFirst() // giữ một mẫu ngay trước cửa sổ làm mốc đầu
    }

    /** Giây bài tải được mỗi giây đồng hồ trong [WINDOW_MS] vừa qua; null khi chưa đo đủ 1 giây. */
    fun rate(nowMs: Long): Double? {
        val first = samples.lastOrNull { nowMs - it.first > WINDOW_MS } ?: samples.firstOrNull() ?: return null
        val span = nowMs - first.first
        if (span < 1000) return null
        return (samples.last().second - first.second).toDouble() / span
    }

    fun keepsUp(nowMs: Long, bufferedMs: Long, durationMs: Long): Boolean =
        whole(bufferedMs, durationMs) || (rate(nowMs) ?: 0.0) / MARGIN >= 1.0

    companion object {
        const val WINDOW_MS = 8000L
        const val BURST_MS = 500L
        const val MARGIN = 1.3
        const val FADE_MS = 300L    // hụt thì mờ ra / tải kịp lại thì mờ vào trong chừng này, không tắt / bật phụt
        const val LOW_MS = 1000L    // phần đệm trước còn dưới chừng này mà tải không kịp: bắt đầu mờ ra
        const val RESUME_MS = 3000L // vào (và vào lại sau khi hụt) khi đệm trước có chừng này VÀ tải kịp (hay đã tải trọn)
        const val SAFE_MS = 30_000L // đệm trước chừng này thì vào được dù chưa đo được tốc độ (ExoPlayer ngừng tải khi đệm đầy)

        fun whole(bufferedMs: Long, durationMs: Long): Boolean = durationMs > 0 && bufferedMs >= durationMs - 250
    }
}
