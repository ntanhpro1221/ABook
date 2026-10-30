package vn.abook.player.ui.nav

import androidx.compose.animation.core.Animatable
import androidx.compose.runtime.withFrameNanos
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.Stable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch
import vn.abook.player.ui.data.ListenBook
import vn.abook.player.ui.devices.DevicesPage
import vn.abook.player.ui.export.ExportFormat
import vn.abook.player.ui.voice.VoicePage
import vn.abook.player.ui.data.SettingsGroup
import vn.abook.player.ui.motion.Motion
import vn.abook.player.ui.motion.ScreenGeometry
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

    /** Một màn của nhóm Thiết bị (Nối máy tính, Chia sẻ thư viện, Dung lượng): đi từ trang nhóm Thiết bị, Back về lại trang ấy. */
    @Immutable
    data class Devices(val page: DevicesPage) : Destination

    /** Một màn của nhóm Giọng đọc (Khoá giọng trực tuyến) hay Nghe (Nhạc của tôi): đi từ trang nhóm, Back về lại trang ấy. */
    @Immutable
    data class Voice(val page: VoicePage) : Destination

    /** Studio của máy tính `computer` ("" = máy tính chính): danh sách dự án. Đi từ hàng "Studio" ở Thiết bị, Back về lại trang ấy. */
    @Immutable
    data class Studio(val computer: String) : Destination

    /** Một dự án Studio ở tab `tab`: từ danh sách dự án hay từ thông báo "cần duyệt / đã xong". */
    @Immutable
    data class StudioProject(val computer: String, val book: String, val tab: StudioTab = StudioTab.Chapters) : Destination

    /** Một màn con của dự án Studio (Duyệt trước khi thu, Kịch bản, Cách đọc tên): đi từ "Thêm" của dự án, Back về lại dự án. */
    @Immutable
    data class StudioSub(val computer: String, val book: String, val kind: StudioSubKind) : Destination
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

    /** Đang chạy một chuyển cảnh (kể cả hai khung chờ dựng của [push]). */
    val busy: Boolean get() = job?.isActive == true

    /** Hai khung chờ dựng của [push]: màn mới còn nằm ngoài màn, chưa trượt - một màn nối tiếp (màn tự mở màn sau) vẫn được đẩy. */
    private var staging = false

    fun push(destination: Destination) {
        if (busy && !staging) return // đang trượt: chạm đúp không đẩy hai màn
        job?.cancel()
        job = scope.launch {
            stack = stack.push(destination)
            progress.snapTo(0f)
            // Màn mới được dựng + dàn trang + ghi ở khung đầu khi nó còn nằm ngoài màn (p = 0); hoạt ảnh chỉ bắt đầu sau đó. Nếu chạy ngay, khung nặng nhất
            // (dựng cả màn) là khung đầu của hoạt ảnh: đồng hồ hoạt ảnh nhảy qua nó và cả đường trượt giật một nhịp.
            staging = true
            try { repeat(BUILD_FRAMES) { withFrameNanos { } } } finally { staging = false }
            progress.animateTo(1f, Motion.PushIn)
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
            progress.animateTo(0f, Motion.popOut(progress.value))
            stack = BackStack()
            progress.snapTo(1f)
        }
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

    private companion object {
        /** Số khung để màn mới dựng xong trước khi trượt. */
        const val BUILD_FRAMES = 2
    }
}
