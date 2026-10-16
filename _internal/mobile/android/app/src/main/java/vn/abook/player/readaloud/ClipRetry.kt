package vn.abook.player.readaloud

/**
 * Thử lại một đoạn đọc hỏng vì lỗi thoáng qua của giọng trực tuyến (Edge cắt lượt / bận / chậm - [VoiceException.transient]): nghỉ lùi dần rồi đọc lại, ở luồng nền, để các đoạn đã nạp
 * vẫn phát và người nghe chỉ phải dừng khi hết lần thử (cùng luật với máy tính, listen/readAloud.ts). Lỗi khác (mất mạng, bị từ chối, khoá / giọng hỏng, lời cuối của [ClipReader]) và giọng
 * chạy trên máy: trả ngay như trước, không thử lại. Tổng thời gian thử lại một đoạn có trần ([ClipBudget]): mạng còn nối mà im lìm thì không bắt người nghe chờ cả phút.
 */
object ClipRetry {
    /**
     * `attempt(willRetry)`: một lần đọc; `willRetry` bật ở mọi lần trừ lần cuối - [ClipReader.read] khi ấy ném lỗi thoáng qua lên nguyên vẹn thay vì cho giọng nghỉ / rơi sang giọng khác (trừ
     * khi hết quỹ thời gian [ClipBudget]: lúc đó nó rơi sang giọng kế ngay, vì sẽ không có lần thử nào nữa). `sleep(ms)`: nghỉ, trả false nếu việc đã cũ (tua, đổi chương, đổi giọng) hay
     * người nghe đã tạm dừng - dừng ngay. `record(ms)`: số đo thời gian lấy clip cho [ReadAheadPolicy] (lượt thành công, và lượt hỏng mà đã chờ từ [ReadAheadPolicy.SLOW_MS]).
     * `budgetMs`: trần tổng thời gian từ lần đọc đầu tới lúc bắt đầu một lần thử lại ([ClipBudget.BUDGET_MS]).
     */
    fun run(
        online: Boolean, delaysMs: LongArray, sleep: (Long) -> Boolean, record: (Long) -> Unit = {}, clock: () -> Long = System::nanoTime,
        budgetMs: Long = ClipBudget.BUDGET_MS, attempt: (Boolean) -> Clip,
    ): Result<Clip> {
        var tries = 0
        val scope = ClipBudget.Scope(clock(), budgetMs, clock)
        val before = ClipBudget.enter(scope)
        try {
            while (true) {
                val began = clock()
                scope.retrying = tries > 0
                scope.nextDelayMs = if (online) delaysMs.getOrNull(tries) else null
                val outcome = runCatching { attempt(online && tries < delaysMs.size) }
                val spentMs = (clock() - began) / 1_000_000
                val error = outcome.exceptionOrNull() as? VoiceException
                if (online && ReadAheadPolicy.isMeasure(outcome.isSuccess, spentMs)) record(spentMs)
                if (error == null || !online || !error.transient || tries >= delaysMs.size) return outcome
                if (!scope.fits(delaysMs[tries]) || !sleep(delaysMs[tries])) return outcome
                tries += 1
            }
        } finally {
            ClipBudget.leave(before)
        }
    }
}

/**
 * Quỹ thời gian thử lại của MỘT đoạn (điện thoại; máy tính có `retryFits` ở listen/readAloud.ts): mạng còn nối mà dịch vụ im lìm (mỗi lần chờ tin 15 giây, cả lượt 45 giây) thì ba lần Edge tự thử
 * lại x ba lần ngoài [ClipRetry] làm người nghe chờ 50-140 giây trước khi được rơi sang giọng của máy hay thấy "Thử lại". Quỹ chung cho cả hai tầng, tính từ lần đọc đầu: một lần thử LẠI chỉ
 * bắt đầu nếu còn đủ [MIN_ATTEMPT_MS] sau quãng nghỉ của nó, và lần thử lại chỉ được chờ phần còn lại (tối thiểu [MIN_ATTEMPT_MS]). Lần đọc đầu không bị cắt (Edge chậm thật 9-24 giây vẫn xong).
 * Hết quỹ thì [ClipReader] rơi sang giọng kế ngay trong lần hỏng đó. Chỉ có hiệu lực trong [ClipRetry.run] (luồng nền đang đọc); ngoài ra mọi thứ như cũ.
 */
object ClipBudget {
    const val BUDGET_MS = 20_000L
    const val MIN_ATTEMPT_MS = 4_000L

    /** `began`/`clock` tính bằng nano giây. `retrying`: đang ở lần thử lại của [ClipRetry]; `nextDelayMs`: quãng nghỉ trước lần thử lại kế (null = không còn). */
    class Scope(val began: Long, val budgetMs: Long, val clock: () -> Long) {
        var retrying = false
        var nextDelayMs: Long? = null

        fun remainingMs(): Long = budgetMs - (clock() - began) / 1_000_000

        /** Nghỉ `delayMs` rồi thử lại còn đủ [MIN_ATTEMPT_MS] không? */
        fun fits(delayMs: Long): Boolean = remainingMs() - delayMs >= MIN_ATTEMPT_MS
    }

    private val current = ThreadLocal<Scope?>()

    /** Vào quỹ `scope` ở luồng này; trả quỹ ngoài (nếu có) để [leave]. */
    fun enter(scope: Scope): Scope? = current.get().also { current.set(scope) }

    fun leave(before: Scope?) = current.set(before)

    /** [ClipReader]: lần hỏng này, người gọi có thật sự thử lại không? Ngoài [within] (đọc song song): có. */
    fun retryFollows(): Boolean {
        val scope = current.get() ?: return true
        return scope.nextDelayMs?.let(scope::fits) ?: false
    }

    /** Lần Edge tự thử lại thêm sau `delayMs` còn nằm trong quỹ không? */
    fun fits(delayMs: Long): Boolean = current.get()?.fits(delayMs) ?: true

    /** Hạn (ms) cho một lượt gọi mạng: `full` cho lần đọc đầu; lần thử lại (của Edge hay của [ClipRetry]) chỉ được phần quỹ còn lại, tối thiểu [MIN_ATTEMPT_MS]. */
    fun attemptMs(full: Long, retry: Boolean): Long {
        val scope = current.get() ?: return full
        if (!retry && !scope.retrying) return full
        return minOf(full, maxOf(MIN_ATTEMPT_MS, scope.remainingMs()))
    }
}
