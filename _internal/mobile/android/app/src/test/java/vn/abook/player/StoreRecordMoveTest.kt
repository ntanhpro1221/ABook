package vn.abook.player

import java.io.File
import java.nio.file.Files
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Before
import org.junit.Test

/**
 * "Chuyển sang cuốn khác…" của hồ sơ nghe trên điện thoại - cùng nghĩa với webui/listening.py move_record: hồ sơ rời cuốn cũ,
 * gắn vào cuốn nhận và thành hồ sơ đang dùng ở đó; chỗ nghe (file trạng thái của hồ sơ) đi theo.
 */
class StoreRecordMoveTest {
    private lateinit var root: File
    private val first = "r-0000000000000001"
    private val second = "r-0000000000000002"
    private val other = "r-0000000000000003"

    @Before
    fun setUp() {
        root = Files.createTempDirectory("abook-record-move").toFile()
        // Store là object: đặt thư mục và bỏ bộ đệm hồ sơ bằng phản chiếu cho từng test JVM.
        Store::class.java.getDeclaredField("root").apply { isAccessible = true }.set(null, root)
        Store::class.java.getDeclaredField("recordsCache").apply { isAccessible = true }.set(null, null)
        val meta = { name: String -> JSONObject().put("name", name).put("createdAt", 1.0).put("nameAt", 1.0) }
        File(root, "records.json").writeText(JSONObject().put("version", 2)
            .put("records", JSONObject().put(first, meta("Mặc định")).put(second, meta("Con")).put(other, meta("Bản mới")))
            .put("links", JSONObject()
                .put("cu", JSONObject().put("records", JSONArray().put(first).put(second)).put("active", second).put("activeAt", 5.0))
                .put("moi", JSONObject().put("records", JSONArray().put(other)).put("active", other).put("activeAt", 5.0)))
            .put("deleted", JSONObject()).toString())
        File(root, "state").mkdirs()
        File(root, "state/$second.json").writeText(JSONObject()
            .put("last", JSONObject().put("chapterId", 7).put("seconds", 55.0)).put("updatedAt", 9.0).toString())
    }

    private fun ids(records: JSONArray) = (0 until records.length()).map { records.getJSONObject(it).getString("id") }

    private fun active(bookId: String) =
        Store.records(bookId).let { list -> (0 until list.length()).map { list.getJSONObject(it) }.firstOrNull { it.getBoolean("active") }?.getString("id") }

    @Test
    fun the_record_leaves_its_book_and_becomes_the_active_one_of_the_other() {
        val left = Store.moveRecord("cu", second, "moi")

        assertEquals(listOf(first), ids(left))
        assertEquals(first, active("cu"))
        assertEquals(listOf(other, second), ids(Store.records("moi")))
        assertEquals(second, active("moi"))
        assertEquals(7, Store.state("moi").getJSONObject("last").getInt("chapterId"))
    }

    @Test
    fun a_book_without_records_gets_its_first_one() {
        Store.moveRecord("cu", first, "chua-nghe")

        assertEquals(listOf(first), ids(Store.records("chua-nghe")))
        assertEquals(first, active("chua-nghe"))
    }

    @Test
    fun only_a_record_of_this_book_moves_and_only_to_another_book() {
        assertThrows(IllegalArgumentException::class.java) { Store.moveRecord("cu", other, "moi") }
        assertThrows(IllegalArgumentException::class.java) { Store.moveRecord("cu", "r-ffffffffffffffff", "moi") }
        assertThrows(IllegalArgumentException::class.java) { Store.moveRecord("cu", first, "cu") }
        assertThrows(IllegalArgumentException::class.java) { Store.moveRecord("cu", first, "") }
        assertEquals(listOf(first, second), ids(Store.records("cu")))
        assertNull(Store.knownActiveRecord("chua-nghe"))
    }
}
