package vn.abook.player

import java.io.File
import java.io.FileInputStream
import java.nio.file.Files
import org.json.JSONArray
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Before
import org.junit.Test

/**
 * "Thêm sách từ file…" trên điện thoại (TextImports.kt, phần không dính Android của LibraryPlugin) trên bộ ví dụ nhập sách dùng chung
 * (tests/fixtures/import/): chép thứ đã chọn, xem trước danh sách chương bằng luật của BookImport, nhập thành sách chỉ-có-chữ - kể cả PDF,
 * nơi WebView (pdf.js) lấy chữ từng trang rồi đưa sang Kotlin (cầu `previewImport` với `pages`).
 */
class TextImportsTest {
    private lateinit var root: File
    private lateinit var cache: File

    private val imports: File by lazy {
        val found = File("../../../tests/fixtures/import")
        if (!File(found, "expected/story.json").isFile) fail("Không thấy bộ ví dụ nhập sách: ${found.absoluteFile}")
        found.canonicalFile
    }

    private val textBooks: File by lazy { File("../../../tests/fixtures/text_books").canonicalFile }

    @Before
    fun setUp() {
        root = Files.createTempDirectory("abook-imports").toFile()
        cache = Files.createTempDirectory("abook-imports-cache").toFile()
        BookEditsFixtures.useStoreRoot(root)
        TextImports.codec = null
    }

    @After
    fun tearDown() {
        TextImports.sweep()
    }

    private fun stageFile(relative: String): TextImports.Staged {
        val file = File(imports, relative)
        return TextImports.stageFile(file.name) { FileInputStream(file) }
    }

    private fun stageFolder(relative: String): TextImports.Staged {
        val folder = File(imports, relative)
        return TextImports.stageFolder(folder.name, folder.listFiles()!!.map { child -> child.name to { FileInputStream(child) as java.io.InputStream? } })
    }

    @Test
    fun a_long_chapter_file_name_keeps_its_txt_ending_and_no_two_files_collide() {
        val long = "[001] " + "Một tên chương light novel rất dài ".repeat(5)
        val staged = TextImports.stageFolder("Sách dài", listOf(
            "${long}phần 1.txt" to { "Chương 1\n\nMột.".byteInputStream() as java.io.InputStream? },
            "${long}phần 2.txt" to { "Chương 2\n\nHai.".byteInputStream() as java.io.InputStream? },
        ))
        val preview = TextImports.preview(staged.ref)
        assertEquals(2, preview.getJSONArray("chapters").length()) // trước đây: cắt còn 120 ký tự -> mất ".txt" -> không còn chương nào
        assertTrue(TextImports.safeName("x".repeat(200) + ".txt", "c").let { it.length == 120 && it.endsWith(".txt") })
        val used = HashSet<String>()
        assertEquals(listOf("a.txt", "a (2).txt", "A (3).txt"), listOf("a.txt", "a.txt", "A.txt").map { TextImports.uniqueName(it, used) })
    }

    private fun pagesOf(name: String): Triple<List<List<String>>, String, String> {
        val raw = StrictJson.parse(File(imports, "pages/$name.pages.json").readText(Charsets.UTF_8)) as JSONObject
        return Triple(TextImports.pagesOf(raw.getJSONArray("pages"))!!, raw.getString("title"), raw.getString("author"))
    }

    private fun sharedPreview(name: String): JSONObject {
        val all = (StrictJson.parse(File(textBooks, "cases.json").readText(Charsets.UTF_8)) as JSONObject).getJSONArray("cases")
        return (0 until all.length()).map { all.getJSONObject(it) }.first { it.getString("name") == name }.getJSONObject("expected").getJSONObject("preview")
    }

    private fun titles(preview: JSONObject): List<String> =
        preview.getJSONArray("chapters").let { rows -> (0 until rows.length()).map { rows.getJSONObject(it).getString("title") } }

    @Test
    fun an_epub_previews_the_chapter_list_python_shows_and_suggests_without_applying() {
        val staged = stageFile("epub3.epub")
        assertNull("chỉ PDF mới cần WebView", staged.pdf)
        val preview = TextImports.preview(staged.ref)
        val expected = sharedPreview("epub3")
        assertEquals(titles(expected), titles(preview))
        assertEquals(expected.getJSONObject("totals").toString(), preview.getJSONObject("totals").toString())
        assertEquals("Chuyến phà cuối ngày", preview.getString("title"))
        assertEquals("Lê Thử Nghiệm", preview.getString("author"))
        val notes = (0 until preview.getJSONArray("notes").length()).map { preview.getJSONArray("notes").getString(it) }
        assertTrue(notes.any { it.contains("ghi công") && it.contains("không tự bỏ") })
        assertTrue(StrictJson.equal(StrictJson.parse("""[{"chapter": 2, "line": "Dịch: Nhóm Lục Bình"}]"""), preview.getJSONArray("suggestions")))
        assertTrue(preview.isNull("existing"))
        assertEquals("chưa ghi gì vào thư viện", 0, Store.books().size)
    }

    @Test
    fun the_preview_already_knows_the_book_is_there_and_a_separate_copy_can_still_be_added() {
        val first = TextImports.create(stageFile("epub3.epub").ref.also { TextImports.preview(it) }, "", cache)
        val again = stageFile("epub3.epub")
        val existing = TextImports.preview(again.ref).getJSONObject("existing")
        assertEquals(first.getString("id"), existing.getString("id")) // hỏi ngay ở bước xem trước
        assertEquals("Chuyến phà cuối ngày", existing.getString("title"))
        val copy = TextImports.create(again.ref, "Bản thứ hai", cache, separate = true)
        assertEquals("new", copy.getString("how"))
        assertEquals(first.getString("id") + "-2", copy.getString("id"))
        assertEquals("Bản thứ hai", Store.manifest(copy.getString("id"))!!.getString("title"))
    }

    @Test
    fun a_credit_line_suggestion_is_skipped_only_when_the_listener_accepts_it() {
        val id = TextImports.create(stageFile("epub3.epub").ref.also { TextImports.preview(it) }, "", cache).getString("id")
        fun call(method: String, path: String, body: JSONObject? = null) = LocalStudio.handle(method, "/api/books/$id$path", body)
        val (status, before) = call("GET", "/suggestions")
        assertEquals(200, status)
        assertTrue(StrictJson.equal(
            StrictJson.parse("""{"suggestions": [{"chapter": 2, "title": "Chương 2: Người khách lạ", "line": "Dịch: Nhóm Lục Bình", "skipped": false}]}"""),
            before,
        ))
        val (putStatus, put) = call("PUT", "/skip", JSONObject().put("line", "Dịch: Nhóm Lục Bình").put("chapters", JSONArray().put(2)).put("skip", true))
        assertEquals(200, putStatus)
        assertTrue(StrictJson.equal(StrictJson.parse("""{"skip": {"2": ["Dịch: Nhóm Lục Bình"]}}"""), put))
        assertEquals(400, call("PUT", "/skip", JSONObject().put("line", "Dịch: A").put("chapters", JSONArray().put(9))).first)
        val chapters = Store.manifest(id)!!.getJSONArray("chapters")
        assertEquals("""["Dịch: Nhóm Lục Bình"]""", chapters.getJSONObject(1).getJSONArray("skip").toString()) // màn đọc + đọc to bỏ qua
        assertFalse(chapters.getJSONObject(0).has("skip"))
        assertTrue("chữ của sách không đổi", Store.file(id, "texts/2.txt").readText().contains("Dịch: Nhóm Lục Bình"))
        assertTrue((call("GET", "/suggestions").second as JSONObject).getJSONArray("suggestions").getJSONObject(0).getBoolean("skipped"))
    }

    @Test
    fun a_pdf_goes_through_the_webview_pages_and_the_kotlin_rules() {
        val staged = stageFile("story.pdf")
        assertNotNull("WebView đọc bản sao này bằng pdf.js", staged.pdf)
        assertTrue(staged.pdf!!.isFile)
        try {
            TextImports.preview(staged.ref)
            fail("PDF cần chữ do pdf.js lấy")
        } catch (error: BookImport.Failed) {
            assertTrue(error.message!!, error.message!!.contains("PDF"))
        }
        val (pages, title, author) = pagesOf("story")
        val preview = TextImports.preview(staged.ref, pages, title, author)
        assertEquals(titles(sharedPreview("story")), titles(preview))
        assertEquals(sharedPreview("story").getJSONObject("totals").toString(), preview.getJSONObject("totals").toString())
        val created = TextImports.create(staged.ref, "", cache)
        assertEquals("new", created.getString("how"))
        assertEquals(3, created.getInt("chapters"))
        assertEquals(sharedExpected("story").getString("contentKey"), created.getString("id"))
        assertFalse("bản sao PDF được dọn", staged.pdf!!.exists())
    }

    private fun sharedExpected(name: String): JSONObject {
        val all = (StrictJson.parse(File(textBooks, "cases.json").readText(Charsets.UTF_8)) as JSONObject).getJSONArray("cases")
        return (0 until all.length()).map { all.getJSONObject(it) }.first { it.getString("name") == name }.getJSONObject("expected")
    }

    @Test
    fun a_pdf_with_no_text_layer_says_it_needs_ocr() {
        val staged = stageFile("scan.pdf")
        try {
            TextImports.preview(staged.ref, listOf(emptyList(), emptyList(), emptyList()))
            fail("PDF scan")
        } catch (error: BookImport.Failed) {
            assertTrue(error.message!!, error.message!!.startsWith("PDF này là ảnh chụp"))
        }
    }

    @Test
    fun a_text_folder_comes_in_with_its_chapters_in_natural_order() {
        val staged = stageFolder("txt")
        assertEquals("txt", staged.name)
        val preview = TextImports.preview(staged.ref)
        assertEquals(titles(sharedPreview("txt")), titles(preview))
        val created = TextImports.create(staged.ref, "Truyện của tôi", cache)
        assertEquals(sharedExpected("txt").getString("contentKey"), created.getString("id"))
        assertEquals("Truyện của tôi", Store.manifest(created.getString("id"))!!.getString("title"))
    }

    @Test
    fun adding_the_same_file_twice_says_it_is_already_there_and_keeps_the_book_unchanged() {
        val first = stageFile("epub3.epub")
        TextImports.preview(first.ref)
        val one = TextImports.create(first.ref, "", cache)
        val second = stageFile("epub3.epub")
        TextImports.preview(second.ref)
        val two = TextImports.create(second.ref, "Tên khác", cache)
        assertEquals("new", one.getString("how"))
        assertEquals("existing", two.getString("how"))
        assertEquals(one.getString("id"), two.getString("id"))
        assertEquals(1, Store.books().size)
        assertEquals("Chuyến phà cuối ngày", Store.manifest(one.getString("id"))!!.getString("title"))
        assertEquals("không để lại file tạm", 0, cache.listFiles()!!.size)
    }

    @Test
    fun the_imported_text_is_the_file_studio_would_read_and_credit_lines_stay() {
        val staged = stageFile("epub3.epub")
        TextImports.preview(staged.ref)
        val id = TextImports.create(staged.ref, "", cache).getString("id")
        val second = Store.readText(id, "texts/2.txt")!!
        assertTrue(second, second.startsWith("Chương 2: Người khách lạ\n\nDịch: Nhóm Lục Bình"))
        assertTrue(second.endsWith("ngay bên kia sông.\n"))
    }

    @Test
    fun a_choice_that_is_not_a_book_is_refused_in_words_the_user_can_act_on() {
        try {
            TextImports.stageFile("anh.png") { "x".byteInputStream() }
            fail("không phải file sách")
        } catch (error: BookImport.Failed) {
            assertTrue(error.message!!, error.message!!.startsWith("Chưa đọc được file .png"))
        }
        try {
            TextImports.stageFolder("rong", listOf("a.md" to { "x".byteInputStream() }))
            fail("thư mục không có TXT")
        } catch (error: BookImport.Failed) {
            assertEquals("Thư mục này không có file .txt nào nằm ngay bên trong", error.message)
        }
        try {
            TextImports.create("khongco", "", cache)
            fail("lần chọn đã hết hạn")
        } catch (error: BookImport.Failed) {
            assertTrue(error.message!!.contains("chọn lại"))
        }
        assertEquals(0, File(root, "imports").listFiles()?.size ?: 0)
    }

    @Test
    fun a_discarded_choice_leaves_nothing_and_a_sweep_clears_what_a_killed_app_left() {
        val staged = stageFile("epub3.epub")
        TextImports.preview(staged.ref)
        TextImports.discard(staged.ref)
        assertEquals(0, File(root, "imports").listFiles()?.size ?: 0)
        stageFile("epub2.epub")
        TextImports.sweep()
        assertFalse(File(root, "imports").exists())
        try {
            TextImports.discard("../x")
        } catch (error: Exception) {
            fail("bỏ một mã lạ không được làm hỏng gì: $error")
        }
    }

    @Test
    fun pages_from_the_bridge_are_read_as_lists_of_lines() {
        assertNull(TextImports.pagesOf(null))
        val array = JSONArray().put(JSONArray().put("a").put("b")).put(JSONArray())
        assertEquals(listOf(listOf("a", "b"), emptyList()), TextImports.pagesOf(array))
    }
}
