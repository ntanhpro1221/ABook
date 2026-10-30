package vn.abook.player.ui.studio

import androidx.compose.runtime.Stable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import org.json.JSONObject
import vn.abook.player.ClipState
import vn.abook.player.StudioErrors
import vn.abook.player.StudioPoller
import vn.abook.player.StudioPolling
import vn.abook.player.ui.data.Choice

/** Bộ lọc tab "Cần nghe lại" (web `filter`): câu chưa có cách xử lý, hay đã có. */
enum class ReviewFilter(override val key: String, override val label: String) : Choice { Todo("todo", "Chưa xem"), Done("done", "Đã xem") }

/** Các trang đã nạp của một bộ lọc, gộp lại: đếm và chương chờ thu lại lấy của trang đầu, còn lại của trang cuối (như `ReviewQueue.tsx`). */
data class ReviewList(
    val filter: ReviewFilter,
    val minor: Boolean,
    val items: List<ReviewItem>,
    val pending: Int,
    val counts: Map<ReviewKind, Int>,
    val redoChapters: List<Int>,
    val nextCursor: String?,
    val remaining: Int,
)

/** Máy khác hay cửa sổ khác vừa phán quyết khác cho câu này: hỏi giữ của mình hay lấy của máy kia. `theirs` rỗng = máy kia không đặt gì. */
data class ReviewElsewhere(val stableId: String, val chapterId: Int, val audioSha256: String, val theirs: String)

/**
 * Tab "Cần nghe lại" (NATIVE_REMOTE_STUDIO.md §6.5): câu khâu tự kiểm không chắc, nghe rồi bấm Ổn hay Cần thu lại. Phán quyết gửi ngay (như web, không có
 * hoàn tác 15 giây - bấm lại lần nữa là bỏ phán quyết) và hiện ngay trên màn trước khi máy trả lời. Nghe đi qua [vn.abook.player.StudioClips]: tải chương một lần
 * vào cache, phát đúng đoạn của câu. "Nghe liền" tự sang câu kế nghe được khi câu này phát hết.
 */
@Stable
class StudioReviewState(private val project: StudioProjectState, pause: suspend (Long) -> Unit = { delay(it) }) {
    private val session get() = project.session
    private var wanted = 1
    private val poller = StudioPoller<ReviewList>({ fetch() }, { if (project.live) StudioWorkState.PRODUCING_REFRESH_MS else null }, pause)
    val poll: StateFlow<StudioPolling.Poll<ReviewList>> get() = poller.state

    var filter by mutableStateOf(ReviewFilter.Todo)
        private set

    /** Cả câu lệch nhẹ ("Hiện N câu nhẹ"). */
    var showMinor by mutableStateOf(false)
        private set

    /** Phán quyết vừa bấm mà máy chưa xác nhận (null = vừa bỏ phán quyết). */
    var verdicts by mutableStateOf<Map<String, String?>>(emptyMap())
        private set

    /** Đang "Nghe liền". */
    var continuous by mutableStateOf(false)
        private set

    /** Vừa nghe hết các câu trong danh sách. */
    var finished by mutableStateOf(false)
        private set

    var elsewhere by mutableStateOf<ReviewElsewhere?>(null)
        private set

    /** Lời báo khi một phán quyết không ghi được ("" = không có). */
    var problem by mutableStateOf("")
        private set

    var loadingMore by mutableStateOf(false)
        private set

    val clip: StateFlow<ClipState>? get() = session.clips?.state

    val book: StudioBook? get() = project.poll.value.data?.book

    private suspend fun fetch(): ReviewList {
        val filter = filter
        val minor = showMinor
        val count = wanted
        val first = session.source.review(session.computer, project.bookId, filter.key, minor, "")
        var items = first.items
        var cursor = first.nextCursor
        var remaining = first.remaining
        var read = 1
        while (read < count && cursor != null) {
            val next = session.source.review(session.computer, project.bookId, filter.key, minor, cursor)
            items = items + next.items
            cursor = next.nextCursor
            remaining = next.remaining
            read++
        }
        return ReviewList(filter, minor, items.distinctBy { it.stableId }, first.pending, first.counts, first.redoChapters, cursor, remaining)
    }

    suspend fun run() = poller.run()

    suspend fun refresh() = poller.refresh()

    /** Danh sách của bộ lọc đang chọn (null khi chưa về, hay còn là của bộ lọc cũ). */
    fun list(): ReviewList? = poller.state.value.data?.takeIf { it.filter == filter && it.minor == showMinor }

    /** Các câu hiện ra: phán quyết vừa bấm áp lên trước, rồi lọc theo "chưa xem / đã xem". */
    fun items(): List<ReviewItem> = list()?.items.orEmpty().map { item ->
        if (item.stableId in verdicts) item.copy(verdict = verdicts[item.stableId]) else item
    }.filter { if (filter == ReviewFilter.Todo) !ReviewLogic.handled(it) else ReviewLogic.handled(it) }

    fun pick(next: ReviewFilter) {
        if (next == filter) return
        filter = next
        wanted = 1
        reload()
    }

    fun toggleMinor() {
        showMinor = !showMinor
        wanted = 1
        reload()
    }

    fun loadMore() {
        if (loadingMore || list()?.nextCursor == null) return
        loadingMore = true
        wanted++
        session.scope.launch {
            try {
                poller.refresh()
            } finally {
                loadingMore = false
            }
        }
    }

    fun refreshSoon() = reload()

    private fun reload() {
        session.scope.launch { poller.refresh() }
    }

    // ---- nghe ----

    fun clipOf(item: ReviewItem) = ReviewLogic.clip(session.computer, project.bookId, item)

    /** Bấm nghe một câu (bấm lại: dừng). Phát hết thì, khi đang "Nghe liền", sang câu kế nghe được. */
    fun play(item: ReviewItem) {
        val spec = clipOf(item) ?: return
        session.clips?.toggle(ReviewLogic.clipId(item), spec) { if (continuous) playNext(item.stableId) }
    }

    fun startContinuous() {
        continuous = true
        finished = false
        playNext(null)
    }

    fun stopContinuous() {
        continuous = false
        session.clips?.stop()
    }

    private fun playNext(after: String?) {
        val next = ReviewLogic.nextPlayable(items(), session.computer, project.bookId, after)
        if (next == null) {
            continuous = false
            finished = true
            return
        }
        play(next)
    }

    /** Đóng tab / màn: dừng tiếng, thôi nghe liền. */
    fun release() {
        continuous = false
        session.clips?.stop()
    }

    // ---- phán quyết ----

    /** Phán quyết một câu; `value` null = bỏ phán quyết. Đang nghe liền mà bấm khi câu này đang phát thì sang câu kế ngay. */
    fun judge(item: ReviewItem, value: String?) {
        val shown = items().firstOrNull { it.stableId == item.stableId } ?: return
        problem = ""
        elsewhere = null
        val advance = continuous && session.clips?.state?.value?.playing == ReviewLogic.clipId(item)
        val next = if (advance) ReviewLogic.nextPlayable(items(), session.computer, project.bookId, item.stableId) else null
        verdicts = verdicts + (item.stableId to value)
        if (advance) {
            session.clips?.stop()
            if (next != null) play(next) else {
                continuous = false
                finished = true
            }
        }
        session.scope.launch {
            try {
                val answer = write(WorkDecisions.review(item.stableId, item.chapterId, item.audioSha256, value, shown.verdict.orEmpty()))
                val theirs = (answer.opt("elsewhere") as? JSONObject)?.takeIf { it.has(item.stableId) }?.optString(item.stableId)
                if (theirs != null) elsewhere = ReviewElsewhere(item.stableId, item.chapterId, item.audioSha256, theirs)
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (error: Throwable) {
                val failure = StudioErrors.of(error)
                session.note(failure)
                problem = StudioText.failure(failure)
            }
            poller.refresh()
            verdicts = verdicts - item.stableId
            project.refreshSoon()
        }
    }

    /** "Lấy của máy kia": ghi lại đúng phán quyết máy kia đã đặt (hay bỏ phán quyết nếu máy kia không đặt gì). */
    fun takeTheirs() {
        val note = elsewhere ?: return
        elsewhere = null
        session.scope.launch {
            try {
                write(WorkDecisions.review(note.stableId, note.chapterId, note.audioSha256, note.theirs.ifEmpty { null }, null))
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (error: Throwable) {
                problem = StudioText.failure(StudioErrors.of(error))
            }
            poller.refresh()
        }
    }

    fun dismissElsewhere() {
        elsewhere = null
    }

    private suspend fun write(step: WorkStep): JSONObject = session.source.write(session.computer, project.bookId, step)
}
