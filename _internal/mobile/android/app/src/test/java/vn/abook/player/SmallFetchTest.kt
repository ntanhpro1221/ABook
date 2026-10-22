package vn.abook.player

import java.io.File
import java.io.InputStream
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import org.junit.Assert.*
import org.junit.Test
import kotlin.concurrent.thread

class SmallFetchTest {
    @Test fun unannounced_script_cannot_grow_past_its_budget() {
        val root = BookEditsFixtures.tempDir("small-budget")
        val target = File(root, "script.json").apply { writeText("old") }
        val input = object : InputStream() {
            var remaining = 16 * 1024 * 1024 + 1
            override fun read(): Int = error("bulk only")
            override fun read(b: ByteArray, off: Int, len: Int): Int {
                if (remaining == 0) return -1
                val count = minOf(len, remaining)
                b.fill(120, off, off + count)
                remaining -= count
                return count
            }
        }
        assertNull(Streaming.fetchSmallFile(target) { connection(input) })
        assertEquals("old", target.readText())
        assertEquals(listOf("script.json"), root.list()!!.toList())
    }
    @Test fun interrupted_fetch_preserves_old_target_and_removes_partial() {
        val root = BookEditsFixtures.tempDir("small-interrupted")
        val target = File(root, "script.json").apply { writeText("old") }
        val input = object : InputStream() {
            override fun read(): Int = throw java.io.IOException("cut")
        }
        assertNull(Streaming.fetchSmallFile(target) { connection(input) })
        assertEquals("old", target.readText())
        assertEquals(listOf("script.json"), root.list()!!.toList())
    }
    private fun connection(input: InputStream) = object : HttpURLConnection(URL("https://peer.invalid/file")) {
        override fun connect() {}
        override fun disconnect() {}
        override fun usingProxy() = false
        override fun getResponseCode() = 200
        override fun getInputStream() = input
    }

    @Test fun concurrent_fetches_never_publish_an_open_writer() {
        val target = File(BookEditsFixtures.tempDir("small-fetch"), "script.json").apply { writeText("old") }
        val halfway = CountDownLatch(1)
        val resume = CountDownLatch(1)
        val input = object : InputStream() {
            var step = 0
            override fun read(): Int = error("use bulk read")
            override fun read(b: ByteArray, off: Int, len: Int): Int {
                if (step == 2) return -1
                if (step++ == 1) {
                    halfway.countDown()
                    check(resume.await(5, TimeUnit.SECONDS))
                }
                "AAAA".toByteArray().copyInto(b, off)
                return 4
            }
        }
        val first = thread { Streaming.fetchSmallFile(target) { connection(input) } }
        assertTrue(halfway.await(5, TimeUnit.SECONDS))
        assertEquals("old", target.readText())
        val second = Streaming.fetchSmallFile(target) { connection("BBBBBBBB".byteInputStream()) }
        assertNotNull(second)
        assertEquals("BBBBBBBB", target.readText())
        resume.countDown()
        first.join(5000)
        assertFalse(first.isAlive)
        assertTrue("published corrupt data: ${target.readText()}", target.readText() in listOf("AAAAAAAA", "BBBBBBBB"))
    }
}
