package vn.abook.player

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Before
import org.junit.Test
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.io.File
import java.io.IOException
import java.io.OutputStream

/**
 * Soát a99 C2: "Lưu" vào chỗ đã nhớ không được để lại file rỗng / cụt nếu lần lưu mới hỏng - gói dựng và kiểm trong file tạm trước, đích chỉ bị mở sau đó,
 * và bản cũ được trả lại khi chép giữa chừng hỏng.
 */
class BookSaveTest {
    private lateinit var work: File

    @Before
    fun setUp() {
        work = BookEditsFixtures.tempDir("abook-save")
        BookEditsFixtures.useStoreRoot(BookEditsFixtures.tempDir("abook-save-root"))
    }

    private fun book() = BookEditsFixtures.copyBase(File(work, "book"))

    /** Đích giả: nội dung hiện có, đếm lần mở, và (tuỳ ca) hỏng sau `failAfter` byte của lượt ghi đầu tiên. */
    private class Target(var content: ByteArray, private val failAfter: Int? = null) {
        var opens = 0
        fun previous() = ByteArrayInputStream(content)
        fun open(): OutputStream {
            opens++
            content = ByteArray(0) // "wt": mở là cắt
            val limit = if (opens == 1) failAfter else null
            return object : ByteArrayOutputStream() {
                override fun write(b: ByteArray, off: Int, len: Int) {
                    if (limit != null && size() + len > limit) {
                        content = toByteArray() // phần đã ghi dở nằm lại trên đích
                        throw IOException("hết chỗ")
                    }
                    super.write(b, off, len)
                }

                override fun close() {
                    super.close()
                    content = toByteArray()
                }
            }
        }
    }

    @Test
    fun a_good_save_replaces_the_old_bytes_with_a_complete_verified_package() {
        val target = Target("bản cũ".toByteArray())
        val written = BookSave.save(book(), File(work, "cache"), false, target::previous, target::open)
        assertEquals(written.size, target.content.size.toLong())
        val file = File(work, "check.abook").also { it.writeBytes(target.content) }
        BookSave.verify(file, written, false)
        assertEquals(1, target.opens)
    }

    @Test
    fun a_missing_source_file_never_touches_the_target() {
        val dir = book()
        val audio = File(dir, "chapters").walkTopDown().first { it.isFile && it.extension == "mp3" }
        assertTrue(audio.delete())
        val target = Target("bản lưu tốt trước đó".toByteArray())
        try {
            BookSave.save(dir, File(work, "cache"), false, target::previous, target::open)
            fail("thiếu file nguồn phải bị từ chối")
        } catch (expected: BookDocumentWriter.Refused) {
        }
        assertEquals("đích chưa được mở", 0, target.opens)
        assertArrayEquals("bản lưu tốt trước đó".toByteArray(), target.content)
    }

    @Test
    fun a_failure_while_copying_puts_the_previous_save_back() {
        val old = ByteArray(5000) { (it % 251).toByte() }
        val target = Target(old, failAfter = 100)
        try {
            BookSave.save(book(), File(work, "cache"), false, target::previous, target::open)
            fail("chép hỏng giữa chừng phải báo lỗi")
        } catch (expected: IOException) {
        }
        assertArrayEquals("bản cũ còn nguyên, không cụt", old, target.content)
        assertEquals("mở lại một lần để trả bản cũ", 2, target.opens)
    }

    @Test
    fun no_scratch_file_is_left_behind() {
        val cache = File(work, "cache")
        val target = Target(ByteArray(0))
        BookSave.save(book(), cache, false, target::previous, target::open)
        assertFalse(cache.listFiles().orEmpty().any { it.isFile })
    }

    @Test
    fun a_package_that_does_not_read_back_is_refused() {
        val junk = File(work, "junk.abook").also { it.writeBytes("không phải zip".toByteArray()) }
        try {
            BookSave.verify(junk, BookDocumentWriter.Written(junk.length(), 0, 1), false)
            fail("gói hỏng phải bị từ chối")
        } catch (expected: BookSave.Failed) {
        }
    }
}
