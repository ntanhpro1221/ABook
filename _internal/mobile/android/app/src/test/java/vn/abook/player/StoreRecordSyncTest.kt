package vn.abook.player

import java.io.File
import java.nio.file.Files
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Before
import org.junit.Test

/**
 * Chuyển hồ sơ nghe rồi đồng bộ với máy tính: lần chuyển sau thắng (`movedAt`). Bộ ví dụ DÙNG CHUNG với pytest
 * (tests/fixtures/listening_records/move_sync.json, tests/test_listening_records.py - webui/listening.py merge_record):
 * điện thoại gửi đúng các khoá ấy, và theo lời đáp của máy tính như bộ ví dụ nói. Trước đây hồ sơ chuyển trên điện
 * thoại bị lần đồng bộ kế kéo về cuốn cũ.
 */
class StoreRecordSyncTest {
    private lateinit var root: File
    private val fixture: JSONObject by lazy {
        val file = File("../../../tests/fixtures/listening_records/move_sync.json")
        if (!file.isFile) fail("Không thấy bộ ví dụ dùng chung: ${file.absoluteFile} (chạy test từ mobile/android/app)")
        JSONObject(file.readText(Charsets.UTF_8))
    }
    private val a = "r-000000000000000a"
    private val b = "r-000000000000000b"
    private val idle = { "" to false }

    @Before
    fun setUp() {
        root = Files.createTempDirectory("abook-record-sync").toFile()
        // Store là object: đặt thư mục và bỏ bộ đệm hồ sơ bằng phản chiếu cho từng test JVM.
        Store::class.java.getDeclaredField("root").apply { isAccessible = true }.set(null, root)
        Store::class.java.getDeclaredField("recordsCache").apply { isAccessible = true }.set(null, null)
        File(root, "state").mkdirs()
    }

    private fun case(name: String): JSONObject = fixture.getJSONObject("cases").getJSONObject(name)

    /** Sổ hồ sơ của điện thoại dựng từ phía `phone` của một ca. */
    private fun phone(spec: JSONObject) {
        val side = spec.getJSONObject("phone")
        val names = fixture.getJSONObject("names")
        val records = JSONObject()
        for (id in names.keys()) {
            val meta = JSONObject().put("name", names.getString(id)).put("createdAt", 0.0).put("nameAt", 0.0)
            side.getJSONObject("movedAt").optDouble(id).takeUnless { it.isNaN() }?.let { meta.put("movedAt", it) }
            records.put(id, meta)
        }
        File(root, "records.json").writeText(JSONObject().put("version", 2).put("records", records)
            .put("links", side.getJSONObject("links")).put("deleted", JSONObject()).toString())
    }

    private fun ids(bookId: String) = Store.records(bookId).let { list -> (0 until list.length()).map { list.getJSONObject(it).getString("id") } }

    private fun active(bookId: String) =
        Store.records(bookId).let { list -> (0 until list.length()).map { list.getJSONObject(it) }.firstOrNull { it.getBoolean("active") }?.getString("id") }

    private fun assertLinks(expected: JSONObject) {
        for (bookId in expected.keys()) {
            val want = expected.getJSONArray(bookId).let { list -> (0 until list.length()).map { list.getString(it) } }
            assertEquals("hồ sơ của $bookId", want, ids(bookId))
        }
    }

    /** Lời đáp của máy tính: đúng các khoá bộ ví dụ nói, cộng trạng thái nghe đã gộp. */
    private fun reply(spec: JSONObject): JSONObject = JSONObject(spec.getJSONObject("reply").toString())
        .put("chapters", JSONObject()).put("bookmarks", JSONArray())

    @Test
    fun a_move_on_the_phone_is_sent_with_its_time_and_kept_after_the_reply() {
        val spec = case("phone_moved_later")
        phone(spec)
        val move = spec.getJSONObject("phoneMove")

        Store.moveRecord(move.getString("from"), move.getString("record"), move.getString("to"))
        val body = Store.syncBody(spec.getJSONObject("push").getString("book"))

        val sent = spec.getJSONObject("push").getJSONObject("body")
        for (key in listOf("record", "recordName", "nameAt", "activeAt", "movedAt", "deletedRecords")) {
            assertTrue("gói gửi máy tính thiếu $key", body.has(key))
        }
        assertEquals(sent.getString("record"), body.getString("record"))
        assertTrue("lúc chuyển mới hơn lần chuyển máy tính biết", body.getDouble("movedAt") > spec.getJSONObject("computer")
            .getJSONObject("movedAt").getDouble(b))
        assertEquals("chuyển là chọn hồ sơ ấy ở cuốn mới", body.getDouble("movedAt"), body.getDouble("activeAt"), 0.0)

        Store.applySync(spec.getJSONObject("push").getString("book"), reply(spec), idle)

        assertLinks(spec.getJSONObject("phoneAfter"))
        assertEquals(b, active("sach-moi"))
    }

    @Test
    fun a_later_move_on_the_computer_moves_the_record_here_too() {
        val spec = case("computer_moved_later")
        phone(spec)
        val push = spec.getJSONObject("push")

        val body = Store.syncBody(push.getString("book"))
        assertEquals(push.getJSONObject("body").getString("record"), body.getString("record"))
        assertEquals(push.getJSONObject("body").getDouble("movedAt"), body.getDouble("movedAt"), 0.0)
        Store.applySync(push.getString("book"), reply(spec), idle)

        assertLinks(spec.getJSONObject("phoneAfter"))
        assertEquals(b, active("sach-moi"))
        assertEquals(a, active("sach-cu"))
        assertEquals("nhớ lúc chuyển của máy tính", spec.getJSONObject("reply").getDouble("movedAt"),
            Store.syncBody("sach-moi").getDouble("movedAt"), 0.0)
    }

    @Test
    fun a_computer_that_knows_nothing_of_moves_does_not_undo_one_made_here() {
        val spec = case("phone_moved_later")
        phone(spec)
        Store.moveRecord("sach-cu", b, "sach-moi")

        // máy tính đời trước: không có movedAt, vẫn nói hồ sơ ở cuốn cũ
        Store.applySync("sach-moi", JSONObject().put("record", b).put("book", "sach-cu")
            .put("chapters", JSONObject()).put("bookmarks", JSONArray()), idle)

        assertLinks(spec.getJSONObject("phoneAfter"))
    }

    @Test
    fun the_old_book_does_not_pull_back_a_record_moved_away_here() {
        val spec = case("phone_moved_later")
        phone(spec)
        Store.moveRecord("sach-cu", b, "sach-moi")

        // cuốn cũ đẩy trước khi máy tính biết lần chuyển: máy tính vẫn chọn b ở cuốn cũ, chọn sau cả lần chuyển
        Store.applySync("sach-cu", JSONObject().put("record", a).put("book", "sach-cu").put("movedAt", 0.0)
            .put("active", JSONObject().put("record", b).put("at", 9_999_999_999.0))
            .put("records", JSONArray().put(JSONObject().put("id", a).put("movedAt", 0.0))
                .put(JSONObject().put("id", b).put("movedAt", 1000.0)))
            .put("chapters", JSONObject()).put("bookmarks", JSONArray()), idle)

        assertLinks(spec.getJSONObject("phoneAfter"))
        assertEquals(a, active("sach-cu"))
        assertEquals(b, active("sach-moi"))
    }
}
