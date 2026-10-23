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
 * Bốn việc ghi còn lại của người nghe (đánh dấu chương, đánh dấu cả cuốn, sửa / xoá dấu trang) ghi vào HỒ SƠ ĐÃ CHỐT lúc việc bắt đầu,
 * không phải hồ sơ đang dùng lúc ghi tới (soát a106). Bộ ca dùng chung với pytest (tests/fixtures/records/writes.json,
 * tests/test_a106_record_writes.py - webui/listening.py).
 */
class A106RecordWritesTest {
    private lateinit var root: File
    private val fixture: JSONObject by lazy {
        val file = File("../../../tests/fixtures/records/writes.json")
        if (!file.isFile) fail("Không thấy bộ ví dụ dùng chung: ${file.absoluteFile} (chạy test từ mobile/android/app)")
        JSONObject(file.readText(Charsets.UTF_8))
    }
    private val ids: JSONObject get() = fixture.getJSONObject("ids")
    private val book: String get() = fixture.getString("book")

    @Before
    fun setUp() {
        root = Files.createTempDirectory("abook-record-writes").toFile()
        Store::class.java.getDeclaredField("root").apply { isAccessible = true }.set(null, root)
        Store::class.java.getDeclaredField("recordsCache").apply { isAccessible = true }.set(null, null)
        File(root, "state").mkdirs()
    }

    private fun id(key: String) = ids.getString(key)

    /** Sổ hồ sơ dựng từ `setup` của bộ ca. */
    private fun build() {
        val setup = fixture.getJSONObject("setup")
        val records = JSONObject()
        val links = JSONObject()
        val sources = setup.getJSONObject("records")
        for (key in sources.keys()) {
            val item = sources.getJSONObject(key)
            records.put(id(key), JSONObject().put("name", key).put("createdAt", 0.0).put("nameAt", 0.0))
            File(root, "state/${id(key)}.json").writeText(item.getJSONObject("state").toString())
            val link = links.optJSONObject(item.getString("book")) ?: JSONObject().put("records", JSONArray()).put("active", id(key)).put("activeAt", 0.0)
            link.getJSONArray("records").put(id(key))
            links.put(item.getString("book"), link)
        }
        links.getJSONObject(book).put("active", id(setup.getString("active")))
        File(root, "records.json").writeText(JSONObject().put("version", 2).put("records", records).put("links", links).put("deleted", JSONObject()).toString())
    }

    private fun stateOf(key: String): JSONObject = Store.readJson(File(root, "state/${id(key)}.json"))!!

    private fun projection(key: String): String {
        val state = stateOf(key)
        return listOf("chapters", "bookmarks", "finished", "deleted").joinToString("|") { "$it=${state.opt(it)}" }
    }

    private fun snapshot(): Map<String, String> = fixture.getJSONObject("setup").getJSONObject("records").keys().asSequence().associateWith(::projection)

    private fun apply(op: JSONObject) {
        val record = if (op.has("record")) id(op.getString("record")) else null
        when (op.getString("kind")) {
            "chapterDone" -> Store.setChapterDone(book, op.getInt("chapterId"), op.getBoolean("done"), record)
            "finished" -> Store.setFinished(book, op.getBoolean("finished"), record)
            "updateBookmark" -> Store.updateBookmark(book, op.getString("markId"), op.getString("note"), record)
            else -> Store.deleteBookmark(book, op.getString("markId"), record)
        }
    }

    private fun checkApplied(key: String, before: JSONObject, op: JSONObject) {
        val after = stateOf(key)
        when (op.getString("kind")) {
            "chapterDone" -> {
                val chapter = after.getJSONObject("chapters").getJSONObject(op.getInt("chapterId").toString())
                assertEquals(op.getBoolean("done"), chapter.getBoolean("done"))
                val was = before.getJSONObject("chapters").getJSONObject(op.getInt("chapterId").toString()).getDouble("heard")
                assertEquals(if (op.getBoolean("done")) was else 0.0, chapter.getDouble("heard"), 0.0)
            }
            "finished" -> assertEquals(op.getBoolean("finished"), after.getBoolean("finished"))
            "updateBookmark" -> {
                val marks = after.getJSONArray("bookmarks")
                val old = before.getJSONArray("bookmarks")
                assertEquals(old.length(), marks.length())
                for (index in 0 until marks.length()) {
                    val mark = marks.getJSONObject(index)
                    val want = if (mark.getString("id") == op.getString("markId")) op.getString("note") else old.getJSONObject(index).getString("note")
                    assertEquals(want, mark.getString("note"))
                }
            }
            else -> {
                val marks = after.getJSONArray("bookmarks")
                assertTrue((0 until marks.length()).none { marks.getJSONObject(it).getString("id") == op.getString("markId") })
                assertTrue(after.getJSONObject("deleted").has(op.getString("markId")))
            }
        }
    }

    @Test
    fun the_phone_follows_every_case_of_the_shared_contract() {
        val cases = fixture.getJSONObject("cases")
        for (name in cases.keys().asSequence().toList().sorted()) {
            setUp()
            build()
            val spec = cases.getJSONObject(name)
            val applied = if (spec.isNull("applied")) null else spec.getString("applied")
            val before = snapshot()
            val states = before.keys.associateWith { JSONObject(stateOf(it).toString()) }
            try {
                if (applied == null) {
                    try {
                        apply(spec.getJSONObject("op"))
                        fail("việc ghi vào hồ sơ đã xoá / sang sách khác phải bị từ chối")
                    } catch (expected: IllegalStateException) {
                        assertEquals(Store.RECORD_GONE, expected.message)
                    }
                    assertEquals(before, snapshot())
                    continue
                }
                apply(spec.getJSONObject("op"))
                val after = snapshot()
                for (key in before.keys) {
                    if (key == applied) checkApplied(key, states.getValue(key), spec.getJSONObject("op"))
                    else assertEquals("hồ sơ $key không được đổi", before.getValue(key), after.getValue(key))
                }
            } catch (error: AssertionError) {
                throw AssertionError("ca $name: ${error.message}", error)
            }
        }
    }

    @Test
    fun switching_the_active_record_in_between_does_not_move_a_held_write() {
        build()
        val held = id("a")
        Store.activateRecord(book, id("a"))
        Store.activateRecord(book, id("b"))
        Store.setChapterDone(book, 3, true, held)
        Store.setFinished(book, true, held)
        assertTrue(stateOf("a").getBoolean("finished"))
        assertFalse(stateOf("b").has("finished"))
        assertFalse(stateOf("b").getJSONObject("chapters").getJSONObject("3").getBoolean("done"))
    }
}
