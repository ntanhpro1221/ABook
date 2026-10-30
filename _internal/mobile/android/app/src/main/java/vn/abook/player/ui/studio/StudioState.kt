package vn.abook.player.ui.studio

import androidx.compose.runtime.Stable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import vn.abook.player.StudioError
import vn.abook.player.StudioErrors
import vn.abook.player.StudioPoller
import vn.abook.player.StudioPolling

/**
 * Phiên làm việc với MỘT máy tính: nguồn dữ liệu và trạng thái quyền dùng chung cho mọi màn Studio của máy ấy (NATIVE_REMOTE_STUDIO.md §3.4). Máy nói
 * `listenOnly` (công tắc điều khiển sản xuất hay quyền của điện thoại này đang tắt) ở bất cứ lời gọi nào thì cả Studio chỉ còn một thẻ "Máy tính chưa
 * cho bạn sửa" - không có nút xám rải rác.
 */
@Stable
class StudioSession(val computer: String, val source: StudioSource, val scope: CoroutineScope) {
    /** Một lệnh (không phải lần hỏi định kỳ) vừa bị từ chối vì chỉ nghe; lần hỏi định kỳ báo qua `poll.error` của từng màn. */
    var listenOnly by mutableStateOf(false)
        private set

    /** Tăng mỗi lần bấm "Thử lại": các màn khởi động lại nhịp hỏi (nhịp đã dừng vì chỉ nghe không tự chạy lại). */
    var retries by mutableIntStateOf(0)
        private set

    val name: String get() = source.name(computer)

    fun note(error: StudioError) {
        if (error is StudioError.ListenOnly) listenOnly = true
    }

    fun retry() {
        listenOnly = false
        retries++
    }
}

/** Các phiên theo máy tính; sống cùng tiến trình (Application) để rời màn rồi quay lại không phải hỏi lại quyền. */
@Stable
class StudioHub(private val source: StudioSource, private val scope: CoroutineScope) {
    private val sessions = HashMap<String, StudioSession>()

    fun session(computer: String): StudioSession = sessions.getOrPut(computer) { StudioSession(computer, source, scope) }
}

/** Danh sách dự án của một máy tính (6.1): hỏi 5 giây một lần khi có sách chạy, 15 giây khi rảnh; chỉ hỏi khi màn đang hiện ([run] trong `repeatOnLifecycle`). */
@Stable
class StudioHomeState(val session: StudioSession, pause: suspend (Long) -> Unit = { delay(it) }) {
    private val poller = StudioPoller<List<StudioBook>>({ session.source.library(session.computer) }, StudioLogic::listInterval, pause)
    val poll: StateFlow<StudioPolling.Poll<List<StudioBook>>> get() = poller.state

    /** Máy tính khác phiên bản: nói một dải đầu danh sách thay vì để lỗi lạ xuất hiện giữa chừng. */
    var mismatched by mutableStateOf(false)
        private set

    suspend fun run() {
        mismatched = try {
            session.source.mismatched(session.computer)
        } catch (error: StudioError) {
            false
        }
        poller.run()
    }

    suspend fun refresh() = poller.refresh()

    /** "Thử lại": hỏi ngay một lần ở phạm vi của phiên (không mất khi màn đóng giữa chừng). */
    fun refreshSoon() {
        session.scope.launch { poller.refresh() }
    }
}

/**
 * Một dự án (6.2): trang sách hỏi 3 giây một lần khi máy đang làm, 15 giây khi rảnh. Lệnh của nút chính chạy ở phạm vi của phiên (không mất khi bạn
 * bấm Back giữa chừng) và mỗi lúc chỉ một lệnh (như `scope: start-stop` của web).
 */
@Stable
class StudioProjectState(val session: StudioSession, val bookId: String, tab: StudioTab = StudioTab.Chapters, pause: suspend (Long) -> Unit = { delay(it) }) {
    private val poller = StudioPoller<StudioPage>({ session.source.book(session.computer, bookId) }, StudioLogic::bookInterval, pause)
    val poll: StateFlow<StudioPolling.Poll<StudioPage>> get() = poller.state

    var tab by mutableStateOf(tab)

    /** Một lệnh đang chạy: nút chính nhạt đi, không gửi thêm lệnh thứ hai. */
    var busy by mutableStateOf(false)
        private set

    /** Lời máy trả khi lệnh vừa rồi hỏng ("" khi không có): hiện tại chỗ dưới nút chính, kèm "Thử lại". */
    var problem by mutableStateOf("")
        private set

    private var last: StudioCommand? = null

    suspend fun run() = poller.run()

    suspend fun refresh() = poller.refresh()

    fun refreshSoon() {
        session.scope.launch { poller.refresh() }
    }

    fun send(command: StudioCommand) {
        if (busy) return
        busy = true
        problem = ""
        last = command
        session.scope.launch {
            try {
                session.source.command(session.computer, bookId, command)
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (error: Throwable) {
                val failure = StudioErrors.of(error)
                session.note(failure)
                problem = StudioText.failure(failure)
            } finally {
                busy = false
            }
            // Dù lệnh thành hay hỏng, đọc lại để nút chính đổi sang trạng thái thật (sách đã tự dừng, hàng đã đi...).
            poller.refresh()
        }
    }

    /** "Thử lại" dưới lỗi của lệnh. */
    fun retryLast() {
        last?.let(::send)
    }
}
