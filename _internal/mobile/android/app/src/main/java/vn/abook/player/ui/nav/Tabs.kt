package vn.abook.player.ui.nav

import androidx.compose.animation.core.Animatable
import androidx.compose.runtime.Stable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.setValue
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import vn.abook.player.ui.motion.Motion

/** Ba tab đáy, theo thứ tự trái -> phải (chỉ số tab quyết định chiều trượt). */
enum class Tab(val label: String, val tag: String) {
    Library("Thư viện", "tab_library"),
    Studio("Studio", "tab_studio"),
    Settings("Cài đặt", "tab_settings"),
}

/**
 * Tab đang chọn + vị trí trượt. [position] tính theo đơn vị tab (0f..2f) và là NGUỒN DUY NHẤT cho cả nội dung (tab i ở `(i - position)` bề rộng)
 * lẫn vạch chỉ tab - cả hai đọc nó trong pha vẽ, nên đổi tab không dựng lại gì.
 *
 * Tab đã từng hiện ([visitedMask]) ở lại trong cây mãi: đổi tab không phải dựng lại nó (đo trên máy thật: dựng tab lúc bắt đầu trượt là khung 31 ms).
 * Tab chưa hiện được dựng trước lúc rảnh ([precomposeRest]) ngay sau khung nội dung đầu.
 */
@Stable
class TabState(private val scope: CoroutineScope, initial: Tab = Tab.Library) {
    var selected by mutableIntStateOf(initial.ordinal)
        private set

    /** Bit i bật = tab i đã dựng (giữ trạng thái cuộn ở nơi khác - ShellState - nên tab chỉ cần ở lại trong cây). */
    var visitedMask by mutableIntStateOf(1 shl initial.ordinal)
        private set

    val position = Animatable(initial.ordinal.toFloat())
    private var job: Job? = null

    fun isVisited(tab: Tab): Boolean = visitedMask and (1 shl tab.ordinal) != 0

    fun visit(tab: Tab) {
        visitedMask = visitedMask or (1 shl tab.ordinal)
    }

    fun select(tab: Tab) {
        if (tab.ordinal == selected) return
        visit(tab)
        selected = tab.ordinal
        job?.cancel()
        job = scope.launch { position.animateTo(tab.ordinal.toFloat(), Motion.TabSlide) }
    }

    /**
     * Dựng trước các tab còn lại khi máy rảnh: chờ một khung + [afterMs], rồi mỗi khung một tab (không dồn hai tab vào cùng khung).
     * Gọi trong coroutine của composition (LaunchedEffect) sau khi Thư viện đã có nội dung.
     */
    suspend fun precomposeRest(afterMs: Long = 300) {
        androidx.compose.runtime.withFrameNanos { }
        delay(afterMs)
        for (tab in Tab.entries) {
            if (isVisited(tab)) continue
            visit(tab)
            androidx.compose.runtime.withFrameNanos { }
        }
    }
}
