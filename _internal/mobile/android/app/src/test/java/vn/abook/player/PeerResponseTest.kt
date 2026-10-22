package vn.abook.player

import java.io.InputStream
import java.net.HttpURLConnection
import java.net.URL
import org.junit.Assert.*
import org.junit.Test

class PeerResponseTest {
    @Test fun response_budgets_cover_announced_chunked_and_error_bodies() {
        for (code in listOf(200, 500)) for (announced in listOf(false, true)) {
            val cap = if (code >= 400) 64 * 1024 else 16 * 1024 * 1024
            var read = 0
            val input = object : InputStream() {
                override fun read(): Int = if (read++ <= cap) 32 else -1
                override fun read(b: ByteArray, off: Int, len: Int): Int {
                    if (read > cap) return -1
                    val count = minOf(len, cap + 1 - read)
                    b.fill(32, off, off + count)
                    read += count
                    return count
                }
            }
            val connection = object : HttpURLConnection(URL("https://peer.invalid/reply")) {
                override fun connect() {}
                override fun disconnect() {}
                override fun usingProxy() = false
                override fun getInputStream() = input
                override fun getErrorStream() = input
                override fun getHeaderField(name: String): String? = if (name.equals("Content-Length", true) && announced) (cap + 1).toString() else null
            }
            assertTrue("unbounded body ($code, $announced)", runCatching { SyncLink.responseText(connection, code) }.isFailure)
            assertTrue(read <= if (announced) 0 else cap + 1)
        }
    }
}
