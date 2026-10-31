package vn.abook.player.ui.studio

import android.content.Intent
import androidx.compose.runtime.Immutable
import vn.abook.player.StudioPaths
import vn.abook.player.ui.data.Choice

/** Năm tab của một dự án (DESIGN.md §7, web `MAIN_TABS`): `key` là giá trị `?tab=` của đường trang Studio. */
enum class StudioTab(override val key: String, override val label: String) : Choice {
    Chapters("chapters", "Chương"),
    Work("work", "Việc cần duyệt"),
    Review("review", "Cần nghe lại"),
    Cast("cast", "Nhân vật"),
    Music("music", "Nhạc nền");

    companion object {
        /** Tab theo `?tab=` của web; màn con ([StudioSubKind.of]), trang chưa có ở native (activity...) hay giá trị lạ về Chương. */
        fun of(key: String?): StudioTab = entries.firstOrNull { it.key == key } ?: Chapters
    }
}

/** Các màn con của một dự án (S3: duyệt, kịch bản, cách đọc tên; S4: xuất, nhật ký, bìa), mở từ "Thêm" hay thông báo: đi sau tab, Back về lại dự án. `key` là giá trị `?tab=` của web. */
enum class StudioSubKind(val key: String) {
    Precast("precast"), Script("script"), Readings("readings"), Export("export"), Activity("activity"), Cover("cover");

    companion object {
        fun of(key: String?): StudioSubKind? = entries.firstOrNull { it.key == key }
    }
}

/** Tạm dừng đang diễn ra mà tiến trình vẫn sống: máy tính chạy pin hay người bấm "Tạm dừng". */
enum class StudioPause { Battery, Listener }

/** Ước lượng còn bao lâu của bước đang làm (`phase`: analysis, synthesis hay speaker). */
@Immutable
data class StudioEta(val phase: String, val seconds: Double)

/** Lượt "Xác định người nói từng câu": chương xong / tổng. */
@Immutable
data class StudioSpeakerPass(val done: Int, val total: Int, val active: Boolean)

/** Cuốn xếp hàng mà cuốn đang giữ máy lại đang tạm dừng. */
@Immutable
data class StudioQueueWait(val title: String, val paused: StudioPause)

/** Một dự án như `GET /api/library` và `GET /api/books/<id>` mô tả (web `BookSummary`): chỉ phần màn native dùng. */
@Immutable
data class StudioBook(
    val id: String,
    val title: String,
    val phase: String,
    val statusLabel: String,
    val running: Boolean,
    val starting: Boolean,
    val stopping: Boolean,
    val paused: StudioPause?,
    val canPause: Boolean,
    val queuePosition: Int?,
    val queueWaitsOn: StudioQueueWait?,
    val analysisInterrupted: Boolean,
    val precastHeld: Boolean,
    val pendingChanges: Int,
    val seedPending: Boolean,
    val chaptersTotal: Int,
    val chaptersCompleted: Int,
    val chaptersRedo: Int,
    val segmentsTotal: Int,
    val segmentsAnalyzed: Int,
    val segmentsPending: Int?,
    val overall: Float,
    val analysis: Float,
    val synthesis: Float,
    val eta: StudioEta?,
    val speaker: StudioSpeakerPass?,
    val startError: String,
    val lastError: String,
    /** Vì sao không mở được (sổ làm việc hỏng, tạo dở...): rỗng khi mở được. */
    val broken: String,
    /** Phân vai đã khoá (lúc "Duyệt trước khi thu"): sửa của người nghe áp ở ranh giới chương đầu (web `castLocked`). */
    val castLocked: Boolean = false,
    /** Số câu đã có bản thu; null khi máy không nói. */
    val segmentsRecorded: Int? = null,
    /** Phiên bản ảnh bìa thật của sách (đổi khi đổi ảnh); null = chưa có, sách dùng bìa vẽ từ tên. */
    val cover: String? = null,
) {
    /** Máy đang làm sách này (kể cả lúc đang khởi động). */
    val working: Boolean get() = running || starting
}

/** Một chương của dự án (web `Chapter`). */
@Immutable
data class StudioChapter(
    val id: Int,
    val index: Int,
    val title: String,
    val status: String,
    val statusLabel: String,
    val redo: Boolean,
    val seconds: Double,
    val playable: Boolean,
)

/** Lời đáp của `GET /api/books/<id>`. */
@Immutable
data class StudioPage(val book: StudioBook, val chapters: List<StudioChapter>)

/**
 * Nơi cần mở trong Studio của một máy: danh sách (book = null) hay một dự án ở một tab. Đến từ thông báo, từ hàng "Studio" ở Thiết bị hay từ đường
 * trang cũ của web (`/#/studio/<mã>?tab=work`) - đường ấy chỉ được đọc ở đây, không bao giờ dựng lại.
 */
@Immutable
data class StudioRoute(val book: String? = null, val tab: StudioTab = StudioTab.Chapters, val sub: StudioSubKind? = null) {
    companion object {
        const val EXTRA_COMPUTER = "studio_computer"
        const val EXTRA_BOOK = "studio_book"
        const val EXTRA_TAB = "studio_tab"

        /** `/#/studio`, `/#/studio/<mã>`, `/#/studio/<mã>?tab=work`; mã lạ hay đường khác về danh sách. */
        fun parse(path: String?): StudioRoute {
            if (path == null || !path.startsWith("/#/studio/")) return StudioRoute()
            val rest = path.removePrefix("/#/studio/")
            val id = rest.substringBefore('?')
            if (!StudioPaths.valid(id)) return StudioRoute()
            val tab = rest.substringAfter('?', "").split('&').firstOrNull { it.startsWith("tab=") }?.removePrefix("tab=")
            return of(id, tab)
        }

        private fun of(book: String?, key: String?): StudioRoute = StudioRoute(book, StudioTab.of(key), StudioSubKind.of(key))

        /** Thông báo bấm vào: mã máy, mã sách và tab (hay màn con) đi bằng extras (mã thiết bị không bao giờ nằm trong Intent). */
        fun put(intent: Intent, computer: String, route: StudioRoute): Intent {
            intent.putExtra(EXTRA_COMPUTER, computer).putExtra(EXTRA_TAB, route.sub?.key ?: route.tab.key)
            route.book?.let { intent.putExtra(EXTRA_BOOK, it) }
            return intent
        }

        /** Yêu cầu mở Studio trong Intent, hay null khi Intent không mang. */
        fun request(intent: Intent?): StudioRequest? {
            if (intent == null || !intent.hasExtra(EXTRA_COMPUTER)) return null
            val book = intent.getStringExtra(EXTRA_BOOK)?.takeIf { StudioPaths.valid(it) }
            return StudioRequest(intent.getStringExtra(EXTRA_COMPUTER).orEmpty(), of(book, intent.getStringExtra(EXTRA_TAB)))
        }
    }
}

/** Mở Studio của máy `computer` ("" = máy tính chính) ở `route`. */
@Immutable
data class StudioRequest(val computer: String, val route: StudioRoute)
