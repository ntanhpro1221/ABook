package vn.abook.player.ui.editbook

import androidx.compose.runtime.Stable
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

/** Draft is live state; typing schedules durable edits, including when Back leaves this screen. */
@Stable
class BookEditor(val id: String, private val source: EditSource, private val scope: CoroutineScope) {
    private val flow = MutableStateFlow(EditState())
    val state: StateFlow<EditState> = flow
    private var typing: Job? = null
    private val writes = Mutex()

    init { reload() }

    fun reload() {
        scope.launch { writes.withLock {
            val previous = flow.value.saved
            try {
                val latest = source.load(id)
                val draft = EditLogic.rebase(previous, flow.value.draft, latest)
                flow.value = flow.value.copy(saved = latest, draft = draft, loading = false)
            } catch (error: Exception) {
                if (error is CancellationException) throw error
                flow.value = flow.value.copy(loading = false, problem = error.message ?: "Bạn hãy thử lại.")
            }
        } }
    }

    fun change(update: (EditDraft) -> EditDraft) {
        val draft = flow.value.draft ?: return
        flow.value = flow.value.copy(draft = update(draft), problem = "")
        typing?.cancel()
        typing = scope.launch { delay(450); scope.launch { flush() } }
    }

    fun retry() { scope.launch { if (flow.value.saved == null) attempt { source.load(id) } else flush() } }

    suspend fun flush(): Boolean = writes.withLock {
        val before = flow.value
        val saved = before.saved ?: return@withLock false
        val draft = before.draft ?: return@withLock false
        val diff = EditLogic.diff(saved, draft)
        if (diff.empty) return@withLock true
        val invalid = EditLogic.validate(diff)
        if (invalid != null) { flow.value = flow.value.copy(problem = invalid); return@withLock false }
        flow.value = flow.value.copy(saving = true)
        try {
            val result = source.save(id, diff)
            // A later keystroke must not be replaced by the result of this earlier write.
            val latest = flow.value.draft
            flow.value = flow.value.copy(saved = result, draft = if (latest == draft) EditLogic.draft(result) else latest,
                saving = false, problem = "")
            true
        } catch (error: Exception) {
            if (error is CancellationException) throw error
            flow.value = flow.value.copy(saving = false, problem = failure(EditLogic.failure(diff), error))
            false
        }
    }

    fun setCover(image: ByteArray?, onDone: () -> Unit = {}): Job = scope.launch {
        if (flush()) writes.withLock {
            if (attempt(if (image == null) "Chưa bỏ được ảnh bìa." else "Chưa đặt được ảnh bìa.") { source.cover(id, image) }) onDone()
        }
    }

    fun revertChapter(chapterId: Long) {
        scope.launch { if (flush()) writes.withLock { attempt("Chưa đổi được tên chương.") { source.revertChapter(id, chapterId) } } }
    }

    fun send() {
        if (flow.value.sending) return
        flow.value = flow.value.copy(sending = true, sendProblem = "")
        scope.launch {
            if (!flush()) { flow.value = flow.value.copy(sending = false); return@launch }
            try {
                val result = source.send(id)
                flow.value = flow.value.copy(saved = result, draft = EditLogic.rebase(flow.value.saved, flow.value.draft, result))
            } catch (error: Exception) {
                if (error is CancellationException) throw error
                val holder = flow.value.saved?.holder ?: "máy tính"
                flow.value = flow.value.copy(sendProblem = listOf("Chưa gửi được về $holder.", error.message.orEmpty(), "Phần sửa vẫn nằm trên máy này.")
                    .filter { it.isNotBlank() }.joinToString(" "))
            } finally { flow.value = flow.value.copy(sending = false) }
        }
    }

    /** `what`: câu đầu của lời lỗi (việc chưa làm được); null = nạp sách, chỉ lý do. */
    private suspend fun attempt(what: String? = null, block: suspend () -> EditSnapshot): Boolean {
        val before = flow.value.draft
        flow.value = flow.value.copy(saving = true, problem = "")
        return try {
            val saved = block()
            val latest = flow.value.draft
            flow.value = EditState(saved, if (latest == before) EditLogic.draft(saved) else latest, loading = false)
            true
        } catch (error: Exception) {
            if (error is CancellationException) throw error
            flow.value = flow.value.copy(loading = false, saving = false, problem = if (what == null) error.message ?: "Bạn hãy thử lại." else failure(what, error))
            false
        }
    }

    /** Lời lỗi: việc chưa làm được (cùng chữ với lời báo của web) + lý do của lõi. */
    private fun failure(what: String, error: Exception) = listOf(what, error.message ?: "Bạn hãy thử lại.").joinToString(" ")
}
