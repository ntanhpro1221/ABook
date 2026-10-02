package vn.abook.player

import android.content.Context
import android.net.Uri
import android.provider.OpenableColumns
import org.json.JSONObject
import java.io.File
import java.security.MessageDigest
import java.util.zip.ZipEntry
import java.util.zip.ZipFile

/**
 * Mở một file sách của app (.abook - abook/webui/bookfile.py): kiểm y như máy tính rồi giải nén vào
 * books/<thư mục>/, đúng chỗ sách tải qua Wi-Fi nằm - thư viện, trình phát, đọc theo dùng lại nguyên vẹn. Sách không mang
 * mã nào: tên thư mục do app đặt (suy từ nội dung, hoặc đúng cuốn cùng lần sản xuất đã có trên máy).
 *
 * File đến từ bất kỳ đâu (Zalo, Drive, email, thẻ nhớ), nên coi là dữ liệu của người lạ: chỉ nhận đúng các tên mục của
 * định dạng (không đường dẫn tuyệt đối, không ".."), số mục và cỡ có trần, định dạng mới hơn app thì nhắc cập nhật, và
 * mọi file phải đúng cỡ + mã băm ghi trong book.json TRƯỚC khi sách vào thư viện. Giải nén vào thư mục tạm rồi mới đổi
 * tên: hỏng giữa chừng không bao giờ để lại nửa cuốn. Nhập lại cùng cuốn thì thay bản cũ.
 *
 * Phiên bản 3 (cả bộ nhiều phần trong một file, bookfile.pack_series): audio ở chapters/<phần>/<tên>.mp3 và có thể vài GB,
 * nên trước khi chép từ trình quản lý file và trước khi giải nén phải còn đủ chỗ - không thì từ chối rõ ràng thay vì để
 * bộ nhớ đầy giữa chừng.
 */
object BookFileImport {
    const val MIMETYPE = "application/vnd.ngdtuanh.abook+zip"
    private const val FORMAT = "abook"
    private const val FORMAT_VERSION = 3  // 2 = có thêm rãnh nhạc nền (music/<sha1>.mp3); 3 = cả bộ nhiều phần (chapters/<phần>/...)
    /** Chỗ trống dư ngoài cỡ giải nén (book.json, thư mục tạm): đủ để không đầy bộ nhớ giữa chừng. */
    private const val ROOM_MARGIN = 64L shl 20
    private const val MAX_ENTRIES = 20_000
    private const val MAX_TOTAL_BYTES = 64L shl 30
    private const val MAX_JSON_BYTES = 32L shl 20
    private const val COMMON = """cast\.json|cover\.jpg|scripts/\d+\.json|samples/\d+\.wav|music/[0-9a-f]{40}\.mp3"""
    private val CONTENT = Regex("""$COMMON|chapters/[0-9A-Za-z_.\-]+\.mp3""")
    /** Phiên bản 3 thêm thư mục phần: chapters/<phần>/<tên>.mp3 (phiên bản 1-2 không có - gặp thì là mục lạ). */
    private val CONTENT_V3 = Regex("""$COMMON|chapters/(?:\d{1,4}/)?[0-9A-Za-z_.\-]+\.mp3""")
    private val DESCRIPTIONS = setOf("mimetype", "book.json", "manifest.json")

    /** Lý do không nhận file - câu chữ để người dùng đọc. */
    class Refused(message: String) : Exception(message)

    data class Imported(val id: String, val title: String)

    /** Chép từ content:// (trình quản lý file, Zalo, Drive...) vào bộ nhớ đệm rồi nhập. */
    fun import(context: Context, uri: Uri): Imported {
        Store.init(context)
        val copy = File(context.cacheDir, "import-${System.nanoTime()}.abook")
        try {
            sizeOf(context, uri)?.let { requireRoom(context.cacheDir, it + ROOM_MARGIN) }
            val input = context.contentResolver.openInputStream(uri) ?: throw Refused("Không đọc được file.")
            input.use { source -> copy.outputStream().use { source.copyTo(it) } }
            return importFile(copy)
        } finally {
            copy.delete()
        }
    }

    /** Cỡ file theo trình quản lý file (content://), nếu nó cho biết. */
    private fun sizeOf(context: Context, uri: Uri): Long? = runCatching {
        context.contentResolver.query(uri, arrayOf(OpenableColumns.SIZE), null, null, null)?.use { cursor ->
            if (cursor.moveToFirst() && !cursor.isNull(0)) cursor.getLong(0) else null
        }
    }.getOrNull()

    /** Ổ chứa `dir` còn đủ `need` byte không? Không thì từ chối, nói cần bao nhiêu và còn bao nhiêu (`File.usableSpace` là
     *  số StatFs báo cho ứng dụng). `freeSpace` cho test JVM đặt số khác. */
    private fun requireRoom(dir: File, need: Long, freeSpace: (File) -> Long = { it.usableSpace }) {
        val free = freeSpace(dir)
        if (free < need) {
            throw Refused("Bộ nhớ máy không đủ chỗ để mở sách này: cần khoảng ${gigabytes(need)}, còn ${gigabytes(free)}. " +
                "Hãy xoá bớt rồi mở lại file.")
        }
    }

    private fun gigabytes(bytes: Long) = "%.1f GB".format(java.util.Locale.ROOT, bytes / (1L shl 30).toDouble()).replace('.', ',')

    fun importFile(file: File, freeSpace: (File) -> Long = { it.usableSpace }): Imported {
        val zip = try {
            ZipFile(file)
        } catch (error: Exception) {
            throw Refused("Đây không phải file sách của app.")
        }
        zip.use {
            val entries = zip.entries().toList()
            val first = entries.firstOrNull()
            if (first == null || first.name != "mimetype" || first.method != ZipEntry.STORED ||
                zip.getInputStream(first).use { it.readBytes() }.toString(Charsets.US_ASCII).trim() != MIMETYPE
            ) {
                throw Refused("Đây không phải file sách của app.")
            }
            if (entries.size > MAX_ENTRIES) throw Refused("File sách có quá nhiều mục.")
            val names = HashSet<String>()
            var total = 0L
            for (entry in entries) {
                val name = entry.name
                if (entry.isDirectory || !names.add(name)) throw Refused("Gói có mục trùng hay thư mục lạ: $name")
                total += maxOf(0L, entry.size)
            }
            if (total > MAX_TOTAL_BYTES) throw Refused("File sách quá lớn.")
            val bookEntry = zip.getEntry("book.json") ?: throw Refused("File sách thiếu phần mô tả (book.json).")
            if (bookEntry.size > MAX_JSON_BYTES) throw Refused("book.json quá lớn.")
            val book = try {
                JSONObject(zip.getInputStream(bookEntry).use { it.readBytes() }.toString(Charsets.UTF_8))
            } catch (error: Exception) {
                throw Refused("book.json hỏng.")
            }
            val pack = book.optJSONObject("package")
            if (pack == null || pack.optString("format") != FORMAT) throw Refused("Đây không phải file sách của app.")
            val version = pack.optInt("version", -1)
            if (version < 1) throw Refused("File sách có phiên bản định dạng không hợp lệ.")
            if (version > FORMAT_VERSION) throw Refused("Sách này được làm bằng bản app mới hơn. Hãy cập nhật app để mở.")
            val allowed = if (version >= 3) CONTENT_V3 else CONTENT  // thư mục phần chỉ có từ phiên bản 3
            for (name in names - DESCRIPTIONS) if (!allowed.matches(name)) throw Refused("Gói có mục lạ: $name")
            val files = pack.optJSONObject("files") ?: throw Refused("Danh sách file trong sách không khớp nội dung gói.")
            val content = names - DESCRIPTIONS
            if (files.keys().asSequence().toSet() != content) {
                throw Refused("Danh sách file trong sách không khớp nội dung gói.")
            }
            // Sách không mang mã nào (chủ sách 27-09): app nhận ra cùng một lần sản xuất bằng audio từng chương.
            val chapters = JSONObject()
            for (name in content.filter { it.startsWith("chapters/") }) {
                val meta = files.getJSONObject(name)
                chapters.put(name, JSONObject().put("size", meta.optLong("size")).put("sha256", meta.optString("sha256")))
            }
            // Cùng cuốn đã có trên máy (tải qua Wi-Fi, hay mở từ file trước đó): nhập VÀO đúng cuốn ấy, giữ mã của nó để
            // chỗ nghe vẫn nối - không thành hai cuốn. Bản trên máy nhiều chương hơn file thì giữ nguyên bản trên máy.
            val existing = Store.findByChapters(chapters)
            val target = existing ?: contentKey(chapters)
            val current = existing?.let { Store.manifest(it) }
            if (current != null && current.optInt("chaptersAvailable") > book.optInt("chaptersAvailable")) {
                return Imported(target, current.optString("title"))
            }
            val books = File(Store.root, "books").apply { mkdirs() }
            requireRoom(books, total + ROOM_MARGIN, freeSpace)
            val staging = File(books, ".$target.${System.nanoTime()}.part")
            try {
                for (name in DESCRIPTIONS.filter { it != "mimetype" && it in names } + content.sorted()) {
                    val (size, sha256) = extract(zip, name, File(staging, name))
                    val expected = files.optJSONObject(name) ?: continue
                    if (size != expected.optLong("size", -1) || sha256 != expected.optString("sha256")) {
                        throw Refused("File sách bị hỏng hoặc bị sửa ($name). Hãy chép lại file từ nguồn.")
                    }
                }
                // Bản sách của app trên máy mang mã thư mục của app (book.json không nằm trong danh sách mã băm).
                Store.writeAtomic(File(staging, "book.json"), book.put("id", target).toString())
                replace(books, staging, Store.bookDir(target), target)
            } finally {
                staging.deleteRecursively()
            }
            Store.rememberChapters(target, chapters, imported = existing == null || Store.isImported(existing))
            return Imported(target, book.optString("title"))
        }
    }

    /**
     * Tên thư mục cho cuốn mở từ file, suy từ nội dung - mở lại đúng file ấy thì trùng tên. Đúng công thức của máy tính
     * (abook/webui/fingerprints.py: content_key): "f-" + 24 hex đầu của sha256("tên:sha256" các chương, xếp tên).
     */
    fun contentKey(chapters: JSONObject): String {
        val text = chapters.keys().asSequence().sorted()
            .joinToString("\n") { "$it:${chapters.getJSONObject(it).optString("sha256")}" }
        val digest = MessageDigest.getInstance("SHA-256").digest(text.toByteArray(Charsets.UTF_8))
        return "f-" + digest.joinToString("") { "%02x".format(it) }.take(24)
    }

    private fun extract(zip: ZipFile, name: String, target: File): Pair<Long, String> {
        target.parentFile?.mkdirs()
        val digest = MessageDigest.getInstance("SHA-256")
        var size = 0L
        zip.getInputStream(zip.getEntry(name)).use { source ->
            target.outputStream().use { sink ->
                val buffer = ByteArray(1 shl 16)
                while (true) {
                    val read = source.read(buffer)
                    if (read < 0) break
                    digest.update(buffer, 0, read)
                    sink.write(buffer, 0, read)
                    size += read
                }
            }
        }
        return size to digest.digest().joinToString("") { "%02x".format(it) }
    }

    private fun replace(books: File, staging: File, target: File, id: String) = synchronized(Store) {
        if (!target.exists()) {
            if (!staging.renameTo(target)) throw Refused("Không ghi được sách vào thư viện.")
            return@synchronized
        }
        val retired = File(books, ".$id.${System.nanoTime()}.old")
        if (!target.renameTo(retired)) throw Refused("Không thay được bản cũ của sách.")
        if (!staging.renameTo(target)) {
            retired.renameTo(target)
            throw Refused("Không ghi được sách vào thư viện.")
        }
        retired.deleteRecursively()
    }
}
