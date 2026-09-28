package vn.ebookreader.player

import java.io.File
import java.nio.file.Files
import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/** Xoá sách trên điện thoại chỉ theo một mã hợp lệ: mã rỗng từng là CẢ thư mục books/ (bookDir("") = root/books). */
class StoreDeleteTest {
    private lateinit var root: File

    @Before
    fun setUp() {
        root = Files.createTempDirectory("abook-store").toFile()
        // Store.root là `lateinit var ... private set` của một object: trường tĩnh, đặt bằng phản chiếu cho test JVM.
        Store::class.java.getDeclaredField("root").apply { isAccessible = true }.set(null, root)
        File(root, "books/a1/chapters").mkdirs()
        File(root, "books/a1/chapters/001.mp3").writeText("x")
        File(root, "books/pKEY_b2").mkdirs()
    }

    @Test
    fun an_empty_or_escaping_id_is_refused_and_nothing_is_deleted() {
        for (id in listOf("", "..", "../books", "a1/chapters", "a 1", "ả")) {
            assertThrows(IllegalArgumentException::class.java) { Store.deleteBook(id) }
        }
        assertTrue(File(root, "books/a1/chapters/001.mp3").isFile)
        assertTrue(File(root, "books/pKEY_b2").isDirectory)
    }

    @Test
    fun a_valid_id_names_exactly_its_own_folder() {
        // deleteBook còn ghi sổ prints.json bằng org.json - thứ test JVM không có; phần chọn thư mục là chỗ cần chặn.
        assertEquals(File(root, "books/pKEY_b2").canonicalFile, Store.deletableBookDir("pKEY_b2"))
        assertEquals(File(root, "books/a1").canonicalFile, Store.deletableBookDir("a1"))
    }
}
