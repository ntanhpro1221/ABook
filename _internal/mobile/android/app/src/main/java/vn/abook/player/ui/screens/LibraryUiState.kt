package vn.abook.player.ui.screens

import androidx.compose.animation.core.Animatable
import androidx.compose.foundation.pager.PagerState
import androidx.compose.runtime.derivedStateOf
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

/** Library filter pages and their indicator share one continuous pager position. */
@Stable
class LibraryUiState(
    private val scope: CoroutineScope,
    sort: LibrarySort = LibrarySort.Recent,
    private val onSortChanged: (LibrarySort) -> Unit = {},
) {
    /** Bộ lọc người dùng vừa chọn (vạch, chữ đậm). */
    var filter by mutableStateOf(LibraryFilter.All)
        private set

    /** Selected page; each resident page builds content from its own filter. */
    val shown: LibraryFilter get() = filter

    var sort by mutableStateOf(sort)
        private set
    var query by mutableStateOf("")
        private set
    var searchOpen by mutableStateOf(false)
        private set
    var menuOpen by mutableStateOf(false)
        private set

    /** Chỉ số bộ lọc theo đơn vị chữ (0f..3f): vị trí vạch hổ phách và độ đậm màu chữ. */
    val pager = PagerState(pageCount = { LibraryFilter.entries.size })
    val position = derivedStateOf { pager.currentPage + pager.currentPageOffsetFraction }


    /** Ô tìm: 0 = chỉ là biểu tượng, 1 = nở hết hàng. */
    val search = Animatable(0f)

    private var job: Job? = null
    private var searchJob: Job? = null

    fun select(target: LibraryFilter) {
        if (target == filter) return
        filter = target
        job?.cancel()
        job = scope.launch { pager.animateScrollToPage(target.ordinal, animationSpec = Motion.TabSlide) }
    }

    fun settled(page: Int) { filter = LibraryFilter.entries[page] }

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

    /** Nút X của ô tìm (web: LibraryScreen.tsx): có chữ thì xoá chữ, ô vẫn mở để gõ lại; ô trống thì đóng ô. */
    fun clearOrClose() {
        if (query.isNotEmpty()) query = "" else closeSearch()
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
