package vn.abook.player

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Test
import java.io.File

class StateSyncCrashTest {
    @Test
    fun snapshots_survive_restart_and_ack_is_scoped_to_the_sent_revision() {
        val file = File(BookEditsFixtures.tempDir("state-sync-snapshot"), "pending.json")
        val queue = PendingPushes(file)
        val body = JSONObject().put("record", "r-old").put("last", JSONObject().put("seconds", 42))
        val first = queue.add("b", body)
        body.getJSONObject("last").put("seconds", 64)
        queue.add("b", body)
        queue.add("b", JSONObject().put("record", "r-new"))
        val restored = PendingPushes(file)
        restored.ack("b", "r-old", first.getString("revision"))
        assertEquals(2, restored.entries().size)
        assertEquals(64, restored.entries().first { it.getString("recordId") == "r-old" }
            .getJSONObject("body").getJSONObject("last").getInt("seconds"))
        assertEquals(42, first.getJSONObject("body").getJSONObject("last").getInt("seconds"))
    }

    @Test
    fun restart_keeps_each_record_and_old_ack_cannot_remove_a_new_revision() {
        val dir = BookEditsFixtures.tempDir("state-sync-crash")
        val file = File(dir, "pending.json")
        val old = JSONObject().put("bookId", "b").put("recordId", "r-old").put("revision", "one")
            .put("body", JSONObject().put("record", "r-old").put("last", JSONObject().put("seconds", 42)))
        val newer = JSONObject(old.toString()).put("revision", "two")
        val other = JSONObject(old.toString()).put("recordId", "r-new").put("revision", "three")
        file.writeText(JSONArray().put(newer).put(other).toString())
        val queue = PendingPushes(file)
        assertEquals("restart must retain structured pending entries", setOf("b"), queue.ids())
        val ack = PendingPushes::class.java.getDeclaredMethod("ack", String::class.java, String::class.java, String::class.java)
        ack.invoke(queue, "b", "r-old", "one")
        assertEquals(2, JSONArray(file.readText()).length())
        ack.invoke(queue, "b", "r-old", "two")
        val left = JSONArray(file.readText())
        assertEquals(1, left.length())
        assertEquals("r-new", left.getJSONObject(0).getString("recordId"))
    }
}
