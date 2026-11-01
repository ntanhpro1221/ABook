package vn.abook.player

/**
 * Hỏi mốc chương kế rồi tải sẵn bài mốc ĐẦU của nó khi chương này còn <= [WARM_SECONDS] (ui/src/listen/musicBed.ts NextChapterWarm, desktop_qt musicbed.h): chương mới
 * mở bằng bài đã nằm trên máy, không im lặng chờ tải (đo 15,5 giây trung vị trên máy tính trước khi có việc này, PLAN_lx §2). Chương kế chưa dựng xong / chưa có
 * danh mục / hỏi hỏng thì bỏ qua và hỏi lại sau [RETRY_MS]. Một luồng (luồng chính): `ask` trả lời trên luồng ấy.
 */
internal class NextChapterWarm(
    private val ask: (chapterId: Int, answer: (Answer?) -> Unit) -> Unit,
    private val warm: (link: String) -> Unit,
    private val now: () -> Long,
) {
    /** Lời đáp mốc của chương kế (null: hỏi hỏng). `first`: link bài mốc đầu, null khi chương không có nhạc. */
    data class Answer(val pending: Boolean, val unavailable: Boolean, val first: String?)

    private val done = HashSet<String>()
    private var asking: String? = null
    private val retryAt = HashMap<String, Long>()

    /** Gọi mỗi nhịp. `key`: chương đang nghe (cuốn:chương); `next`: mã chương kế (null = hết cuốn); `remaining`: giây còn lại của chương, <= 0 khi chưa biết. */
    fun update(key: String, next: Int?, remaining: Double) {
        if (next == null || !(remaining > 0) || remaining > WARM_SECONDS) return
        val ticket = "$key>$next"
        if (ticket in done || asking != null || (retryAt[ticket] ?: 0L) > now()) return
        asking = ticket
        ask(next) { answer ->
            if (asking == ticket) asking = null
            val first = answer?.takeIf { !it.pending }?.first
            when {
                first != null -> {
                    done.add(ticket)
                    warm(first)
                }
                answer == null || answer.pending || answer.unavailable -> retryAt[ticket] = now() + RETRY_MS
                else -> done.add(ticket) // chương kế không có nhạc
            }
        }
    }

    companion object {
        const val WARM_SECONDS = 120.0
        const val RETRY_MS = 15_000L
    }
}
