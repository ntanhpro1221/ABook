package vn.abook.player

import java.io.File
import java.nio.file.Files
import org.junit.Assert.assertEquals
import org.junit.Test

/** Bản chép tạm `import-*.abook` mà lần nhập trước bị giết nên không kịp xoá (soát a81 lỗi 11): dọn khi mở app, chỉ những bản đã cũ. */
class BookFileCacheSweepTest {
    @Test
    fun old_import_copies_are_swept_and_everything_else_is_left_alone() {
        val cache = Files.createTempDirectory("abook-cache").toFile()
        val now = System.currentTimeMillis()
        fun make(name: String, age: Long) = File(cache, name).apply { writeText("x"); setLastModified(now - age) }
        val old = make("import-123.abook", 3 * 60 * 60 * 1000L)
        val fresh = make("import-456.abook", 60 * 1000L) // lần nhập đang chạy
        val other = make("share-1.abook", 3 * 60 * 60 * 1000L)
        BookFileImport.sweepCache(cache, now)
        assertEquals(listOf(false, true, true), listOf(old.exists(), fresh.exists(), other.exists()))
    }
}
