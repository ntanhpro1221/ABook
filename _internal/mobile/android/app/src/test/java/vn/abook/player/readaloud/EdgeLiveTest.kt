package vn.abook.player.readaloud

import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test
import vn.abook.player.readaloud.EdgeFake.Answer
import vn.abook.player.readaloud.EdgeFake.audioOf
import vn.abook.player.readaloud.EdgeFake.metadata
import vn.abook.player.readaloud.EdgeFake.mp3Frames
import vn.abook.player.readaloud.EdgeFake.text
import java.io.ByteArrayOutputStream
import java.io.File
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.CopyOnWriteArrayList
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger
import java.util.concurrent.atomic.AtomicReference

/**
 * Clip Edge phát luồng (uxfix57; máy tính: `edge.py` bộ phát theo thứ tự): file ghi dần và mốc báo dần phải GIỐNG HỆT file / mốc của đường thường trên cùng máy chủ giả; byte đầu ra ngay khi mảnh đứng
 * đầu nhận được (không đợi hết lượt); mảnh sau chờ tới lượt; mảnh đầu hỏng giữa chừng thì lần thử lại phải ra đúng phần đã phát.
 */
class EdgeLiveTest {
    private val dir = java.nio.file.Files.createTempDirectory("edge-live").toFile()
    private val sentences = "Trời đã sẩm tối khi đoàn người tới được cổng làng. Người gác cổng đứng chờ sẵn, tay cầm chiếc đèn dầu cũ. " +
        "Họ im lặng bước vào sân, nơi mấy con chó nằm ngủ dưới hiên. Mưa bắt đầu rơi lúc nào không ai hay."

    @After
    fun cleanUp() {
        EdgeTts.connections = ConnectionSlots(EdgePieces.EDGE_CONNECTIONS)
        EdgeTts.clockSkewSeconds = 0.0
        EdgeTts.totalMs = EdgeTts.TOTAL_MS
        dir.deleteRecursively()
    }

    /** Ghi lại mọi điều [EdgeTts.synthesize] báo; mỗi lần file lớn thêm chụp luôn phần đầu file lúc ấy. */
    private class Recorder(val onGrew: (Long) -> Unit = {}) : LiveSink {
        val totals = CopyOnWriteArrayList<Long>()
        val snapshots = CopyOnWriteArrayList<ByteArray>()
        val boundaries = CopyOnWriteArrayList<Boundary>()
        @Volatile var done: Clip? = null
        @Volatile var failure: Exception? = null
        val cuts = CopyOnWriteArrayList<Int>()
        /** Số byte đã ghi lúc nhận [cut]. */
        @Volatile var bytesAtCut = -1L

        override fun grew(file: File, totalBytes: Long) {
            totals += totalBytes
            snapshots += file.readBytes().copyOf(totalBytes.toInt())
            onGrew(totalBytes)
        }

        override fun boundaries(found: List<Boundary>) {
            boundaries += found
        }

        override fun done(clip: Clip) {
            done = clip
        }

        override fun failed(error: Exception) {
            failure = error
        }

        override fun cut(words: Int) {
            bytesAtCut = totals.lastOrNull() ?: 0L
            cuts += words
        }
    }

    /** Mỗi mảnh `w` chữ: một mốc 100 ms mỗi chữ (kết thúc ở (w - 1) x 100 + 80 ms), 200 khung mp3 hợp lệ (dư đuôi lặng như Edge thật) hay byte lạ; `tag` mỗi mảnh một số. */
    private fun answer(spoken: String, realFrames: Boolean, gate: CountDownLatch? = null, cut: Boolean = false, tag: (String) -> Int = { 1 }): Answer {
        val words = spoken.split(" ")
        var meta = ByteArray(0)
        words.forEachIndexed { i, word -> meta += metadata(i * 1_000_000L, 800_000, word) }
        val data = if (realFrames) mp3Frames(200, tag(spoken)) else ByteArray(words.size * 600) { tag(spoken).toByte() }
        // Cắt ngang một khung mp3 ở giữa audio: phần đầu đã chứa mọi mốc và nửa audio; phần sau là nửa còn lại + hết lượt.
        val half = data.size / 2
        return Answer(meta + audioOf(data.copyOf(half)), audioOf(data.copyOfRange(half, data.size)) + text("turn.end"), gate, cut)
    }

    private fun connector(realFrames: Boolean = true, build: (String) -> Answer = { answer(it, realFrames) }) = EdgeTts.Connector { _, _ ->
        val sent = ByteArrayOutputStream()
        WebSocket({ }, EdgeFake.Reply(sent, build), sent)
    }

    private fun assertLiveEqualsNormal(text: String, realFrames: Boolean) {
        val normal = EdgeTts("v", connector(realFrames)).synthesize(text, File(dir, "normal.mp3"))
        val recorder = Recorder()
        val live = EdgeTts("v", connector(realFrames)).synthesize(text, File(dir, "live.mp3"), recorder)
        val normalBytes = File(dir, "normal.mp3").readBytes()
        val liveBytes = File(dir, "live.mp3").readBytes()
        assertTrue("file ghi dần phải bằng file đường thường", normalBytes.contentEquals(liveBytes))
        assertEquals(normal.durationMs, live.durationMs)
        assertEquals(normal.words, live.words)
        assertEquals(normal.words, WordTokens.map(text, recorder.boundaries, live.durationMs)) // mốc đã báo dựng lại đúng mốc cuối
        assertTrue(recorder.totals.isNotEmpty())
        assertEquals(liveBytes.size.toLong(), recorder.totals.last())
        assertEquals(recorder.totals.sorted(), recorder.totals.toList()) // chỉ lớn lên
        for ((i, snapshot) in recorder.snapshots.withIndex()) { // mỗi lúc file chỉ lớn thêm, không bao giờ đổi phần đã ghi
            assertTrue("ảnh chụp $i phải là phần đầu của file cuối", snapshot.contentEquals(liveBytes.copyOf(snapshot.size)))
        }
        assertEquals(live, recorder.done)
        assertNull(recorder.failure)
    }

    @Test
    fun streamedFileAndBoundariesEqualTheNormalPathWithTrimmedPieces() {
        assertTrue(EdgePieces.split(sentences).size >= 3)
        assertLiveEqualsNormal(sentences, realFrames = true)
    }

    @Test
    fun streamedFileEqualsTheNormalPathWhenTheFramesAreNotWhatEdgeSends() {
        assertLiveEqualsNormal(sentences, realFrames = false) // trim trả nguyên: phát nốt toàn bộ
    }

    @Test
    fun aSinglePieceClipStreamsEverythingAsItArrives() {
        assertEquals(1, EdgePieces.split("Xin chào các bạn.").size)
        assertLiveEqualsNormal("Xin chào các bạn.", realFrames = true)
    }

    @Test
    fun theHeadPieceReachesTheFileBeforeItsTurnEndsAndLaterPiecesWaitForTheirTurn() {
        val pieces = EdgePieces.split(sentences)
        val first = pieces[0]
        val gate = CountDownLatch(1)
        val started = CountDownLatch(1)
        val recorder = Recorder { started.countDown() }
        val build = { spoken: String -> answer(spoken, true, gate = if (spoken == first) gate else null) }
        val result = AtomicReference<Clip>()
        val worker = Thread { result.set(EdgeTts("v", connector(true, build)).synthesize(sentences, File(dir, "gated.mp3"), recorder)) }.also { it.start() }
        try {
            assertTrue("byte đầu phải ra khi mảnh đầu chưa xong lượt", started.await(5, TimeUnit.SECONDS))
            Thread.sleep(300) // các mảnh sau xong hết trong lúc mảnh đầu còn đứng ở cổng
            // Mảnh đầu chưa phải mảnh cuối: chỉ phát tới khung floor(mốc hết chữ cuối / 24 ms); mốc ấy là (w - 1) x 100 + 80 ms, có 100 audio của nửa clip giả (100 khung) nên khung tối đa = min(100, ...).
            val words = first.split(" ").size
            val frames = minOf(100, ((words - 1) * 100 + 80) / EdgeJoin.FRAME_MS)
            assertEquals(listOf(frames * EdgeJoin.FRAME_BYTES.toLong()), recorder.totals.toList())
            assertTrue(recorder.boundaries.size >= words) // mốc của mảnh đầu đã báo (nó về trước tiếng)
            assertTrue(recorder.boundaries.size == words) // mảnh sau chưa tới lượt: mốc của chúng chưa báo
        } finally {
            gate.countDown()
            worker.join(10_000)
        }
        assertNull(recorder.failure)
        val normal = EdgeTts("v", connector(true)).synthesize(sentences, File(dir, "normal.mp3"))
        assertTrue(File(dir, "normal.mp3").readBytes().contentEquals(File(dir, "gated.mp3").readBytes()))
        assertEquals(normal.words, result.get().words)
    }

    @Test
    fun aHeadPieceCutAfterItWasStreamedIsRetriedAndMustAnswerTheSameThing() {
        val first = EdgePieces.split(sentences)[0]
        val attempts = ConcurrentHashMap<String, AtomicInteger>()
        val build = { spoken: String ->
            val n = attempts.getOrPut(spoken) { AtomicInteger() }.getAndIncrement()
            answer(spoken, true, cut = spoken == first && n == 0)
        }
        val recorder = Recorder()
        val clip = EdgeTts("v", connector(true, build)) { }.synthesize(sentences, File(dir, "retry.mp3"), recorder)
        assertEquals(2, attempts.getValue(first).get()) // mảnh đầu bị cắt giữa lượt rồi đọc lại
        val normal = EdgeTts("v", connector(true)).synthesize(sentences, File(dir, "normal.mp3"))
        assertTrue(File(dir, "normal.mp3").readBytes().contentEquals(File(dir, "retry.mp3").readBytes()))
        assertEquals(normal.words, clip.words)
        assertEquals(normal.words, WordTokens.map(sentences, recorder.boundaries, clip.durationMs))
        assertNull(recorder.failure)
    }

    @Test
    fun aHeadPieceThatAnswersDifferentlyAfterBeingStreamedFailsTheClip() {
        val first = EdgePieces.split(sentences)[0]
        val attempts = ConcurrentHashMap<String, AtomicInteger>()
        val build = { spoken: String ->
            val n = attempts.getOrPut(spoken) { AtomicInteger() }.getAndIncrement()
            answer(spoken, true, cut = spoken == first && n == 0, tag = { if (n == 0) 1 else 2 }) // lần sau trả byte khác
        }
        val recorder = Recorder()
        try {
            EdgeTts("v", connector(true, build)) { }.synthesize(sentences, File(dir, "diff.mp3"), recorder)
            fail("đáng ra lỗi")
        } catch (error: VoiceException) {
            assertEquals("service", error.reason)
            assertTrue(error.message!!.contains("khác đi"))
        }
        assertTrue(recorder.failure is VoiceException)
        assertNull(recorder.done)
    }

    @Test
    fun aLaterPieceThatFailsIsToldAtOnceAndThePiecesBeforeItStillReachTheFile() {
        // uxfix63 (máy tính: edge.py `_gather`, a59d e1): mảnh 3 hỏng hẳn khi mảnh 1 còn đang về. Trước: cả clip hỏng ngay, mảnh 1-2 bị huỷ, người nghe chỉ còn phần đã ghi. Giờ: chỗ nhận
        // biết NGAY tiếng dừng ở chữ đầu mảnh 3 (xin phần nối sớm), mảnh 1-2 vẫn về và ghi hết, phần dở của mảnh 3 không bao giờ vào file, rồi mới báo lỗi.
        val pieces = EdgePieces.split(sentences)
        assertTrue(pieces.size >= 3)
        val gate = CountDownLatch(1)
        val build = { spoken: String -> answer(spoken, true, gate = if (spoken == pieces[0]) gate else null, cut = spoken == pieces[2]) }
        val recorder = Recorder()
        val error = AtomicReference<Exception>()
        val worker = Thread {
            try {
                EdgeTts("v", connector(true, build)) { }.synthesize(sentences, File(dir, "cut.mp3"), recorder)
            } catch (failure: Exception) {
                error.set(failure)
            }
        }.also { it.start() }
        val before = pieces[0].split(" ").size + pieces[1].split(" ").size
        try {
            val deadline = System.nanoTime() + 5_000_000_000L
            while (recorder.cuts.isEmpty() && System.nanoTime() < deadline) Thread.sleep(10)
            assertEquals(listOf(before), recorder.cuts.toList()) // báo khi mảnh 1 còn đứng ở cổng
            assertTrue(worker.isAlive)
            assertNull(recorder.failure)
        } finally {
            gate.countDown()
            worker.join(10_000)
        }
        assertTrue(error.get() is VoiceException)
        assertTrue(recorder.failure is VoiceException)
        assertNull(recorder.done)
        assertEquals(before, recorder.boundaries.size) // mảnh 1-2 đủ mốc, không mốc nào của mảnh hỏng
        val normal = File(dir, "normal.mp3").also { EdgeTts("v", connector(true)).synthesize(sentences, it) }.readBytes()
        val streamed = File(dir, "cut.mp3").readBytes()
        assertTrue(streamed.size > recorder.bytesAtCut)
        assertTrue("phần đã ghi là phần đầu đúng của clip", streamed.contentEquals(normal.copyOf(streamed.size)))
        assertEquals(recorder.totals.last(), streamed.size.toLong())
        val heard = WordTokens.map(sentences, recorder.boundaries, EdgeProtocol.durationMs(streamed.size.toLong()))
        assertTrue(heard[before - 1].end <= EdgeProtocol.durationMs(streamed.size.toLong()))
    }

    @Test
    fun aFirstPieceThatFailsStillFailsTheClipAtOnceWithoutACut() {
        val pieces = EdgePieces.split(sentences)
        val build = { spoken: String -> answer(spoken, true, cut = spoken == pieces[0]) }
        val recorder = Recorder()
        try {
            EdgeTts("v", connector(true, build)) { }.synthesize(sentences, File(dir, "first.mp3"), recorder)
            fail("đáng ra lỗi")
        } catch (error: VoiceException) {
            assertTrue(recorder.cuts.isEmpty())
        }
    }

    @Test
    fun aCutNamesTheFirstShownWordWithoutSound() {
        // "năm 1900 anh đi." đọc thành "năm một nghìn chín trăm anh đi.": cắt trước chữ đọc thứ 5 ("anh") = chữ hiện thứ 2; cắt giữa "1900" thì đọc lại cả chữ ấy.
        val spans = listOf(SpokenText.Range(0, 0), SpokenText.Range(1, 4), SpokenText.Range(5, 5), SpokenText.Range(6, 6))
        val got = CopyOnWriteArrayList<Int>()
        val target = object : LiveClips.Target {
            override fun accepting() = true
            override fun grew(file: File, total: Long) {}
            override fun words(words: List<Span>, durationMs: Long, heardMs: Long) {}
            override fun done(total: Long) {}
            override fun failed(error: Exception) {}
            override fun cut(word: Int) { got += word }
        }
        val words = LiveWords("năm một nghìn chín trăm anh đi.", { SpokenText.expandWords(it, spans) }, target)
        for (said in listOf(5, 3, 1, 0, 7)) words.cut(said)
        assertEquals(listOf(2, 1, 1, 0, 4), got.toList())
    }

    @Test
    fun aFailureBeforeTheFirstByteIsReportedAndNothingWasStreamed() {
        val recorder = Recorder()
        val connector = EdgeTts.Connector { _, _ -> throw java.net.UnknownHostException("speech.platform.bing.com") }
        try {
            EdgeTts("v", connector).synthesize(sentences, File(dir, "none.mp3"), recorder)
            fail("đáng ra lỗi")
        } catch (error: VoiceException) {
            assertTrue(error.offline)
        }
        assertTrue(recorder.totals.isEmpty())
        assertTrue(recorder.failure is VoiceException)
        assertNull(recorder.done)
    }

    @Test
    fun noAudioIsStillAnErrorWhenStreaming() {
        val recorder = Recorder()
        val connector = connector(true) { Answer(text("turn.start"), text("turn.end")) }
        try {
            EdgeTts("v", connector).synthesize("Xin", File(dir, "empty.mp3"), recorder)
            fail("đáng ra lỗi")
        } catch (error: VoiceException) {
            assertTrue(error.message!!.contains("không trả về âm thanh"))
        }
        assertTrue(recorder.failure is VoiceException)
    }

    @Test
    fun tentativeWordsOfANormalisedParagraphComeBackAsOneSpanPerShownWord() {
        // Edge nhận chữ đã chuẩn hoá (nhiều chữ đọc hơn chữ hiện): mốc tạm đi qua cùng phép đổi như mốc cuối ([Voice.synthesize]).
        val received = CopyOnWriteArrayList<List<Span>>()
        val target = object : LiveClips.Target {
            override fun accepting() = true
            override fun grew(file: File, total: Long) {}
            override fun words(words: List<Span>, durationMs: Long, heardMs: Long) { received += words }
            override fun done(total: Long) {}
            override fun failed(error: Exception) {}
        }
        val text = "Haaah, HP 1,500 và Otsuki-san."
        val clip = LiveClips.receiving(target) { EdgeTts("v", connector(true)).synthesize(text, File(dir, "n.mp3"), "ja", null) }
        assertEquals(text.split(" ").size, clip.words.size)
        assertTrue(received.isNotEmpty())
        assertEquals(clip.words, received.last())
    }

    @Test
    fun theThreadLocalTargetReceivesTentativeWordsAndOnlyTheFirstStream() {
        val grew = AtomicInteger()
        val received = CopyOnWriteArrayList<Pair<List<Span>, Long>>()
        val target = object : LiveClips.Target {
            var claimed = false
            override fun accepting() = !claimed
            override fun grew(file: File, total: Long) { claimed = true; grew.incrementAndGet() }
            override fun words(words: List<Span>, durationMs: Long, heardMs: Long) { received += words to durationMs }
            override fun done(total: Long) {}
            override fun failed(error: Exception) {}
        }
        // Clip phát luồng cho chỗ nhận gắn vào luồng (LiveClips.receiving): mốc tạm về dần, rồi mốc cuối.
        val clip = LiveClips.receiving(target) { EdgeTts("v", connector(true)).synthesize("Xin chào các bạn.", File(dir, "t1.mp3")) }
        assertTrue(grew.get() > 0)
        assertTrue(clip.words.isNotEmpty())
        assertTrue(received.isNotEmpty())
        assertEquals(clip.words.size, received.last().first.size)
        assertTrue(received.last().second <= clip.durationMs + 100)
        val before = grew.get()
        LiveClips.receiving(target) { EdgeTts("v", connector(true)).synthesize("Xin chào các bạn.", File(dir, "t2.mp3")) } // đã phát luồng một lần: đường thường
        assertEquals(before, grew.get())
        assertFalse(File(dir, "t2.mp3").length() == 0L)
    }
}
