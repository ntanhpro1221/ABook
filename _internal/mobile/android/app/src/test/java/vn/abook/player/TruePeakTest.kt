package vn.abook.player

import org.json.JSONObject
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import kotlin.math.PI
import kotlin.math.log10
import kotlin.math.sin

/** [TruePeak] (đo đỉnh thật sau AAC của bản xuất) và [TruePeak.lower] (`_Lowered` của máy tính). */
class TruePeakTest {
    private val params = MusicRender.Params.parse(JSONObject(File("../../../abook/webui/assets/music_mix.json").readText()))

    private fun sine(n: Int, amplitude: Double, cycle: Double, phase: Double, channels: Int = 1) =
        ShortArray(n * channels) { k -> Math.rint(32768 * amplitude * sin(2 * PI * (k / channels) / cycle + phase)).toInt().toShort() }

    @Test
    fun a_quarter_rate_sine_between_samples_reads_its_true_peak() {
        // fs/4 lệch pha pi/4: mẫu chỉ +-0,707 A (-3 dB dưới đỉnh), đỉnh thật A nằm giữa hai mẫu - x4 phải thấy.
        val amplitude = 0.5
        // Chỉ đo đoạn giữa: chỗ sin bắt đầu / bị cắt cụt (sang im) bộ lọc rung thật (~0,1 dB, numpy cùng số) - đỉnh ấy không phải của sin.
        val peak = TruePeak(params, 1, longArrayOf(0, 1000, 47000)).apply { feed(sine(48000, amplitude, 4.0, PI / 4)) }.finish()[1]
        val want = 20 * log10(amplitude)
        assertTrue("đo $peak, đỉnh thật $want", peak in want - 0.05..want + 0.01)
    }

    @Test
    fun each_segment_gets_its_own_peak_and_silence_is_minus_infinity() {
        val quiet = sine(1000, 0.1, 48.0, 0.0, 2)
        val loud = sine(1000, 0.8, 48.0, 0.0, 2)
        val meter = TruePeak(params, 2, longArrayOf(0, 1000, 1900, 2100))
        meter.feed(quiet)
        meter.feed(loud)
        meter.feed(ShortArray(2 * 1000))
        val peaks = meter.finish()
        // 0,1 -> 0,8 đổi ở khung 1000: nội suy của vài khung cuối đoạn 1 chạm mẫu to (rung của bộ lọc)
        assertEquals(20 * log10(0.1), peaks[0], 0.3)
        assertEquals(20 * log10(0.8), peaks[1], 0.01)
        // [1900, 2100): sin bị cắt cụt ở 2000 -> rung, vẫn đo được; từ 2100 chân bộ lọc chỉ chạm khung im: -inf
        assertTrue(peaks[2] > peaks[0])
        assertEquals(Double.NEGATIVE_INFINITY, peaks[3], 0.0)
        assertEquals(Double.NEGATIVE_INFINITY, TruePeak(params, 1).apply { feed(ShortArray(500)) }.finish().single(), 0.0)
    }

    @Test
    fun bytes_cut_anywhere_read_like_whole_frames() {
        val samples = sine(3001, 0.6, 37.0, 0.3, 2)
        val bytes = ByteArray(samples.size * 2)
        for (i in samples.indices) {
            bytes[2 * i] = samples[i].toInt().toByte()
            bytes[2 * i + 1] = (samples[i].toInt() shr 8).toByte()
        }
        val whole = TruePeak(params, 2, longArrayOf(0, 1500)).apply { feed(samples) }.finish()
        val cut = TruePeak(params, 2, longArrayOf(0, 1500))
        var at = 0
        for (size in generateSequence(1) { it % 7 + 1 }) {
            if (at >= bytes.size) break
            val take = minOf(size, bytes.size - at)
            cut.write(bytes, at, take)
            at += take
        }
        assertArrayEquals(whole, cut.finish(), 0.0)
    }

    /** Every interpolated point of every frame, no shortcut: the peak [TruePeak] must give to the last bit. */
    private fun everyPoint(x: DoubleArray): Double {
        var best = 0.0
        for (m in x.indices) {
            best = maxOf(best, Math.abs(x[m]))
            for (p in 0 until MusicRender.FIR_PHASES) {
                var v = 0.0
                for (j in 0 until MusicRender.FIR_TAPS) v += params.fir[p][j] * x.getOrElse(m - MusicRender.FIR_LEFT + j) { 0.0 }
                best = maxOf(best, Math.abs(v))
            }
        }
        return if (best > 0.0) 20 * log10(best) else Double.NEGATIVE_INFINITY
    }

    @Test
    fun the_peak_is_that_of_every_interpolated_point_whatever_the_signal() {
        val random = java.util.Random(7)
        // speech-like: loud bursts, a quiet tail, one lone peak late, then silence; also a clip that is quiet then loud
        for (shape in 0 until 4) {
            val n = 12000
            val x = DoubleArray(n) { i ->
                val burst = if ((i / 1500) % 2 == 0) 0.6 else 0.05
                when (shape) {
                    0 -> burst * random.nextGaussian() * 0.5
                    1 -> if (i < 6000) 0.01 * random.nextGaussian() else 0.9 * sin(2 * PI * i / 31.0)
                    2 -> if (i > 9000) 0.0 else burst * sin(2 * PI * i / 23.0 + 0.4) + 0.001 * random.nextGaussian()
                    else -> 0.0003 * random.nextGaussian()
                }
            }
            if (shape == 0) x[10001] = 1.07 // over full scale: measured as it is
            val floats = FloatArray(n) { x[it].toFloat() }
            val want = everyPoint(DoubleArray(n) { floats[it].toDouble() })
            assertEquals("shape $shape", want, TruePeak(params, 1).apply { feed(floats) }.finish()[0], 0.0)
        }
        val stereo = sine(5000, 0.7, 41.0, 0.2, 2).also { for (i in 2000 until 2600) it[i] = 0 }
        val split = TruePeak(params, 2, longArrayOf(0, 2500)).apply { feed(stereo) }.finish()
        val side = { c: Int, from: Int, to: Int -> DoubleArray(to - from) { stereo[2 * (from + it) + c] / 32768.0 } }
        // the first segment's frames are measured with the real samples after it as context: compare on the whole stream's peak instead
        val whole = maxOf(everyPoint(side(0, 0, 5000)), everyPoint(side(1, 0, 5000)))
        assertEquals(whole, maxOf(split[0], split[1]), 0.0)
    }

    @Test
    fun lowering_matches_the_desktop_formula_and_clips() {
        val samples = shortArrayOf(0, 1, -1, 1000, -1000, 32767, -32768, 12345)
        val db = 1.37
        val want = samples.map { Math.rint(it * Math.pow(10.0, -db / 20)).toInt().toShort() }
        TruePeak.lower(samples, db)
        assertEquals(want, samples.toList())
        val loud = shortArrayOf(30000, -30000)
        TruePeak.lower(loud, -6.0) // tăng thì kẹp
        assertEquals(listOf<Short>(32767, -32768), loud.toList())
    }
}
