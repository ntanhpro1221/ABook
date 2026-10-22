package vn.abook.player

import java.io.File
import java.nio.file.Files
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class CoverRemovalParityTest {
    @Test fun removing_a_cover_does_not_invent_an_edit() {
        val cases = JSONArray(File("../../../tests/fixtures/book_edits/cover_removal.json").readText())
        for (i in 0 until cases.length()) {
            val case = cases.getJSONObject(i)
            val folder = Files.createTempDirectory("abook-no-cover").toFile()
            File(folder, "book.json").writeText("""{"title":"Sách","chapters":[]}""")
            if (case.getBoolean("base")) File(folder, "cover.jpg").writeText("base")
            if (case.getBoolean("edited")) {
                File(folder, "edits").mkdirs()
                File(folder, "edits/cover.jpg").writeText("edited")
                File(folder, "edits.json").writeText("""{"format":"abook-edits","version":1,"cover":{"color":"#112233","width":1,"height":1,"version":1}}""")
            }
            BookEdits.removeCover(folder)
            val edits = BookEdits.load(folder)
            assertEquals(case.getString("name"), case.getBoolean("hasCoverKey"), edits.has("cover"))
            if (case.getBoolean("hasCoverKey")) assertTrue(edits.isNull("cover"))
            assertFalse(File(folder, "edits/cover.jpg").exists())
        }
    }
}
