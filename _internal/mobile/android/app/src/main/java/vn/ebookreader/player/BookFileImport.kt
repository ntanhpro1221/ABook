package vn.ebookreader.player

import android.content.Context
import android.net.Uri
import org.json.JSONObject
import java.io.File
import java.security.MessageDigest
import java.util.zip.ZipEntry
import java.util.zip.ZipFile

/**
 * Mở một file sách của app (.abook - ebook_reader/webui/bookfile.py): kiểm y như máy tính rồi giải nén vào
 * books/<mã sách>/, đúng chỗ sách tải qua Wi-Fi nằm - thư viện, trình phát, đọc theo dùng lại nguyên vẹn.
 *
 * File đến từ bất kỳ đâu (Zalo, Drive, email, thẻ nhớ), nên coi là dữ liệu của người lạ: chỉ nhận đúng các tên mục của
 * định dạng (không đường dẫn tuyệt đối, không ".."), số mục và cỡ có trần, định dạng mới hơn app thì nhắc cập nhật, và
 * mọi file phải đúng cỡ + mã băm ghi trong book.json TRƯỚC khi sách vào thư viện. Giải nén vào thư mục tạm rồi mới đổi
 * tên: hỏng giữa chừng không bao giờ để lại nửa cuốn. Nhập lại cùng cuốn thì thay bản cũ.
 */
object BookFileImport {
    const val MIMETYPE = "application/vnd.ngdtuanh.abook+zip"
    private const val FORMAT = "abook"
    private const val FORMAT_VERSION = 1
    private const val MAX_ENTRIES = 20_000
    private const val MAX_TOTAL_BYTES = 64L shl 30
    private const val MAX_JSON_BYTES = 32L shl 20
    private val CONTENT = Regex("""cast\.json|cover\.jpg|chapters/[0-9A-Za-z_.\-]+\.mp3|scripts/\d+\.json|samples/\d+\.wav""")
    private val IDENTITY = Regex("bk-[0-9a-f]{24}")
    private val DESCRIPTIONS = setOf("mimetype", "book.json", "manifest.json")

    /** Lý do không nhận file - câu chữ để người dùng đọc. */
    class Refused(message: String) : Exception(message)

    data class Imported(val id: String, val title: String)

    /** Chép từ content:// (trình quản lý file, Zalo, Drive...) vào bộ nhớ đệm rồi nhập. */
    fun import(context: Context, uri: Uri): Imported {
        Store.init(context)
        val copy = File(context.cacheDir, "import-${System.nanoTime()}.abook")
        try {
            val input = context.contentResolver.openInputStream(uri) ?: throw Refused("Không đọc được file.")
            input.use { source -> copy.outputStream().use { source.copyTo(it) } }
            return importFile(copy)
        } finally {
            copy.delete()
        }
    }

    fun importFile(file: File): Imported {
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
                if (name !in DESCRIPTIONS && !CONTENT.matches(name)) throw Refused("Gói có mục lạ: $name")
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
            val id = pack.optString("id")
            if (!IDENTITY.matches(id)) throw Refused("File sách có mã sách không hợp lệ.")
            val files = pack.optJSONObject("files") ?: throw Refused("Danh sách file trong sách không khớp nội dung gói.")
            val content = names - DESCRIPTIONS
            if (files.keys().asSequence().toSet() != content) {
                throw Refused("Danh sách file trong sách không khớp nội dung gói.")
            }
            val books = File(Store.root, "books").apply { mkdirs() }
            val staging = File(books, ".$id.${System.nanoTime()}.part")
            try {
                for (name in DESCRIPTIONS.filter { it != "mimetype" && it in names } + content.sorted()) {
                    val (size, sha256) = extract(zip, name, File(staging, name))
                    val expected = files.optJSONObject(name) ?: continue
                    if (size != expected.optLong("size", -1) || sha256 != expected.optString("sha256")) {
                        throw Refused("File sách bị hỏng hoặc bị sửa ($name). Hãy chép lại file từ nguồn.")
                    }
                }
                replace(books, staging, Store.bookDir(id), id)
            } finally {
                staging.deleteRecursively()
            }
            return Imported(id, book.optString("title"))
        }
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
