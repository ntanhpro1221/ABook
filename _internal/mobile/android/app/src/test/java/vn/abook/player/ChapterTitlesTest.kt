package vn.abook.player

import java.io.File
import java.text.Normalizer
import org.json.JSONArray
import org.junit.Assert.assertEquals
import org.junit.Test

class ChapterTitlesTest {
    @Test fun sharedOriginalCases() {
        val cases = JSONArray(File("../../../tests/fixtures/chapter_titles.json").readText())
        for (i in 0 until cases.length()) {
            val row = cases.getJSONArray(i)
            val text = row.getString(0)
            val expected = row.getString(1)
            assertEquals("case $i", expected, ChapterTitles.firstHeading(text))
            assertEquals("NFD case $i", expected, ChapterTitles.firstHeading(Normalizer.normalize(text, Normalizer.Form.NFD)))
        }
    }

    @Test fun metadataKeepsTheSource() {
        val folder = java.nio.file.Files.createTempDirectory("chapter-titles").toFile()
        try {
            val source = File(folder, "013.txt")
            val text = "Đoạn kết\n\nChiếc hộp nằm trên bàn.\n"
            source.writeText(text)
            val book = BookImport.importFile(folder)
            val chapter = book.chapters.single()
            assertEquals("Chương 13", chapter.title)
            assertEquals("Đoạn kết", chapter.name)
            assertEquals(text, BookImport.chapterSource(book, chapter))
            assertEquals(text, source.readText())
            assertEquals("Đoạn kết", BookImport.selectChapters(book, listOf(1 to "")).chapters.single().name)
            assertEquals("Chương 8", ChapterTitles.display("013", "Một chiếc lá rơi.", 8))
            assertEquals("Chương 13", ChapterTitles.display("013", "Một chiếc lá rơi.", null))
            assertEquals(listOf(1, null, 3), ChapterTitles.fallbackPositions(listOf("767", "0000 Mở đầu", "768")))
            assertEquals(listOf(1, 2), ChapterTitles.fallbackPositions(listOf("187", "188")))
            assertEquals(listOf(1), ChapterTitles.fallbackPositions(listOf("١١")))
            assertEquals("Chương 1", ChapterTitles.display("١١", "Một chiếc lá rơi.", 1))
            assertEquals(listOf(1, 2), ChapterTitles.fallbackPositions(listOf("003", "013")))
        } finally { folder.deleteRecursively() }
    }
}
