package vn.abook.player.ui.studio

import androidx.compose.runtime.Immutable
import androidx.compose.runtime.Stable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import org.json.JSONObject
import vn.abook.player.StudioErrors
import vn.abook.player.StudioPoller
import vn.abook.player.StudioPolling

// "Duyệt trước khi thu" (NATIVE_REMOTE_STUDIO.md §6.9). Port từ precast.ts / PrecastReview.tsx (webui/precast.py): ngay khi phân tích xong và trước khi thu những chương
// đầu, dẫn qua đúng thứ tự người duyệt cần. Không bước nào chặn dây chuyền; chỉ khi bật "Chờ tôi duyệt" thì sách đứng lại (tạm dừng) và chờ nút "Thu âm".

@Immutable
data class PrecastChapter(val id: Int, val title: String)

/** Lời đáp của `GET /api/books/<id>/precast`. */
@Immutable
data class PrecastView(
    val ready: Boolean,
    val wait: Boolean,
    /** Lúc Studio báo mốc phân tích xong (một lần mỗi cuốn); null = chưa. */
    val announcedAt: Double?,
    val held: Boolean,
    val chapters: Int,
    val recordedChapters: Int,
    /** Chương xa nhất đã thu xong: sửa ở chương sau nó không phải thu lại. */
    val recordedThrough: PrecastChapter?,
    /** Vài chương sắp thu, theo thứ tự đọc. */
    val upcoming: List<PrecastChapter>,
)

/** Bốn bước của màn duyệt (web `PRECAST_STEPS`). */
enum class PrecastStep(val label: String) {
    Cast("Nhân vật và giọng"),
    Names("Cách đọc tên"),
    Lines("Ai nói câu này"),
    Done("Xong"),
}

internal object StudioPrecastJson {
    private fun chapter(json: JSONObject?) = json?.let { PrecastChapter(it.optInt("id"), it.text("title")) }

    fun view(json: JSONObject) = PrecastView(
        ready = json.optBoolean("ready"),
        wait = json.optBoolean("wait"),
        announcedAt = if (json.isNull("announcedAt") || !json.has("announcedAt")) null else json.optDouble("announcedAt"),
        held = json.optBoolean("held"),
        chapters = json.optInt("chapters"),
        recordedChapters = json.optInt("recordedChapters"),
        recordedThrough = chapter(json.optJSONObject("recordedThrough")),
        upcoming = json.optJSONArray("upcoming").objects().mapNotNull(::chapter),
    )
}

object PrecastLogic {
    /** Những người nói nhiều nhất: giọng của họ nghe suốt cuốn. */
    const val TOP_PEOPLE = 6

    /** Nhịp hỏi lại (web `usePrecast`: 15 giây). */
    const val REFRESH_MS = 15_000L

    private val CAST_KINDS = setOf(WorkKind.Gender, WorkKind.Alias, WorkKind.SharedVoice)
    private val LINE_KINDS = setOf(WorkKind.Speaker, WorkKind.Turn, WorkKind.Vocative, WorkKind.Bracket, WorkKind.Unnamed)

    private fun open(items: List<WorkItem>) = items.filter(WorkLogic::isOpen)

    /** (a) Việc về người và giọng: nam hay nữ, một người hai tên, hai người chung giọng. Giữ thứ tự lợi / lần bấm của hộp việc. */
    fun castItems(items: List<WorkItem>): List<WorkItem> = open(items).filter { it.kind in CAST_KINDS }

    /** (b) Cách đọc tên máy tự đoán - tên máy kém chắc nhất trước, cùng mức thì tên gặp nhiều câu hơn trước. */
    fun nameItems(items: List<WorkItem>): List<WorkItem> =
        open(items).filter { it.kind == WorkKind.Pronunciation }.sortedWith(compareByDescending<WorkItem> { it.doubt }.thenByDescending { it.affected })

    /** (c) "Ai nói câu này" kém chắc ở các chương sắp thu - thu xong chương ấy thì sửa phải thu lại. */
    fun lineItems(items: List<WorkItem>, upcoming: List<Int>): List<WorkItem> {
        val ahead = upcoming.toSet()
        return open(items).filter { it.kind in LINE_KINDS && it.chapters.any { id -> id in ahead } }
    }

    /** Mã các thẻ nằm trong màn duyệt: tab "Việc cần duyệt" không hiện lại chúng. */
    fun keys(items: List<WorkItem>, upcoming: List<Int>): Set<String> =
        (castItems(items) + nameItems(items) + lineItems(items, upcoming)).map { it.key }.toSet()

    fun lineCount(items: List<WorkItem>): Int = items.sumOf { it.affected }

    /** "Chương 1" / "Chương 1 → Chương 3" cho các chương sắp thu (đã theo thứ tự đọc). */
    fun chapterRange(chapters: List<PrecastChapter>): String = when {
        chapters.isEmpty() -> ""
        chapters.size == 1 -> chapters.first().title
        else -> "${chapters.first().title} → ${chapters.last().title}"
    }

    /** Sửa tới đâu thì miễn phí: chưa thu gì là mọi sửa; đã thu tới chương X thì sửa ở chương sau X không phải thu lại. */
    fun freeNote(view: PrecastView): String = view.recordedThrough?.let {
        "Đã thu tới ${it.title} - sửa ở chương sau đó không phải thu lại; sửa chỗ đã thu thì máy thu lại đúng các câu ấy."
    } ?: "Chưa thu chương nào - sửa bây giờ không phải thu lại câu nào."

    /** Có nên mở màn duyệt: phân tích xong và phân vai đã khoá (web `precast.ready`), sách chưa xong. */
    fun canReview(book: StudioBook): Boolean = book.phase != "done" && book.castLocked

    /** Công tắc "Chờ tôi duyệt" chỉ có nghĩa trước mốc (Studio mở màn này cả khi chưa kịp báo, vd app đóng lúc phân tích xong). */
    fun showWait(view: PrecastView): Boolean = view.announcedAt == null && view.recordedChapters == 0

    /** Dòng phụ dưới công tắc. */
    fun waitHint(view: PrecastView): String = when {
        view.announcedAt != null -> PrecastText.WAIT_PASSED
        view.wait -> PrecastText.WAIT_ON
        else -> PrecastText.WAIT_OFF
    }

    /** Số việc mỗi bước, ngắn (dòng phụ của bước). */
    fun count(step: PrecastStep, cast: List<WorkItem>, names: List<WorkItem>, lines: List<WorkItem>, people: Int): String = when (step) {
        PrecastStep.Cast -> if (cast.isNotEmpty()) "${cast.size} việc" else "$people người"
        PrecastStep.Names -> if (names.isNotEmpty()) "${names.size} tên" else "ổn"
        PrecastStep.Lines -> if (lines.isNotEmpty()) "${lineCount(lines)} câu" else "ổn"
        PrecastStep.Done -> ""
    }

    fun next(step: PrecastStep): PrecastStep = PrecastStep.entries[minOf(step.ordinal + 1, PrecastStep.entries.lastIndex)]
}

object PrecastText {
    const val TITLE = "Duyệt trước khi thu"
    const val LEAD = "Duyệt nhanh trước khi thu; có thể bỏ qua từng bước."
    const val HELD = "Sách đang chờ bạn duyệt - duyệt xong bấm “Thu âm”."
    const val WAIT = "Duyệt trước khi thu"
    const val WAIT_PASSED = "Phân tích đã xong. Muốn dừng thì bấm “Tạm dừng”."
    const val WAIT_ON = "Dừng sau phân tích để bạn duyệt, rồi bấm “Thu âm”."
    const val WAIT_OFF = "Phân tích xong thì thu luôn; duyệt lúc nào cũng được."
    const val WHEN = "Khi áp dụng"
    const val LOADING = "Đang tải lượt duyệt"
    const val CAST_LEAD = "Nghe và chỉnh giọng cho những nhân vật nói nhiều nhất."
    const val CAST_UNSURE = "Máy chưa chắc"
    const val NAMES_ALL = "Xem và sửa cách đọc từng tên ở danh sách riêng."
    const val NAMES_OPEN = "Cách đọc tên"
    const val SKIP = "Bỏ qua bước này"
    const val NEXT = "Tiếp tục"
    const val DONE_TITLE = "Xong lượt duyệt"
    const val FINISH = "Duyệt xong"
    const val RECORD = "Thu âm"
    const val BACK = "Về danh sách chương"
    const val DONE_HELD = "Đã ghi lại. Bấm “Thu âm” để làm tiếp."
    const val DONE_RUNNING = "Sửa nào cũng đã ghi lại; máy áp ở chương kế tiếp. Những chỗ khác máy chưa chắc vẫn ở “Việc cần duyệt”."
    const val DONE_IDLE = "Sửa nào cũng đã ghi lại; máy áp khi sách chạy tiếp. Những chỗ khác máy chưa chắc vẫn ở “Việc cần duyệt”."
    const val SAME_NAME = "Cùng tên với người khác trong sách - một người?"

    fun step(index: Int, total: Int) = "Bước $index/$total"
    fun castUnsure(count: Int) = "$count việc về người và giọng"
    fun namesLead(count: Int) = if (count > 0) "Nghe và sửa $count cách đọc tên, tên kém chắc ở trên." else NAMES_ALL
    fun linesLead(count: Int, range: String, anyUpcoming: Boolean) = when {
        count > 0 -> "$count câu máy chưa chắc ai nói ở ${range.ifEmpty { "những chương sắp thu" }} - các chương thu đầu tiên; các chương sau xem ở Việc cần duyệt."
        anyUpcoming -> "Không có câu nghi ngờ ở $range; các chương sau xem ở Việc cần duyệt."
        else -> "Đã thu mọi chương; các chương sau xem ở Việc cần duyệt."
    }

    fun done(book: StudioBook) = when {
        book.precastHeld -> DONE_HELD
        book.running -> DONE_RUNNING
        else -> DONE_IDLE
    }
}

/**
 * Màn duyệt của một dự án: số liệu `GET /precast` (15 giây một lần), bước đang mở, và công tắc "Chờ tôi duyệt" (`PUT /precast`). Thẻ việc, người nói, giọng lấy từ
 * chính [StudioWorkState] / [StudioCastState] của dự án - cùng quyết định, cùng hàng chờ "Hoàn tác".
 */
@Stable
class StudioPrecastState(private val project: StudioProjectState, pause: suspend (Long) -> Unit = { delay(it) }) {
    private val session get() = project.session
    private val poller = StudioPoller<PrecastView>({ session.source.precast(session.computer, project.bookId) }, { PrecastLogic.REFRESH_MS }, pause)
    val poll: StateFlow<StudioPolling.Poll<PrecastView>> get() = poller.state

    var step by mutableStateOf(PrecastStep.Cast)
        private set

    var saving by mutableStateOf(false)
        private set

    var problem by mutableStateOf("")
        private set

    suspend fun run() = poller.run()

    suspend fun refresh() = poller.refresh()

    fun open(next: PrecastStep) {
        step = next
    }

    fun next() {
        step = PrecastLogic.next(step)
    }

    /** `PUT /precast {wait}`: bật = dây chuyền dừng ở cổng này sau phân tích. */
    fun setWait(value: Boolean) {
        if (saving) return
        saving = true
        problem = ""
        session.scope.launch {
            try {
                session.source.put(session.computer, project.bookId, "precast", JSONObject().put("wait", value))
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (error: Throwable) {
                val failure = StudioErrors.of(error)
                session.note(failure)
                problem = StudioText.failure(failure)
            } finally {
                saving = false
            }
            poller.refresh()
            project.refresh()
        }
    }
}
