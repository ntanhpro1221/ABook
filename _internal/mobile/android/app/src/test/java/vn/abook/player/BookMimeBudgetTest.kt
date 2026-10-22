package vn.abook.player

import java.io.InputStream
import org.junit.Assert.*
import org.junit.Test

class BookMimeBudgetTest {
    @Test fun oversized_mime_is_refused_before_opening_the_entry() {
        var opened = false
        assertTrue(runCatching { BookFileImport.readMime(1024 * 1024) { opened = true; ByteArray(1024).inputStream() } }.isFailure)
        assertFalse(opened)
    }

    @Test fun unknown_mime_size_is_still_read_with_a_tiny_budget() {
        var read = 0
        val input = object : InputStream() {
            override fun read(): Int = if (read++ < 1024) 120 else -1
        }
        assertTrue(runCatching { BookFileImport.readMime(-1) { input } }.isFailure)
        assertTrue(read <= BookFileImport.PROJECT_MIMETYPE.length + 1)
    }

    @Test fun mime_bytes_are_exact_without_trimming() {
        for (mime in listOf(BookFileImport.MIMETYPE, BookFileImport.PROJECT_MIMETYPE)) {
            assertEquals(mime, BookFileImport.readMime(mime.length.toLong()) { mime.byteInputStream() })
            assertTrue(runCatching { BookFileImport.readMime((mime.length + 1).toLong()) { "$mime\n".byteInputStream() } }.isFailure)
        }
    }
}
