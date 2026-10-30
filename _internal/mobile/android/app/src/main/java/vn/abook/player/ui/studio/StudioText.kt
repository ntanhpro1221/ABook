package vn.abook.player.ui.studio

import vn.abook.player.Pin
import vn.abook.player.StudioError
import vn.abook.player.StudioLink
import vn.abook.player.ui.data.Fmt

/**
 * Mọi chữ tiếng Việt của Studio từ xa ở MỘT nơi (NATIVE_REMOTE_STUDIO.md §3.3, §8): lời lỗi giữ y chữ của web (`polling.ts failureText`,
 * `stopText.ts`, `format.ts`) để hai nền tảng nói cùng một câu. Nhãn nút 1-4 chữ; nói với người dùng là "bạn".
 */
object StudioText {
    const val TITLE = "Studio"

    // ---- lỗi và quyền ----

    const val OFFLINE = "Mất kết nối tới ABook."
    const val GONE = "Sách có thể đã bị chuyển hoặc xoá."
    const val UNPAIRED = "Máy tính đã bỏ ghép điện thoại này. Bạn ghép lại ở Cài đặt, mục Thiết bị."
    const val TOO_BIG = "Gói gửi lên quá lớn."
    const val RETRY = "Thử lại"

    /** Lời cho người nghe của một lỗi Studio, theo loại: một nơi duy nhất. */
    fun failure(error: StudioError): String = when (error) {
        is StudioError.Offline -> OFFLINE
        is StudioError.Gone -> GONE
        is StudioError.Unauthorized -> UNPAIRED
        is StudioError.PinChanged -> Pin.CHANGED
        is StudioError.TooBig -> TOO_BIG
        is StudioError.ListenOnly -> PERMISSION_TITLE
        is StudioError.Busy -> error.message.orEmpty()
        is StudioError.Server -> error.message.orEmpty().ifBlank { GONE }
    }

    const val PERMISSION_TITLE = "Máy tính chưa cho bạn sửa"

    /** `name`: tên máy như bạn thấy ở Thiết bị. */
    fun permissionLine(name: String): String = "Bật “Cho phép điều khiển sản xuất” trên ${machine(name)} rồi quay lại."

    /** "máy NGDtuanh-Lecoo": giữa câu nên không viết hoa. */
    fun machine(name: String): String = StudioLink.called(name).replaceFirstChar { it.lowercase() }

    fun silent(name: String): String = StudioLink.silentLine(name)

    const val MISMATCH = "Máy tính cần cập nhật ABook ở cùng phiên bản với điện thoại."

    // ---- danh sách dự án ----

    const val NO_PROJECTS = "Chưa có dự án nào"
    const val NO_PROJECTS_HINT = "Dự án tạo trên máy tính sẽ hiện ở đây."
    const val LOADING = "Đang mở Studio"

    fun group(group: StudioGroup): String = when (group) {
        StudioGroup.Working -> "Đang làm"
        StudioGroup.Review -> "Cần bạn duyệt"
        StudioGroup.Rest -> "Còn lại"
    }

    /** Chỗ trong hàng chờ nói bằng "còn mấy việc trước" ("thứ 6" đọc thành "thứ Sáu"); `position` đếm từ 1. */
    fun queue(position: Int): String = if (position <= 1) "Sắp tới lượt" else "Còn ${position - 1} việc trước"

    // ---- dự án ----

    const val GONE_TITLE = "Dự án này không còn"
    const val BACK_TO_STUDIO = "Về Studio"
    const val MORE = "Thêm"
    const val NO_CHAPTERS = "Chưa có chương nào"

    fun label(kind: PrimaryKind, book: StudioBook): String = when (kind) {
        PrimaryKind.Starting -> "Đang khởi động"
        PrimaryKind.Stopping -> "Đang dừng"
        PrimaryKind.Unpause -> if (book.precastHeld) "Thu âm" else "Tiếp tục"
        PrimaryKind.Pause -> "Tạm dừng"
        PrimaryKind.Start -> "Bắt đầu"
        PrimaryKind.Record -> "Thu âm"
        PrimaryKind.Resume, PrimaryKind.Continue -> "Tiếp tục"
        PrimaryKind.Apply -> "Áp dụng ${book.pendingChanges} thay đổi"
        PrimaryKind.Dequeue -> "Bỏ xếp hàng"
        PrimaryKind.Listen -> "Nghe trong Thư viện"
    }

    /** Hai nút chính này chỉ báo trạng thái (đang khởi động / đang dừng), chưa bấm được. */
    fun inert(kind: PrimaryKind) = kind == PrimaryKind.Starting || kind == PrimaryKind.Stopping

    /** Dòng dưới nút chính (web `Actions`): vì sao đứng, hay việc đang chờ; "" khi không có gì để nói. */
    fun actionNote(book: StudioBook, kind: PrimaryKind?): String {
        val redoWaiting = if (book.phase == "done") book.chaptersRedo else 0
        return when {
            book.queuePosition != null ->
                "Chờ lượt ${book.queuePosition}, tự chạy khi cuốn trước xong${if (book.seedPending) ", giữ giọng và cách đọc tên" else ""}." +
                    (book.queueWaitsOn?.let { " " + queueWait(it) } ?: "")
            book.running && book.stopping -> "Dừng ở checkpoint kế, giữ phần đã xong; có thể mất vài phút."
            kind == PrimaryKind.Resume -> {
                val pending = book.segmentsPending ?: (book.segmentsTotal - book.segmentsAnalyzed)
                "Phân tích đã dừng giữa chừng" + (if (book.segmentsTotal > 0) " (còn $pending/${book.segmentsTotal} câu)" else "") +
                    "; tiếp tục thì $ANALYSIS_CUT_COST."
            }
            redoWaiting > 0 && kind == PrimaryKind.Continue ->
                (if (redoWaiting == 1) "1 chương đang chờ thu lại" else "$redoWaiting chương đang chờ thu lại") +
                    " theo sửa của bạn. Bản cũ vẫn nghe được cho tới khi thu xong."
            book.running && book.paused == StudioPause.Battery -> "Studio tạm dừng; cắm sạc để tiếp tục. Bấm “Tiếp tục” để làm ngay trên pin (chậm và hao pin hơn)."
            else -> ""
        }
    }

    /** Cuốn xếp hàng đứng sau một cuốn đang tạm dừng: hàng không tự đi tiếp (stopText.ts `queueWaitNotice`). */
    fun queueWait(waits: StudioQueueWait): String =
        if (waits.paused == StudioPause.Battery) {
            "“${waits.title}” đang tạm dừng vì máy chạy pin nên cuốn này chưa tới lượt - cắm sạc là cuốn kia tự làm tiếp, hay bấm “Tiếp tục” ở cuốn kia để làm tiếp ngay trên pin."
        } else {
            "“${waits.title}” đang tạm dừng nên cuốn này chưa tới lượt - bấm “Tiếp tục” ở cuốn kia để hàng chạy tiếp."
        }

    // ---- xác nhận ----

    /** Hệ quả, đứng sau "… thì" / "… sẽ" (stopText.ts `ANALYSIS_CUT_COST`). */
    const val ANALYSIS_CUT_COST = "có thể ra một cuốn khác: người nói ở đoạn sau chỗ dừng có thể đổi, kéo theo nhân vật và giọng đọc"
    const val ANALYSIS_STOP_FACT = "Phần đã phân tích được giữ nguyên, nhưng làm tiếp từ chỗ dừng"

    fun stopTitle(book: StudioBook) = if (book.phase == "analysis") "Dừng phân tích?" else "Dừng thu âm?"

    /** Các dòng của hộp Dừng: lúc phân tích nói thẳng giá phải trả; không thì nói việc đã xong được giữ. */
    fun stopLines(book: StudioBook): List<String> {
        if (book.phase != "analysis") {
            return listOf(
                if (book.paused != null) "Tạm dừng vẫn giữ bộ nhớ card đồ hoạ. Dừng hẳn thì nhả ra; việc đã xong giữ nguyên."
                else "Mọi chương và câu đã xong được giữ nguyên - làm tiếp lúc nào cũng được, từ đúng chỗ dừng.",
            )
        }
        val eta = etaOf(book)
        return listOf("$ANALYSIS_STOP_FACT - $ANALYSIS_CUT_COST.", "Nên để chạy hết bước này${if (eta != null) " ($eta)" else ""}. ${stopAdvice(book)}".trim())
    }

    /** Câu cuối hộp Dừng lúc phân tích: đang tạm dừng thì nói sách đang yên ở đâu, không mời "bấm Tạm dừng" - không có nút ấy. */
    fun stopAdvice(book: StudioBook): String = when {
        book.paused != null -> "Sách đang tạm dừng - đứng yên đúng chỗ, phần đã phân tích không mất. Cứ để tạm dừng tới khi muốn làm tiếp."
        book.canPause -> "Cần nghỉ thì bấm Tạm dừng: sách đứng yên rồi làm tiếp đúng chỗ, phần đã phân tích không mất."
        else -> ""
    }

    fun stopKeep(book: StudioBook) = if (book.paused != null) "Để nguyên" else "Để chạy tiếp"
    fun stopConfirm(book: StudioBook) = if (book.phase == "analysis") "Vẫn dừng" else "Dừng"

    fun resumeTitle() = "Tiếp tục phân tích?"
    fun resumeLines(book: StudioBook): List<String> = listOf(
        "Phân tích của “${book.title}” đã dừng giữa chừng. Làm tiếp từ chỗ ấy $ANALYSIS_CUT_COST - khác với khi phân tích liền một mạch.",
        "Muốn chắc như chạy liền mạch, hãy làm lại phân tích từ đầu trên máy tính.",
    )

    fun applyTitle(book: StudioBook) = "Áp dụng ${book.pendingChanges} thay đổi?"
    const val APPLY_LINE = "Máy chỉ thu lại những câu bị ảnh hưởng, rồi dựng lại các chương có câu ấy - không làm lại cả cuốn."

    // ---- chữ có số đổi theo thời gian (đi qua ClockLabel; xem TickingValuePolicyTest) ----

    private fun clamp(fraction: Float): Float = if (fraction.isFinite()) fraction.coerceIn(0f, 1f) else if (fraction == Float.POSITIVE_INFINITY) 1f else 0f

    /** Phần trăm của thanh tiến độ, làm tròn XUỐNG: chưa xong thì không bao giờ 100% (format.ts `formatPercent`). */
    fun percent(fraction: Float): String {
        val value = clamp(fraction) * 100f
        if (value > 0f && value < 1f) return "<1%"
        if (value < 100f && value > 99f) return "99%"
        return "${value.toInt()}%"
    }

    /** Từ mức này của bước đang làm thì "còn dưới 2 phút" mới là "sắp xong". */
    private const val NEAR_DONE = 0.85f

    /** format.ts `formatEta`: còn ít giây mà bước chưa tới mức gần xong thì chỉ nói còn dưới 2 phút. */
    fun eta(seconds: Double, fraction: Float? = null): String =
        if (seconds < 90) { if (fraction == null || fraction >= NEAR_DONE) "sắp xong" else "còn dưới 2 phút" } else "còn khoảng ${Fmt.length(seconds)}"

    /**
     * Thời gian còn lại của bước máy đang làm, hay null khi chưa có tốc độ để ước (format.ts `etaOf`). Nói rõ là của bước nào: cạnh "N% tổng", "sắp xong"
     * trần đọc thành cả cuốn sắp xong trong khi còn các bước sau.
     */
    fun etaOf(book: StudioBook): String? {
        val estimate = book.eta ?: return null
        if (estimate.phase == "speaker") {
            val pass = book.speaker
            return "pha xác định người nói " + eta(estimate.seconds, pass?.takeIf { it.total > 0 }?.let { it.done.toFloat() / it.total })
        }
        val synthesis = estimate.phase == "synthesis"
        return (if (synthesis) "pha thu âm " else "pha phân tích ") + eta(estimate.seconds, if (synthesis) book.synthesis else book.analysis)
    }

    /** Dòng nói còn bao lâu của cả lượt làm sách (hay vì sao đang đứng); "" khi không có gì để nói (web `progressNote`). */
    fun progressNote(book: StudioBook): String {
        val live = book.working
        return when {
            book.stopping -> "đang dừng"
            book.paused != null -> if (book.precastHeld) "chờ bạn duyệt rồi bấm Thu âm" else ""
            else -> etaOf(book) ?: if (live) "đang ước tính thời gian" else ""
        }
    }

    /** "chương 12/48" của một dự án đang làm. */
    fun chapterLine(book: StudioBook): String =
        if (book.chaptersTotal > 0) "${book.chaptersCompleted}/${book.chaptersTotal} chương" else ""

    /** Dòng trạng thái ngắn của thẻ dự án: nhãn, rồi tiến độ chương khi đang làm. */
    fun statusLine(book: StudioBook): String {
        val status = StudioLogic.status(book)
        val line = chapterLine(book)
        return if (line.isNotEmpty() && book.phase != "idle") "${status.label} · $line" else status.label
    }

    /** Thời lượng một chương ("12 phút"). */
    fun length(seconds: Double): String = if (seconds > 0) Fmt.length(seconds) else ""
}
