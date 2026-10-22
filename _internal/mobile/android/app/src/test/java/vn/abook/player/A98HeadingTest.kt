package vn.abook.player

import java.io.File
import org.junit.Assert.*
import org.junit.Test

/** Soát a98 F5: cùng bộ ca thử với Python (tests/test_a98_import_fixes.py) - đoạn văn mở bằng "Hồi/Phần…" kết bằng nháy cong không phải tiêu đề chương. */
class A98HeadingTest {
    private val fixture = File("../../../tests/fixtures/import/a98_heading_lines.json").canonicalFile

    @Test fun txt_heading_lines_match_python() {
        val cases = org.json.JSONArray(fixture.readText())
        assertTrue(cases.length() > 20)
        for (i in 0 until cases.length()) {
            val case = cases.getJSONArray(i)
            val line = case.getString(0)
            assertEquals(line, case.getBoolean(1), BookImport.isHeadingLine(line, BookImport.TXT_HEADING))
        }
    }

    @Test fun a_curly_quote_ending_keeps_a_story_in_one_chapter() {
        val body = "Trời mưa rất to, anh Nam đứng đợi ở cổng trường đến tối mới thấy cô ấy quay lại.\n\n"
        val text = "Truyện Thử\n\nChương 1: Mở\n\n" + body + "Hồi năm ngoái anh ấy đã nói với tôi: “Anh sẽ không đi đâu cả.”\n\n" + body +
            "Chương 2: Hai\n\n" + body + "Hồi hai giờ chiều cô ấy hỏi: “Anh có đi không?”\n\n" + body + "Chương 3: Ba\n\n" + body
        val file = File.createTempFile("a98", ".txt").also { it.deleteOnExit(); it.writeText(text) }
        val book = BookImport.importFile(file, splitChapters = true, keepShort = true)
        assertEquals(listOf("Mở đầu", "Chương 1: Mở", "Chương 2: Hai", "Chương 3: Ba"), book.chapters.map { it.title })
    }

    @Test fun ends_sentence_looks_past_closing_marks() {
        assertTrue(BookImport.endsSentence("anh đi rồi.”"))
        assertTrue(BookImport.endsSentence("thế à?)"))
        assertFalse(BookImport.endsSentence("“Gặp gỡ”"))
        assertFalse(BookImport.endsSentence("(hết)"))
        assertFalse(BookImport.endsSentence(""))
    }
}
