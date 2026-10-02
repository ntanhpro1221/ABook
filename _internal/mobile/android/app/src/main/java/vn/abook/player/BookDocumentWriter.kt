package vn.abook.player

import org.json.JSONObject
import java.io.File
import java.io.FilterOutputStream
import java.io.OutputStream
import java.security.MessageDigest
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone
import java.util.zip.CRC32
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

/**
 * Đóng một cuốn đã nhập thành MỘT file `.abook` - `bookfile.repack` + `_seal` của máy tính (abook/webui/bookfile.py) bằng
 * ZipOutputStream. Lớp sách y nguyên (file nào đã biết cỡ + mã băm thì không băm lại - audio hàng trăm MB), cộng lớp sửa của
 * người nghe nếu có: khi ấy phiên bản 4 (`edits.json`, `edits/cover.jpg`); không thì phiên bản thấp nhất đủ chứa sách (1 / 2 /
 * 3). `manifest.json` (Readium) dựng lại từ sách ĐÃ SỬA, nên app đọc sách nói khác thấy đúng tên người nghe đặt.
 *
 * Gói: `mimetype` đầu tiên và KHÔNG nén; `.mp3` / `.wav` / `.jpg` không nén (phát và tua thẳng trong gói), cỡ + CRC ghi trước
 * vì ZipOutputStream không quay lại sửa mục đã ghi. Thứ tự các mục như `_order` bên Python.
 */
object BookDocumentWriter {
    const val EXTENSION = ".abook"
    private const val PRODUCER = "ABook"
    private const val FORMAT = "abook"
    private val STORED = listOf(".mp3", ".jpg", ".wav", ".m4a", ".ogg", ".opus", ".flac")
    private val RANK = listOf("edits", "cover.jpg", "cast.json", "scripts/", "samples/", "chapters/", "music/")
    private val PART_AUDIO = Regex("chapters/[0-9]+/.+")

    /** Không đóng được - câu chữ để người dùng đọc. */
    class Refused(message: String) : Exception(message)

    /** Kết quả: cỡ file, số thay đổi của người nghe trong đó, phiên bản định dạng. */
    class Written(val size: Long, val edits: Int, val version: Int)

    /** Tên file từ tên sách, giữ tiếng Việt, bỏ ký tự Windows cấm (`bookfile.default_name`). */
    fun defaultName(title: String): String {
        val name = title.replace(Regex("""[\\/:*?"<>|\u0000-\u001f]+"""), " ").trim(' ', '.').ifEmpty { "Sách nói" }
        val words = name.split(Regex("[\\p{Z}\\s]+")).filter { it.isNotEmpty() }.joinToString(" ")
        return BookEdits.cut(words, 150) + EXTENSION
    }

    fun write(bookDir: File, out: OutputStream): Written {
        val book = try {
            JSONObject(File(bookDir, "book.json").readText())
        } catch (error: Exception) {
            throw Refused("Không đọc được thư mục sách này.")
        }
        val listed = book.optJSONObject("package")?.optJSONObject("files") ?: throw Refused("Đây không phải một cuốn đã nhập từ file sách.")
        val files = HashMap<String, Any>() // tên mục -> File hay ByteArray
        val known = HashMap<String, JSONObject>()
        for (name in listed.keys().asSequence().toList()) {
            if (name == BookEdits.EDITS_FILE || name == BookEdits.EDITS_COVER) continue // lớp sửa suy lại từ phần sửa hiện có
            val source = runCatching { Store.contained(bookDir, name) }.getOrNull()?.takeIf { it.isFile }
                ?: throw Refused("Thư mục sách thiếu file $name.")
            files[name] = source
            listed.optJSONObject(name)?.let { known[name] = it }
        }
        book.remove("package")
        book.remove("id") // mã sách là của app này, không đi theo file (sách không mang mã nào)
        val edits = BookEdits.load(bookDir)
        val changes = BookEdits.count(edits)
        if (changes > 0) {
            files[BookEdits.EDITS_FILE] = BookEdits.dump(edits)
            if (edits.opt("cover") is JSONObject) {
                files[BookEdits.EDITS_COVER] = File(bookDir, BookEdits.EDITS_COVER).takeIf { it.isFile }
                    ?: throw Refused("Thiếu ảnh bìa trong phần sửa của sách.")
            }
            // Bài nhạc của người nghe đã ghim: đi theo file như bài của người làm sách (music/<sha1>.<đuôi>).
            for (name in BookEdits.pinnedFiles(edits)) {
                if (name in files) continue
                files[name] = runCatching { Store.contained(bookDir, name) }.getOrNull()?.takeIf { it.isFile }
                    ?: throw Refused("Thiếu file bài nhạc người nghe đã chọn trong thư mục sách.")
            }
        }
        val version = when {
            changes > 0 -> 4
            files.keys.any { PART_AUDIO.matches(it) } -> 3
            book.has("music") -> 2
            else -> 1
        }
        if (files.keys.none { it.startsWith("chapters/") }) throw Refused("Sách chưa có chương nào nghe được để xuất.")
        val sorted = files.keys.sorted()
        val described = LinkedHashMap<String, Any>()
        for (name in sorted) described[name] = describe(name, files.getValue(name), known[name])
        val unknown = sorted.filter { !BookFileImport.contentPattern(version).matches(it) }
        if (unknown.isNotEmpty()) throw Refused("Không gói được các file có tên ngoài định dạng: ${unknown.take(3)}")
        val format = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'+00:00'", Locale.ROOT).apply { timeZone = TimeZone.getTimeZone("UTC") }
        val packageInfo = LinkedHashMap<String, Any>()
        packageInfo["format"] = FORMAT
        packageInfo["version"] = version
        packageInfo["createdAt"] = format.format(Date())
        packageInfo["producer"] = PRODUCER
        packageInfo["files"] = described
        book.put("package", packageInfo as Any)

        val counting = Counting(out)
        ZipOutputStream(counting).use { zip ->
            put(zip, "mimetype", BookFileImport.MIMETYPE.toByteArray(Charsets.US_ASCII), stored = true)
            put(zip, "book.json", StrictJson.dumps(book, 1).toByteArray(Charsets.UTF_8), stored = false)
            put(zip, "manifest.json", StrictJson.dumps(readium(BookEdits.applyManifest(book, edits), packageInfo["createdAt"] as String), 1).toByteArray(Charsets.UTF_8), stored = false)
            for (name in files.keys.sortedWith(compareBy({ rank(it) }, { it }))) {
                val stored = STORED.any { name.lowercase(Locale.ROOT).endsWith(it) }
                when (val source = files.getValue(name)) {
                    is File -> putFile(zip, name, source, stored)
                    else -> put(zip, name, source as ByteArray, stored)
                }
            }
        }
        return Written(counting.written, changes, version)
    }

    private fun rank(name: String) = RANK.indexOfFirst { name.startsWith(it) }

    private fun describe(name: String, source: Any, known: JSONObject?): JSONObject {
        if (source is File && known != null && known.optLong("size", -1) == source.length() && known.opt("sha256") is String) {
            return JSONObject().put("size", source.length()).put("sha256", known.getString("sha256"))
        }
        val digest = MessageDigest.getInstance("SHA-256")
        var size = 0L
        if (source is File) {
            source.inputStream().use { input ->
                val buffer = ByteArray(1 shl 16)
                while (true) {
                    val read = input.read(buffer)
                    if (read < 0) break
                    digest.update(buffer, 0, read)
                    size += read
                }
            }
        } else {
            digest.update(source as ByteArray)
            size = source.size.toLong()
        }
        return JSONObject().put("size", size).put("sha256", digest.digest().joinToString("") { "%02x".format(it) })
    }

    private fun put(zip: ZipOutputStream, name: String, bytes: ByteArray, stored: Boolean) {
        val entry = ZipEntry(name)
        if (stored) {
            entry.method = ZipEntry.STORED
            entry.size = bytes.size.toLong()
            entry.compressedSize = bytes.size.toLong()
            entry.crc = CRC32().also { it.update(bytes) }.value
        }
        zip.putNextEntry(entry)
        zip.write(bytes)
        zip.closeEntry()
    }

    private fun putFile(zip: ZipOutputStream, name: String, file: File, stored: Boolean) {
        val entry = ZipEntry(name)
        if (stored) {
            val crc = CRC32()
            file.inputStream().use { input ->
                val buffer = ByteArray(1 shl 16)
                while (true) {
                    val read = input.read(buffer)
                    if (read < 0) break
                    crc.update(buffer, 0, read)
                }
            }
            entry.method = ZipEntry.STORED
            entry.size = file.length()
            entry.compressedSize = file.length()
            entry.crc = crc.value
        }
        zip.putNextEntry(entry)
        file.inputStream().use { it.copyTo(zip, 1 shl 16) }
        zip.closeEntry()
    }

    /** Cùng cuốn theo Readium Web Publication Manifest, hồ sơ Audiobook - chỉ phần audio có thật trong gói (`bookfile._readium`). */
    private fun readium(book: JSONObject, createdAt: String): Map<String, Any?> {
        val order = ArrayList<Map<String, Any?>>()
        val chapters = book.optJSONArray("chapters")
        for (index in 0 until (chapters?.length() ?: 0)) {
            val chapter = chapters?.optJSONObject(index) ?: continue
            if (!BookEdits.truthy(chapter.opt("file"))) continue
            val item = LinkedHashMap<String, Any?>()
            item["href"] = chapter.opt("file")
            item["type"] = "audio/mpeg"
            item["title"] = listOf(chapter.opt("fullTitle"), chapter.opt("title")).firstOrNull { BookEdits.truthy(it) } ?: ""
            if (BookEdits.truthy(chapter.opt("duration"))) item["duration"] = chapter.opt("duration")
            order.add(item)
        }
        val seconds = order.sumOf { ((it["duration"] as? Number)?.toDouble()) ?: 0.0 }
        val metadata = LinkedHashMap<String, Any?>()
        metadata["@type"] = "http://schema.org/Audiobook"
        metadata["conformsTo"] = "https://readium.org/webpub-manifest/profiles/audiobook"
        metadata["title"] = book.opt("title")
        metadata["language"] = "vi"
        metadata["readBy"] = if (BookEdits.truthy(book.opt("narrator"))) book.opt("narrator") else ""
        metadata["duration"] = Math.round(seconds * 1000) / 1000.0
        metadata["modified"] = createdAt
        val manifest = LinkedHashMap<String, Any?>()
        manifest["@context"] = "https://readium.org/webpub-manifest/context.jsonld"
        manifest["metadata"] = metadata
        manifest["readingOrder"] = order
        manifest["toc"] = order.map { linkedMapOf("href" to it["href"], "title" to it["title"]) }
        if (BookEdits.truthy(book.opt("cover"))) {
            manifest["resources"] = listOf(linkedMapOf("href" to "cover.jpg", "type" to "image/jpeg", "rel" to "cover"))
        }
        return manifest
    }

    /** Đếm byte đã ghi - kích cỡ file cho giao diện, khi nơi nhận (SAF) không cho hỏi cỡ. */
    private class Counting(out: OutputStream) : FilterOutputStream(out) {
        var written = 0L

        override fun write(byte: Int) {
            out.write(byte)
            written++
        }

        override fun write(bytes: ByteArray, offset: Int, length: Int) {
            out.write(bytes, offset, length)
            written += length
        }
    }
}
