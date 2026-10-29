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

    /** Dàn nhân vật như người nghe thấy (tên đã đổi, việc đang chờ); null khi không đọc được. Sách chưa phân vai: dàn rỗng. */
    suspend fun cast(id: String): CastView?

    /** Đường tới file nói mẫu của một người (`samples/<n>.wav`); null khi file chưa có trên máy (cuốn nghe thẳng chưa tải). */
    suspend fun samplePath(id: String, sampleId: Int): String?

    // ---- hồ sơ nghe: null = xong, khác null = câu lỗi của lõi. Cuốn đang ở trình phát thì trình phát theo sang hồ sơ mới. ----

    suspend fun createRecord(id: String, name: String): String?

    suspend fun activateRecord(id: String, record: String): String?

    suspend fun renameRecord(id: String, record: String, name: String): String?

    /** Chuyển hồ sơ sang cuốn khác (chỗ nghe, lịch sử đi theo). */
    suspend fun moveRecord(id: String, record: String, toBook: String): String?

    suspend fun deleteRecord(id: String, record: String): String?

    // ---- sửa một người ở tab Nhân vật (đường của lõi như Studio: LocalStudio) ----

    /** "Đổi tên": tên trên màn hình, không đổi giọng hay audio; `name` rỗng = về tên gốc. */
    suspend fun renamePerson(id: String, character: String, name: String): Edit<Renamed>

    /** "Đổi giới tính": một thay đổi chờ Studio (cuốn mở từ file). `Edit.value` = mốc để hoàn tác. */
    suspend fun setGender(id: String, character: String, gender: Gender): Edit<Double>

    /** Rút lần "Đổi giới tính" có mốc `requestedAt`. */
    suspend fun withdrawGender(id: String, character: String, requestedAt: Double): String?

    /** "Gộp vào…": mọi câu của `from` thành của `into`. `Edit.value` = số câu. */
    suspend fun mergePeople(id: String, from: String, into: String): Edit<Int>

    companion object {
        /** Không có kho (ảnh chụp, xem trước): trang sách chỉ có phần đầu từ ô của Thư viện, mọi việc ghi không làm gì. */
        val None: BookSource = object : BookSource {
            override suspend fun detail(id: String): BookDetail? = null
            override suspend fun passages(id: String, chapter: ChapterLine): List<Passage>? = null
            override suspend fun setFinished(id: String, finished: Boolean) = Unit
            override suspend fun setChapterDone(id: String, chapterId: Int, done: Boolean) = Unit
            override suspend fun delete(id: String): String? = null
            override suspend fun share(id: String): Intent? = null
            override suspend fun cast(id: String): CastView? = null
            override suspend fun samplePath(id: String, sampleId: Int): String? = null
            override suspend fun createRecord(id: String, name: String): String? = null
            override suspend fun activateRecord(id: String, record: String): String? = null
            override suspend fun renameRecord(id: String, record: String, name: String): String? = null
            override suspend fun moveRecord(id: String, record: String, toBook: String): String? = null
            override suspend fun deleteRecord(id: String, record: String): String? = null
            override suspend fun renamePerson(id: String, character: String, name: String): Edit<Renamed> = Edit(null, null)
            override suspend fun setGender(id: String, character: String, gender: Gender): Edit<Double> = Edit(null, null)
            override suspend fun withdrawGender(id: String, character: String, requestedAt: Double): String? = null
            override suspend fun mergePeople(id: String, from: String, into: String): Edit<Int> = Edit(null, null)
        }
    }
}

/** Kết quả một lần sửa: `value` khi xong, `problem` (câu của lõi cho người nghe) khi không. */
class Edit<out T>(val value: T?, val problem: String?)

/** Lời đáp của "Đổi tên": tên đang hiện, và có khác tên gốc không. */
class Renamed(val name: String, val renamed: Boolean)
