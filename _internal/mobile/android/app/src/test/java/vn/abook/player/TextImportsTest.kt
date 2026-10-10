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

    private fun titles(preview: JSONObject, ticked: Boolean = false): List<String> =
        preview.getJSONArray("chapters").let { rows ->
            (0 until rows.length()).map { rows.getJSONObject(it) }.filter { !ticked || it.getBoolean("included") }.map { it.getString("title") }
        }

    @Test
    fun an_epub_previews_the_chapter_list_python_shows_and_suggests_without_applying() {
        val staged = stageFile("epub3.epub")
        assertNull("chỉ PDF mới cần WebView", staged.pdf)
        val preview = TextImports.preview(staged.ref)
        val expected = sharedPreview("epub3")
        assertEquals(titles(expected), titles(preview, ticked = true))
        assertEquals(listOf(false, true, true, true), preview.getJSONArray("chapters").let { rows -> (0 until rows.length()).map { rows.getJSONObject(it).getBoolean("included") } })
        assertTrue("trang đề tựa rất ngắn: hiện ra, chưa tích", preview.getJSONArray("chapters").getJSONObject(0).getBoolean("short"))
        assertEquals(expected.getJSONObject("totals").toString(), preview.getJSONObject("totals").toString())
        assertEquals("Chuyến phà cuối ngày", preview.getString("title"))
        assertEquals("Lê Thử Nghiệm", preview.getString("author"))
        val notes = (0 until preview.getJSONArray("notes").length()).map { preview.getJSONArray("notes").getString(it) }
        assertTrue(notes.any { it.contains("ghi công") && it.contains("không tự bỏ") })
        assertTrue(StrictJson.equal(StrictJson.parse("""[{"chapter": 3, "line": "Dịch: Nhóm Lục Bình"}]"""), preview.getJSONArray("suggestions"))) // số hàng của bước xem trước
        assertTrue(preview.isNull("existing"))
        assertEquals("chưa ghi gì vào thư viện", 0, Store.books().size)
    }

    @Test
    fun the_preview_offers_the_footnotes_it_found_and_the_book_follows_only_what_the_listener_ticked() {
        val plain = TextImports.preview(stageFile("endnotes.epub").ref)
        val offer = plain.getJSONObject("footnotes")
        assertEquals(3, offer.getInt("found"))
        assertEquals(3, offer.getInt("marks"))
        assertEquals(3, offer.getJSONArray("examples").length())
        val rows = plain.getJSONArray("chapters")
        assertEquals(listOf("Chương 1: Bến đò", "Chương 2: Mưa", "Endnotes"), (0 until rows.length()).map { rows.getJSONObject(it).getString("title") })
        assertEquals("mặc định giữ chương Endnotes, chưa tích", listOf(true, true, false), (0 until rows.length()).map { rows.getJSONObject(it).getBoolean("included") })
        assertEquals("Chú thích", rows.getJSONObject(2).getString("matter"))

        val choice = BookImport.footnoteChoiceFromJson(JSONObject("""{"hideMarks": true, "notes": "end"}"""))
        val ticked = TextImports.preview(stageFile("endnotes.epub").ref, footnotes = choice)
        val tickedRows = ticked.getJSONArray("chapters")
        assertEquals(listOf("Chương 1: Bến đò", "Chương 2: Mưa"), (0 until tickedRows.length()).map { tickedRows.getJSONObject(it).getString("title") })
        assertEquals(offer.toString(), ticked.getJSONObject("footnotes").toString())
        assertFalse("sách không có chú thích thì không có đề xuất", TextImports.preview(stageFile("epub3.epub").ref).has("footnotes"))
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
    fun the_preview_knows_the_same_file_was_added_before_whatever_chapters_were_picked() {
        val fresh = stageFile("epub3.epub").ref
        assertTrue(TextImports.preview(fresh).isNull("sameSource"))
        val first = TextImports.create(fresh, "", cache, picks = listOf(2 to "", 3 to ""))
        val preview = TextImports.preview(stageFile("epub3.epub").ref)
        assertTrue("bộ chương mặc định khác bộ đã thêm", preview.isNull("existing"))
        val same = preview.getJSONObject("sameSource") // nhưng đúng file ấy đã được thêm
        assertEquals(first.getString("id"), same.getString("id"))
        assertEquals("Chuyến phà cuối ngày", same.getString("title"))
        assertEquals(2, same.getInt("chapters"))
        val whole = stageFile("whole.txt").ref
        TextImports.preview(whole)
        val oneChapter = TextImports.create(whole, "", cache)
        assertEquals("tách chương hay không vẫn là file ấy", oneChapter.getString("id"), TextImports.preview(stageFile("whole.txt").ref, splitChapters = true).getJSONObject("sameSource").getString("id"))
        assertTrue("file khác thì không", TextImports.preview(stageFile("plain.docx").ref).isNull("sameSource"))
    }

    @Test
    fun a_listener_unticks_chapters_renames_one_and_brings_back_a_short_item() {
        val ref = stageFile("epub3.epub").ref
        TextImports.preview(ref)
        val picks = TextImports.picksOf(
            JSONArray().put(JSONObject().put("index", 1).put("title", "Trang đề tựa")).put(JSONObject().put("index", 3).put("title", "  Người   khách  ")).put(JSONObject().put("index", 4)),
        )
        val added = TextImports.create(ref, "", cache, picks = picks)
        assertEquals("new", added.getString("how"))
        assertEquals(3, added.getInt("chapters"))
        val id = added.getString("id")
        val chapters = Store.manifest(id)!!.getJSONArray("chapters")
        assertEquals(listOf("Trang đề tựa", "Người khách", "Chương 3"), (0 until 3).map { chapters.getJSONObject(it).getString("title") }) // đúng thứ tự trong file
        assertEquals("Chuyến phà cuối ngày", Store.readText(id, "texts/1.txt")!!.trim()) // mục ngắn vào sách với chữ của nó
        assertTrue("đổi tên chỉ đổi tên - chữ của chương giữ nguyên", Store.readText(id, "texts/2.txt")!!.startsWith("Chương 2: Người khách lạ\n\nDịch: Nhóm Lục Bình"))
        // Bộ chương mặc định khác bộ này: một cuốn khác. Tên khác thì không (tên không nằm trong chữ).
        val other = stageFile("epub3.epub").ref
        assertTrue(TextImports.preview(other).isNull("existing"))
        assertEquals("new", TextImports.create(other, "", cache).getString("how"))
        val third = stageFile("epub3.epub").ref
        assertEquals(2, Store.books().size)
        TextImports.preview(third)
        assertEquals("existing", TextImports.create(third, "", cache, picks = listOf(2 to "Tên khác", 3 to "", 4 to "")).getString("how"))
    }

    @Test
    fun a_txt_keeps_its_own_heading_line_when_the_listener_renames_the_chapter() {
        val ref = stageFile("whole.txt").ref
        TextImports.preview(ref, splitChapters = true)
        val added = TextImports.create(ref, "", cache, picks = listOf(1 to "Lời mở", 3 to "Khách lạ"))
        val id = added.getString("id")
        val chapters = Store.manifest(id)!!.getJSONArray("chapters")
        assertEquals(listOf("Lời mở", "Khách lạ"), (0 until chapters.length()).map { chapters.getJSONObject(it).getString("title") })
        assertTrue(Store.readText(id, "texts/2.txt")!!.startsWith("Chương 2: Người khách lạ\nDịch: Nhóm Lục Bình"))
    }

    @Test
    fun a_choice_with_no_chapters_or_a_wrong_list_is_refused_and_adds_nothing() {
        val ref = stageFile("epub3.epub").ref
        TextImports.preview(ref)
        for (picks in listOf(emptyList(), listOf(9 to ""), listOf(2 to "", 2 to "Lặp"))) {
            try {
                TextImports.create(ref, "", cache, picks = picks)
                fail("lẽ ra phải từ chối: $picks")
            } catch (error: BookImport.Failed) {
                assertTrue(error.message!!, error.message!!.isNotEmpty())
            }
        }
        assertEquals(0, Store.books().size)
        for (bad in listOf(JSONArray().put(JSONObject().put("index", "2")), JSONArray().put(JSONObject().put("title", "x")), JSONArray().put(JSONObject().put("index", 2).put("title", 5)), JSONArray().put("2"))) {
            try {
                TextImports.picksOf(bad)
                fail("lẽ ra phải từ chối: $bad")
            } catch (error: BookImport.Failed) {
                assertEquals("Danh sách chương đã chọn không hợp lệ", error.message)
            }
        }
        assertNull(TextImports.picksOf(null))
        assertEquals(listOf(3 to "A", 1 to ""), TextImports.picksOf(JSONArray().put(JSONObject().put("index", 3).put("title", "A")).put(JSONObject().put("index", 1))))
    }

    @Test
    fun a_whole_story_txt_previews_as_one_chapter_offers_the_split_and_adds_what_the_last_preview_showed() {
        val ref = stageFile("whole.txt").ref
        val plain = TextImports.preview(ref)
        assertEquals(1, plain.getJSONArray("chapters").length())
        assertEquals(4, plain.getInt("splitOffer")) // mặc định KHÔNG tách, nhưng cho biết tách sẽ ra bao nhiêu chương
        assertEquals(3, plain.getInt("splitHeadings")) // nhãn: 3 dòng "Chương N", thêm phần "Mở đầu" thành 4 chương - như Python
        val split = TextImports.preview(ref, splitChapters = true)
        assertEquals(listOf("Mở đầu", "Chương 1: Bến phà lúc bình minh", "Chương 2: Người khách lạ", "Chương 3"), titles(split))
        assertEquals(4, split.getInt("splitOffer"))
        val added = TextImports.create(ref, "", cache)
        assertEquals(4, added.getInt("chapters"))
        assertFalse(TextImports.preview(stageFile("epub3.epub").ref).has("splitOffer")) // không có gì để tách thì không có khoá
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

    @Test
    fun a_file_sent_from_another_app_goes_to_the_preview_only_when_it_is_a_text_book() {
        val epub = "application/epub+zip"
        val docx = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        // Tên có đuôi đọc được: theo tên, kể cả khi nơi gửi nói octet-stream (Drive).
        assertEquals("Truyện.epub", TextImports.incomingName("application/octet-stream", "Truyện.epub"))
        assertEquals("a.TXT", TextImports.incomingName(null, "a.TXT"))
        // Tên không có đuôi: theo kiểu nội dung.
        assertEquals("Truyện.epub", TextImports.incomingName(epub, "Truyện"))
        assertEquals("Sách.docx", TextImports.incomingName(docx, null))
        assertEquals("Sách.pdf", TextImports.incomingName("application/pdf", ""))
        assertEquals("ghi chú.txt", TextImports.incomingName("text/plain; charset=utf-8", "ghi chú"))
        // File sách của app và loại lạ: đường mở file sách (BookFileImport) như trước.
        assertNull(TextImports.incomingName("application/vnd.ngdtuanh.abook+zip", "Sách.abook"))
        assertNull(TextImports.incomingName("text/plain", "Sách.abookproj"))
        assertNull(TextImports.incomingName("application/octet-stream", "Sách.abook"))
        assertNull(TextImports.incomingName("application/zip", "nhac.zip"))
        assertNull(TextImports.incomingName(null, null))
    }

    @Test
    fun an_app_book_file_picked_in_add_book_is_told_apart_from_a_text_book() {
        assertTrue(TextImports.isAppBookFile("application/octet-stream", "Sách.abook"))
        assertTrue(TextImports.isAppBookFile(null, "Sách.ABOOKPROJ"))
        assertTrue(TextImports.isAppBookFile("application/vnd.ngdtuanh.abook+zip", "Sách"))
        assertTrue(TextImports.isAppBookFile("application/vnd.ngdtuanh.abookproj+zip; x=1", null))
        assertFalse(TextImports.isAppBookFile("text/plain", "Truyện.txt"))
        assertFalse(TextImports.isAppBookFile("application/zip", "nhac.zip"))
        assertFalse(TextImports.isAppBookFile(null, null))
    }
}
