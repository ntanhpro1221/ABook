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
import java.util.concurrent.CancellationException
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference
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
        EdgeTts.clockSkewSeconds = 0.0
        EdgeTts.totalMs = EdgeTts.TOTAL_MS
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

    // ---- huỷ, hạn chung, độ lệch đồng hồ (a50) ---------------------------------------------------------------------------------

    /** Chờ tới khi `condition` đúng (tối đa 5 giây) - bài thử đa luồng không đoán giờ. */
    private fun waitUntil(what: String, condition: () -> Boolean) {
        val end = System.nanoTime() + 5_000_000_000L
        while (!condition()) {
            assertTrue("hết 5 giây mà chưa $what", System.nanoTime() < end)
            Thread.sleep(10)
        }
    }

    private val threePieces = (1..9).joinToString(" ") { "Câu số $it kể về một chuyện nhỏ trong ngôi làng ven sông." }

    private fun httpDate(seconds: Double): String =
        java.text.SimpleDateFormat("EEE, dd MMM yyyy HH:mm:ss 'GMT'", java.util.Locale.US).apply { timeZone = java.util.TimeZone.getTimeZone("UTC") }.format(java.util.Date((seconds * 1000).toLong()))

    @Test
    fun piecesRefusedTogetherLearnTheClockSkewOnceAndNoneIsRejected() {
        // Cả ba mảnh cùng bị 403 vì đồng hồ máy chậm 1 giờ: độ lệch GÁN (server - bây giờ) nên mảnh nào cũng nối được ở lần thử lại; bản cộng dồn (+=) nhân nó lên 2-3 lần.
        assertEquals(3, EdgePieces.split(threePieces).size)
        val ahead = 3600.0
        val everyoneRefused = CountDownLatch(3)
        val accepted = AtomicInteger(0)
        val refusals = AtomicInteger(0)
        val connector = EdgeTts.Connector { url, _ ->
            val server = System.currentTimeMillis() / 1000.0 + ahead
            val onServerTime = listOf(-300.0, 0.0, 300.0).any { url.contains("Sec-MS-GEC=" + EdgeProtocol.secMsGec(server + it)) }
            if (!onServerTime) {
                everyoneRefused.countDown()
                everyoneRefused.await(5, TimeUnit.SECONDS) // cả ba cùng tính giờ bằng độ lệch cũ rồi mới nhận 403...
                if (refusals.incrementAndGet() > 1) Thread.sleep(300) // ...mảnh đầu học độ lệch và nối lại xong TRƯỚC khi hai mảnh kia nhận 403 (cộng dồn thì chúng cộng chồng lên)
                throw HandshakeException(403, mapOf("date" to httpDate(server)))
            }
            accepted.incrementAndGet()
            val sent = ByteArrayOutputStream()
            WebSocket({ }, Reply(sent) { audio(600, 1) + text("turn.end") }, sent)
        }
        val clip = EdgeTts("v", connector) { }.synthesize(threePieces, File(dir, "skew.mp3"))
        assertEquals(3, accepted.get())
        assertEquals(3 * 600 * 1000L / 6000, clip.durationMs)
        assertEquals(ahead, EdgeTts.clockSkewSeconds, 5.0)
    }

    @Test
    fun cancellingAClipClosesTheSocketsOfItsRunningPiecesAndDoesNotRetry() {
        val expected = EdgePieces.split(sentences).size
        assertTrue(expected >= 2)
        val opened = AtomicInteger(0)
        val closed = AtomicInteger(0)
        val connector = EdgeTts.Connector { _, _ ->
            opened.incrementAndGet()
            val gate = CountDownLatch(1)
            val silent = object : InputStream() { // không bao giờ trả lời: đọc chờ tới khi ổ cắm bị đóng, rồi văng lỗi như ổ cắm thật
                override fun read(): Int {
                    gate.await(10, TimeUnit.SECONDS)
                    throw java.net.SocketException("Socket closed")
                }
            }
            WebSocket({ closed.incrementAndGet(); gate.countDown() }, silent, ByteArrayOutputStream())
        }
        val cancel = ClipCancel()
        val result = AtomicReference<Result<Clip>>()
        val reader = Thread { result.set(ClipRetry.run(true, longArrayOf(1_000L), { true }, cancel = cancel) { EdgeTts("v", connector) { }.synthesize(sentences, File(dir, "x.mp3")) }) }
        reader.start()
        waitUntil("mọi mảnh đã nối") { opened.get() == expected }
        assertEquals("đang chờ trả lời nên chưa ổ cắm nào đóng", 0, closed.get())
        cancel.cancel()
        reader.join(5_000)
        assertFalse("luồng đọc phải thoát ngay khi huỷ", reader.isAlive)
        assertTrue(result.get().exceptionOrNull() is CancellationException)
        waitUntil("mọi ổ cắm đã đóng") { closed.get() == expected }
        assertEquals("huỷ thì không thử lại, không nối thêm", expected, opened.get())
        waitUntil("chỗ kết nối nhả hết") { EdgeTts.connections.availablePermits() == EdgePieces.EDGE_CONNECTIONS }
    }

    @Test
    fun aFailingPieceFailsTheClipAtOnceAndClosesTheSocketsOfTheOthers() {
        // Mảnh đầu (đứng trước) im lìm; mảnh khác nhận tin hỏng ngay: cả clip hỏng ngay (không đợi mảnh đầu), và ổ cắm mảnh đầu đóng - không giữ chỗ tới hết lượt.
        val total = EdgePieces.split(sentences).size
        val closed = AtomicInteger(0)
        val connector = EdgeTts.Connector { _, _ ->
            val sent = ByteArrayOutputStream()
            val gate = CountDownLatch(1)
            WebSocket({ closed.incrementAndGet(); gate.countDown() }, Reply(sent) { bytes ->
                if (spokenIn(bytes).startsWith("Trời")) {
                    gate.await(10, TimeUnit.SECONDS)
                    throw java.net.SocketException("Socket closed")
                }
                frame(WebSocket.OP_BINARY, byteArrayOf(0, 99, 1)) // độ dài header vượt tin: hỏng
            }, sent)
        }
        val began = System.nanoTime()
        try {
            EdgeTts("v", connector) { }.synthesize(sentences, File(dir, "ff.mp3"))
            fail("đáng ra lỗi")
        } catch (error: VoiceException) {
            assertTrue(error.message, error.message!!.contains("tin hỏng"))
        }
        assertTrue("không được đợi mảnh đứng trước", (System.nanoTime() - began) < 5_000_000_000L)
        waitUntil("mọi ổ cắm đã đóng") { closed.get() == total }
        waitUntil("chỗ kết nối nhả hết") { EdgeTts.connections.availablePermits() == EdgePieces.EDGE_CONNECTIONS }
    }
}
