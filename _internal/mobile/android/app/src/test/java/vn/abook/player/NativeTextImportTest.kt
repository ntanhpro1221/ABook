package vn.abook.player

import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import java.io.File
import java.nio.file.Files

/** Typed native path has the same core behavior as the JSON adapter, without putting text through JSON. */
class NativeTextImportTest {
    private lateinit var cache: File
    @Before fun store() {
        BookEditsFixtures.useStoreRoot(Files.createTempDirectory("native-import").toFile())
        cache = Files.createTempDirectory("native-import-cache").toFile()
        TextImports.codec = null
    }

    @Test fun typedPreviewAndCreateKeepSourceTextAndRenumberChapters() {
        val original = "Chương 1\n\nDịch: Nhóm Lục Bình\n\nMột người khách đang chờ bên sông.\n\nChương 2\n\nNgười khách trở về nhà."
        val staged = TextImports.stageFile("Truyện.txt") { original.byteInputStream() }
        val whole = TextImports.prepare(staged.ref)
        assertTrue(whole.chapters.single().text.contains("Dịch: Nhóm Lục Bình"))
        val split = TextImports.prepare(staged.ref, splitChapters = true)
        val expected = BookImport.chapterSource(split, split.chapters[1])
        val result = TextImports.createBook(staged.ref, "Tên của bạn", cache, picks = listOf(2 to "Trở về"))
        assertEquals(1, result.chapters)
        val manifest = Store.manifest(result.id)!!
        assertEquals("Tên của bạn", manifest.getString("title"))
        val chapter = manifest.getJSONArray("chapters").getJSONObject(0)
        assertEquals("Trở về", chapter.getString("title"))
        assertEquals(expected, Store.file(result.id, chapter.getString("text")).readText(Charsets.UTF_8))
    }

    @Test fun creditSuggestionNeverChangesTextUnlessExplicitlyAcceptedAsSkip() {
        val original = "Dịch: Nhóm Lục Bình\n\nMột ngày nọ, người khách bước xuống chuyến phà cuối ngày."
        val staged = TextImports.stageFile("Truyện.txt") { original.byteInputStream() }
        TextImports.prepare(staged.ref)
        val result = TextImports.createBook(staged.ref, "Truyện", cache)
        val before = Store.manifest(result.id)!!.getJSONArray("chapters").getJSONObject(0)
        val text = Store.file(result.id, before.getString("text")).readBytes()
        assertFalse(before.has("skip"))
        BookEdits.setSkipLine(Store.bookDir(result.id), listOf(1), "Dịch: Nhóm Lục Bình", true)
        val accepted = Store.manifest(result.id)!!.getJSONArray("chapters").getJSONObject(0)
        assertEquals("Dịch: Nhóm Lục Bình", accepted.getJSONArray("skip").getString(0))
        assertArrayEquals(text, Store.file(result.id, before.getString("text")).readBytes())
        BookEdits.setSkipLine(Store.bookDir(result.id), listOf(1), "Dịch: Nhóm Lục Bình", false)
        val reverted = Store.manifest(result.id)!!.getJSONArray("chapters").getJSONObject(0)
        assertFalse(reverted.has("skip") && reverted.getJSONArray("skip").length() > 0)
        assertArrayEquals(text, Store.file(result.id, before.getString("text")).readBytes())
    }

    @Test fun typedAndJsonPreviewsMatchAndFootnotesAreOptIn() {
        val source = File("../../../tests/fixtures/import/notes2.epub")
        val staged = TextImports.stageFile(source.name) { source.inputStream() }
        val typed = TextImports.prepare(staged.ref)
        val json = TextImports.preview(staged.ref)
        assertEquals(typed.title, json.getString("title"))
        assertEquals(typed.chapters.size, json.getJSONArray("chapters").length())
        assertEquals(typed.chapters.map { it.text }, TextImports.prepare(staged.ref, footnotes = BookImport.FootnoteChoice()).chapters.map { it.text })
        assertTrue(typed.footnoteFound > 0)
        assertNotEquals(typed.chapters.map { it.text }, TextImports.prepare(staged.ref,
            footnotes = BookImport.FootnoteChoice(hideMarks = true, notes = "drop")).chapters.map { it.text })
    }
}
