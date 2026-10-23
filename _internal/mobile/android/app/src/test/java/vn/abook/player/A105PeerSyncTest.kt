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

/**
 * Sách của thiết bị ghép mang mã cục bộ `p<thiết bị>_<mã bên ấy>`; lời đáp của máy giữ sách nói mã BÊN ẤY. Trước đây
 * `Store.applySync` coi nó là mã cục bộ nên hồ sơ rời cuốn `p<thiết bị>_sach` sang cuốn `sach` (soát a105 F2).
 */
class A105PeerSyncTest {
    private lateinit var root: File
    private val a = "r-000000000000000a"
    private val b = "r-000000000000000b"
    private val idle = { "" to false }

    @Before
    fun setUp() {
        root = Files.createTempDirectory("abook-peer-sync").toFile()
        Store::class.java.getDeclaredField("root").apply { isAccessible = true }.set(null, root)
        Store::class.java.getDeclaredField("recordsCache").apply { isAccessible = true }.set(null, null)
        File(root, "state").mkdirs()
    }

    private fun library(vararg links: Pair<String, String>) {
        val records = JSONObject()
        val linked = JSONObject()
        for ((book, record) in links) {
            records.put(record, JSONObject().put("name", "Mặc định").put("createdAt", 0.0).put("nameAt", 0.0))
            linked.put(book, JSONObject().put("records", JSONArray().put(record)).put("active", record).put("activeAt", 0.0))
        }
        File(root, "records.json").writeText(JSONObject().put("version", 2).put("records", records).put("links", linked).put("deleted", JSONObject()).toString())
    }

    private fun ids(book: String) = Store.records(book).let { list -> (0 until list.length()).map { list.getJSONObject(it).getString("id") } }

    private fun reply(record: String, book: String, movedAt: Double = 0.0) = JSONObject().put("record", record).put("book", book)
        .put("movedAt", movedAt).put("chapters", JSONObject()).put("bookmarks", JSONArray())
        .put("active", JSONObject().put("record", record).put("at", 0.0))

    @Test
    fun the_reply_book_is_translated_into_the_peers_namespace_so_the_record_stays_in_its_book() {
        library("p1_sach" to a)
        val reply = reply(a, "sach")

        StateSync.localizeReply("p1_sach", "sach", "1", reply)
        Store.applySync("p1_sach", reply, idle)

        assertEquals("p1_sach", reply.getString("book"))
        assertEquals(listOf(a), ids("p1_sach"))
        assertTrue("không đẻ cuốn thô `sach`", ids("sach").isEmpty())
    }

    @Test
    fun two_peers_with_the_same_book_code_do_not_collide() {
        library("p1_sach" to a, "p2_sach" to b)
        val reply = reply(a, "sach")

        StateSync.localizeReply("p1_sach", "sach", "1", reply)
        Store.applySync("p1_sach", reply, idle)

        assertEquals(listOf(a), ids("p1_sach"))
        assertEquals(listOf(b), ids("p2_sach"))
    }

    @Test
    fun a_record_moved_on_the_holder_follows_to_the_peers_destination_book() {
        library("p1_sach" to a)
        val reply = reply(a, "sach-moi", movedAt = 5000.0)

        StateSync.localizeReply("p1_sach", "sach", "1", reply)
        Store.applySync("p1_sach", reply, idle)

        assertEquals("p1_sach-moi", reply.getString("book"))
        assertEquals(listOf(a), ids("p1_sach-moi"))
        assertTrue(ids("p1_sach").isEmpty())
    }

    @Test
    fun the_main_computers_book_codes_are_the_local_ones() {
        library("sach" to a)
        val reply = reply(a, "sach")

        StateSync.localizeReply("sach", "sach", "", reply)
        assertEquals("sach", reply.getString("book"))

        val moved = reply(a, "sach-moi", movedAt = 5000.0)
        StateSync.localizeReply("sach", "sach", "", moved)
        assertEquals("sach-moi", moved.getString("book"))
    }

    private fun replyListing(record: String, vararg listed: Triple<String, String, Double>): JSONObject {
        val reply = reply(record, "sach")
        val items = JSONArray()
        for ((id, name, moved) in listed) items.put(JSONObject().put("id", id).put("name", name).put("nameAt", 5.0).put("movedAt", moved))
        return reply.put("records", items)
    }

    @Test
    fun every_record_the_holder_lists_shows_up_in_the_picker_not_only_the_pushed_and_active_ones() {
        val c = "r-000000000000000c"
        library("sach" to a)
        val reply = replyListing(a, Triple(a, "Mặc định", 0.0), Triple(b, "Bố", 0.0), Triple(c, "Con", 0.0))
        reply.put("active", JSONObject().put("record", c).put("at", 9.0))

        Store.applySync("sach", reply, idle)

        assertEquals(setOf(a, b, c), ids("sach").toSet())
        val names = Store.records("sach").let { list -> (0 until list.length()).associate { list.getJSONObject(it).getString("id") to list.getJSONObject(it).getString("name") } }
        assertEquals("Bố", names[b])
        assertEquals(c, Store.knownActiveRecord("sach"))
        assertFalse("hồ sơ chưa tải chưa có trạng thái", Store.hasState(b))
    }

    @Test
    fun a_record_deleted_here_is_not_listed_again_and_one_moved_here_later_stays_put() {
        library("sach" to a)
        Store.createRecord("sach-moi", "Con")
        val moved = Store.records("sach-moi").getJSONObject(0).getString("id")
        Store.moveRecord("sach-moi", moved, "sach-khac")  // chuyển ở đây, mốc mới hơn mọi mốc máy giữ sách biết
        Store.deleteRecord("sach", a)
        val reply = replyListing(b, Triple(a, "Mặc định", 0.0), Triple(b, "Bố", 0.0), Triple(moved, "Con", 1.0))

        Store.applySync("sach", reply, idle)

        assertEquals(listOf(b), ids("sach"))
        assertEquals(listOf(moved), ids("sach-khac"))
    }
}
