package vn.abook.player.net

import java.io.Closeable
import java.io.FilterOutputStream
import java.io.IOException
import java.io.OutputStream
import java.net.HttpURLConnection
import java.net.SocketTimeoutException
import java.util.concurrent.ScheduledFuture
import java.util.concurrent.ScheduledThreadPoolExecutor
import java.util.concurrent.TimeUnit

/**
 * MỘT chính sách chờ cho mọi lời gọi từ điện thoại tới máy đã ghép (máy tính, thiết bị khác); bản cho máy tính: web `shared/hostWait.ts`, Qt `hostwait.h` + `hostcall.cpp`.
 * Lời gọi hỏng khi KHÔNG CÓ BYTE NÀO về trong [idleMs], không phải sau một tổng thời gian: tải dài mà byte vẫn về thì không bị cắt. Máy kia im quá hạn thì lời gọi được
 * gửi lại đúng một lần ([call]), im nữa thì báo [Timeout] (lý do "timeout", không phải "mất mạng"; là [SocketTimeoutException] nên mọi nơi đang xử lý hết giờ - [vn.abook.player.NetErrors] -
 * vẫn đúng). Quy tắc máy dò (HostWaitRulesTest): lời gọi tới máy đã ghép đi qua [open], không tự đặt hạn đọc.
 *
 * Hạn "không byte nào" do chính `readTimeout` của kết nối canh (mỗi lần đọc một hạn), nên [open] đặt nó và [awaiting] biến lần hết hạn đó thành [Timeout]. Phần GHI (gửi tệp lên)
 * HttpURLConnection không có hạn nào: [writing] canh bằng đồng hồ riêng, mỗi khúc ghi được là một lần "còn sống".
 */
object HostWait {
    const val IDLE_MS = 30_000

    /**
     * Việc nặng: máy tính làm xong cả việc rồi mới trả lời nên suốt lúc đó không byte nào về - đọc giọng (hạn Edge của chính máy tính là 90 s + 1 s: lỗi kèm lý do của nó luôn tới
     * trước), quét/tách nguồn, kể ngôi "tôi", tạo sách, dựng lại nhạc, nghe thử cách đọc. Hạn ngắn hơn sẽ cắt việc dài mà vẫn khoẻ rồi gửi lại.
     */
    const val LONG_IDLE_MS = 100_000
    const val ATTEMPTS = 2

    /** Chốt chặn cuối của trình phát: chờ âm thanh lâu thế này nghĩa là mọi lời gọi ở dưới đã có lượt báo lỗi của nó. */
    const val STALL_MS = ATTEMPTS * LONG_IDLE_MS + 15_000L

    const val TIMEOUT_MESSAGE = "Máy chưa trả lời kịp."
    const val TIMEOUT_REASON = "timeout"

    /** Bài thử đặt hạn ngắn thay cho hạn của chính sách (> 0). */
    @Volatile internal var idleOverrideMs = 0

    /** Máy kia im quá hạn ở mọi lượt gửi. Cùng lý do với hạn của chính máy tính (504, "timeout"). */
    class Timeout(cause: Throwable? = null) : SocketTimeoutException(TIMEOUT_MESSAGE) {
        val reason: String get() = TIMEOUT_REASON

        init { if (cause != null) initCause(cause) }
    }

    /** Danh sách việc nặng, giống từng chữ ở web `shared/hostWait.ts` và Qt `hostwait.h` (tests/test_host_wait_parity.py); `*` là đúng một đoạn đường dẫn. */
    val LONG_WORK = listOf(
        "/api/readaloud/clip",
        "/api/books/*/voice/preview",
        "/api/books/*/pronunciation/preview",
        "/api/books/*/music/rebuild",
        "/api/books/*/music",
        "/api/books/*/edits/fold",
        "/api/scan",
        "/api/sources/split",
        "/api/first-person",
        "/api/books",
        "/sync/v1/books/*/edits",
    )

    /** Đường dẫn (bỏ phần `?...`) khớp một mục của [LONG_WORK]. */
    fun isLongWork(path: String): Boolean {
        val parts = path.substringBefore('?').split('/')
        return LONG_WORK.any { pattern ->
            val want = pattern.split('/')
            want.size == parts.size && want.indices.all { want[it] == "*" || want[it] == parts[it] }
        }
    }

    fun idleMs(path: String): Int = if (idleOverrideMs > 0) idleOverrideMs else if (isLongWork(path)) LONG_IDLE_MS else IDLE_MS

    /** Cửa DUY NHẤT mở kết nối HTTP tới máy đã ghép: [FastConnect.open] với hạn đọc = hạn "không byte nào" của lời gọi. */
    fun open(url: String, connectTimeoutMs: Int, idleMs: Int = if (idleOverrideMs > 0) idleOverrideMs else IDLE_MS): HttpURLConnection =
        FastConnect.open(url, connectTimeoutMs).also { it.readTimeout = idleMs }

    /**
     * Chạy một lượt gửi + nhận. [Timeout] (từ [awaiting] / [writing]) thì gửi lại đúng lượt ấy một lần; `resend` false (tệp lên không phát lại được, hay lời gọi người gọi tự
     * đặt hạn riêng) thì báo ngay. Lỗi khác đi thẳng ra, không gửi lại.
     */
    fun <T> call(resend: Boolean = true, attempt: () -> T): T {
        val tries = if (resend) ATTEMPTS else 1
        var done = 0
        while (true) {
            try {
                return attempt()
            } catch (error: Timeout) {
                if (++done >= tries) throw error
            }
        }
    }

    /**
     * Nối rồi đọc (`read` thường là mã trả lời + thân): lỗi lúc NỐI là của đường mạng (không tới được máy) và đi nguyên; hết hạn `readTimeout` SAU khi đã nối là máy kia im - [Timeout].
     * Lỗi nối phải tách riêng vì cả hai đều là [SocketTimeoutException]: máy tắt thì vẫn là "không tới được", không phải "chưa trả lời kịp".
     */
    fun <T> awaiting(connection: HttpURLConnection, read: () -> T): T {
        connection.connect()
        try {
            return read()
        } catch (error: Timeout) {
            throw error
        } catch (error: SocketTimeoutException) {
            throw Timeout(error)
        }
    }

    /** Ghi thân gửi lên: không khúc nào ghi được trong `idleMs` (máy kia không đọc nữa) thì đóng kết nối và báo [Timeout]. `write` gọi `alive()` sau mỗi khúc đã ghi. */
    fun <T> writing(connection: HttpURLConnection, idleMs: Int, write: (alive: () -> Unit) -> T): T {
        Watch(idleMs) { connection.disconnect() }.use { watch ->
            try {
                return write(watch::alive)
            } catch (error: IOException) {
                if (watch.fired) throw Timeout(error)
                throw error
            }
        }
    }

    /** `out` báo `alive` sau mỗi khúc ghi xong. */
    fun counting(out: OutputStream, alive: () -> Unit): OutputStream = object : FilterOutputStream(out) {
        override fun write(b: Int) { out.write(b); alive() }
        override fun write(b: ByteArray, off: Int, len: Int) { out.write(b, off, len); alive() }
    }

    private val timer = ScheduledThreadPoolExecutor(1) { task -> Thread(task, "host-wait").apply { isDaemon = true } }.apply { removeOnCancelPolicy = true }

    /** Đồng hồ "im lặng": [alive] đặt lại; quá `idleMs` không ai gọi thì chạy `onStall` một lần. */
    internal class Watch(private val idleMs: Int, private val onStall: () -> Unit) : Closeable {
        @Volatile private var last = System.nanoTime()
        @Volatile private var closed = false
        @Volatile var fired = false
            private set
        @Volatile private var task: ScheduledFuture<*>? = null

        init { arm(idleMs.toLong()) }

        fun alive() { last = System.nanoTime() }

        private fun arm(delayMs: Long) { task = timer.schedule({ check() }, delayMs, TimeUnit.MILLISECONDS) }

        private fun check() {
            if (closed) return
            val quiet = TimeUnit.NANOSECONDS.toMillis(System.nanoTime() - last)
            if (quiet < idleMs) return arm(idleMs - quiet)
            fired = true
            try { onStall() } catch (_: RuntimeException) { }
        }

        override fun close() {
            closed = true
            task?.cancel(false)
        }
    }
}
