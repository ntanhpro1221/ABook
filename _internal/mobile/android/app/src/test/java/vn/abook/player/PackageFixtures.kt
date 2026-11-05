package vn.abook.player

import org.json.JSONObject
import java.io.File
import java.security.MessageDigest
import java.util.zip.CRC32
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

/** Dựng file .abook nhỏ cho test (dùng chung BookFileImportTest và các test thay file / làm mới trình phát). */
object PackageFixtures {
    fun sha256(bytes: ByteArray) = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }

    /** Một chương của book.json: có file audio `file`, chữ `scripts/<id>.json`, độ dài `duration` giây. */
    fun chapter(id: Int, part: Int, file: String, duration: Double = 60.0): JSONObject = JSONObject().put("id", id).put("part", part)
        .put("title", "Chương $id").put("fullTitle", "Chương $id").put("available", true).put("file", file)
        .put("script", "scripts/$id.json").put("duration", duration)

    /** Ghi `work/<name>` là file sách phiên bản `version` chứa `content` (đường dẫn trong gói -> byte) với mô tả `book`; `at` = giờ đóng gói (package.createdAt). */
    fun abook(work: File, name: String, version: Int, content: Map<String, ByteArray>, book: JSONObject = JSONObject(), at: String? = null): File {
        val files = JSONObject()
        for ((entry, bytes) in content) files.put(entry, JSONObject().put("size", bytes.size).put("sha256", sha256(bytes)))
        book.put("package", JSONObject().put("format", "abook").put("version", version).put("files", files))
        at?.let { book.getJSONObject("package").put("createdAt", it) }
        val target = File(work, name)
        ZipOutputStream(target.outputStream()).use { zip ->
            fun put(entry: String, bytes: ByteArray, stored: Boolean) {
                val item = ZipEntry(entry)
                if (stored) {
                    item.method = ZipEntry.STORED
                    item.size = bytes.size.toLong()
                    item.compressedSize = bytes.size.toLong()
                    item.crc = CRC32().also { it.update(bytes) }.value
                }
                zip.putNextEntry(item)
                zip.write(bytes)
                zip.closeEntry()
            }
            put("mimetype", BookFileImport.MIMETYPE.toByteArray(), stored = true)
            put("book.json", book.toString().toByteArray(), stored = false)
            put("manifest.json", "{}".toByteArray(), stored = false)
            for ((entry, bytes) in content) put(entry, bytes, stored = true)
        }
        return target
    }
}
