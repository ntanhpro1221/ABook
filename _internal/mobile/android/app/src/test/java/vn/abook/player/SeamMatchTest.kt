package vn.abook.player

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assert.assertNull
import org.junit.Assert.assertSame
import org.junit.Test

class SeamMatchTest {
    /** WAV giả 2 kênh: mẫu ngẫu nhiên hạt cố định trong ±20000 (không có hai cửa sổ dài nào trùng nhau). */
    private fun ref(frames: Int): ShortArray {
        val random = java.util.Random(42)
        return ShortArray(frames * 2) { (random.nextInt(40001) - 20000).toShort() }
    }

    private fun window(ref: ShortArray, frame: Int, frames: Int) = ref.copyOfRange(frame * 2, (frame + frames) * 2)

    @Test
    fun findsTheExactFrameAcrossTheWholeFile() {
        val r = ref(5000)
        val w = window(r, 4321, 256)
        assertEquals(4321L, SeamMatch.locate(r, 2, w, 0, Long.MAX_VALUE, 0))
        // tìm khớp thứ hai từ sau khớp đầu: không có
        assertEquals(-1L, SeamMatch.locate(r, 2, w, 4322, Long.MAX_VALUE, 0))
    }

    @Test
    fun exactMatchRejectsOneLsbButToleranceTwoAcceptsIt() {
        val r = ref(3000)
        val w = window(r, 1000, 64)
        w[10] = (w[10] + 1).toShort()
        assertEquals(-1L, SeamMatch.locate(r, 2, w, 0, Long.MAX_VALUE, 0))
        assertEquals(1000L, SeamMatch.locate(r, 2, w, 0, Long.MAX_VALUE, 2))
    }

    @Test
    fun rangeIsClampedAndRespected() {
        val r = ref(3000)
        val w = window(r, 2900, 100) // cửa sổ chạm cuối file
        assertEquals(2900L, SeamMatch.locate(r, 2, w, -500, 99_999, 0))
        assertEquals(-1L, SeamMatch.locate(r, 2, w, 0, 2899, 0))
        assertEquals(-1L, SeamMatch.locate(r, 2, w, 2901, 99_999, 0))
        assertEquals(-1L, SeamMatch.locate(r, 2, ShortArray(0), 0, 99_999, 0))
    }

    @Test
    fun silenceMatchesFirstThenSecondPosition() {
        val r = ShortArray(2000) // 1000 khung im
        val w = ShortArray(512)
        assertEquals(0L, SeamMatch.locate(r, 2, w, 0, Long.MAX_VALUE, 0))
        assertEquals(1L, SeamMatch.locate(r, 2, w, 1, Long.MAX_VALUE, 0))
    }

    // ---- lưới an toàn của Nối: SeamMatch.nearest / LoopSeam.landOf ----

    /** Nối giả 44,1 kHz stereo dài 2 s (như ls_06), ±1 s quanh đích như [LoopSeam.landOf]. */
    private val sr = 44100

    @Test
    fun nearestFindsTheTargetItself() {
        val r = ref(2 * sr)
        val w = window(r, 21703, 256)
        assertEquals(21703L, SeamMatch.nearest(r, 0, 2, w, 21703, sr.toLong()))
        // đoạn tham chiếu là một khúc của trục chung bắt đầu ở 21703 - 44100 < 0 -> kẹp 0; bắt đầu ở 1000 thì kết quả vẫn trên trục chung
        val part = r.copyOfRange(1000 * 2, r.size)
        assertEquals(21703L, SeamMatch.nearest(part, 1000, 2, w, 21703, sr.toLong()))
    }

    @Test
    fun nearestFindsTheLs06OffsetOfPlus4365() {
        // lần 3 của ls_06: đích 21703, tiếng thật bắt đầu ở 26068 (= 22005 + 4063, khối 17595 bị bỏ)
        val r = ref(2 * sr)
        val w = window(r, 26068, 256)
        val landed = SeamMatch.nearest(r, 0, 2, w, 21703, sr.toLong())
        assertEquals(26068L, landed)
        assertEquals(4365L, landed!! - 21703)
        assertEquals(98.98, (landed - 21703) * 1000.0 / sr, 0.01)
        // lệch về trước cũng thấy
        assertEquals(17595L, SeamMatch.nearest(r, 0, 2, window(r, 17595, 256), 21703, sr.toLong()))
    }

    @Test
    fun nearestReturnsNullWhenNotFoundOrOutOfRadius() {
        val r = ref(2 * sr)
        val other = java.util.Random(7).let { rnd -> ShortArray(512) { (rnd.nextInt(40001) - 20000).toShort() } }
        assertNull(SeamMatch.nearest(r, 0, 2, other, 21703, sr.toLong()))
        // có trong file nhưng xa hơn bán kính
        assertNull(SeamMatch.nearest(r, 0, 2, window(r, 30000, 256), 21703, 4000))
        assertNull(SeamMatch.nearest(r, 0, 2, ShortArray(0), 21703, sr.toLong()))
        // một bit lệch: không khớp (PCM16 đi thẳng, không dung sai)
        val w = window(r, 21703, 256)
        w[300] = (w[300] + 1).toShort()
        assertNull(SeamMatch.nearest(r, 0, 2, w, 21703, sr.toLong()))
    }

    @Test
    fun nearestPrefersTheTargetInSilence() {
        val r = ShortArray(2 * sr * 2)
        assertEquals(21703L, SeamMatch.nearest(r, 0, 2, ShortArray(512), 21703, sr.toLong())) // im lặng: mọi chỗ đều khớp, không có bằng chứng lệch
        // gần đích nhất: hai chỗ khớp ở +100 và -60 -> -60
        val noisy = ref(2 * sr)
        val w = window(noisy, 5000, 64)
        w.copyInto(noisy, (21703 + 100) * 2)
        w.copyInto(noisy, (21703 - 60) * 2)
        assertEquals(21643L, SeamMatch.nearest(noisy, 0, 2, w, 21703, sr.toLong()))
    }

    @Test
    fun landOfReadsTheSeamWavAroundTheTarget() {
        val r = ref(2 * sr)
        val wav = java.io.File.createTempFile("seam", ".wav")
        try {
            val data = java.nio.ByteBuffer.allocate(r.size * 2).order(java.nio.ByteOrder.LITTLE_ENDIAN)
            data.asShortBuffer().put(r)
            wav.writeBytes(LoopSeam.wavHeader(sr, 2, r.size * 2) + data.array())
            val seam = LoopSeam.Seam(java.io.File("ls_06.mp3"), wav, 1152, 115200, 1152000, 2 * sr, sr, 2, 1152, 0L)
            assertEquals(26068L, LoopSeam.landOf(seam, 21703, window(r, 26068, LoopSeam.LAND_FRAMES)))
            assertEquals(21703L, LoopSeam.landOf(seam, 21703, window(r, 21703, LoopSeam.LAND_FRAMES)))
            // sát đầu / cuối Nối: vùng đọc kẹp trong file
            assertEquals(3L, LoopSeam.landOf(seam, 0, window(r, 3, LoopSeam.LAND_FRAMES)))
            assertEquals(2L * sr - 256, LoopSeam.landOf(seam, 2L * sr - 300, window(r, 2 * sr - 256, LoopSeam.LAND_FRAMES)))
            assertNull(LoopSeam.landOf(seam, 21703, ShortArray(LoopSeam.LAND_FRAMES * 2) { 12345.toShort() }))
            assertArrayEquals(window(r, 100, 3), LoopSeam.readWavFrames(wav, 2, 100, 3))
        } finally {
            wav.delete()
        }
    }

    /** Thời gian (JVM, máy dev) của một lần tìm: đúng đích (ca thường, O(K)), lệch +4365 (ls_06), không thấy (quét hết ±1 s). In ra để ghi vào báo cáo; trần lỏng chỉ chặn hồi quy lớn. */
    @Test
    fun nearestMicroBench() {
        val r = ref(3 * sr) // ±1 s quanh đích 1,5 s đọc từ WAV
        val center = 1L * sr
        val cases = listOf(
            "dich" to window(r, (center + sr / 2).toInt(), 256),
            "+4365" to window(r, (center + sr / 2 + 4365).toInt(), 256),
            "khong" to java.util.Random(9).let { rnd -> ShortArray(512) { (rnd.nextInt(40001) - 20000).toShort() } },
        )
        val expected = center + sr / 2
        val out = StringBuilder()
        for ((name, w) in cases) {
            repeat(200) { SeamMatch.nearest(r, 0, 2, w, expected, sr.toLong()) } // làm nóng JIT
            val n = 200
            val t0 = System.nanoTime()
            repeat(n) { SeamMatch.nearest(r, 0, 2, w, expected, sr.toLong()) }
            val us = (System.nanoTime() - t0) / 1000.0 / n
            out.append("$name ${"%.1f".format(java.util.Locale.ROOT, us)} us; ")
            assertTrue("$name: $us µs", us < 50_000)
        }
        println("SeamMatch.nearest bench (K=256, ±1 s @44,1 kHz stereo): $out")
    }

    @Test
    fun teeMarkTakesTheLastFlushInTheWindowBeforeTheNextSeek() {
        val ms = 1_000_000L
        val a = Triple(1, 100 * ms, 0)
        val a2 = Triple(2, 110 * ms, 0) // lệnh tua đệm (stepAside) rồi tua thật: hai flush
        val b = Triple(3, 300 * ms, 9000)
        val marks = listOf(a, a2, b)
        // lần A (100 ms), lần B ở 290 ms: chỉ lấy flush trước B
        assertSame(a2, SeamMatch.teeMark(marks, 95 * ms, 300 * ms, 290 * ms))
        // lần B
        assertSame(b, SeamMatch.teeMark(marks, 290 * ms, 300 * ms))
        // không giới hạn: mốc cuối trong cửa sổ (như land() cũ)
        assertSame(b, SeamMatch.teeMark(marks, 95 * ms, 300 * ms))
        // ngoài cửa sổ: mốc đầu tiên sau lệnh tua
        assertSame(b, SeamMatch.teeMark(marks, 150 * ms, 100 * ms))
        assertNull(SeamMatch.teeMark(marks, 400 * ms, 300 * ms))
        assertNull(SeamMatch.teeMark(marks, 120 * ms, 300 * ms, 200 * ms))
    }
}
