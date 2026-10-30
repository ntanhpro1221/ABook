package vn.abook.player.ui.studio

/**
 * Chữ của ba tab nội dung Studio (Việc cần duyệt, Cần nghe lại, Nhân vật) và bảng giọng, ở MỘT nơi. Chữ của chính các thẻ (tiêu đề, nút trả lời, lời đã ghi)
 * lấy từ máy tính hay từ [WorkLogic] / [ReviewLogic] / [VoiceLogic] để hai nền tảng nói cùng một câu; ở đây chỉ là chữ riêng của điện thoại. Nhãn nút 1-4 chữ.
 */
object WorkText {
    // ---- chung ----

    /** Máy từ chối vì câu đã đổi từ lúc bạn mở thẻ (409 hay 400): thẻ nạp lại, không tự gửi lại. */
    const val STALE = "Câu này đã đổi, bạn xem lại."
    const val UNDO = "Hoàn tác"
    const val CLOSE = "Đóng"
    const val SKIP = "Bỏ qua"
    const val MORE = "Chọn khác"
    const val PLAY = "Nghe"
    const val STOP = "Dừng"
    const val DONE = "Xong"
    const val LOADING = "Đang mở"
    const val PLAY_FAILED_OFFLINE = "Chưa tải được đoạn này - kiểm tra kết nối tới máy tính."
    const val PLAY_FAILED_MISSING = "Máy tính không còn đoạn này."

    // ---- Việc cần duyệt ----

    const val WORK_LOADING = "Đang mở danh sách việc"
    const val WORK_EMPTY_TITLE = "Đã duyệt hết"
    const val WORK_EMPTY = "Máy chắc chắn về mọi thứ đã làm tới giờ."
    const val WORK_EMPTY_LIVE = "Máy đang làm sách; việc mới sẽ hiện ở đây."

    fun left(count: Int): String = "Còn $count việc"

    fun affected(count: Int): String = "Ảnh hưởng $count câu"

    fun using(text: String): String = "Máy đang dùng: $text"

    fun waiting(count: Int): String = if (count == 1) "1 thay đổi đang chờ áp dụng" else "$count thay đổi đang chờ áp dụng"

    const val SCOPE_LEAD = "Đổi người nói cho"
    const val OTHER_PERSON = "Người khác"
    const val OTHER_SHEET_TITLE = "Chọn người nói"
    const val NEW_PERSON_HINT = "hay đặt tên một người mới"
    const val NEW_PERSON_FIELD = "Tên người nói"
    const val NEW_GENDER_LEAD = "Giới (bấm để lưu)"
    const val GENDER_MALE = "Nam"
    const val GENDER_FEMALE = "Nữ"
    const val GENDER_UNKNOWN = "Không rõ"
    const val NARRATOR_OTHER = "Người kể khác"
    const val NARRATOR_FIELD = "Tên người kể"
    const val NARRATOR_SET = "Đặt người kể"
    const val PICK_LINES = "Chọn câu"
    const val PICK_ALL = "Chọn hết"
    const val PICK_NONE = "Bỏ hết"

    fun scope(scope: WorkScope, labels: Pair<String, String>?, alternate: Int, all: Int): String = when (scope) {
        WorkScope.Alternate -> "${labels?.first ?: "Câu xen kẽ"} · $alternate"
        WorkScope.All -> "${labels?.second ?: "Cả chuỗi"} · $all"
    }

    fun scopeNote(labels: Pair<String, String>?): String =
        if (labels != null) "${labels.first} theo chương; ${labels.second} theo cả sách và các phần sau."
        else "Câu xen kẽ chỉ đổi câu đánh dấu; cả chuỗi đổi toàn bộ người nói."

    fun keepName(item: WorkItem): String = item.keepLabel ?: if (item.kind == WorkKind.Unnamed) "Đúng là vai phụ" else "Giữ ${item.current}"

    // thẻ cách đọc tên
    const val READING_OR = "hoặc đọc là"
    const val READING_SAVE = "Đọc thế này"
    const val READING_TRY = "Nghe thử"
    const val READING_TRYING = "Máy đang đọc thử"
    const val READING_HINT = "Gõ cách đọc, bấm Nghe thử để nghe trước khi lưu."

    fun readingKeep(current: String): String = "Đúng rồi, giữ “$current”"

    fun readingField(surface: String): String = "Cách đọc mới cho $surface"

    fun readingUse(suggestion: String): String = "Dùng “$suggestion”"

    // thẻ giọng
    const val VOICE_OTHER = "Chọn giọng khác"

    // thẻ bản thu lỗi
    const val LISTEN_LINE = "Những câu này nghe lại ở tab Cần nghe lại."
    const val LISTEN_OPEN = "Mở Cần nghe lại"

    // thẻ yêu cầu chưa được
    const val REFUSED_DROP = "Bỏ yêu cầu này"

    // thẻ chưa trả lời được trên điện thoại
    const val PLAIN_LINE = "Việc này bạn xem trên máy tính."

    // ---- Cần nghe lại ----

    const val REVIEW_LOADING = "Đang mở danh sách câu"
    const val REVIEW_EMPTY_TITLE = "Không còn câu nào cần xem"
    const val REVIEW_EMPTY = "Máy nghe lại những câu đã thu và chúng đều khớp với chữ."
    const val REVIEW_NOT_RECORDED_TITLE = "Chưa có câu nào để nghe lại"
    const val REVIEW_NOT_RECORDED = "Máy sẽ kiểm các câu sau khi thu âm."
    const val REVIEW_DONE_EMPTY = "Bạn chưa xem câu nào."
    const val OK = "Ổn"
    const val REDO = "Cần thu lại"
    const val PLAY_ALL_STOP = "Dừng nghe liền"
    const val PLAY_FINISHED = "Đã nghe hết các câu trong danh sách."
    const val MORE_ITEMS = "Xem thêm"
    const val HEARD = "Máy nghe ra"
    const val HEARD_NOTHING = "Máy không nghe ra chữ nào"
    const val NO_AUDIO = "Chưa có bản thu để nghe"
    const val MINOR_SHOW = "Hiện cả câu lệch nhẹ"
    const val MINOR_HIDE = "Chỉ câu lệch nhiều"
    const val TAKE_THEIRS = "Lấy của máy kia"
    const val KEEP_MINE = "Giữ của tôi"

    fun playAll(count: Int): String = "Nghe liền $count câu"

    fun reviewPending(count: Int): String = "Còn $count câu chưa xem"

    fun redoChapters(chapters: List<Int>): String =
        if (chapters.size == 1) "Chương ${chapters[0]} sẽ được thu lại khi bạn áp dụng thay đổi."
        else "${chapters.size} chương sẽ được thu lại khi bạn áp dụng thay đổi."

    fun matched(percent: String): String = ReviewLogic.matchShort(percent)

    fun elsewhere(theirs: String): String {
        val was = WorkLogic.verdictWord(theirs.ifEmpty { null })
        return if (was.isEmpty()) "Máy hay cửa sổ khác vừa bỏ phán quyết của câu này." else "Máy hay cửa sổ khác vừa chọn $was cho câu này."
    }

    fun kind(kind: ReviewKind): String = when (kind) {
        ReviewKind.Failed -> "Bản thu hỏng"
        ReviewKind.Unverified -> "Chưa kiểm được"
        ReviewKind.NameLow -> "Tên đọc lệch nhiều"
        ReviewKind.TextLow -> "Chữ lệch nhiều"
        ReviewKind.Name -> "Tên đọc lệch nhẹ"
        ReviewKind.Text -> "Chữ lệch nhẹ"
    }

    // ---- Nhân vật ----

    const val CAST_LOADING = "Đang mở dàn nhân vật"
    const val CAST_EMPTY = "Chưa có dàn nhân vật"
    const val CAST_EMPTY_HINT = "Nhân vật hiện ra khi máy đọc xong phần phân tích."
    const val CAST_NARRATOR = "Người kể"
    const val CAST_MAIN = "Nhân vật chính"
    const val CAST_EXTRAS = "Vai phụ"
    const val CAST_CARRIED = "Từ phần trước"
    const val CAST_NO_VOICE = "Chưa có giọng"
    const val CAST_PLAY = "Nghe một câu"

    fun castLines(count: Int): String = "$count câu"

    fun pendingVoice(label: String): String = "Đã chọn giọng $label - chờ áp dụng"

    fun mergedInto(name: String): String = "Chờ gộp vào $name"

    fun renamed(original: String): String = "Tên gốc: $original"

    // ---- Bảng giọng ----

    fun voiceTitle(name: String): String = "Giọng của $name"

    const val VOICE_LOADING = "Đang mở danh sách giọng"
    const val VOICE_PENDING_TITLE = "Bạn đã chọn một giọng chưa vào sách"
    const val VOICE_KEEP_CURRENT = "Giữ giọng đang dùng"
    const val VOICE_CHOOSE = "Chọn"
    const val VOICE_IN_USE = "Đang dùng"
    const val VOICE_CHOSEN = "Đã chọn"
    const val VOICE_TRY = "Nghe thử bằng câu sách"
    const val VOICE_TRYING = "Máy đang đọc thử"
    const val VOICE_CROSS_YES = "Đổi giọng và giới"
    const val VOICE_CROSS_NO = "Thôi"
    const val VOICE_NO_VOICES = "Giới này chưa có giọng nào"
    const val VOICE_NOT_INSTALLED = "Giọng này cần cài thêm trên máy tính"

    fun voicePending(name: String): String = if (name.isEmpty()) "Giọng bạn chọn đang chờ vào sách." else "Giọng $name đang chờ vào sách."

    fun voiceCross(person: String, gender: String, voice: String): String =
        "${voice} là giọng ${if (gender == "female") "nữ" else "nam"}. Chọn nó thì $person cũng thành nhân vật ${if (gender == "female") "nữ" else "nam"}."
}
