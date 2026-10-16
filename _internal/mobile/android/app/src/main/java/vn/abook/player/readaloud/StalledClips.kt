package vn.abook.player.readaloud

/**
 * Đoạn đọc hỏng vì dịch vụ trục trặc (Edge cắt lượt / bận / chậm - reason "service" / "timeout", kể cả lời cuối `final` của [ClipReader]) sau khi hết lần thử lại ([ClipRetry]) mà người nghe
 * CHƯA tới đoạn ấy: không dừng, nhưng cũng không bỏ cuộc vĩnh viễn như trước (soát a46 trên máy tính: Edge sống lại sau 28 giây, người nghe tới đoạn hỏng lúc 39,5 giây mà vẫn bị dừng vì chưa ai
 * hỏi lại - bấm "Thử lại" là xong ngay). Luật chung với máy tính (listen/readAloud.ts `gaveUp` / `probe`):
 *  - lượt đọc kế của đúng đoạn ấy là lần hỏi MỚI ([takeFresh] -> `ClipReader.read(fresh = true)`: quên lệnh nghỉ của giọng, quỹ thử lại tính lại);
 *  - trong lúc người nghe còn âm thanh để nghe, cứ [REASK_MS] mới hỏi lại một lần ([cooldownMs]) - mất mạng dài không thành bão lượt gọi;
 *  - hàng đợi cạn (người nghe tới nơi) thì hỏi ngay, không chờ nhịp ([ReadAloud.pump]); lần hỏi mới ấy hỏng nữa mới dừng và báo.
 * Lần hỏi theo nhịp lúc người nghe còn âm thanh là "hỏi thăm" ([isProbe]): MỘT lượt gọi, không thử lại, không giữ khoá CPU / Wi-Fi - như `probe` ở máy tính (đã hỏng thì hỏi tiếp cũng chỉ
 * để biết dịch vụ sống lại chưa; thử lại ba lần giữ khoá cả phút trong lúc chẳng ai chờ). Đoạn CHƯA TỚI hỏng vì BẤT KỲ lỗi giọng nào cũng không dừng nghe khi còn âm thanh ([verdict]); máy tính cũng im
 * lặng với mọi lỗi của đoạn chưa tới (listen/readAloud.ts, `index !== this.target.index`).
 */
class StalledClips(private val clock: () -> Long = System::nanoTime) {
    /** Việc phải làm khi một đoạn hết cách đọc: [FAIL] dừng và báo lỗi; [DEFER] chưa ai chờ đoạn ấy - nhớ lại, [ReadAloud.pump] hỏi lại sau; [QUIET] người nghe đã tạm dừng - bấm phát thì xin lại. */
    enum class Verdict { FAIL, DEFER, QUIET }

    companion object {
        /** Hỏi lại một đoạn đã hết lần thử cách nhau ít nhất chừng này (ms) khi người nghe còn âm thanh. */
        const val REASK_MS = 10_000L

        /** Lỗi thuộc loại "dịch vụ trục trặc" (không tính mất mạng / bị từ chối / khoá hỏng: hỏi lại cũng vô ích hay đã có đường riêng). */
        fun isServiceTrouble(error: Throwable?): Boolean = error is VoiceException && error.reason in VoiceException.TRANSIENT_REASONS

        /** Không thử lại lần nào: dùng cho lần hỏi thăm ([isProbe]). */
        val NO_RETRY = LongArray(0)

        /** Lần hỏi này là hỏi thăm ngầm? Đoạn vừa hỏng (`fresh`: [takeFresh]) mà người nghe còn âm thanh - chưa ai chờ đoạn ấy. Người nghe tới nơi (hàng đợi cạn) thì là hỏi thật, có thử lại. */
        fun isProbe(fresh: Boolean, listenerHasAudio: Boolean): Boolean = fresh && listenerHasAudio

        /** Nghỉ giữa các lần thử lại của lượt đọc này: hỏi thăm thì không có lần nào. */
        fun delaysFor(probe: Boolean, normal: LongArray): LongArray = if (probe) NO_RETRY else normal

        /** Giữ khoá CPU / Wi-Fi ([FetchWake]) cho lượt đọc này? Chỉ khi người nghe ĐANG CHỜ qua mạng: hỏi thăm lúc người nghe còn âm thanh thì không (ExoPlayer đang giữ khoá của nó). */
        fun holdsWake(online: Boolean, listenerWants: Boolean, probe: Boolean): Boolean = online && listenerWants && !probe

        /**
         * `error`: lỗi cuối của đoạn; `wantsPlay`: người nghe đang muốn nghe; `listenerHasAudio`: còn âm thanh để nghe (đoạn này chưa phải của họ); `probe`: lượt này là hỏi thăm.
         * Lỗi dịch vụ trục trặc: im lặng nếu đã tạm dừng, hoãn nếu còn âm thanh, dừng nếu hàng đợi cạn. Lỗi giọng KHÁC (mất mạng, bị từ chối, khoá...): vẫn hoãn khi người nghe đang nghe và còn
         * âm thanh (a50: trước đây dừng ngay dù còn cả hàng đoạn đã đọc sẵn; máy tính im lặng với mọi lỗi của đoạn chưa tới), còn lại dừng như trước. Hỏi thăm hỏng thì không bao giờ dừng:
         * người nghe tới nơi thì [ReadAloud.pump] hỏi thật, có thử lại.
         */
        fun verdict(error: Throwable?, wantsPlay: Boolean, listenerHasAudio: Boolean, probe: Boolean): Verdict = when {
            probe || isServiceTrouble(error) -> if (!wantsPlay) Verdict.QUIET else if (probe || listenerHasAudio) Verdict.DEFER else Verdict.FAIL
            error is VoiceException && wantsPlay && listenerHasAudio -> Verdict.DEFER
            else -> Verdict.FAIL
        }
    }

    private var chapter = -1
    private var segment = -1
    private var failedAt = 0L

    /** Ghi nhớ đoạn (`chapter`, `segment`) vừa hỏng vì dịch vụ trục trặc. Một đoạn một lúc: đoạn khác hỏng thì quên đoạn cũ (đọc theo thứ tự nên chỉ có một đoạn đang chờ nạp). */
    fun failed(chapter: Int, segment: Int) {
        this.chapter = chapter
        this.segment = segment
        failedAt = clock()
    }

    /** Đoạn này vừa hỏng vì dịch vụ trục trặc? Có thì lượt đọc kế là lần hỏi mới - trả true một lần rồi quên. */
    fun takeFresh(chapter: Int, segment: Int): Boolean {
        if (chapter != this.chapter || segment != this.segment) return false
        this.chapter = -1
        this.segment = -1
        return true
    }

    /** Còn bao nhiêu ms nữa mới được hỏi lại đoạn này (0 = được ngay, hoặc đoạn này không vừa hỏng). */
    fun cooldownMs(chapter: Int, segment: Int): Long {
        if (chapter != this.chapter || segment != this.segment) return 0L
        return (REASK_MS - (clock() - failedAt) / 1_000_000).coerceIn(0L, REASK_MS)
    }

    fun clear() {
        chapter = -1
        segment = -1
    }
}

/**
 * Một hẹn giờ trên luồng chính (`postDelayed` / `removeCallbacks` do người gọi đưa vào, để kiểm thử không cần Looper): một hẹn một lúc, gỡ được. [ReadAloud.remind] hẹn [ReadAloud.pump] sau
 * nhịp nghỉ của [StalledClips]; mỗi lần nhảy (tua, đổi chương, đổi giọng) hẹn cũ phải bỏ ([cancel]) - nếu để lại, cờ "đang hẹn" của nó chặn hẹn mới của đoạn sau khi tua tới khi hẹn cũ nổ (a50 mục 7).
 */
class Reminder(private val postDelayed: (Runnable, Long) -> Unit, private val removeCallbacks: (Runnable) -> Unit) {
    private var pending: Runnable? = null

    /** Hẹn `action` sau `ms`; đã có hẹn thì bỏ qua (một hẹn một lúc). */
    fun schedule(ms: Long, action: () -> Unit) {
        if (pending != null) return
        val task = object : Runnable {
            override fun run() {
                if (pending === this) pending = null
                action()
            }
        }
        pending = task
        postDelayed(task, ms)
    }

    /** Bỏ hẹn đang chờ (nếu có): hẹn mới đặt được ngay. */
    fun cancel() {
        pending?.let(removeCallbacks)
        pending = null
    }
}
