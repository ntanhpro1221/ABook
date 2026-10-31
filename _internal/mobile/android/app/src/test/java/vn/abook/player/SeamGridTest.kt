package vn.abook.player

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Lưới khối của Nối WAV khi tua (PLAN_loop §44.7, result10): mô hình media3 1.11.1 đọc từ bytecode -
 * tải lại ở T ms: khung đầu = floor(T × sr / 1000) (WavSeekMap), khối sr/10 khung, nhãn khối j = T ms + floor(j × khối × 1e6 / sr) µs (WavExtractor);
 * tua trong bộ đệm tới P ms: khối ĐẦU TIÊN có nhãn >= P ms (SampleQueue.findSampleAfter, audio/raw mọi mẫu là mẫu đồng bộ).
 */
class SeamGridTest {
    private val rates = intArrayOf(8000, 11025, 12000, 16000, 22050, 24000, 32000, 44100, 48000)

    private fun chunk(sr: Int) = (sr / 10).toLong().coerceAtLeast(1)

    /** Khối đáp khi tua TRONG bộ đệm tới `p` ms, bộ đệm tải từ `t` ms (khung đầu của khối đáp). */
    private fun inBuffer(sr: Int, t: Long, p: Long): Long {
        val f0 = t * sr / 1000
        var j = 0L
        while (t * 1000 + j * chunk(sr) * 1_000_000 / sr < p * 1000) j++
        return f0 + j * chunk(sr)
    }

    /** Khối đáp khi tua NGOÀI bộ đệm tới `p` ms: tải lại từ đó. */
    private fun reload(sr: Int, p: Long): Long = p * sr / 1000

    private fun seam(sr: Int) = LoopSeam.Seam(java.io.File("a.mp3"), java.io.File("a.wav"), 1152, 115200, 1152000, sr * 3, sr, 2, 1152, 0L)

    @Test
    fun oneMillisecondStepAsideReproducesTheLs06Offset() {
        // lần 3 của ls_06: đích 21703 -> (400 ms, 4063); tua đệm cũ 399 ms tải lại lệch lưới, tua thật rơi vào bộ đệm ấy -> khối 22005
        val sr = 44100
        val plan = LoopSeam.seekPlan(seam(sr), 1, 21703)
        val landedChunk = inBuffer(sr, LoopSeam.stepAside(plan.positionMs), plan.positionMs)
        assertEquals(22005L, landedChunk)
        assertEquals(4365L, landedChunk + plan.trimFrames - 21703) // = 4410 - 45: tiếng vào muộn 98,98 ms
    }

    @Test
    fun seamSeeksStayOnTheChunkGridAtEveryCommonRateDivisibleByTen() {
        for (sr in rates.filter { LoopSeam.seamGridExact(it) }) {
            val s = seam(sr)
            val c = chunk(sr)
            assertEquals("sr $sr: khối đúng 100 ms", LoopSeam.SEAM_CHUNK_MS * sr, c * 1000)
            for (m in 0 until 25L) for (frac in longArrayOf(0, 1, c / 3, c - 1)) {
                val target = m * c + frac
                val plan = LoopSeam.seekPlan(s, 1, target)
                val b0 = m * c
                val what = "sr $sr đích $target"
                assertEquals(what, target - b0, plan.trimFrames)
                // tải lại ở chính vị trí tua: ms nguyên đúng của ranh khối
                assertEquals(what, b0, reload(sr, plan.positionMs))
                // tua trong bộ đệm tải từ đầu Nối (chuyển mục liền)
                assertEquals(what, b0, inBuffer(sr, 0, plan.positionMs))
                // tua đệm (ExoPlayer bỏ lệnh tua cùng chỗ): lần tải lại ở chỗ tua đệm vẫn trên lưới, tua thật sau đó (trong hay ngoài bộ đệm ấy) đáp đúng b0
                val aside = LoopSeam.stepAside(1, plan.positionMs)
                assertTrue(what, aside != plan.positionMs && !LoopSeam.seekIsNoop(1, plan.positionMs, 1, aside))
                assertEquals(what, 0L, reload(sr, aside) % c)
                if (aside < plan.positionMs) assertEquals(what, b0, inBuffer(sr, aside, plan.positionMs))
                else assertEquals(what, b0, reload(sr, plan.positionMs)) // tua đệm sau vị trí: bộ đệm ấy không chứa P, tải lại ở P
                // mục Nối khác (index 3, 5) cùng luật
                assertEquals(what, plan.positionMs, LoopSeam.seekPlan(s, 3, target).positionMs)
                assertEquals(what, aside, LoopSeam.stepAside(3, plan.positionMs))
            }
        }
    }

    @Test
    fun seamStepAsideIsTheNeighbouringChunkBoundary() {
        assertEquals(300L, LoopSeam.stepAside(1, 400))
        assertEquals(0L, LoopSeam.stepAside(1, 100))
        assertEquals(100L, LoopSeam.stepAside(1, 0)) // đầu Nối: ranh khối sau
        assertEquals(1900L, LoopSeam.stepAside(5, 2000))
    }

    @Test
    fun clipStepAsideIsUnchanged() {
        for (index in intArrayOf(0, 2, 4)) {
            assertEquals(399L, LoopSeam.stepAside(index, 400))
            assertEquals(1L, LoopSeam.stepAside(index, 0))
            assertEquals(LoopSeam.stepAside(139_520), LoopSeam.stepAside(index, 139_520))
        }
    }

    @Test
    fun elevenKilohertzIsTheKnownExceptionLeftToTheSafetyNet() {
        // khối 1102 khung = 99,95 ms: ms của ranh khối làm tròn xuống nên tải lại ở đó đáp sớm vài khung (lưới an toàn bắt, |lệch| < 1 ms)
        val sr = 11025
        assertFalse(LoopSeam.seamGridExact(sr))
        val s = seam(sr)
        var worst = 0L
        for (m in 1 until 25L) {
            val target = m * chunk(sr) + 7
            val plan = LoopSeam.seekPlan(s, 1, target)
            val b0 = target - plan.trimFrames
            assertEquals(b0, inBuffer(sr, 0, plan.positionMs)) // tua trong bộ đệm từ đầu Nối vẫn đúng
            worst = maxOf(worst, Math.abs(reload(sr, plan.positionMs) - b0))
        }
        assertTrue("lệch khi tải lại: $worst khung", worst in 1..sr / 1000L)
    }
}
