package vn.abook.player.ui.nav

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.FiniteAnimationSpec
import androidx.compose.runtime.MonotonicFrameClock
import androidx.compose.runtime.withFrameNanos
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.Stable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull
import vn.abook.player.ui.data.ListenBook
import vn.abook.player.ui.export.ExportFormat
import vn.abook.player.ui.voice.VoicePage
import vn.abook.player.ui.data.SettingsGroup
import vn.abook.player.ui.motion.Motion
import vn.abook.player.ui.motion.ScreenGeometry
import vn.abook.player.ui.motion.RenderedFrameClock
import vn.abook.player.ui.studio.StudioSubKind
import vn.abook.player.ui.studio.StudioTab

/** Màn con xếp trên ba tab. Đang nghe không phải màn con: nó là cửa sổ nở ra từ thanh phát nhỏ ([vn.abook.player.ui.nowplaying.NowPlayingLayer]), có Back riêng. */
@Immutable
sealed interface Destination {
    data object AddBook : Destination
    data class ImportReview(val itemId: Long) : Destination
    data class ImportChapter(val itemId: Long, val index: Int) : Destination
    data class EditBook(val book: ListenBook) : Destination
    data class EditChapter(val book: ListenBook, val chapterId: Long) : Destination
    data class CropCover(val book: ListenBook, val uri: String) : Destination

    /** "Tìm ảnh bìa" của Sửa sách (đi từ bảng ảnh bìa, Back về lại Sửa sách). */
    data class CoverSearch(val book: ListenBook) : Destination
    @Immutable
    data class Book(val book: ListenBook) : Destination

    /** Xuất sách thành MP3 hay M4B (đi từ menu "Thêm" của trang sách, Back về lại trang sách). */
    @Immutable
    data class Export(val book: ListenBook, val format: ExportFormat? = null) : Destination

    /** Một nhóm Cài đặt (cấp hai, cũng là cấp cuối: Cài đặt -> nhóm -> mục). */
    @Immutable
    data class Settings(val group: SettingsGroup) : Destination

    /** Nhạc của tôi: đường hiện có giữ cho nhánh dev/musiclib chuyển sang tab Nhạc. Khoá trực tuyến đã gập tại chỗ. */
    @Immutable
    data class Voice(val page: VoicePage) : Destination

    /** Studio của máy tính `computer` ("" = máy tính chính): danh sách dự án mở từ thông báo; tab Studio nhúng danh sách trực tiếp. */
    @Immutable
    data class Studio(val computer: String) : Destination

    /** Trình tạo sách mới trên máy tính `computer`: đi từ danh sách dự án; tạo xong thì được thay bằng dự án vừa tạo. */
    @Immutable
    data class StudioNew(val computer: String) : Destination

    /** Một dự án Studio ở tab `tab`: từ danh sách dự án hay từ thông báo "cần duyệt / đã xong". */
    @Immutable
    data class StudioProject(val computer: String, val book: String, val tab: StudioTab = StudioTab.Chapters) : Destination

    /** Một màn con của dự án Studio (Duyệt trước khi thu, Kịch bản, Cách đọc tên): đi từ "Thêm" của dự án, Back về lại dự án. */
    @Immutable
    data class StudioSub(val computer: String, val book: String, val kind: StudioSubKind) : Destination

    /** Kho nhạc ở chế độ chọn cho đoạn `scene` của cuốn `book` ("Xem cả kho" cuối "Đổi bài"): chọn xong ghim bài rồi quay lại. */
    @Immutable
    data class MusicPick(val book: String, val scene: String) : Destination
}

/**
 * Màn có thanh nút đáy riêng (Lưu, Thêm, Xuất...): thanh phát nhỏ nhường đáy cho nó. Mọi màn con khác giữ thanh phát nhỏ ở đáy khi có sách đang nạp (DESIGN.md L3b).
 * Không có nhánh `else`: thêm một [Destination] thì trình biên dịch bắt phải quyết định ở đây.
 */
fun Destination.ownsBottomBar(): Boolean = when (this) {
    Destination.AddBook, is Destination.ImportReview, is Destination.ImportChapter,
    is Destination.EditBook, is Destination.EditChapter, is Destination.CropCover, is Destination.CoverSearch,
    is Destination.Export, is Destination.StudioNew -> true
    is Destination.Book, is Destination.Settings, is Destination.Voice,
    is Destination.Studio, is Destination.StudioProject, is Destination.StudioSub, is Destination.MusicPick -> false
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

    /** Chỉ giữ `count` màn dưới cùng. */
    fun keep(count: Int): BackStack = BackStack(entries.take(count), nextKey)

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

    /** Includes waiting for the incoming entry's actual layout. */
    val busy: Boolean get() = job?.isActive == true

    /** An entry may redirect while its initial layout is still being staged. */
    private var staging = false
    private var entering: Pair<Int, CompletableDeferred<Unit>>? = null

    /** A keyed layout acknowledgment; a stale entry cannot start another entry's animation. */
    fun entryReady(key: Int) {
        entering?.takeIf { it.first == key }?.second?.complete(Unit)
    }

    fun push(destination: Destination) {
        if (busy && !staging) return // đang trượt: chạm đúp không đẩy hai màn
        enter { it.push(destination) }
    }

    /** Thay màn trên cùng bằng `destination` (màn mới trượt vào, Back từ nó về màn bên dưới màn cũ): "Sách mới" xong thì mở dự án vừa tạo, không để màn tạo nằm sau lưng. */
    fun replaceTop(destination: Destination) {
        if (!canPop || (busy && !staging)) return
        enter { it.pop().push(destination) }
    }

    private fun enter(next: (BackStack) -> BackStack) {
        job?.cancel()
        job = scope.launch {
            val incoming = next(stack)
            progress.snapTo(0f)
            val ready = incoming.top!!.key to CompletableDeferred<Unit>()
            entering = ready
            staging = true
            try {
                stack = incoming
                // Bounded: an entry that never reports placement must not hold navigation.
                withTimeoutOrNull(ENTRY_READY_MAX_MS) { ready.second.await() }
                withFrameNanos { }
            } finally {
                if (entering === ready) { entering = null; staging = false }
            }
            animateTo(1f, Motion.PushIn)
        }
    }

    /** Back từ nút / phím: chạy ngược p về 0 rồi bỏ màn. */
    fun pop() {
        if (!canPop) return
        job?.cancel()
        job = scope.launch { finishPop() }
    }

    /** Về gốc (ba tab) một lần: màn trên cùng đi ra như Back, rồi cả ngăn xếp rỗng. */
    fun popToRoot() {
        if (!canPop) return
        job?.cancel()
        job = scope.launch {
            animateTo(0f, Motion.popOut(progress.value))
            stack = BackStack()
            progress.snapTo(1f)
        }
    }

    /**
     * Về màn trên cùng khớp `match` nếu nó đã có trong ngăn xếp (màn phía trên đi ra như Back, rồi bỏ hết chúng). Trả về false khi không có màn nào khớp;
     * chính nó đang ở đỉnh thì đứng yên. Nhờ vậy "mở trang sách" không bao giờ đẩy trùng một trang.
     */
    fun popTo(match: (Destination) -> Boolean): Boolean {
        val at = stack.entries.indexOfLast { match(it.destination) }
        if (at < 0) return false
        if (at == stack.size - 1) return true
        job?.cancel()
        job = scope.launch {
            animateTo(0f, Motion.popOut(progress.value))
            stack = stack.keep(at + 1)
            progress.snapTo(1f)
        }
        return true
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
        animateTo(1f, Motion.PushIn)
    }

    private suspend fun finishPop() {
        animateTo(0f, Motion.popOut(progress.value))
        stack = stack.pop()
        progress.snapTo(1f)
    }

    private suspend fun animateTo(target: Float, spec: FiniteAnimationSpec<Float>) {
        val clock = checkNotNull(currentCoroutineContext()[MonotonicFrameClock])
        withContext(RenderedFrameClock(clock)) { progress.animateTo(target, spec) }
    }

    private companion object {
        /** A cold cover decode on a slow phone stays well under this; past it the page slides without its cover. */
        const val ENTRY_READY_MAX_MS = 1_500L
    }
}
