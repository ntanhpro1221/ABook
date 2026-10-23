package vn.abook.player

import java.io.File
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** Bắt văng (a114): mỗi lần văng một file `crash-<giờ>.txt`, giữ 5 file mới nhất; đọc lại mới nhất trước, nội dung cắt ngắn; mã lọt vào stack bị che. */
class CrashLogTest {
    @Test
    fun only_the_five_newest_crash_files_are_kept_and_read_newest_first() {
        val folder = BookEditsFixtures.tempDir("abook-crash")
        for (index in 1..8) assertTrue(CrashLog.write(folder, index * 1_000_000L, "main", IllegalStateException("lần $index")) != null)
        val names = folder.listFiles()!!.map { it.name }.sorted()
        assertEquals(5, names.size)
        val read = CrashLog.read(folder)
        assertEquals(names.reversed(), read.map { it.first })
        assertTrue(read.first().second.contains("lần 8") && read.last().second.contains("lần 4"))
        assertTrue(read.all { it.second.contains("IllegalStateException") && it.second.contains("luồng main") })
    }

    @Test
    fun content_is_cut_and_secrets_in_a_stack_are_masked() {
        val folder = BookEditsFixtures.tempDir("abook-crash2")
        val hex = "cd".repeat(32)
        CrashLog.write(folder, 5L, "worker", RuntimeException("Authorization: Bearer abcdef0123456789 $hex"))
        val text = File(folder, folder.list()!!.single()).readText()
        assertTrue(!text.contains("abcdef0123456789") && !text.contains(hex))
        assertEquals(100, CrashLog.read(folder, maxChars = 100).single().second.length)
    }

    @Test
    fun nothing_to_read_and_an_unwritable_folder_are_quiet() {
        assertTrue(CrashLog.read(null).isEmpty())
        assertTrue(CrashLog.read(File("không-có-thư-mục-này")).isEmpty())
        val blocker = BookEditsFixtures.tempDir("abook-crash3").resolve("f").apply { writeText("x") }
        assertNull(CrashLog.write(File(blocker, "diag"), 1L, "main", RuntimeException("x")))
    }
}
