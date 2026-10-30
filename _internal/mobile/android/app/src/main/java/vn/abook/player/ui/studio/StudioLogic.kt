package vn.abook.player.ui.studio

/** Màu của một trạng thái (web `Tone`): màn dịch sang màu của bảng màu. */
enum class StudioTone { Accent, Success, Danger, Warning, Muted }

/** Trạng thái một dự án như người dùng thấy: nhãn, màu, và có đang chạy thật (không tạm dừng, không đang dừng) không. */
data class StudioStatus(val label: String, val tone: StudioTone, val live: Boolean)

/** Dấu nhỏ trên một hàng chương (web `chapterMark`). */
data class StudioMark(val label: String, val tone: StudioTone)

/** MỘT nút chính của đầu trang dự án, chọn theo trạng thái (web `PrimaryKind`; DESIGN.md mục 7). */
enum class PrimaryKind { Starting, Stopping, Unpause, Pause, Start, Record, Resume, Continue, Apply, Dequeue, Listen }

/** Nhóm trên danh sách dự án: sắp theo điều cần làm ngay (NATIVE_REMOTE_STUDIO.md §6.1). */
enum class StudioGroup { Working, Review, Rest }

/**
 * Logic thuần của Studio, port từ `ui/src/studio` (ProjectScreen.tsx `primaryKind`, data.ts `projectStatus` / `phaseTone` / `queueLabel`, stopText.ts
 * `asksBeforeResume`): cùng điều kiện, nên nút nào hiện ở web thì hiện ở đây. Chữ nằm ở [StudioText].
 */
object StudioLogic {
    /** Các màn con hiện trong "Thêm": duyệt trước khi thu khi phân vai đã khoá và sách chưa xong; kịch bản và cách đọc tên khi đã phân tích được câu nào. */
    fun subPages(book: StudioBook): List<StudioSubKind> = buildList {
        if (PrecastLogic.canReview(book)) add(StudioSubKind.Precast)
        if (book.segmentsAnalyzed > 0) {
            add(StudioSubKind.Script)
            add(StudioSubKind.Readings)
        }
    }

    /** "Tiếp tục" phải hỏi trước: pha phân tích đã bị ngắt - làm tiếp ra MỘT CUỐN KHÁC (AGENTS.md). Sau pha phân tích thì không hỏi. */
    fun asksBeforeResume(book: StudioBook): Boolean = book.phase != "done" && book.analysisInterrupted

    /**
     * Nút chính, hay null khi lúc ấy không có việc gì để bấm. Khác web ở hai chỗ: xếp hàng thì nút chính là "Bỏ xếp hàng" (web để nó trong menu), và
     * phân tích bị ngắt thì [PrimaryKind.Resume] (web: "Phân tích lại" - màn tạo sách chưa có ở điện thoại - nên chỉ còn lối "Vẫn tiếp tục" có hỏi).
     */
    fun primaryKind(book: StudioBook): PrimaryKind? {
        val listen = if (book.chaptersCompleted > 0) PrimaryKind.Listen else null
        val redoWaiting = if (book.phase == "done") book.chaptersRedo else 0
        if (book.queuePosition != null) return PrimaryKind.Dequeue
        if (book.starting) return PrimaryKind.Starting
        if (book.running) {
            if (book.stopping) return PrimaryKind.Stopping
            if (book.paused != null) return PrimaryKind.Unpause
            return if (book.canPause) PrimaryKind.Pause else listen
        }
        if (book.phase == "idle") return PrimaryKind.Start
        // Sách đang chờ duyệt mà tiến trình đã chết (máy chủ khởi động lại): vẫn là "Thu âm".
        if (book.precastHeld && book.phase != "done") return PrimaryKind.Record
        if (asksBeforeResume(book)) return PrimaryKind.Resume
        if (book.phase != "done") return PrimaryKind.Continue
        // Sách đã xong không tự chạy lại: sửa của người nghe chờ ở đây.
        if (book.pendingChanges > 0) return PrimaryKind.Apply
        // Chương chờ thu lại mà không còn yêu cầu nào để "áp".
        if (redoWaiting > 0) return PrimaryKind.Continue
        return listen
    }

    fun tone(phase: String, running: Boolean): StudioTone = when {
        phase == "done" -> StudioTone.Success
        phase == "error" -> StudioTone.Danger
        running -> StudioTone.Accent
        // Làm dở mà không chạy: cần bạn để ý (bấm Tiếp tục) - không phải trạng thái trung tính.
        phase in setOf("analysis", "casting", "synthesis", "stopped") -> StudioTone.Warning
        else -> StudioTone.Muted
    }

    /** Nhãn + màu + "đang chạy" của một dự án: MỘT nơi cho đầu trang dự án và danh sách (cùng trạng thái = cùng chữ, cùng màu). */
    fun status(book: StudioBook): StudioStatus {
        val working = book.working
        val label = when {
            book.broken.isNotEmpty() -> book.broken
            book.queuePosition != null -> StudioText.queue(book.queuePosition)
            book.starting -> "Đang khởi động"
            book.precastHeld -> "Chờ bạn duyệt"
            else -> book.statusLabel
        }
        val tone = if (book.queuePosition != null || book.paused != null || book.stopping) StudioTone.Warning else tone(book.phase, working)
        return StudioStatus(label, if (book.broken.isNotEmpty()) StudioTone.Danger else tone, working && book.paused == null && !book.stopping)
    }

    /** Chỉ chương LỆCH khỏi mặc định mới có dấu (30 viên "Đã xong" xếp cột là nhiễu che mất chương thật sự cần để ý). */
    fun chapterMark(chapter: StudioChapter): StudioMark? {
        if (chapter.statusLabel == "Mất file audio") return StudioMark(chapter.statusLabel, StudioTone.Warning)
        if (chapter.status == "completed" && !chapter.redo) return null
        if (chapter.status in setOf("pending", "analyzed", "synthesizing", "verifying")) return null
        val tone = when (chapter.status) {
            "failed" -> StudioTone.Danger
            "warning" -> StudioTone.Warning
            else -> StudioTone.Muted
        }
        return StudioMark(chapter.statusLabel, tone)
    }

    /** Nhóm của một dự án trên danh sách. */
    fun group(book: StudioBook): StudioGroup = when {
        book.precastHeld || (book.phase == "done" && book.pendingChanges > 0 && !book.working) -> StudioGroup.Review
        book.working || book.queuePosition != null -> StudioGroup.Working
        else -> StudioGroup.Rest
    }

    /** Dự án theo nhóm, giữ thứ tự máy tính trả trong từng nhóm; nhóm trống bỏ. */
    fun groups(books: List<StudioBook>): List<Pair<StudioGroup, List<StudioBook>>> =
        StudioGroup.entries.mapNotNull { group -> books.filter { group(it) == group }.takeIf { it.isNotEmpty() }?.let { group to it } }

    /** Có sách nào đang chạy / xếp hàng: nhịp hỏi danh sách nhanh. */
    fun anyWorking(books: List<StudioBook>): Boolean = books.any { it.working }

    /** Nhịp hỏi một dự án: cơ sở theo trạng thái (chạy 3 giây, không thì 15 giây) - xem [vn.abook.player.StudioPolling]. */
    fun bookInterval(page: StudioPage?): Long = if (page?.book?.working == true) vn.abook.player.StudioPolling.BOOK_LIVE_MS else vn.abook.player.StudioPolling.IDLE_MS

    fun listInterval(books: List<StudioBook>?): Long = if (books != null && anyWorking(books)) vn.abook.player.StudioPolling.LIST_LIVE_MS else vn.abook.player.StudioPolling.IDLE_MS
}
