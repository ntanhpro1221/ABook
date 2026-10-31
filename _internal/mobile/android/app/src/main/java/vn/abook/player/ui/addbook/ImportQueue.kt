package vn.abook.player.ui.addbook

import androidx.compose.runtime.Stable
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

/** One parsed book at a time; Back does not cancel imports or lose choices. No unbounded parsed-book cache. */
@Stable
class ImportQueue(private val source: ImportSource, private val scope: CoroutineScope, private val changed: suspend () -> Unit = {}) {
    private val flow = MutableStateFlow(ImportState())
    val state: StateFlow<ImportState> = flow
    private var nextId = 1L
    private var ref: String? = null
    private var worker: Job? = null
    private val progress = HashMap<Long, MutableStateFlow<Float>>()
    private val reviewed = HashSet<Long>()
    private val opened = HashSet<Long>()

    fun takeAutoReview(id: Long): Boolean = reviewed.add(id)
    fun takeAutoOpen(id: Long): Boolean = opened.add(id)

    fun progress(id: Long): StateFlow<Float> = progress.getOrPut(id) { MutableStateFlow(0f) }

    fun enqueue(sources: List<String>, folder: Boolean = false) {
        val items = sources.take(40).map { ImportItem(nextId++, it, folder = folder) }
        flow.value = flow.value.copy(items = flow.value.items + items)
        scope.launch {
            // Resolve small document metadata before parsing so every waiting row has its file name.
            for (item in items) {
                val name = try { source.describe(item) } catch (error: Exception) {
                    if (error is CancellationException) throw error
                    item.name
                }
                flow.value = flow.value.copy(items = flow.value.items.map { if (it.id == item.id) it.copy(name = name) else it })
            }
            advance()
        }
    }

    fun choose(change: (ImportChoices) -> ImportChoices) {
        if (!flow.value.busy) flow.value = flow.value.copy(choices = change(flow.value.choices), problem = "")
    }

    fun revise(change: (ImportChoices) -> ImportChoices) {
        if (flow.value.busy) return
        val staged = ref ?: return
        val old = flow.value.preview ?: return
        val choices = change(flow.value.choices)
        flow.value = flow.value.copy(busy = true, problem = "")
        worker = scope.launch {
            try {
                val preview = source.revise(staged, choices)
                flow.value = flow.value.copy(preview = preview, choices = ImportLogic.retain(preview, old, choices))
            } catch (error: Exception) {
                if (error is CancellationException) throw error
                flow.value = flow.value.copy(problem = failure("Chưa đọc lại được file.", error))
            } finally { flow.value = flow.value.copy(busy = false) }
        }
    }

    fun add() {
        if (flow.value.busy) return
        if (flow.value.packageReview != null) { replacePackage(); return }
        val current = flow.value
        val id = current.currentId ?: return
        val staged = ref ?: return
        val preview = current.preview ?: return
        flow.value = current.copy(busy = true, problem = "", items = ImportLogic.settle(current.items, id, ImportStage.Adding))
        worker = scope.launch {
            try {
                val (bookId, existing) = if (preview.existingId != null && !current.choices.separate) {
                    source.discard(staged)
                    preview.existingId to true
                } else source.add(staged, preview, current.choices)
                changed()
                finish(id, if (existing) ImportStage.Existing else ImportStage.Added, bookId, current.choices.title.ifBlank { preview.title })
            } catch (error: Exception) {
                if (error is CancellationException) throw error
                if (flow.value.addingRest) {
                    runCatching { source.discard(staged) }
                    finish(id, ImportStage.Error)
                    flow.value = flow.value.copy(items = ImportLogic.settle(flow.value.items, id, ImportStage.Error, failure("Chưa thêm được sách.", error)))
                    advance()
                    return@launch
                }
                flow.value = flow.value.copy(busy = false, problem = failure("Chưa thêm được sách.", error),
                    items = ImportLogic.settle(flow.value.items, id, ImportStage.Review))
                return@launch
            }
            advance()
        }
    }

    fun addRest() {
        if (flow.value.busy) return
        flow.value = flow.value.copy(addingRest = true)
        val preview = flow.value.preview
        if (preview != null) add()
        else if (flow.value.packageReview != null) keepPackage()
        else advance()
    }

    fun keepPackage() {
        val p = flow.value.packageReview ?: return
        val id = flow.value.currentId ?: return
        finish(id, ImportStage.Existing, p.bookId)
        advance()
    }

    private fun replacePackage() {
        val item = flow.value.items.firstOrNull { it.id == flow.value.currentId } ?: return
        flow.value = flow.value.copy(busy = true, problem = "")
        worker = scope.launch {
            try {
                val result = source.replace(item)
                changed()
                finish(item.id, ImportStage.Added, result.bookId)
                flow.value = flow.value.copy(notice = result.notice)
                advance()
            } catch (e: Exception) {
                if (e is CancellationException) throw e
                flow.value = flow.value.copy(busy = false, problem = failure("Chưa thay được sách", e))
            }
        }
    }

    fun skip() {
        if (flow.value.busy) return
        val id = flow.value.currentId ?: return
        flow.value = flow.value.copy(busy = true)
        worker = scope.launch {
            ref?.let { source.discard(it) }
            finish(id, ImportStage.Skipped)
            advance()
        }
    }

    fun retry(id: Long) {
        if (flow.value.items.none { it.id == id && it.stage == ImportStage.Error }) return
        flow.value = flow.value.copy(items = ImportLogic.settle(flow.value.items, id, ImportStage.Waiting))
        advance()
    }

    /** Lời lỗi: việc chưa làm được (cùng chữ với lời báo của web) + lý do của lõi. */
    private fun failure(what: String, error: Exception) = listOf(what, error.message ?: "Bạn hãy thử lại.").joinToString(" ")

    /**
     * "Bỏ phần còn lại" khi đóng Thêm sách giữa hàng (web AddBook `reset`): cuốn đang đọc dừng, bản tạm của cuốn đang xem bị bỏ, cả hàng về trống. Cuốn đã thêm vẫn ở
     * Thư viện. Đang thêm một cuốn thì không bỏ (ghi dở một cuốn còn tệ hơn), trả false.
     */
    fun dropRest(): Boolean {
        if (flow.value.items.any { it.stage == ImportStage.Adding }) return false
        worker?.cancel()
        worker = null
        val staged = ref
        ref = null
        flow.value = ImportState()
        progress.clear()
        reviewed.clear()
        opened.clear()
        if (staged != null) scope.launch {
            try { source.discard(staged) } catch (error: Exception) { if (error is CancellationException) throw error }
        }
        return true
    }

    private fun finish(id: Long, stage: ImportStage, bookId: String? = null, title: String = "") {
        progress.getOrPut(id) { MutableStateFlow(0f) }.value = 1f
        ref = null
        flow.value = flow.value.copy(items = ImportLogic.settle(flow.value.items, id, stage, bookId = bookId),
            currentId = null, preview = null, packageReview = null, choices = ImportChoices(), busy = false, problem = "",
            notice = if (stage == ImportStage.Added) (if (title.isBlank()) "Đã thêm" else "Đã thêm “$title”") else flow.value.notice)
    }

    private fun advance() {
        if (flow.value.currentId != null) return
        worker = scope.launch {
            while (flow.value.currentId == null) {
                val item = ImportLogic.next(flow.value.items) ?: break
                flow.value = flow.value.copy(currentId = item.id, busy = true,
                    items = ImportLogic.settle(flow.value.items, item.id, ImportStage.Reading))
                progress.getOrPut(item.id) { MutableStateFlow(0f) }.value = 0.2f
                try {
                    val result = source.prepare(item)
                    ref = result.ref
                    flow.value = flow.value.copy(items = flow.value.items.map { if (it.id == item.id) it.copy(name = result.name) else it })
                    if (result.packageReview != null) {
                        flow.value = flow.value.copy(packageReview = result.packageReview, busy = false,
                            items = ImportLogic.settle(flow.value.items, item.id, ImportStage.Review))
                        if (flow.value.addingRest) { keepPackage(); return@launch }
                    } else if (result.bookId != null) {
                        changed()
                        finish(item.id, if (result.existing) ImportStage.Existing else ImportStage.Added, result.bookId)
                        flow.value = flow.value.copy(notice = result.notice)
                    } else {
                        val preview = requireNotNull(result.preview)
                        if (flow.value.addingRest && (preview.chapters.isEmpty() || preview.title.isBlank())) {
                            finish(item.id, ImportStage.Error)
                            flow.value = flow.value.copy(items = ImportLogic.settle(flow.value.items, item.id, ImportStage.Error,
                                if (preview.chapters.isEmpty()) "File này chưa có chương nào để thêm." else "File này chưa có tên sách - thêm riêng để đặt tên."))
                            source.discard(result.ref!!)
                            continue
                        }
                        progress.getValue(item.id).value = 0.55f
                        flow.value = flow.value.copy(preview = preview, choices = ImportLogic.defaults(preview), busy = false,
                            items = ImportLogic.settle(flow.value.items, item.id, ImportStage.Review))
                        if (flow.value.addingRest) { add(); return@launch }
                    }
                } catch (error: Exception) {
                    if (error is CancellationException) throw error
                    flow.value = flow.value.copy(currentId = null, busy = false,
                        items = ImportLogic.settle(flow.value.items, item.id, ImportStage.Error, ImportLogic.openFailure(item, error.message)))
                }
            }
            if (ImportLogic.next(flow.value.items) == null && flow.value.currentId == null)
                flow.value = flow.value.copy(addingRest = false)
        }
    }
}
