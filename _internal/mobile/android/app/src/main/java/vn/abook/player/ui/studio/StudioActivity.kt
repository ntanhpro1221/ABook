package vn.abook.player.ui.studio

import androidx.compose.runtime.Immutable
import androidx.compose.runtime.Stable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import org.json.JSONArray
import vn.abook.player.StudioPoller
import vn.abook.player.StudioPolling
import vn.abook.player.ui.data.Fmt

// "Nhật ký" và thông tin của một dự án (NATIVE_REMOTE_STUDIO.md §6.14). `GET /api/books/<id>/activity[?technical=1]` trả MẢNG (ActivityView của ProjectScreen.tsx):
// diễn biến là mặc định; "Chi tiết kỹ thuật" là phần mở thêm của chính danh sách, không phải tab lồng trong tab.

/** Một dòng nhật ký: `level` info | success | warning | error; `code` chỉ có ở chế độ kỹ thuật. */
@Immutable
data class StudioLogItem(val id: String, val at: Double, val level: String, val code: String, val text: String)

internal object StudioActivityJson {
    fun items(array: JSONArray): List<StudioLogItem> = array.objects().map {
        StudioLogItem(it.text("id"), it.optDouble("at", 0.0).let { at -> if (at.isFinite()) at else 0.0 }, it.text("level").ifEmpty { "info" }, it.text("code"), it.text("text"))
    }
}

object StudioActivityLogic {
    /** Nhịp hỏi khi máy đang làm sách (web: 5 giây); sách rảnh thì không hỏi theo nhịp. */
    const val LIVE_MS = 5_000L

    /** Mục gần nhất ở trên: máy trả cũ trước hay mới trước đều được - sắp lại một lần ở đây. */
    fun ordered(items: List<StudioLogItem>): List<StudioLogItem> = items.sortedByDescending { it.at }

    /** Giờ của một dòng: "hôm nay 14:02". */
    fun at(item: StudioLogItem, nowMs: Long = System.currentTimeMillis()): String = Fmt.whenText(item.at, nowMs)

    /** Thông tin chỉ đọc của dự án: nhãn + giá trị, theo thứ tự hiện. */
    fun facts(page: StudioPage): List<Pair<String, String>> {
        val book = page.book
        val seconds = page.chapters.sumOf { it.seconds }
        return buildList {
            add(StudioActivityText.STATUS to StudioLogic.status(book).label)
            add(StudioActivityText.CHAPTERS to StudioActivityText.chapters(book.chaptersCompleted, book.chaptersTotal))
            if (seconds > 0) add(StudioActivityText.LENGTH to Fmt.length(seconds))
        }
    }
}

object StudioActivityText {
    const val TITLE = "Nhật ký"
    const val INFO = "Thông tin"
    const val STATUS = "Trạng thái"
    const val CHAPTERS = "Chương"
    const val LENGTH = "Dài"
    const val EMPTY = "Chưa có gì"
    const val EMPTY_HINT = "Diễn biến hiện ở đây khi sách bắt đầu chạy."
    const val LOADING = "Đang mở nhật ký"
    const val TECHNICAL = "Chi tiết kỹ thuật"

    fun chapters(done: Int, total: Int) = if (total > 0) "$done/$total xong" else "$done"
    fun count(count: Int) = "$count mục gần nhất"
}

/** Nhật ký của một dự án: hỏi 5 giây một lần khi máy đang làm sách, không thì chỉ hỏi lúc mở; bật "Chi tiết kỹ thuật" thì hỏi lại ngay. */
@Stable
class StudioActivityState(private val project: StudioProjectState, pause: suspend (Long) -> Unit = { delay(it) }) {
    private val session get() = project.session

    var technical by mutableStateOf(false)
        private set

    private val poller = StudioPoller<List<StudioLogItem>>(
        { session.source.activity(session.computer, project.bookId, technical) },
        { if (project.live) StudioActivityLogic.LIVE_MS else null },
        pause,
    )
    val poll: StateFlow<StudioPolling.Poll<List<StudioLogItem>>> get() = poller.state

    suspend fun run() = poller.run()

    suspend fun refresh() = poller.refresh()

    fun refreshSoon() {
        session.scope.launch { poller.refresh() }
    }

    fun showTechnical(on: Boolean) {
        if (technical == on) return
        technical = on
        refreshSoon()
    }
}
