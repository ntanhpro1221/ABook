package vn.abook.player

import org.junit.Assert.assertEquals
import org.junit.Test

/** Đọc nhiều file văn bản trong một lượt qua cầu (ô "Tìm trong sách" của điện thoại - soát a101 F6). */
class TextBatchTest {
    @Test
    fun answers_follow_the_order_of_the_paths_and_a_missing_file_is_null() {
        val files = mapOf("scripts/1.json" to "một", "scripts/3.json" to "ba")
        val out = TextBatch.read(listOf("scripts/1.json", "scripts/2.json", "scripts/3.json")) { files[it] }
        assertEquals(listOf("một", null, "ba"), out)
    }

    @Test
    fun too_much_text_returns_the_first_part_only_and_the_caller_asks_again() {
        val asked = ArrayList<String>()
        val out = TextBatch.read((1..10).map { "scripts/$it.json" }, budget = 25) { path ->
            asked.add(path)
            "x".repeat(10)
        }
        assertEquals("stops once the total passes the budget (10+10+10 > 25)", 3, out.size)
        assertEquals(3, asked.size)
    }

    @Test
    fun one_huge_file_is_still_returned() {
        assertEquals(1, TextBatch.read(listOf("a", "b"), budget = 5) { "y".repeat(100) }.size)
    }
}
