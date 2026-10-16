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
import java.util.concurrent.atomic.AtomicInteger

/**
 * Đọc song song các câu của một đoạn (uxfix47): luật cắt mảnh trên bộ ví dụ DÙNG CHUNG với pytest (tests/fixtures/readaloud/edge/pieces.json), mốc chữ sau khi nối, trần
 * kết nối, lỗi một mảnh - mọi thứ trên máy chủ giả, không mạng.
 */
class EdgePiecesTest {
    private val dir = java.nio.file.Files.createTempDirectory("edge-pieces").toFile()
    private val sentences = "Trời đã sẩm tối khi đoàn người tới được cổng làng. Người gác cổng đứng chờ sẵn, tay cầm chiếc đèn dầu cũ. " +
        "Họ im lặng bước vào sân, nơi mấy con chó nằm ngủ dưới hiên. Mưa bắt đầu rơi lúc nào không ai hay."

    private val twelveSentences = "Con đường mòn dẫn xuống thung lũng phủ đầy sương sớm. Mấy chú bò già chậm rãi nhai cỏ ven bờ suối. Bà lão gánh hai thúng khoai đi ngang qua cầu tre. " +
        "Đứa bé chạy theo sau, tay cầm cành hoa dại vừa hái. Tiếng chuông chùa vọng lại từ phía bên kia ngọn đồi. Khói bếp bắt đầu bay lên từ những mái nhà thấp. " +
        "Người thợ rèn mở cửa lò, ngọn lửa hắt sáng cả con ngõ. Lũ gà con chíp chíp quanh chiếc sọt đan dở. Ông trưởng thôn ngồi hút thuốc lào trước hiên nhà. " +
        "Một cơn gió nhẹ thổi qua, cuốn theo mùi rơm mới phơi. Cả làng chầm chậm thức dậy sau một đêm dài yên ắng. Ngày mới bắt đầu như bao ngày khác."

    @After
    fun cleanUp() {
        EdgeTts.connections = ConnectionSlots(EdgePieces.EDGE_CONNECTIONS)
        EdgeTts.clockSkewSeconds = 0.0
        EdgeTts.totalMs = EdgeTts.TOTAL_MS
        dir.deleteRecursively()
    }

    @Test
    fun theSharedCasesCutTheSameWayAsPython() {
        val file = File("../../../tests/fixtures/readaloud/edge/pieces.json")
        assertTrue("Không thấy ${file.absoluteFile}", file.isFile)
        val cases = JSONObject(file.readText(Charsets.UTF_8)).getJSONArray("cases")
        assertTrue(cases.length() >= 20)
        for (i in 0 until cases.length()) {
            val case = cases.getJSONObject(i)
            val expected = case.getJSONArray("pieces").let { array -> List(array.length()) { array.getString(it) } }
            assertEquals(case.getString("note"), expected, EdgePieces.split(case.getString("text"), case.optInt("rank", EdgePieces.RANK_BACKGROUND)))
        }
    }

    @Test
    fun onlyTheParagraphBeingWaitedForIsCutIntoUpToSixPieces() {
        assertEquals(3, EdgePieces.PIECE_PARALLEL)
        assertEquals(6, EdgePieces.TARGET_PIECES)
        assertEquals(listOf(6, 3, 3, 3, 3), listOf(0, 1, 2, 98, EdgePieces.RANK_BACKGROUND).map { EdgePieces.pieceLimit(it) })
        val text = twelveSentences
        assertEquals(6, EdgePieces.split(text, 0).size)
        for (rank in listOf(1, 5, 98, EdgePieces.RANK_BACKGROUND)) assertEquals(3, EdgePieces.split(text, rank).size)
        assertEquals(EdgePieces.split(text, EdgePieces.RANK_BACKGROUND), EdgePieces.split(text))
        for (rank in listOf(0, 1)) {
            val pieces = EdgePieces.split(text, rank)
            assertEquals(text.split(" "), pieces.joinToString(" ").split(" "))
            assertTrue(pieces.all { it.length >= EdgePieces.MIN_PIECE_CHARS })
        }
    }

    @Test
    fun aRankZeroClipRunsSixPiecesAtOnceAndOtherRanksThree() {
        for ((rank, expected) in listOf(0 to 6, 1 to 3, EdgePieces.RANK_BACKGROUND to 3)) {
            val live = AtomicInteger(0)
            val peak = AtomicInteger(0)
            val sent = AtomicInteger(0)
            val connector = EdgeTts.Connector { _, _ ->
                val out = ByteArrayOutputStream()
                sent.incrementAndGet()
                peak.accumulateAndGet(live.incrementAndGet(), { a, b -> maxOf(a, b) })
                WebSocket({ live.decrementAndGet() }, Reply(out) { bytes ->
                    Thread.sleep(250) // mỗi mảnh giữ chỗ đủ lâu để các mảnh khác kịp mở cùng lúc
                    val words = spokenIn(bytes).split(" ")
                    var reply = ByteArray(0)
                    words.forEachIndexed { i, word -> reply += metadata(i * 1_000_000L, 800_000, word) }
                    reply + audio(words.size * 600, 1) + text("turn.end")
                }, out)
            }
            val before = ClipBudget.enterRank(rank)
            try {
                EdgeTts("v", connector).synthesize(twelveSentences, File(dir, "rank$rank.mp3"))
            } finally {
                ClipBudget.leaveRank(before)
            }
            assertEquals("rank $rank", expected to expected, sent.get() to peak.get())
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

    // uxfix55: đoạn người nghe đứng chờ cắt cân bằng (máy tính: test_readaloud_edge_pieces.py, cùng chữ).
    private val balS = "Ông lái đò ngồi bên bếp lửa nhỏ, hút điếu thuốc lào đã cháy gần hết, nhìn dòng sông đen chảy qua bến cũ, và nghĩ về những chuyến đò đêm đã qua mà chẳng ai nhớ."
    private val balM = "Người gác cổng đứng chờ sẵn trước hiên, tay cầm chiếc đèn dầu cũ, mắt nhìn xa xăm về phía con đường mòn dẫn ra đồng, nơi ánh trăng đã tắt từ lâu lắm rồi."
    private val balQ = "Mưa bắt đầu rơi lúc nào không ai hay biết."
    private val balLong = "Họ đi mãi, đi mãi qua những cánh đồng lúa chín vàng, qua những con suối nhỏ trong veo chảy róc rách bên đường, qua cả những xóm làng xơ xác sau mùa lũ lớn, " +
        "mà vẫn không tìm thấy bóng dáng của người dẫn đường, và càng đi họ càng thấy đường dài thêm ra, núi cao thêm lên, sương dày thêm xuống, cho tới lúc trời tối hẳn."

    @Test
    fun theLongestPieceStaysNearTheBalancedSize() {
        val texts = listOf(
            listOf(balS, balM, balS, balQ), listOf(balQ, balM, balLong), listOf(balLong, balQ, balM), listOf(balM, balLong, balQ, balQ),
            listOf(balS, balLong, balM, balQ), listOf(balS, balM, balS, balM, balS),
        ).map { it.joinToString(" ") }
        for (text in texts) for (rank in listOf(0, EdgePieces.RANK_BACKGROUND)) {
            val limit = EdgePieces.pieceLimit(rank)
            val pieces = EdgePieces.speechPieces(text, rank)
            assertTrue(pieces.size in 2..limit)
            assertEquals(text.split(" "), pieces.joinToString(" ").split(" "))
            assertTrue(pieces.all { it.length >= EdgePieces.MIN_PIECE_CHARS })
            assertTrue("${pieces.map { it.length }}", pieces.maxOf { it.length } <= 1.4 * text.length / limit)
        }
    }

    @Test
    fun aSentenceUnderTwoHundredCharsIsCutWhenLongerThanABalancedPiece() {
        val text = listOf(balS, balM, balS, balM).joinToString(" ")
        assertTrue(EdgePieces.splitSentences(text).all { it.length <= EdgePieces.LONG_SENTENCE_CHARS })
        assertTrue(EdgePieces.clauseThreshold(text.length, EdgePieces.TARGET_PIECES) < EdgePieces.LONG_SENTENCE_CHARS)
        val pieces = EdgePieces.speechPieces(text, 0)
        assertEquals(EdgePieces.TARGET_PIECES, pieces.size)
        assertTrue(pieces.maxOf { it.length } < 125)
        assertEquals(EdgePieces.LONG_SENTENCE_CHARS, EdgePieces.clauseThreshold(text.length, EdgePieces.PIECE_PARALLEL))
    }

    @Test
    fun theClauseThresholdIsBoundedByTheOldLimitAndTheMinimumPiece() {
        assertEquals(EdgePieces.LONG_SENTENCE_CHARS, EdgePieces.clauseThreshold(10_000, 3))
        assertEquals(EdgePieces.MIN_PIECE_CHARS, EdgePieces.clauseThreshold(100, 6))
        assertEquals(130, EdgePieces.clauseThreshold(600, 6))
        assertEquals(136, EdgePieces.clauseThreshold(313, 3))
    }

    @Test
    fun aClauseCutKeepsTheShortJoinTailAndShortClausesDoNotMergeIntoOnePiece() {
        val pieces = EdgePieces.speechPieces(balLong, 0)
        assertTrue(pieces.size > 1)
        assertEquals(EdgeJoin.TAIL_OTHER_MS, EdgeJoin.tailMs(pieces.first()))
        assertEquals(EdgeJoin.TAIL_SENTENCE_MS, EdgeJoin.tailMs(pieces.last()))
        val text = "Con thuyền cập bến lúc nửa đêm, trên boong chỉ còn mình người lái đò thức. Ông ngồi hút thuốc lào và nhìn dòng sông đen, chờ trời sáng để đón khách đầu tiên."
        assertEquals(2, EdgePieces.speechPieces(text).size)
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
        EdgeTts.connections = ConnectionSlots(2)
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

    // ---- đoạn gần người nghe hơn đi trước khi hết chỗ kết nối (uxfix51) -------------------------------------------------------------

    @Test
    fun connectionSlotsGrantTheNearestToTheListenerFirstAndKeepArrivalOrderAmongEquals() {
        val slots = ConnectionSlots(1)
        slots.acquire()
        val granted = java.util.Collections.synchronizedList(ArrayList<String>())
        val threads = ArrayList<Thread>()
        val specs = listOf("bg" to EdgePieces.RANK_BACKGROUND, "ahead3" to 3, "ahead1" to 1, "target" to 0, "ahead2" to 2, "ahead1b" to 1)
        for ((name, rank) in specs) {
            val before = slots.waiting()
            threads += Thread { if (slots.tryAcquire(5_000, rank)) granted.add(name) }.also { it.start() }
            waitUntil("$name đã xếp hàng") { slots.waiting() == before + 1 }
        }
        repeat(specs.size) { n ->
            slots.release()
            waitUntil("chỗ thứ $n đã trao") { granted.size == n + 1 }
        }
        threads.forEach { it.join(2_000) }
        assertEquals(listOf("target", "ahead1", "ahead1b", "ahead2", "ahead3", "bg"), granted)
    }

    @Test
    fun aWaiterThatTimesOutLeavesTheQueueAndTheWayFree() {
        val slots = ConnectionSlots(1)
        slots.acquire()
        assertFalse(slots.tryAcquire(50))
        assertEquals(0, slots.waiting())
        slots.release()
        assertEquals(1, slots.availablePermits())
        try {
            slots.release()
            fail("trả quá số đã giữ phải lỗi")
        } catch (expected: IllegalStateException) {
        }
    }

    @Test
    fun theProductionSlotsLetOnlyRankZeroPastTheEightConnectionCap() {
        assertEquals(EdgePieces.EDGE_CONNECTIONS, EdgeTts.productionSlots().size)
        assertEquals(EdgePieces.TARGET_PIECES, EdgeTts.productionSlots().extra)
    }

    @Test
    fun rankZeroTakesASlotAtOnceWhenEightAreHeldByRankThreeAndTheCeilingHolds() {
        val slots = ConnectionSlots(EdgePieces.EDGE_CONNECTIONS, EdgePieces.TARGET_PIECES)
        repeat(EdgePieces.EDGE_CONNECTIONS) { assertTrue(slots.tryAcquire(100, 3)) }
        assertFalse(slots.tryAcquire(50, 1)) // rank >= 1 không được vượt trần
        assertFalse(slots.tryAcquire(50))
        repeat(EdgePieces.TARGET_PIECES) {
            val began = System.nanoTime()
            assertTrue(slots.tryAcquire(5_000, 0))
            assertTrue("rank 0 không được đợi", (System.nanoTime() - began) < 200_000_000L)
        }
        assertEquals(-EdgePieces.TARGET_PIECES, slots.availablePermits())
        val began = System.nanoTime()
        assertFalse(slots.tryAcquire(100, 0)) // trần cứng size + TARGET_PIECES
        assertTrue((System.nanoTime() - began) >= 90_000_000L)
        assertEquals(0, slots.waiting())
    }

    @Test
    fun twoRankZeroClipsShareTheCeilingAndThePiecesPastItWaitInArrivalOrder() {
        // uxfix54: đoạn ngắn đứng trước không tính vào rank -> tiêu đề + đoạn 1 cùng rank 0, nay có thể cùng lúc 6 + 6 mảnh. Trần cứng vẫn size + extra.
        val slots = ConnectionSlots(EdgePieces.EDGE_CONNECTIONS, EdgePieces.TARGET_PIECES)
        repeat(EdgePieces.EDGE_CONNECTIONS) { assertTrue(slots.tryAcquire(100, 3)) }
        repeat(EdgePieces.TARGET_PIECES) { assertTrue(slots.tryAcquire(5_000, 0)) } // clip rank 0 thứ nhất: 6 mảnh, vượt trần 8
        assertEquals(-EdgePieces.TARGET_PIECES, slots.availablePermits())
        val granted = java.util.Collections.synchronizedList(ArrayList<String>())
        val threads = ArrayList<Thread>()
        for ((name, rank) in listOf("b1" to 0, "b2" to 0, "b3" to 0, "sibling" to 1)) { // clip rank 0 thứ hai (mảnh 1-3 của 6) + một clip rank 1
            val before = slots.waiting()
            threads += Thread { if (slots.tryAcquire(5_000, rank)) granted.add(name) }.also { it.start() }
            waitUntil("$name đã xếp hàng") { slots.waiting() == before + 1 }
        }
        repeat(3) { n -> // mỗi chỗ nhả ra, mảnh rank 0 kế trong hàng lấy ngay (vẫn ở trần size + extra), theo thứ tự đến
            slots.release()
            waitUntil("chỗ thứ $n đã trao") { granted.size == n + 1 }
        }
        assertEquals(listOf("b1", "b2", "b3"), granted.toList())
        assertEquals(-EdgePieces.TARGET_PIECES, slots.availablePermits())
        repeat(EdgePieces.TARGET_PIECES) { slots.release() } // giữ lại 8: clip rank 1 vẫn chưa được chỗ (cần xuống dưới size)
        Thread.sleep(100)
        assertEquals(listOf("b1", "b2", "b3"), granted.toList())
        assertEquals(0, slots.availablePermits())
        slots.release()
        waitUntil("clip rank 1 đã được chỗ") { granted.size == 4 }
        threads.forEach { it.join(2_000) }
        assertEquals(listOf("b1", "b2", "b3", "sibling"), granted.toList()) // rank 0 trước theo thứ tự đến, rồi rank 1
    }

    @Test
    fun overCapReleasesNeverLetFreeExceedSizeAndTheWaitersKeepTheirOrder() {
        val slots = ConnectionSlots(2, 2)
        assertTrue(slots.tryAcquire(100, 3))
        assertTrue(slots.tryAcquire(100, 3))
        assertTrue(slots.tryAcquire(100, 0))
        assertTrue(slots.tryAcquire(100, 0)) // hai chỗ vượt trần
        val granted = java.util.Collections.synchronizedList(ArrayList<String>())
        val threads = ArrayList<Thread>()
        for ((name, rank) in listOf("bg" to EdgePieces.RANK_BACKGROUND, "ahead2" to 2, "ahead1" to 1)) {
            val before = slots.waiting()
            threads += Thread { if (slots.tryAcquire(5_000, rank)) granted.add(name) }.also { it.start() }
            waitUntil("$name đã xếp hàng") { slots.waiting() == before + 1 }
        }
        slots.release() // đang giữ 3 / size 2: chưa ai trong hàng được chỗ
        slots.release() // đang giữ 2: vẫn chưa (free == 0)
        Thread.sleep(100)
        assertTrue(granted.isEmpty())
        assertEquals(0, slots.availablePermits())
        repeat(3) { n ->
            slots.release()
            waitUntil("chỗ thứ $n đã trao") { granted.size == n + 1 }
            assertTrue(slots.availablePermits() <= slots.size)
        }
        threads.forEach { it.join(2_000) }
        assertEquals(listOf("ahead1", "ahead2", "bg"), granted.toList())
        while (slots.availablePermits() < slots.size) slots.release()
        assertEquals(slots.size, slots.availablePermits())
        try {
            slots.release()
            fail("trả quá số đã giữ phải lỗi")
        } catch (expected: IllegalStateException) {
        }
    }

    @Test
    fun theClipTheListenerWaitsForAskedAfterReadAheadClipsWaitGetsTheNextFreeSlot() {
        // Một chỗ duy nhất đang bận; hai clip đọc trước (rank 2, 1) xếp hàng trước, clip người nghe chờ (rank 0) xin SAU CÙNG - chỗ nhả ra là của nó.
        val slots = ConnectionSlots(1)
        EdgeTts.connections = slots
        slots.acquire()
        val order = java.util.Collections.synchronizedList(ArrayList<String>())
        val connector = EdgeTts.Connector { _, _ ->
            val sent = ByteArrayOutputStream()
            WebSocket({ }, Reply(sent) { bytes ->
                order.add(spokenIn(bytes))
                audio(600, 1) + text("turn.end")
            }, sent)
        }
        val threads = ArrayList<Thread>()
        for ((text, rank) in listOf("Đọc trước hai." to 2, "Đọc trước một." to 1, "Người nghe chờ." to 0)) {
            val before = slots.waiting()
            threads += Thread { ClipRetry.run(true, longArrayOf(), { true }, rank = rank) { EdgeTts("v", connector) { }.synthesize(text, File(dir, "u$rank.mp3")) } }.also { it.start() }
            waitUntil("$text đã xếp hàng") { slots.waiting() == before + 1 }
        }
        slots.release()
        threads.forEach { it.join(10_000) }
        assertEquals(listOf("Người nghe chờ.", "Đọc trước một.", "Đọc trước hai."), order.toList())
    }

    @Test
    fun theRankReachesEveryPieceThreadOfAClipButOnlyInsideTheRun() {
        assertEquals(EdgePieces.RANK_BACKGROUND, ClipBudget.rank())
        val seen = java.util.Collections.synchronizedList(ArrayList<Int>())
        val connector = EdgeTts.Connector { _, _ ->
            seen.add(ClipBudget.rank()) // chạy ở luồng của mảnh
            val sent = ByteArrayOutputStream()
            WebSocket({ }, Reply(sent) { audio(600, 1) + text("turn.end") }, sent)
        }
        ClipRetry.run(true, longArrayOf(), { true }, rank = 2) {
            assertEquals(2, ClipBudget.rank())
            EdgeTts("v", connector) { }.synthesize(sentences, File(dir, "r.mp3"))
        }
        assertEquals(EdgePieces.RANK_BACKGROUND, ClipBudget.rank())
        assertTrue("nhiều mảnh", seen.size >= 2)
        assertTrue("mọi mảnh nhận rank của clip: $seen", seen.all { it == 2 })
        ClipRetry.run(true, longArrayOf(), { true }) { assertEquals(EdgePieces.RANK_BACKGROUND, ClipBudget.rank()); Clip(File("x"), 1, emptyList(), "v") }
    }

    // ---- chỗ nối giữa các mảnh (uxfix50) -----------------------------------------------------------------------------------------

    /** `count` khung mp3 hợp lệ (MPEG-2 lớp III, 48 kbps, 24 kHz, đơn kênh, 144 byte); byte 4-5 ghi số thứ tự khung. */
    private fun mp3Frames(count: Int): ByteArray {
        val out = ByteArrayOutputStream()
        for (index in 0 until count) {
            val frame = ByteArray(EdgeJoin.FRAME_BYTES)
            frame[0] = 0xFF.toByte(); frame[1] = 0xF3.toByte(); frame[2] = 0x64; frame[3] = 0xC0.toByte()
            frame[4] = (index ushr 8).toByte(); frame[5] = index.toByte()
            out.write(frame)
        }
        return out.toByteArray()
    }

    private fun audioOf(data: ByteArray): ByteArray {
        val header = "X-RequestId:r\r\nContent-Type:audio/mpeg\r\nPath:audio\r\n".toByteArray()
        return frame(WebSocket.OP_BINARY, byteArrayOf((header.size ushr 8).toByte(), header.size.toByte()) + header + data)
    }

    @Test
    fun theJoinTailCutFollowsTheSharedCases() {
        val file = File("../../../tests/fixtures/readaloud/edge/join_tail.json")
        assertTrue("Không thấy ${file.absoluteFile}", file.isFile)
        val cases = JSONObject(file.readText(Charsets.UTF_8)).getJSONArray("cases")
        assertTrue(cases.length() >= 6)
        for (i in 0 until cases.length()) {
            val case = cases.getJSONObject(i)
            val audio = mp3Frames(case.getInt("frames"))
            val trimmed = EdgeJoin.trim(audio, case.getString("piece"), case.getLong("last_end_ms"))
            assertEquals(case.getString("note"), case.getInt("kept_frames") * EdgeJoin.FRAME_BYTES, trimmed.size)
            assertTrue(case.getString("note"), trimmed.contentEquals(audio.copyOf(trimmed.size))) // chỉ cắt đuôi
        }
    }

    @Test
    fun theJoinTailIsLeftAloneWhenTheFramesAreNotWhatEdgeSends() {
        val audio = mp3Frames(300)
        assertTrue(EdgeJoin.trim(audio, "Xong rồi.", 2000).size < audio.size) // đối chứng: dữ liệu tốt thì cắt
        assertTrue(EdgeJoin.trim(audio, "Xong rồi.", null).contentEquals(audio)) // không có mốc
        assertEquals(0, EdgeJoin.trim(ByteArray(0), "Xong rồi.", 2000).size)
        val odd = audio + byteArrayOf(0)
        assertTrue(EdgeJoin.trim(odd, "Xong rồi.", 2000).contentEquals(odd)) // không chia hết cho khung
        val padded = audio.copyOf().also { it[144 * 200 + 2] = (it[144 * 200 + 2].toInt() or 0x02).toByte() } // khung có bit đệm
        assertTrue(EdgeJoin.trim(padded, "Xong rồi.", 2000).contentEquals(padded))
        val otherRate = audio.copyOf().also { it[144 * 10 + 2] = 0x68 }
        assertTrue(EdgeJoin.trim(otherRate, "Xong rồi.", 2000).contentEquals(otherRate))
        val noise = ByteArray(144 * 20) { (it % 251).toByte() }
        assertTrue(EdgeJoin.trim(noise, "Xong rồi.", 2000).contentEquals(noise))
    }

    @Test
    fun aSentenceEndKeepsEdgesOwnSentencePauseAndOtherCutsKeepLess() {
        assertEquals(EdgeJoin.TAIL_SENTENCE_MS, EdgeJoin.tailMs("Hết câu."))
        assertEquals(EdgeJoin.TAIL_SENTENCE_MS, EdgeJoin.tailMs("Hết câu?”"))
        assertEquals(EdgeJoin.TAIL_SENTENCE_MS, EdgeJoin.tailMs("Hết câu…"))
        assertEquals(EdgeJoin.TAIL_OTHER_MS, EdgeJoin.tailMs("Còn tiếp,"))
        assertEquals(EdgeJoin.TAIL_OTHER_MS, EdgeJoin.tailMs("“Còn tiếp,”"))
        assertEquals(EdgeJoin.TAIL_OTHER_MS, EdgeJoin.tailMs("một hai ba"))
    }

    @Test
    fun synthesizeTrimsEveryPieceButTheLastAndShiftsLaterWordsByTheTrimmedLength() {
        val pieces = EdgePieces.split(sentences)
        assertTrue(pieces.size >= 3)
        // Mảnh có `w` chữ: mốc chữ cuối kết thúc ở (w - 1) x 100 + 80 ms theo dịch vụ, audio dài 200 khung (4,8 giây) như Edge thật (dư đuôi lặng).
        val frames = 200
        val connector = EdgeTts.Connector { _, _ ->
            val sent = ByteArrayOutputStream()
            WebSocket({ }, Reply(sent) { bytes ->
                val words = spokenIn(bytes).split(" ")
                var reply = ByteArray(0)
                words.forEachIndexed { i, word -> reply += metadata(i * 1_000_000L, 800_000, word) }
                reply + audioOf(mp3Frames(frames)) + text("turn.end")
            }, sent)
        }
        val out = File(dir, "join.mp3")
        val clip = EdgeTts("v", connector).synthesize(sentences, out)
        val kept = pieces.mapIndexed { n, piece ->
            if (n == pieces.size - 1) frames
            else ((piece.split(" ").size - 1) * 100L + 80 + EdgeJoin.tailMs(piece) + EdgeJoin.FRAME_MS - 1).div(EdgeJoin.FRAME_MS).toInt()
        }
        pieces.dropLast(1).forEachIndexed { n, _ -> assertTrue("mảnh $n phải bị cắt", kept[n] < frames) }
        assertEquals(kept.sum() * EdgeJoin.FRAME_BYTES, out.length().toInt())
        assertEquals(kept.sum() * EdgeJoin.FRAME_MS.toLong(), clip.durationMs)
        var firstWord = 0
        var before = 0L
        pieces.forEachIndexed { n, piece ->
            assertEquals(before + EdgeProtocol.BOUNDARY_SHIFT_MS, clip.words[firstWord].start)
            before += kept[n] * EdgeJoin.FRAME_MS.toLong()
            firstWord += piece.split(" ").size
        }
    }

    // ---- bắt tay treo (uxfix50) ------------------------------------------------------------------------------------------------

    private fun okSession(): WebSocket {
        val sent = ByteArrayOutputStream()
        return WebSocket({ }, Reply(sent) { audio(600, 1) + text("turn.end") }, sent)
    }

    @Test
    fun aHandshakeThatTimesOutOnceIsRetriedAndTheClipSucceeds() {
        val calls = AtomicInteger(0)
        val connector = EdgeTts.Connector { _, _ ->
            if (calls.incrementAndGet() == 1) throw java.net.SocketTimeoutException("connect timed out")
            okSession()
        }
        val clip = EdgeTts("v", connector) { }.synthesize("Xin chào", File(dir, "t1.mp3"))
        assertEquals(2, calls.get())
        assertEquals(100L, clip.durationMs)
    }

    @Test
    fun oneHangingPieceDoesNotFailTheClip() {
        val calls = AtomicInteger(0)
        val pieces = EdgePieces.split(sentences)
        val connector = EdgeTts.Connector { _, _ ->
            if (calls.incrementAndGet() == 2) throw java.net.SocketTimeoutException("connect timed out")
            okSession()
        }
        val clip = EdgeTts("v", connector) { }.synthesize(sentences, File(dir, "t2.mp3"))
        assertEquals(pieces.size + 1, calls.get())
        assertEquals(pieces.size * 100L, clip.durationMs)
    }

    @Test
    fun aHandshakeThatAlwaysTimesOutEndsAsLostNetworkAfterTheRetries() {
        val calls = AtomicInteger(0)
        val connector = EdgeTts.Connector { _, _ ->
            calls.incrementAndGet()
            throw java.net.SocketTimeoutException("connect timed out")
        }
        try {
            EdgeTts("v", connector) { }.synthesize("Xin chào", File(dir, "t3.mp3"))
            fail("đáng ra lỗi")
        } catch (error: VoiceException) {
            assertTrue(error.offline)
            assertEquals(EdgeTts.LOST_NETWORK, error.message)
            assertEquals(EdgeTts.RETRIES + 1, calls.get())
        }
    }

    @Test
    fun theConnectTimeoutIsAFewTimesTheMeasuredHandshakeNotEightSeconds() {
        assertTrue(EdgeTts.CONNECT_MS in 3_000..6_000)
    }
}
