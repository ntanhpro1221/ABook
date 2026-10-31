package vn.abook.player.net

import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertSame
import org.junit.Assert.assertTrue
import org.junit.Test
import vn.abook.player.NetErrors
import vn.abook.player.PeerTransfer
import java.io.ByteArrayOutputStream
import java.net.ConnectException
import java.net.SocketTimeoutException
import java.util.concurrent.atomic.AtomicBoolean

/** Chính sách chờ chung ([HostWait]) với một máy giả im lặng thật trên vòng lặp. Hạn rút còn 300 ms (`idleOverrideMs`) để bài thử chạy nhanh. */
class HostWaitTest {
    @After fun reset() { HostWait.idleOverrideMs = 0 }

    private fun fast() { HostWait.idleOverrideMs = 300 }

    private fun statusOf(host: FakeHost, path: String = "/x"): Int =
        HostWait.call {
            val connection = HostWait.open("${host.base}$path", 1000)
            try { HostWait.awaiting(connection) { connection.responseCode } } finally { connection.disconnect() }
        }

    @Test fun theLimitsAreTheDesktopOnes() {
        assertEquals(30_000, HostWait.idleMs("/api/listen/library"))
        assertEquals(100_000, HostWait.idleMs("/api/books/b1/pronunciation/preview"))
        assertEquals(100_000, HostWait.idleMs("/api/scan"))
        assertEquals(100_000, HostWait.idleMs("/api/readaloud/clip"))
        assertEquals(100_000, HostWait.idleMs("/api/readaloud/clip?voice=x"))
        assertEquals(100_000, HostWait.idleMs("/api/books/b1/voice/preview"))
        assertFalse(HostWait.isLongWork("/api/books/b1/voice"))
        assertFalse(HostWait.isLongWork("/media/books/b1/voice/preview"))
    }

    @Test fun aSilentHostIsAskedTwiceThenTimesOutWithReasonTimeout() {
        fast()
        FakeHost(FakeHost.silent).use { host ->
            val started = System.nanoTime()
            val error = runCatching { statusOf(host) }.exceptionOrNull()
            val seconds = (System.nanoTime() - started) / 1e9
            assertTrue("$error", error is HostWait.Timeout)
            assertEquals("timeout", (error as HostWait.Timeout).reason)
            assertTrue(error is SocketTimeoutException)
            assertEquals(NetErrors.Kind.TIMEOUT, NetErrors.kind(error))
            assertEquals(2, host.connections)
            assertTrue("hai lượt 300 ms mỗi lượt, không chờ mãi: $seconds s", seconds in 0.5..5.0)
        }
    }

    @Test fun aHostThatAnswersTheSecondTimeIsFine() {
        fast()
        FakeHost { attempt, socket, head -> if (attempt == 1) FakeHost.silent(attempt, socket, head) else FakeHost.reply(socket, 200, "{}") }.use { host ->
            assertEquals(200, statusOf(host))
            assertEquals(2, host.connections)
        }
    }

    @Test fun anAnswerThatKeepsTricklingIsNeverCut() {
        fast()
        val body = """{"ok":true}"""
        FakeHost { _, socket, _ ->
            socket.getOutputStream().apply {
                write("HTTP/1.1 200 X\r\nContent-Length: ${body.length}\r\nConnection: close\r\n\r\n".toByteArray())
                flush()
                for (ch in body) { Thread.sleep(120); write(ch.code); flush() } // 11 byte x 120 ms = 1,3 s, mỗi nhịp dưới hạn 300 ms
            }
        }.use { host ->
            val text = HostWait.call {
                val connection = HostWait.open("${host.base}/x", 1000)
                try { HostWait.awaiting(connection) { String(connection.inputStream.readBytes()) } } finally { connection.disconnect() }
            }
            assertEquals(body, text)
            assertEquals(1, host.connections)
        }
    }

    @Test fun aStallInTheMiddleOfTheBodyIsASilentHostToo() {
        fast()
        FakeHost { _, socket, _ ->
            socket.getOutputStream().apply { write("HTTP/1.1 200 X\r\nContent-Length: 50\r\n\r\nabc".toByteArray()); flush() }
            Thread.sleep(3000)
        }.use { host ->
            val error = runCatching {
                HostWait.call {
                    val connection = HostWait.open("${host.base}/x", 1000)
                    try { HostWait.awaiting(connection) { connection.inputStream.readBytes() } } finally { connection.disconnect() }
                }
            }.exceptionOrNull()
            assertTrue("$error", error is HostWait.Timeout)
            assertEquals(2, host.connections)
        }
    }

    @Test fun aPeerErrorAndAConnectionFailureAreNotTimeoutsAndAreNotResent() {
        fast()
        val attempts = intArrayOf(0)
        val peer = runCatching { HostWait.call { attempts[0]++; throw IllegalStateException("máy trả lỗi 500") } }.exceptionOrNull()
        assertTrue(peer is IllegalStateException)
        assertEquals(1, attempts[0])
        // Cổng không ai nghe: lỗi nối đi nguyên ra (UNREACHABLE), không phải "chưa trả lời kịp".
        val closed = java.net.ServerSocket(0).use { it.localPort }
        attempts[0] = 0
        val refused = runCatching {
            HostWait.call {
                attempts[0]++
                val connection = HostWait.open("http://127.0.0.1:$closed/x", 1000)
                try { HostWait.awaiting(connection) { connection.responseCode } } finally { connection.disconnect() }
            }
        }.exceptionOrNull()
        assertTrue("$refused", refused is ConnectException)
        assertFalse(refused is HostWait.Timeout)
        assertEquals(1, attempts[0])
    }

    @Test fun withoutResendTheFirstStallIsFinal() {
        fast()
        FakeHost(FakeHost.silent).use { host ->
            val error = runCatching {
                HostWait.call(resend = false) {
                    val connection = HostWait.open("${host.base}/x", 1000)
                    try { HostWait.awaiting(connection) { connection.responseCode } } finally { connection.disconnect() }
                }
            }.exceptionOrNull()
            assertTrue(error is HostWait.Timeout)
            assertEquals(1, host.connections)
        }
    }

    @Test fun aDownloadHeaderStallIsResentOnceThenTimesOut() {
        fast()
        FakeHost(FakeHost.silent).use { host ->
            val error = runCatching { PeerTransfer.openGet(pause = {}) { HostWait.open("${host.base}/f", 1000) } }.exceptionOrNull()
            assertTrue("$error", error is HostWait.Timeout)
            assertEquals(2, host.connections)
        }
        FakeHost { attempt, socket, head -> if (attempt == 1) FakeHost.silent(attempt, socket, head) else FakeHost.reply(socket, 200, "xyz", "text/plain") }.use { host ->
            val connection = PeerTransfer.openGet(pause = {}) { HostWait.open("${host.base}/f", 1000) }
            assertEquals(200, connection.responseCode)
            assertEquals("xyz", String(connection.inputStream.readBytes()))
            assertEquals(2, host.connections)
            connection.disconnect()
        }
    }

    @Test fun aHostThatStopsReadingAnUploadIsCutByTheWriteWatchdog() {
        fast()
        FakeHost { _, socket, _ -> Thread.sleep(8000); socket.close() }.use { host ->
            val connection = HostWait.open("${host.base}/up", 1000)
            connection.requestMethod = "POST"
            connection.doOutput = true
            connection.setChunkedStreamingMode(64 * 1024)
            val started = System.nanoTime()
            val error = runCatching {
                HostWait.writing(connection, 300) { alive ->
                    HostWait.counting(connection.outputStream, alive).use { out ->
                        val chunk = ByteArray(64 * 1024)
                        repeat(4096) { out.write(chunk) } // 256 MiB: máy kia không đọc thì kẹt ở đây
                    }
                }
            }.exceptionOrNull()
            val seconds = (System.nanoTime() - started) / 1e9
            assertTrue("$error", error is HostWait.Timeout)
            assertTrue("cắt ngay sau hạn, không chờ mãi: $seconds s", seconds < 6)
            assertEquals(1, host.connections)
        }
    }

    @Test fun aSlowButSteadyUploadIsNotCut() {
        fast()
        val received = ByteArrayOutputStream()
        val finished = AtomicBoolean(false)
        FakeHost { _, socket, _ ->
            val input = socket.getInputStream()
            val buffer = ByteArray(1024)
            // Thân gửi theo từng khúc (chunked): xong khi gặp khúc cuối rỗng.
            while (!received.toString("ISO-8859-1").endsWith("\r\n0\r\n\r\n")) { val n = input.read(buffer); if (n < 0) break; received.write(buffer, 0, n) }
            finished.set(true)
            FakeHost.reply(socket, 200, "{}")
        }.use { host ->
            val connection = HostWait.open("${host.base}/up", 1000)
            connection.requestMethod = "POST"
            connection.doOutput = true
            connection.setChunkedStreamingMode(1024)
            HostWait.writing(connection, 300) { alive ->
                HostWait.counting(connection.outputStream, alive).use { out ->
                    repeat(8) { out.write(ByteArray(1024)); out.flush(); Thread.sleep(150) } // 1,2 s > hạn, nhưng khúc nào cũng tới đúng nhịp
                }
            }
            assertEquals(200, connection.responseCode)
            assertTrue(finished.get())
            connection.disconnect()
        }
    }

    @Test fun theLastTimeoutIsThrownAsIs() {
        val last = HostWait.Timeout()
        val error = runCatching { HostWait.call { throw last } }.exceptionOrNull()
        assertSame(last, error)
    }
}
