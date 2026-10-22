package vn.abook.player

import java.io.File
import org.junit.Assert.*
import org.junit.Test

class A84ImportTest {
    private val fixtures = File("../../../tests/fixtures/import").canonicalFile

    // JSONObject.similar không có trong vỏ android.jar mà trình biên dịch thấy trước: so bằng Map/List thường.
    private fun plain(value: Any?): Any? = when (value) {
        is org.json.JSONObject -> value.keys().asSequence().filter { !value.isNull(it) }.associateWith { plain(value.get(it)) }  // JSONObject(map) bỏ khoá null: null = vắng
        is org.json.JSONArray -> (0 until value.length()).map { plain(value.get(it)) }
        is Number -> value.toDouble()
        org.json.JSONObject.NULL -> null
        else -> value
    }

    @Test fun all_a84_shared_sources_and_preview_choices_match_python() {
        val cases = org.json.JSONArray(File(fixtures, "expected/a84_contracts.json").readText())
        for (i in 0 until cases.length()) {
            val case = cases.getJSONObject(i)
            val source = File(fixtures, case.getString("file"))
            try {
                val book = if (source.extension == "json") {
                    val raw = org.json.JSONArray(source.readText())
                    val pages = (0 until raw.length()).map { p -> raw.getJSONArray(p).let { a -> (0 until a.length()).map { a.getString(it) } } }
                    BookImport.fromPdfPages("Sách", pages)
                } else BookImport.importFile(source, splitChapters = true, keepShort = true)
                assertFalse(source.name, case.has("error"))
                assertEquals("${source.name}: book", plain(case.getJSONObject("book")), plain(org.json.JSONObject(BookImport.toMap(book))))
                assertEquals("${source.name}: preview", plain(case.getJSONObject("preview")), plain(TextBook.preview(book)))
            } catch (error: BookImport.Failed) {
                assertEquals(source.name, case.optString("error"), error.message)
            }
        }
    }

    @Test fun a84_19_pdf_scan_error_gives_you_a_next_action() {
        try { BookImport.fromPdfPages("Scan", List(3) { emptyList() }); fail("Phải báo không có chữ") }
        catch (error: BookImport.Failed) {
            val message = error.message.orEmpty()
            assertTrue(message.contains("chữ") && message.contains("Bạn") && message.contains("OCR"))
        }
    }

    @Test fun a84_17_unicode_filename_order_matches_shared_contract() {
        val a = org.json.JSONArray(File(fixtures, "a84_unicode_names.json").readText())
        val names = (0 until a.length()).map { a.getString(it) }
        assertEquals(listOf("A01.txt", "a1.txt", "Straße1.txt", "STRASSE2.txt", "Ánh2.txt", "ÁNH10.txt", "Σ1.txt", "ς2.txt", "σ10.txt"), names.reversed().sortedWith(BookImport.naturalOrder))
    }

    @Test fun a84_18_sparse_pdf_keeps_text_and_warns_about_image_pages() {
        val raw = org.json.JSONArray(File(fixtures, "a84_sparse_pdf.json").readText())
        val pages = (0 until raw.length()).map { i -> raw.getJSONArray(i).let { p -> (0 until p.length()).map { p.getString(it) } } }
        val book = BookImport.fromPdfPages("Sách", pages)
        assertEquals("Chương 1", book.chapters[0].title)
        assertTrue(book.chapters[0].text.contains("Một ngày yên ả"))
        assertTrue(book.notes.any { it.contains("9 trang không có chữ") })
        try { BookImport.fromPdfPages("Scan", List(10) { emptyList() }); fail("Scan không được nhận") } catch (_: BookImport.Failed) { }
    }

    @Test fun a84_15_bad_txt_bytes_are_reported_without_replacement() {
        for (name in listOf("le", "be", "tail")) {
            try {
                BookImport.importFile(File(fixtures, "a84_bad_$name.txt"))
                fail("Không được tự thay byte hỏng: $name")
            } catch (error: BookImport.Failed) {
                assertTrue(error.message.orEmpty().contains("Bạn"))
                assertTrue(error.message.orEmpty().contains("UTF-8"))
            }
        }
    }

    @Test fun a84_14_docx_inherited_and_outline_headings_split() {
        val book = BookImport.importFile(File(fixtures, "a84_styles.docx"))
        assertEquals(listOf("Bến đò", "Cơn mưa", "Đêm xuống", "Bình minh"), book.chapters.map { it.title })
    }

    @Test fun a84_13_lone_h1_is_kept_in_default_book() {
        for (name in listOf("meta", "plain")) {
            val book = BookImport.importFile(File(fixtures, "a84_h1_$name.docx"), keepShort = true)
            val kept = BookImport.selectChapters(book, BookImport.defaultPicks(book))
            val text = kept.chapters.joinToString("\n") { BookImport.chapterSource(kept, it) }
            assertEquals(1, Regex("Lời mở đầu").findAll(text).count())
            assertTrue(text.contains("Câu chuyện bắt đầu."))
        }
    }

    @Test fun a84_12_docx_reads_final_tracked_move_once() {
        val text = BookImport.importFile(File(fixtures, "a84_moves.docx")).chapters.joinToString(" ") { it.text }
        assertEquals(1, Regex("Xin chào\\.").findAll(text).count())
        assertEquals(1, Regex("Đã chuyển\\.").findAll(text).count())
        assertTrue(text.contains("Đã thêm."))
        assertFalse(text.contains("Đã xoá."))
    }

    @Test fun a84_11_txt_separating_controls_keep_words_and_heading_boundaries() {
        val book = BookImport.importFile(File(fixtures, "a84_controls.txt"), splitChapters = true)
        assertEquals(3, book.chapters.size)
        assertEquals(List(5) { listOf("Xin", "chào.") }.flatten(), book.chapters[0].text.split(Regex("\\s+")))
    }

    @Test fun a84_10_docx_breaks_keep_word_boundaries() {
        val text = BookImport.importFile(File(fixtures, "a84_breaks.docx")).chapters.joinToString(" ") { it.text }
        assertEquals(4, Regex("Xin chào\\.").findAll(text).count())
        assertFalse(text.contains("Xinchào"))
    }

    @Test fun a84_09_light_novel_special_sections_are_chapters() {
        val book = BookImport.importFile(File(fixtures, "a84_special.txt"), splitChapters = true)
        assertEquals(7, book.chapters.size)
        assertEquals(listOf("Lời bạt", "Minh họa", "Phần 1"), book.chapters.takeLast(3).map { it.title })
        assertEquals(7, BookImport.defaultPicks(book).size)
        assertFalse(BookImport.isHeadingLine("Lời bạt của tôi rất dài."))
    }

    @Test fun a84_08_prose_with_a_number_is_not_a_chapter_heading() {
        val book = BookImport.importFile(File(fixtures, "a84_prose.txt"), splitChapters = true)
        assertEquals(2, book.chapters.size)
        assertTrue(book.chapters[0].text.contains("Hồi hai đứa còn học"))
        assertTrue(book.chapters[0].text.contains("Chương 1 này hay thật."))
        assertTrue(BookImport.isHeadingLine("Chương XIV: " + "Một phụ đề khá dài ".repeat(3)))
    }

    @Test fun a84_07_volume_line_belongs_to_the_next_chapter() {
        val book = BookImport.importFile(File(fixtures, "a84_volume.txt"), splitChapters = true)
        assertEquals(2, book.chapters.size)
        assertEquals("Chương 1\nA.", book.chapters[0].text)
        assertTrue(book.chapters[1].text.startsWith("Tập 2\n"))
    }

    @Test fun a84_03_pdf_running_lines_are_reversible_proposals() {
        val raw = org.json.JSONArray(File(fixtures, "a84_pdf_lines.json").readText())
        val pages = (0 until raw.length()).map { i -> raw.getJSONArray(i).let { p -> (0 until p.length()).map { p.getString(it) } } }
        val book = BookImport.fromPdfPages("Sách", pages)
        assertEquals(pages.flatten().joinToString(" ").split(Regex("\\s+")), book.chapters.joinToString("\n") { it.text }.split(Regex("\\s+")))
        assertTrue(book.credits.any { it.second == "Tôi vẫn chờ anh." })
    }

    @Test fun a84_02_default_selection_keeps_every_preamble_word() {
        for (name in listOf("a84_lead_one.txt", "a84_lead_two.txt")) {
            val source = File(fixtures, name)
            val book = BookImport.importFile(source, splitChapters = true, keepShort = true)
            val selected = BookImport.selectChapters(book, BookImport.defaultPicks(book))
            assertEquals(name, source.readText().trim().split(Regex("\\s+")), selected.chapters.joinToString("\n") { it.text }.trim().split(Regex("\\s+")))
        }
    }

    @Test fun a84_01_docx_notes_and_call_marks_stay_until_explicitly_removed() {
        val source = File(fixtures, "notes.docx")
        val book = BookImport.importFile(source)
        val text = book.chapters.joinToString("\n") { it.text }
        assertTrue(text.contains("Lời chú thứ nhất."))
        assertTrue(text.contains("Lời chú cuối sách về cơn mưa."))
        assertTrue(text.contains("¹"))
        assertEquals(4, book.footnoteMarks)
        val dropped = BookImport.importFile(source, footnotes = BookImport.FootnoteChoice(true, "drop"))
        assertFalse(dropped.chapters.any { it.text.contains("Lời chú") || it.text.contains("¹") })
        assertEquals(BookImport.toMap(book), BookImport.toMap(BookImport.importFile(source)))
    }
}
