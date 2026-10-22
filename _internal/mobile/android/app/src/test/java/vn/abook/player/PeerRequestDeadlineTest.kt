package vn.abook.player

import java.io.ByteArrayOutputStream
import java.io.File
import java.io.InputStream
import java.net.InetAddress
import java.net.Socket
import java.net.SocketException
import java.security.MessageDigest
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class PeerRequestDeadlineTest {
    private class Alarm(val due: Long, val expire: () -> Unit) { var cancelled = false }

    private fun request(paired: Boolean, slowHeaders: Boolean = false) {
        val token = "deadline-test-token"
        val root = BookEditsFixtures.tempDir("peer-deadline")
        val devices = File(root, "share.json")
        val digest = MessageDigest.getInstance("SHA-256").digest(token.toByteArray()).joinToString("") { "%02x".format(it) }
        devices.writeText(JSONObject().put("devices", JSONObject().put(digest,
            JSONObject().put("name", "test").put("lastSeen", 1e12))).toString())
        val field = LibraryServer::class.java.getDeclaredField("devicesFile").apply { isAccessible = true }
        val previous = field.get(LibraryServer)
        field.set(LibraryServer, devices)
        var now = 0L
        var closed = false
        val alarms = mutableListOf<Alarm>()
        val bodySize = 1024 * 1024
        val header = ("POST /sync/v1/unknown HTTP/1.1\r\nContent-Length: $bodySize\r\n" +
            (if (paired) "Authorization: Bearer $token\r\n" else "") + "\r\n").toByteArray()
        fun advance(time: Long) {
            now = time
            alarms.filter { !it.cancelled && it.due <= now }.forEach { it.cancelled = true; it.expire() }
            if (closed) throw SocketException("deadline")
        }
        val input = object : InputStream() {
            var head = 0
            var body = 0
            override fun read(): Int { val b = ByteArray(1); return if (read(b, 0, 1) < 0) -1 else b[0].toInt() and 255 }
            override fun read(b: ByteArray, off: Int, len: Int): Int {
                if (head < header.size) {
                    val count = if (slowHeaders) 1 else minOf(len, header.size - head)
                    header.copyInto(b, off, head, head + count)
                    head += count
                    if (slowHeaders) advance(35_000L * head / header.size)
                    return count
                }
                if (body == bodySize) return -1
                val count = minOf(len, bodySize - body)
                b.fill(120, off, off + count)
                body += count
                advance(35_000L * body / bodySize)
                return count
            }
        }
        val output = ByteArrayOutputStream()
        val socket = object : Socket() {
            override fun getInetAddress() = InetAddress.getByName("127.0.0.1")
            override fun getInputStream() = input
            override fun getOutputStream() = output
            override fun close() { closed = true }
        }
        try {
            val result = runCatching { LibraryServer.handleRequest(socket) { millis, expire ->
                val alarm = Alarm(now + millis, expire).also { alarms.add(it) }
                val cancel: () -> Unit = { alarm.cancelled = true }
                cancel
            } }
            if (paired && !slowHeaders) {
                result.getOrThrow()
                assertEquals(35_000L, now)
                assertFalse(closed)
                assertTrue(output.toString("UTF-8").startsWith("HTTP/1.1 404"))
                assertEquals(LibraryServer.PEER_HEADER_MILLIS + bodySize * 1000L /
                    LibraryServer.PEER_MIN_BODY_BYTES_PER_SECOND, alarms.last().due)
            } else {
                assertTrue(result.exceptionOrNull() is SocketException)
                assertTrue(closed)
                assertEquals(1, alarms.size)
                assertEquals(LibraryServer.PEER_HEADER_MILLIS, alarms.single().due)
            }
            assertTrue(alarms.all { it.cancelled })
        } finally { field.set(LibraryServer, previous) }
    }

    @Test fun paired_one_megabyte_body_over_35_seconds_is_received() = request(paired = true)
    @Test fun unknown_body_still_has_the_30_second_deadline() = request(paired = false)
    @Test fun unknown_dripping_headers_are_cut_at_30_seconds() = request(paired = false, slowHeaders = true)
}
