package vn.abook.player.ui.screens

import androidx.compose.animation.core.Animatable
import androidx.compose.runtime.Stable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch
import vn.abook.player.ui.data.LibraryFilter
import vn.abook.player.ui.data.LibrarySort
import vn.abook.player.ui.motion.Motion

/**
 * Trạng thái của màn Thư viện sống ở khung (ShellState) để rời tab / quay lại không mất: bộ lọc, cách xếp, ô tìm và ba giá trị chạy theo khung -
 * vạch hổ phách dưới bộ lọc ([position]), nội dung lưới trượt theo chiều bộ lọc ([slide]), ô tìm nở ra ([search]). Cả ba chỉ đọc trong pha vẽ / dàn trang.
 *
 * Đổi bộ lọc: vạch trượt sang chữ mới ngay, còn lưới trượt RA (90 ms) theo chiều ngón tay rồi đổi dữ liệu và trượt VÀO (220 ms) từ phía kia - chỉ dịch ngang,
 * không mờ. Lưới lười không giữ được hai bộ ô chồng nhau nên hai nửa nối tiếp (xem NATIVE_P1A_PROGRESS.md).
 */
@Stable
class LibraryUiState(
    private val scope: CoroutineScope,
    sort: LibrarySort = LibrarySort.Recent,
    private val onSortChanged: (LibrarySort) -> Unit = {},
) {
    /** Bộ lọc người dùng vừa chọn (vạch, chữ đậm). */
    var filter by mutableStateOf(LibraryFilter.All)
        private set

    /** Bộ lọc của dữ liệu đang vẽ: theo [filter] sau nửa trượt ra. */
    var shown by mutableStateOf(LibraryFilter.All)
        private set

    var sort by mutableStateOf(sort)
        private set
    var query by mutableStateOf("")
        private set
    var searchOpen by mutableStateOf(false)
        private set
    var menuOpen by mutableStateOf(false)
        private set

    /** Chỉ số bộ lọc theo đơn vị chữ (0f..3f): vị trí vạch hổ phách và độ đậm màu chữ. */
    val position = Animatable(0f)

    /** Dịch ngang của các ô bìa theo bề rộng lưới: 0 = đúng chỗ. */
    val slide = Animatable(0f)

    /** Ô tìm: 0 = chỉ là biểu tượng, 1 = nở hết hàng. */
    val search = Animatable(0f)

    private var job: Job? = null
    private var searchJob: Job? = null

    fun select(target: LibraryFilter) {
        if (target == filter) return
        val direction = if (target.ordinal > filter.ordinal) 1f else -1f
        filter = target
        job?.cancel()
        job = scope.launch {
            launch { position.animateTo(target.ordinal.toFloat(), Motion.TabSlide) }
            slide.animateTo(-direction, Motion.SlideOut)
            shown = target
            slide.snapTo(direction)
            slide.animateTo(0f, Motion.SlideIn)
        }
    }

    fun openMenu() {
        menuOpen = true
    }

    fun closeMenu() {
        menuOpen = false
    }

    fun chooseSort(next: LibrarySort) {
        menuOpen = false
        if (next == sort) return
        sort = next
        onSortChanged(next)
    }

    /** Nạp cách xếp đã nhớ (không ghi lại). */
    fun restoreSort(saved: LibrarySort) {
        sort = saved
    }

    fun openSearch() {
        searchOpen = true
        searchJob?.cancel()
        searchJob = scope.launch { search.animateTo(1f, Motion.Expand) }
    }

    fun updateQuery(text: String) {
        query = text
    }

    /** Đóng ô tìm và xoá chữ đã gõ; ô còn hiện trong lúc thu lại. */
    fun closeSearch() {
        if (!searchOpen) return
        query = ""
        searchJob?.cancel()
        searchJob = scope.launch {
            search.animateTo(0f, Motion.Collapse)
            searchOpen = false
        }
    }
}
