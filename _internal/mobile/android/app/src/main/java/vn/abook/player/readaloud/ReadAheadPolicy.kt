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
    fun needMore(aheadMs: List<Long>): Boolean {
        if (aheadMs.size < base) return true
        if (aheadMs.size >= maxOf(base, MAX_AHEAD)) return false
        return aheadMs.sum() < wantedMs()
    }
}
