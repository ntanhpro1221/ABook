package vn.abook.player

import android.content.Context
import android.content.Intent
import android.net.Uri
import java.io.File

/**
 * "Lưu thay đổi" / "Lưu thành" một cuốn thành file sách - việc mà cả hai giao diện cùng làm (WebView qua [LibraryPlugin.saveBook], native qua `ui.data.LibraryRepo`).
 * Ghi file là [BookSave] (dựng và kiểm trong file tạm trước, bản cũ không mất); ở đây là phần quanh nó: loại file, chỗ lưu NHỚ lần trước, hộp "tạo file" của hệ thống.
 * Đọc / ghi đĩa: gọi ở luồng nền.
 */
object BookSaves {
    /** Kết quả một lần ghi: tên file người dùng thấy, cỡ, và số thay đổi của người nghe đi theo (0 = file giống hệt bản gốc). */
    class Written(val name: String, val size: Long, val edits: Int)

    /** Cuốn này lưu thành file được: cuốn mở từ file / làm trên máy; sách của máy tính thì lưu từ máy ấy. */
    fun canSave(id: String): Boolean = BookActions.canShare(id)

    /** "Lưu" giữ loại file cuốn đã đến (có `project.json` = file dự án); "Lưu thành" chọn `as` ("abook" | "abookproj"). */
    fun asProject(id: String, kind: String?): Boolean =
        (kind ?: if (ProjectDocument.kept(Store.bookDir(id)) != null) "abookproj" else "abook") == "abookproj"

    /** Hộp "tạo file" của hệ thống, sẵn tên gợi ý; người nghe chọn chỗ và tên. */
    fun askIntent(id: String, project: Boolean): Intent {
        val title = Store.manifest(id)?.optString("title").orEmpty()
        return Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE)
            .setType(if (project) BookFileImport.PROJECT_MIMETYPE else BookFileImport.MIMETYPE)
            .putExtra(Intent.EXTRA_TITLE, BookDocumentWriter.defaultName(title, project))
            .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION or Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION)
    }

    private fun places(context: Context) = context.getSharedPreferences("book_saves", Context.MODE_PRIVATE)

    /** Chỗ "Lưu" đã ghi lần trước của cuốn này, cùng loại file và còn quyền ghi; không thì null (hỏi lại). */
    fun remembered(context: Context, id: String, project: Boolean): Uri? {
        val (kind, address) = places(context).getString(id, null)?.split("|", limit = 2)?.takeIf { it.size == 2 } ?: return null
        if ((kind == "abookproj") != project) return null
        val uri = Uri.parse(address)
        return uri.takeIf { context.contentResolver.persistedUriPermissions.any { grant -> grant.uri == it && grant.isWritePermission } }
    }

    fun remember(context: Context, id: String, project: Boolean, uri: Uri) {
        val kept = runCatching {
            context.contentResolver.takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION)
        }
        if (kept.isSuccess) places(context).edit().putString(id, "${if (project) "abookproj" else "abook"}|$uri").apply()
    }

    fun forget(context: Context, id: String) {
        places(context).edit().remove(id).apply()
    }

    /** Cỡ file đang nằm ở `uri` (0 = không biết) - để BookSave tính chỗ trống cho cả bản cũ. */
    private fun sizeAt(context: Context, uri: Uri): Long = runCatching {
        context.contentResolver.query(uri, arrayOf(android.provider.OpenableColumns.SIZE), null, null, null)?.use { cursor ->
            if (cursor.moveToFirst() && !cursor.isNull(0)) cursor.getLong(0) else 0L
        }
    }.getOrNull() ?: 0L

    private fun nameAt(context: Context, uri: Uri): String = runCatching {
        context.contentResolver.query(uri, arrayOf(android.provider.OpenableColumns.DISPLAY_NAME), null, null, null)?.use { cursor ->
            if (cursor.moveToFirst()) cursor.getString(0) else null
        }
    }.getOrNull() ?: ""

    /**
     * Ghi cuốn vào `uri` (gói dựng và kiểm trong file tạm trước, đích chỉ bị mở sau đó - [BookSave.save]). `direct`: chỗ nhớ từ lần trước - mở không được thì ném
     * [BookSave.DestinationUnavailable] để nơi gọi hỏi lại chỗ lưu; chỗ vừa chọn thì nhớ lại. Ném câu lỗi cho người đọc khi không lưu được.
     */
    fun write(context: Context, id: String, uri: Uri, project: Boolean, direct: Boolean): Written {
        val snapshot = ExportHistory.snapshot(Store.bookDir(id))
        val written = BookSave.save(Store.bookDir(id), File(context.cacheDir, "save"), project,
            previous = { context.contentResolver.openInputStream(uri) ?: throw BookSave.DestinationUnavailable() },
            open = { context.contentResolver.openOutputStream(uri, "wt") ?: throw BookSave.DestinationUnavailable() },
            keepDir = OldSaves.dir(context.filesDir), keepName = Store.manifest(id)?.optString("title").orEmpty(),
            previousSize = sizeAt(context, uri), destination = uri.toString())
        ExportHistory.remember(Store.bookDir(id), if (project) "abookproj" else "abook", uri.toString(), snapshot)
        BookEdits.markSaved(Store.bookDir(id)) // "Lưu thay đổi" đếm lại từ đây
        if (!direct) remember(context, id, project, uri)
        return Written(nameAt(context, uri), written.size, written.edits)
    }
}
