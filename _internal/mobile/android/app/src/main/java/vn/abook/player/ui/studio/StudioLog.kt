package vn.abook.player.ui.studio

import vn.abook.player.S

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

internal object StudioLogJson {
    fun items(array: JSONArray): List<StudioLogItem> = array.objects().map {
        StudioLogItem(it.text("id"), it.optDouble("at", 0.0).let { at -> if (at.isFinite()) at else 0.0 }, it.text("level").ifEmpty { "info" }, it.text("code"), it.text("text"))
    }
}

object StudioLogLogic {
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
            add(StudioLogText.STATUS to StudioLogic.status(book).label)
            add(StudioLogText.CHAPTERS to StudioLogText.chapters(book.chaptersCompleted, book.chaptersTotal))
            if (seconds > 0) add(StudioLogText.LENGTH to Fmt.length(seconds))
        }
    }
}

object StudioLogText {
    const val TITLE = S.s_nhat_ky_1e6c3c10
    const val INFO = S.s_thong_tin_4aa16c92
    const val STATUS = S.s_trang_thai_cb31de81
    const val CHAPTERS = S.s_chuong_2d157977
    const val LENGTH = S.s_dai_c9cdc15c
    const val EMPTY = S.s_chua_co_gi_adba6b1d
    const val EMPTY_HINT = S.s_dien_bien_se_hien_o_day_khi_sach_bat_dau_c_7794dda1
    const val LOADING = S.s_dang_mo_nhat_ky_9a166cda
    const val TECHNICAL = S.s_chi_tiet_ky_thuat_f27eb5f6

    fun chapters(done: Int, total: Int) = if (total > 0) "$done/$total xong" else "$done"
    fun count(count: Int) = S.s_0_muc_gan_nhat_fd2e30e0(count)
}

/** Nhật ký của một dự án: hỏi 5 giây một lần khi máy đang làm sách, không thì chỉ hỏi lúc mở; bật "Chi tiết kỹ thuật" thì hỏi lại ngay. */
@Stable
class StudioLogState(private val project: StudioProjectState, pause: suspend (Long) -> Unit = { delay(it) }) {
    private val session get() = project.session

    var technical by mutableStateOf(false)
        private set

    private val poller = StudioPoller<List<StudioLogItem>>(
        { session.source.activity(session.computer, project.bookId, technical) },
        { if (project.live) StudioLogLogic.LIVE_MS else null },
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
