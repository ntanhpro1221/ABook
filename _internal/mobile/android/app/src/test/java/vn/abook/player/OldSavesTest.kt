package vn.abook.player

import java.io.ByteArrayOutputStream
import java.io.File
import java.nio.file.Files
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Before
import org.junit.Test

/**
 * Màn "Bản lưu cũ" (soát a106 G3): file BookSave giữ ở filesDir/ban-luu-cu khi trả lại bản trước thất bại - liệt kê, chặn tên, chép, xoá.
 */
class OldSavesTest {
    private lateinit var files: File
    private lateinit var dir: File

    @Before
    fun setUp() {
        files = Files.createTempDirectory("abook-old-saves").toFile()
        dir = OldSaves.dir(files)
    }

    private fun put(name: String, bytes: ByteArray, modified: Long): File = File(dir, name).also {
        dir.mkdirs()
        it.writeBytes(bytes)
        it.setLastModified(modified)
    }

    private fun refused(block: () -> Unit) = try {
        block()
        fail("tên không hợp lệ phải bị từ chối")
    } catch (expected: IllegalArgumentException) {
        // đúng
    }

    @Test
    fun no_folder_or_an_empty_one_lists_nothing() {
        assertTrue(OldSaves.list(dir).isEmpty())
        dir.mkdirs()
        assertTrue(OldSaves.list(dir).isEmpty())
    }

    @Test
    fun lists_files_newest_first_with_name_and_size() {
        put("Sách A 20260101-101010.abook", ByteArray(10), 1_000_000L)
        put("Sách B 20260202-101010.abookproj", ByteArray(2048), 3_000_000L)
        File(dir, "thư mục con").mkdirs()
        val list = OldSaves.list(dir)
        assertEquals(listOf("Sách B 20260202-101010.abookproj", "Sách A 20260101-101010.abook"), list.map { it.name })
        assertEquals(2048L, list[0].size)
        assertEquals(3_000_000L, list[0].modified)
    }

    @Test
    fun names_that_could_leave_the_folder_are_refused() {
        put("an toan.abook", ByteArray(1), 1L)
        File(files, "ngoai.abook").writeBytes(ByteArray(1))
        for (bad in listOf("../ngoai.abook", "..", ".", "", " ", "a/b.abook", "a\b.abook", "/etc/passwd", "an toan.abook ", "x\u0000.abook")) {
            refused { OldSaves.resolve(dir, bad) }
            refused { OldSaves.delete(dir, bad) }
            refused { OldSaves.copyTo(dir, bad, ByteArrayOutputStream()) }
        }
        assertTrue(File(files, "ngoai.abook").isFile)
        assertTrue(File(dir, "an toan.abook").isFile)
    }

    @Test
    fun a_name_that_is_not_there_is_refused_and_a_title_with_dots_is_an_ordinary_name() {
        refused { OldSaves.resolve(dir, "khong-co.abook") }
        put("Chuyện dài... 20260101-101010.abook", ByteArray(3), 1L)
        assertEquals("Chuyện dài... 20260101-101010.abook", OldSaves.resolve(dir, "Chuyện dài... 20260101-101010.abook").name)
    }

    @Test
    fun copy_writes_the_same_bytes_in_chunks_and_leaves_the_file() {
        val bytes = ByteArray(3 * 1024 * 1024 + 17) { (it * 31).toByte() }
        put("Sách 20260101-101010.abook", bytes, 1L)
        val out = ByteArrayOutputStream()
        assertEquals(bytes.size.toLong(), OldSaves.copyTo(dir, "Sách 20260101-101010.abook", out))
        assertArrayEquals(bytes, out.toByteArray())
        assertTrue(File(dir, "Sách 20260101-101010.abook").isFile)
    }

    @Test
    fun delete_removes_only_that_file() {
        put("A 20260101-101010.abook", ByteArray(1), 1L)
        put("B 20260101-101010.abook", ByteArray(1), 2L)
        assertTrue(OldSaves.delete(dir, "A 20260101-101010.abook"))
        assertFalse(File(dir, "A 20260101-101010.abook").exists())
        assertEquals(listOf("B 20260101-101010.abook"), OldSaves.list(dir).map { it.name })
        refused { OldSaves.delete(dir, "A 20260101-101010.abook") }
    }

    @Test
    fun the_dialog_type_follows_the_extension() {
        assertEquals(BookFileImport.MIMETYPE, OldSaves.mimeOf("A.abook"))
        assertEquals(BookFileImport.PROJECT_MIMETYPE, OldSaves.mimeOf("A.abookproj"))
    }
}
