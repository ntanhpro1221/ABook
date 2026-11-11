package vn.abook.player

/** Bước của một việc dài mà thanh tiến độ nói ra (chép file vào máy, kiểm mã băm từng phần, đọc chữ, thêm vào thư viện). */
enum class WorkStep { Copy, Check, Read, Add }

/**
 * Một lần báo tiến độ theo việc THẬT: bước đang làm, `done` / `total` của bước (byte; trang hay số file khi `bytes` = false; `total` <= 0 = chưa biết tổng),
 * và khoảng [from, to] của cả thanh mà bước ấy chiếm. Không có số đoán: chưa biết tổng thì [fraction] là null và thanh chạy liên tục.
 */
data class Work(val step: WorkStep, val done: Long = 0, val total: Long = 0, val from: Float = 0f, val to: Float = 1f, val bytes: Boolean = true) {
    /** Phần đã xong của cả việc (0..1), hay null khi bước chưa biết tổng. */
    val fraction: Float? get() = if (total > 0) from + (to - from) * (done.coerceIn(0, total).toFloat() / total) else null
}

/** Nơi nhận tiến độ; việc chạy ở luồng nền gọi nó thường xuyên (mỗi khối 64 KB), nên phía nhận tự thưa lại ([WorkThrottle]). */
typealias WorkSink = (Work) -> Unit

/**
 * Thưa lời báo còn tối đa một lần mỗi `minMs` (mặc định 100 ms = 10 lần/giây). Đổi bước, đổi khoảng và lúc bước xong luôn đi qua ngay,
 * để thanh không đứng ở số cũ khi việc đã sang bước khác. `now` cho test JVM đặt đồng hồ giả.
 */
class WorkThrottle(private val sink: WorkSink, private val minMs: Long = 100, private val now: () -> Long = { System.nanoTime() / 1_000_000 }) : WorkSink {
    private var last: Work? = null
    private var at = Long.MIN_VALUE

    @Synchronized
    override fun invoke(work: Work) {
        val previous = last
        val time = now()
        val turn = previous == null || previous.step != work.step || previous.from != work.from || previous.total != work.total
        val finished = work.total > 0 && work.done >= work.total
        if (!turn && !finished && time - at < minMs) return
        last = work
        at = time
        sink(work)
    }
}

/**
 * Lời báo của bước chép: `done` byte trên cỡ hệ thống báo, chiếm [0, `to`] của thanh. Đã chép quá cỡ ấy thì cỡ ấy sai (cột SIZE cũ):
 * bỏ tổng, thanh chạy liên tục thay vì đứng ở "918 MB / 918 MB" trong khi việc vẫn đang chạy.
 */
fun copyWork(done: Long, total: Long, to: Float): Work = Work(WorkStep.Copy, done, if (done > total) 0 else total, 0f, to)

/** Chép `input` sang `output`, báo số byte đã chép sau mỗi khối; trả số byte đã chép. */
fun copyCounting(input: java.io.InputStream, output: java.io.OutputStream, report: (Long) -> Unit): Long {
    val buffer = ByteArray(1 shl 16)
    var done = 0L
    report(0)
    while (true) {
        val read = input.read(buffer)
        if (read < 0) break
        output.write(buffer, 0, read)
        done += read
        report(done)
    }
    return done
}
