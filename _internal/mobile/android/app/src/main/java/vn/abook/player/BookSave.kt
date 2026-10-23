package vn.abook.player

import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.io.FileNotFoundException
import java.io.InputStream
import java.io.OutputStream
import java.util.zip.ZipEntry
import java.util.zip.ZipFile

/**
 * "Lưu" / "Lưu thành…" vào một file có sẵn (LibraryPlugin.writeSavedBook) mà không để mất bản cũ (soát a99 C2, a100): gói hoàn chỉnh được dựng và KIỂM trong file tạm
 * (cache) trước; chỉ khi đó mới mở đích để chép. Thiếu file nguồn hay gói hỏng thì đích chưa bị chạm. Mở đích ("wt") cắt nó về 0 byte ngay, nên bản cũ được
 * chép và sync ở keepDir cùng nhật ký URI/tên sách trước đó. Lỗi chép thì trả lại bản trước; chết tiến trình thì lần mở sau bản trước có ngay trong Bản lưu cũ.
 * Không giữ được bản cũ hoặc nhật ký thì dừng TRƯỚC khi mở đích; thiếu chỗ cho gói + bản cũ thì báo sớm.
 */
object BookSave {
    /** Không lưu được vì gói dựng ra không hợp lệ - câu chữ để người dùng đọc. */
    class Failed(message: String, cause: Throwable? = null) : Exception(message, cause)

    class DestinationUnavailable(cause: Throwable? = null) : Exception("Không mở được nơi lưu cũ của bạn. Bạn hãy chọn nơi lưu khác.", cause)

    internal fun shouldChooseAnotherLocation(direct: Boolean, error: Throwable): Boolean = direct && error is DestinationUnavailable

    private fun <T : Any> openDestination(open: () -> T?): T = try {
        open() ?: throw DestinationUnavailable()
    } catch (error: FileNotFoundException) {
        throw DestinationUnavailable(error)
    } catch (error: SecurityException) {
        throw DestinationUnavailable(error)
    }

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
        destination: String = "",
    ): BookDocumentWriter.Written {
        scratch.mkdirs()
        val needed = roomNeeded(bookDir, previousSize)
        val free = spaceLeft(scratch)
        if (free < needed) {
            throw Failed("Thiếu chỗ lưu (cần ${megabytes(needed)} MB, còn ${free.coerceAtLeast(0) shr 20} MB); giữ file đang có.")
        }
        val built = File.createTempFile("save-", ".part", scratch)
        var backup: File? = null
        var journal: File? = null
        var completed = false
        try {
            val written = built.outputStream().use { BookDocumentWriter.write(bookDir, it, asProject) }
            verify(built, written, asProject)
            // Only opening the URI is classified as lost access. Failures while writing
            // the durable backup/journal remain preservation failures, even if ENOENT.
            val previousStream = try { previous() }
                catch (error: DestinationUnavailable) { throw error }
                catch (error: FileNotFoundException) { throw DestinationUnavailable(error) }
                catch (error: SecurityException) { throw DestinationUnavailable(error) }
                catch (error: Exception) { throw Failed("Không giữ được bản cũ để phòng hỏng - file đang lưu không bị thay.", error) }
            try {
                previousStream?.use { input ->
                    check(keepDir.isDirectory || keepDir.mkdirs()) { "Không mở được nơi giữ bản lưu cũ của bạn" }
                    val pendingDir = File(keepDir, ".pending")
                    check(pendingDir.isDirectory || pendingDir.mkdirs()) { "Không mở được nhật ký lưu sách của bạn" }
                    val stamp = java.text.SimpleDateFormat("yyyyMMdd-HHmmss", java.util.Locale.ROOT).format(java.util.Date(now()))
                    val extension = if (asProject) BookDocumentWriter.PROJECT_EXTENSION else BookDocumentWriter.EXTENSION
                    val title = BookDocumentWriter.defaultName(keepName, asProject).removeSuffix(extension)
                    val temporary = File.createTempFile("$title $stamp-", ".part", pendingDir)
                    // Durable storage and fsync precede the first open("wt") on the destination.
                    FileOutputStream(temporary).use { output -> input.copyTo(output); output.fd.sync() }
                    val kept = File(keepDir, temporary.name.removeSuffix(".part") + extension)
                    check(!kept.exists() && temporary.renameTo(kept)) { "Không giữ được bản lưu cũ của bạn" }
                    backup = kept
                    val pending = File(keepDir, ".pending/${kept.name}.json")
                    Store.writeAtomic(pending, JSONObject().put("backup", kept.name).put("uri", destination)
                        .put("title", keepName).put("startedAt", now()).toString())
                    journal = pending
                }
                check(previousSize <= 0 || backup != null) { "Chưa đọc được file cũ của bạn" }
            } catch (error: Exception) {
                throw Failed("Không giữ được bản cũ để phòng hỏng - file đang lưu không bị thay.", error)
            }
            try {
                openDestination(open).use { sink ->
                    built.inputStream().use { it.copyTo(sink) }
                    sink.flush()
                    if (sink is FileOutputStream) sink.fd.sync()
                }
            } catch (error: Exception) {
                if (error is DestinationUnavailable) throw error // no output stream was opened; keep the backup
                val kept = backup
                if (kept != null) {
                    val restored = runCatching { open().use { sink ->
                        kept.inputStream().use { it.copyTo(sink) }
                        sink.flush()
                        if (sink is FileOutputStream) sink.fd.sync()
                    } }
                    if (restored.isFailure) {
                        throw Failed(lostMessage(kept), error)
                    }
                }
                completed = true // previous destination restored; no interrupted write remains
                throw error
            }
            completed = true
            return written
        } finally {
            built.delete()
            // Process death (including Error in tests) never removes the durable backup or intent.
            if (completed) {
                // Remove intent first. A crash before deleting the backup merely retains an extra old save.
                val pending = journal
                if (pending == null || pending.delete()) backup?.delete()
                pending?.parentFile?.delete() // succeeds only for an empty directory
            }
        }
    }

    private fun megabytes(bytes: Long) = ((bytes + (1L shl 20) - 1) shr 20)

    private fun lostMessage(kept: File): String =
        "Lưu lỗi, chưa khôi phục được; bản cũ còn ở Cài đặt → Bản lưu cũ: ${kept.name}."

    /** Reopening an interrupted save exposes the already durable backup in OldSaves. Idempotent; never opens a URI. */
    fun recover(keepDir: File): List<String> = File(keepDir, ".pending").listFiles().orEmpty()
        .filter { it.isFile && it.extension == "json" }.mapNotNull { file ->
            try {
                val intent = Store.readJson(file) ?: return@mapNotNull null
                val name = intent.getString("backup")
                OldSaves.resolve(keepDir, name)
                name
            } catch (_: Exception) {
                // A broken journal or a backup the user already exported/deleted must not hide other saves.
                Store.addDataNotice("Lưu chưa xong; giữ các file còn lại — bạn xem Cài đặt → Bản lưu cũ.")
                null
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
