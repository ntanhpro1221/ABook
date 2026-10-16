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
        ClipRetry.run(true, delays, sleep = { true }, record = { recorded += it }, clock = clock) { _ ->
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
