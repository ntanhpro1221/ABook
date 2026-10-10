package vn.abook.player

/**
 * Bài nhạc nền không phát được -> lúc được thử lại (đồng hồ `now`, mili-giây; MusicBed dùng SystemClock.elapsedRealtime): phát hỏng
 * (mạng tới máy tính rớt) thì sau [RETRY_MS], file hỏng thì không bao giờ trong phiên. Phát được thì xoá. Cùng luật với RETRY_MS của
 * ui/src/listen/musicBed.ts. Bài danh mục tải hỏng ([dropDownload]) thì lùi dần và có hạn: không tải đi tải lại mãi trên 4G.
 */
class MusicFailures(private val now: () -> Long) {
    private val retryAt = mutableMapOf<String, Long>()
    private val downloads = mutableMapOf<String, Int>() // số lần tải hỏng liền nhau của mỗi bài

    /** `retry`: phát hỏng - thử lại sau [RETRY_MS]; không thì cả phiên. */
    fun drop(link: String, retry: Boolean) {
        retryAt[link] = if (retry) now() + RETRY_MS else Long.MAX_VALUE
    }

    /** Tải bài danh mục hỏng (mạng, nguồn gỡ bài): chờ [RETRY_MS], rồi gấp đôi mỗi lần hỏng tiếp; quá [DOWNLOAD_RETRIES] lần thử lại
     *  thì bỏ cả phiên. */
    fun dropDownload(link: String) {
        val failures = (downloads[link] ?: 0) + 1
        downloads[link] = failures
        retryAt[link] = if (failures > DOWNLOAD_RETRIES) Long.MAX_VALUE else now() + (RETRY_MS shl (failures - 1))
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
        downloads.remove(link)
    }

    fun clear() {
        retryAt.clear()
        downloads.clear()
    }

    companion object {
        const val RETRY_MS = 5 * 60_000L
        /** Bài tải hỏng được thử lại chừng ấy lần (sau 5, 10, 20 phút) rồi bỏ tới phiên sau. */
        const val DOWNLOAD_RETRIES = 3
    }
}
