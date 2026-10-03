package vn.abook.player

import java.io.File
import java.nio.file.Files
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream
import org.json.JSONArray
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test

/**
 * Bộ nhập sách (BookImport.kt) trên bộ ví dụ DÙNG CHUNG với pytest (tests/import_fixtures.py, tests/fixtures/import/): bản Kotlin
 * phải ra đúng từng byte JSON mà abook/importers.py ra. Thư mục làm việc của Gradle là mobile/android/app.
 */
class BookImportTest {
    private val dir: File by lazy {
        val found = File("../../../tests/fixtures/import")
        if (!File(found, "expected/story.json").isFile) {
            fail("Không thấy bộ ví dụ dùng chung: ${found.absoluteFile} (sinh lại bằng runtime/.venv/Scripts/python.exe -m tests.import_fixtures)")
        }
        found.canonicalFile
    }

    private fun expectedText(name: String) = File(dir, "expected/$name.json").readText(Charsets.UTF_8)

    private fun dump(book: BookImport.Book) = StrictJson.dumps(BookImport.toMap(book)) + "\n"

    private fun titles(book: BookImport.Book) = book.chapters.map { it.title }

    private fun failure(block: () -> Unit): String =
        try {
            block()
            fail("lẽ ra phải từ chối")
            ""
        } catch (error: BookImport.Failed) {
            error.message ?: ""
        }

    @Test
    fun every_file_format_gives_exactly_what_python_gives() {
        for ((file, expected) in listOf(
            "epub3.epub" to "epub3", "epub2.epub" to "epub2", "headings.docx" to "headings", "plain.docx" to "plain", "txt" to "txt",
        )) {
            assertEquals("$file", expectedText(expected), dump(BookImport.importFile(File(dir, file))))
        }
    }

    @Test
    fun the_pdf_rules_layer_gives_what_python_gives_from_the_shared_raw_pages() {
        val raw = StrictJson.parse(File(dir, "pages/story.pages.json").readText(Charsets.UTF_8)) as org.json.JSONObject
        val all = raw.get("pages") as JSONArray
        val pages = (0 until all.length()).map { number ->
            val lines = all.get(number) as JSONArray
            (0 until lines.length()).map { lines.getString(it) }
        }
        val book = BookImport.fromPdfPages("story", pages, raw.getString("title"), raw.getString("author"))
        assertEquals(expectedText("story"), dump(book))
    }

    @Test
    fun a_pdf_with_no_text_layer_says_it_needs_ocr_in_the_same_words_as_python() {
        val said = failure { BookImport.fromPdfPages("scan", listOf(emptyList(), emptyList(), emptyList())) }
        assertEquals((StrictJson.parse(expectedText("scan")) as org.json.JSONObject).getString("error"), said)
    }

    @Test
    fun epub_follows_the_spine_and_takes_the_cover() {
        val book = BookImport.importFile(File(dir, "epub3.epub"))
        assertEquals("image/png", book.coverType)
        assertTrue(book.cover!!.take(4) == listOf<Byte>(0x89.toByte(), 'P'.code.toByte(), 'N'.code.toByte(), 'G'.code.toByte()))
        assertEquals(listOf("Chương 1: Bến phà lúc bình minh", "Chương 2: Người khách lạ", "Chương 3"), titles(book))
        assertTrue(book.chapters[0].text.endsWith("Nước lớn dần."))
        assertFalse(book.chapters.any { it.text.contains("không nằm trong thứ tự đọc chính") })
        assertEquals(listOf("Bỏ qua 1 trang chỉ có ảnh.", "Bỏ qua 1 mục rất ngắn (bìa, trang bản quyền?)."), book.notes.take(2)) // đếm, không kể tên file trong gói
        assertEquals("image/jpeg", BookImport.importFile(File(dir, "epub2.epub")).coverType)
    }

    @Test
    fun a_credit_line_is_suggested_never_removed() {
        val book = BookImport.importFile(File(dir, "epub3.epub"))
        assertTrue(book.chapters[1].text.startsWith("Dịch: Nhóm Lục Bình"))
        assertEquals(1, book.notes.count { it.contains("ghi công") })
        assertEquals(listOf(2 to "Dịch: Nhóm Lục Bình"), book.credits) // gợi ý có cấu trúc: bước xem trước cho chọn bỏ khỏi phần đọc
    }

    @Test
    fun txt_folder_reads_every_encoding_in_the_studio_order() {
        val book = BookImport.importFile(File(dir, "txt"))
        // Trùng số thì theo tên (01 trước 1), chữ số Ả Rập cũng là số, file ".txt" không có đuôi (Path.suffix), file trắng có ghi chú;
        // dòng đầu là tiêu đề chương thì nó là tên chương ("Chương hai"), không thì tên file.
        assertEquals(listOf("Chương 1", "Chương 1", "Chương hai", "9 Ngoại truyện", "Chương ba", "Chương ١١"), titles(book))
        assertTrue(book.chapters[0].text.startsWith("Bản trùng số"))
        assertEquals("Sương sớm\n\nChuyến phà đầu tiên rời bến lúc năm giờ.\nCậu bé đứng ở mạn thuyền.", book.chapters[1].text)
        assertEquals("Chương hai\n\nTiếng máy nổ trầm đục.", book.chapters[2].text)
        assertTrue(book.chapters[4].text.contains("Mưa rơi suốt chiều."))
        assertEquals("Bỏ qua mục không có chữ: Chương 3", book.notes[0])
    }

    @Test
    fun file_names_split_like_python_path() {
        assertEquals("" to ".txt", BookImport.suffixOf(".txt") to BookImport.stemOf(".txt"))
        assertEquals(".txt" to ".an", BookImport.suffixOf(".an.txt") to BookImport.stemOf(".an.txt"))
        assertEquals("" to "ten.", BookImport.suffixOf("ten.") to BookImport.stemOf("ten."))
        assertEquals(".TXT" to "a.b", BookImport.suffixOf("a.b.TXT") to BookImport.stemOf("a.b.TXT"))
    }

    @Test
    fun epub_reads_every_html_entity_like_python_even_in_the_table_of_contents() {
        val book = BookImport.importFile(File(dir, "epub3.epub"))
        assertTrue(book.chapters[0].text.contains("Ông Tám cười: “Phà cũ rồi.” © 1975 ă"))
        assertEquals("Chương 1: Bến phà lúc bình minh", book.chapters[0].title)
        // html.unescape: số ngoài phạm vi -> U+FFFD, ký tự điều khiển bỏ, tên lạ giữ nguyên, &#13; là \r.
        assertEquals("\uFFFD|\uFFFD|x|&khongco;|\r|&", BookImport.Markup.decode("&#xD800;|&#99999999999;|x&#1;|&khongco;|&#13;|&"))
        assertEquals("¬it; AT&T €", BookImport.Markup.decode("&notit; AT&T &#128;"))
    }

    @Test
    fun docx_reads_any_namespace_prefix_and_skips_the_word_table_of_contents() {
        val plain = BookImport.importFile(File(dir, "plain.docx")) // xmlns mặc định, không có tiền tố "w:"
        assertEquals(listOf("Mở đầu", "Chương 1: Bến phà lúc bình minh", "Chương 2: Người khách lạ"), titles(plain))
        val headings = BookImport.importFile(File(dir, "headings.docx"))
        assertEquals("Bỏ qua mục lục của tài liệu (3 dòng).", headings.notes[0])
        assertFalse(headings.chapters[0].text.contains("Người khách lạ"))
    }

    @Test
    fun text_encodings_follow_python_decode_text_bytes() {
        val sample = "Chương một: Tiếng Việt"
        assertEquals(sample, BookImport.decodeTextBytes("﻿$sample".toByteArray(Charsets.UTF_8)))
        assertEquals(sample, BookImport.decodeTextBytes(byteArrayOf(0xFF.toByte(), 0xFE.toByte()) + sample.toByteArray(Charsets.UTF_16LE)))
        assertEquals(sample, BookImport.decodeTextBytes(sample.toByteArray(Charsets.UTF_16LE)))
        assertEquals(sample, BookImport.decodeTextBytes(sample.toByteArray(Charsets.UTF_16BE)))
        assertEquals("Đúng", BookImport.decodeTextBytes("Đúng".toByteArray(charset("windows-1258"))))
        assertEquals("a\n\nb", BookImport.cleanText("a  \r\n\r\n\r\n\r\nb\n\n"))
        assertEquals("Chương 645", BookImport.chapterTitle("0645"))
        assertEquals("Mở đầu", BookImport.chapterTitle("  Mở đầu "))
    }

    @Test
    fun natural_order_puts_2_before_10() {
        val sorted = listOf("10.txt", "2.txt", "1.txt", "9 b.txt", "Z.txt", "a.txt").sortedWith(BookImport.naturalOrder)
        assertEquals(listOf("1.txt", "2.txt", "9 b.txt", "10.txt", "a.txt", "Z.txt"), sorted)
        // Trùng số: theo tên gốc, bất kể thứ tự thư mục liệt kê (io_utils.discover_txt_files); chữ số Unicode là số.
        assertEquals(listOf("001.txt", "01.txt", "1.txt"), listOf("1.txt", "01.txt", "001.txt").sortedWith(BookImport.naturalOrder))
        assertEquals(listOf("٢.txt", "10.txt"), listOf("10.txt", "٢.txt").sortedWith(BookImport.naturalOrder))
    }

    @Test
    fun the_chapter_heading_pattern_matches_what_python_matches() {
        for (line in listOf("Chương 12", "chương thứ hai", "Chapter IV", "Hồi 3: Gặp gỡ", "第十章 开始", "Quyển 2")) assertTrue(line, BookImport.isHeadingLine(line))
        for (line in listOf("Chương trình hôm nay", "Một câu bình thường.")) assertFalse(line, BookImport.isHeadingLine(line))
        assertFalse(BookImport.isHeadingLine("Chương 1 " + "x".repeat(130)))
    }

    @Test
    fun running_lines_only_go_when_they_repeat_and_chapter_headings_never_do() {
        val body = "Một đoạn văn đủ dài để không bị coi là tiêu đề hay số trang của cuốn sách thử nghiệm này."
        val pages = (1..5).map { n -> listOf("Chương $n") + (0 until 5).map { "$body Dòng $n.$it" } + "- $n -" }
        val book = BookImport.fromPdfPages("x", pages)
        assertEquals((1..5).map { "Chương $it" }, titles(book))
        assertTrue(book.chapters.none { it.text.contains("- ") })
        val filler = (0 until 5).map { "$body Dòng $it." }
        val two = BookImport.fromPdfPages("x", listOf(listOf("Sách thử") + filler + "1", listOf("Sách thử") + filler.reversed() + "2"))
        assertTrue(two.chapters[0].text.contains("Sách thử"))
        assertFalse(two.chapters[0].text.endsWith("2"))
        // Tiêu đề chạy mang số trang: bỏ ở mọi trang, ghi chú một lần.
        val numbered = BookImport.fromPdfPages("x", (1..5).map { n -> listOf("Sách thử · $n") + (0 until 5).map { "$body " + "x".repeat(n * 5 + it) } + "$n" })
        assertEquals(listOf("Bỏ dòng lặp đầu / cuối trang: “Sách thử · 1”"), numbered.notes.filter { it.startsWith("Bỏ dòng lặp") })
    }

    @Test
    fun a_soft_hyphen_at_a_line_end_is_dropped_but_a_real_hyphen_stays() {
        val filler = (0 until 6).map { "Một dòng văn xuôi dài vừa đủ để làm dòng đầy của trang thử số $it, kết thúc không có dấu chấm" }
        val pages = listOf(filler + listOf("Cuối trang là chữ khô­", "ng tách ở giữa từ, còn Hà-", "nội thì giữ gạch nối."))
        val text = BookImport.fromPdfPages("x", pages).chapters[0].text
        assertTrue(text.contains("không tách ở giữa từ") && text.contains("Hà-nội thì giữ gạch nối."))
        assertFalse(text.contains("­"))
    }

    @Test
    fun hostile_or_broken_files_say_why() {
        val work = Files.createTempDirectory("abook-import-test").toFile()
        val broken = File(work, "hong.docx").apply { writeBytes("not a zip".toByteArray()) }
        assertTrue(failure { BookImport.importFile(broken) }.contains("DOCX"))
        val hostile = File(work, "doc.docx")
        ZipOutputStream(hostile.outputStream()).use { zip ->
            zip.putNextEntry(ZipEntry("word/document.xml"))
            zip.write("""<?xml version="1.0"?><!DOCTYPE d [<!ENTITY a "aaaa">]><w:document xmlns:w="x"><w:body/></w:document>""".toByteArray())
            zip.closeEntry()
        }
        assertTrue(failure { BookImport.importFile(hostile) }.contains("entity"))
        val odd = File(work, "x.mobi").apply { writeBytes(byteArrayOf(1)) }
        assertTrue(failure { BookImport.importFile(odd) }.contains("Chưa đọc được"))
        val empty = File(work, "trong").apply { mkdirs() }
        File(empty, "1.txt").writeBytes("  \n".toByteArray())
        assertEquals("Không có chương nào có chữ", failure { BookImport.importFile(empty) })
        assertNotNull(work)
    }
}
