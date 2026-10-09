package vn.abook.player

import java.io.File
import java.nio.file.Files
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/** Dấu trang đặt ở màn đọc trỏ tới CÂU: vị trí câu + ~60 chữ đầu câu, cùng trường với máy tính (tests/test_sentence_bookmarks.py). */
class StoreSentenceBookmarkTest {
    @Before
    fun setUp() {
        val root = Files.createTempDirectory("abook-bookmark").toFile()
        Store::class.java.getDeclaredField("root").apply { isAccessible = true }.set(null, root)
        Store::class.java.getDeclaredField("recordsCache").apply { isAccessible = true }.set(null, null)
        File(root, "state").mkdirs()
        File(root, "books/b1").mkdirs()
    }

    @Test
    fun a_reader_bookmark_keeps_the_sentence_and_a_player_bookmark_does_not() {
        val long = "Trời   đã sáng,\n" + "và sương còn phủ kín cánh đồng làng ".repeat(5)
        val reader = Store.addBookmark("b1", 2, 0.0, "", 7, long)
        assertEquals(7, reader.getInt("index"))
        assertTrue(reader.getString("quote").length <= 61)
        assertEquals("Trời đã sáng, và sương còn phủ kín cánh đồng làng và sương…", reader.getString("quote"))
        assertEquals("Câu ngắn.", Store.bookmarkQuote("  Câu   ngắn.\n"))
        val player = Store.addBookmark("b1", 2, 64.0, "")
        assertFalse(player.has("index"))
        assertFalse(player.has("quote"))
    }
}
