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

    @Test
    fun a_file_whose_pinned_track_is_missing_is_refused_whole() {
        val edits = BookEdits.parse(BookEditsFixtures.bytes("edits/music_pin.json"))
        val book = JSONObject().put("title", "X").put("chaptersAvailable", 1).put("chapters", JSONArray().put(chapter(1, 0, "chapters/00001.mp3")))
        val file = abook("pin.abook", 4, mapOf("cast.json" to "{}".toByteArray(), "chapters/00001.mp3" to "ID3-x".toByteArray(),
            "scripts/1.json" to "{}".toByteArray(), "edits.json" to BookEdits.dump(edits)), book)
        try {
            BookFileImport.importFile(file)
            fail("lẽ ra bị từ chối")
        } catch (error: BookFileImport.Refused) {
            assertEquals("File sách thiếu bài nhạc mà người nghe đã chọn.", error.message)
        }
        assertFalse(File(root, "books").listFiles()?.isNotEmpty() ?: false)
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
        val message = refusal { BookFileImport.importFile(seriesFile("moi.abook", version = 6)) }
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

    /** Chép gói `file` sang `name`, thay byte của mục `entry` (book.json giữ nguyên - như file hỏng trên đường chép). */
    private fun spoiled(file: File, name: String, entry: String, replacement: ByteArray): File {
        val broken = File(work, name)
        java.util.zip.ZipFile(file).use { zip ->
            ZipOutputStream(broken.outputStream()).use { out ->
                for (original in zip.entries().toList()) {
                    val bytes = if (original.name == entry) replacement else zip.getInputStream(original).use { it.readBytes() }
                    val item = ZipEntry(original.name)
                    if (original.method == ZipEntry.STORED) {
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
        return broken
    }

    @Test
    fun a_damaged_entry_is_refused_and_leaves_no_half_book() {
        // Đổi byte một audio trong gói: cỡ giữ nguyên, mã băm không còn khớp.
        val broken = spoiled(seriesFile(), "hong.abook", "chapters/2/00001.mp3", "ID3-phan-xxx".toByteArray())
        val message = refusal { BookFileImport.importFile(broken) }
        assertTrue(message, "hỏng" in message)
        assertTrue(File(root, "books").listFiles().orEmpty().none { it.isDirectory })
    }

    @Test
    fun a_broken_music_track_leaves_silence_not_an_unopenable_book() {
        // Soát a26 L4 (bookfile.py cùng luật): một bài nhạc nền hỏng không chặn cả cuốn - bài ấy bị bỏ, đoạn ấy im lặng.
        val calm = "music/" + "c".repeat(40) + ".mp3"
        val battle = "music/" + "d".repeat(40) + ".mp3"
        fun track(name: String) = JSONObject().put("file", name).put("title", name)
        fun cue(start: Double, end: Double, name: String) = JSONObject().put("start", start).put("end", end).put("track", name)
        val music = JSONObject().put("levelDb", -18.0).put("tracks", JSONObject().put(calm, track(calm)).put(battle, track(battle)))
            .put("chapters", JSONObject().put("1", JSONArray().put(cue(0.0, 30.0, calm)).put(cue(30.0, 60.0, battle))))
        val book = JSONObject().put("title", "Nhạc hỏng").put("chaptersAvailable", 1)
            .put("chapters", JSONArray().put(JSONObject().put("id", 1).put("file", "chapters/00001.mp3"))).put("music", music)
        val file = abook("nhac.abook", 2, mapOf("cast.json" to "{}".toByteArray(), "scripts/1.json" to "{}".toByteArray(),
            "chapters/00001.mp3" to "ID3-chuong".toByteArray(), calm to "ID3-calm".toByteArray(), battle to "ID3-battle".toByteArray()), book)
        for ((name, bytes) in listOf("cut.abook" to "ID3".toByteArray(), "same.abook" to "ID3-xxxxxx".toByteArray())) {
            val imported = BookFileImport.importFile(spoiled(file, name, battle, bytes), separate = true)
            assertEquals(name, 1, imported.brokenMusic)
            val dir = Store.bookDir(imported.id)
            assertFalse("bài hỏng không vào thư viện", File(dir, battle).exists())
            assertEquals("ID3-calm", File(dir, calm).readText())
            val kept = JSONObject(File(dir, "book.json").readText())
            assertFalse(kept.getJSONObject("package").getJSONObject("files").has(battle))
            assertFalse(kept.getJSONObject("music").getJSONObject("tracks").has(battle))
            val cues = kept.getJSONObject("music").getJSONObject("chapters").getJSONArray("1")
            assertEquals(1, cues.length())
            assertEquals(calm, cues.getJSONObject(0).getString("track"))
        }
        // Audio chương hỏng thì vẫn từ chối cả file.
        val message = refusal { BookFileImport.importFile(spoiled(file, "chuong.abook", "chapters/00001.mp3", "ID3".toByteArray()), separate = true) }
        assertTrue(message, "hỏng" in message)
    }

    @Test
    fun a_book_that_does_not_fit_is_refused_before_anything_is_copied() {
        val message = refusal { BookFileImport.importFile(seriesFile()) { 1_000L } }
        assertTrue(message, "không đủ chỗ" in message && "cần khoảng" in message && "còn" in message)
        assertTrue("chưa chép gì vào thư viện", File(root, "books").listFiles().orEmpty().isEmpty())
    }

    // ---- file dự án .abookproj phiên bản 3: phần nghe + xưởng giữ nguyên byte, bí danh, bản chụp -----------------------------

    private val chapterEntry = "chapters/00001_645.mp3"
    private val musicEntry = "music/" + "a".repeat(40) + ".mp3"
    private val workshopSqlite = ByteArray(300_000) { 7 }

    private fun metaOf(bytes: ByteArray) = JSONObject().put("size", bytes.size).put("sha256", sha256(bytes))

    /**
     * Dựng một file .abookproj phiên bản 3 như projectfile.pack: `listening` là phần nghe (mục thật, tên như file .abook), `workshop`
     * là phần xưởng (project/, sources/, views/), `aliases` {bí danh -> mục thật} KHÔNG nằm trong gói nhưng có trong project.json.
     * book.json kể đúng các mục logic của phần nghe (kể cả bí danh) trong `package.files`.
     */
    private fun abookproj(
        name: String = "du_an.abookproj",
        projectVersion: Int = 3,
        workshopState: String = "present",
        listening: Map<String, ByteArray> = mapOf(
            chapterEntry to "ID3-chuong-mot".toByteArray(),
            "cast.json" to "{}".toByteArray(),
            "scripts/1.json" to "{}".toByteArray(),
            musicEntry to "ID3-nhac".toByteArray(),
        ),
        workshop: Map<String, ByteArray> = mapOf(
            "project/project.sqlite3" to workshopSqlite,
            "project/book_settings.json" to "{}".toByteArray(),
            "project/work/s3.wav" to ByteArray(200_000) { 3 },
            "sources/00001_645.txt" to "Chương 645".toByteArray(),
            "views/work.json" to """{"items": [], "castReady": true}""".toByteArray(),
        ),
        aliases: Map<String, String> = mapOf("project/output/chapters/00001_645.mp3" to chapterEntry),
        book: JSONObject? = null,
        withBook: Boolean = true,
        corrupt: (String, ByteArray) -> ByteArray = { _, bytes -> bytes },
    ): File {
        val physical = listening + if (workshopState == "present") workshop else workshop.filterKeys { !it.startsWith("project/") }
        val described = JSONObject()
        val listed = JSONObject()
        for ((entry, bytes) in physical) {
            described.put(entry, metaOf(bytes))
            if (entry in listening) listed.put(entry, metaOf(bytes))
        }
        for ((alias, target) in aliases) {
            val bytes = physical[target] ?: "không có".toByteArray()
            described.put(alias, metaOf(bytes))
            if (alias in listening || alias.startsWith("chapters/") || alias.startsWith("samples/")) listed.put(alias, metaOf(bytes))
        }
        val manifest = book ?: JSONObject().put("title", "Dự án thử").put("chaptersAvailable", 1).put("chaptersTotal", 2)
            .put("chapters", JSONArray().put(chapter(1, 0, chapterEntry).also { it.remove("part") })
                .put(JSONObject().put("id", 2).put("available", false).put("file", JSONObject.NULL)))
        manifest.put("package", JSONObject().put("format", "abook").put("version", 1).put("files", listed))
        val bookBytes = manifest.toString().toByteArray()
        if (withBook) described.put("book.json", metaOf(bookBytes))
        val project = JSONObject().put("format", "abookproj").put("version", projectVersion).put("workshop", workshopState)
            .put("projectRoot", if (workshopState == "present") "D:\\Studio\\sach_thu" else "")
            .put("sources", JSONArray().also { if (workshopState == "present") it.put(JSONObject().put("path", "D:\\nguon\\645.txt").put("entry", "sources/00001_645.txt")) })
            .put("missingSources", JSONArray()).put("aliases", JSONObject(aliases)).put("files", described)
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
            put("mimetype", BookFileImport.PROJECT_MIMETYPE.toByteArray(), stored = true)
            put("project.json", project.toString().toByteArray(), false)
            if (withBook) put("book.json", bookBytes, stored = false)
            for ((entry, bytes) in physical) put(entry, corrupt(entry, bytes), stored = true)
        }
        return target
    }

    private fun filesUnder(dir: File): Set<String> =
        dir.walkTopDown().filter { it.isFile }.map { it.relativeTo(dir).path.replace('\\', '/') }.toSet()

    @Test
    fun a_project_file_keeps_its_workshop_next_to_the_listening_layer_and_never_opens_the_database() {
        val imported = BookFileImport.importFile(abookproj())

        assertEquals("Dự án thử", imported.title)
        val dir = Store.bookDir(imported.id)
        assertEquals(
            setOf("book.json", "project.json", "cast.json", "scripts/1.json", "chapters/00001_645.mp3", musicEntry, "project/project.sqlite3",
                "project/book_settings.json", "project/work/s3.wav", "sources/00001_645.txt", "views/work.json"),
            filesUnder(dir),
        )
        assertEquals("ID3-chuong-mot", File(dir, "chapters/00001_645.mp3").readText())
        assertFalse("bí danh của audio chương không giải ra hai lần", File(dir, "project/output").exists())
        assertTrue("sổ dự án chép nguyên byte", workshopSqlite.contentEquals(File(dir, "project/project.sqlite3").readBytes()))
        val shown = Store.manifest(imported.id)!!
        assertEquals("present", shown.getJSONObject("projectFile").getString("workshop"))
        assertEquals(listOf("work"), shown.getJSONObject("projectFile").getJSONArray("views").let { v -> (0 until v.length()).map { v.getString(it) } })
        assertTrue(Store.importedBooks().contains(imported.id))
    }

    @Test
    fun opening_the_project_file_of_a_book_already_here_merges_the_workshop_edits_of_both() {
        // Soát UX a25 T5: bản trên máy bị thay bằng bản của file - sửa trong xưởng của bản trên máy (cách đọc Rhine mới hơn, phán
        // quyết s5) không mất, sửa của file (Heidi) được lấy; project.json mang đúng cỡ + mã băm của file vừa gộp.
        fun workshop(overrides: String, reviews: String) = mapOf(
            "project/project.sqlite3" to workshopSqlite, "project/book_settings.json" to "{}".toByteArray(),
            "project/overrides.json" to overrides.toByteArray(), "project/reviews.json" to reviews.toByteArray(),
        )
        val here = BookFileImport.importFile(abookproj(name = "may_nay.abookproj", workshop = workshop(
            """{"version": 1, "pronunciations": {"rhine": {"surface": "Rhine", "spoken_form": "Rai", "requested_at": 300.0}}}""",
            """{"s5": {"verdict": "ok", "chapterId": 1, "at": 100.0}}""",
        )))
        val again = BookFileImport.importFile(abookproj(name = "may_kia.abookproj", workshop = workshop(
            """{"version": 1, "pronunciations": {"rhine": {"surface": "Rhine", "spoken_form": "Rai-nơ", "requested_at": 100.0},""" +
                """ "heidi": {"surface": "Heidi", "spoken_form": "Hai-đi", "requested_at": 200.0}}}""",
            """{"s6": {"verdict": "redo", "chapterId": 1, "at": 150.0}}""",
        )))

        assertEquals(here.id, again.id)
        val dir = Store.bookDir(again.id)
        val pronunciations = JSONObject(File(dir, "project/overrides.json").readText()).getJSONObject("pronunciations")
        assertEquals("Rai", pronunciations.getJSONObject("rhine").getString("spoken_form"))
        assertEquals("Hai-đi", pronunciations.getJSONObject("heidi").getString("spoken_form"))
        val reviews = JSONObject(File(dir, "project/reviews.json").readText())
        assertEquals(setOf("s5", "s6"), reviews.keys().asSequence().toSet())
        val described = JSONObject(File(dir, "project.json").readText()).getJSONObject("files")
        for (name in listOf("project/overrides.json", "project/reviews.json")) {
            assertEquals(metaOf(File(dir, name).readBytes()).toString(), described.getJSONObject(name).toString())
        }
    }

    @Test
    fun a_project_file_with_fewer_chapters_than_the_book_here_still_brings_its_workshop_edits() {
        // Soát UX a25 T5, nhánh giữ bản trên máy (máy này nhiều chương hơn file): sửa trong xưởng của file vẫn được gộp vào.
        fun workshop(overrides: String) = mapOf(
            "project/project.sqlite3" to workshopSqlite, "project/book_settings.json" to "{}".toByteArray(),
            "project/overrides.json" to overrides.toByteArray(),
        )
        val here = BookFileImport.importFile(abookproj(name = "may_nay.abookproj", workshop = workshop(
            """{"version": 1, "pronunciations": {"rhine": {"surface": "Rhine", "spoken_form": "Rai", "requested_at": 300.0}}}""",
        )))
        val dir = Store.bookDir(here.id)
        File(dir, "book.json").writeText(JSONObject(File(dir, "book.json").readText()).put("chaptersAvailable", 2).toString())
        val again = BookFileImport.importFile(abookproj(name = "may_kia.abookproj", workshop = workshop(
            """{"version": 1, "pronunciations": {"rhine": {"surface": "Rhine", "spoken_form": "Rai-nơ", "requested_at": 100.0},""" +
                """ "heidi": {"surface": "Heidi", "spoken_form": "Hai-đi", "requested_at": 200.0}}}""",
        )))

        assertEquals(here.id, again.id)
        assertEquals("bản trên máy được giữ", 2, Store.rawManifest(here.id)!!.getInt("chaptersAvailable"))
        val pronunciations = JSONObject(File(dir, "project/overrides.json").readText()).getJSONObject("pronunciations")
        assertEquals("Rai", pronunciations.getJSONObject("rhine").getString("spoken_form"))
        assertEquals("Hai-đi", pronunciations.getJSONObject("heidi").getString("spoken_form"))
        val described = JSONObject(File(dir, "project.json").readText()).getJSONObject("files")
        assertEquals(metaOf(File(dir, "project/overrides.json").readBytes()).toString(), described.getJSONObject("project/overrides.json").toString())
    }

    @Test
    fun a_listening_entry_that_is_an_alias_reads_the_bytes_of_its_real_entry() {
        // Mục nghe có thể là bí danh của một mục trong xưởng (điện thoại / máy khác ghi file có audio nằm ở project/ trước): đọc byte mục thật.
        val sample = ByteArray(1000) { 5 }
        val imported = BookFileImport.importFile(
            abookproj(
                listening = mapOf(chapterEntry to "ID3-chuong-mot".toByteArray(), "cast.json" to "{}".toByteArray()),
                workshop = mapOf(
                    "project/project.sqlite3" to workshopSqlite, "project/book_settings.json" to "{}".toByteArray(),
                    "project/work/s3.wav" to sample,
                ),
                aliases = mapOf("samples/3.wav" to "project/work/s3.wav"),
            ),
        )

        assertTrue(sample.contentEquals(File(Store.bookDir(imported.id), "samples/3.wav").readBytes()))
        assertTrue(Store.manifest(imported.id)!!.getJSONObject("package").getJSONObject("files").has("samples/3.wav"))
    }

    @Test
    fun a_users_own_music_keeps_its_format_and_comes_along_with_the_book() {
        // "Nhạc của tôi": bài người dùng nhập đi theo sách nguyên định dạng (music_plan.TRACK_EXTENSIONS), không chỉ .mp3.
        val flac = "music/" + "b".repeat(40) + ".flac"
        val imported = BookFileImport.importFile(
            abookproj(
                listening = mapOf(
                    chapterEntry to "ID3-chuong-mot".toByteArray(),
                    "cast.json" to "{}".toByteArray(),
                    "scripts/1.json" to "{}".toByteArray(),
                    flac to "fLaC-nhac".toByteArray(),
                ),
            ),
        )

        assertEquals("fLaC-nhac", File(Store.bookDir(imported.id), flac).readText())
    }

    @Test
    fun a_project_files_chapters_are_ordinary_imported_chapters() {
        val imported = BookFileImport.importFile(abookproj())

        val book = Store.manifest(imported.id)!!
        assertEquals(imported.id, book.getString("id"))
        assertEquals("chapters/00001_645.mp3", LibraryTree.chapters(book)[0].file)
        assertTrue(Store.file(imported.id, "chapters/00001_645.mp3").isFile)
        assertEquals(setOf("chapters/00001_645.mp3"), Store.chapterPrints(imported.id).keys().asSequence().toSet())
    }

    @Test
    fun a_project_file_and_a_book_file_of_the_same_chapters_are_one_book() {
        val audio = "ID3-chuong-mot".toByteArray()
        val flat = abook("sach.abook", 1, mapOf("chapters/00001_645.mp3" to audio),
            JSONObject().put("title", "Dự án thử").put("chaptersAvailable", 1)
                .put("chapters", JSONArray().put(chapter(1, 0, "chapters/00001_645.mp3").also { it.remove("part") })))
        val first = BookFileImport.importFile(flat)
        assertTrue("cuốn từ file .abook chưa có xưởng", Store.manifest(first.id)!!.isNull("projectFile"))
        val again = BookFileImport.importFile(abookproj())

        assertEquals("cùng một lần sản xuất: nhập vào đúng cuốn đã có", first.id, again.id)
        assertEquals(1, File(root, "books").listFiles()!!.count { it.isDirectory && !it.name.startsWith(".") })
        assertTrue(File(root, "books/${first.id}/cast.json").isFile)
        assertTrue("cuốn nay mang xưởng của file dự án", File(root, "books/${first.id}/project/project.sqlite3").isFile)
    }

    @Test
    fun a_project_file_newer_or_older_than_the_app_is_refused_and_copies_nothing() {
        val newer = refusal { BookFileImport.importFile(abookproj("moi.abookproj", projectVersion = 4)) }
        assertTrue(newer, "Hãy cập nhật app" in newer)
        val older = refusal { BookFileImport.importFile(abookproj("cu.abookproj", projectVersion = 2)) }
        assertTrue(older, "cũ hơn" in older)
        assertTrue(File(root, "books").listFiles().orEmpty().isEmpty())
    }

    @Test
    fun a_project_without_a_finished_chapter_says_so() {
        val message = refusal { BookFileImport.importFile(abookproj("trong.abookproj", listening = emptyMap(), aliases = emptyMap(), withBook = false)) }
        assertTrue(message, "chưa có chương nào nghe được" in message)
    }

    @Test
    fun a_file_waiting_for_its_workshop_imports_as_a_book_and_cannot_carry_a_project_folder() {
        val imported = BookFileImport.importFile(abookproj("cho.abookproj", workshopState = "pending", aliases = emptyMap()))
        val dir = Store.bookDir(imported.id)
        assertEquals("pending", Store.manifest(imported.id)!!.getJSONObject("projectFile").getString("workshop"))
        assertTrue(File(dir, "project.json").isFile && !File(dir, "project").exists())
        assertTrue("sources/ tuỳ chọn vẫn được giữ", File(dir, "sources/00001_645.txt").isFile)

        // file nói chưa có xưởng mà vẫn mang sổ dự án: từ chối
        val sneaky = abookproj("gia.abookproj", workshopState = "present")
        val forged = File(work, "gia2.abookproj")
        java.util.zip.ZipFile(sneaky).use { zip ->
            ZipOutputStream(forged.outputStream()).use { out ->
                for (entry in zip.entries().toList()) {
                    var bytes = zip.getInputStream(entry).use { it.readBytes() }
                    if (entry.name == "project.json") bytes = JSONObject(String(bytes)).put("workshop", "pending").toString().toByteArray()
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
        val message = refusal { BookFileImport.importFile(forged) }
        assertTrue(message, "chưa có xưởng" in message)
    }

    @Test
    fun the_room_check_counts_what_is_unpacked() {
        val whole = abookproj()
        val workshopBytes = workshopSqlite.size + 2 + 200_000 + "Chương 645".length + """{"items": [], "castReady": true}""".length
        val listeningBytes = "ID3-chuong-mot".length + 2 + 2 + "ID3-nhac".length  // chương + cast + script + nhạc
        val margin = 64L shl 20
        val need = listeningBytes + workshopBytes
        val message = refusal { BookFileImport.importFile(whole) { margin + need - 1_000 } }
        assertTrue(message, "không đủ chỗ" in message)
        assertTrue(File(root, "books").listFiles().orEmpty().isEmpty())
        val imported = BookFileImport.importFile(whole) { margin + need + 100_000 }
        assertTrue(File(Store.bookDir(imported.id), "chapters/00001_645.mp3").isFile)
    }

    @Test
    fun a_project_chapter_that_points_outside_the_listening_layer_is_refused() {
        val book = JSONObject().put("title", "X").put("chaptersAvailable", 1)
            .put("chapters", JSONArray().put(chapter(1, 0, "project/output/chapters/khong_co.mp3").also { it.remove("part") }))
        val message = refusal { BookFileImport.importFile(abookproj("la.abookproj", book = book)) }
        assertTrue(message, "thiếu audio" in message)
        assertTrue(File(root, "books").listFiles().orEmpty().none { it.isDirectory })
    }

    @Test
    fun a_damaged_project_chapter_is_refused_and_leaves_no_half_book() {
        val broken = abookproj("hong.abookproj", corrupt = { entry, bytes -> if (entry == chapterEntry) "ID3-chuong-xxx".toByteArray() else bytes })
        val message = refusal { BookFileImport.importFile(broken) }
        assertTrue(message, "hỏng" in message)
        assertTrue(File(root, "books").listFiles().orEmpty().none { it.isDirectory })
    }

    @Test
    fun a_broken_alias_is_refused() {
        val target = refusal { BookFileImport.importFile(abookproj("a.abookproj", aliases = mapOf("project/output/chapters/00001_645.mp3" to "chapters/khong_co.mp3"))) }
        assertTrue(target, "Bí danh" in target)
        val different = refusal {
            BookFileImport.importFile(abookproj("b.abookproj", aliases = mapOf("project/output/chapters/00001_645.mp3" to "cast.json")))
        }
        assertTrue(different, "Bí danh" in different)
        assertTrue(File(root, "books").listFiles().orEmpty().none { it.isDirectory })
    }

    // ---- file dự án do Python ghi (tests/book_edits_fixtures.py) ----------------------------------------------------------------

    @Test
    fun the_workshop_file_python_wrote_opens_and_keeps_its_aliased_audio_once() {
        val imported = BookFileImport.importFile(BookEditsFixtures.file("written/python_workshop.abookproj"))

        val dir = Store.bookDir(imported.id)
        assertEquals("Sách thử · Tập 1", imported.title)
        val files = filesUnder(dir)
        assertTrue(files.containsAll(setOf("chapters/00001_645.mp3", "samples/3.wav", "cover.jpg", "project/project.sqlite3", "project.json",
            "sources/00001_645.txt", "sources/00002_646.txt", "views/work.json", "views/casting.json", "views/names.json")))
        assertTrue("bí danh của audio chương và câu mẫu không nằm lại trong project/", files.none { it == "project/output/chapters/00001_645.mp3" || it == "project/work/s3.wav" || it == "project/cover.jpg" })
        val info = Store.manifest(imported.id)!!.getJSONObject("projectFile")
        assertEquals("present", info.getString("workshop"))
        assertEquals(3, info.getJSONArray("views").length())
        val inFile = java.util.zip.ZipFile(BookEditsFixtures.file("written/python_workshop.abookproj")).use {
            StrictJson.parse(it.getInputStream(it.getEntry("views/work.json")).readBytes().toString(Charsets.UTF_8))
        }
        assertTrue("bản chụp đọc ra đúng JSON trong file", StrictJson.equal(inFile, ProjectDocument.view(dir, "work")))
    }

    @Test
    fun the_pending_file_python_wrote_opens_with_its_edits() {
        val imported = BookFileImport.importFile(BookEditsFixtures.file("written/python_pending.abookproj"))

        val dir = Store.bookDir(imported.id)
        assertEquals("pending", Store.manifest(imported.id)!!.getJSONObject("projectFile").getString("workshop"))
        assertFalse(File(dir, "project").exists())
        assertEquals("Sách của tôi", imported.title)
        val edits = BookEdits.load(dir)
        assertEquals(BookEdits.count(BookEditsFixtures.obj("edits/everything.json")), BookEdits.count(edits))
        assertTrue(File(dir, "edits/cover.jpg").isFile)
    }

    // ---- lớp sửa của người nghe (phiên bản 4: edits.json, edits/cover.jpg - BookEdits) --------------------------------------

    private val jpeg = byteArrayOf(0xFF.toByte(), 0xD8.toByte(), 0xFF.toByte(), 0xE0.toByte(), 1, 2, 3)
    private val otherJpeg = byteArrayOf(0xFF.toByte(), 0xD8.toByte(), 0xFF.toByte(), 0xE1.toByte(), 9, 9)

    private fun cover(color: String, version: Long) = JSONObject().put("color", color).put("width", 10L).put("height", 20L).put("version", version)

    /** Một file .abook có một chương nghe được (và một chưa có), cùng audio mỗi lần - nhập lại là nhập lại CÙNG một cuốn. */
    private fun editedBook(name: String, version: Int = 4, edits: JSONObject? = null, cover: ByteArray? = null, available: Int = 1,
                           editsBytes: ByteArray? = null): File {
        val content = linkedMapOf("cast.json" to "{}".toByteArray(), "chapters/00001.mp3" to "ID3-mot".toByteArray(),
            "scripts/1.json" to "{}".toByteArray(), "scripts/2.json" to "{}".toByteArray())
        if (editsBytes != null) content["edits.json"] = editsBytes else if (edits != null) content["edits.json"] = BookEdits.dump(edits)
        if (cover != null) content["edits/cover.jpg"] = cover
        val chapters = JSONArray()
            .put(JSONObject().put("id", 1).put("title", "Chương 1").put("subtitle", "").put("fullTitle", "Chương 1").put("available", true)
                .put("file", "chapters/00001.mp3").put("script", "scripts/1.json").put("duration", 60.0))
            .put(JSONObject().put("id", 2).put("title", "Chương 2").put("subtitle", "").put("fullTitle", "Chương 2").put("available", false)
                .put("file", JSONObject.NULL).put("script", "scripts/2.json").put("duration", 0.0))
        val book = JSONObject().put("title", "Truyện Y").put("chaptersAvailable", available).put("chaptersTotal", 2).put("chapters", chapters)
        return abook(name, version, content, book)
    }

    private fun dirOf(imported: BookFileImport.Imported) = Store.bookDir(imported.id)

    private class FakeCodec(private val color: String) : CoverCodec {
        override fun normalize(raw: ByteArray) = CoverCodec.Normalized(raw, color, 10, 20)
    }

    @Test
    fun a_version_4_file_brings_the_listeners_edits_in() {
        val edits = BookEdits.empty().put("title", "Tên của bạn").put("chapters", JSONObject().put("1", JSONObject().put("subtitle", "Hồi một")))
            .put("cover", cover("#112233", 5L))
        val imported = BookFileImport.importFile(editedBook("v4.abook", edits = edits, cover = jpeg))

        assertEquals("tên đã sửa là tên hiện trong thư viện", "Tên của bạn", imported.title)
        assertTrue(StrictJson.equal(edits, BookEdits.load(dirOf(imported))))
        assertTrue(File(dirOf(imported), "edits/cover.jpg").readBytes().contentEquals(jpeg))
        val shown = Store.manifest(imported.id)!!
        assertEquals("Tên của bạn", shown.getString("title"))
        assertEquals("Chương 1 · Hồi một", shown.getJSONArray("chapters").getJSONObject(0).getString("fullTitle"))
        assertEquals("edits/cover.jpg", shown.getJSONObject("cover").getString("file"))
        assertEquals(3, shown.getInt("edits"))
        assertEquals("lớp sách nguyên văn không bị sửa", "Truyện Y", Store.rawManifest(imported.id)!!.getString("title"))
    }

    @Test
    fun reimporting_over_an_edited_book_keeps_the_local_edits_and_takes_the_rest_from_the_file() {
        val first = BookFileImport.importFile(editedBook("v1.abook", version = 1))
        val dir = dirOf(first)
        BookEdits.setTitle(dir, "Của tôi")
        BookEdits.setChapterTitle(dir, 1, null, "Phụ của tôi")

        val again = BookFileImport.importFile(editedBook("v4.abook", edits = BookEdits.empty().put("title", "Của file")
            .put("chapters", JSONObject().put("1", JSONObject().put("title", "Chương Mới").put("subtitle", "Phụ của file")))
            .put("cover", cover("#112233", 5L)), cover = jpeg))

        assertEquals("cùng một cuốn", first.id, again.id)
        val edits = BookEdits.load(dir)
        assertEquals("máy này thắng", "Của tôi", edits.getString("title"))
        assertEquals("Phụ của tôi", edits.getJSONObject("chapters").getJSONObject("1").getString("subtitle"))
        assertEquals("phần còn lại lấy từ file", "Chương Mới", edits.getJSONObject("chapters").getJSONObject("1").getString("title"))
        assertTrue(File(dir, "edits/cover.jpg").readBytes().contentEquals(jpeg))
        assertEquals("Của tôi", again.title)
        assertEquals("Của tôi", Store.manifest(again.id)!!.getString("title"))
        assertEquals("hai thay đổi của máy này được báo là giữ nguyên", 2, again.keptEdits)
        assertEquals("cuốn mới chưa có gì để giữ", 0, first.keptEdits)
    }

    @Test
    fun the_local_cover_wins_over_the_files_cover() {
        val first = BookFileImport.importFile(editedBook("v1.abook", version = 1))
        val dir = dirOf(first)
        BookEdits.setCover(dir, otherJpeg, 77L, FakeCodec("#aabbcc"))

        BookFileImport.importFile(editedBook("v4.abook", edits = BookEdits.empty().put("cover", cover("#112233", 5L)), cover = jpeg))

        assertTrue("bìa của máy này còn đó", File(dir, "edits/cover.jpg").readBytes().contentEquals(otherJpeg))
        assertEquals("#aabbcc", BookEdits.load(dir).getJSONObject("cover").getString("color"))
    }

    @Test
    fun a_file_with_fewer_chapters_than_the_phone_still_hands_over_its_edits() {
        val first = BookFileImport.importFile(editedBook("full.abook", version = 1, available = 2))
        val dir = dirOf(first)
        BookEdits.setTitle(dir, "Của tôi")

        val again = BookFileImport.importFile(editedBook("short.abook", available = 1, edits = BookEdits.empty().put("title", "Của file")
            .put("characters", JSONObject().put("LUCIEN", "Lu-xi-en"))))

        assertEquals(first.id, again.id)
        val edits = BookEdits.load(dir)
        assertEquals("Của tôi", edits.getString("title"))
        assertEquals("Lu-xi-en", edits.getJSONObject("characters").getString("LUCIEN"))
        assertEquals("bản trên máy (nhiều chương hơn) giữ nguyên", 2, Store.rawManifest(first.id)!!.getInt("chaptersAvailable"))
        assertEquals(1, again.keptEdits)
    }

    @Test
    fun a_malformed_edits_file_refuses_the_whole_book() {
        fun refused(editsBytes: ByteArray? = null, cover: ByteArray? = null, edits: JSONObject? = null): String {
            val message = refusal { BookFileImport.importFile(editedBook("la.abook", edits = edits, cover = cover, editsBytes = editsBytes)) }
            assertTrue("chưa chép gì vào thư viện", File(root, "books").listFiles().orEmpty().none { it.isDirectory })
            return message
        }
        val head = """{"format": "abook-edits", "version": 1"""
        assertEquals("Phần sửa của sách có mục lạ.", refused(editsBytes = "$head, \"pins\": []}".toByteArray()))
        assertEquals("Phần sửa của sách bị hỏng.", refused(editsBytes = "{".toByteArray()))
        assertEquals("Phần sửa của sách bị hỏng.", refused(editsBytes = "$head, \"music\": {\"levelDb\": NaN}}".toByteArray()))
        assertEquals("Tên sách trong phần sửa không hợp lệ.", refused(editsBytes = "$head, \"title\": \"Tên  sách\"}".toByteArray()))
        assertEquals("Phần sửa của sách quá lớn.", refused(editsBytes = "$head, \"title\": \"${"a".repeat(BookEdits.MAX_EDITS_BYTES)}\"}".toByteArray()))
        // bìa sửa đi đôi với phần sửa: có một mà không có kia là sai
        assertEquals("Ảnh bìa trong phần sửa của sách không khớp.", refused(edits = BookEdits.empty().put("cover", cover("#112233", 5L))))
        assertEquals("Ảnh bìa trong phần sửa của sách không khớp.", refused(edits = BookEdits.empty().put("title", "x"), cover = jpeg))
        assertEquals("Ảnh bìa trong phần sửa của sách không dùng được.",
            refused(edits = BookEdits.empty().put("cover", cover("#112233", 5L)), cover = "không phải JPEG".toByteArray()))
        assertEquals("Ảnh bìa trong phần sửa của sách không dùng được.",
            refused(edits = BookEdits.empty().put("cover", cover("#112233", 5L)), cover = jpeg + ByteArray(BookEdits.MAX_COVER_BYTES)))
    }

    @Test
    fun edits_belong_to_version_4_only() {
        val edits = BookEdits.empty().put("title", "Tên khác")
        for (version in listOf(1, 2, 3)) {
            val message = refusal { BookFileImport.importFile(editedBook("cu$version.abook", version = version, edits = edits)) }
            assertTrue("phiên bản $version: $message", "mục lạ" in message && "edits.json" in message)
        }
        val message = refusal { BookFileImport.importFile(editedBook("cover3.abook", version = 3, edits = BookEdits.empty().put("cover", cover("#112233", 5L)), cover = jpeg)) }
        assertTrue(message, "mục lạ" in message)
        assertTrue(File(root, "books").listFiles().orEmpty().none { it.isDirectory })
    }

    @Test
    fun a_file_still_cannot_carry_project_sources_or_views() {
        for (name in listOf("project/project.sqlite3", "sources/1.txt", "views/cast.json")) {
            val file = abook("du.abook", 4, mapOf("chapters/00001.mp3" to byteArrayOf(1), name to byteArrayOf(2)), JSONObject().put("chapters", JSONArray()))
            assertTrue(name, "mục lạ" in refusal { BookFileImport.importFile(file) })
        }
    }

    @Test
    fun edits_in_a_file_do_not_land_on_a_book_that_came_from_the_computer() {
        // Cuốn tải qua Wi-Fi (không mở từ file) cùng audio với file: sửa của người nghe sửa ở máy tính, không rơi vào đây.
        val existing = "0123456789abcdef01234567"
        File(root, "books/$existing/chapters").mkdirs()
        File(root, "books/$existing/chapters/00001.mp3").writeBytes("ID3-mot".toByteArray())
        File(root, "books/$existing/book.json").writeText(JSONObject().put("id", existing).put("title", "Truyện Y").put("chaptersAvailable", 1)
            .put("chapters", JSONArray().put(JSONObject().put("id", 1).put("available", true).put("file", "chapters/00001.mp3"))).toString())

        val imported = BookFileImport.importFile(editedBook("v4.abook", edits = BookEdits.empty().put("title", "Của file")))

        assertEquals(existing, imported.id)
        assertFalse(File(root, "books/$existing/edits.json").exists())
        assertEquals("Truyện Y", Store.manifest(existing)!!.getString("title"))
        // sách của máy tính: sửa được ở đây và phần sửa gửi về máy tính (EditsSync) - không phải phần sửa trong file sách
        assertTrue(Store.manifest(existing)!!.getJSONObject("capabilities").getBoolean("sync"))
    }
}
