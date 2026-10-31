package vn.abook.player.ui.data

/**
 * Chữ của "Lưu thay đổi" / "Lưu thành" (web: listen/BookScreen.tsx `useSaveBook`, listen/EditBook.tsx `SaveAsDialog`). Hàm thuần - thử trên JVM (SaveTextTest).
 */
object SaveText {
    const val SAVED = "Đã lưu file sách"
    const val FAILED = "Chưa lưu được file sách"
    const val NO_CHANGES = "Chưa có thay đổi nào - file giống bản gốc."

    /** Lời báo sau khi lưu xong; không có thay đổi nào vẫn lưu được, nhưng nói rõ file giống hệt bản gốc. */
    fun done(edits: Int): String = if (edits > 0) SAVED else "$SAVED. $NO_CHANGES"

    /** Lưu hỏng: tên việc, rồi lý do của lõi nếu có. */
    fun failed(message: String?): String = if (message.isNullOrBlank()) FAILED else "$FAILED. ${message.trim()}"

    /** Dòng giải thích dưới lựa chọn loại file của "Lưu thành". */
    fun kindNote(project: Boolean, workshop: String?, wishes: Int): String = when {
        project && workshop == "present" -> "Cả dự án kèm thay đổi của bạn; mở bằng Studio để áp."
        project -> "Chỉ có phần nghe và thay đổi của bạn. Studio dựng lại được dự án từ file này."
        else -> "Sách nghe mở được bằng ABook trên máy tính và điện thoại, mang theo tên, bìa, tên nhân vật, tên chương, nhạc bạn đã sửa" +
            (if (wishes > 0) ", cùng $wishes việc đang chờ máy làm sách (chưa làm gì trong giọng đọc)" else "") + "."
    }
}
