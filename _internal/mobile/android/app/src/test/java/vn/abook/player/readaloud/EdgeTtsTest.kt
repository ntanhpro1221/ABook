package vn.abook.player.readaloud

import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.io.File
import java.io.InputStream
import java.net.SocketTimeoutException
import java.net.UnknownHostException

/** Giao thức Edge (token Sec-MS-GEC, tin, mốc chữ) và giọng Edge chạy trên một máy chủ giả: khung dựng sẵn, không mạng. */
class EdgeTtsTest {
    private val dir = java.nio.file.Files.createTempDirectory("edge-tts").toFile()

    @After
    fun cleanUp() {
        EdgeTts.clockSkewSeconds = 0.0
        dir.deleteRecursively()
    }

    // ---- giao thức ----------------------------------------------------------------------------

    @Test
    fun secMsGecIsTheUppercaseSha256OfTheFiveMinuteWindowAndTheToken() {
        // Số kỳ vọng tính bằng edge-tts (drm.py) cho giờ 1700000000.5.
        assertEquals("42301B335578FEFDAE2637DED1ABD614505D432559EC08032B82048483726AFF", EdgeProtocol.secMsGec(1_700_000_000.5))
    }

    @Test
    fun secMsGecIsStableInsideTheFiveMinuteWindowAndChangesAfterIt() {
        val start = EdgeProtocol.secMsGec(1_699_999_800.0)
        assertEquals(start, EdgeProtocol.secMsGec(1_700_000_099.9))
        assertNotEquals(start, EdgeProtocol.secMsGec(1_700_000_100.0))
    }

    @Test
    fun theUrlCarriesTokenConnectionIdAndVersion() {
        val url = EdgeProtocol.url("abc123", 1_700_000_000.5)
        assertTrue(url.startsWith("wss://speech.platform.bing.com/consumer/speech/synthesize/readaloud/edge/v1?TrustedClientToken=6A5AA1D4EAFF4E9FB37E23D68491D6F4"))
        assertTrue(url.contains("&ConnectionId=abc123&Sec-MS-GEC=42301B33"))
        assertTrue(url.endsWith("&Sec-MS-GEC-Version=1-143.0.3650.75"))
    }

    @Test
    fun speechConfigAsksForWordBoundariesAnd48kMp3() {
        val config = EdgeProtocol.speechConfig("Sat Oct 03 2026 12:00:00 GMT+0000 (Coordinated Universal Time)")
        assertTrue(config.contains("Path:speech.config\r\n\r\n"))
        assertTrue(config.contains("\"wordBoundaryEnabled\":\"true\""))
        assertTrue(config.contains("\"outputFormat\":\"audio-24khz-48kbitrate-mono-mp3\""))
    }

    @Test
    fun ssmlNamesTheVoiceAndKeepsTheStrangeTimestampZ() {
        val message = EdgeProtocol.ssml("vi-VN-HoaiMyNeural", "Xin chào", "rid", "STAMP")
        assertTrue(message.startsWith("X-RequestId:rid\r\nContent-Type:application/ssml+xml\r\nX-Timestamp:STAMPZ\r\nPath:ssml\r\n\r\n<speak"))
        assertTrue(message.contains("<voice name='vi-VN-HoaiMyNeural'>"))
        assertTrue(message.endsWith("Xin chào</prosody></voice></speak>"))
    }

    @Test
    fun escapeProtectsXmlAndReplacesControlCharacters() {
        assertEquals("a &amp; b &lt;c&gt; d e", EdgeProtocol.escape("a & b <c> d\u000Be"))
        assertEquals(5, EdgeProtocol.escapedBytes('&'))
        assertEquals(2, EdgeProtocol.escapedBytes('é'))
        assertEquals(3, EdgeProtocol.escapedBytes('ạ'))
        assertEquals(3, EdgeProtocol.escapedBytes('—'))
    }

    @Test
    fun metadataBecomesBoundariesInMillisecondsPlusTheShift() {
        val body = """{"Metadata":[{"Type":"WordBoundary","Data":{"Offset":4500000,"Duration":3000000,"text":{"Text":"R&amp;D","Length":3,"BoundaryType":"WordBoundary"}}},{"Type":"SessionEnd","Data":{"Offset":9}}]}"""
        val list = EdgeProtocol.parseMetadata(body, 100)
        assertEquals(1, list.size)
        assertEquals(Boundary(550, 850, "R&D"), list[0])
    }

    @Test
    fun binaryMessagesSplitIntoHeaderAndAudio() {
        val header = "X-RequestId:r\r\nPath:audio\r\n".toByteArray()
        val data = byteArrayOf(1, 2, 3)
        val message = byteArrayOf((header.size ushr 8).toByte(), header.size.toByte()) + header + data
        val (headers, audio) = EdgeProtocol.parseBinary(message)!!
        assertEquals("audio", headers["Path"])
        assertEquals(listOf<Byte>(1, 2, 3), audio.toList())
        assertEquals(null, EdgeProtocol.parseBinary(byteArrayOf(0, 99, 1)))
    }

    @Test
    fun durationComesFromTheByteCountAtFortyEightKbps() {
        assertEquals(1000, EdgeProtocol.durationMs(6000))
        assertEquals(2500, EdgeProtocol.durationMs(15_000))
    }

    @Test
    fun theServerDateHeaderParses() {
        val seconds = EdgeTts.parseHttpDate("Sat, 03 Oct 2026 12:00:00 GMT")
        assertNotNull(seconds)
        assertEquals(1_791_028_800.0, seconds!!, 0.0)
        assertEquals(null, EdgeTts.parseHttpDate("not a date"))
    }

    // ---- giọng trên máy chủ giả -------------------------------------------------------------------

    private fun frame(opcode: Int, payload: ByteArray): ByteArray {
        val out = ByteArrayOutputStream()
        out.write(0x80 or opcode)
        if (payload.size < 126) out.write(payload.size) else { out.write(126); out.write(payload.size ushr 8); out.write(payload.size and 0xFF) }
        out.write(payload)
        return out.toByteArray()
    }

    private fun text(path: String, body: String = "") = frame(WebSocket.OP_TEXT, "X-RequestId:r\r\nPath:$path\r\n\r\n$body".toByteArray())

    private fun audio(bytes: Int): ByteArray {
        val header = "X-RequestId:r\r\nContent-Type:audio/mpeg\r\nPath:audio\r\n".toByteArray()
        return frame(WebSocket.OP_BINARY, byteArrayOf((header.size ushr 8).toByte(), header.size.toByte()) + header + ByteArray(bytes) { 7 })
    }

    private fun metadata(offset: Long, duration: Long, word: String) =
        text("audio.metadata", """{"Metadata":[{"Type":"WordBoundary","Data":{"Offset":$offset,"Duration":$duration,"text":{"Text":"$word","Length":${word.length},"BoundaryType":"WordBoundary"}}}]}""")

    private class Fake(val replies: List<ByteArray>) {
        val urls = mutableListOf<String>()
        val headers = mutableListOf<Map<String, String>>()
        val sent = ByteArrayOutputStream()
        var calls = 0
        fun connector() = EdgeTts.Connector { url, header ->
            urls += url
            headers += header
            WebSocket({ }, ByteArrayInputStream(replies[minOf(calls++, replies.size - 1)]), sent)
        }
    }

    private fun session(vararg frames: ByteArray) = frames.fold(ByteArray(0)) { a, b -> a + b }

    @Test
    fun synthesizesAClipWithWordTimesFromTheBoundaries() {
        val fake = Fake(listOf(session(
            text("turn.start"), text("response"), audio(3000), audio(3000),
            metadata(0, 4_000_000, "Xin"), metadata(4_500_000, 3_000_000, "chào"), text("turn.end"),
        )))
        val out = File(dir, "a.mp3")
        val clip = EdgeTts("vi-VN-HoaiMyNeural", fake.connector()).synthesize("Xin chào", out)
        assertEquals("edge:vi-VN-HoaiMyNeural", clip.voice)
        assertEquals(1000, clip.durationMs)
        assertEquals(6000, out.length())
        // Mốc Edge cộng 100 ms bù trễ bộ mã mp3.
        assertEquals(listOf(Span(100, 500), Span(550, 850)), clip.words)
        assertEquals(1, fake.calls)
        assertTrue(fake.urls[0].contains("Sec-MS-GEC="))
        assertTrue(fake.headers[0]["Origin"]!!.startsWith("chrome-extension://"))
        assertTrue(fake.headers[0]["Cookie"]!!.startsWith("muid="))
        // Máy khách gửi cấu hình rồi SSML, cả hai là khung chữ có mặt nạ.
        val sentFrames = ByteArrayInputStream(fake.sent.toByteArray())
        val config = String(WebSocket.decode(sentFrames).payload)
        val ssml = String(WebSocket.decode(sentFrames).payload)
        assertTrue(config.contains("Path:speech.config"))
        assertTrue(ssml.contains("Path:ssml") && ssml.contains("Xin chào"))
    }

    @Test
    fun noBoundariesStillGiveEvenlySpreadWords() {
        val fake = Fake(listOf(session(text("turn.start"), audio(6000), text("turn.end"))))
        val clip = EdgeTts("vi-VN-NamMinhNeural", fake.connector()).synthesize("một hai", File(dir, "b.mp3"))
        assertEquals(2, clip.words.size)
        assertEquals(0, clip.words[0].start)
        assertEquals(1000, clip.words[1].end)
    }

    @Test
    fun aLongParagraphGoesInSeveralCallsAndTheClipsAreJoined() {
        val body = "ab ".repeat(1400).trim()
        val fake = Fake(listOf(session(audio(6000), text("turn.end"))))
        val clip = EdgeTts("vi-VN-HoaiMyNeural", fake.connector()).synthesize(body, File(dir, "c.mp3"))
        assertTrue(fake.calls >= 2)
        assertEquals(1000L * fake.calls, clip.durationMs)
        assertEquals(1400, clip.words.size)
        assertTrue(clip.words.last().end <= clip.durationMs)
    }

    @Test
    fun noAudioIsAnError() {
        val fake = Fake(listOf(session(text("turn.start"), text("turn.end"))))
        try {
            EdgeTts("v", fake.connector()).synthesize("Xin", File(dir, "d.mp3"))
            fail("đáng ra lỗi")
        } catch (error: VoiceException) {
            assertTrue(error.message!!.contains("không trả về âm thanh"))
        }
    }

    @Test
    fun noNetworkIsAnOfflineErrorInVietnamese() {
        val connector = EdgeTts.Connector { _, _ -> throw UnknownHostException("speech.platform.bing.com") }
        try {
            EdgeTts("v", connector).synthesize("Xin", File(dir, "e.mp3"))
            fail("đáng ra lỗi")
        } catch (error: VoiceException) {
            assertTrue(error.offline)
            assertTrue(error.message!!.startsWith("Không có mạng"))
        }
    }

    @Test
    fun aStalledServerTimesOutInsteadOfWaitingForever() {
        val stalled = object : InputStream() {
            override fun read(): Int = throw SocketTimeoutException("read timed out")
        }
        val connector = EdgeTts.Connector { _, _ -> WebSocket({ }, stalled, ByteArrayOutputStream()) }
        try {
            EdgeTts("v", connector).synthesize("Xin", File(dir, "f.mp3"))
            fail("đáng ra lỗi")
        } catch (error: VoiceException) {
            assertTrue(error.offline)
            assertTrue(error.message!!.contains("quá chậm"))
        }
    }

    @Test
    fun aRefusedHandshakeLearnsTheClockSkewAndRetriesOnce() {
        val calls = intArrayOf(0)
        val connector = EdgeTts.Connector { _, _ ->
            if (calls[0]++ == 0) throw HandshakeException(403, mapOf("date" to "Sat, 03 Oct 2026 12:00:00 GMT"))
            WebSocket({ }, ByteArrayInputStream(session(audio(6000), text("turn.end"))), ByteArrayOutputStream())
        }
        val clip = EdgeTts("v", connector).synthesize("Xin", File(dir, "g.mp3"))
        assertEquals(2, calls[0])
        assertEquals(1000, clip.durationMs)
        assertNotEquals(0.0, EdgeTts.clockSkewSeconds, 0.0)
    }

    @Test
    fun aSecondRefusalIsReportedNotRetriedForever() {
        val calls = intArrayOf(0)
        val connector = EdgeTts.Connector { _, _ ->
            calls[0]++
            throw HandshakeException(403, mapOf("date" to "Sat, 03 Oct 2026 12:00:00 GMT"))
        }
        try {
            EdgeTts("v", connector).synthesize("Xin", File(dir, "h.mp3"))
            fail("đáng ra lỗi")
        } catch (error: VoiceException) {
            assertFalse(error.offline)
            assertEquals(2, calls[0])
        }
    }
}
