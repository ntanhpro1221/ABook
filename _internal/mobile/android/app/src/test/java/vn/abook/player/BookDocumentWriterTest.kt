package vn.abook.player

import java.io.File
import java.security.MessageDigest
import java.util.zip.ZipEntry
import java.util.zip.ZipFile
import org.json.JSONObject
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Before
import org.junit.Test

/**
 * Lưu thành file .abook (BookDocumentWriter = bookfile.repack + _seal): file ghi ra phải qua `bookfile.BookFile(...).verify()` của
 * Python (từng mục đúng cỡ + mã băm, `mimetype` đầu tiên và không nén, nhạc/ảnh không nén) - ở đây kiểm bằng bộ kiểm riêng - và
 * mở lại được bằng BookFileImport với phần sửa còn nguyên. File bản Python ghi (written/python_v4.abook) cũng phải mở được.
 */
class BookDocumentWriterTest {
    private lateinit var work: File

    @Before
    fun setUp() {
        work = BookEditsFixtures.tempDir("abook-writer")
        BookEditsFixtures.useStoreRoot(BookEditsFixtures.tempDir("abook-writer-root"))
    }

    private fun sha256(bytes: ByteArray) = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }

    /** Một cuốn đã nhập (bản sao `base/`) mang phần sửa của ca `edits/<name>.json` (và bìa sửa của nó). */
    private fun bookWith(name: String?): File {
        val dir = BookEditsFixtures.copyBase(File(work, "book-${name ?: "none"}"))
        if (name != null) {
            File(dir, "edits.json").writeBytes(BookEditsFixtures.bytes("edits/$name.json"))
            val cover = BookEditsFixtures.file("edits/$name.cover.jpg")
            if (cover.isFile) File(dir, "edits/cover.jpg").apply { parentFile?.mkdirs() }.writeBytes(cover.readBytes())
            // bài nhạc người nghe đã ghim (ca `music_pin*`): file của nó nằm trong thư mục sách như khi ghim ở máy
            for (pinned in BookEdits.pinnedFiles(BookEdits.parse(BookEditsFixtures.bytes("edits/$name.json")))) {
                File(dir, pinned).apply { parentFile?.mkdirs() }.writeBytes(BookEditsFixtures.bytes("track/tone.wav"))
            }
        }
        return dir
    }

    private fun write(dir: File, name: String): Pair<File, BookDocumentWriter.Written> {
        val target = File(work, name)
        val written = target.outputStream().use { BookDocumentWriter.write(dir, it) }
        return target to written
    }

    private fun rank(name: String) = listOf("edits", "cover.jpg", "cast.json", "scripts/", "samples/", "chapters/", "music/").indexOfFirst { name.startsWith(it) }

    /** Kiểm như `BookFile.verify()` + hình dạng gói; trả book.json trong file. */
    private fun verify(file: File): JSONObject {
        ZipFile(file).use { zip ->
            val entries = zip.entries().toList()
            assertEquals("mimetype là mục đầu tiên", "mimetype", entries[0].name)
            assertEquals("mimetype không nén", ZipEntry.STORED, entries[0].method)
            assertEquals(BookFileImport.MIMETYPE, zip.getInputStream(entries[0]).readBytes().toString(Charsets.US_ASCII))
            assertEquals("book.json", entries[1].name)
            assertEquals("manifest.json", entries[2].name)
            assertEquals("không có mục trùng", entries.size, entries.map { it.name }.toSet().size)
            val book = JSONObject(zip.getInputStream(zip.getEntry("book.json")).readBytes().toString(Charsets.UTF_8))
            val files = book.getJSONObject("package").getJSONObject("files")
            val rest = entries.drop(3)
            assertEquals("danh sách file khớp nội dung gói", rest.map { it.name }.toSet(), files.keys().asSequence().toSet())
            for (entry in rest) {
                val bytes = zip.getInputStream(entry).readBytes()
                assertEquals("${entry.name}: cỡ", files.getJSONObject(entry.name).getLong("size"), bytes.size.toLong())
                assertEquals("${entry.name}: mã băm", files.getJSONObject(entry.name).getString("sha256"), sha256(bytes))
                val stored = listOf(".mp3", ".wav", ".jpg").any { entry.name.endsWith(it) }
                assertEquals("${entry.name}: ${if (stored) "không nén" else "nén"}", if (stored) ZipEntry.STORED else ZipEntry.DEFLATED, entry.method)
            }
            assertEquals("thứ tự mục như bookfile._order", rest.map { it.name }.sortedWith(compareBy({ rank(it) }, { it })), rest.map { it.name })
            assertEquals("abook", book.getJSONObject("package").getString("format"))
            assertEquals("ABook", book.getJSONObject("package").getString("producer"))
            assertTrue(book.getJSONObject("package").getString("createdAt").matches(Regex("""\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\+00:00""")))
            assertFalse("sách không mang mã nào", book.has("id"))
            return book
        }
    }

    @Test
    fun a_book_without_edits_is_written_at_the_lowest_version_that_fits() {
        val (file, written) = write(bookWith(null), "plain.abook")
        val book = verify(file)
        assertEquals(2, book.getJSONObject("package").getInt("version")) // có nhạc nền
        assertEquals(2, written.version)
        assertEquals(0, written.edits)
        assertEquals(file.length(), written.size)
        ZipFile(file).use { zip ->
            assertNull(zip.getEntry("edits.json"))
            assertNull(zip.getEntry("edits/cover.jpg"))
        }
        // lớp sách y nguyên
        assertEquals(BookEditsFixtures.obj("base/book.json").getString("title"), book.getString("title"))
    }

    @Test
    fun every_edits_case_is_written_as_version_4_and_opens_again_with_its_edits() {
        for (name in BookEditsFixtures.cases("edits")) {
            val edits = BookEdits.parse(BookEditsFixtures.bytes("edits/$name.json"))
            val (file, written) = write(bookWith(name), "$name.abook")
            val book = verify(file)
            assertEquals("$name: phiên bản", 4, book.getJSONObject("package").getInt("version"))
            assertEquals(BookEdits.count(edits), written.edits)
            ZipFile(file).use { zip ->
                assertArrayEquals("$name: edits.json là phần sửa chuẩn", BookEdits.dump(edits), zip.getInputStream(zip.getEntry("edits.json")).readBytes())
                val coverEntry = zip.getEntry("edits/cover.jpg")
                assertEquals("$name: bìa sửa đi đôi với phần sửa", edits.opt("cover") is JSONObject, coverEntry != null)
                if (coverEntry != null) assertArrayEquals(BookEditsFixtures.bytes("edits/$name.cover.jpg"), zip.getInputStream(coverEntry).readBytes())
                // manifest.json (Readium) mang tên người nghe đặt
                val readium = JSONObject(zip.getInputStream(zip.getEntry("manifest.json")).readBytes().toString(Charsets.UTF_8))
                assertEquals("$name: tên trong manifest.json", BookEditsFixtures.obj("expected/$name.json").getJSONObject("manifest").getString("title"),
                    readium.getJSONObject("metadata").getString("title"))
                assertEquals(1, readium.getJSONArray("readingOrder").length())
            }
            // mở lại bằng chính bộ nhập của điện thoại
            val library = BookEditsFixtures.tempDir("abook-writer-lib")
            BookEditsFixtures.useStoreRoot(library)
            val imported = BookFileImport.importFile(file)
            assertTrue("$name: phần sửa còn nguyên", StrictJson.equal(edits, BookEdits.load(Store.bookDir(imported.id))))
            val shown = (BookEdits.deepCopy(Store.manifest(imported.id)!!) as JSONObject).also { listOf("id", "edits", "wishes", "capabilities", "package").forEach(it::remove) }
            assertTrue("$name: sách người nghe thấy khớp bản Python", StrictJson.equal(BookEditsFixtures.obj("expected/$name.json").getJSONObject("manifest"), shown))
            assertEquals(imported.title, shown.getString("title"))
        }
    }

    @Test
    fun audio_and_other_known_files_are_not_hashed_again() {
        val dir = bookWith(null)
        val book = JSONObject(File(dir, "book.json").readText())
        val files = book.getJSONObject("package").getJSONObject("files")
        files.getJSONObject("chapters/00001_645.mp3").put("sha256", "f".repeat(64)) // cố tình sai, cùng cỡ: nếu băm lại thì lộ
        File(dir, "book.json").writeText(book.toString())
        val (file, _) = write(dir, "known.abook")
        ZipFile(file).use { zip ->
            val written = JSONObject(zip.getInputStream(zip.getEntry("book.json")).readBytes().toString(Charsets.UTF_8))
            assertEquals("f".repeat(64), written.getJSONObject("package").getJSONObject("files").getJSONObject("chapters/00001_645.mp3").getString("sha256"))
            // file cỡ khác với lúc ghi sổ thì băm lại
            assertEquals(BookEditsFixtures.bytes("base/cast.json").size.toLong(), written.getJSONObject("package").getJSONObject("files").getJSONObject("cast.json").getLong("size"))
        }
        val sizeChanged = JSONObject(File(dir, "book.json").readText())
        sizeChanged.getJSONObject("package").getJSONObject("files").getJSONObject("cast.json").put("size", 1).put("sha256", "e".repeat(64))
        File(dir, "book.json").writeText(sizeChanged.toString())
        val (again, _) = write(dir, "rehashed.abook")
        ZipFile(again).use { zip ->
            val written = JSONObject(zip.getInputStream(zip.getEntry("book.json")).readBytes().toString(Charsets.UTF_8))
            assertEquals(sha256(BookEditsFixtures.bytes("base/cast.json")), written.getJSONObject("package").getJSONObject("files").getJSONObject("cast.json").getString("sha256"))
        }
    }

    @Test
    fun a_series_book_is_version_3_and_a_plain_one_is_version_1() {
        fun mini(name: String, audio: String, music: Boolean): File {
            val dir = File(work, name)
            val bytes = "ID3-x".toByteArray()
            File(dir, audio).apply { parentFile?.mkdirs() }.writeBytes(bytes)
            val book = JSONObject().put("title", "Bộ").put("chapters", org.json.JSONArray().put(JSONObject().put("id", 100001).put("title", "Chương 1")
                .put("fullTitle", "Chương 1").put("available", true).put("file", audio).put("duration", 5.0)))
                .put("package", JSONObject().put("format", "abook").put("version", 2).put("files",
                    JSONObject().put(audio, JSONObject().put("size", bytes.size).put("sha256", sha256(bytes)))))
            if (music) book.put("music", JSONObject.NULL)
            File(dir, "book.json").writeText(book.toString())
            return dir
        }
        assertEquals(3, write(mini("series", "chapters/1/00001.mp3", false), "series.abook").second.version)
        assertEquals(1, write(mini("flat", "chapters/00001.mp3", false), "flat.abook").second.version)
        val nullMusic = write(mini("flat2", "chapters/00001.mp3", true), "flat2.abook")
        assertEquals("khoá music có mặt là phiên bản 2, như `\"music\" in book`", 2, nullMusic.second.version)
        verify(nullMusic.first)
        verify(write(mini("series2", "chapters/1/00001.mp3", false), "series2.abook").first)
    }

    @Test
    fun a_folder_that_is_not_an_imported_book_is_refused() {
        val empty = File(work, "empty").apply { mkdirs() }
        try {
            BookDocumentWriter.write(empty, java.io.ByteArrayOutputStream())
            fail("lẽ ra bị từ chối")
        } catch (error: BookDocumentWriter.Refused) {
            assertEquals("Không đọc được thư mục sách này.", error.message)
        }
        val noPackage = File(work, "nopackage").apply { mkdirs() }
        File(noPackage, "book.json").writeText("{\"title\": \"x\"}")
        try {
            BookDocumentWriter.write(noPackage, java.io.ByteArrayOutputStream())
            fail("lẽ ra bị từ chối")
        } catch (error: BookDocumentWriter.Refused) {
            assertEquals("Đây không phải một cuốn đã nhập từ file sách.", error.message)
        }
        val missing = bookWith(null)
        File(missing, "samples/3.wav").delete()
        try {
            BookDocumentWriter.write(missing, java.io.ByteArrayOutputStream())
            fail("lẽ ra bị từ chối")
        } catch (error: BookDocumentWriter.Refused) {
            assertEquals("Thư mục sách thiếu file samples/3.wav.", error.message)
        }
        val noCover = bookWith("cover_set")
        File(noCover, "edits/cover.jpg").delete()
        try {
            BookDocumentWriter.write(noCover, java.io.ByteArrayOutputStream())
            fail("lẽ ra bị từ chối")
        } catch (error: BookDocumentWriter.Refused) {
            assertEquals("Thiếu ảnh bìa trong phần sửa của sách.", error.message)
        }
    }

    @Test
    fun default_names_follow_bookfile_default_name() {
        assertEquals("Sách thử · Tập 1.abook", BookDocumentWriter.defaultName("Sách thử · Tập 1"))
        assertEquals("a b c.abook", BookDocumentWriter.defaultName("a/b:c*?"))
        assertEquals("Sách nói.abook", BookDocumentWriter.defaultName(""))
        assertEquals("Sách nói.abook", BookDocumentWriter.defaultName(" . "))
        assertEquals("a b.abook", BookDocumentWriter.defaultName("  a \t b\n"))
        assertEquals(150 + ".abook".length, BookDocumentWriter.defaultName("x".repeat(300)).length)
    }

    @Test
    fun the_file_python_wrote_opens_with_its_edits_intact() {
        val python = BookEditsFixtures.file("written/python_v4.abook")
        assertTrue("thiếu file bản Python ghi: ${python.absolutePath}", python.isFile)
        val book = verify(python)
        assertEquals(4, book.getJSONObject("package").getInt("version"))
        val library = BookEditsFixtures.tempDir("abook-python-v4")
        BookEditsFixtures.useStoreRoot(library)
        val imported = BookFileImport.importFile(python)
        val edits = BookEdits.load(Store.bookDir(imported.id))
        assertTrue(StrictJson.equal(BookEdits.parse(BookEditsFixtures.bytes("edits/everything.json")), edits))
        assertArrayEquals(BookEditsFixtures.bytes("edits/everything.cover.jpg"), File(Store.bookDir(imported.id), "edits/cover.jpg").readBytes())
        assertEquals("Sách của tôi", imported.title)
        assertNotNull(Store.coverFile(imported.id))
        val shown = (BookEdits.deepCopy(Store.manifest(imported.id)!!) as JSONObject).also { listOf("id", "edits", "wishes", "capabilities", "package").forEach(it::remove) }
        assertTrue(StrictJson.equal(BookEditsFixtures.obj("expected/everything.json").getJSONObject("manifest"), shown))
        assertEquals(BookEdits.count(edits), Store.manifest(imported.id)!!.getInt("edits"))
        // và mở lại bản vừa nhập: ghi ra lần nữa vẫn đúng từng mục
        val (again, written) = write(Store.bookDir(imported.id), "from-python.abook")
        verify(again)
        assertEquals(4, written.version)
        assertEquals(BookEdits.count(edits), written.edits)
    }

    private val toneSha = MessageDigest.getInstance("SHA-1").digest(BookEditsFixtures.bytes("track/tone.wav")).joinToString("") { "%02x".format(it) }

    /** Một cuốn đã nhập mà người nghe đã ghim bài `tone.wav` của kho "Nhạc của tôi" vào đoạn 1:0 (bằng đúng đường của app). */
    private fun pinnedBook(): File {
        val dir = bookWith(null)
        val store = MusicStore(File(work, "music"), FakeTags)
        store.importFile(BookEditsFixtures.file("track/tone.wav"))
        BookEdits.setMusic(dir, JSONObject().put("pins", JSONObject().put("1:0", "local:$toneSha")), store::track)
        return dir
    }

    @Test
    fun a_pinned_track_travels_with_the_file_and_opens_again() {
        val name = "music/$toneSha.wav"
        val (file, written) = write(pinnedBook(), "pins.abook")
        val book = verify(file)
        assertEquals(4, book.getJSONObject("package").getInt("version"))
        assertEquals(1, written.edits)
        ZipFile(file).use { zip ->
            val entry = zip.getEntry(name)
            assertEquals("bài ghim không nén (phát và tua thẳng trong gói)", ZipEntry.STORED, entry.method)
            assertArrayEquals(BookEditsFixtures.bytes("track/tone.wav"), zip.getInputStream(entry).readBytes())
            assertFalse("lớp sách không bị sửa tại chỗ", book.getJSONObject("music").getJSONObject("tracks").has(name))
        }
        val library = BookEditsFixtures.tempDir("abook-pins-lib")
        BookEditsFixtures.useStoreRoot(library)
        val imported = BookFileImport.importFile(file)
        assertArrayEquals(BookEditsFixtures.bytes("track/tone.wav"), File(Store.bookDir(imported.id), name).readBytes())
        val cue = Store.manifest(imported.id)!!.getJSONObject("music").getJSONObject("chapters").getJSONArray("1").getJSONObject(0)
        assertEquals(name, cue.getString("track"))
        // bản Kotlin ghi ra file bản Python mở được: `-Dabook.writeFixtures=true` ghi thẳng vào written/kotlin_v4_pins.abook
        val build = File("build/kotlin_v4_pins.abook").apply { parentFile?.mkdirs() }
        file.copyTo(build, overwrite = true)
        if (System.getProperty("abook.writeFixtures") == "true") file.copyTo(BookEditsFixtures.file("written/kotlin_v4_pins.abook"), overwrite = true)
    }

    @Test
    fun the_pins_file_python_wrote_opens_and_plays_the_same_overlay() {
        val python = BookEditsFixtures.file("written/python_v4_pins.abook")
        assertTrue("thiếu file bản Python ghi: ${python.absolutePath}", python.isFile)
        verify(python)
        BookEditsFixtures.useStoreRoot(BookEditsFixtures.tempDir("abook-python-pins"))
        val imported = BookFileImport.importFile(python)
        val dir = Store.bookDir(imported.id)
        assertTrue(StrictJson.equal(BookEdits.parse(BookEditsFixtures.bytes("edits/music_pin.json")), BookEdits.load(dir)))
        assertArrayEquals(BookEditsFixtures.bytes("track/tone.wav"), File(dir, "music/$toneSha.wav").readBytes())
        val shown = (BookEdits.deepCopy(Store.manifest(imported.id)!!) as JSONObject).also { listOf("id", "edits", "wishes", "capabilities", "package").forEach(it::remove) }
        assertTrue(StrictJson.equal(BookEditsFixtures.obj("expected/music_pin.json").getJSONObject("manifest"), shown))
        // ghi lại bản vừa nhập: vẫn mang bài ghim
        ZipFile(write(dir, "again.abook").first).use { zip -> assertNotNull(zip.getEntry("music/$toneSha.wav")) }
    }

    @Test
    fun opening_the_book_again_keeps_the_pinned_file_and_a_file_with_pins_brings_its_own() {
        val library = BookEditsFixtures.tempDir("abook-pins-again")
        BookEditsFixtures.useStoreRoot(library)
        val withPins = BookEditsFixtures.file("written/python_v4_pins.abook")
        val without = BookEditsFixtures.file("written/python_v4.abook")
        // 1) cuốn đã ghim bài; mở lại một file khác của cùng cuốn (không bài ghim): phần sửa hợp lại, file bài ghim không mất
        val first = BookFileImport.importFile(withPins)
        val dir = Store.bookDir(first.id)
        val second = BookFileImport.importFile(without)
        assertEquals(first.id, second.id)
        assertEquals("local:$toneSha", BookEdits.load(dir).getJSONObject("music").getJSONObject("pins").getString("1:0"))
        assertArrayEquals(BookEditsFixtures.bytes("track/tone.wav"), File(dir, "music/$toneSha.wav").readBytes())
        // 2) cuốn chưa có bài ghim, bản trên máy nhiều chương hơn file: file không giải nén lại nhưng phần sửa + file bài ghim của nó vào
        BookEdits.clear(dir)
        assertFalse(File(dir, "music/$toneSha.wav").exists())
        File(dir, "book.json").writeText(JSONObject(File(dir, "book.json").readText()).put("chaptersAvailable", 99).toString())
        BookFileImport.importFile(withPins)
        assertEquals(1, BookEdits.count(BookEdits.load(dir)))
        assertArrayEquals(BookEditsFixtures.bytes("track/tone.wav"), File(dir, "music/$toneSha.wav").readBytes())
    }

    @Test
    fun a_pin_without_its_file_is_refused_when_saving() {
        val dir = bookWith(null)
        File(dir, "edits.json").writeBytes(BookEditsFixtures.bytes("edits/music_pin.json"))
        try {
            BookDocumentWriter.write(dir, java.io.ByteArrayOutputStream())
            fail("lẽ ra bị từ chối")
        } catch (error: BookDocumentWriter.Refused) {
            assertEquals("Thiếu file bài nhạc người nghe đã chọn trong thư mục sách.", error.message)
        }
    }

    @Test
    fun the_file_for_the_python_cross_check_is_written_next_to_the_build() {
        // Phía Python mở file này bằng bookfile.BookFile(...).verify() (pytest) - sao tay sang fixtures/written/kotlin_v4.abook, hay
        // chạy với -Dabook.writeFixtures=true để ghi thẳng vào đó.
        val dir = bookWith("everything")
        val (file, _) = write(dir, "kotlin_v4.abook")
        verify(file)
        val build = File("build/kotlin_v4.abook").apply { parentFile?.mkdirs() }
        file.copyTo(build, overwrite = true)
        if (System.getProperty("abook.writeFixtures") == "true") file.copyTo(BookEditsFixtures.file("written/kotlin_v4.abook"), overwrite = true)
        assertTrue(build.isFile)
    }
}
