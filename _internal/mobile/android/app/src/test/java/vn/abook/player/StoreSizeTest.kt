package vn.abook.player

import java.io.File
import java.nio.file.Files
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/** Cỡ từng cuốn nhớ theo dấu thư mục, không đi cả cây mỗi lần mở Thư viện (soát a101 F6). */
class StoreSizeTest {
    private lateinit var root: File

    @Before
    fun setUp() {
        root = Files.createTempDirectory("abook-sizes").toFile()
        Store::class.java.getDeclaredField("root").apply { isAccessible = true }.set(null, root)
        File(root, "books/a1/chapters").mkdirs()
        File(root, "books/a1/book.json").writeText("{}")
        File(root, "books/a1/chapters/001.mp3").writeText("x".repeat(100))
    }

    private fun bump(file: File) {
        file.setLastModified(file.lastModified() + 5_000) // mốc sửa nhích đủ để dấu đổi (ổ thô có thể chỉ phân giải 1-2 giây)
    }

    @Test
    fun the_size_is_remembered_until_something_in_the_book_changes() {
        val book = File(root, "books/a1")
        assertEquals(102L, Store.bookBytes(book))
        // Thay đổi KHÔNG đổi dấu thì số cũ còn nguyên (đang chứng minh là không đo lại): ghi đè nội dung, giữ mốc sửa.
        val chapter = File(book, "chapters/001.mp3")
        val stamp = chapter.lastModified()
        chapter.writeText("y".repeat(500))
        chapter.setLastModified(stamp)
        assertEquals(102L, Store.bookBytes(book))
        // Thêm một chương: thư mục chapters đổi mốc sửa -> đo lại.
        File(book, "chapters/002.mp3").writeText("z".repeat(40))
        bump(File(book, "chapters"))
        assertEquals(542L, Store.bookBytes(book))
    }

    @Test
    fun a_new_cover_or_edit_file_is_noticed_through_the_book_folder() {
        val book = File(root, "books/a1")
        assertEquals(102L, Store.bookBytes(book))
        File(book, "cover.jpg").writeText("c".repeat(10))
        bump(book)
        assertEquals(112L, Store.bookBytes(book))
    }

    @Test
    fun sizes_survive_a_restart_and_forget_deleted_books() {
        val book = File(root, "books/a1")
        val other = File(root, "books/b2").apply { mkdirs() }
        File(other, "book.json").writeText("{}")
        assertEquals(mapOf("a1" to 102L, "b2" to 2L), Store.bookSizes())
        assertTrue(File(root, "sizes.json").isFile)
        // Tiến trình mới: bộ nhớ trống, đọc lại sizes.json - số đã lưu được dùng khi dấu khớp.
        Store::class.java.getDeclaredField("sizesFrom").apply { isAccessible = true }.set(null, null)
        val chapter = File(book, "chapters/001.mp3")
        val stamp = chapter.lastModified()
        chapter.writeText("y".repeat(500))
        chapter.setLastModified(stamp)
        assertEquals(102L, Store.bookBytes(book))
        other.deleteRecursively()
        Store.bookSizes()
        assertTrue(!File(root, "sizes.json").readText().contains("b2"))
    }
}
