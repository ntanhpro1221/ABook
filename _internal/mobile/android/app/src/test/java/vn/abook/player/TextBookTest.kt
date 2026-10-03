package vn.abook.player

import java.io.ByteArrayOutputStream
import java.io.File
import java.nio.file.Files
import java.security.MessageDigest
import java.util.zip.ZipEntry
import java.util.zip.ZipFile
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Before
import org.junit.Test

/**
 * Sách CHỈ CÓ CHỮ (TextBook.kt = webui/textbook.py) trên bộ ví dụ DÙNG CHUNG với pytest (tests/text_book_fixtures.py,
 * tests/fixtures/text_books/): `book.json`, mã băm từng mục, chữ từng chương, tên thư mục (`contentKey`) và danh sách chương của bước xem
 * trước phải ra đúng như bản Python. Rồi cả đường nhập: file Python ghi mở được, nhập lại không nhân đôi, hai cuốn chung một chương vẫn là hai
 * cuốn, "Lưu thành .abook" ghi lại sách chỉ-chữ (phiên bản 5, kể cả khi có lớp sửa), và đọc được bằng bộ kiểm riêng.
 */
class TextBookTest {
    private lateinit var root: File
    private lateinit var work: File

    private val shared: File by lazy {
        val found = File("../../../tests/fixtures/text_books")
        if (!File(found, "cases.json").isFile) {
            fail("Không thấy bộ ví dụ dùng chung: ${found.absoluteFile} (sinh lại bằng runtime/.venv/Scripts/python.exe -m tests.text_book_fixtures)")
        }
        found.canonicalFile
    }

    @Before
    fun setUp() {
        root = Files.createTempDirectory("abook-textbook").toFile()
        work = Files.createTempDirectory("abook-textbook-work").toFile()
        BookEditsFixtures.useStoreRoot(root)
    }

    private fun sha256(bytes: ByteArray) = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }

    private fun cases(): List<JSONObject> {
        val all = (StrictJson.parse(File(shared, "cases.json").readText(Charsets.UTF_8)) as JSONObject).getJSONArray("cases")
        return (0 until all.length()).map { all.getJSONObject(it) }
    }

    private fun bookOf(input: JSONObject): BookImport.Book {
        val chapters = input.getJSONArray("chapters")
        return BookImport.Book(
            title = input.getString("title"),
            author = if (input.isNull("author")) null else input.getString("author"),
            language = if (input.isNull("language")) null else input.getString("language"),
            chapters = (0 until chapters.length()).map {
                val chapter = chapters.getJSONObject(it)
                BookImport.Chapter(chapter.getString("title"), chapter.getString("text"), chapter.optBoolean("short", false), chapter.optString("name", ""))
            }.toMutableList(),
            textHasTitle = input.getBoolean("textHasTitle"),
        )
    }

    private fun build(book: BookImport.Book, name: String, codec: CoverCodec? = null): File {
        val out = ByteArrayOutputStream()
        TextBook.build(book, out, codec)
        return File(work, name).apply { writeBytes(out.toByteArray()) }
    }

    private fun entries(file: File): Map<String, ByteArray> = ZipFile(file).use { zip ->
        zip.entries().toList().associate { it.name to zip.getInputStream(it).readBytes() }
    }

    @Test
    fun every_case_gives_the_book_json_the_hashes_and_the_texts_python_gives() {
        for (case in cases()) {
            val name = case.getString("name")
            val expected = case.getJSONObject("expected")
            val file = build(bookOf(case.getJSONObject("input")), "$name.abook")
            val parts = entries(file)
            val book = JSONObject(parts.getValue("book.json").toString(Charsets.UTF_8))
            val pack = book.getJSONObject("package")
            book.remove("package")
            assertTrue("$name: book.json ${StrictJson.dumps(book)}", StrictJson.equal(StrictJson.parse(expected.getJSONObject("book").toString()), book))
            assertEquals("$name: phiên bản", expected.getInt("version"), pack.getInt("version"))
            assertTrue("$name: cỡ + mã băm", StrictJson.equal(StrictJson.parse(expected.getJSONObject("files").toString()), pack.getJSONObject("files")))
            val texts = expected.getJSONObject("texts")
            for (entry in texts.keys()) assertEquals("$name: $entry", texts.getString(entry), parts.getValue(entry).toString(Charsets.UTF_8))
            assertEquals("$name: mục trong gói", texts.keys().asSequence().toSet() + setOf("mimetype", "book.json", "manifest.json"), parts.keys)
            val prints = BookFileImport.identityPrints(pack.getJSONObject("files").keys().asSequence().toList(), pack.getJSONObject("files"))
            assertEquals("$name: tên thư mục", expected.getString("contentKey"), BookFileImport.contentKey(prints))
            assertTrue("$name: xem trước ${StrictJson.dumps(TextBook.preview(bookOf(case.getJSONObject("input"))))}",
                StrictJson.equal(StrictJson.parse(expected.getJSONObject("preview").toString()), TextBook.preview(bookOf(case.getJSONObject("input")))))
        }
    }

    @Test
    fun the_file_python_wrote_opens_with_every_chapter_readable_and_no_audio() {
        val imported = BookFileImport.importFile(File(shared, "python_text.abook"))
        val book = Store.manifest(imported.id)!!
        assertEquals("Chuyến phà cuối ngày", imported.title)
        val chapters = book.getJSONArray("chapters")
        assertEquals(3, chapters.length())
        for (index in 0 until chapters.length()) {
            val chapter = chapters.getJSONObject(index)
            assertEquals("text", chapter.getString("state"))
            assertFalse(chapter.has("file"))
            assertFalse(chapter.getBoolean("available"))
            assertTrue(Store.file(imported.id, chapter.getString("text")).isFile)
        }
        assertTrue(Store.readText(imported.id, "texts/2.txt")!!.startsWith("Chương 2: Người khách lạ\n\nDịch: Nhóm Lục Bình"))
        assertEquals(imported.id, Store.books().single().getString("id"))
        val expected = cases().first { it.getString("name") == "epub3" }.getJSONObject("expected")
        assertEquals(expected.getString("contentKey"), imported.id)
    }

    @Test
    fun opening_the_same_file_again_gives_the_same_book_and_keeps_the_edits() {
        val first = BookFileImport.importFile(File(shared, "python_text.abook"))
        BookEdits.setTitle(Store.bookDir(first.id), "Tên tôi đặt")
        val again = BookFileImport.importFile(File(shared, "python_text.abook"))
        assertEquals(first.id, again.id)
        assertEquals(1, again.keptEdits)
        assertEquals(1, Store.books().size)
        assertEquals("Tên tôi đặt", Store.manifest(first.id)!!.getString("title"))
    }

    @Test
    fun two_books_sharing_one_chapter_text_stay_two_books() {
        val first = BookFileImport.importFile(File(shared, "python_text.abook"))
        val input = cases().first { it.getString("name") == "epub3" }.getJSONObject("input")
        val other = bookOf(input).apply {
            title = "Cuốn khác"
            chapters[1] = BookImport.Chapter("Chương mới", "Chữ hoàn toàn khác.")
        }
        val second = BookFileImport.importFile(build(other, "khac.abook"))
        assertNotEquals(first.id, second.id)
        assertEquals(2, Store.books().size)
        // Một cuốn bớt chương so với cuốn đã có cũng là cuốn khác (Python: tập chữ phải bằng nhau).
        val shorter = bookOf(input).apply { chapters.removeAt(2) }
        assertNotEquals(first.id, BookFileImport.importFile(build(shorter, "ngan.abook")).id)
        assertEquals(3, Store.books().size)
    }

    @Test
    fun a_text_book_saves_back_as_a_text_book_file_with_the_listeners_edits() {
        val imported = BookFileImport.importFile(File(shared, "python_text.abook"))
        val folder = Store.bookDir(imported.id)
        BookEdits.setTitle(folder, "Tên tôi đặt")
        val out = ByteArrayOutputStream()
        val written = BookDocumentWriter.write(folder, out)
        assertEquals(5, written.version)
        assertEquals(1, written.edits)
        val file = File(work, "luu.abook").apply { writeBytes(out.toByteArray()) }
        val parts = entries(file)
        assertTrue(parts.keys.containsAll(listOf("texts/1.txt", "texts/2.txt", "texts/3.txt", "edits.json")))
        val book = JSONObject(parts.getValue("book.json").toString(Charsets.UTF_8))
        assertEquals(5, book.getJSONObject("package").getInt("version"))
        assertEquals("Chuyến phà cuối ngày", book.getString("title"))
        assertEquals("Tên tôi đặt", JSONObject(parts.getValue("manifest.json").toString(Charsets.UTF_8)).getJSONObject("metadata").getString("title"))
        // Mở lại đúng file ấy: cùng cuốn, sửa đổi được hợp (máy này thắng), không nhân đôi.
        val again = BookFileImport.importFile(file)
        assertEquals(imported.id, again.id)
        assertEquals(1, Store.books().size)
        // Bản Python mở được file này: `-Dabook.writeFixtures=true` ghi thẳng vào fixtures/text_books/kotlin_text.abook.
        File("build").mkdirs()
        file.copyTo(File("build/kotlin_text.abook"), overwrite = true)
        if (System.getProperty("abook.writeFixtures") == "true") file.copyTo(File(shared, "kotlin_text.abook"), overwrite = true)
    }

    @Test
    fun a_text_book_saved_as_a_project_file_waits_for_its_workshop_and_opens_again() {
        val imported = BookFileImport.importFile(File(shared, "python_text.abook"))
        val out = ByteArrayOutputStream()
        val written = BookDocumentWriter.write(Store.bookDir(imported.id), out, asProject = true)
        assertEquals(5, written.version)
        val file = File(work, "du_an.abookproj").apply { writeBytes(out.toByteArray()) }
        val parts = entries(file)
        val project = JSONObject(parts.getValue("project.json").toString(Charsets.UTF_8))
        assertEquals("pending", project.getString("workshop"))
        assertTrue(project.getJSONObject("files").has("texts/1.txt"))
        Store.deleteBook(imported.id)
        val again = BookFileImport.importFile(file)
        assertEquals(imported.id, again.id)
        assertEquals("pending", ProjectDocument.info(Store.bookDir(again.id))!!.getString("workshop"))
        assertTrue(Store.file(again.id, "texts/3.txt").isFile)
    }

    @Test
    fun the_file_kotlin_writes_without_edits_is_a_plain_version_5_book() {
        val file = build(bookOf(cases().first { it.getString("name") == "epub3" }.getJSONObject("input")), "epub3.abook")
        ZipFile(file).use { zip ->
            val first = zip.entries().nextElement()
            assertEquals("mimetype", first.name)
            assertEquals(ZipEntry.STORED, first.method)
            assertEquals(listOf("mimetype", "book.json", "manifest.json", "texts/1.txt", "texts/2.txt", "texts/3.txt"), zip.entries().toList().map { it.name })
            val readium = JSONObject(zip.getInputStream(zip.getEntry("manifest.json")).readBytes().toString(Charsets.UTF_8))
            assertEquals(0, readium.getJSONArray("readingOrder").length())
        }
        val imported = BookFileImport.importFile(file)
        assertEquals(cases().first { it.getString("name") == "epub3" }.getJSONObject("expected").getString("contentKey"), imported.id)
    }

    @Test
    fun a_book_with_nothing_in_it_is_still_refused() {
        try {
            BookDocumentWriter.seal(JSONObject().put("title", "Rỗng"), emptyMap(), emptyMap(), BookEdits.empty(), 5, ByteArrayOutputStream())
            fail("lẽ ra bị từ chối")
        } catch (error: BookDocumentWriter.Refused) {
            assertTrue(error.message!!.contains("chưa có chương nào"))
        }
    }

    @Test
    fun chapter_texts_exist_only_from_version_5_and_must_exist_in_the_package() {
        val file = build(bookOf(cases().first { it.getString("name") == "epub3" }.getJSONObject("input")), "epub3.abook")
        fun rewrite(name: String, change: (JSONObject) -> Unit): File {
            val parts = entries(file).toMutableMap()
            val book = JSONObject(parts.getValue("book.json").toString(Charsets.UTF_8))
            change(book)
            parts["book.json"] = book.toString().toByteArray()
            val target = File(work, name)
            java.util.zip.ZipOutputStream(target.outputStream()).use { zip ->
                for ((entry, bytes) in parts) {
                    val item = ZipEntry(entry)
                    if (entry == "mimetype") {
                        item.method = ZipEntry.STORED
                        item.size = bytes.size.toLong()
                        item.compressedSize = bytes.size.toLong()
                        item.crc = java.util.zip.CRC32().also { it.update(bytes) }.value
                    }
                    zip.putNextEntry(item)
                    zip.write(bytes)
                    zip.closeEntry()
                }
            }
            return target
        }
        try {
            BookFileImport.importFile(rewrite("cu.abook") { it.getJSONObject("package").put("version", 4) })
            fail("phiên bản 4 không có texts/")
        } catch (error: BookFileImport.Refused) {
            assertTrue(error.message!!, error.message!!.startsWith("Gói có mục lạ"))
        }
        try {
            BookFileImport.importFile(rewrite("hong.abook") { it.getJSONArray("chapters").getJSONObject(0).put("text", "texts/99.txt") })
            fail("chương trỏ tới chữ không có")
        } catch (error: BookFileImport.Refused) {
            assertEquals("File sách thiếu chữ của một chương.", error.message)
        }
        assertTrue(Store.books().isEmpty())
    }

    /** Bộ chuẩn hoá ảnh giả cho test JVM (không có Bitmap): ảnh hợp lệ khi dài hơn 3 byte. */
    private class FakeCodec : CoverCodec {
        override fun normalize(raw: ByteArray): CoverCodec.Normalized {
            if (raw.size < 4) throw CoverCodec.CoverError("Không đọc được ảnh này")
            return CoverCodec.Normalized(byteArrayOf(0xFF.toByte(), 0xD8.toByte(), 0xFF.toByte(), 1), "#aa3333", 240, 320)
        }
    }

    @Test
    fun a_cover_is_stored_as_a_jpeg_with_its_colour_and_a_broken_one_is_dropped() {
        val input = cases().first { it.getString("name") == "epub3" }.getJSONObject("input")
        val with = bookOf(input).apply { cover = ByteArray(10) { 7 }; coverType = "image/png" }
        val parts = entries(build(with, "bia.abook", FakeCodec()))
        assertTrue(parts.containsKey("cover.jpg"))
        val shown = JSONObject(parts.getValue("book.json").toString(Charsets.UTF_8)).getJSONObject("cover")
        assertEquals("cover.jpg", shown.getString("file"))
        assertEquals(320, shown.getInt("height"))
        assertEquals("#aa3333", shown.getString("color"))
        val broken = bookOf(input).apply { cover = byteArrayOf(1, 2); coverType = "image/png" }
        val none = entries(build(broken, "hong.abook", FakeCodec()))
        assertFalse(none.containsKey("cover.jpg"))
        assertTrue(JSONObject(none.getValue("book.json").toString(Charsets.UTF_8)).isNull("cover"))
    }

    @Test
    fun the_text_of_a_chapter_is_the_source_file_studio_reads() {
        val input = cases().first { it.getString("name") == "epub3" }.getJSONObject("input")
        val epub = bookOf(input)
        assertEquals("${epub.chapters[1].title}\n\n${epub.chapters[1].text}\n", BookImport.chapterSource(epub, epub.chapters[1]))
        val folder = bookOf(cases().first { it.getString("name") == "txt" }.getJSONObject("input"))
        assertEquals(folder.chapters[0].text + "\n", BookImport.chapterSource(folder, folder.chapters[0]))
    }
}
