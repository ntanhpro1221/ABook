package vn.abook.player

import androidx.media3.exoplayer.DefaultLoadControl
import androidx.media3.exoplayer.LoadControl

/**
 * Tốc độ tải của một bài nhạc stream từ máy kia (http, [Streaming.chapterUri]): ExoPlayer phát dần như `<audio src>` của web và bài đang tải dở
 * của bản Qt - bài vào mà tải không kịp thì đệm cạn giữa bài, tiếng tắt phụt rồi bật phụt. Đo bằng trung bình trượt [WINDOW_MS] của phần đã đệm
 * (giây bài tải được mỗi giây đồng hồ); đợt dồn [BURST_MS] đầu (phần bộ đệm đĩa / máy chủ đã có sẵn) gộp vào mốc gốc. Cổng vào là [playsThrough]:
 * cùng công thức, cùng hằng số với `keepsUp` của musicmixer.cpp và `playsThrough` của musicBed.ts.
 */
internal class StreamPace {
    private val samples = ArrayDeque<Pair<Long, Long>>()
    private var began = -1L

    fun add(nowMs: Long, bufferedMs: Long) {
        // Phần đã đệm lùi (tua sang chỗ chưa tải): đo lại từ đầu.
        if (began < 0 || samples.lastOrNull()?.let { bufferedMs < it.second - 50 } == true) { began = nowMs; samples.clear() }
        if (nowMs - began < BURST_MS) samples.clear()
        samples.addLast(nowMs to bufferedMs)
        while (samples.size > 2 && nowMs - samples[1].first > WINDOW_MS) samples.removeFirst() // giữ một mẫu ngay trước cửa sổ làm mốc đầu
    }

    /** Giây bài tải được mỗi giây đồng hồ trong [WINDOW_MS] vừa qua, tính tới bây giờ (nguồn đứng thì tụt dần về 0); null khi chưa đo đủ 1 giây. */
    fun rate(nowMs: Long): Double? {
        val first = samples.lastOrNull { nowMs - it.first > WINDOW_MS } ?: samples.firstOrNull() ?: return null
        val span = nowMs - first.first
        if (span < 1000) return null
        return (samples.last().second - first.second).toDouble() / span
    }

    /**
     * Phát từ `fromMs` tới hết bài mà không hụt, nếu tốc độ tải giữ ở trung bình trượt chia [MARGIN]: đã đệm `bufferedMs` + rate/lề·t, phát tới from + t - cả hai
     * tuyến tính theo t, nên chỉ cần đúng bây giờ (có sẵn [LEAD_MS] trước con trỏ) và lúc phát hết. Chưa đo được tốc độ: chưa chắc, coi như không.
     */
    fun playsThrough(nowMs: Long, bufferedMs: Long, fromMs: Long, durationMs: Long): Boolean {
        if (whole(bufferedMs, durationMs)) return true
        val rate = rate(nowMs) ?: return false
        return durationMs > 0 && bufferedMs - fromMs >= LEAD_MS && rate > 0 && (durationMs - bufferedMs) / rate * MARGIN <= durationMs - fromMs
    }

    companion object {
        const val WINDOW_MS = 8000L
        const val BURST_MS = 500L
        const val MARGIN = 1.3
        const val LEAD_MS = 2000L   // phần phải có sẵn trước con trỏ lúc vào
        const val FADE_MS = 300L    // hụt thì mờ ra / phát được tới hết bài lại thì mờ vào trong chừng này, không tắt / bật phụt
        const val LOW_MS = 1000L    // phần đệm trước còn dưới chừng này mà tốc độ tụt: bắt đầu mờ ra, tới 0 thì tạm dừng tại chỗ
        /** ExoPlayer mặc định chỉ đệm 50 s phía trước rồi ngừng tải: bài dài tải chậm không bao giờ có đủ để qua cổng. Đệm tới chừng này (cỡ cả bài). */
        const val BUFFER_MS = 180_000

        fun whole(bufferedMs: Long, durationMs: Long): Boolean = durationMs > 0 && bufferedMs >= durationMs - 250

        /** Bộ đệm của trình phát nhạc stream: tải liền tới [BUFFER_MS] phía trước, kể cả lúc đứng chờ cổng (tạm dừng). */
        fun loadControl(): LoadControl = DefaultLoadControl.Builder()
            .setBufferDurationsMs(BUFFER_MS, BUFFER_MS, 2500, 5000)
            .setPrioritizeTimeOverSizeThresholds(true)
            .build()
    }
}
