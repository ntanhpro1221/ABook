package vn.abook.player.readaloud

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * Điện thoại sống sót qua giọng Edge chậm / chập chờn: độ sâu đọc trước theo tốc độ lấy clip ([ReadAheadPolicy], cùng luật `readAheadCount` ở máy tính) và tự thử lại lỗi
 * thoáng qua trước khi làm phiền người nghe ([ClipRetry]).
 */
class ReadAheadTest {
    private fun clip() = Clip(File("x.mp3"), 1000, emptyList(), "edge:v")

    // ---- độ sâu -----------------------------------------------------------------------------------------------

    @Test
    fun withoutEnoughMeasurementsItKeepsTheBaseDepthAndFastClipsStillKeepTheMinimumBuffer() {
        val policy = ReadAheadPolicy(2)
        val short = List(10) { 1_500L }
        val long = List(10) { 12_000L }
        assertTrue(policy.needMore(emptyList()))
        assertTrue(policy.needMore(listOf(1_500L)))
        assertFalse(policy.needMore(short.take(2))) // đủ 2 đoạn, chưa có số đo
        policy.record(20_000)
        assertFalse("một số đo chưa đủ", policy.needMore(short.take(2)))
        for (ms in listOf(800L, 1_100L, 900L, 1_200L, 1_000L, 900L, 1_100L, 1_000L)) policy.record(ms)
        assertEquals("Edge nhanh: vẫn đệm tối thiểu 20 s", ReadAheadPolicy.MIN_BUFFER_MS, policy.wantedMs())
        assertTrue("đoạn ngắn: 3 đoạn (4,5 s) chưa đủ 20 s", policy.needMore(short.take(3)))
        assertFalse("đoạn dài: 2 đoạn đã đủ", policy.needMore(long.take(2)))
        assertFalse(policy.slow())
    }

    @Test
    fun slowClipsGrowTheQueueUpToTheCapAndFastOnesShrinkItBack() {
        val policy = ReadAheadPolicy(2)
        val short = List(10) { 1_500L } // đoạn đối thoại ngắn
        for (ms in listOf(20_000L, 22_000L, 24_000L, 21_000L, 23_000L, 22_000L, 20_000L, 21_000L)) policy.record(ms)
        assertTrue(policy.slow())
        assertEquals(46_000L, policy.wantedMs()) // 2 x p80 (23 s)
        // 4 đoạn ngắn (6 s) chưa đủ -> còn nạp; chạm trần thì thôi
        assertTrue(policy.needMore(short.take(4)))
        assertTrue(policy.needMore(short.take(ReadAheadPolicy.MAX_AHEAD - 1)))
        assertFalse(policy.needMore(short.take(ReadAheadPolicy.MAX_AHEAD)))
        // đoạn văn xuôi dài (12 s): 4 đoạn = 48 s là đủ
        val long = List(10) { 12_000L }
        assertTrue(policy.needMore(long.take(3)))
        assertFalse(policy.needMore(long.take(4)))
        // trần thời gian đệm 60 s dù Edge chậm cỡ nào
        val glacial = ReadAheadPolicy(2)
        repeat(3) { glacial.record(100_000) }
        assertEquals(ReadAheadPolicy.MAX_BUFFER_MS, glacial.wantedMs())
        // clip về nhanh trở lại: số đo chậm trôi khỏi cửa sổ, độ sâu co về tối thiểu
        repeat(ReadAheadPolicy.SAMPLES) { policy.record(1_000) }
        assertFalse(policy.slow())
        assertEquals(ReadAheadPolicy.MIN_BUFFER_MS, policy.wantedMs())
        assertFalse(policy.needMore(long.take(2)))
        policy.record(30_000)
        policy.reset()
        assertEquals(0L, policy.wantedMs())
    }

    @Test
    fun cacheHitsAreNotMeasurements() {
        val policy = ReadAheadPolicy(2)
        repeat(8) { policy.record(30) } // bộ đệm: vài chục ms
        repeat(2) { policy.record(20_000) }
        assertTrue("chỉ hai số đo thật, p80 vẫn là 20 s", policy.wantedMs() >= 40_000L)
    }

    // ---- thử lại ----------------------------------------------------------------------------------------------

    private val delays = longArrayOf(2_000L, 5_000L)

    @Test
    fun aTransientErrorIsRetriedWithBackoffAndTheListenerIsNeverBotheredWhenItRecovers() {
        val slept = ArrayList<Long>()
        val flags = ArrayList<Boolean>()
        var calls = 0
        val result = ClipRetry.run(true, delays, sleep = { slept += it; true }) { willRetry ->
            flags += willRetry
            calls += 1
            if (calls <= 2) throw VoiceException("Giọng Edge đang không trả lời", reason = "service")
            clip()
        }
        assertTrue(result.isSuccess)
        assertEquals(3, calls)
        assertEquals(listOf(2_000L, 5_000L), slept)
        assertEquals("lần cuối thì tắt willRetry", listOf(true, true, false), flags)
    }

    @Test
    fun retriesAreExhaustedThenTheErrorGoesUp() {
        var calls = 0
        val result = ClipRetry.run(true, delays, sleep = { true }) { _ ->
            calls += 1
            throw VoiceException("Giọng Edge đang không trả lời", reason = "timeout")
        }
        assertEquals(1 + delays.size, calls)
        assertTrue(result.isFailure)
        assertEquals("timeout", (result.exceptionOrNull() as VoiceException).reason)
    }

    @Test
    fun nonTransientErrorsLocalVoicesAndFinalWordsAreNotRetried() {
        for (error in listOf(
            VoiceException("Không có mạng", offline = true),
            VoiceException("Từ chối", reason = "rejected"),
            VoiceException("Khóa sai", reason = "auth"),
            VoiceException("Hết hạn mức", reason = "quota"),
            VoiceException(ClipReader.NO_USABLE_VOICE, reason = "service", final = true),
        )) {
            var calls = 0
            val slept = ArrayList<Long>()
            val result = ClipRetry.run(true, delays, sleep = { slept += it; true }) { _ -> calls += 1; throw error }
            assertEquals(error.message, 1, calls)
            assertTrue(slept.isEmpty())
            assertTrue(result.isFailure)
        }
        var calls = 0
        ClipRetry.run(false, delays, sleep = { true }) { willRetry ->
            calls += 1
            assertFalse("giọng trên máy không có willRetry", willRetry)
            throw VoiceException("hỏng", reason = "service")
        }
        assertEquals(1, calls)
        ClipRetry.run(true, delays, sleep = { true }) { _ -> calls += 1; throw IllegalStateException("không phải lỗi giọng") }
        assertEquals("lỗi lạ không thử lại", 2, calls)
    }

    @Test
    fun aStaleJobStopsRetryingAtOnce() {
        var calls = 0
        val result = ClipRetry.run(true, delays, sleep = { false }) { _ ->
            calls += 1
            throw VoiceException("Edge bận", reason = "service")
        }
        assertEquals("người nghe đã tua đi chỗ khác: không gọi thêm lượt nào", 1, calls)
        assertTrue(result.isFailure)
    }

    @Test
    fun measurementsCountSuccessesAndSlowFailuresButNotInstantFailures() {
        val recorded = ArrayList<Long>()
        var now = 0L
        val clock = { now }
        var step = 0
        ClipRetry.run(true, delays, sleep = { true }, record = { recorded += it }, clock = clock, budgetMs = 600_000L) { _ ->
            step += 1
            when (step) {
                1 -> { now += 300_000_000L; throw VoiceException("502 tức thì", reason = "service") } // 0,3 s: không nói gì về tốc độ
                2 -> { now += 15_000_000_000L; throw VoiceException("chờ 15 s rồi hỏng", reason = "timeout") }
                else -> { now += 9_000_000_000L; clip() }
            }
        }
        assertEquals(listOf(15_000L, 9_000L), recorded)
        val local = ArrayList<Long>()
        ClipRetry.run(false, delays, sleep = { true }, record = { local += it }) { _ -> clip() }
        assertTrue("giọng trên máy không ghi số đo trực tuyến", local.isEmpty())
    }

    // ---- "Edge chậm" không dính mãi (soát a47 mục 2) ----------------------------------------------------------

    @Test
    fun fastParallelReadsTurnSlowModeOffAgain() {
        val policy = ReadAheadPolicy(2)
        repeat(ReadAheadPolicy.SAMPLES) { policy.record(12_000) }
        assertTrue(policy.slow())
        // Edge nhanh lại: đoạn kế chỉ được đọc song song (warm), lượt chính lấy từ bộ đệm - chỉ lượt song song có số đo. Nó phải đủ làm p80 tụt.
        var now = 0L
        repeat(ReadAheadPolicy.SAMPLES) {
            val result = policy.measure({ now }) { now += 1_200_000_000L; Result.success(clip()) }
            assertTrue(result.isSuccess)
        }
        assertFalse("8 lượt nhanh liền: không còn chậm", policy.slow())
        assertEquals(ReadAheadPolicy.MIN_BUFFER_MS, policy.wantedMs())
    }

    @Test
    fun measureRecordsSlowFailuresButNotInstantOnes() {
        val policy = ReadAheadPolicy(2)
        var now = 0L
        repeat(2) { policy.measure({ now }) { now += 300_000_000L; Result.failure<Clip>(VoiceException("tức thì", reason = "service")) } }
        assertEquals("lượt hỏng tức thì không nói gì về tốc độ", 0L, policy.wantedMs())
        repeat(2) { policy.measure({ now }) { now += 9_000_000_000L; Result.failure<Clip>(VoiceException("chờ rồi hỏng", reason = "timeout")) } }
        assertTrue(policy.slow())
    }

    // ---- quỹ thời gian thử lại (soát a47 mục 4) -----------------------------------------------------------------

    @Test
    fun aStalledNetworkFallsBackAfterOneAttemptNotAfterAMinute() {
        // Mạng còn nối mà Edge im: mỗi lần chờ tin 15 giây rồi "timeout". Trước quỹ: 3 lần ngoài (và 4 lần Edge tự thử trong mỗi lần) = tới cả phút+; giờ lần hỏng đầu đã quá quỹ.
        var now = 0L
        var calls = 0
        val slept = ArrayList<Long>()
        ClipRetry.run(true, delays, sleep = { slept += it; now += it * 1_000_000; true }, clock = { now }) { retry ->
            calls += 1
            now += 15_000_000_000L
            // Như ClipReader: ném lỗi thoáng qua lên chỉ khi người gọi sẽ thử lại (còn quỹ); không thì rơi sang giọng kế (ở đây: lời cuối).
            if (retry && !ClipBudget.retryFollows()) throw VoiceException("rơi sang giọng máy", reason = "service", final = true)
            throw VoiceException("Giọng Edge trả lời quá chậm", reason = "timeout")
        }
        assertEquals(1, calls)
        assertTrue("không nghỉ chờ thêm", slept.isEmpty())
    }

    @Test
    fun quickFailuresStillGetTheirRetriesInsideTheBudget() {
        var now = 0L
        var calls = 0
        val result = ClipRetry.run(true, delays, sleep = { now += it * 1_000_000; true }, clock = { now }) { retry ->
            calls += 1
            now += 500_000_000L
            if (calls <= 2) {
                assertTrue(retry)
                assertTrue("còn quỹ: ClipReader ném lỗi lên cho vòng ngoài", ClipBudget.retryFollows())
                throw VoiceException("Giọng Edge đang không trả lời", reason = "service")
            }
            clip()
        }
        assertTrue(result.isSuccess)
        assertEquals(3, calls)
    }

    @Test
    fun theBudgetCapsTheTotalWaitAcrossAllAttempts() {
        // Lần hỏng nào cũng mất 6 giây: quỹ 20 s đủ cho lần thứ hai (6 + 2 + 4 <= 20), không đủ cho lần ba (6 + 2 + 6 + 5 + 4 > 20).
        var now = 0L
        var calls = 0
        ClipRetry.run(true, delays, sleep = { now += it * 1_000_000; true }, clock = { now }) { _ ->
            calls += 1
            now += 6_000_000_000L
            throw VoiceException("Giọng Edge đang không trả lời", reason = "service")
        }
        assertEquals(2, calls)
        assertTrue("tổng chờ không quá quỹ", now <= ClipBudget.BUDGET_MS * 1_000_000)
    }

    @Test
    fun retriesAreGivenOnlyWhatIsLeftOfTheBudgetButTheFirstAttemptIsNeverCut() {
        var now = 0L
        val limits = ArrayList<Long>()
        ClipRetry.run(true, delays, sleep = { now += it * 1_000_000; true }, clock = { now }) { _ ->
            limits += ClipBudget.attemptMs(EdgeTts.TOTAL_MS, false) // lần đọc đầu của EdgeTts trong lần này
            limits += ClipBudget.attemptMs(EdgeTts.TOTAL_MS, true) // lần EdgeTts tự thử lại
            now += 3_000_000_000L
            throw VoiceException("cắt lượt", reason = "service")
        }
        // Lần 1: đọc đầu = đủ 45 s (Edge chậm thật 9-24 s vẫn xong); lần Edge tự thử lại = phần quỹ còn lại (20 s).
        assertEquals(EdgeTts.TOTAL_MS, limits[0])
        assertEquals(ClipBudget.BUDGET_MS, limits[1])
        // Lần 2 (thử lại của vòng ngoài): cả hai chỉ được phần còn lại: 20 - 3 - 2 = 15 s.
        assertEquals(15_000L, limits[2])
        assertEquals(15_000L, limits[3])
        // Ngoài quỹ (đọc song song): không giới hạn.
        assertEquals(EdgeTts.TOTAL_MS, ClipBudget.attemptMs(EdgeTts.TOTAL_MS, true))
        assertTrue(ClipBudget.retryFollows())
    }

    @Test
    fun voiceExceptionClassifiesWhatTheEdgeClientActuallyReturns() {
        assertTrue(VoiceException("cắt lượt", reason = "service").transient) // EdgeTts.NOT_ANSWERING, HTTP 429/5xx hết lần thử, không có âm thanh
        assertTrue(VoiceException("chậm", reason = "timeout").transient) // EdgeProtocol.readTurn
        assertTrue(VoiceException(EdgeTts.NOT_ANSWERING).transient)
        assertFalse(VoiceException(EdgeTts.LOST_NETWORK, offline = true).transient)
        assertFalse(VoiceException("Không có mạng để dùng giọng Edge", offline = true).transient)
        assertFalse(VoiceException("Dịch vụ giọng Edge từ chối (403)", reason = "rejected").transient)
        assertFalse(VoiceException("khoá", reason = "auth").transient)
        assertFalse(VoiceException("hạn mức", reason = "quota").transient)
        assertFalse(VoiceException("giọng lạ", reason = "voice").transient)
    }
}
