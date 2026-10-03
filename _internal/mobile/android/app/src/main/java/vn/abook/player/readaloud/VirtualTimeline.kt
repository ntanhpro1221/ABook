package vn.abook.player.readaloud

/**
 * Đồng hồ ẢO của một chương đọc to: chương là chuỗi đoạn, mỗi đoạn một đoạn âm thanh mà ExoPlayer phát riêng, nhưng giao diện (và thanh vị trí, lưu vị trí, hẹn
 * giờ hết chương) cần MỘT đồng hồ chạy từ đầu chương. Đoạn nào đã có âm thanh thì dùng độ dài thật; chưa có thì ước theo số ký tự (mặc định 14 ký tự mỗi
 * giây - ~tốc độ nói của giọng tiếng Việt ở tốc độ 1.0). Mốc đầu một đoạn chỉ phụ thuộc các đoạn đứng TRƯỚC nó, nên khi đoạn đang nghe và các đoạn sau được
 * đọc xong (độ dài thật thay ước lượng) vị trí đang nghe không nhảy; chỉ tổng độ dài chương co giãn.
 *
 * Thuần tính toán, không đụng Android (VirtualTimelineTest). Chạy trên một luồng (luồng chính).
 */
class VirtualTimeline(private val chars: IntArray, private val charsPerSecond: Double = DEFAULT_CHARS_PER_SECOND) {
    companion object {
        const val DEFAULT_CHARS_PER_SECOND = 14.0
        /** Ước lượng tối thiểu của một đoạn (ms) - đoạn một chữ vẫn chiếm thời gian. */
        const val MIN_ESTIMATE_MS = 400L
    }

    private val known = LongArray(chars.size) { -1L }
    /** starts[i] = tổng độ dài các đoạn trước i; starts[n] = tổng cả chương. Tính lại khi có đoạn mới biết độ dài. */
    private var starts = LongArray(chars.size + 1)
    private var dirty = true

    val size: Int get() = chars.size

    /** Đoạn `index` đã đọc xong, dài `ms` thật. */
    fun setDuration(index: Int, ms: Long) {
        if (known[index] == ms) return
        known[index] = ms.coerceAtLeast(0)
        dirty = true
    }

    fun isKnown(index: Int) = known[index] >= 0

    fun durationOf(index: Int): Long =
        if (known[index] >= 0) known[index] else Math.round(chars[index] * 1000.0 / charsPerSecond).coerceAtLeast(MIN_ESTIMATE_MS)

    private fun fresh(): LongArray {
        if (dirty) {
            var sum = 0L
            for (i in chars.indices) {
                starts[i] = sum
                sum += durationOf(i)
            }
            starts[chars.size] = sum
            dirty = false
        }
        return starts
    }

    /** Mốc bắt đầu đoạn `index` (ms từ đầu chương). */
    fun startOf(index: Int): Long = fresh()[index.coerceIn(0, chars.size)]

    fun endOf(index: Int): Long = startOf(index) + durationOf(index)

    /** Tổng độ dài chương: phần đã biết + ước lượng phần còn lại. */
    fun totalMs(): Long = fresh()[chars.size]

    /** Đoạn chứa mốc `ms` (kẹp vào đoạn đầu / đoạn cuối). Chương không có đoạn: 0. */
    fun segmentAt(ms: Long): Int {
        if (chars.isEmpty()) return 0
        val s = fresh()
        var low = 0
        var high = chars.size - 1
        while (low < high) {
            val mid = (low + high + 1) ushr 1
            if (s[mid] <= ms) low = mid else high = mid - 1
        }
        return low
    }

    /** Số đoạn đã biết độ dài thật. */
    fun knownCount(): Int = known.count { it >= 0 }
}
