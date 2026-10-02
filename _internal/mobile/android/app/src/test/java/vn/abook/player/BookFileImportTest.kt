package vn.abook.player

import java.io.File
import java.nio.file.Files
import java.security.MessageDigest
import java.util.zip.CRC32
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Before
import org.junit.Test

/**
 * Mở file sách .abook (BookFileImport): phiên bản 3 là cả bộ nhiều phần trong một file - audio ở chapters/<phần>/<tên>.mp3,
 * mã chương chung của bộ. Phiên bản mới hơn app thì từ chối kèm lời nhắc cập nhật, ổ đầy thì từ chối trước khi chép.
 */
class BookFileImportTest {
    private lateinit var root: File
    private lateinit var work: File

    @Before
    fun setUp() {
        root = Files.createTempDirectory("abook-import").toFile()
        work = Files.createTempDirectory("abook-import-src").toFile()
        // Store là object: đặt thư mục và bỏ bộ đệm hồ sơ bằng phản chiếu cho từng test JVM (như StoreRekeyTest).
        Store::class.java.getDeclaredField("root").apply { isAccessible = true }.set(null, root)
        Store::class.java.getDeclaredField("recordsCache").apply { isAccessible = true }.set(null, null)
    }

    private fun sha256(bytes: ByteArray) =
        MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }

    /** Dựng một file .abook: `content` là {tên mục -> byte}; `book` là phần còn lại của book.json. */
    private fun abook(name: String, version: Int, content: Map<String, ByteArray>, book: JSONObject = JSONObject()): File {
        val files = JSONObject()
        for ((entry, bytes) in content) files.put(entry, JSONObject().put("size", bytes.size).put("sha256", sha256(bytes)))
        book.put("package", JSONObject().put("format", "abook").put("version", version).put("files", files))
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

    private fun chapter(id: Int, part: Int, file: String) = JSONObject().put("id", id).put("part", part)
        .put("title", "Chương $id").put("fullTitle", "Chương $id").put("available", true).put("file", file)
        .put("script", "scripts/$id.json").put("duration", 60.0)

    private fun seriesFile(name: String = "bo.abook", version: Int = 3): File {
        val content = mapOf(
            "cast.json" to "{}".toByteArray(),
            "chapters/1/00001.mp3" to "ID3-phan-mot".toByteArray(),
            "chapters/2/00001.mp3" to "ID3-phan-hai".toByteArray(), // cùng tên file ở hai phần
            "scripts/100001.json" to "{}".toByteArray(),
            "scripts/200001.json" to "{}".toByteArray(),
        )
        val book = JSONObject().put("title", "Truyện X").put("chaptersAvailable", 2).put("chaptersTotal", 2)
            .put("chapters", JSONArray().put(chapter(100001, 1, "chapters/1/00001.mp3")).put(chapter(200001, 2, "chapters/2/00001.mp3")))
            .put("parts", JSONArray()
                .put(JSONObject().put("part", 1).put("title", "Truyện X · Phần 1").put("chapters", JSONArray(listOf(100001, 100001))))
                .put(JSONObject().put("part", 2).put("title", "Truyện X · Phần 2").put("chapters", JSONArray(listOf(200001, 200001)))))
        return abook(name, version, content, book)
    }

    private fun refusal(block: () -> Unit): String {
        try {
            block()
        } catch (error: BookFileImport.Refused) {
            return error.message.orEmpty()
        }
        fail("lẽ ra bị từ chối")
        return ""
    }

    @Test
    fun a_whole_series_file_is_extracted_with_its_part_folders() {
        val imported = BookFileImport.importFile(seriesFile())

        assertEquals("Truyện X", imported.title)
        assertTrue(imported.id.startsWith("f-"))
        val dir = Store.bookDir(imported.id)
        assertEquals("ID3-phan-mot", File(dir, "chapters/1/00001.mp3").readText())
        assertEquals("ID3-phan-hai", File(dir, "chapters/2/00001.mp3").readText())
        val book = Store.manifest(imported.id)!!
        assertEquals(imported.id, book.getString("id"))
        assertEquals(2, book.getJSONArray("parts").length())
        assertEquals(200001, book.getJSONArray("chapters").getJSONObject(1).getInt("id"))
        assertEquals("chapters/2/00001.mp3", LibraryTree.chapters(book)[1].file)
        assertEquals("sách đã nhập được ghi vào sổ", setOf(imported.id), Store.importedBooks().toSet())
        assertTrue(Store.file(imported.id, "chapters/2/00001.mp3").isFile)
    }

    @Test
    fun opening_the_same_series_file_again_goes_to_the_same_book() {
        val first = BookFileImport.importFile(seriesFile())
        val again = BookFileImport.importFile(seriesFile("lai.abook"))
        assertEquals(first.id, again.id)
        assertEquals(1, File(root, "books").listFiles()!!.count { it.isDirectory && !it.name.startsWith(".") })
    }

    @Test
    fun a_book_downloaded_with_flat_names_is_the_same_book_as_its_part_in_a_series_file() {
        // Cuốn đã có trên máy (tải qua Wi-Fi) giữ audio ở chapters/<tên>.mp3; file cả bộ đặt cùng audio ở chapters/1/<tên>.mp3.
        val flat = "ID3-phan-mot".toByteArray()
        val existing = "0123456789abcdef01234567"
        File(root, "books/$existing/chapters").mkdirs()
        File(root, "books/$existing/chapters/00001.mp3").writeBytes(flat)
        File(root, "books/$existing/book.json").writeText(JSONObject().put("id", existing).put("title", "Truyện X")
            .put("chaptersAvailable", 1)
            .put("chapters", JSONArray().put(JSONObject().put("id", 1).put("available", true).put("file", "chapters/00001.mp3")))
            .toString())

        val imported = BookFileImport.importFile(seriesFile())

        assertEquals("cùng một cuốn: nhập vào đúng thư mục đã có, giữ mã của nó", existing, imported.id)
        assertTrue(File(root, "books/$existing/chapters/2/00001.mp3").isFile)
    }

    @Test
    fun a_newer_format_asks_to_update_the_app_and_copies_nothing() {
        val message = refusal { BookFileImport.importFile(seriesFile("moi.abook", version = 4)) }
        assertTrue(message, "Hãy cập nhật app" in message)
        assertFalse(File(root, "books").exists() && File(root, "books").listFiles()!!.isNotEmpty())
    }

    @Test
    fun part_folders_belong_to_version_3_only() {
        val message = refusal { BookFileImport.importFile(seriesFile("cu.abook", version = 2)) }
        assertTrue(message, "mục lạ" in message)
    }

    @Test
    fun names_outside_the_layout_are_refused() {
        for (name in listOf("chapters/a/x.mp3", "chapters/1/2/x.mp3", "chapters/../x.mp3")) {
            val file = abook("la.abook", 3, mapOf("chapters/1/00001.mp3" to byteArrayOf(1), name to byteArrayOf(2)),
                JSONObject().put("chapters", JSONArray()))
            assertTrue(name, "mục lạ" in refusal { BookFileImport.importFile(file) })
        }
    }

    @Test
    fun a_damaged_entry_is_refused_and_leaves_no_half_book() {
        val file = seriesFile()
        // Đổi byte một audio trong gói: cỡ giữ nguyên, mã băm không còn khớp.
        val broken = File(work, "hong.abook")
        java.util.zip.ZipFile(file).use { zip ->
            ZipOutputStream(broken.outputStream()).use { out ->
                for (entry in zip.entries().toList()) {
                    var bytes = zip.getInputStream(entry).use { it.readBytes() }
                    if (entry.name == "chapters/2/00001.mp3") bytes = "ID3-phan-xxx".toByteArray()
                    val item = ZipEntry(entry.name)
                    if (entry.method == ZipEntry.STORED) {
                        item.method = ZipEntry.STORED
                        item.size = bytes.size.toLong()
                        item.compressedSize = bytes.size.toLong()
                        item.crc = CRC32().also { it.update(bytes) }.value
                    }
                    out.putNextEntry(item)
                    out.write(bytes)
                    out.closeEntry()
                }
            }
        }
        val message = refusal { BookFileImport.importFile(broken) }
        assertTrue(message, "hỏng" in message)
        assertTrue(File(root, "books").listFiles().orEmpty().none { it.isDirectory })
    }

    @Test
    fun a_book_that_does_not_fit_is_refused_before_anything_is_copied() {
        val message = refusal { BookFileImport.importFile(seriesFile()) { 1_000L } }
        assertTrue(message, "không đủ chỗ" in message && "cần khoảng" in message && "còn" in message)
        assertTrue("chưa chép gì vào thư viện", File(root, "books").listFiles().orEmpty().isEmpty())
    }
}
