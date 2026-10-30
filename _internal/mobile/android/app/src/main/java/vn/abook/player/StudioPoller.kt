package vn.abook.player

import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.async
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.selects.select

/** Nhịp hỏi máy tính của Studio - port nguyên `ui/src/studio/polling.ts` `pollDelay` và hằng của `data.ts` (số ms giữ y). */
object StudioPolling {
    /** Sách đang chạy: thanh tiến độ phải sống (web: `LIVE_MS * 1.5`); không thì thưa hẳn. */
    const val BOOK_LIVE_MS = 3000L
    const val IDLE_MS = 15_000L

    /** Danh sách dự án: có sách chạy thì 5 giây (đang xem Studio), không thì [IDLE_MS]. */
    const val LIST_LIVE_MS = 5000L

    /** Trần của nhịp lùi: lỗi kéo dài thì hai phút hỏi một lần, đủ để màn tự khỏi khi máy tính sống lại. */
    const val BACKOFF_CAP_MS = 120_000L

    /**
     * Nhịp hỏi kế tiếp, hay null = thôi hỏi theo nhịp. `base` null = không hỏi theo nhịp; 404 và chỉ-nghe dừng hẳn (hỏi tiếp vô ích);
     * lỗi khác gấp đôi theo số lần lỗi liên tiếp (tối đa 2^8), tới trần.
     */
    fun pollDelay(base: Long?, error: StudioError?, failures: Int): Long? {
        if (error is StudioError.Gone || error is StudioError.ListenOnly || error is StudioError.Unauthorized || error is StudioError.PinChanged) return null
        if (error == null || base == null) return base
        return minOf(base * (1L shl minOf(failures, 8)), BACKOFF_CAP_MS)
    }

    /** Bản mới nhất của một nguồn hỏi định kỳ: `data` giữ lại cả khi lần hỏi sau lỗi (web: "stale" - giữ trang, thêm dải báo). */
    data class Poll<T>(val data: T? = null, val error: StudioError? = null, val failures: Int = 0, val loaded: Boolean = false)
}

/**
 * Một nguồn dữ liệu hỏi định kỳ (thuần, test bằng `pause` giả). [run] chạy tới khi bị huỷ - gọi trong `repeatOnLifecycle(STARTED)` để màn
 * không hiện / app ở nền thì KHÔNG hỏi, và hỏi ngay một lần khi trở lại. `interval(data)`: nhịp cơ sở theo dữ liệu mới nhất, null = không hỏi
 * theo nhịp (vẫn hỏi khi [refresh] được gọi).
 */
class StudioPoller<T : Any>(
    private val fetch: suspend () -> T,
    private val interval: (T?) -> Long?,
    private val pause: suspend (Long) -> Unit = { delay(it) },
) {
    private val flow = MutableStateFlow(StudioPolling.Poll<T>())
    private val nudge = Channel<Unit>(Channel.CONFLATED)

    val state: StateFlow<StudioPolling.Poll<T>> get() = flow

    /** Hỏi một lần ngay: sau một lệnh của người dùng, hay nút "Thử lại". Gộp với nhịp đang chờ. */
    suspend fun refresh() {
        step()
        nudge.trySend(Unit)
    }

    /** Hỏi một lần rồi hỏi theo nhịp tới khi bị huỷ; ngừng hẳn khi máy tính nói hỏi tiếp vô ích (404, chỉ nghe, bỏ ghép). */
    suspend fun run() {
        var ask = true
        while (true) {
            if (ask) step()
            ask = true
            val current = flow.value
            val wait = StudioPolling.pollDelay(interval(current.data), current.error, current.failures)
            if (wait == null) {
                if (current.error != null) return
                nudge.receive() // không hỏi theo nhịp: đợi một lệnh [refresh] (đã hỏi xong) rồi xét lại nhịp theo dữ liệu mới
                ask = false
            } else if (!sleep(wait)) {
                ask = false // [refresh] đã hỏi trong lúc chờ: đừng hỏi trùng, chờ lại từ đầu
            }
        }
    }

    /** Chờ `wait`; true = hết giờ, false = có người gọi [refresh]. */
    private suspend fun sleep(wait: Long): Boolean = coroutineScope {
        val timer = async { pause(wait); true }
        val nudged = async { nudge.receive(); false }
        select<Boolean> {
            timer.onAwait { it }
            nudged.onAwait { it }
        }.also {
            timer.cancel()
            nudged.cancel()
        }
    }

    private suspend fun step() {
        try {
            val value = fetch()
            flow.value = StudioPolling.Poll(value, null, 0, true)
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (error: Throwable) {
            val failure = StudioErrors.of(error)
            val old = flow.value
            flow.value = StudioPolling.Poll(old.data, failure, old.failures + 1, true)
        }
    }
}
