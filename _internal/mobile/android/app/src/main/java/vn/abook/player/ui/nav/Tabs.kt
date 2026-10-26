package vn.abook.player.ui.nav

import androidx.compose.animation.core.Animatable
import androidx.compose.runtime.Stable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.setValue
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
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
 * lẫn vạch chỉ tab - cả hai đọc nó trong pha vẽ, nên đổi tab không dựng lại gì ngoài hai tab kề nhau lúc bắt đầu / kết thúc.
 */
@Stable
class TabState(private val scope: CoroutineScope, initial: Tab = Tab.Library) {
    var selected by mutableIntStateOf(initial.ordinal)
        private set

    val position = Animatable(initial.ordinal.toFloat())
    private var job: Job? = null

    fun select(tab: Tab) {
        if (tab.ordinal == selected) return
        selected = tab.ordinal
        job?.cancel()
        job = scope.launch { position.animateTo(tab.ordinal.toFloat(), Motion.TabSlide) }
    }
}
