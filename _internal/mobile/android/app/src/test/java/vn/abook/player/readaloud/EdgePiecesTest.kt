package vn.abook.player.readaloud

import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.io.File
import java.io.InputStream
import java.util.concurrent.Semaphore
import java.util.concurrent.atomic.AtomicInteger

/**
 * Đọc song song các câu của một đoạn (uxfix47): luật cắt mảnh trên bộ ví dụ DÙNG CHUNG với pytest (tests/fixtures/readaloud/edge/pieces.json), mốc chữ sau khi nối, trần
 * kết nối, lỗi một mảnh - mọi thứ trên máy chủ giả, không mạng.
 */
class EdgePiecesTest {
    private val dir = java.nio.file.Files.createTempDirectory("edge-pieces").toFile()
    private val sentences = "Trời đã sẩm tối khi đoàn người tới được cổng làng. Người gác cổng đứng chờ sẵn, tay cầm chiếc đèn dầu cũ. " +
        "Họ im lặng bước vào sân, nơi mấy con chó nằm ngủ dưới hiên. Mưa bắt đầu rơi lúc nào không ai hay."

    @After
    fun cleanUp() {
        EdgeTts.connections = Semaphore(EdgePieces.EDGE_CONNECTIONS)
        dir.deleteRecursively()
    }

    @Test
    fun theSharedCasesCutTheSameWayAsPython() {
        val file = File("../../../tests/fixtures/readaloud/edge/pieces.json")
        assertTrue("Không thấy ${file.absoluteFile}", file.isFile)
        val cases = JSONObject(file.readText(Charsets.UTF_8)).getJSONArray("cases")
        assertTrue(cases.length() >= 8)
        for (i in 0 until cases.length()) {
            val case = cases.getJSONObject(i)
            val expected = case.getJSONArray("pieces").let { array -> List(array.length()) { array.getString(it) } }
            assertEquals(case.getString("note"), expected, EdgePieces.split(case.getString("text")))
        }
    }

    @Test
    fun aShortParagraphStaysOneRequestAndBlankIsNothing() {
        assertEquals(listOf("Một. Hai. Ba."), EdgePieces.split("Một. Hai. Ba."))
        assertEquals(emptyList<String>(), EdgePieces.split("   "))
    }

    @Test
    fun piecesAreFewBalancedAndNeverTiny() {
        val text = (1..24).joinToString(" ") { "Câu số $it nói về chuyện nhỏ." }
        val pieces = EdgePieces.split(text)
        assertTrue(pieces.size in 2..EdgePieces.PIECE_PARALLEL)
        assertEquals(text.split(" "), pieces.joinToString(" ").split(" "))
        assertTrue(pieces.all { it.length >= EdgePieces.MIN_PIECE_CHARS })
        assertTrue(pieces.all { it.endsWith(".") })
    }

    @Test
    fun theServiceByteLimitStillApplies() {
        val text = (1..600).joinToString(" ") { "Câu số một hai ba." }
        val pieces = EdgePieces.split(text)
        assertTrue(pieces.size > EdgePieces.PIECE_PARALLEL)
        assertTrue(pieces.all { piece -> piece.sumOf { EdgeProtocol.escapedBytes(it) } <= EdgeProtocol.MAX_TEXT_BYTES })
    }

    // ---- máy chủ giả: trả lời theo CHỮ mảnh gửi lên (số chữ), có thể chậm ----------------------------------------------------

    private fun frame(opcode: Int, payload: ByteArray): ByteArray {
        val out = ByteArrayOutputStream()
        out.write(0x80 or opcode)
        if (payload.size < 126) out.write(payload.size) else { out.write(126); out.write(payload.size ushr 8); out.write(payload.size and 0xFF) }
        out.write(payload)
        return out.toByteArray()
    }

    private fun text(path: String, body: String = "") = frame(WebSocket.OP_TEXT, "X-RequestId:r\r\nPath:$path\r\n\r\n$body".toByteArray())

    private fun audio(bytes: Int, fill: Byte): ByteArray {
        val header = "X-RequestId:r\r\nContent-Type:audio/mpeg\r\nPath:audio\r\n".toByteArray()
        return frame(WebSocket.OP_BINARY, byteArrayOf((header.size ushr 8).toByte(), header.size.toByte()) + header + ByteArray(bytes) { fill })
    }

    private fun metadata(offset: Long, duration: Long, word: String) =
        text("audio.metadata", """{"Metadata":[{"Type":"WordBoundary","Data":{"Offset":$offset,"Duration":$duration,"text":{"Text":"$word","Length":${word.length},"BoundaryType":"WordBoundary"}}}]}""")

    /** Đọc chữ trong khung SSML mà máy khách đã gửi vào `sent`. */
    private fun spokenIn(sent: ByteArray): String {
        val input = ByteArrayInputStream(sent)
        WebSocket.decode(input) // speech.config
        val ssml = String(WebSocket.decode(input).payload)
        return ssml.substringAfter("volume='+0%'>").substringBefore("</prosody>")
    }

    /** Luồng trả lời dựng khi máy khách đọc lần đầu - lúc ấy chữ đã gửi xong, nên biết đang là mảnh nào. */
    private class Reply(val sent: ByteArrayOutputStream, val build: (ByteArray) -> ByteArray) : InputStream() {
        private var data: ByteArrayInputStream? = null
        private fun source() = data ?: ByteArrayInputStream(build(sent.toByteArray())).also { data = it }
        override fun read(): Int = source().read()
        override fun read(b: ByteArray, off: Int, len: Int): Int = source().read(b, off, len)
    }

    /** Mảnh có `w` chữ trả `w` x 600 byte (100 ms một chữ) mp3 điền byte `w`, mỗi chữ một mốc 100 ms; mảnh đứng đầu chậm hơn. */
    private fun connectorBySpokenWords(live: AtomicInteger? = null, peak: AtomicInteger? = null, failOn: (String) -> Boolean = { false }) = EdgeTts.Connector { _, _ ->
        val sent = ByteArrayOutputStream()
        live?.let { peak?.accumulateAndGet(it.incrementAndGet(), { a, b -> maxOf(a, b) }) }
        WebSocket({ live?.decrementAndGet() }, Reply(sent) { bytes ->
            val spoken = spokenIn(bytes)
            if (failOn(spoken)) throw java.io.IOException("hỏng")
            val words = spoken.split(" ")
            Thread.sleep(if (spoken.startsWith("Trời")) 250 else 30) // mảnh đầu xong SAU các mảnh khác
            var reply = ByteArray(0)
            words.forEachIndexed { i, word -> reply += metadata(i * 1_000_000L, 800_000, word) }
            reply + audio(words.size * 600, words.size.toByte()) + text("turn.end")
        }, sent)
    }

    @Test
    fun piecesFinishingOutOfOrderAreJoinedInReadingOrderWithOffsets() {
        val pieces = EdgePieces.split(sentences)
        assertTrue(pieces.size >= 2)
        val out = File(dir, "a.mp3")
        val clip = EdgeTts("v", connectorBySpokenWords()).synthesize(sentences, out)
        val bytes = out.readBytes()
        var at = 0
        for (piece in pieces) { // mp3 ghép đúng thứ tự đọc: mỗi mảnh điền byte = số chữ của mảnh ấy
            val words = piece.split(" ").size
            assertTrue(bytes.slice(at until at + words * 600).all { it == words.toByte() })
            at += words * 600
        }
        assertEquals(at, bytes.size)
        assertEquals(at * 1000L / 6000, clip.durationMs)
        assertEquals(sentences.split(" ").size, clip.words.size)
        var firstWord = 0
        var before = 0L
        for (piece in pieces) { // chữ đầu của mỗi mảnh bắt đầu sau toàn bộ audio các mảnh trước (+ 100 ms bù trễ bộ mã)
            val words = piece.split(" ").size
            assertEquals(before + EdgeProtocol.BOUNDARY_SHIFT_MS, clip.words[firstWord].start)
            before += words * 100L
            firstWord += words
        }
        for (i in 1 until clip.words.size) assertTrue(clip.words[i].start >= clip.words[i - 1].start)
        assertTrue(clip.words.last().end <= clip.durationMs)
    }

    @Test
    fun aFailingPieceFailsTheClipWithTheSameKindOfError() {
        val connector = EdgeTts.Connector { _, _ ->
            val sent = ByteArrayOutputStream()
            WebSocket({ }, Reply(sent) { bytes -> if ("Người gác" in spokenIn(bytes)) throw java.io.IOException("x") else audio(600, 1) + text("turn.end") }, sent)
        }
        // Hỏng lượt giữa chừng ở mảnh có "Người gác": thử lại đủ lần rồi báo như khi đọc nối tiếp (dịch vụ không trả lời - không phải mất mạng).
        try {
            EdgeTts("v", connector) { }.synthesize(sentences, File(dir, "b.mp3"))
            fail("đáng ra lỗi")
        } catch (error: VoiceException) {
            assertFalse(error.offline)
            assertEquals(EdgeTts.NOT_ANSWERING, error.message)
        }
    }

    @Test
    fun aRefusedPieceIsReportedAsRejected() {
        val calls = AtomicInteger(0)
        val connector = EdgeTts.Connector { _, _ ->
            if (calls.incrementAndGet() == 2) throw HandshakeException(403, emptyMap())
            val sent = ByteArrayOutputStream()
            WebSocket({ }, Reply(sent) { audio(600, 1) + text("turn.end") }, sent)
        }
        try {
            EdgeTts("v", connector) { }.synthesize(sentences, File(dir, "c.mp3"))
            fail("đáng ra lỗi")
        } catch (error: VoiceException) {
            assertEquals("rejected", error.reason)
        }
    }

    @Test
    fun theProcessWideCapLimitsOpenConnections() {
        EdgeTts.connections = Semaphore(2)
        val live = AtomicInteger(0)
        val peak = AtomicInteger(0)
        val voices = List(2) { EdgeTts("v", connectorBySpokenWords(live, peak)) }
        val clips = voices.mapIndexed { i, voice -> Thread { voice.synthesize(sentences, File(dir, "cap$i.mp3")) }.also { it.start() } }
        clips.forEach { it.join(20_000) }
        assertEquals(0, live.get())
        assertEquals(2, peak.get()) // trần 2 giữ được, và có song song thật
    }

    @Test
    fun anOfflineFirstAttemptStillFallsThroughImmediately() {
        val calls = AtomicInteger(0)
        val connector = EdgeTts.Connector { _, _ ->
            calls.incrementAndGet()
            throw java.net.UnknownHostException("speech.platform.bing.com")
        }
        try {
            EdgeTts("v", connector) { fail("không được nghỉ chờ") }.synthesize(sentences, File(dir, "d.mp3"))
            fail("đáng ra lỗi")
        } catch (error: VoiceException) {
            assertTrue(error.offline)
            assertEquals("Không có mạng để dùng giọng Edge", error.message)
        }
    }
}
