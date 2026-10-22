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
import java.io.InputStream
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

    private val keep get() = File(work, "ban-luu-cu")

    /** Lưu vào đích giả; mọi tham số mới (chỗ giữ bản cũ, chỗ trống) có giá trị dễ của test. */
    private fun save(target: Target, dir: File = book(), cache: File = File(work, "cache"), space: (File) -> Long = { Long.MAX_VALUE }) =
        BookSave.save(dir, cache, false, target::previous, target::open, keepDir = keep, keepName = "Sách thử", previousSize = target.content.size.toLong(), spaceLeft = space, now = { 1_700_000_000_000L })

    /** Đích giả: nội dung hiện có, đếm lần mở, và (tuỳ ca) hỏng sau `failAfter` byte của lượt ghi đầu tiên. */
    private class Target(var content: ByteArray, private val failAfter: Int? = null, private val failEvery: Boolean = false, private val unreadable: Boolean = false) {
        var opens = 0
        var asked = 0
        fun previous(): InputStream {
            asked++
            if (unreadable) return object : InputStream() { override fun read(): Int = throw IOException("không đọc được bản cũ") }
            return ByteArrayInputStream(content)
        }
        fun open(): OutputStream {
            opens++
            content = ByteArray(0) // "wt": mở là cắt
            val limit = if (opens == 1 || failEvery) failAfter else null
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
        val written = save(target)
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
            save(target, dir)
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
            save(target)
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
        save(target, cache = cache)
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

    @Test
    fun an_old_save_that_cannot_be_kept_aside_stops_before_the_target_is_opened() {
        val target = Target("bản lưu tốt trước đó".toByteArray(), unreadable = true)
        try {
            save(target)
            fail("không giữ được bản cũ thì không được ghi đè")
        } catch (expected: BookSave.Failed) {
            assertTrue(expected.message!!, expected.message!!.contains("Không giữ được bản cũ"))
        }
        assertEquals("đích chưa được mở", 0, target.opens)
        assertArrayEquals("bản lưu tốt trước đó".toByteArray(), target.content)
    }

    @Test
    fun a_previous_that_throws_when_opened_stops_before_the_target_is_opened() {
        val target = Target("bản cũ".toByteArray())
        try {
            BookSave.save(book(), File(work, "cache"), false, { throw IOException("hết chỗ") }, target::open, keepDir = keep, keepName = "x")
            fail("không giữ được bản cũ thì không được ghi đè")
        } catch (expected: BookSave.Failed) {
        }
        assertEquals(0, target.opens)
    }

    @Test
    fun when_even_putting_the_old_save_back_fails_it_is_kept_in_a_durable_folder() {
        val old = ByteArray(5000) { (it % 251).toByte() }
        val target = Target(old, failAfter = 100, failEvery = true)
        val cache = File(work, "cache")
        try {
            save(target, cache = cache)
            fail("chép hỏng hai lần phải báo lỗi")
        } catch (expected: BookSave.Failed) {
            val kept = keep.listFiles().orEmpty().single()
            assertTrue(expected.message!!, expected.message!!.contains(kept.name))
            assertTrue(expected.message!!, expected.message!!.contains("ban-luu-cu"))
        }
        val kept = keep.listFiles().orEmpty().single()
        assertArrayEquals("file giữ phòng là đúng bản cũ", old, kept.readBytes())
        assertTrue(kept.name, kept.name.startsWith("Sách thử") && kept.name.endsWith(".abook"))
        assertFalse("cache không còn giữ bản cũ", cache.listFiles().orEmpty().any { it.isFile })
    }

    @Test
    fun a_good_save_leaves_nothing_in_the_keep_folder() {
        save(Target("bản cũ".toByteArray()))
        assertTrue(keep.listFiles().orEmpty().isEmpty())
    }

    @Test
    fun a_restore_that_works_leaves_nothing_in_the_keep_folder() {
        val target = Target(ByteArray(5000) { 7 }, failAfter = 100)
        try {
            save(target)
            fail()
        } catch (expected: IOException) {
        }
        assertTrue(keep.listFiles().orEmpty().isEmpty())
    }

    @Test
    fun too_little_room_is_reported_early_with_the_megabytes_needed() {
        val target = Target("bản lưu tốt trước đó".toByteArray())
        try {
            save(target, space = { 0L })
            fail("thiếu chỗ phải báo sớm")
        } catch (expected: BookSave.Failed) {
            assertTrue(expected.message!!, Regex("""cần khoảng \d+ MB""").containsMatchIn(expected.message!!))
        }
        assertEquals("bản cũ chưa được hỏi", 0, target.asked)
        assertEquals("đích chưa được mở", 0, target.opens)
        assertArrayEquals("bản lưu tốt trước đó".toByteArray(), target.content)
    }

    @Test
    fun the_room_needed_counts_the_new_package_and_the_old_one() {
        val dir = book()
        assertTrue(BookSave.estimate(dir) > 0)
        assertEquals(BookSave.estimate(dir) + 3_000_000L + BookSave.HEADROOM, BookSave.roomNeeded(dir, 3_000_000L))
    }
}
