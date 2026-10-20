package vn.abook.player.readaloud

/**
 * Độ sâu đọc trước của giọng trực tuyến (cùng luật với `readAheadCount` ở listen/readAloud.ts): giọng Edge có lúc chậm 9-24 giây một đoạn (soát a45) mà hàng đợi chỉ
 * đọc sẵn [base] đoạn thì đoạn ngắn (đối thoại) chỉ đủ vài giây và giọng im ngay giữa chương. Ghi lại thời gian lấy clip THẬT của vài clip gần nhất; cần đọc sẵn tối thiểu [MIN_BUFFER_MS], và [FACTOR] lần thời gian lấy clip ở
 * phân vị 80 khi lớn hơn (tối đa [MAX_BUFFER_MS]) mili-giây âm thanh - đoạn ngắn thì cần nhiều đoạn hơn - nhưng không quá [MAX_AHEAD] đoạn (mỗi đoạn là một lượt gọi Edge, đoạn nào người nghe bỏ đi là uổng).
 * Chưa đủ số đo thì đúng [base] đoạn như trước. Lượt lấy từ bộ đệm (vài chục ms) không tính. An toàn giữa các luồng.
 */
class ReadAheadPolicy(private val base: Int) {
    companion object {
        const val MAX_AHEAD = 8
        const val FACTOR = 2.0
        const val MIN_BUFFER_MS = 20_000L
        const val MAX_BUFFER_MS = 60_000L
        const val REAL_FETCH_MS = 250L
        const val SAMPLES = 8
        /** Từ ngần này (p80 thời gian lấy một clip) giọng được coi là CHẬM: đáng đọc song song hai đoạn một lúc ([slow]). Edge bình thường ~0,6-2 s; lúc chậm 9-24 s. */
        const val SLOW_MS = 4_000L

        /** Giọng trên máy (uxfix72): đọc sẵn tới chừng này mili-giây âm thanh, không theo số đoạn - a65 (máy ảo, rtf ~0,22): hai dòng ngắn (hay lặp lại, lấy từ bộ đệm tức thì) đứng
         *  trước một đoạn dài 18 s là đủ "2 đoạn" mà chỉ có vài giây âm thanh, đoạn dài bắt đầu đọc khi chỉ còn ~3,9 s phía trước và cần 4 s - im 0,16-0,35 s. 20 s đủ cho một đoạn ~300 ký tự
         *  ở rtf tới ~1 (máy chậm). */
        const val LOCAL_BUFFER_MS = 20_000L
        /** Trần số đoạn đọc sẵn của giọng trên máy: đoạn người nghe nhảy qua là CPU / pin uổng. */
        const val LOCAL_MAX_AHEAD = 6

        /** Giọng trên máy: hàng đợi có `aheadMs` (các đoạn ĐÃ đọc xong sau đoạn đang nghe) - còn cần đọc thêm không? Tối thiểu `base` đoạn, rồi tới khi đủ [LOCAL_BUFFER_MS], tối đa [LOCAL_MAX_AHEAD] đoạn. */
        fun localNeedsMore(aheadMs: List<Long>, base: Int): Boolean = needsMore(aheadMs, base, LOCAL_MAX_AHEAD, LOCAL_BUFFER_MS)

        /** Mở chương bằng giọng trên máy (uxfix72): tiêu đề 2 giây phát xong trước khi đoạn đầu đọc xong - im giữa chừng (a65 máy ảo: Supertonic 1,44 s, Nano 0,74 s). Khoảng hụt ước từ
         *  ngần này trở lên thì dời nó vào lúc bắt đầu (người nghe chịu chờ lúc mở hơn là khựng giữa)... */
        const val OPENING_GAP_MS = 300L
        /** ...nhưng chờ thêm không quá ngần này (livejoin2: 1,5 -> 2,5 s - khe im sau tiêu đề tệ hơn chờ thêm 1 s lúc bắt đầu, a65: tiêu đề 3,34 s + 1,5 s vẫn thiếu ~0,8 s khúc đầu của Nano khi máy bận). */
        const val OPENING_HOLD_MAX_MS = 2_500L

        /**
         * Giữ clip đầu (tiêu đề, `firstMs` âm thanh) bao lâu trước khi phát, để đoạn kế vào được trước khi clip đầu hết (`nextChars` = số ký tự phải đọc trước đó: cả đoạn, hay chỉ các khúc đầu nếu đoạn phát luồng - [LocalLive.charsBeforeStart]; null: không có / đã có trong bộ đệm).
         * `secondsPerChar`: tốc độ đã đo của giọng (null: chưa đo - giữ tới trần, đoạn kế xong sớm thì phát sớm). 0 = phát ngay.
         */
        fun openingHoldMs(firstMs: Long, nextChars: Int?, secondsPerChar: Double?): Long {
            if (nextChars == null || nextChars <= 0) return 0L
            val gap = if (secondsPerChar == null) OPENING_HOLD_MAX_MS else (secondsPerChar * nextChars * 1000).toLong() - firstMs
            return if (gap < OPENING_GAP_MS) 0L else minOf(gap, OPENING_HOLD_MAX_MS)
        }

        private fun needsMore(aheadMs: List<Long>, base: Int, cap: Int, wantedMs: Long): Boolean {
            if (aheadMs.size < base) return true
            if (aheadMs.size >= maxOf(base, cap)) return false
            return aheadMs.sum() < wantedMs
        }

        /** Một lượt lấy clip đáng ghi làm số đo: lượt thành công, hay lượt hỏng mà đã chờ từ [SLOW_MS] (lượt hỏng tức thì không nói gì về tốc độ). Dùng chung cho [ClipRetry] và [measure]. */
        fun isMeasure(success: Boolean, spentMs: Long): Boolean = success || spentMs >= SLOW_MS
    }

    private val fetches = ArrayDeque<Long>()

    /**
     * Chạy một lượt gọi giọng trực tuyến và ghi thời gian THẬT của nó ([record], theo luật [isMeasure]). Dùng cho lượt đọc song song ([ReadAloud] warm): nếu chỉ lượt "chính" ghi số đo thì khi
     * Edge đã nhanh lại mà đoạn kế đã được đọc song song, lượt chính chỉ lấy từ bộ đệm (không tính) - số đo đứng yên và chế độ "Edge chậm" (2 luồng, đọc trước tới 8 đoạn) dính mãi.
     */
    fun <T> measure(clock: () -> Long = System::nanoTime, block: () -> Result<T>): Result<T> {
        val began = clock()
        val result = block()
        val spentMs = (clock() - began) / 1_000_000
        if (isMeasure(result.isSuccess, spentMs)) record(spentMs)
        return result
    }

    @Synchronized
    fun record(fetchMs: Long) {
        if (fetchMs < REAL_FETCH_MS) return
        fetches.addLast(fetchMs)
        while (fetches.size > SAMPLES) fetches.removeFirst()
    }

    @Synchronized
    fun reset() = fetches.clear()

    @Synchronized
    private fun p80(): Long? {
        if (fetches.size < 2) return null
        val sorted = fetches.sorted()
        return sorted[minOf(sorted.size - 1, Math.ceil(sorted.size * 0.8).toInt() - 1)]
    }

    /** Mili-giây âm thanh cần đọc sẵn phía trước; 0 khi chưa đủ số đo. */
    fun wantedMs(): Long = p80()?.let { minOf(MAX_BUFFER_MS, maxOf(MIN_BUFFER_MS, (FACTOR * it).toLong())) } ?: 0L

    /** Giọng đang chậm (p80 >= [SLOW_MS]): đọc song song đoạn kế bằng luồng thứ hai. */
    fun slow(): Boolean = (p80() ?: 0L) >= SLOW_MS

    /** Hàng đợi đã có `aheadMs` mili-giây (các đoạn ĐÃ nạp sau đoạn đang nghe, theo thứ tự) - còn cần nạp thêm đoạn nữa không? Tối thiểu [base] đoạn; hơn nữa chỉ khi chưa đủ [wantedMs] và chưa chạm [MAX_AHEAD]. */
    fun needMore(aheadMs: List<Long>): Boolean = needsMore(aheadMs, base, MAX_AHEAD, wantedMs())
}
