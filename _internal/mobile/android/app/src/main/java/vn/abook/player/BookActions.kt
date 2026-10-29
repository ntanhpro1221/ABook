package vn.abook.player

import android.content.ClipData
import android.content.Context
import android.content.Intent
import android.os.Handler
import android.os.Looper
import androidx.core.content.FileProvider
import org.json.JSONObject

/**
 * Việc với MỘT cuốn mà cả hai giao diện cùng làm (WebView qua [LibraryPlugin], native qua `ui.data.LibraryRepo`): sửa tên / tác giả, đánh dấu đã nghe,
 * xoá khỏi máy, đóng file sách để chia sẻ. Trước đây nằm trong thân phương thức plugin (docs/NATIVE_PHONE_UI.md §2: logic dời vào lõi, plugin chỉ chuyển tiếp).
 * Mọi hàm đọc / ghi đĩa: gọi ở luồng nền.
 */
object BookActions {
    /** Sau một lần sửa thành công (khác GET) qua [LocalStudio]: nhạc đang phát đọc lại lớp sửa, cuốn tải từ máy tính gửi phần sửa về sau vài giây. */
    fun edited(context: Context, id: String) {
        MusicBed.invalidate(id)
        EditsSync.schedule(context, id)
    }

    /**
     * Một đường của [LocalStudio] - cùng đường và cùng lời đáp mà bản web gọi (`EbookLibrary.studio`), nên hai giao diện sửa sách như nhau. Khác 200: ném câu lỗi của
     * lõi. Sửa xong (khác GET): nhạc đang phát đọc lại lớp sửa, cuốn của máy tính gửi phần sửa về ([edited], như LibraryPlugin.studio).
     */
    fun studio(context: Context, method: String, id: String, rest: String, body: JSONObject? = null): JSONObject {
        Store.init(context)
        val (status, reply) = LocalStudio.handle(method, "/api/books/$id$rest", body)
        val answer = reply as? JSONObject ?: JSONObject()
        if (status != 200) error(answer.optString("error").ifEmpty { "Bạn hãy thử lại." })
        if (method != "GET") edited(context, id)
        return answer
    }

    /** Một file văn bản của gói như người nghe thấy (lớp sửa phủ lên); sách nghe thẳng chưa có file thì lấy từ máy giữ sách trước. null khi không có. */
    fun text(context: Context, id: String, path: String): String? {
        val file = Store.file(id, path)
        val fromPeer = !Store.streamManifest(id)?.optString("source").isNullOrEmpty()
        if (!file.isFile && Store.rawManifest(id) == null && (fromPeer || SyncLink.paired(context))) Streaming.fetchSmall(context, id, path)
        return Store.readText(id, path)
    }

    /** "Đã nghe xong" / "Chưa nghe xong" cả cuốn ở hồ sơ đang dùng, rồi gửi chỗ nghe cho máy đã ghép. */
    fun setFinished(context: Context, id: String, finished: Boolean): JSONObject {
        val state = Store.setFinished(id, finished)
        runCatching { StateSync.pushNow(context, id) }
        return state
    }

    /** Một chương đã nghe xong / chưa nghe, rồi gửi chỗ nghe cho máy đã ghép. */
    fun setChapterDone(context: Context, id: String, chapterId: Int, done: Boolean): JSONObject {
        val state = Store.setChapterDone(id, chapterId, done)
        runCatching { StateSync.pushNow(context, id) }
        return state
    }

    /**
     * "Xoá khỏi máy": cuốn nằm chờ [TrashPending.UNDO_SECONDS] giây ([Store.holdBook]) rồi mới xoá hẳn; trả mã "Hoàn tác" (null khi đã xoá thẳng).
     * Chương tạm của "Xuất sách nói" bỏ dở đi theo sách khi sách bị xoá hẳn ([ListenExports.sweep] - cuốn đang xuất không bị đụng).
     * `background`: chỗ chạy việc dọn (luồng nền của nơi gọi).
     */
    fun delete(context: Context, id: String, background: (Runnable) -> Unit): String? {
        // Thiếu mã thì từ chối (Store.deletableBookDir) - `?: ""` từng biến thành xoá CẢ thư mục sách.
        // Cuốn đang có lượt tải chạy thì không dời thư mục dưới chân nó (soát a97 V6).
        require(!BookDownloads.isActive(context, id)) { "Đang tải cuốn này - huỷ tải rồi mới xoá được." }
        val undo = Store.holdBook(id)
        if (undo != null) {
            Handler(Looper.getMainLooper()).postDelayed(
                { background(Runnable { runCatching { Store.sweepTrash() }; runCatching { ListenExports.sweep(context) } }) },
                (TrashPending.UNDO_SECONDS + 1) * 1000L,
            )
        } else {
            background(Runnable { runCatching { ListenExports.sweep(context) } })
        }
        return undo
    }

    /** Cuốn này gửi được thành file sách: cuốn mở từ file / làm trên máy (có `package`); sách của máy tính thì gửi từ máy ấy. */
    fun canShare(id: String): Boolean {
        val manifest = Store.rawManifest(id) ?: return false
        return !Store.isComputerBook(id) && manifest.optJSONObject("package") != null
    }

    /** Bảng chia sẻ đã dựng: `chooser` mở bằng startActivity, `name` là tên file gửi đi. */
    class Shared(val chooser: Intent, val name: String)

    /**
     * Đóng cuốn thành file `.abook` (hay `.abookproj` khi `project`) trong `cacheDir/share` ([BookShare]) và dựng bảng chia sẻ của Android. Lỗi thì dọn file
     * dở và ném lại. Luồng nền; mở bảng (startActivity) là việc của nơi gọi, ở luồng chính.
     */
    fun share(context: Context, id: String, project: Boolean): Shared {
        require(canShare(id)) { "Sách này lấy từ máy tính khác - muốn gửi file sách thì gửi từ máy ấy" }
        val title = Store.manifest(id)?.optString("title").orEmpty()
        val file = BookShare.target(context.cacheDir, title, project)
        try {
            file.parentFile?.mkdirs()
            val snapshot = ExportHistory.snapshot(Store.bookDir(id))
            file.outputStream().use { BookDocumentWriter.write(Store.bookDir(id), it, project) }
            ExportHistory.remember(Store.bookDir(id), if (project) "abookproj" else "abook", file.name, snapshot)
            val uri = FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", file)
            val send = Intent(Intent.ACTION_SEND).setType(BookShare.mimeType(project))
                .putExtra(Intent.EXTRA_STREAM, uri)
                .putExtra(Intent.EXTRA_TITLE, file.name)
                .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            send.clipData = ClipData.newUri(context.contentResolver, file.name, uri)
            val chooser = Intent.createChooser(send, "Chia sẻ “${title.ifBlank { file.nameWithoutExtension }}”")
                .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            return Shared(chooser, file.name)
        } catch (error: Exception) {
            file.parentFile?.deleteRecursively()
            throw error
        }
    }
}
