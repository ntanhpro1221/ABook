package vn.abook.player

import java.io.ByteArrayInputStream
import java.io.File
import java.util.zip.ZipInputStream
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** Phần thuần của bản chẩn đoán (a114): kẹp số dòng, ghép từng phần trong try riêng, giữ cỡ trong trần, gói .zip, tên lý do chết. */
class DiagnosticsTest {
    @Test fun shared_states_preserve_empty_errors_and_collection_failure_envelopes() {
        val cases = JSONArray(File("../../../tests/fixtures/diagnostics_states.json").readText(Charsets.UTF_8))
        for (index in 0 until cases.length()) {
            val case = cases.getJSONObject(index)
            val report = case.getJSONObject("report")
            assertEquals(case.getString("name"), report.toString(), Diagnostics.sanitize(report).toString())
        }
    }
    @Test
    fun the_line_count_is_clamped_and_read_from_the_query() {
        assertEquals(Diagnostics.DEFAULT_LINES, Diagnostics.clampLines(null))
        assertEquals(1, Diagnostics.clampLines(-5))
        assertEquals(1, Diagnostics.clampLines(0))
        assertEquals(50, Diagnostics.clampLines(50))
        assertEquals(Diagnostics.MAX_LINES, Diagnostics.clampLines(10_000_000))
        assertEquals(50, Diagnostics.linesOf("a=1&lines=50"))
        assertNull(Diagnostics.linesOf("lines=abc"))
        assertNull(Diagnostics.linesOf(""))
        assertNull(Diagnostics.linesOf("mylines=5"))
    }

    @Test
    fun a_failing_part_becomes_an_error_object_and_the_rest_still_come_out() {
        val report = Diagnostics.assemble(listOf(
            "ok" to { JSONObject().put("a", 1) },
            "boom" to { throw IllegalStateException("hỏng ở đây") },
            "none" to { null },
            "list" to { JSONArray().put("x") },
        ))
        assertEquals(1, report.getInt("schema"))
        assertEquals(1, report.getJSONObject("ok").getInt("a"))
        assertEquals("IllegalStateException: hỏng ở đây", report.getJSONObject("boom").getString("error"))
        assertTrue(report.getJSONObject("boom").getBoolean("collectionFailed"))
        assertTrue(!report.has("none"))
        assertEquals("x", report.getJSONArray("list").getString(0))
    }

    @Test
    fun an_error_thrown_as_an_Error_is_caught_too() {
        val report = Diagnostics.assemble(listOf("lack" to { throw NoClassDefFoundError("androidx/work/Z") }, "after" to { JSONObject() }))
        assertTrue(report.getJSONObject("lack").getString("error").startsWith("NoClassDefFoundError"))
        assertTrue(report.has("after"))
    }

    @Test
    fun an_oversized_report_drops_logcat_then_the_oldest_log_lines() {
        val big = { prefix: String -> JSONArray((0 until 400).map { "$prefix $it " + "z".repeat(100) }) }
        val report = JSONObject().put("schema", 1).put("log", big("log")).put("logcat", big("cat"))
        val fitted = Diagnostics.fit(report, maxChars = 12_000)
        assertFalse(fitted.has("logcat"))
        assertTrue(fitted.getBoolean("truncated"))
        val log = fitted.getJSONArray("log")
        assertTrue(log.length() in 10 until 400)
        assertTrue("giữ các dòng MỚI nhất", log.getString(log.length() - 1).startsWith("log 399 "))
        assertTrue(fitted.toString().length <= 12_000)
        val small = JSONObject().put("log", JSONArray().put("a"))
        assertFalse(Diagnostics.fit(small, maxChars = 12_000).has("truncated"))
    }

    @Test
    fun the_zip_holds_the_json_and_a_readable_log_text() {
        val report = JSONObject().put("schema", 1).put("app", JSONObject().put("versionName", "0.4.133"))
            .put("log", JSONArray().put("dòng một").put("dòng hai")).put("logcat", JSONArray().put("I/AudioTrack: x"))
        val entries = linkedMapOf<String, String>()
        ZipInputStream(ByteArrayInputStream(Diagnostics.bundle(report))).use { zip ->
            while (true) {
                val entry = zip.nextEntry ?: break
                entries[entry.name] = zip.readBytes().toString(Charsets.UTF_8)
            }
        }
        assertEquals(listOf("chan-doan.json", "nhat-ky.txt"), entries.keys.toList())
        assertEquals("0.4.133", JSONObject(entries.getValue("chan-doan.json")).getJSONObject("app").getString("versionName"))
        val text = entries.getValue("nhat-ky.txt")
        assertTrue(text.contains("dòng một\ndòng hai") && text.contains("I/AudioTrack: x"))
        assertTrue(Diagnostics.bundleName(1_700_000_000_000L).matches(Regex("abook-nhat-ky-\\d{8}-\\d{6}\\.zip")))
    }

    @Test
    fun clip_says_how_much_it_cut() {
        assertEquals("abc", Diagnostics.clip("abc", 10))
        assertTrue(Diagnostics.clip("x".repeat(30), 10).endsWith("còn 20 ký tự)"))
    }

    @Test
    fun exit_reasons_and_work_entries_are_readable() {
        val entry = ExitReasons.entry(3, "swap de-prioritized", 1_700_000_000_000L, 300, 120_000L, 180_000L, "x".repeat(10_000))
        assertTrue(entry.getString("reason").startsWith("LOW_MEMORY") && entry.getInt("code") == 3)
        assertTrue(entry.getString("importance").startsWith("SERVICE"))
        assertEquals(ExitReasons.TRACE_CHARS, entry.getString("trace").length)
        assertFalse(ExitReasons.entry(10, null, 1L, 100, 0, 0, null).has("trace"))
        assertTrue(ExitReasons.reasonName(99).startsWith("UNKNOWN"))
        val work = Diagnostics.workEntry("id-1", "RUNNING", setOf("vn.abook.player.Mp3ExportWorker"), 2, -256, mapOf("done" to "3"))
        assertEquals("Mp3ExportWorker", work.getJSONArray("tags").getString(0))
        assertEquals("3", work.getJSONObject("progress").getString("done"))
    }

    @Test fun nestedHostFieldsArePrivateWithoutAColonOrPort() {
        val data = JSONObject().put("nested", JSONArray().put(JSONObject()
            .put("host", "private-phone").put("hostname", "private-phone.local.")
            .put("address", "private-phone:47630").put("addresses", JSONArray().put("private-phone"))))
        val safe = Diagnostics.sanitize(data)
        assertFalse(safe.toString().contains("private-phone"))
        val fields = safe.getJSONArray("nested").getJSONObject(0)
        for (key in listOf("host", "hostname", "address", "addresses")) assertEquals("***", fields.getString(key))
    }

}
