package vn.abook.player.ui.studio

import androidx.compose.runtime.Stable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import vn.abook.player.ClipSpec
import vn.abook.player.ClipState
import vn.abook.player.StudioError
import vn.abook.player.StudioErrors
import vn.abook.player.StudioPaths
import vn.abook.player.StudioPoller
import vn.abook.player.StudioPolling

/** Kết quả phép kiểm một cách đọc trước khi giữ 15 giây. */
sealed interface ReadingCheck {
    data object Ok : ReadingCheck
    data class Rejected(val message: String, val suggestion: String) : ReadingCheck
    data class Failed(val message: String) : ReadingCheck
}

/**
 * Bộ bài "Việc cần duyệt" của một dự án (NATIVE_REMOTE_STUDIO.md §6.4). Hỏi `GET /work` khi mở tab, rồi mỗi [PRODUCING_REFRESH_MS] khi sách đang chạy
 * (`liveRefresh.ts`: việc mới sinh ra theo chương; không chạy thì không có việc mới nên không hỏi theo nhịp). Quyết định đi qua [StudioDecisions] (giữ 15 giây).
 */
@Stable
class StudioWorkState(private val project: StudioProjectState, pause: suspend (Long) -> Unit = { delay(it) }) {
    private val session get() = project.session
    private val poller = StudioPoller<WorkView>(
        { session.source.work(session.computer, project.bookId) },
        { if (project.live) PRODUCING_REFRESH_MS else null },
        pause,
    )
    val poll: StateFlow<StudioPolling.Poll<WorkView>> get() = poller.state

    /** Thẻ người duyệt bấm "Bỏ qua": xuống cuối bộ bài, không gửi gì. */
    var skipped by mutableStateOf<List<String>>(emptyList())
        private set

    val decisions: StudioDecisions get() = project.decisions

    val clip: StateFlow<ClipState>? get() = session.clips?.state

    suspend fun run() = poller.run()

    suspend fun refresh() = poller.refresh()

    fun refreshSoon() {
        session.scope.launch { poller.refresh() }
    }

    /** Nghe một câu ví dụ trên thẻ (bản thu riêng của câu); bấm lại để dừng. */
    fun playExample(example: WorkExample) {
        session.clips?.toggle(clipId(example), ClipSpec(session.computer, StudioPaths.sample(project.bookId, example.segmentId)))
    }

    /** Rời tab: dừng tiếng. */
    fun release() {
        session.clips?.stop()
    }

    /** Bộ bài từ danh sách mới nhất: thẻ chờ duyệt, bỏ thẻ đang chờ gửi, thẻ "Bỏ qua" xuống cuối. */
    fun deck(view: WorkView?): List<WorkItem> = if (view == null) emptyList() else WorkLogic.deck(view.items, decisions.hiding(), skipped)

    fun skip(key: String) {
        skipped = skipped - key + key
    }

    /** Quyết xong một thẻ: giữ 15 giây cho "Hoàn tác" rồi gửi. */
    fun decide(decision: WorkDecision) {
        skipped = skipped - decision.key
        decisions.hold(decision)
    }

    /** Sau mỗi lần gửi: nạp lại bộ bài; thẻ đã gửi chỉ rời `away` khi danh sách mới về được (máy đã đánh dấu nó là đã quyết). */
    suspend fun afterSend() {
        val keys = decisions.away
        poller.refresh()
        if (poller.state.value.error == null) decisions.forgetSent(keys)
    }

    /** Trang kế câu ví dụ của thẻ nhóm lớn. */
    suspend fun moreExamples(item: WorkItem, loaded: Int): WorkExamplesPage =
        session.source.workExamples(session.computer, project.bookId, item.key, loaded, PICK_PAGE)

    /** Kiểm cách đọc (nghe được là lưu được) trước khi giữ 15 giây. */
    suspend fun checkReading(item: WorkItem, spoken: String): ReadingCheck = try {
        session.source.write(session.computer, project.bookId, WorkDecisions.pronunciationCheck(item, spoken))
        ReadingCheck.Ok
    } catch (cancelled: CancellationException) {
        throw cancelled
    } catch (error: Throwable) {
        val failure = StudioErrors.of(error)
        session.note(failure)
        if (failure is StudioError.Server && failure.status == 400) ReadingCheck.Rejected(failure.message.orEmpty(), StudioErrors.detail(failure, "suggestion"))
        else ReadingCheck.Failed(StudioText.failure(failure))
    }

    /** "Nghe thử" một cách đọc tên: máy đọc một câu có tên ấy bằng cách đọc đang gõ. */
    suspend fun previewReading(item: WorkItem, spoken: String): PreviewOutcome = session.preview(project.bookId, WorkDecisions.pronunciationPreview(item, spoken))

    /** Phát bản nghe thử (tải về cache rồi phát); bấm lại thì dừng. */
    fun playPreview(preview: VoicePreview) {
        session.clips?.toggle("try-${preview.url}", ClipSpec(session.computer, preview.url))
    }

    companion object {
        fun clipId(example: WorkExample) = "work-${example.segmentId}"

        /** Nhịp hỏi lại danh sách khi sách đang chạy (`liveRefresh.ts PRODUCING_REFRESH_MS`). */
        const val PRODUCING_REFRESH_MS = 15_000L

        /** Một trang câu ví dụ của thẻ nhóm lớn (`WorkInbox.tsx PICK_PAGE`). */
        const val PICK_PAGE = 100
    }
}
