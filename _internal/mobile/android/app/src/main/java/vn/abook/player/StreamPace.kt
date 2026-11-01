package vn.abook.player

import androidx.media3.exoplayer.DefaultLoadControl
import androidx.media3.exoplayer.LoadControl

/**
 * Tốc độ tải của một bài nhạc stream từ máy kia (http, [Streaming.chapterUri]): ExoPlayer phát dần như `<audio src>` của web và bài đang tải dở
 * của bản Qt - bài vào mà tải không kịp thì đệm cạn giữa bài, tiếng tắt phụt rồi bật phụt. Đo bằng trung bình trượt [MusicMix.underrunRateWindowMs] của phần đã đệm
 * (giây bài tải được mỗi giây đồng hồ); đợt dồn [MusicMix.underrunBurstMs] đầu (phần bộ đệm đĩa / máy chủ đã có sẵn) gộp vào mốc gốc. Cổng vào là
 * [playsThrough]: cùng công thức, cùng hằng số (music_mix.json, khoá underrun*) với `keepsUp` của musicmixer.cpp và `playsThrough` của musicBed.ts.
 */
internal class StreamPace {
    private val mix = MusicCues.mix
    private val samples = ArrayDeque<Pair<Long, Long>>()
    private var began = -1L
    private var lastNow = 0L
    private var lastPosition = 0L

    /** `bufferedMs`: đã đệm tới (ms của bài), `positionMs`: con trỏ phát lúc `nowMs`. */
    fun add(nowMs: Long, bufferedMs: Long, positionMs: Long) {
        // Phần đã đệm lùi, hay con trỏ nhảy (tua; lần READY đầu dời bài đang chờ tới giây của giọng - emulator 02-11: đã đệm nhảy 2,4 -> 11 s trong tích tắc,
        // trung bình trượt coi là tải được 8,5 s, bài 11 KB/s qua cổng với 2 s đệm rồi mờ ra ngay): đo lại từ đầu.
        val jumped = began >= 0 && (positionMs < lastPosition - 50 || positionMs > lastPosition + (nowMs - lastNow) + 1000)
        if (began < 0 || jumped || samples.lastOrNull()?.let { bufferedMs < it.second - 50 } == true) { began = nowMs; samples.clear() }
        lastNow = nowMs
        lastPosition = positionMs
        if (nowMs - began < mix.underrunBurstMs) samples.clear()
        samples.addLast(nowMs to bufferedMs)
        while (samples.size > 2 && nowMs - samples[1].first > mix.underrunRateWindowMs) samples.removeFirst() // giữ một mẫu ngay trước cửa sổ làm mốc đầu
    }

    /** Giây bài tải được mỗi giây đồng hồ trong [MusicMix.underrunRateWindowMs] vừa qua, tính tới bây giờ (nguồn đứng thì tụt dần về 0); null khi chưa đo đủ 1 giây. */
    fun rate(nowMs: Long): Double? {
        val first = samples.lastOrNull { nowMs - it.first > mix.underrunRateWindowMs } ?: samples.firstOrNull() ?: return null
        val span = nowMs - first.first
        if (span < 1000) return null
        return (samples.last().second - first.second).toDouble() / span
    }

    /**
     * Phát từ `fromMs` tới `endMs` của bài (chỗ bài thôi kêu: min(độ dài, [MusicCues.playEnd])) mà không hụt, nếu tốc độ tải giữ ở trung bình trượt chia
     * [MusicMix.underrunMargin]: đã đệm `bufferedMs` + rate/lề·t, phát tới from + t - cả hai tuyến tính theo t, nên chỉ cần đúng bây giờ (có sẵn
     * [MusicMix.underrunLeadMs] trước con trỏ) và lúc tới `endMs`. Đã đệm tới `endMs` thì qua luôn. Chưa đo được tốc độ: chưa chắc, coi như không.
     */
    fun playsThrough(nowMs: Long, bufferedMs: Long, fromMs: Long, endMs: Long): Boolean {
        if (whole(bufferedMs, endMs)) return true
        val rate = rate(nowMs) ?: return false
        return endMs > 0 && bufferedMs - fromMs >= mix.underrunLeadMs && rate > 0 && (endMs - bufferedMs) / rate * mix.underrunMargin <= endMs - fromMs
    }

    companion object {
        /** ExoPlayer mặc định chỉ đệm 50 s phía trước rồi ngừng tải: bài dài tải chậm không bao giờ có đủ để qua cổng. Đệm tới chừng này (cỡ cả bài). */
        const val BUFFER_MS = 180_000

        fun whole(bufferedMs: Long, durationMs: Long): Boolean = durationMs > 0 && bufferedMs >= durationMs - 250

        /**
         * Đệm phía trước đã đầy [BUFFER_MS] (trình phát ngừng tải vì đủ, không phải vì nguồn chậm): có sẵn chừng ấy thì phát được dù tốc độ đo thế nào.
         * Nói thẳng điều ấy thay vì suy từ `isLoading` = false: ExoPlayer còn ngừng tải vì lý do khác (lỗi chờ thử lại, lượt tải tiến dần tạm khép chờ hỏi
         * LoadControl), lúc ấy 2 s đệm không nói gì về tốc độ.
         */
        fun full(aheadMs: Long): Boolean = aheadMs >= BUFFER_MS - 5_000

        /** Bộ đệm của trình phát nhạc stream: tải liền tới [BUFFER_MS] phía trước, kể cả lúc đứng chờ cổng (tạm dừng). */
        fun loadControl(): LoadControl = DefaultLoadControl.Builder()
            .setBufferDurationsMs(BUFFER_MS, BUFFER_MS, 2500, 5000)
            .setPrioritizeTimeOverSizeThresholds(true)
            .build()
    }
}
