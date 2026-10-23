package vn.abook.player

import java.io.File
import java.nio.file.Files
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test

class BookmarkParityTest {
    @Test fun undo_keeps_the_id_and_survives_an_old_delete_and_edit_from_the_other_device() {
        val spec = JSONObject(File("../../../tests/fixtures/listening_records/restore_bookmark.json").readText())
        val mark = spec.getJSONObject("mark")
        val gone = JSONObject().put(mark.getString("id"), spec.getDouble("deletedAt"))
        val goneRevs = JSONObject().put(mark.getString("id"), spec.getJSONObject("deletedRev"))
        Store.mergeRemote("b", JSONObject().put("deleted", gone).put("_deletedRevs", goneRevs))
        val restored = Store.restoreBookmark("b", mark)
        val expected = JSONObject(mark.toString()).put("at", restored.getDouble("at")).put("rev", restored.getJSONObject("rev"))
        assertTrue(StrictJson.equal(expected, restored))
        assertTrue(restored.getDouble("at") > spec.getDouble("deletedAt"))
        assertTrue("undo keeps the tombstone (a118 bug 6)", Store.state("b").getJSONObject("deleted").has(mark.getString("id")))
        Store.mergeRemote("b", JSONObject().put("deleted", gone).put("_deletedRevs", goneRevs).put("bookmarks", JSONArray().put(spec.getJSONObject("remoteEdit"))))
        assertTrue(StrictJson.equal(JSONArray().put(restored), Store.state("b").getJSONArray("bookmarks")))
        Store.restoreBookmark("b", mark)
        assertEquals(1, Store.state("b").getJSONArray("bookmarks").length())
    }

    @Before fun setup() {
        val root = Files.createTempDirectory("abook-marks-parity").toFile()
        Store::class.java.getDeclaredField("root").apply { isAccessible = true }.set(null, root)
        Store::class.java.getDeclaredField("recordsCache").apply { isAccessible = true }.set(null, null)
        File(root, "state").mkdirs()
    }

    @Test fun shared_places_follow_the_same_sentence_or_five_second_rule() {
        val cases = JSONArray(File("../../../tests/fixtures/listening_records/bookmark_places.json").readText())
        for (i in 0 until cases.length()) {
            val case = cases.getJSONObject(i)
            fun add(mark: JSONObject) = Store.addBookmark("b$i", mark.optInt("chapterId", 1), mark.getDouble("seconds"), "",
                if (mark.has("index")) mark.getInt("index") else null)
            val first = add(case.getJSONObject("old"))
            val second = add(case.getJSONObject("new"))
            assertEquals(case.getString("name"), case.getBoolean("same"), first.getString("id") == second.getString("id"))
        }
    }

    @Test fun a_duplicate_fills_an_empty_note_without_changing_creation_time() {
        Store.mergeRemote("b", JSONObject("""{"chapters":{},"bookmarks":[{"id":"old","chapterId":1,"seconds":64,"note":"","at":10,"rev":{"counter":1,"node":"fixture"}}]}"""))
        val mark = Store.addBookmark("b", 1, 64.0, " Ghi chú mới ")
        assertEquals("old", mark.getString("id"))
        assertEquals("Ghi chú mới", mark.getString("note"))
        assertEquals(10.0, mark.getDouble("createdAt"), 0.0)
        assertTrue(mark.getDouble("at") > 10)
        assertTrue(mark.getBoolean("existing"))
        assertEquals("Ghi chú mới", Store.addBookmark("b", 1, 64.0, "Thay thế").getString("note"))
        assertEquals(1, Store.state("b").getJSONArray("bookmarks").length())
        assertFalse(Store.state("b").getJSONArray("bookmarks").getJSONObject(0).has("existing"))
    }
}
