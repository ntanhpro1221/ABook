package vn.abook.player

/**
 * Hỏi mốc chương kế rồi tải sẵn bài mốc ĐẦU của nó ngay khi chương này đã biết độ dài (ui/src/listen/musicBed.ts NextChapterWarm, desktop_qt musicbed.h): chương mới
 * mở bằng bài đã nằm trên máy, không im lặng chờ tải (đo 15,5 giây trung vị trên máy tính trước khi có việc này, PLAN_lx §2). Không đợi tới hai phút cuối: nguồn
 * bài chậm (incompetech 29 KB/s trên emulator, đo 01-11) thì bài 6,2 MB mất 215 giây. Giọng trước: chỉ hỏi / tải khi giọng đã sẵn [VOICE_SECONDS] phía trước. Một lượt
 * mỗi lúc; chương kế chưa dựng xong / chưa có danh mục / hỏi hỏng thì hỏi lại sau [RETRY_MS]. [LAST_CHANCE_SECONDS] cuối chương: xin tải lại mỗi [RETRY_MS] (lần trước
 * hỏng thì lần này tải; bài đã có / đang tải thì `warm` bỏ qua). Một luồng (luồng chính): `ask` trả lời trên luồng ấy.
 */
internal class NextChapterWarm(
    private val ask: (chapterId: Int, answer: (Answer?) -> Unit) -> Unit,
    private val warm: (link: String) -> Unit,
    private val now: () -> Long,
) {
    /** Lời đáp mốc của chương kế (null: hỏi hỏng). `first`: link bài mốc đầu, null khi chương không có nhạc. */
    data class Answer(val pending: Boolean, val unavailable: Boolean, val first: String?)

    /** Vé đã có lời đáp -> link bài đầu chương kế (null: chương kế không có nhạc). */
    private val done = HashMap<String, String?>()
    private var asking: String? = null
    private val retryAt = HashMap<String, Long>()

    /** Gọi mỗi nhịp. `key`: chương đang nghe (cuốn:chương); `next`: mã chương kế (null = hết cuốn); `remaining`: giây còn lại của chương, <= 0 khi chưa biết;
     *  `voiceAhead`: giây giọng đã sẵn phía trước người nghe ([vn.abook.player.readaloud.ReadAloud.voiceAheadMs]). */
    fun update(key: String, next: Int?, remaining: Double, voiceAhead: Double = Double.POSITIVE_INFINITY) {
        if (next == null || !(remaining > 0) || !(voiceAhead >= VOICE_SECONDS)) return
        val ticket = "$key>$next"
        if (asking != null || (retryAt[ticket] ?: 0L) > now()) return
        if (ticket in done) {
            val link = done[ticket] ?: return
            if (remaining > LAST_CHANCE_SECONDS) return
            retryAt[ticket] = now() + RETRY_MS
            warm(link)
            return
        }
        asking = ticket
        ask(next) { answer ->
            if (asking == ticket) asking = null
            val first = answer?.takeIf { !it.pending }?.first
            when {
                first != null -> {
                    done[ticket] = first
                    retryAt[ticket] = now() + RETRY_MS // lưới cuối không xin lại ngay sau lần đầu
                    warm(first)
                }
                answer == null || answer.pending || answer.unavailable -> retryAt[ticket] = now() + RETRY_MS
                else -> done[ticket] = null // chương kế không có nhạc
            }
        }
    }

    /** Lượt tải `link` đứt vì đứng nhường giọng ([MusicCatalog.Yielded]): quên lời đáp để sau [RETRY_MS] hỏi + tải lại (vẫn qua cổng giọng) thay vì chờ lưới cuối. */
    fun again(link: String) {
        for (ticket in done.filterValues { it == link }.keys) {
            done.remove(ticket)
            retryAt[ticket] = now() + RETRY_MS
        }
    }

    companion object {
        const val RETRY_MS = 15_000L
        /** Giọng ưu tiên tuyệt đối: chỉ tải sẵn khi giọng đã sẵn chừng này giây phía trước (= đệm tối thiểu của giọng, [vn.abook.player.readaloud.ReadAheadPolicy.MIN_BUFFER_MS]). */
        const val VOICE_SECONDS = vn.abook.player.readaloud.ReadAheadPolicy.MIN_BUFFER_MS / 1000.0
        /** Lưới cuối: chương còn chừng này giây thì xin tải lại bài đầu chương kế mỗi [RETRY_MS]. */
        const val LAST_CHANCE_SECONDS = 120.0
    }
}
