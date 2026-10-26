package vn.abook.player.ui.nav

import androidx.compose.animation.core.Animatable
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.Stable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch
import vn.abook.player.ui.data.ListenBook
import vn.abook.player.ui.motion.Motion
import vn.abook.player.ui.motion.ScreenGeometry

/** Màn con xếp trên ba tab (trang sách và Đang phát còn là giữ chỗ; P1b/P2 làm thật). */
@Immutable
sealed interface Destination {
    data object AddBook : Destination
    data class ImportReview(val itemId: Long) : Destination
    data class EditBook(val book: ListenBook) : Destination
    data class EditChapter(val book: ListenBook, val chapterId: Long) : Destination
    data class CropCover(val book: ListenBook, val uri: String) : Destination
    @Immutable
    data class Book(val book: ListenBook) : Destination

    /** Trình phát đầy đủ - giữ chỗ cho tới khi màn thật vào (thanh phát nhỏ gọi onOpenNowPlaying để tới đây). */
    @Immutable
    data object NowPlaying : Destination
}

/** Một mục của ngăn xếp: `key` ổn định để Compose giữ trạng thái màn khi nó đổi chỗ (trên cùng -> bên dưới). */
@Immutable
data class Entry(val key: Int, val destination: Destination)

/**
 * Ngăn xếp màn thuần dữ liệu (không Compose) - dễ thử. Gốc (ba tab) không nằm trong ngăn xếp: rỗng = đang ở gốc.
 * Bất biến: mỗi thao tác trả ngăn xếp mới.
 */
@Immutable
class BackStack private constructor(val entries: List<Entry>, private val nextKey: Int) {
    constructor() : this(emptyList(), 0)

    val size: Int get() = entries.size
    val isEmpty: Boolean get() = entries.isEmpty()
    val top: Entry? get() = entries.lastOrNull()

    fun push(destination: Destination): BackStack = BackStack(entries + Entry(nextKey, destination), nextKey + 1)

    /** Bỏ màn trên cùng; ngăn xếp rỗng thì giữ nguyên (Back ở gốc là việc của Activity). */
    fun pop(): BackStack = if (entries.isEmpty()) this else BackStack(entries.dropLast(1), nextKey)

    override fun equals(other: Any?) = other is BackStack && other.entries == entries
    override fun hashCode() = entries.hashCode()
}

/**
 * Trạng thái điều hướng màn con + chuyển cảnh của chúng. [progress] là tiến trình của màn TRÊN CÙNG (1 = đã vào hẳn); chỉ giá trị này chạy theo khung,
 * và được đọc trong pha vẽ (graphicsLayer) - không ai đọc nó trong thân composable. Vào, Back và Back dự đoán cùng điều khiển nó (xem [ScreenGeometry]).
 */
@Stable
class NavState(private val scope: CoroutineScope) {
    var stack by mutableStateOf(BackStack())
        private set

    val progress = Animatable(1f)
    private var job: Job? = null

    val canPop: Boolean get() = !stack.isEmpty

    fun push(destination: Destination) {
        if (job?.isActive == true) return // đang chuyển cảnh: chạm đúp không đẩy hai màn
        job?.cancel()
        job = scope.launch {
            stack = stack.push(destination)
            progress.snapTo(0f)
            progress.animateTo(1f, Motion.PushIn)
        }
    }

    /** Back từ nút / phím: chạy ngược p về 0 rồi bỏ màn. */
    fun pop() {
        if (!canPop) return
        job?.cancel()
        job = scope.launch { finishPop() }
    }

    /** Back dự đoán: ngón tay kéo `back` (0..1) - màn đi theo ngón tay. Gọi trong coroutine của [PredictiveBackHandler]. */
    suspend fun dragBack(back: Float) {
        job?.cancel()
        progress.snapTo(ScreenGeometry.forBack(back))
    }

    /** Thả qua ngưỡng: chạy nốt phần còn lại về 0 rồi bỏ màn. */
    suspend fun commitBack() = finishPop()

    /** Thả trước ngưỡng / huỷ: màn quay lại hẳn. */
    suspend fun cancelBack() {
        progress.animateTo(1f, Motion.PushIn)
    }

    private suspend fun finishPop() {
        progress.animateTo(0f, Motion.popOut(progress.value))
        stack = stack.pop()
        progress.snapTo(1f)
    }
}
