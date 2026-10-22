package vn.abook.player

import java.io.File
import java.nio.file.Files
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test

/** Cùng request/current/reply với pytest: người nghe sửa hồ sơ trong lúc mạng chưa trả lời. */
class StoreInflightReplyTest {
    private lateinit var root: File
    private val spec get() = JSONObject(File("../../../tests/fixtures/listening_records/inflight_reply.json").readText())

    @Before fun setup() {
        root = Files.createTempDirectory("abook-inflight").toFile()
        Store::class.java.getDeclaredField("root").apply { isAccessible = true }.set(null, root)
        Store::class.java.getDeclaredField("recordsCache").apply { isAccessible = true }.set(null, null)
        File(root, "state").mkdirs()
    }

    @Test fun reply_keeps_changes_in_the_sent_record_even_after_switching() {
        val record = Store.syncBody("b").getString("record")
        File(root, "state/$record.json").writeText(spec.getJSONObject("request").toString())
        val request = Store.syncBody("b")
        File(root, "state/$record.json").writeText(spec.getJSONObject("current").toString())
        Store.createRecord("b", "Khác")
        val other = Store.activeRecord("b")
        Store.applySync("b", spec.getJSONObject("reply").put("record", record), { "" to false })
        assertEquals(10, request.getJSONObject("last").getInt("seconds"))
        assertTrue(StrictJson.equal(spec.getJSONObject("expected"), JSONObject(File(root, "state/$record.json").readText())))
        assertEquals(other, Store.syncBody("b").getString("record"))
        assertFalse(Store.state("b").has("last"))
    }

    @Test fun active_state_also_merges_with_the_existing_record() {
        val record = Store.syncBody("b").getString("record")
        Store.createRecord("b", "Khác")
        val other = Store.activeRecord("b")
        File(root, "state/$other.json").writeText(spec.getJSONObject("current").toString())
        Store.applySync("b", JSONObject().put("record", record)
            .put("active", JSONObject().put("record", other).put("at", 9e9))
            .put("activeState", spec.getJSONObject("reply")), { "" to false })
        assertTrue(StrictJson.equal(spec.getJSONObject("expected"), Store.state("b")))
    }

    @Test fun legacy_reply_merges_with_current_state() {
        Store.mergeRemote("b", spec.getJSONObject("current"))
        Store.applySync("b", spec.getJSONObject("reply"), { "" to false })
        assertTrue(StrictJson.equal(spec.getJSONObject("expected"), Store.state("b")))
    }

    @Test fun a_record_deleted_while_waiting_is_not_brought_back_by_its_old_reply() {
        val record = Store.activeRecord("b")
        Store.deleteRecord("b", record)
        Store.applySync("b", spec.getJSONObject("reply").put("record", record)
            .put("records", org.json.JSONArray().put(JSONObject().put("id", record))), { "" to false })
        assertFalse(File(root, "state/$record.json").exists())
        assertEquals(0, Store.records("b").length())
    }
}
