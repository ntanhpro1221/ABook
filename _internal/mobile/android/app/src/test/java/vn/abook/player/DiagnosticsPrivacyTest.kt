package vn.abook.player

import java.io.ByteArrayInputStream
import java.io.File
import java.util.zip.ZipInputStream
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

/** Real a115 ReviewProbe payloads; no copy of the production scrubber/collector. */
class DiagnosticsPrivacyTest {
    private val azure = "0123456789abcdef0123456789abcdef"
    private val bearer = "private-token-123456789"
    private val path = "C:\\Users\\Alice\\Private\\novel.txt"
    private val stack = "    at vn.abook.Playback.play(Playback.kt:306)"

    @Test fun bridge_keys_pair_codes_cast_urls_and_private_addresses_are_scrubbed() {
        val bridge = "callback: 1, pluginId: ReadAloud, methodName: setOnlineKey, methodData: {\"provider\":\"azure\",\"key\":\"$azure\",\"region\":\"southeastasia\"}"
        val pair = "methodName: pair, methodData: {\"host\":\"100.64.1.2\",\"code\":\"123456\"}"
        val samples = listOf(bridge to azure, pair to "123456", "http://192.168.1.2:40000/c/$azure.mp3" to azure,
            "Bearer $bearer" to bearer, "apiKey=x secret=y password=z code=123456" to "123456", "pair 123456" to "123456",
            path to path, "/storage/emulated/0/Books/private.mp3" to "/storage/emulated/0/",
            "/data/user/0/com.app/files/book" to "/data/user/0/", "content://com.provider/private/book" to "content://",
            "192.168.123.9" to "192.168.123.9", "2001:db8::1234" to "2001:db8::1234", "::1" to "::1",
            "::ffff:192.168.1.1" to "::ffff:192.168.1.1", "2001:db8::1234." to "2001:db8::1234",
            "192.168.123.9." to "192.168.123.9", "pairing code is 123456" to "123456", "mã ghép là 123456" to "123456")
        for ((input, secret) in samples) {
            val clean = AppLog.scrub("IllegalStateException: $input\n$stack")
            assertFalse(clean, clean.contains(secret))
            assertTrue(clean.contains("IllegalStateException:"))
            assertTrue(clean.contains(stack))
        }
        val logged = AppLog.logcatText("failed", IllegalStateException("Bearer $bearer $path"))
        assertFalse(logged.contains(bearer))
        assertFalse(logged.contains(path))
        assertTrue(logged.contains("IllegalStateException"))
    }

    @Test fun logcat_exports_only_approved_tags_and_scrubs_the_survivors() {
        val lines = listOf(
            "10-23 12:00:00.000 123 456 V Capacitor/Plugin: methodName: setOnlineKey, methodData: {\"key\":\"$azure\"}",
            "10-23 12:00:00.000 123 456 V Capacitor: methodName: pair, methodData: {\"code\":\"123456\"}",
            "10-23 12:00:00.000 123 456 I Console: private story", "I/chromium(123): story",
            "I/WebView(123): story", "I/Unapproved(123): story", "unparseable private story",
            "10-23 12:00:00.000 123 456 E MediaCodec: Bearer $bearer $path",
            "W/AudioTrack(123): http://192.168.1.2/c/$azure.mp3",
            "E/AndroidRuntime(123): IllegalStateException")
        val clean = Diagnostics.filterLogcat(lines)
        assertEquals(3, clean.size)
        val text = clean.joinToString("\n")
        for (secret in listOf(azure, bearer, path, "192.168.1.2", "story", "123456", "Capacitor")) assertFalse(text, text.contains(secret))
    }

    @Test fun every_json_string_and_exit_description_trace_and_bundle_are_scrubbed() {
        val exit = ExitReasons.entry(4, "Bearer $bearer $path", 1, 325, 0, 0, "IllegalStateException: 192.168.1.2\n$stack")
        assertFalse(exit.toString().contains(bearer))
        assertFalse(exit.toString().contains(path))
        assertFalse(exit.toString().contains("192.168.1.2"))
        assertTrue(exit.getString("trace").contains(stack))
        val report = Diagnostics.assemble(listOf("nested" to { JSONArray().put(JSONObject().put("message", "Bearer $bearer")) },
            "failed" to { throw IllegalStateException("Bearer $bearer") }))
        assertFalse(report.toString().contains(bearer))
        // bundle also protects callers which did not go through collect/assemble.
        ZipInputStream(ByteArrayInputStream(Diagnostics.bundle(JSONObject().put("error", "Bearer $bearer")))).use { zip ->
            while (zip.nextEntry != null) assertFalse(zip.readBytes().toString(Charsets.UTF_8).contains(bearer))
        }
        assertFalse(CrashLog.text(1, "main", IllegalStateException("$path 192.168.1.2 Bearer $bearer")).contains(path))
    }

    @Test fun huge_metadata_and_arrays_fit_even_without_any_log() {
        for (logs in listOf(false, true)) {
            val report = JSONObject().put("playback", JSONObject().put("bookTitle", "x".repeat(3_000_010)))
                .put("items", JSONArray((0..5000).map { "z".repeat(2100) }))
            if (logs) report.put("log", JSONArray().put("last log"))
            val fit = Diagnostics.fit(report)
            assertTrue(fit.toString().length <= Diagnostics.MAX_CHARS)
            assertTrue(fit.getJSONObject("playback").getString("bookTitle").length <= 2000)
            assertTrue(fit.getJSONArray("items").length() <= 200)
        }
        val many = JSONObject()
        repeat(200) { many.put("part$it", JSONObject().apply { repeat(200) { put("field$it", "x".repeat(2000)) } }) }
        assertTrue(Diagnostics.fit(many, 5000).toString().length <= 5000)
        assertTrue(Diagnostics.fit(JSONObject().put("x", "z".repeat(100)), 2).toString().length <= 2)
    }

    @Test fun importance_keeps_current_name_and_raw_number() {
        for ((number, name) in listOf(100 to "FOREGROUND", 125 to "FOREGROUND_SERVICE", 200 to "VISIBLE", 230 to "PERCEPTIBLE",
            300 to "SERVICE", 325 to "TOP_SLEEPING", 350 to "CANT_SAVE_STATE", 400 to "CACHED", 1000 to "GONE")) {
            val entry = ExitReasons.entry(4, null, 1, number, 0, 0, null)
            assertEquals(number, entry.getInt("importanceCode"))
            assertEquals(name, entry.getString("importance").substringBefore(' '))
        }
    }

    @Test fun collector_reads_the_same_events_as_all_four_workers() {
        val book = "diag-test-book"
        val downloadRun = "diag-download"
        BookDownloads.active[book] = downloadRun
        val exports = listOf(Mp3Exports.live to Mp3Exports::emit, M4bExports.live to M4bExports::emit, ListenExports.live to ListenExports::emit)
        try {
            BookDownloads.emit(JSONObject().put("bookId", book).put("done", 3).put("total", 10))
            val download = Diagnostics.workEntry(downloadRun, "RUNNING", emptySet(), 0, 0, emptyMap())
            assertEquals("3", download.getJSONObject("progress").getString("done"))
            for ((index, pair) in exports.withIndex()) {
                val (live, emit) = pair
                val run = "diag-export-$index"
                live.note(book, run, JSONObject())
                emit(JSONObject().put("bookId", book).put("run", run).put("done", 2).put("total", 9))
                assertEquals("2", Diagnostics.workEntry(run, "RUNNING", emptySet(), 0, 0, emptyMap()).getJSONObject("progress").getString("done"))
                emit(JSONObject().put("bookId", book).put("run", run).put("done", 4).put("total", 9))
                assertEquals("4", Diagnostics.workEntry(run, "RUNNING", emptySet(), 0, 0, emptyMap()).getJSONObject("progress").getString("done"))
            }
        } finally {
            BookDownloads.active.remove(book)
            BookDownloads.emit(JSONObject().put("bookId", book).put("finished", true))
            for ((index, pair) in exports.withIndex()) pair.second(JSONObject().put("bookId", book).put("run", "diag-export-$index").put("finished", true))
        }
        assertEquals(0, Diagnostics.workEntry(downloadRun, "RUNNING", emptySet(), 0, 0, emptyMap()).getJSONObject("progress").length())
    }

    @Test fun app_log_rotates_after_append_and_handles_an_oversized_record() {
        val dir = BookEditsFixtures.tempDir("diag-rotation")
        AppLog.useFolder(dir, 512)
        try {
            repeat(12) { AppLog.i("Test", "x".repeat(400)) }
            AppLog.i("Test", "y".repeat(1500))
            AppLog.tail(100) // flush queue before inspection
            assertTrue(dir.listFiles()!!.all { it.length() <= 512 })
            assertTrue(AppLog.tail(10).joinToString("\n").contains("y"))
        } finally { AppLog.useFolder(null) }
    }
}
