package vn.abook.player.ui.data

import android.content.Intent

/**
 * Việc của trang sách với kho dữ liệu - tách khỏi màn để thử bằng nguồn giả (nguồn thật: [LibraryRepo], qua lõi [vn.abook.player.BookActions]).
 * Mọi hàm tự chạy ở luồng nền; hàm ghi làm mới Thư viện xong mới trả.
 */
interface BookSource {
    /** Trang sách của cuốn `id`; null khi cuốn không còn trên máy. */
    suspend fun detail(id: String): BookDetail?

    /** Chữ một chương cho "Tìm trong sách" (các câu theo thứ tự); null khi không đọc được. */
    suspend fun passages(id: String, chapter: ChapterLine): List<Passage>?

    suspend fun setFinished(id: String, finished: Boolean)

    suspend fun setChapterDone(id: String, chapterId: Int, done: Boolean)

    /** Xoá khỏi máy: null = đã nhận (native chờ hết cửa sổ Hoàn tác mới xoá đĩa), khác null = câu lỗi. */
    suspend fun delete(id: String): String?

    /** Đóng file sách và dựng bảng chia sẻ; null khi không đóng được (đã ghi nhật ký). */
    suspend fun share(id: String): Intent?

    companion object {
        /** Không có kho (ảnh chụp, xem trước): trang sách chỉ có phần đầu từ ô của Thư viện, mọi việc ghi không làm gì. */
        val None: BookSource = object : BookSource {
            override suspend fun detail(id: String): BookDetail? = null
            override suspend fun passages(id: String, chapter: ChapterLine): List<Passage>? = null
            override suspend fun setFinished(id: String, finished: Boolean) = Unit
            override suspend fun setChapterDone(id: String, chapterId: Int, done: Boolean) = Unit
            override suspend fun delete(id: String): String? = null
            override suspend fun share(id: String): Intent? = null
        }
    }
}
