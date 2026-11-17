package vn.abook.player

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.io.File

/**
 * Same cases as tests/test_book_metadata.py (tests/fixtures/book_metadata): saving descriptive fields records only real
 * changes, and a TXT header summary ends where Python ends it.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class BookMetadataParityTest {
    @get:Rule val temp = TemporaryFolder()

    private fun fixture(name: String) = JSONObject(File("../../../tests/fixtures/book_metadata/$name").readText())

    private fun metadataOf(raw: JSONObject): JSONObject {
        val out = JSONObject()
        for (key in BookMetadata.fields) if (raw.has(key)) out.put(key, raw.get(key))
        return out
    }

    @Test fun savingMetadataRecordsOnlyRealChanges() {
        val cases = fixture("set_metadata.json").getJSONArray("cases")
        for (index in 0 until cases.length()) {
            val case = cases.getJSONObject(index)
            val name = case.getString("name")
            val folder = temp.newFolder()
            val book = JSONObject().put("format", "abook-book/1").put("title", "Hồ giấy").put("version", "v").put("chapters", org.json.JSONArray())
            val base = case.getJSONObject("base")
            for (key in base.keys()) book.put(key, base.get(key))
            File(folder, "book.json").writeText(book.toString())
            BookEdits.setMetadata(folder, case.getJSONObject("changes"))
            val edits = BookEdits.load(folder)
            val expected = case.getJSONObject("edits")
            assertTrue("$name: edits ${metadataOf(edits)}", StrictJson.equal(expected, metadataOf(edits)))
            assertEquals(name, expected.length(), BookEdits.count(edits))
            val shown = metadataOf(BookEdits.applyManifest(book, edits))
            assertTrue("$name: shown $shown", StrictJson.equal(case.getJSONObject("shown"), shown))
        }
    }

    @Test fun headerSummaryEndsWherePythonEndsIt() {
        val root = fixture("header.json")
        val filler = root.getString("fillerLine")
        val cases = root.getJSONArray("cases")
        for (index in 0 until cases.length()) {
            val case = cases.getJSONObject(index)
            val text = case.getString("text") + (0 until case.getInt("filler")).joinToString("\n") { filler.replace("{n}", it.toString()) }
            val found = BookImport.headerMetadata(text)
            if (case.has("expected")) {
                assertTrue("${case.getString("name")}: $found", StrictJson.equal(case.getJSONObject("expected"), found))
            } else {
                assertTrue(case.getString("name"), found.getString("summary").lines().size < case.getInt("summaryLinesBelow"))
            }
        }
    }

    /** The real import path (chapter text already cleaned, which folds blank lines) ends the summary where the parser does. */
    @Test fun headerSummaryThroughTheRealImportMatchesTheParser() {
        val root = fixture("header.json")
        val filler = root.getString("fillerLine")
        val cases = root.getJSONArray("cases")
        for (index in 0 until cases.length()) {
            val case = cases.getJSONObject(index)
            val name = case.getString("name")
            val file = File(temp.newFolder(), "story.txt")
            file.writeText(case.getString("text") + (0 until case.getInt("filler")).joinToString("\n") { filler.replace("{n}", it.toString()) })
            val found = metadataOf(BookImport.importFile(file).metadata)
            if (case.has("expected")) {
                assertTrue("$name: $found", StrictJson.equal(case.getJSONObject("expected"), found))
            } else {
                assertTrue(name, found.getString("summary").lines().size < case.getInt("summaryLinesBelow"))
            }
        }
    }
}
