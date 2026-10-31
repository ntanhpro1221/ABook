package vn.abook.player.ui.data

import androidx.compose.runtime.Stable
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

/**
 * "Làm trước" sống (web: `usePrepareStatus` + PrepareAhead trong menu Giọng đọc): trạng thái việc của cả máy, ước trước khi bấm, lỗi của lần bấm cuối.
 * Chỉ nghe lõi khi có chỗ đang hiện nó ([watch] đếm số nơi xem): ẩn hết thì gỡ listener, không đọc gì trong lúc không ai thấy.
 */
@Stable
class PrepareState(private val source: PrepareSource, private val scope: CoroutineScope) {
    private val _status = MutableStateFlow(PrepareStatus())
    val status: StateFlow<PrepareStatus> = _status

    private val _plan = MutableStateFlow<PreparePlan?>(null)
    val plan: StateFlow<PreparePlan?> = _plan

    /** Câu lỗi của lần bấm "Làm trước" vừa rồi (web: toast "Chưa làm trước được"); null = không có. */
    private val _failure = MutableStateFlow<String?>(null)
    val failure: StateFlow<String?> = _failure

    private val _busy = MutableStateFlow(false)
    val busy: StateFlow<Boolean> = _busy

    private var watchers = 0
    private var unlisten: (() -> Unit)? = null

    /** Một nơi bắt đầu / thôi xem: đọc trạng thái một lần khi nơi đầu tiên hiện, đăng ký nhận khi đổi. Gọi từ luồng chính. */
    fun watch(on: Boolean) {
        if (on) {
            watchers++
            if (watchers == 1) {
                unlisten = source.listen { next -> _status.value = next }
                refresh()
            }
        } else if (watchers > 0) {
            watchers--
            if (watchers == 0) { unlisten?.invoke(); unlisten = null }
        }
    }

    fun refresh() {
        scope.launch { runCatching { source.status() }.onSuccess { _status.value = it } }
    }

    /** Ước cho các chương `ids` bằng `voice`; rỗng thì bỏ ước cũ. Kết quả cũ về muộn (đã đổi yêu cầu) bị bỏ. */
    private var planKey: Triple<String, String, List<Int>>? = null
    fun loadPlan(voice: String, bookId: String, ids: List<Int>) {
        val key = Triple(voice, bookId, ids)
        if (key == planKey) return
        planKey = key
        _plan.value = null
        if (ids.isEmpty()) return
        scope.launch {
            val got = runCatching { source.plan(voice, bookId, ids) }.getOrNull()
            if (planKey == key) _plan.value = got
        }
    }

    fun start(voice: String, bookId: String, ids: List<Int>, label: String) {
        if (_busy.value) return
        _busy.value = true
        _failure.value = null
        scope.launch {
            try {
                _status.value = source.start(voice, bookId, ids, label, _status.value.chargingOnly)
            } catch (cancel: CancellationException) {
                throw cancel
            } catch (error: Exception) {
                _failure.value = error.message ?: "Chưa rõ vì sao"
            } finally {
                _busy.value = false
            }
        }
    }

    fun cancel() {
        scope.launch { runCatching { source.cancel() }.onSuccess { _status.value = it } }
    }

    fun setChargingOnly(on: Boolean) {
        _status.value = _status.value.copy(chargingOnly = on)
        scope.launch { runCatching { source.setChargingOnly(on) }.onSuccess { _status.value = it } }
    }

    fun dismissFailure() { _failure.value = null }
}
