package vn.abook.player.ui.addbook

import vn.abook.player.ImportJob
import vn.abook.player.ImportJobState
import vn.abook.player.S
import vn.abook.player.Work
import vn.abook.player.WorkStep
import vn.abook.player.WorkThrottle

import androidx.compose.runtime.Stable
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

/**
 * One parsed book at a time; Back does not cancel imports or lose choices. No unbounded parsed-book cache.
 * Thanh của mỗi hàng chạy theo việc thật ([progress]): byte đã chép / kiểm, số file, số trang; bước chưa biết tổng thì thanh chạy liên tục.
 * `now` (ms) cho test JVM đặt đồng hồ giả của bộ thưa lời báo (tối đa 10 lần/giây).
 */
@Stable
class ImportQueue(
    private val source: ImportSource, private val scope: CoroutineScope,
    private val now: () -> Long = { System.nanoTime() / 1_000_000 },
    private val changed: suspend () -> Unit = {},
    /** Sổ các lượt nhập nền của tiến trình ([vn.abook.player.BookImports.jobs]): màn này là một người xem của nó. */
    background: StateFlow<Map<String, ImportJob>>? = null,
    /** "Thử lại" ở hàng của một lượt nền: xếp lại lượt ấy (cùng file, cùng cách xoá file nguồn). */
    private val retryJob: (String) -> Unit = {},
) {
    private val flow = MutableStateFlow(ImportState())
    val state: StateFlow<ImportState> = flow
    private var nextId = 1L
    /** Bản tạm (bước xem trước) gắn với ĐÚNG hàng đã đọc ra nó: hàng khác không bao giờ thêm / đọc lại / bỏ bằng bản tạm này. */
    private var held: Held? = null
    private data class Held(val id: Long, val ref: String)
    private fun refOf(id: Long?): String? = held?.takeIf { id != null && it.id == id }?.ref
    private var worker: Job? = null
    private val progress = HashMap<Long, MutableStateFlow<Work>>()
    private val reviewed = HashSet<Long>()
    private val opened = HashSet<Long>()
    /** Lượt nền -> hàng đang xem nó; lượt nền của chính hàng đợi này (file đang đọc ở một hàng) không có hàng riêng. */
    private val mirrored = HashMap<String, Long>()
    private val own = HashSet<String>()

    init {
        if (background != null) scope.launch { background.collect(::mirror) }
    }

    /**
     * Hiện các lượt nhập nền mà màn này không xếp (lệnh adb, nút trên thông báo) thành hàng như mọi file: mở "Thêm sách" giữa chừng vẫn thấy đúng bước và
     * byte; xong thì "Đã thêm", lỗi thì "Thử lại". Lượt đã xong trước khi màn thấy nó thì không thêm hàng (nằm ở Thư viện và thông báo).
     */
    private fun mirror(jobs: Map<String, ImportJob>) {
        for (job in jobs.values) {
            if (job.id in own) continue
            var row = mirrored[job.id]
            if (row == null) {
                if (job.state != ImportJobState.Running) continue
                val items = flow.value.items
                if (items.any { !it.background && it.source == job.source && it.stage in ACTIVE }) { own += job.id; continue }
                // "Thử lại" của một hàng nền: lượt mới của cùng file dùng lại hàng lỗi ấy, không thêm hàng thứ hai.
                val again = items.firstOrNull { it.background && it.source == job.source && it.stage == ImportStage.Error }
                row = again?.id ?: nextId++
                mirrored.entries.removeAll { it.value == row }
                mirrored[job.id] = row
                flow.value = flow.value.copy(items = if (again != null) items else items + ImportItem(row, job.source, job.name, background = true))
            }
            val item = flow.value.items.firstOrNull { it.id == row } ?: continue
            when (job.state) {
                ImportJobState.Running -> {
                    bar(row).value = job.work
                    if (item.stage != ImportStage.Reading) flow.value = flow.value.copy(items = ImportLogic.settle(flow.value.items, row, ImportStage.Reading))
                }
                ImportJobState.Failed -> if (item.stage != ImportStage.Error)
                    flow.value = flow.value.copy(items = ImportLogic.settle(flow.value.items, row, ImportStage.Error, job.problem))
                ImportJobState.Done -> if (item.stage == ImportStage.Reading) {
                    val existing = job.how == "existing" || job.needsChoice
                    bar(row).value = Work(job.work.step, 1, 1)
                    flow.value = flow.value.copy(items = ImportLogic.settle(flow.value.items, row, if (existing) ImportStage.Existing else ImportStage.Added, bookId = job.bookId),
                        notice = when {
                            existing -> flow.value.notice
                            job.how == "updated" -> S.s_da_cap_nhat_0_627a2681(job.title)
                            else -> S.s_da_them_0_ea40abe7(job.title)
                        })
                    scope.launch { changed() }
                }
            }
        }
    }

    fun takeAutoReview(id: Long): Boolean = reviewed.add(id)
    fun takeAutoOpen(id: Long): Boolean = opened.add(id)

    fun progress(id: Long): StateFlow<Work> = bar(id)

    private fun bar(id: Long): MutableStateFlow<Work> = synchronized(progress) { progress.getOrPut(id) { MutableStateFlow(Work(WorkStep.Read)) } }

    /** Nơi nhận tiến độ của một hàng, đã thưa còn tối đa 10 lần/giây. */
    private fun sink(id: Long): WorkThrottle { val flow = bar(id); return WorkThrottle({ flow.value = it }, now = now) }

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
        val staged = refOf(flow.value.currentId) ?: return
        val old = flow.value.preview ?: return
        val choices = change(flow.value.choices)
        flow.value = flow.value.copy(busy = true, problem = "")
        worker = scope.launch {
            try {
                val preview = source.revise(staged, choices)
                flow.value = flow.value.copy(preview = preview, choices = ImportLogic.retain(preview, old, choices))
            } catch (error: Exception) {
                if (error is CancellationException) throw error
                flow.value = flow.value.copy(problem = failure(S.s_chua_doc_lai_duoc_file_f399dcd5, error))
            } finally { flow.value = flow.value.copy(busy = false) }
        }
    }

    fun add() {
        if (flow.value.busy) return
        if (flow.value.packageReview != null) { replacePackage(); return }
        val current = flow.value
        val id = current.currentId ?: return
        val staged = refOf(id) ?: return
        val preview = current.preview ?: return
        flow.value = current.copy(busy = true, problem = "", items = ImportLogic.settle(current.items, id, ImportStage.Adding))
        // Ghi sách vào thư viện không báo được phần đã làm: thanh chạy liên tục, không đứng ở số của bước trước.
        bar(id).value = Work(WorkStep.Add)
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
                    flow.value = flow.value.copy(items = ImportLogic.settle(flow.value.items, id, ImportStage.Error, failure(S.s_chua_them_duoc_sach_a46be70d, error)))
                    advance()
                    return@launch
                }
                flow.value = flow.value.copy(busy = false, problem = failure(S.s_chua_them_duoc_sach_a46be70d, error),
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
        flow.value = flow.value.copy(busy = true, problem = "", items = ImportLogic.settle(flow.value.items, item.id, ImportStage.Adding))
        bar(item.id).value = Work(WorkStep.Copy)
        worker = scope.launch {
            try {
                val result = source.replace(item, sink(item.id))
                changed()
                finish(item.id, ImportStage.Added, result.bookId)
                flow.value = flow.value.copy(notice = result.notice)
                advance()
            } catch (e: Exception) {
                if (e is CancellationException) throw e
                flow.value = flow.value.copy(busy = false, problem = failure(S.s_chua_thay_duoc_sach_8eebed8f, e),
                    items = ImportLogic.settle(flow.value.items, item.id, ImportStage.Review))
            }
        }
    }

    fun skip() {
        if (flow.value.busy) return
        val id = flow.value.currentId ?: return
        flow.value = flow.value.copy(busy = true)
        worker = scope.launch {
            refOf(id)?.let { source.discard(it) }
            finish(id, ImportStage.Skipped)
            advance()
        }
    }

    fun retry(id: Long) {
        if (flow.value.items.none { it.id == id && it.stage == ImportStage.Error }) return
        mirrored.entries.firstOrNull { it.value == id }?.let { (job, _) -> retryJob(job); return }
        flow.value = flow.value.copy(items = ImportLogic.settle(flow.value.items, id, ImportStage.Waiting))
        advance()
    }

    /** Lời lỗi: việc chưa làm được (cùng chữ với lời báo của web) + lý do của lõi. */
    private fun failure(what: String, error: Exception) = listOfNotNull(what, error.message?.takeIf { it.isNotBlank() }).joinToString(" ")

    /**
     * "Bỏ phần còn lại" khi đóng Thêm sách giữa hàng (web AddBook `reset`): cuốn đang đọc dừng, bản tạm của cuốn đang xem bị bỏ, cả hàng về trống. Cuốn đã thêm vẫn ở
     * Thư viện. Đang thêm một cuốn thì không bỏ (ghi dở một cuốn còn tệ hơn), trả false.
     */
    fun dropRest(): Boolean {
        if (flow.value.items.any { it.stage == ImportStage.Adding }) return false
        worker?.cancel()
        worker = null
        val staged = held?.ref
        held = null
        flow.value = ImportState()
        // Lượt nền không dừng theo màn: lượt còn chạy hiện lại thành hàng ở lời báo tiến độ kế tiếp của nó.
        mirrored.clear()
        own.clear()
        synchronized(progress) { progress.clear() }
        reviewed.clear()
        opened.clear()
        if (staged != null) scope.launch {
            try { source.discard(staged) } catch (error: Exception) { if (error is CancellationException) throw error }
        }
        return true
    }

    private fun finish(id: Long, stage: ImportStage, bookId: String? = null, title: String = "") {
        bar(id).value = Work(bar(id).value.step, 1, 1)
        if (held?.id == id) held = null
        flow.value = flow.value.copy(items = ImportLogic.settle(flow.value.items, id, stage, bookId = bookId),
            currentId = null, preview = null, packageReview = null, choices = ImportChoices(), busy = false, problem = "",
            notice = if (stage == ImportStage.Added) (if (title.isBlank()) S.s_da_them_e26b2fcb else S.s_da_them_0_ea40abe7(title)) else flow.value.notice)
    }

    private fun advance() {
        if (flow.value.currentId != null) return
        worker = scope.launch {
            while (flow.value.currentId == null) {
                val item = ImportLogic.next(flow.value.items) ?: break
                // Mỗi lượt bắt đầu sạch: bản tạm, bản xem trước, lựa chọn, lời lỗi của lượt trước không đi theo sang file này.
                held?.let { left ->
                    held = null
                    try { source.discard(left.ref) } catch (error: Exception) { if (error is CancellationException) throw error }
                }
                flow.value = flow.value.copy(currentId = item.id, busy = true, preview = null, packageReview = null, choices = ImportChoices(), problem = "",
                    items = ImportLogic.settle(flow.value.items, item.id, ImportStage.Reading))
                // Chưa có lời báo nào của lõi: thanh chạy liên tục với chữ "Đang đọc", không phải một con số đứng yên.
                bar(item.id).value = Work(WorkStep.Read)
                try {
                    val result = source.prepare(item, sink(item.id))
                    held = result.ref?.let { Held(item.id, it) }
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
                                if (preview.chapters.isEmpty()) S.s_file_nay_chua_co_chuong_nao_de_them_83a1704f else S.s_file_nay_chua_co_ten_sach_them_rieng_de_da_ec9e7d95))
                            source.discard(result.ref!!)
                            continue
                        }
                        bar(item.id).value = Work(WorkStep.Read, 1, 1)
                        flow.value = flow.value.copy(preview = preview, choices = ImportLogic.defaults(preview), busy = false,
                            items = ImportLogic.settle(flow.value.items, item.id, ImportStage.Review))
                        if (flow.value.addingRest) { add(); return@launch }
                    }
                } catch (error: Exception) {
                    if (error is CancellationException) throw error
                    if (held?.id == item.id) held = null
                    flow.value = flow.value.copy(currentId = null, busy = false, preview = null, packageReview = null, choices = ImportChoices(), problem = "",
                        items = ImportLogic.settle(flow.value.items, item.id, ImportStage.Error, ImportLogic.openFailure(item, error.message)))
                }
            }
            if (ImportLogic.next(flow.value.items) == null && flow.value.currentId == null)
                flow.value = flow.value.copy(addingRest = false)
        }
    }

    private companion object {
        val ACTIVE = setOf(ImportStage.Waiting, ImportStage.Reading, ImportStage.Review, ImportStage.Adding)
    }
}
