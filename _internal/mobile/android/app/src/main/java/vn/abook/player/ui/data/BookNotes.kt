package vn.abook.player.ui.data

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/**
 * Lời báo ngắn của trang sách (web: `toast`): "Đã đổi tên hồ sơ", "Đang nghe lại từ đầu" + "Quay lại chỗ cũ", "Đã ghi: ... là nhân vật nữ" + "Hoàn tác".
 * Một lúc một lời; lời mới thay lời cũ. Có nút thì ở lâu hơn (web: 8 giây "đủ lâu để kịp bấm"), không thì 5 giây. Sống cùng trang sách - rời trang là hết.
 */
class BookNotes(private val scope: CoroutineScope, private val holdMs: Long = HOLD_MS, private val holdActionMs: Long = HOLD_ACTION_MS) {
    private val shown = MutableStateFlow(Note("", null))
    private val open = MutableStateFlow(false)
    private var action: (() -> Unit)? = null
    private var timer: Job? = null

    /** Dòng đang hiện; khi thanh khép thì giữ lại câu cuối để chữ không đổi giữa lúc trượt ra. */
    val note: StateFlow<Note> = shown.asStateFlow()
    val visible: StateFlow<Boolean> = open.asStateFlow()

    class Note(val text: String, val actionLabel: String?)

    fun say(text: String, actionLabel: String? = null, onAction: (() -> Unit)? = null) {
        timer?.cancel()
        action = if (actionLabel != null) onAction else null
        shown.value = Note(text, actionLabel.takeIf { onAction != null })
        open.value = true
        val ms = if (action != null) holdActionMs else holdMs
        timer = scope.launch {
            delay(ms)
            open.value = false
        }
    }

    /** Bấm nút của lời báo: thanh khép, rồi việc ấy chạy. */
    fun act() {
        val run = action
        dismiss()
        run?.invoke()
    }

    fun dismiss() {
        timer?.cancel()
        action = null
        open.value = false
    }

    companion object {
        const val HOLD_MS = 5_000L
        const val HOLD_ACTION_MS = 8_000L
    }
}
