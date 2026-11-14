package vn.abook.player

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class BookVolumesTest {
    private fun chapter(id: Int, index: Int, volume: Int) = JSONObject().put("id", id).put("index", index).put("volumeId", volume)

    private fun book(vararg volumes: Pair<Int, String>, chapters: List<JSONObject>) = JSONObject()
        .put("title", "Fixture")
        .put("volumes", JSONArray(volumes.map { (id, title) -> JSONObject().put("id", id).put("number", id).put("title", title) }))
        .put("chapters", JSONArray(chapters))

    @Test
    fun severalVolumesAreWrittenAsATreeAndReadBackInTheGlobalOrder() {
        val tree = BookVolumes.nested(book(1 to "One", 2 to "Two", chapters = listOf(chapter(1, 1, 1), chapter(2, 2, 1), chapter(3, 3, 2))))
        assertFalse(tree.has("chapters"))
        assertTrue(BookVolumes.needsTree(tree))
        val read = BookVolumes.project(JSONObject(tree.toString()))
        val ids = (0 until read.getJSONArray("chapters").length()).map { read.getJSONArray("chapters").getJSONObject(it).getInt("id") }
        assertEquals(listOf(1, 2, 3), ids)
        assertEquals(2, read.getJSONArray("chapters").getJSONObject(2).getInt("volumeId"))
    }

    @Test
    fun onePlainVolumeStaysAFlatChapterList() {
        val flat = BookVolumes.nested(book(1 to "Quyển 1", chapters = listOf(chapter(1, 1, 1), chapter(2, 2, 1))))
        assertFalse(flat.has("volumes"))
        assertFalse(flat.getJSONArray("chapters").getJSONObject(0).has("volumeId"))
        assertSame(flat, BookVolumes.project(flat))
    }

    @Test
    fun aSeriesNumbersChaptersInsideEachVolumeButRefusesDisorderWithinOne() {
        val series = JSONObject().put("volumes", JSONArray()
            .put(JSONObject().put("id", 1).put("number", 1).put("title", "A").put("chapters", JSONArray().put(JSONObject().put("id", 100001).put("index", 1))))
            .put(JSONObject().put("id", 2).put("number", 2).put("title", "B").put("chapters", JSONArray().put(JSONObject().put("id", 200001).put("index", 1)))))
        assertEquals(2, BookVolumes.project(series).getJSONArray("chapters").length())
        val disorder = JSONObject().put("volumes", JSONArray().put(JSONObject().put("id", 1).put("number", 1).put("title", "A").put("chapters", JSONArray()
            .put(JSONObject().put("id", 1).put("index", 2)).put(JSONObject().put("id", 2).put("index", 1)))))
        assertThrows(IllegalArgumentException::class.java) { BookVolumes.project(disorder) }
    }
}
