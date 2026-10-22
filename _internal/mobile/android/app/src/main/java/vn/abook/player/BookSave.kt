package vn.abook.player

import org.json.JSONObject
import java.io.File
import java.io.InputStream
import java.io.OutputStream
import java.util.zip.ZipEntry
import java.util.zip.ZipFile

/**
 * "Lưu" / "Lưu thành…" vào một file có sẵn (LibraryPlugin.writeSavedBook) mà không để mất bản cũ (soát a99 C2, a100): gói hoàn chỉnh được dựng và KIỂM trong file tạm
 * (cache) trước; chỉ khi đó mới mở đích để chép. Thiếu file nguồn hay gói hỏng thì đích chưa bị chạm. Mở đích ("wt") cắt nó về 0 byte ngay, nên bản cũ được
 * chép sang file tạm riêng trước đó và trả lại nếu chép gói mới giữa chừng hỏng (đầy ổ, mất kết nối) - lúc ấy người dùng vẫn còn bản lưu trước.
 * Ba chỗ không để mất bản cũ: không giữ được bản cũ sang file tạm thì dừng TRƯỚC khi mở đích; thiếu chỗ cho gói + bản cũ thì báo sớm; trả bản cũ cũng hỏng
 * thì file giữ phòng dời sang [save]`.keepDir` (bền, không bị hệ thống dọn như cache) và lời báo nói rõ nó nằm đâu.
 */
object BookSave {
    /** Không lưu được vì gói dựng ra không hợp lệ - câu chữ để người dùng đọc. */
    class Failed(message: String, cause: Throwable? = null) : Exception(message, cause)

    /** Chỗ dư ngoài cỡ gói + bản cũ: chép dở, thư mục tạm, bộ nhớ gần đầy làm hệ thống từ chối ghi. */
    const val HEADROOM = 8L shl 20

    /** Cỡ gói dựng ước từ thư mục sách (audio, chữ, bìa nằm nguyên trong gói; dư chút vì lớp sửa và dự án chia bí danh). */
    fun estimate(bookDir: File): Long = bookDir.walkTopDown().filter { it.isFile }.sumOf { it.length() }

    /** Byte cần trống trong thư mục tạm: gói mới + bản cũ (đều nằm đó cùng lúc) + [HEADROOM]. */
    fun roomNeeded(bookDir: File, previousSize: Long): Long = estimate(bookDir) + previousSize.coerceAtLeast(0) + HEADROOM

    /**
     * Dựng cuốn `bookDir` thành gói trong `scratch`, kiểm, rồi chép vào `open()`. `previous()`: nội dung hiện có của đích (null = chưa có gì để giữ), chỉ được hỏi
     * sau khi gói đã kiểm xong; `previousSize`: cỡ nội dung ấy nếu biết (0 = không biết). `keepDir`/`keepName`: chỗ bền và tên sách để đặt file bản cũ khi trả lại hỏng.
     * `spaceLeft`: byte còn trống ở thư mục tạm. Trả [BookDocumentWriter.Written] của gói đã chép.
     */
    fun save(
        bookDir: File,
        scratch: File,
        asProject: Boolean,
        previous: () -> InputStream?,
        open: () -> OutputStream,
        keepDir: File,
        keepName: String,
        previousSize: Long = 0,
        spaceLeft: (File) -> Long = { it.usableSpace },
        now: () -> Long = System::currentTimeMillis,
    ): BookDocumentWriter.Written {
        scratch.mkdirs()
        val needed = roomNeeded(bookDir, previousSize)
        val free = spaceLeft(scratch)
        if (free < needed) {
            throw Failed("Máy không đủ chỗ trống để lưu: cần khoảng ${megabytes(needed)} MB (gói mới và bản đang có), còn ${free.coerceAtLeast(0) shr 20} MB - file đang lưu không bị thay.")
        }
        val built = File.createTempFile("save-", ".part", scratch)
        val backup = File.createTempFile("save-", ".old", scratch)
        var keepBackup = false
        try {
            val written = built.outputStream().use { BookDocumentWriter.write(bookDir, it, asProject) }
            verify(built, written, asProject)
            val hadPrevious = try {
                previous()?.use { input -> backup.outputStream().use { input.copyTo(it) } } != null
            } catch (error: Exception) {
                throw Failed("Không giữ được bản cũ để phòng hỏng - file đang lưu không bị thay.", error)
            }
            try {
                open().use { sink -> built.inputStream().use { it.copyTo(sink) } }
            } catch (error: Exception) {
                if (hadPrevious) {
                    val restored = runCatching { open().use { sink -> backup.inputStream().use { it.copyTo(sink) } } }
                    if (restored.isFailure) {
                        val kept = keepBackup(backup, keepDir, keepName, asProject, now())
                        keepBackup = kept == null
                        throw Failed(lostMessage(kept, backup), error)
                    }
                }
                throw error
            }
            return written
        } finally {
            built.delete()
            if (!keepBackup) backup.delete()
        }
    }

    private fun megabytes(bytes: Long) = ((bytes + (1L shl 20) - 1) shr 20)

    /** Dời file giữ phòng sang `keepDir`; trả đường dẫn mới, hay null khi không dời được (khi ấy file ở nguyên chỗ cũ và không bị xoá). */
    private fun keepBackup(backup: File, keepDir: File, name: String, asProject: Boolean, time: Long): File? = try {
        keepDir.mkdirs()
        val stamp = java.text.SimpleDateFormat("yyyyMMdd-HHmmss", java.util.Locale.ROOT).format(java.util.Date(time))
        val title = BookDocumentWriter.defaultName(name, asProject).removeSuffix(if (asProject) BookDocumentWriter.PROJECT_EXTENSION else BookDocumentWriter.EXTENSION)
        val target = File(keepDir, "$title $stamp" + if (asProject) BookDocumentWriter.PROJECT_EXTENSION else BookDocumentWriter.EXTENSION)
        if (!backup.renameTo(target)) {
            backup.copyTo(target, overwrite = true)
            backup.delete()
        }
        target
    } catch (error: Exception) {
        null
    }

    private fun lostMessage(kept: File?, backup: File): String =
        if (kept != null) "Lưu giữa chừng bị hỏng và bản lưu trước cũng chưa trả lại được vào file. Bản lưu trước vẫn còn nguyên trong bộ nhớ của app: thư mục ${kept.parentFile?.name}, file ${kept.name}."
        else "Lưu giữa chừng bị hỏng và bản lưu trước cũng chưa trả lại được vào file. Bản lưu trước tạm nằm ở ${backup.path} - hãy chép nó ra trước khi dọn bộ nhớ của app."

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
