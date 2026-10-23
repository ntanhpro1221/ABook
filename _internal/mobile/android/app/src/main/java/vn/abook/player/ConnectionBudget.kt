package vn.abook.player

/**
 * Trần kết nối của cổng audio Cast (Dlna.Media), như `ConnectionBudget` của webui/cast.py: cổng nghe mọi card mạng và mã chỉ kiểm được sau khi đọc
 * xong header, nên máy lạ cùng LAN mở socket rồi im lặng (hay gửi từng byte) sẽ giữ worker mãi (soát a109 F3). Hàm thuần để test JVM.
 */
internal class ConnectionBudget(private val total: Int = MAX_CONNECTIONS, private val perIp: Int = MAX_PER_IP) {
    private val held = HashMap<String, Int>()

    @Synchronized
    fun take(who: String): Boolean {
        if (held.values.sum() >= total || (held[who] ?: 0) >= perIp) return false
        held[who] = (held[who] ?: 0) + 1
        return true
    }

    @Synchronized
    fun release(who: String) {
        val left = (held[who] ?: 0) - 1
        if (left > 0) held[who] = left else held.remove(who)
    }

    @Synchronized
    fun active(): Int = held.values.sum()

    companion object {
        /** Đang chạy + đang chờ trong hàng đợi. */
        const val MAX_CONNECTIONS = 24
        /** Một TV hay mở vài kết nối song song (HEAD + GET Range + bìa). */
        const val MAX_PER_IP = 6
        const val WORKERS = 16
        const val QUEUE = 8
        const val HEADER_DEADLINE_MS = 10_000L

        /** Thời gian còn lại (ms) để đọc xong header kể từ [startMs]; 0 hay âm = hết hạn. Deadline TỔNG, không phải từng lần đọc: đọc từng byte chậm
         *  vẫn bị cắt đúng hạn. */
        fun headerRemainingMs(startMs: Long, nowMs: Long, limitMs: Long = HEADER_DEADLINE_MS): Long = startMs + limitMs - nowMs
    }
}
