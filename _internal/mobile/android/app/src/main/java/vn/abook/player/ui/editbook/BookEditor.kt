package vn.abook.player.ui.editbook

import androidx.compose.runtime.Stable
import androidx.compose.ui.graphics.ImageBitmap
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
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
    private val readingsFlow = MutableStateFlow(ReadingsUi())
    private val coversFlow = MutableStateFlow(CoverSearchUi())
    private var search: Job? = null
    private var choice: Job? = null
    private val thumbs = HashMap<String, ImageBitmap>()

    /** "Cách đọc tên" (chỉ đọc khi phần ấy mở - [loadReadings]). */
    val readings: StateFlow<ReadingsUi> = readingsFlow

    /** Màn "Tìm ảnh bìa". */
    val covers: StateFlow<CoverSearchUi> = coversFlow

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
            flow.value = flow.value.copy(saving = false, problem = error.message ?: "Bạn hãy thử lưu lại.")
            false
        }
    }

    fun setCover(image: ByteArray?, onDone: () -> Unit = {}): Job =
        scope.launch { if (flush()) writes.withLock { if (attempt { source.cover(id, image) }) onDone() } }

    fun revertChapter(chapterId: Long) {
        scope.launch { if (flush()) writes.withLock { attempt { source.revertChapter(id, chapterId) } } }
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
                flow.value = flow.value.copy(sendProblem = "${error.message.orEmpty()} Phần sửa vẫn được giữ trên máy bạn.")
            } finally { flow.value = flow.value.copy(sending = false) }
        }
    }

    /** "Bỏ mọi thay đổi": cả chữ đang gõ dở cũng bỏ. `done(null)` khi xong, `done(câu lỗi)` khi chưa bỏ được. */
    fun discardAll(done: (String?) -> Unit) {
        typing?.cancel()
        scope.launch {
            val problem = writes.withLock {
                try {
                    val saved = source.discardAll(id)
                    flow.value = EditState(saved, EditLogic.draft(saved), loading = false)
                    null
                } catch (error: Exception) {
                    if (error is CancellationException) throw error
                    "Chưa bỏ được thay đổi"
                }
            }
            if (problem == null && readingsFlow.value.loaded) loadReadings()
            done(problem)
        }
    }

    // ---- cách đọc tên ----------------------------------------------------------------------------------------------

    /** Mỗi lần mở phần "Cách đọc tên" hỏi lại (máy khác có thể vừa đổi một từ) - danh sách nhỏ, rẻ. */
    fun loadReadings() {
        scope.launch {
            try {
                val list = source.readings(id)
                readingsFlow.update { it.copy(loaded = true, list = list, problem = "") }
            } catch (error: Exception) {
                if (error is CancellationException) throw error
                readingsFlow.update { it.copy(problem = "Bạn hãy thử tải lại danh sách cách đọc.") }
            }
        }
    }

    /** Đặt (hay bỏ - `spoken` rỗng) cách đọc của `surface` cho cả cuốn; xong thì gọi `done` (khép ô sửa) và đọc lại số thay đổi của sách. */
    fun setReading(surface: String, spoken: String, done: () -> Unit = {}) {
        if (readingsFlow.value.saving) return
        val said = ReadingText.spoken(spoken)
        readingsFlow.update { it.copy(saving = true, failed = "", notice = "") }
        scope.launch {
            try {
                val list = source.setReading(id, surface, said)
                readingsFlow.update { it.copy(loaded = true, list = list, saving = false, notice = ReadingText.saved(surface, said)) }
                done()
                reload()
            } catch (error: Exception) {
                if (error is CancellationException) throw error
                readingsFlow.update { it.copy(saving = false, failed = if (said.isEmpty()) "Chưa bỏ được cách đọc" else "Chưa lưu được cách đọc") }
            }
        }
    }

    // ---- tìm ảnh bìa -----------------------------------------------------------------------------------------------

    /** Mở "Tìm ảnh bìa": ô tìm mang tên sách, tìm luôn (như web lần đầu hiện bảng). */
    fun openCoverSearch(query: String) {
        stopCoverSearch()
        thumbs.clear()
        coversFlow.value = CoverSearchUi(query = query)
        searchCovers()
    }

    fun setCoverQuery(query: String) = coversFlow.update { it.copy(query = query) }

    /** Tìm theo chữ trong ô; lượt tìm cũ còn bay thì bỏ (lời đáp về muộn không hiện đè lên). */
    fun searchCovers() {
        search?.cancel()
        val query = coversFlow.value.query
        coversFlow.update { it.copy(searching = true, error = false, unset = null) }
        search = scope.launch {
            try {
                val found = source.findCovers(id, query)
                coversFlow.update { it.copy(searching = false, searched = true, error = false, results = found.results, failed = found.failed, broken = emptySet()) }
            } catch (error: Exception) {
                if (error is CancellationException) throw error
                coversFlow.update { it.copy(searching = false, searched = true, error = true, results = emptyList(), failed = emptyList()) }
            }
        }
    }

    /** Đặt ảnh đã chọn làm bìa; xong thì `done` (rời màn tìm). Một lúc một ảnh. */
    fun chooseCover(found: FoundCover, done: () -> Unit = {}) {
        if (coversFlow.value.choosing != null) return
        coversFlow.update { it.copy(choosing = found.url, unset = null) }
        choice = scope.launch {
            try {
                val saved = writes.withLock { source.coverFromUrl(id, found.url) }
                flow.value = flow.value.copy(saved = saved, draft = EditLogic.rebase(flow.value.saved, flow.value.draft, saved), problem = "")
                coversFlow.update { it.copy(choosing = null) }
                done()
            } catch (error: Exception) {
                if (error is CancellationException) throw error
                coversFlow.update { it.copy(choosing = null, unset = found) }
            }
        }
    }

    /** Rời màn tìm: lượt tìm và lượt đặt bìa còn chạy thì bỏ. */
    fun stopCoverSearch() {
        search?.cancel()
        choice?.cancel()
        coversFlow.update { it.copy(searching = false, choosing = null) }
    }

    /** Ảnh nhỏ của một kết quả (nhớ trong lượt tìm này); không tải được thì bỏ ô ấy khỏi lưới. */
    suspend fun thumbnail(url: String): ImageBitmap? {
        thumbs[url]?.let { return it }
        val image = source.thumbnail(url)
        if (image != null) thumbs[url] = image else coversFlow.update { it.copy(broken = it.broken + url) }
        return image
    }

    private suspend fun attempt(block: suspend () -> EditSnapshot): Boolean {
        val before = flow.value.draft
        flow.value = flow.value.copy(saving = true, problem = "")
        return try {
            val saved = block()
            val latest = flow.value.draft
            flow.value = EditState(saved, if (latest == before) EditLogic.draft(saved) else latest, loading = false)
            true
        } catch (error: Exception) {
            if (error is CancellationException) throw error
            flow.value = flow.value.copy(loading = false, saving = false, problem = error.message ?: "Bạn hãy thử lại.")
            false
        }
    }
}
