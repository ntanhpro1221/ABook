package vn.abook.player

import java.io.File
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class PackageScriptViewTest {
    @Test fun importedRowsOfferManualRangesWithoutInventingScenesOrEditingTheBook() {
        val dir = BookEditsFixtures.copyBase(BookEditsFixtures.tempDir("scope-package"))
        // Replace read-along text with original examples for this scenario.
        val scriptFile = File(dir, "scripts/1.json")
        val script = JSONObject(scriptFile.readText())
        val rows = script.getJSONArray("segments")
        for (at in 0 until rows.length()) rows.getJSONObject(at).put("text", "Câu tự viết số $at.")
        scriptFile.writeText(script.toString())
        val stable = rows.getJSONObject(0).getString("stableId")
        File(dir, BookEdits.HOLDER_FILE).writeText(JSONObject().put("speakers", JSONObject().put(stable,
            JSONObject().put("name", "Khách").put("shown", "Khách").put("requestedAt", 1))).toString())
        val before = dir.walkTopDown().filter { it.isFile }.associate { it.relativeTo(dir).path to it.readBytes().toList() }
        val view = PackageScriptView.chapter(dir, 1)!!
        val lines = view.getJSONArray("lines")
        assertEquals(rows.length(), lines.length())
        for (at in 0 until lines.length()) assertTrue(lines.getJSONObject(at).isNull("scene"))
        assertEquals("Khách", lines.getJSONObject(0).getJSONObject("wish").getString("value"))
        assertEquals(64, view.getString("scopeRevision").length)
        assertEquals(before, dir.walkTopDown().filter { it.isFile }.associate { it.relativeTo(dir).path to it.readBytes().toList() })
        assertTrue(PackageScriptView.contents(dir).getJSONArray("chapters").length() > 0)
    }
}
