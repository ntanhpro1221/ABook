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
    /** Dự báo / thực tế lớn nhất đã thấy ở tầm một cửa sổ; null khi chưa đo đủ 2 cửa sổ. */
    private var worst: Double? = null

    /** `bufferedMs`: đã đệm tới (ms của bài), `positionMs`: con trỏ phát lúc `nowMs`. */
    fun add(nowMs: Long, bufferedMs: Long, positionMs: Long) {
        // Phần đã đệm lùi, hay con trỏ nhảy (tua; lần READY đầu dời bài đang chờ tới giây của giọng - emulator 02-11: đã đệm nhảy 2,4 -> 11 s trong tích tắc,
        // trung bình trượt coi là tải được 8,5 s, bài 11 KB/s qua cổng với 2 s đệm rồi mờ ra ngay): đo lại từ đầu.
        val jumped = began >= 0 && (positionMs < lastPosition - 50 || positionMs > lastPosition + (nowMs - lastNow) + 1000)
        if (began < 0 || jumped || samples.lastOrNull()?.let { bufferedMs < it.second - 50 } == true) { began = nowMs; samples.clear(); worst = null }
        lastNow = nowMs
        lastPosition = positionMs
        if (nowMs - began < mix.underrunBurstMs) samples.clear()
        samples.addLast(nowMs to bufferedMs)
        // Giữ hai cửa sổ (một mẫu ngay trước làm mốc đầu): cửa sổ trước là dự báo, cửa sổ sau là thực tế của dự báo ấy.
        val window = mix.underrunRateWindowMs
        while (samples.size > 2 && nowMs - samples[1].first > 2 * window) samples.removeFirst()
        if (samples.first().first <= nowMs - 2 * window) {
            fun at(t: Long) = samples.lastOrNull { it.first <= t }?.second ?: samples.first().second
            val forecast = at(nowMs - window) - at(nowMs - 2 * window)
            val real = bufferedMs - at(nowMs - window)
            val ratio = if (real > 0) forecast.toDouble() / real else if (forecast > 0) Double.POSITIVE_INFINITY else 1.0
            worst = maxOf(worst ?: 1.0, ratio)
        }
    }

    /**
     * Lề chia tốc độ đo được ([playsThrough]): dự báo theo trung bình trượt từng hụt tới đâu so với cái đã tới thật một cửa sổ sau, lấy lần tệ nhất, không quá
     * [MusicMix.underrunMargin]. Chưa đo đủ 2 cửa sổ thì là [MusicMix.underrunMargin]. Đường đều co về ~1: bài vào sớm hơn; đường dao động mạnh giữ đúng lề trần -
     * 76 vết HSDPA thật (Riiser 2013) mô phỏng đều chạm trần, nghe và hụt y như lề cố định (02-11). Cùng luật với musicBed.ts `DownloadPace.margin` và musicmixer.cpp.
     */
    fun margin(): Double = worst?.let { minOf(mix.underrunMargin, it) } ?: mix.underrunMargin

    /** Giây bài tải được mỗi giây đồng hồ trong [MusicMix.underrunRateWindowMs] vừa qua, tính tới bây giờ (nguồn đứng thì tụt dần về 0); null khi chưa đo đủ 1 giây. */
    fun rate(nowMs: Long): Double? {
        val first = samples.lastOrNull { nowMs - it.first > mix.underrunRateWindowMs } ?: samples.firstOrNull() ?: return null
        val span = nowMs - first.first
        if (span < 1000) return null
        return (samples.last().second - first.second).toDouble() / span
    }

    /**
     * Phát từ `fromMs` tới `endMs` của bài (chỗ bài thôi kêu: min(độ dài, [MusicCues.playEnd])) mà không hụt, nếu tốc độ tải giữ ở trung bình trượt chia
     * [margin] (lề đo được, trần [MusicMix.underrunMargin]): đã đệm `bufferedMs` + rate/lề·t, phát tới from + t - cả hai tuyến tính theo t, nên chỉ cần đúng bây giờ (có sẵn
     * [MusicMix.underrunLeadMs] trước con trỏ) và lúc tới `endMs`. Đã đệm tới `endMs` thì qua luôn. Chưa đo được tốc độ: chưa chắc, coi như không.
     */
    fun playsThrough(nowMs: Long, bufferedMs: Long, fromMs: Long, endMs: Long): Boolean {
        if (whole(bufferedMs, endMs)) return true
        val rate = rate(nowMs) ?: return false
        return endMs > 0 && bufferedMs - fromMs >= mix.underrunLeadMs && rate > 0 && (endMs - bufferedMs) / rate * margin() <= endMs - fromMs
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
