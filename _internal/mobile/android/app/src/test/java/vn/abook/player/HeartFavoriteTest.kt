package vn.abook.player

import java.io.File
import java.nio.file.Files
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import vn.abook.player.ui.data.BookJson
import vn.abook.player.ui.data.Library
import vn.abook.player.ui.data.LibraryFilter
import vn.abook.player.ui.data.LibrarySort
import vn.abook.player.ui.data.ListenBook
import vn.abook.player.ui.data.ListenState
import vn.abook.player.ui.data.Progress

/**
 * Thả tim (yêu thích) cho sách: trạng thái NGƯỜI NGHE trong hồ sơ nghe (không vào file sách), đi cùng đồng bộ hồ sơ nghe như `finished` -
 * giá trị + mốc giờ + phiên bản, lần thả mới hơn thắng. Bản Python: tests/test_heart_favorite.py.
 */
class HeartFavoriteTest {
    private lateinit var root: File
    private val book = "0123456789ab"
    private val record = "r-heart"

    @Before
    fun setUp() {
        root = Files.createTempDirectory("abook-heart").toFile()
        Store::class.java.getDeclaredField("root").apply { isAccessible = true }.set(null, root)
        Store::class.java.getDeclaredField("recordsCache").apply { isAccessible = true }.set(null, null)
        File(root, "state").mkdirs()
        File(root, "state/$record.json").writeText(JSONObject().put("chapters", JSONObject()).toString())
        val links = JSONObject().put(book, JSONObject().put("records", JSONArray().put(record)).put("active", record).put("activeAt", 0.0))
        val records = JSONObject().put(record, JSONObject().put("name", "Mặc định").put("createdAt", 0.0).put("nameAt", 0.0))
        File(root, "records.json").writeText(JSONObject().put("version", 2).put("records", records).put("links", links).put("deleted", JSONObject()).toString())
    }

    private fun saved(): JSONObject = Store.readJson(File(root, "state/$record.json"))!!

    private fun stamped(favorite: Boolean, at: Double, counter: Int, node: String) = JSONObject().put("chapters", JSONObject())
        .put("favorite", favorite).put("favoriteAt", at)
        .put("_fieldRevs", JSONObject().put("favorite", JSONObject().put("counter", counter).put("node", node)))

    @Test
    fun `a book is not a favorite until the listener says so`() {
        assertFalse(saved().optBoolean("favorite"))
        assertFalse(BookJson.state(saved()).favorite)
    }

    @Test
    fun `toggling stores value stamp and revision in the record`() {
        val on = Store.setFavorite(book, true)
        assertTrue(on.getBoolean("favorite"))
        assertTrue(on.getDouble("favoriteAt") > 0)
        val first = on.getJSONObject("_fieldRevs").getJSONObject("favorite").getLong("counter")
        assertTrue(first > 0)
        assertTrue(saved().getBoolean("favorite"))
        assertTrue(BookJson.state(saved()).favorite)
        val off = Store.setFavorite(book, false)
        assertFalse(off.getBoolean("favorite"))
        assertTrue(off.getJSONObject("_fieldRevs").getJSONObject("favorite").getLong("counter") > first)
        assertFalse(BookJson.state(saved()).favorite)
    }

    @Test
    fun `the newer heart wins a merge both ways`() {
        val older = stamped(true, 10.0, 1, "a")
        val newer = stamped(false, 20.0, 2, "b")
        assertFalse(Store.mergeStates(older, newer).getBoolean("favorite"))
        assertFalse(Store.mergeStates(newer, older).getBoolean("favorite"))
        assertTrue("máy chưa thả tim nhận tim của máy kia", Store.mergeStates(JSONObject().put("chapters", JSONObject()), older).getBoolean("favorite"))
    }

    @Test
    fun `a heart without revision is dropped whole`() {
        val broken = ListeningSchema.state(JSONObject().put("favorite", true).put("favoriteAt", 5.0).put("_fieldRevs", JSONObject()))
        assertFalse(broken.has("favorite"))
        assertFalse(broken.has("favoriteAt"))
        val kept = ListeningSchema.state(stamped(true, 5.0, 1, "n"))
        assertTrue(kept.getBoolean("favorite"))
        assertEquals(5.0, kept.getDouble("favoriteAt"), 0.0)
        assertTrue(ListeningRevision.checkedPeer(JSONObject(), kept) {}.getBoolean("favorite"))
    }

    @Test
    fun `the favorite shelf follows the heart not the listening state`() {
        fun item(id: String, favorite: Boolean, finished: Boolean = false) =
            ListenBook(id, id, "", state = ListenState(favorite = favorite), progress = Progress.None.copy(finished = finished))
        val loved = item("a", favorite = true, finished = true)
        val plain = item("b", favorite = false)
        assertTrue(Library.inFilter(loved, LibraryFilter.Favorite))
        assertTrue(Library.inFilter(loved, LibraryFilter.Finished))
        assertFalse(Library.inFilter(plain, LibraryFilter.Favorite))
        assertTrue(Library.inFilter(plain, LibraryFilter.All))
        val view = Library.view(listOf(loved, plain), LibraryFilter.Favorite, "", LibrarySort.Recent)
        assertEquals(listOf("book:a"), view.tiles.map { it.key })
        assertEquals(1, view.shown)
        assertEquals(LibraryFilter.Favorite, LibraryFilter.entries.last())
    }
}
