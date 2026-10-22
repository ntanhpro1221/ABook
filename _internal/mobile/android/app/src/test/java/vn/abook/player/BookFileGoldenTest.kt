package vn.abook.player

import java.io.File
import java.nio.file.Files
import java.security.MessageDigest
import java.util.zip.CRC32
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Before
import org.junit.Test

/**
 * Mở file sách .abook phải cho CÙNG phán quyết ở hai nền (soát a81 lỗi 13): bộ file vàng tests/fixtures/book_files/cases.json
 * cũng là bộ pytest dùng (tests/test_a81_open_import.py, `golden_cases`). Thư mục làm việc của Gradle là mobile/android/app.
 * Thêm: gói zip cụt nói "chép chưa xong", JSON lồng sâu không làm sập luồng nhập, bản chép tạm bị bỏ lại được dọn.
 */
class BookFileGoldenTest {
    private lateinit var work: File

    @Before
    fun setUp() {
        work = Files.createTempDirectory("abook-golden-src").toFile()
    }

    /** Store là object: mỗi file một thư mục gốc mới (như BookFileImportTest). */
    private fun freshStore() {
        val root = Files.createTempDirectory("abook-golden").toFile()
        Store::class.java.getDeclaredField("root").apply { isAccessible = true }.set(null, root)
        Store::class.java.getDeclaredField("recordsCache").apply { isAccessible = true }.set(null, null)
    }

    private fun sha256(bytes: ByteArray) = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }

    private fun cases(): List<JSONObject> {
        val found = File("../../../tests/fixtures/book_files/cases.json")
        if (!found.isFile) fail("Không thấy bộ file vàng dùng chung: ${found.absoluteFile} (chạy test từ mobile/android/app)")
        val list = JSONObject(found.readText(Charsets.UTF_8)).getJSONArray("cases")
        return (0 until list.length()).map { list.getJSONObject(it) }
    }

    /** Dựng file .abook từ một ca của bộ vàng - đúng như tests/a81_files.py `build_golden`. */
    private fun build(name: String, case: JSONObject): File {
        val entries = LinkedHashMap<String, ByteArray>()
        val given = case.getJSONObject("entries")
        for (key in given.keys()) {
            val value = given.get(key)
            entries[key] = if (value is JSONObject) ByteArray(value.getInt("zeros")) else (value as String).toByteArray(Charsets.UTF_8)
        }
        val omitted = case.optJSONArray("omitFromFiles")?.let { list -> (0 until list.length()).map { list.getString(it) } } ?: emptyList()
        val deflated = case.optJSONArray("deflate")?.let { list -> (0 until list.length()).map { list.getString(it) } } ?: emptyList()
        val files = JSONObject()
        for ((entry, bytes) in entries) if (entry !in omitted) files.put(entry, JSONObject().put("size", bytes.size).put("sha256", sha256(bytes)))
        val book = JSONObject(case.getJSONObject("book").toString())
        book.put("package", JSONObject().put("format", "abook").put("version", case.opt("version") ?: 1).put("files", files))
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
            if (case.optBoolean("manifest", true)) put("manifest.json", "{}".toByteArray(), stored = false)
            for ((entry, bytes) in entries) put(entry, bytes, stored = entry !in deflated)
        }
        return target
    }

    @Test
    fun the_shared_golden_files_get_the_same_verdict_as_on_the_computer() {
        val wrong = ArrayList<String>()
        for (case in cases()) {
            freshStore()
            val verdict = try {
                BookFileImport.importFile(build("case.abook", case))
                "ok"
            } catch (error: BookFileImport.Refused) {
                "refused"
            }
            if (verdict != case.getString("expect")) wrong.add("${case.getString("name")}: máy tính ${case.getString("expect")}, điện thoại $verdict")
        }
        assertTrue("Hai nền lệch nhau ở:\n" + wrong.joinToString("\n"), wrong.isEmpty())
    }

    @Test
    fun a_file_cut_short_is_called_unfinished_not_foreign() {
        freshStore()
        val whole = build("whole.abook", cases().first { it.getString("expect") == "ok" })
        val cut = File(work, "cut.abook").apply { writeBytes(whole.readBytes().copyOf((whole.length() / 2).toInt())) }
        try {
            BookFileImport.importFile(cut)
            fail("lẽ ra bị từ chối")
        } catch (error: BookFileImport.Refused) {
            assertEquals("File sách bị hỏng hoặc chép chưa xong - chép lại từ nguồn.", error.message)
        }
        val foreign = File(work, "text.abook").apply { writeText("không phải zip") }
        try {
            BookFileImport.importFile(foreign)
            fail("lẽ ra bị từ chối")
        } catch (error: BookFileImport.Refused) {
            assertEquals("Đây không phải file sách của app.", error.message)
        }
    }

    @Test
    fun a_deeply_nested_book_json_is_refused_instead_of_overflowing_the_stack() {
        freshStore()
        val deep = "{\"a\":".repeat(100_000).toByteArray()
        val target = File(work, "deep.abook")
        ZipOutputStream(target.outputStream()).use { zip ->
            val mime = BookFileImport.MIMETYPE.toByteArray()
            zip.putNextEntry(ZipEntry("mimetype").apply { method = ZipEntry.STORED; size = mime.size.toLong(); compressedSize = size; crc = CRC32().also { it.update(mime) }.value })
            zip.write(mime)
            zip.closeEntry()
            zip.putNextEntry(ZipEntry("book.json"))
            zip.write(deep)
            zip.closeEntry()
        }
        try {
            BookFileImport.importFile(target)
            fail("lẽ ra bị từ chối")
        } catch (error: BookFileImport.Refused) {
            assertEquals("book.json hỏng.", error.message)
        }
    }
}
