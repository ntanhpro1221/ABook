package vn.abook.player

/**
 * Đọc nhiều file văn bản của gói trong một lượt qua cầu (EbookLibrary.readTexts - ô "Tìm trong sách" của điện thoại, cùng thế với `search-texts`
 * của máy tính): chữ quá nhiều thì dừng, trả phần đầu - bên hỏi xin lại phần còn lại ở lượt sau.
 */
object TextBatch {
    /** Tổng số ký tự tối đa của một lượt (chương chữ dày vài chục nghìn ký tự: 64 chương ~ vài MB qua cầu là quá nặng). */
    const val BUDGET_CHARS = 1_500_000

    /** Kết quả theo thứ tự `paths` (null: file không có), dừng sau file làm tổng vượt [budget]; luôn trả ít nhất một file nếu có. */
    fun read(paths: List<String>, budget: Int = BUDGET_CHARS, read: (String) -> String?): List<String?> {
        val out = ArrayList<String?>()
        var chars = 0L
        for (path in paths) {
            val text = read(path)
            out.add(text)
            chars += text?.length ?: 0
            if (chars > budget) break
        }
        return out
    }
}
