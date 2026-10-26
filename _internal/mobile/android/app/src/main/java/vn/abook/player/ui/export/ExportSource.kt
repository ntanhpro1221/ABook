package vn.abook.player.ui.export

import androidx.compose.runtime.Stable
import kotlinx.coroutines.flow.Flow
import vn.abook.player.ui.data.ListenBook

/** Lỗi đã dịch cho người nghe (sách chưa có chương nghe được, không mở được thư mục...): `message` là câu nói được. */
class ExportFailure(message: String) : Exception(message)

/**
 * Việc của màn Xuất với các lõi ([vn.abook.player.ExportStart], Mp3Exports, M4bExports, ListenExports, ExportHistory, BookMusic) - tách khỏi màn để thử bằng nguồn giả.
 * Nguồn thật: [ExportRepo]. Hàm suspend tự chạy ở luồng nền; lỗi ném [ExportFailure] (hay lỗi lõi với câu đã sẵn cho người nghe).
 */
interface ExportSource {
    /** Ô "Kèm nhạc nền" của cuốn. */
    suspend fun music(bookId: String): ExportMusic

    /** Các bản đã xuất của cuốn, kèm chương đã đổi từ lúc ấy. */
    suspend fun history(bookId: String): List<PastExport>

    /** Tên thư mục MP3 đã nhớ từ lần trước, null khi chưa chọn (hay quyền đã mất). */
    suspend fun folder(): String?

    /** Giọng đang chọn cho cuốn chỉ có chữ; null khi máy chưa có giọng nào. */
    suspend fun voice(bookId: String): ExportVoice?

    /** Ước của lượt xuất sách nói; `music` null = theo mặc định của cuốn. */
    suspend fun plan(bookId: String, voice: String, music: Boolean?): AudiobookPlan

    /** Máy cho ABook chạy nền chưa; null khi không đọc được. */
    suspend fun background(): BackgroundView?

    /** Giữ quyền ghi thư mục MP3 người dùng vừa chọn ở bộ chọn của hệ thống rồi trả tên thư mục. */
    suspend fun keepFolder(tree: String): String

    /** Sách có gì để xuất không, và tên để hệ thống hỏi tên file: từ chối ngay, TRƯỚC khi hỏi chỗ lưu. */
    suspend fun fileTitle(book: ListenBook, kind: ExportKind): String

    /** Bắt đầu xuất MP3 vào thư mục đã nhớ; `chapterIds`: chỉ các chương ấy (null = cả cuốn). */
    suspend fun startMp3(book: ListenBook, chapterIds: List<Int>?, music: Boolean): Started

    /** Bắt đầu xuất M4B vào `file` (người dùng vừa tạo ở hộp "tạo file" của hệ thống). */
    suspend fun startM4b(book: ListenBook, file: String, music: Boolean): Started

    /** Bắt đầu đọc cả cuốn bằng giọng `voice` rồi ghép thành M4B vào `file`. */
    suspend fun startAudiobook(book: ListenBook, voice: String, file: String, music: Boolean): Started

    /** Dừng lượt đang chạy của cuốn. */
    suspend fun cancel(kind: ExportKind, bookId: String)

    /** Mở file vừa xuất bằng app nghe sách nói của máy; false khi máy không mở được. */
    suspend fun open(uri: String): Boolean

    /** Mở thư mục MP3 bằng app Tệp; false khi máy không mở được. */
    suspend fun openFolder(uri: String): Boolean

    /** Mọi tin của ba kiểu xuất (tiến độ, xong, dừng, lỗi). */
    fun events(): Flow<ExportEvent>

    /** Các lượt đang chạy (tin cuối của từng lượt, kèm nơi lưu): để nối lại khi tiến trình dựng lại giữa lúc việc nền vẫn chạy. */
    suspend fun running(): List<ExportEvent>
}

/** Việc cần hệ điều hành: Activity cung cấp, test đưa bản giả. */
@Stable
class ExportLinks(
    /** Mở bộ chọn thư mục của hệ thống; `result` nhận địa chỉ thư mục, null khi bạn huỷ. */
    val pickFolder: (result: (String?) -> Unit) -> Unit = { it(null) },
    /** Mở hộp "tạo file" của hệ thống với tên gợi ý theo `title`; `result` nhận địa chỉ file vừa tạo, null khi bạn huỷ. */
    val createFile: (title: String, result: (String?) -> Unit) -> Unit = { _, result -> result(null) },
    /** Mở bảng chia sẻ của hệ thống với file vừa xuất; false khi máy không gửi được. */
    val share: (uri: String, name: String) -> Boolean = { _, _ -> false },
    val openAppSettings: () -> Unit = {},
)
