package vn.abook.player

import java.io.File
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * Nhật ký bền (a114): ghi file xoay vòng có trần, không bao giờ ném ra ngoài (kể cả khi thư mục không ghi được và khi `android.util.Log` chưa có -
 * test JVM), che chuỗi trông như mã / khoá, và `tail` trả đúng các dòng cuối theo thứ tự thời gian.
 */
class AppLogTest {
    private lateinit var folder: File

    @Before
    fun setUp() {
        folder = BookEditsFixtures.tempDir("abook-applog")
        AppLog.useFolder(folder, limit = 2_000)
    }

    @After
    fun tearDown() {
        AppLog.useFolder(null)
    }

    @Test
    fun a_line_carries_time_level_tag_pid_and_thread() {
        AppLog.i("Share", "cổng đồng bộ đã bật")
        val line = AppLog.tail(10).single()
        assertTrue(line, Regex("""\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}[+-]\d{4} I Share \d+/.+: cổng đồng bộ đã bật""").matches(line))
        AppLog.w("Playback", "lỗi")
        AppLog.e("Crash", "văng")
        val levels = AppLog.tail(2).map { Regex(""" ([IWE]) (\w+) """).find(it)!!.groupValues.drop(1).joinToString(" ") }
        assertEquals(listOf("W Playback", "E Crash"), levels)
    }

    @Test fun prettyAndTruncatedListsAreScrubbedBeforeStackSplittingAndFileWrite() {
        val payload = org.json.JSONObject().put("addresses", org.json.JSONArray().put(org.json.JSONObject()
            .put("address", "private-phone.local:47630").put("note", "brackets ] [ and escaped \" quote"))).toString(2)
        for (text in listOf(payload + "\nfinished", payload.dropLast(8), payload.substringAfter('['))) {
            assertFalse(AppLog.scrub(text).contains("private-phone"))
        }
        val error = IllegalStateException(payload)
        assertFalse(AppLog.logcatText("failure", error).contains("private-phone"))
        assertFalse(AppLog.format(0, 'E', "Route", "failure", error, 0, "test").joinToString().contains("private-phone"))
        AppLog.e("Route", payload, error)
        assertFalse(AppLog.tail(100).joinToString().contains("private-phone"))
        assertTrue(AppLog.scrub(payload + "\nfinished").contains("finished"))
    }

    @Test
    fun the_file_rotates_at_the_cap_and_keeps_only_two_files() {
        repeat(200) { AppLog.i("T", "dòng số $it " + "x".repeat(40)) }
        AppLog.tail(1) // wait for the dedicated file writer
        val files = folder.listFiles()!!.map { it.name }.sorted()
        assertEquals(listOf("app.log", "app.log.1"), files)
        for (name in files) assertTrue("$name vượt trần", File(folder, name).length() <= 2_000)
        val tail = AppLog.tail(5)
        assertTrue(tail.last().contains("dòng số 199"))
        assertEquals("giữ thứ tự thời gian qua hai file", (195..199).toList(), tail.map { it.substringAfter("dòng số ").substringBefore(' ').toInt() })
    }

    @Test
    fun tail_counts_from_the_end_and_clamps() {
        repeat(5) { AppLog.i("T", "m$it") }
        assertEquals(2, AppLog.tail(2).size)
        assertTrue(AppLog.tail(2)[1].endsWith("m4"))
        assertEquals(5, AppLog.tail(1000).size)
        assertTrue(AppLog.tail(0).isEmpty() && AppLog.tail(-3).isEmpty())
    }

    @Test
    fun it_never_throws_even_when_the_folder_cannot_be_written() {
        val blocker = File(folder, "khong-phai-thu-muc").apply { writeText("x") }
        AppLog.useFolder(File(blocker, "diag")) // cha là một FILE: mkdirs/ghi không thể thành công
        AppLog.i("T", "không ném")
        AppLog.e("T", "cũng không", IllegalStateException("hỏng"))
        assertTrue(AppLog.tail(10).isEmpty())
        AppLog.useFolder(null)
        AppLog.i("T", "chưa có thư mục")
        AppLog.clear()
    }

    @Test
    fun secrets_that_slip_into_a_message_are_masked() {
        val hex = "ab".repeat(32)
        AppLog.i("T", "Authorization: Bearer abcdef0123456789 và token=hunter2hunter2 và $hex và sk-abcdefghijklmnopqrstuv")
        val line = AppLog.tail(1).single()
        assertFalse(line, line.contains("abcdef0123456789") || line.contains("hunter2") || line.contains(hex) || line.contains("sk-abcdefghijkl"))
        assertTrue(line, line.contains("Bearer ***") && line.contains("token=***"))
        AppLog.i("T", "Chương 3 xong, 12 câu")
        assertTrue(AppLog.tail(1).single().endsWith("Chương 3 xong, 12 câu"))
    }

    @Test
    fun a_long_line_is_cut_and_an_error_adds_a_few_stack_lines() {
        AppLog.w("T", "y".repeat(5000), IllegalStateException("hỏng ở đây"))
        val lines = AppLog.tail(100)
        assertTrue(lines.first().length < AppLog.MAX_LINE_CHARS + 120 && lines.first().contains("…"))
        assertTrue(lines.size in 2..(1 + AppLog.STACK_LINES))
        assertTrue(lines[1].startsWith("    ") && lines.joinToString("\n").contains("IllegalStateException: hỏng ở đây"))
        assertEquals("một lần ghi = một khối dòng, không dòng trống", 0, lines.count { it.isBlank() })
    }

    @Test
    fun clear_removes_the_log_and_the_crash_files() {
        AppLog.i("T", "một")
        CrashLog.write(folder, 1_000L, "main", IllegalStateException("x"))
        AppLog.clear()
        assertTrue(folder.listFiles().orEmpty().isEmpty())
        AppLog.i("T", "sau khi xoá")
        assertEquals(1, AppLog.tail(10).size)
    }

    @Test fun tailHostsAndDnsExceptionsUseSharedPrivacyFixture() {
        val rows = org.json.JSONArray(java.io.File("../../../tests/fixtures/peer_diagnostics.json").readText())
        for (i in 0 until rows.length()) {
            val row = rows.getJSONObject(i)
            val safe = AppLog.scrub(row.getString("message"))
            if (row.has("hidden")) org.junit.Assert.assertFalse(safe, safe.contains(row.getString("hidden")))
            if (row.has("kept")) org.junit.Assert.assertTrue(safe, safe.contains(row.getString("kept")))
        }
    }

}
