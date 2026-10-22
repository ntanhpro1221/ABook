package vn.abook.player

import java.io.File
import java.nio.file.Files
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Before
import org.junit.Test

/**
 * Điện thoại làm máy giữ sách: nhận hồ sơ do máy khác gửi lên theo MÃ HỒ SƠ (Store.mergeRecord) đúng hợp đồng của máy tính.
 * Bộ ví dụ dùng chung với pytest (tests/fixtures/sync/records_host.json, tests/test_a105_profiles.py - webui/listening.py
 * merge_record). Trước đây endpoint luôn gộp vào hồ sơ đang dùng và bỏ mã hồ sơ, bia mộ, tên.
 */
class A105HostRecordsTest {
    private lateinit var root: File
    private val fixture: JSONObject by lazy {
        val file = File("../../../tests/fixtures/sync/records_host.json")
        if (!file.isFile) fail("Không thấy bộ ví dụ dùng chung: ${file.absoluteFile} (chạy test từ mobile/android/app)")
        JSONObject(file.readText(Charsets.UTF_8))
    }
    private val ids: JSONObject get() = fixture.getJSONObject("ids")

    @Before
    fun setUp() {
        root = Files.createTempDirectory("abook-host-records").toFile()
        Store::class.java.getDeclaredField("root").apply { isAccessible = true }.set(null, root)
        Store::class.java.getDeclaredField("recordsCache").apply { isAccessible = true }.set(null, null)
        File(root, "state").mkdirs()
    }

    private fun id(key: String) = ids.getString(key)

    private fun list(array: JSONArray) = (0 until array.length()).map { array.getString(it) }

    /** Máy giữ sách dựng từ phía `host` của một ca. */
    private fun host(spec: JSONObject) {
        val records = JSONObject()
        val sources = spec.getJSONObject("records")
        for (key in sources.keys()) {
            val item = sources.getJSONObject(key)
            val meta = JSONObject().put("name", item.getString("name")).put("createdAt", 0.0).put("nameAt", item.getDouble("nameAt"))
            if (item.optDouble("movedAt", 0.0) > 0.0) meta.put("movedAt", item.getDouble("movedAt"))
            records.put(id(key), meta)
            val state = JSONObject(item.getJSONObject("state").toString())
            if (!state.has("chapters")) state.put("chapters", JSONObject())
            if (!state.has("bookmarks")) state.put("bookmarks", JSONArray())
            File(root, "state/${id(key)}.json").writeText(state.toString())
        }
        val links = JSONObject()
        val sourceLinks = spec.getJSONObject("links")
        for (book in sourceLinks.keys()) {
            val link = sourceLinks.getJSONObject(book)
            links.put(book, JSONObject().put("records", JSONArray(list(link.getJSONArray("records")).map(::id)))
                .put("active", id(link.getString("active"))).put("activeAt", link.getDouble("activeAt")))
        }
        val deleted = JSONObject()
        spec.getJSONObject("deleted").let { gone -> for (key in gone.keys()) deleted.put(id(key), gone.getDouble(key)) }
        File(root, "records.json").writeText(JSONObject().put("version", 2).put("records", records).put("links", links).put("deleted", deleted).toString())
    }

    private fun body(raw: JSONObject): JSONObject {
        val copy = JSONObject(raw.toString())
        copy.put("record", id(raw.getString("record")))
        val tombstones = JSONObject()
        raw.optJSONObject("deletedRecords")?.let { gone -> for (key in gone.keys()) tombstones.put(ids.optString(key, key), gone.getDouble(key)) }
        return copy.put("deletedRecords", tombstones)
    }

    private fun lastSeconds(record: String): Double? =
        Store.readJson(File(root, "state/$record.json"))?.optJSONObject("last")?.optDouble("seconds")

    private fun checkReply(reply: JSONObject, expect: JSONObject) {
        assertEquals(id(expect.getString("record")), reply.getString("record"))
        if (expect.has("book")) assertEquals(expect.getString("book"), reply.getString("book"))
        if (expect.has("deleted")) assertEquals(expect.getBoolean("deleted"), reply.optBoolean("deleted"))
        if (expect.has("lastSeconds")) assertEquals(expect.getDouble("lastSeconds"), reply.getJSONObject("last").getDouble("seconds"), 0.0)
        if (expect.has("bookmarkNotes")) {
            val notes = reply.getJSONArray("bookmarks").let { marks -> (0 until marks.length()).map { marks.getJSONObject(it).getString("note") } }
            assertEquals(list(expect.getJSONArray("bookmarkNotes")), notes)
        }
        if (expect.has("recordName")) assertEquals(expect.getString("recordName"), reply.getString("recordName"))
        if (expect.has("movedAt")) assertEquals(expect.getDouble("movedAt"), reply.getDouble("movedAt"), 0.0)
        if (expect.has("activeRecord")) assertEquals(id(expect.getString("activeRecord")), reply.getJSONObject("active").getString("record"))
        if (expect.has("activeStateLastSeconds")) {
            assertEquals(expect.getDouble("activeStateLastSeconds"), reply.getJSONObject("activeState").getJSONObject("last").getDouble("seconds"), 0.0)
        }
        if (expect.has("recordIds")) {
            val sent = reply.getJSONArray("records").let { items -> (0 until items.length()).map { items.getJSONObject(it).getString("id") } }
            assertEquals(list(expect.getJSONArray("recordIds")).map(::id).sorted(), sent.sorted())
        }
        if (expect.has("tombstones")) {
            for (key in list(expect.getJSONArray("tombstones"))) assertTrue(reply.getJSONObject("deletedRecords").has(id(key)))
        }
    }

    private fun checkAfter(expect: JSONObject) {
        val links = expect.getJSONObject("links")
        for (book in links.keys()) {
            val want = links.getJSONObject(book)
            val records = Store.records(book)
            assertEquals("hồ sơ của $book", list(want.getJSONArray("records")).map(::id),
                (0 until records.length()).map { records.getJSONObject(it).getString("id") })
            assertEquals("hồ sơ đang dùng của $book", id(want.getString("active")), Store.knownActiveRecord(book))
        }
        val names = expect.getJSONObject("names")
        val saved = JSONObject(File(root, "records.json").readText(Charsets.UTF_8))
        for (key in names.keys()) assertEquals(names.getString(key), saved.getJSONObject("records").getJSONObject(id(key)).getString("name"))
        assertEquals(list(expect.getJSONArray("deleted")).map(::id).sorted(), saved.getJSONObject("deleted").keys().asSequence().toList().sorted())
        expect.optJSONObject("lastSeconds")?.let { seconds ->
            for (key in seconds.keys()) assertEquals(seconds.getDouble(key), lastSeconds(id(key))!!, 0.0)
        }
        expect.optJSONObject("bookmarkNotes")?.let { notes ->
            for (key in notes.keys()) {
                val marks = Store.readJson(File(root, "state/${id(key)}.json"))?.optJSONArray("bookmarks") ?: JSONArray()
                assertEquals(list(notes.getJSONArray(key)), (0 until marks.length()).map { marks.getJSONObject(it).getString("note") })
            }
        }
    }

    @Test
    fun the_phone_host_follows_every_case_of_the_shared_contract() {
        val cases = fixture.getJSONObject("cases")
        for (name in cases.keys().asSequence().toList().sorted()) {
            setUp()
            val spec = cases.getJSONObject(name)
            host(spec.getJSONObject("host"))
            val request = spec.getJSONObject("request")
            try {
                val reply = Store.mergeRecord(request.getString("book"), body(request.getJSONObject("body")))
                checkReply(reply, spec.getJSONObject("expect").getJSONObject("reply"))
                checkAfter(spec.getJSONObject("expect").getJSONObject("after"))
            } catch (error: AssertionError) {
                throw AssertionError("ca $name: ${error.message}", error)
            }
        }
    }

    @Test
    fun a_request_without_a_record_still_merges_into_the_active_one_for_old_senders() {
        val spec = fixture.getJSONObject("cases").getJSONObject("other_person_is_not_overwritten")
        host(spec.getJSONObject("host"))
        val merged = Store.mergeRemote("sach", JSONObject().put("last", JSONObject().put("chapterId", 1).put("seconds", 700.0).put("at", 5000.0)))
        assertEquals(700.0, merged.getJSONObject("last").getDouble("seconds"), 0.0)
        assertEquals(700.0, lastSeconds(id("b"))!!, 0.0)
        assertFalse(merged.has("record"))
    }
}
