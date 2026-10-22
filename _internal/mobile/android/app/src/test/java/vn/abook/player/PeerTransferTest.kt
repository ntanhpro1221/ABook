package vn.abook.player

import java.io.ByteArrayOutputStream
import java.io.File
import java.io.InputStream
import java.util.concurrent.atomic.AtomicLong
import org.junit.Assert.*
import org.junit.Test

class PeerTransferTest {
    @Test fun endless_stream_stops_before_writing_over_the_promised_size_including_resume() {
        val root = BookEditsFixtures.tempDir("peer-transfer")
        for (have in listOf(0L, 512L)) {
            var read = 0
            val input = object : InputStream() {
                override fun read(): Int = 120
                override fun read(b: ByteArray, off: Int, len: Int): Int {
                    b.fill(120, off, off + len); read += len; return len
                }
            }
            val out = ByteArrayOutputStream()
            assertTrue(runCatching { PeerTransfer.copy(input, out, 1024, root, have) }.exceptionOrNull() is PeerTransfer.Limit)
            assertTrue(have + out.size() <= 1024)
            assertTrue(have + read <= 1025)
        }
    }

    @Test fun disk_pressure_stops_before_writing_the_next_chunk() {
        val dir = object : File("unused") { override fun getUsableSpace() = 0L }
        val out = ByteArrayOutputStream()
        assertTrue(runCatching { PeerTransfer.copy("data".byteInputStream(), out, 1024, dir) }.isFailure)
        assertEquals(0, out.size())
    }

    @Test fun music_uses_the_same_budget_before_writing_and_keeps_old_file() {
        val root = BookEditsFixtures.tempDir("peer-music-budget")
        val name = "music/" + "a".repeat(40) + ".mp3"
        val target = Store.contained(root, name).apply { parentFile!!.mkdirs(); writeText("old") }
        val partial = File(target.path + ".part")
        var step = 0
        var mostWritten = 0L
        val input = object : InputStream() {
            override fun read(): Int = error("bulk only")
            override fun read(b: ByteArray, off: Int, len: Int): Int {
                mostWritten = maxOf(mostWritten, partial.length())
                if (step++ == 2) return -1
                val count = minOf(len, 1024)
                b.fill(120, off, off + count)
                return count
            }
        }
        assertFalse(BookMusic.fetch(root, BookMusic.Track(name, 1024, null)) { BookMusic.Source(input) })
        assertTrue("music overflow was written before validation", mostWritten <= 1024)
        assertEquals("old", target.readText())
        assertFalse(partial.exists())
    }
}
