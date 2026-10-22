package vn.abook.player

import java.io.File
import java.nio.file.Files
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * Mở file sách bị cắt giữa chừng (soát a73, F3): BookFileImport giải vào books/.<mã>.<số>.part (book.json ra đầu tiên) và
 * thay bản cũ qua books/.<mã>.<số>.old. App bị giết lúc ấy thì những thư mục này nằm lại - không được hiện thành sách ma,
 * và lần mở app sau dọn / trả lại chúng.
 */
class StoreStagingTest {
    private lateinit var root: File

    @Before
    fun setUp() {
        root = Files.createTempDirectory("abook-staging").toFile()
        // Store là object: đặt thư mục và bỏ bộ đệm hồ sơ bằng phản chiếu cho từng test JVM (như BookFileImportTest).
        Store::class.java.getDeclaredField("root").apply { isAccessible = true }.set(null, root)
        Store::class.java.getDeclaredField("recordsCache").apply { isAccessible = true }.set(null, null)
    }

    private fun book(name: String, title: String, ageMs: Long = 0): File {
        val dir = File(root, "books/$name").apply { mkdirs() }
        File(dir, "book.json").writeText(JSONObject().put("title", title).toString())
        if (ageMs > 0) dir.setLastModified(System.currentTimeMillis() - ageMs)
        return dir
    }

    @Test
    fun half_written_imports_are_not_books() {
        book("a1", "Sách thật")
        book(".a1.123.part", "Đang giải dở")
        book(".b2.456.old", "Bản cũ chờ xoá")

        assertEquals(listOf("a1"), Store.bookIds())
        assertEquals(listOf("Sách thật"), Store.books().map { it.optString("title") })
        assertEquals(listOf("Sách thật"), Store.playableBooks().map { it.optString("title") })
        assertEquals(setOf("a1"), Store.bookSizes().keys)
    }

    @Test
    fun leftovers_are_put_back_or_swept_when_old_enough() {
        val hour = Store.STAGING_MAX_AGE_MS
        book("c3", "Bản mới")
        val fresh = book(".a1.123.part", "Đang giải", ageMs = 0)
        val orphanOld = book(".b2.456.old", "Bản cũ của b2", ageMs = 2 * hour)
        val replacedOld = book(".c3.789.old", "Bản cũ của c3", ageMs = 2 * hour)
        val stalePart = book(".d4.1.part", "Giải dở hôm qua", ageMs = 2 * hour)

        val stale = Store.recoverStaging()

        // Cắt giữa hai lần đổi tên của `replace`: bản chính vắng, bản cũ về chỗ - người nghe không mất sách.
        assertFalse(orphanOld.exists())
        assertEquals("Bản cũ của b2", Store.rawManifest("b2")?.optString("title"))
        assertEquals(setOf(replacedOld, stalePart).map { it.canonicalPath }.toSet(), stale.map { it.canonicalPath }.toSet())
        assertTrue("bản đang giải (mới) không bị đụng", fresh.isDirectory && fresh !in stale)
        assertEquals(listOf("b2", "c3"), Store.bookIds().sorted())
    }
}
