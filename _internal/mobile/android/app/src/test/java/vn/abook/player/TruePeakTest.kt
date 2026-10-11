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
