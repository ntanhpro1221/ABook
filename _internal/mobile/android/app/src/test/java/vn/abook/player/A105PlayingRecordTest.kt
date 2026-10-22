package vn.abook.player

import java.io.File
import java.nio.file.Files
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Before
import org.junit.Test

/**
 * Phiên phát cục bộ chốt hồ sơ (Playback.recordId): máy khác xoá hồ sơ đang phát thì Store báo cho trình phát (onGone) SAU khi sổ đã lưu,
 * và mọi lần ghi muộn vào hồ sơ đã xoá bị bỏ - không rơi sang hồ sơ còn lại, cũng không đẻ hồ sơ mới (soát a105 F3).
 */
class A105PlayingRecordTest {
    private lateinit var root: File
    private val a = "r-000000000000000a"
    private val b = "r-000000000000000b"
    private val idle = { "" to false }

    @Before
    fun setUp() {
        root = Files.createTempDirectory("abook-playing-record").toFile()
        Store::class.java.getDeclaredField("root").apply { isAccessible = true }.set(null, root)
        Store::class.java.getDeclaredField("recordsCache").apply { isAccessible = true }.set(null, null)
        File(root, "state").mkdirs()
    }

    /** Cuốn `sach` có các hồ sơ [records] (hồ sơ đầu đang dùng). */
    private fun book(vararg records: String) {
        val meta = JSONObject()
        records.forEach { meta.put(it, JSONObject().put("name", it.takeLast(1)).put("createdAt", 0.0).put("nameAt", 0.0)) }
        val link = JSONObject().put("records", JSONArray(records.toList())).put("active", records.first()).put("activeAt", 0.0)
        File(root, "records.json").writeText(JSONObject().put("version", 2).put("records", meta)
            .put("links", JSONObject().put("sach", link)).put("deleted", JSONObject()).toString())
    }

    private fun lastSeconds(record: String): Double? = Store.readJson(File(root, "state/$record.json"))?.optJSONObject("last")?.optDouble("seconds")

    private fun tombstone(record: String) = JSONObject().put("record", b).put("book", "sach").put("chapters", JSONObject()).put("bookmarks", JSONArray())
        .put("deletedRecords", JSONObject().put(record, 99.0)).put("active", JSONObject().put("record", b).put("at", 0.0))

    @Test
    fun a_late_save_into_a_deleted_record_is_dropped_and_does_not_fall_to_the_other_person() {
        book(a, b)
        Store.progress("sach", 1, 20.0, 1000.0, recordId = a)
        Store.progress("sach", 1, 80.0, 1000.0, recordId = b)
        val gone = mutableListOf<Set<String>>()

        Store.applySync("sach", tombstone(a), idle) { gone.add(it) }

        assertEquals(listOf(setOf(a)), gone)
        assertFalse(Store.holds("sach", a))
        // lần lưu muộn của phiên phát đã chốt hồ sơ A
        Store.progress("sach", 1, 999.0, 1000.0, recordId = a)
        Store.setRate("sach", 1.75, a)
        Store.addSession("sach", JSONObject().put("id", "s1").put("listened", 60.0), a)
        assertEquals(80.0, lastSeconds(b)!!, 0.0)
        assertNull(Store.state("sach").opt("rate"))
        assertNull(Store.state("sach").optJSONArray("sessions"))
        try {
            Store.addBookmark("sach", 1, 5.0, "x", recordId = a)
            fail("dấu trang vào hồ sơ đã xoá phải bị từ chối")
        } catch (expected: IllegalStateException) {
            assertTrue(Store.state("sach").getJSONArray("bookmarks").length() == 0)
        }
    }

    @Test
    fun the_only_record_gone_means_a_late_save_does_not_create_a_new_record() {
        book(a)
        Store.progress("sach", 1, 20.0, 1000.0, recordId = a)

        Store.applySync("sach", tombstone(a).put("record", a).put("deleted", true), idle) { }
        Store.progress("sach", 1, 999.0, 1000.0, recordId = a)

        assertEquals(0, Store.records("sach").length())
        assertNull(Store.knownActiveRecord("sach"))
    }

    @Test
    fun the_player_is_told_after_the_book_is_saved_with_a_replacement_chosen() {
        book(a, b)
        var seen: List<String>? = null

        Store.applySync("sach", tombstone(a), idle) {
            seen = (0 until Store.records("sach").length()).map { index -> Store.records("sach").getJSONObject(index).getString("id") }
        }

        assertEquals(listOf(b), seen)
        assertEquals(b, Store.knownActiveRecord("sach"))
        assertTrue(File(root, "records.json").readText().contains("\"deleted\":{\"$a\""))
    }

    @Test
    fun a_tombstone_sent_to_the_phone_as_holder_also_tells_the_player() {
        book(a, b)
        val gone = mutableListOf<Set<String>>()

        Store.mergeRecord("sach", JSONObject().put("record", b).put("recordName", "b").put("nameAt", 0.0).put("activeAt", 0.0).put("movedAt", 0.0)
            .put("deletedRecords", JSONObject().put(a, 50.0)).put("chapters", JSONObject()).put("bookmarks", JSONArray())) { gone.add(it) }

        assertEquals(listOf(setOf(a)), gone)
        assertEquals(b, Store.knownActiveRecord("sach"))
    }

    @Test
    fun a_save_into_a_record_the_player_still_holds_goes_there_even_if_another_is_active() {
        book(a, b)
        Store.progress("sach", 1, 20.0, 1000.0, recordId = b)

        assertEquals(20.0, lastSeconds(b)!!, 0.0)
        assertNull(lastSeconds(a))
        assertEquals(a, Store.knownActiveRecord("sach"))
    }
}
