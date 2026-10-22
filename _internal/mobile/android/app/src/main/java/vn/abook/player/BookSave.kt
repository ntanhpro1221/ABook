package vn.abook.player

import org.json.JSONObject
import java.io.File
import java.io.InputStream
import java.io.OutputStream
import java.util.zip.ZipEntry
import java.util.zip.ZipFile

/**
 * "Lưu" / "Lưu thành…" vào một file có sẵn (LibraryPlugin.writeSavedBook) mà không để mất bản cũ (soát a99 C2): gói hoàn chỉnh được dựng và KIỂM trong file tạm
 * (cache) trước; chỉ khi đó mới mở đích để chép. Thiếu file nguồn hay gói hỏng thì đích chưa bị chạm. Mở đích ("wt") cắt nó về 0 byte ngay, nên bản cũ được
 * chép sang file tạm riêng trước đó và trả lại nếu chép gói mới giữa chừng hỏng (đầy ổ, mất kết nối) - lúc ấy người dùng vẫn còn bản lưu trước.
 */
object BookSave {
    /** Không lưu được vì gói dựng ra không hợp lệ - câu chữ để người dùng đọc. */
    class Failed(message: String, cause: Throwable? = null) : Exception(message, cause)

    /**
     * Dựng cuốn `bookDir` thành gói trong `scratch`, kiểm, rồi chép vào `open()`. `previous()`: nội dung hiện có của đích (null = chưa có gì để giữ), chỉ được hỏi
     * sau khi gói đã kiểm xong. Trả [BookDocumentWriter.Written] của gói đã chép.
     */
    fun save(bookDir: File, scratch: File, asProject: Boolean, previous: () -> InputStream?, open: () -> OutputStream): BookDocumentWriter.Written {
        scratch.mkdirs()
        val built = File.createTempFile("save-", ".part", scratch)
        val backup = File.createTempFile("save-", ".old", scratch)
        try {
            val written = built.outputStream().use { BookDocumentWriter.write(bookDir, it, asProject) }
            verify(built, written, asProject)
            val hadPrevious = runCatching { previous()?.use { input -> backup.outputStream().use { input.copyTo(it) } } != null }.getOrDefault(false)
            try {
                open().use { sink -> built.inputStream().use { it.copyTo(sink) } }
            } catch (error: Exception) {
                if (hadPrevious) runCatching { open().use { sink -> backup.inputStream().use { it.copyTo(sink) } } }
                throw error
            }
            return written
        } finally {
            built.delete()
            backup.delete()
        }
    }

    /** Gói vừa dựng mở lại được như một gói của app: `mimetype` đầu tiên và không nén, đủ cỡ như đã ghi, và (file `.abook`) từng mục khớp cỡ trong `book.json`. */
    internal fun verify(file: File, written: BookDocumentWriter.Written, asProject: Boolean) {
        if (file.length() != written.size) throw Failed("Gói sách ghi ra chưa trọn vẹn - file đang lưu không bị thay.")
        try {
            ZipFile(file).use { zip ->
                val entries = zip.entries().toList()
                val first = entries.firstOrNull()
                if (first == null || first.name != "mimetype" || first.method != ZipEntry.STORED) throw Failed("Gói sách ghi ra không đúng dạng - file đang lưu không bị thay.")
                val mime = zip.getInputStream(first).readBytes().toString(Charsets.US_ASCII)
                if (mime != (if (asProject) BookFileImport.PROJECT_MIMETYPE else BookFileImport.MIMETYPE)) throw Failed("Gói sách ghi ra không đúng dạng - file đang lưu không bị thay.")
                val book = zip.getEntry("book.json") ?: throw Failed("Gói sách ghi ra thiếu phần mô tả - file đang lưu không bị thay.")
                if (!asProject) {
                    val listed = JSONObject(zip.getInputStream(book).readBytes().toString(Charsets.UTF_8)).getJSONObject("package").getJSONObject("files")
                    for (name in listed.keys()) {
                        val entry = zip.getEntry(name)
                        if (entry == null || entry.size != listed.getJSONObject(name).getLong("size")) throw Failed("Gói sách ghi ra thiếu hay lệch file $name - file đang lưu không bị thay.")
                    }
                }
            }
        } catch (error: Failed) {
            throw error
        } catch (error: Exception) {
            throw Failed("Gói sách ghi ra không đọc lại được - file đang lưu không bị thay.", error)
        }
    }
}
