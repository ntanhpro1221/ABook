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
     * `budgetMs`: trần tổng thời gian từ lần đọc đầu tới lúc bắt đầu một lần thử lại ([ClipBudget.BUDGET_MS]). `cancel`: để người gọi huỷ lượt đọc đang chạy (tua / đổi chương / dừng) - giọng
     * mạng đăng ký thứ cần đóng ngay (ổ cắm, [EdgeTts]) vào đó qua [ClipBudget.cancel]. `rank`: số đoạn người nghe phải nghe trước đoạn này (0 = đang đứng chờ đúng nó) - hết chỗ kết nối Edge thì các mảnh của đoạn gần
     * người nghe hơn đứng trước ([ConnectionSlots], [ClipBudget.rank]).
     */
    fun run(
        online: Boolean, delaysMs: LongArray, sleep: (Long) -> Boolean, record: (Long) -> Unit = {}, clock: () -> Long = System::nanoTime,
        budgetMs: Long = ClipBudget.BUDGET_MS, cancel: ClipCancel? = null, rank: Int = EdgePieces.RANK_BACKGROUND, attempt: (Boolean) -> Clip,
    ): Result<Clip> {
        var tries = 0
        val scope = ClipBudget.Scope(clock(), budgetMs, clock)
        scope.cancel = cancel
        val before = ClipBudget.enter(scope)
        val rankBefore = ClipBudget.enterRank(rank)
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
            ClipBudget.leaveRank(rankBefore)
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
        /** Huỷ của người gọi [ClipRetry.run] (null = không ai huỷ được). */
        var cancel: ClipCancel? = null

        fun remainingMs(): Long = budgetMs - (clock() - began) / 1_000_000

        /** Nghỉ `delayMs` rồi thử lại còn đủ [MIN_ATTEMPT_MS] không? */
        fun fits(delayMs: Long): Boolean = remainingMs() - delayMs >= MIN_ATTEMPT_MS
    }

    private val current = ThreadLocal<Scope?>()

    /** Quỹ của luồng này (null ngoài [ClipRetry.run]): để luồng phụ đọc song song các mảnh của một đoạn ([EdgeTts]) chạy trong cùng quỹ qua [inherit]. */
    fun current(): Scope? = current.get()

    private val rankHere = ThreadLocal<Int?>()

    /** [ConnectionSlots] rank của lượt đọc đang chạy ở luồng này (số đoạn người nghe phải nghe trước đoạn này; [EdgePieces.RANK_BACKGROUND] khi không ai nói). Luồng phụ của các mảnh nhận lại qua [enterRank]. */
    fun rank(): Int = rankHere.get() ?: EdgePieces.RANK_BACKGROUND

    /** Đặt rank của luồng này; trả rank cũ để [leaveRank]. */
    fun enterRank(rank: Int): Int? = rankHere.get().also { rankHere.set(rank) }

    fun leaveRank(before: Int?) = rankHere.set(before)

    /** Chỗ huỷ của lượt đọc đang chạy ở luồng này (null ngoài [ClipRetry.run] hay khi người gọi không đưa). */
    fun cancel(): ClipCancel? = current.get()?.cancel

    /** Chạy `block` ở luồng này trong quỹ `scope` (của luồng gọi - [current]); xong trả quỹ cũ. */
    fun <T> inherit(scope: Scope?, block: () -> T): T {
        val before = current.get()
        current.set(scope)
        try {
            return block()
        } finally {
            current.set(before)
        }
    }

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

/**
 * Huỷ MỘT lượt đọc clip đang chạy ở luồng nền (người nghe tua / đổi chương / đổi giọng / dừng: kết quả sẽ bị bỏ): thứ nó đang giữ - ổ cắm SSL của các mảnh Edge, mỗi cái giữ một chỗ trong
 * [EdgeTts.connections] tới 15-45 giây - đóng NGAY thay vì chạy nốt lượt. Giọng đăng ký thứ cần đóng bằng [register] (đã huỷ rồi thì đóng liền) và gỡ bằng [unregister] khi xong.
 * Luồng đọc nhận [CancellationException] (không phải [VoiceException]): không thử lại, không rơi sang giọng kế.
 */
class ClipCancel {
    @Volatile var cancelled = false
        private set
    private val closers = java.util.concurrent.CopyOnWriteArraySet<AutoCloseable>() // duyệt trên bản chụp: đăng ký / gỡ từ luồng khác lúc huỷ không làm hỏng vòng lặp

    fun register(closer: AutoCloseable) {
        closers.add(closer)
        if (cancelled && closers.remove(closer)) runCatching { closer.close() }
    }

    fun unregister(closer: AutoCloseable) {
        closers.remove(closer)
    }

    fun cancel() {
        cancelled = true
        for (closer in closers) if (closers.remove(closer)) runCatching { closer.close() }
    }
}
