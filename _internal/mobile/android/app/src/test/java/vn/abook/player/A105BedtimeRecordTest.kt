package vn.abook.player

import java.io.File
import java.nio.file.Files
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/** Nhật ký đêm thuộc về một hồ sơ nghe: chỉ người ấy nối được đêm cũ, và thẻ buổi sáng chỉ hiện đêm của hồ sơ đang dùng (soát a105 F5). */
class A105BedtimeRecordTest {
    private val a = "r-000000000000000a"
    private val b = "r-000000000000000b"

    @Before
    fun setUp() {
        val root = Files.createTempDirectory("abook-bedtime").toFile()
        Store::class.java.getDeclaredField("root").apply { isAccessible = true }.set(null, root)
    }

    private fun night(record: String, startedAt: Double, book: String = "sach") =
        JSONObject().put("bookId", book).put("recordId", record).put("startedAt", startedAt).put("lastAt", startedAt + 600)

    @Test
    fun a_timer_set_by_another_profile_of_the_same_book_is_a_new_night() {
        val current = night(a, 1000.0)
        assertTrue(Bedtime.continues(current, "sach", a, 1000.0 + 600))
        assertFalse(Bedtime.continues(current, "sach", b, 1000.0 + 600))
        assertFalse("quá 90 phút là đêm mới", Bedtime.continues(current, "sach", a, 1000.0 + 600 + 91 * 60))
        assertFalse(Bedtime.continues(current, "sach-khac", a, 1000.0 + 600))
    }

    @Test
    fun the_morning_card_shows_only_the_night_of_the_active_profile_of_that_book() {
        val nights = listOf(night(a, 1000.0), night(b, 2000.0))  // B nghe sau cùng nhưng A đang dùng
        assertEquals(a, Bedtime.pickLatest(nights) { a }!!.getString("recordId"))
        assertEquals(b, Bedtime.pickLatest(nights) { b }!!.getString("recordId"))
        assertNull("không có đêm của hồ sơ đang dùng thì không hiện thẻ", Bedtime.pickLatest(nights) { "r-000000000000000c" })
    }

    @Test
    fun every_profile_keeps_its_own_file_so_a_late_write_of_one_never_overwrites_the_other() {
        Bedtime.write(night(a, 1000.0))
        Bedtime.write(night(b, 2000.0))
        val saved = Bedtime.all()
        assertEquals(setOf(a, b), saved.map { it.getString("recordId") }.toSet())
        assertTrue(File(Store.root, "bedtime/$a.json").isFile)
    }
}
