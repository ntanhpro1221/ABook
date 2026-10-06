package vn.abook.player

/**
 * Bài nhạc nền không phát được -> lúc được thử lại (đồng hồ `now`, mili-giây; MusicBed dùng SystemClock.elapsedRealtime): tải hỏng
 * (mất mạng) thì sau [RETRY_MS], file hỏng thì không bao giờ trong phiên. Phát được thì xoá. Cùng luật với RETRY_MS của
 * ui/src/listen/musicBed.ts.
 */
class MusicFailures(private val now: () -> Long) {
    private val retryAt = mutableMapOf<String, Long>()

    /** `retry`: tải hỏng - thử lại sau [RETRY_MS]; không thì cả phiên. */
    fun drop(link: String, retry: Boolean) {
        retryAt[link] = if (retry) now() + RETRY_MS else Long.MAX_VALUE
    }

    fun isFailed(link: String): Boolean = (retryAt[link] ?: return false) > now()

    /** Bỏ các bài đã tới hạn thử lại khỏi danh sách hỏng; trả các bài ấy. */
    fun takeDue(): Set<String> {
        val time = now()
        val due = retryAt.filterValues { it <= time }.keys.toSet()
        retryAt.keys.removeAll(due)
        return due
    }

    /** Bài vừa phát được. */
    fun forget(link: String) {
        retryAt.remove(link)
    }

    fun clear() = retryAt.clear()

    companion object {
        const val RETRY_MS = 5 * 60_000L
    }
}
