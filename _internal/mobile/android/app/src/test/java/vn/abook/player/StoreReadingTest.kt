package vn.abook.player

import java.io.File
import java.nio.file.Files
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test

class StoreReadingTest {
    @Before fun setup() {
        val root = Files.createTempDirectory("abook-reading").toFile()
        Store::class.java.getDeclaredField("root").apply { isAccessible = true }.set(null, root)
        Store::class.java.getDeclaredField("recordsCache").apply { isAccessible = true }.set(null, null)
        File(root, "state").mkdirs()
    }

    @Test fun readingKeepsAnchorAndNewerPlaceAcrossReloadAndSync() {
        val anchor = JSONObject().put("segment", 3).put("charOffset", 0).put("textHash", "fnv1a64:0123456789abcdef")
        Store.saveReading("b", 4, 3, 200.0, anchor, rev = JSONObject().put("counter", 2).put("node", "reader"))
        assertTrue(runCatching { Store.saveReading("b", 1, 0, 300.0, rev = JSONObject().put("counter", 1).put("node", "reader")) }.isFailure)
        val place = Store.state("b").getJSONObject("reading")
        assertEquals(4, place.getInt("chapterId"))
        assertEquals(anchor.toString(), place.getJSONObject("anchor").toString())
        Store::class.java.getDeclaredField("recordsCache").apply { isAccessible = true }.set(null, null)
        assertEquals(place.toString(), Store.syncBody("b").getJSONObject("reading").toString())
        val newer = JSONObject().put("reading", JSONObject().put("chapterId", 5).put("index", 10).put("at", 100.0).put("rev", JSONObject().put("counter", 3).put("node", "phone")))
        assertEquals(5, Store.mergeStates(Store.state("b"), newer).getJSONObject("reading").getInt("chapterId"))
    }

    @Test fun lateFlushKeepsItsOriginalProfile() {
        val first = Store.activeRecord("b")
        Store.createRecord("b", "Bạn khác")
        assertNotEquals(first, Store.activeRecord("b"))
        Store.saveReading("b", 4, 10, 200.0, record = first)
        assertFalse(Store.state("b").has("reading"))
        assertEquals(4, Store.syncBody("b", first).getJSONObject("reading").getInt("chapterId"))
    }
}
