package vn.abook.player

import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test
import java.io.File

/** Opt-in import audit for the two local packages; no book content is stored in Git. */
class CastPackageAuditTest {
    @Test
    fun importLocalPackagesAndKeepTheirCast() {
        val arguments = InstrumentationRegistry.getArguments()
        assumeTrue(arguments.getString("castPackageAudit") == "true")
        val only = arguments.getString("castPackage")
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        assertTrue("Private audit package required", context.packageName.endsWith(".castview"))
        assertTrue("Emulator required", android.os.Build.HARDWARE in listOf("ranchu", "goldfish"))
        Store.init(context)
        val results = JSONArray()
        data class Case(val name: String, val main: Int, val extras: Int, val voices: Int)
        for ((name, main, extras, voices) in listOf(
            Case("hello", 4, 20, 2), Case("nhung", 3, 17, 1),
        ).filter { only == null || it.name == only }) {
            val input = File(context.filesDir, "castview-in/$name.abook")
            assertTrue("Missing local package $name", input.isFile)
            val imported = BookFileImport.importFile(input)
            val book = Store.manifest(imported.id)
            assertNotNull(book)
            val cast = JSONObject(File(Store.bookDir(imported.id), "cast.json").readText())
            assertEquals(main, cast.getJSONArray("characters").length())
            assertEquals(extras, cast.getJSONArray("extras").length())
            val narrator = cast.getJSONObject("narrator")
            assertEquals(voices, 1 + (narrator.optJSONArray("chapterVoices")?.length() ?: 0))
            for (mark in listOf("qualityPassed", "qualityWarning", "failedLines", "levelQa", "Cần nghe lại")) {
                assertFalse("QA mark $mark in $name", book.toString().contains(mark))
            }
            val parsed = vn.abook.player.ui.data.Cast.parse(cast.toString())!!
            assertEquals(voices, vn.abook.player.ui.data.Cast.narratorRows(parsed.narrator).size)
            results.put(JSONObject().put("name", name).put("id", imported.id).put("main", main)
                .put("extras", extras).put("narrators", voices).put("title", imported.title))
        }
        File(context.filesDir, "castview-import-results.json").writeText(results.toString(2))
    }
}
