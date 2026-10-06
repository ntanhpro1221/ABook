package vn.abook.player

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

/** "Chia sẻ…" (BookShare): file gửi đi nằm trong `cacheDir/share` (FileProvider phục vụ), mang tên sách như "Lưu thành…". */
class BookShareTest {
    @get:Rule
    val temp = TemporaryFolder()

    @Test
    fun theSharedFileLivesUnderCacheShareAndIsNamedAfterTheBook() {
        val cache = temp.newFolder("cache")
        val file = BookShare.target(cache, "Chuyến phà: cuối ngày?", asProject = false, stamp = 0x2a)
        assertEquals("Chuyến phà cuối ngày.abook", file.name)
        assertEquals(java.io.File(cache, "share/2a"), file.parentFile)
        assertEquals("Dự án sách nói.abookproj", BookShare.target(cache, "", asProject = true, stamp = 1).name)
        assertEquals("application/vnd.ngdtuanh.abook+zip", BookShare.mimeType(false))
        assertEquals("application/vnd.ngdtuanh.abookproj+zip", BookShare.mimeType(true))
    }

    @Test
    fun twoSharesOfTheSameTitleNeverOverwriteEachOther() {
        val cache = temp.newFolder("cache")
        assertNotEquals(BookShare.target(cache, "Sách", false, stamp = 1), BookShare.target(cache, "Sách", false, stamp = 2))
    }

    @Test
    fun sweepingClearsOnlyTheShareFolder() {
        val cache = temp.newFolder("cache")
        val shared = BookShare.target(cache, "Sách", false, stamp = 1).apply { parentFile!!.mkdirs(); writeText("x") }
        val other = java.io.File(cache, "text-book-1.abook").apply { writeText("y") }
        BookShare.sweep(cache)
        assertFalse(shared.exists())
        assertFalse(BookShare.dir(cache).exists())
        assertTrue(other.exists())
    }
}
