package vn.abook.player.ui.data

import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/**
 * "Xoá khỏi điện thoại" có "Hoàn tác": cuốn dời vào chỗ chờ NGAY ([hold] = `Store.holdBook`, bền qua tắt app -
 * tiến trình chết giữa chừng thì lần mở sau dọn hẳn), thanh nói "Đã xoá “X” khỏi điện thoại" + "Hoàn tác" trong [WINDOW_MS]; nhiều cuốn thì "Đã bỏ N cuốn" và
 * Hoàn tác trả lần lượt cũ trước. Hoàn tác thành thì "Đã khôi phục “X”", không thành (quá hạn, chỗ cũ bị chiếm) thì "Chưa hoàn tác được". Mỗi cuốn một hạn riêng.
 * Sống ở Application: rời màn hay dựng lại Activity không rút ngắn hạn.
 */
class UndoDelete(
    private val scope: CoroutineScope,
    /** Dời cuốn vào chỗ chờ; trả mã Hoàn tác, null khi đã xoá thẳng (không đổi tên được). Ném lỗi có câu cho người nghe. */
    private val hold: suspend (String) -> String?,
    /** Hoàn tác một mã; ném lỗi có câu cho người nghe khi quá hạn / chỗ cũ bị chiếm. */
    private val restore: suspend (String) -> Unit,
    private val changed: suspend () -> Unit,
    private val removed: (String) -> Unit = {},
) {
    private class Held(val token: String, val title: String, val partial: Boolean, val expiry: Job)

    private val held = linkedMapOf<String, Held>()

    /** Cuốn đang ẩn khỏi Thư viện: từ lúc bấm xoá tới lúc hết hạn / hoàn tác (cuốn thật đã nằm ở chỗ chờ trên đĩa). */
    private val hiding = MutableStateFlow<List<String>>(emptyList())
    val pending = hiding.asStateFlow()

    /** Cuốn thanh còn mời Hoàn tác, cũ trước. */
    private val actions = MutableStateFlow<List<String>>(emptyList())
    val undoable = actions.asStateFlow()

    private val errors = MutableStateFlow("")
    val problem = errors.asStateFlow()
    private val notes = MutableStateFlow("")

    /** Lời báo không kèm Hoàn tác: "Đã khôi phục “X”", hay "Đã xoá…" khi cuốn bị xoá thẳng. */
    val notice = notes.asStateFlow()
    private val text = MutableStateFlow("")

    /** Dòng của thanh khi có cuốn chờ Hoàn tác; giữ lại sau khi thanh khép để chữ không đổi giữa lúc trượt ra. */
    val message = text.asStateFlow()
    private val visible = MutableStateFlow(false)
    val showing = visible.asStateFlow()
    private var restoring = false

    fun contains(id: String) = id in hiding.value

    /**
     * Xoá khỏi điện thoại: cuốn ẩn ngay, rồi dời vào chỗ chờ. Trả null khi đã nhận, khác null = câu lỗi (cuốn hiện lại, nơi gọi nói tại chỗ).
     * `partial`: phần đã tải dở, chưa thành sách ("Đã xoá phần đã tải của “X”").
     */
    suspend fun remove(id: String, title: String = "", partial: Boolean = false): String? {
        if (contains(id)) return null
        errors.value = ""
        notes.value = ""
        hiding.value = hiding.value + id
        removed(id)
        changed()
        val token = try {
            hold(id)
        } catch (cancelled: CancellationException) {
            hiding.value = hiding.value - id
            throw cancelled
        } catch (error: Exception) {
            hiding.value = hiding.value - id
            changed()
            return error.message?.takeIf { it.isNotBlank() } ?: "Chưa xoá được"
        }
        if (token == null) {
            // Xoá thẳng: chỉ báo, không có Hoàn tác.
            hiding.value = hiding.value - id
            say(removedText(1, title, partial))
            changed()
            return null
        }
        held[id] = Held(token, title, partial, scope.launch { delay(WINDOW_MS); expire(id) })
        actions.value = actions.value + id
        text.value = currentText()
        visible.value = true
        return null
    }

    /** Hết hạn: cuốn thôi mời Hoàn tác (chỗ chờ trên đĩa tự dọn sau ít giây nữa). */
    private suspend fun expire(id: String) {
        held.remove(id) ?: return
        actions.value = actions.value - id
        hiding.value = hiding.value - id
        if (actions.value.isEmpty()) visible.value = false else text.value = currentText()
        changed()
    }

    /** "Hoàn tác": trả lần lượt, cũ trước (xoá "X", thêm "X" mới rồi bỏ nó - "X" cũ về chỗ cũ trước); cuốn không trả được vẫn nằm đó tới hết hạn. */
    fun undo() {
        if (restoring || actions.value.isEmpty()) return
        restoring = true
        scope.launch {
            try {
                for (id in actions.value) {
                    val item = held[id] ?: continue
                    try {
                        restore(item.token)
                    } catch (cancelled: CancellationException) {
                        throw cancelled
                    } catch (error: Exception) {
                        // Tiêu đề "Chưa hoàn tác được" + lý do của lõi.
                        say("Chưa hoàn tác được" + " - " + (error.message?.takeIf { it.isNotBlank() } ?: "bạn thử lại"), error = true)
                        continue
                    }
                    held.remove(id)?.expiry?.cancel()
                    actions.value = actions.value - id
                    hiding.value = hiding.value - id
                    say("Đã khôi phục “${item.title}”")
                }
            } finally {
                restoring = false
                if (actions.value.isEmpty()) visible.value = false else text.value = currentText()
                changed()
            }
        }
    }

    /** Back / gạt thanh: những cuốn ấy không còn mời Hoàn tác (vẫn nằm chờ tới hết hạn). */
    fun dismiss() {
        actions.value = emptyList()
        visible.value = false
        errors.value = ""
        notes.value = ""
    }

    private fun currentText(): String {
        val last = held[actions.value.last()]
        return removedText(actions.value.size, last?.title.orEmpty(), last?.partial == true)
    }

    private fun say(message: String, error: Boolean = false) {
        val flow = if (error) errors else notes
        flow.value = message
        scope.launch { delay(5_000); if (flow.value == message) flow.value = "" }
    }

    companion object {
        /** Khớp `UNDO_TOAST_MS` của `trashUndo.ts` = (hạn của chỗ chờ - 2) giây: bấm ở giây chót không gặp chỗ chờ đã dọn. */
        const val WINDOW_MS = 28_000L

        /** Dòng của thanh / thông báo sau khi xoá. */
        fun removedText(count: Int, title: String, partial: Boolean): String = when {
            count > 1 -> "Đã bỏ $count cuốn"
            partial -> "Đã xoá phần đã tải của “$title”"
            title.isEmpty() -> "Đã xoá khỏi điện thoại"
            else -> "Đã xoá “$title” khỏi điện thoại"
        }
    }
}
