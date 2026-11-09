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
 * "Lưu" / "Lưu thành…" vào một file có sẵn mà không để mất bản cũ (soát a99 C2, a100): gói hoàn chỉnh được dựng và KIỂM trong file tạm
 * (cache) trước; chỉ khi đó mới mở đích để chép. Thiếu file nguồn hay gói hỏng thì đích chưa bị chạm. Mở đích ("wt") cắt nó về 0 byte ngay, nên bản cũ được
 * chép và sync ở keepDir cùng nhật ký URI/tên sách trước đó. Lỗi chép thì trả lại bản trước; chết tiến trình thì lần mở sau bản trước có ngay trong Bản lưu cũ.
 * Không giữ được bản cũ hoặc nhật ký thì dừng TRƯỚC khi mở đích; thiếu chỗ cho gói + bản cũ thì báo sớm.
 */
object BookSave {
    /** Không lưu được vì gói dựng ra không hợp lệ - câu chữ để người dùng đọc. */
    class Failed(message: String, cause: Throwable? = null) : Exception(message, cause)

    class DestinationUnavailable(cause: Throwable? = null) : Exception(S.s_chua_mo_duoc_noi_luu_cu_cua_ban_ban_hay_ch_ce25bbe4, cause)

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
            throw Failed(S.s_thieu_cho_luu_can_0_con_1_giu_file_dang_co_aa53932c(formatSize(needed), formatSize(free.coerceAtLeast(0))))
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
                catch (error: Exception) { throw Failed(S.s_chua_giu_duoc_ban_cu_de_phong_hong_file_da_203d0a7d, error) }
            try {
                previousStream?.use { input ->
                    check(keepDir.isDirectory || keepDir.mkdirs()) { S.s_chua_mo_duoc_noi_giu_ban_luu_cu_cua_ban_0eb38c4a }
                    val pendingDir = File(keepDir, ".pending")
                    check(pendingDir.isDirectory || pendingDir.mkdirs()) { S.s_chua_mo_duoc_nhat_ky_luu_sach_cua_ban_e7eec060 }
                    val stamp = java.text.SimpleDateFormat("yyyyMMdd-HHmmss", java.util.Locale.ROOT).format(java.util.Date(now()))
                    val extension = if (asProject) BookDocumentWriter.PROJECT_EXTENSION else BookDocumentWriter.EXTENSION
                    val title = BookDocumentWriter.defaultName(keepName, asProject).removeSuffix(extension)
                    val temporary = File.createTempFile("$title $stamp-", ".part", pendingDir)
                    // Durable storage and fsync precede the first open("wt") on the destination.
                    FileOutputStream(temporary).use { output -> input.copyTo(output); output.fd.sync() }
                    val kept = File(keepDir, temporary.name.removeSuffix(".part") + extension)
                    check(!kept.exists() && temporary.renameTo(kept)) { S.s_chua_giu_duoc_ban_luu_cu_cua_ban_7cbd7b09 }
                    backup = kept
                    val pending = File(keepDir, ".pending/${kept.name}.json")
                    Store.writeAtomic(pending, JSONObject().put("backup", kept.name).put("uri", destination)
                        .put("title", keepName).put("startedAt", now()).toString())
                    journal = pending
                }
                check(previousSize <= 0 || backup != null) { S.s_chua_doc_duoc_file_cu_cua_ban_9a83e0d2 }
            } catch (error: Exception) {
                throw Failed(S.s_chua_giu_duoc_ban_cu_de_phong_hong_file_da_203d0a7d, error)
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


    private fun lostMessage(kept: File): String =
        S.s_luu_loi_chua_khoi_phuc_duoc_ban_cu_con_o_c_34784af7(kept.name)

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
                Store.addDataNotice(S.s_luu_chua_xong_giu_cac_file_con_lai_ban_xem_8c4547d7)
                null
            }
        }

    /** Gói vừa dựng mở lại được như một gói của app: `mimetype` đầu tiên và không nén, đủ cỡ như đã ghi, và (file `.abook`) từng mục khớp cỡ trong `book.json`. */
    internal fun verify(file: File, written: BookDocumentWriter.Written, asProject: Boolean) {
        if (file.length() != written.size) throw Failed(S.s_goi_sach_ghi_ra_chua_tron_ven_file_dang_lu_f19837d9)
        try {
            ZipFile(file).use { zip ->
                val entries = zip.entries().toList()
                val first = entries.firstOrNull()
                if (first == null || first.name != "mimetype" || first.method != ZipEntry.STORED) throw Failed(S.s_goi_sach_ghi_ra_khong_dung_dang_file_dang_8e689551)
                val mime = zip.getInputStream(first).readBytes().toString(Charsets.US_ASCII)
                if (mime != (if (asProject) BookFileImport.PROJECT_MIMETYPE else BookFileImport.MIMETYPE)) throw Failed(S.s_goi_sach_ghi_ra_khong_dung_dang_file_dang_8e689551)
                val book = zip.getEntry("book.json") ?: throw Failed(S.s_goi_sach_ghi_ra_thieu_phan_mo_ta_file_dang_c03336e8)
                if (!asProject) {
                    val listed = JSONObject(zip.getInputStream(book).readBytes().toString(Charsets.UTF_8)).getJSONObject("package").getJSONObject("files")
                    for (name in listed.keys()) {
                        val entry = zip.getEntry(name)
                        if (entry == null || entry.size != listed.getJSONObject(name).getLong("size")) throw Failed(S.s_goi_sach_ghi_ra_thieu_hay_lech_file_0_file_8349384f(name))
                    }
                }
            }
        } catch (error: Failed) {
            throw error
        } catch (error: Exception) {
            throw Failed(S.s_goi_sach_ghi_ra_khong_doc_lai_duoc_file_da_bc1b363b, error)
        }
    }
}
