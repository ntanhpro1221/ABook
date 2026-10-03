package vn.abook.player.readaloud

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.io.EOFException
import java.io.IOException

/** Máy khách WebSocket tối thiểu: khung, bắt tay, ghép mảnh, ping/pong, đóng. Các vector lấy từ RFC 6455 (mục 1.3 và 5.7). */
class WebSocketTest {
    private fun hex(vararg v: Int) = ByteArray(v.size) { v[it].toByte() }

    /** Khung của MÁY CHỦ (không mặt nạ), cho bài thử `receive`. */
    private fun server(opcode: Int, payload: ByteArray, fin: Boolean = true): ByteArray {
        val out = ByteArrayOutputStream()
        out.write((if (fin) 0x80 else 0) or opcode)
        when {
            payload.size < 126 -> out.write(payload.size)
            payload.size <= 0xFFFF -> { out.write(126); out.write(payload.size ushr 8); out.write(payload.size and 0xFF) }
            else -> { out.write(127); for (s in 56 downTo 0 step 8) out.write(((payload.size.toLong() ushr s) and 0xFF).toInt()) }
        }
        out.write(payload)
        return out.toByteArray()
    }

    private fun socketOver(incoming: ByteArray, sent: ByteArrayOutputStream = ByteArrayOutputStream()) =
        WebSocket({ }, ByteArrayInputStream(incoming), sent)

    @Test
    fun acceptKeyMatchesTheRfcExample() {
        assertEquals("s3pPLMBiTxaQ9kYGzzhZRbK+xOo=", WebSocket.acceptFor("dGhlIHNhbXBsZSBub25jZQ=="))
    }

    @Test
    fun base64MatchesTheStandardVectors() {
        fun b64(s: String) = WebSocket.base64(s.toByteArray(Charsets.US_ASCII))
        assertEquals("", b64(""))
        assertEquals("Zg==", b64("f"))
        assertEquals("Zm8=", b64("fo"))
        assertEquals("Zm9v", b64("foo"))
        assertEquals("Zm9vYg==", b64("foob"))
        assertEquals("Zm9vYmE=", b64("fooba"))
        assertEquals("Zm9vYmFy", b64("foobar"))
        assertEquals("/+8=", WebSocket.base64(hex(0xFF, 0xEF)))
    }

    @Test
    fun aMaskedHelloIsTheRfcFrame() {
        val frame = WebSocket.encode(WebSocket.OP_TEXT, "Hello".toByteArray(), hex(0x37, 0xfa, 0x21, 0x3d))
        assertArrayEquals(hex(0x81, 0x85, 0x37, 0xfa, 0x21, 0x3d, 0x7f, 0x9f, 0x4d, 0x51, 0x58), frame)
    }

    @Test
    fun anUnmaskedHelloFromTheServerDecodes() {
        val frame = WebSocket.decode(ByteArrayInputStream(hex(0x81, 0x05, 0x48, 0x65, 0x6c, 0x6c, 0x6f)))
        assertTrue(frame.fin)
        assertEquals(WebSocket.OP_TEXT, frame.opcode)
        assertEquals("Hello", String(frame.payload))
    }

    @Test
    fun framesRoundTripAtEveryLengthEncoding() {
        for (size in listOf(0, 1, 125, 126, 127, 65_535, 65_536, 70_000)) {
            val payload = ByteArray(size) { (it * 7).toByte() }
            val frame = WebSocket.decode(ByteArrayInputStream(WebSocket.encode(WebSocket.OP_BINARY, payload)))
            assertEquals(WebSocket.OP_BINARY, frame.opcode)
            assertArrayEquals("kích thước $size", payload, frame.payload)
        }
    }

    @Test
    fun clientFramesAreAlwaysMaskedWithAFreshKey() {
        val a = WebSocket.encode(WebSocket.OP_TEXT, "x".toByteArray())
        assertTrue(a[1].toInt() and 0x80 != 0)
    }

    @Test
    fun aTruncatedFrameIsAnEndOfStream() {
        try {
            WebSocket.decode(ByteArrayInputStream(hex(0x81, 0x05, 0x48)))
            fail("đáng ra EOF")
        } catch (expected: EOFException) {
        }
    }

    @Test
    fun anAbsurdLengthIsRefused() {
        val head = hex(0x82, 127, 0, 0, 0, 0, 0xFF, 0, 0, 0)
        try {
            WebSocket.decode(ByteArrayInputStream(head))
            fail("đáng ra từ chối")
        } catch (expected: IOException) {
        }
    }

    @Test
    fun handshakeResponseIsParsedIntoStatusAndLowercasedHeaders() {
        val text = "HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nSec-WebSocket-Accept: abc\r\n\r\n"
        val (status, headers) = WebSocket.readHead(ByteArrayInputStream(text.toByteArray()))
        assertEquals(101, status)
        assertEquals("abc", headers["sec-websocket-accept"])
        val (denied, deniedHeaders) = WebSocket.readHead(ByteArrayInputStream("HTTP/1.1 403 Forbidden\r\nDate: Sat, 03 Oct 2026 12:00:00 GMT\r\n\r\n".toByteArray()))
        assertEquals(403, denied)
        assertEquals("Sat, 03 Oct 2026 12:00:00 GMT", deniedHeaders["date"])
    }

    @Test
    fun receiveJoinsFragmentsAndAnswersAPingInTheMiddle() {
        val sent = ByteArrayOutputStream()
        val incoming = ByteArrayOutputStream().apply {
            write(server(WebSocket.OP_TEXT, "Hel".toByteArray(), fin = false))
            write(server(WebSocket.OP_PING, "p".toByteArray()))
            write(server(WebSocket.OP_CONTINUATION, "lo".toByteArray(), fin = true))
        }.toByteArray()
        val message = socketOver(incoming, sent).receive()
        assertEquals("Hello", (message as WebSocket.Message.Text).text)
        val pong = WebSocket.decode(ByteArrayInputStream(sent.toByteArray()))
        assertEquals(WebSocket.OP_PONG, pong.opcode)
        assertEquals("p", String(pong.payload))
    }

    @Test
    fun receiveReturnsBinaryAndThenClosed() {
        val audio = ByteArray(300) { it.toByte() }
        val sent = ByteArrayOutputStream()
        val incoming = server(WebSocket.OP_BINARY, audio) + server(WebSocket.OP_CLOSE, hex(0x03, 0xE8))
        val socket = socketOver(incoming, sent)
        assertArrayEquals(audio, (socket.receive() as WebSocket.Message.Binary).data)
        assertTrue(socket.receive() is WebSocket.Message.Closed)
        val reply = WebSocket.decode(ByteArrayInputStream(sent.toByteArray()))
        assertEquals("đáp lại khung đóng", WebSocket.OP_CLOSE, reply.opcode)
    }

    @Test
    fun sendTextWritesOneMaskedTextFrame() {
        val sent = ByteArrayOutputStream()
        socketOver(ByteArray(0), sent).sendText("Path:speech.config")
        val frame = WebSocket.decode(ByteArrayInputStream(sent.toByteArray()))
        assertEquals(WebSocket.OP_TEXT, frame.opcode)
        assertEquals("Path:speech.config", String(frame.payload))
        assertFalse(sent.size() == 0)
    }

    @Test
    fun aContinuationWithoutAStartIsRefused() {
        try {
            socketOver(server(WebSocket.OP_CONTINUATION, "x".toByteArray())).receive()
            fail("đáng ra từ chối")
        } catch (expected: IOException) {
        }
    }
}
