package vn.abook.player

import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.exp
import kotlin.math.ln
import kotlin.math.log10
import kotlin.math.max
import kotlin.math.min
import kotlin.math.sin

/**
 * Log-mel cho tháp CLAP của bộ phân tích nhạc (webui/music_mel.py - bản numpy của `ClapFeatureExtractor`, đúng cấu hình của gói
 * trò: 48 kHz, FFT 1024, hop 480, 64 dải mel slaney 50-14000 Hz, repeatpad, không top_db). Mọi hằng số chép từ đó; sửa một hằng là
 * đầu trò lệch (MusicMelTest so với số của Python).
 *
 * Một cửa sổ w (mono, <= 10 giây): lặp lại nguyên số lần rồi đệm 0 cho đủ 480000 mẫu; đệm phản xạ 512 mẫu mỗi bên; 1001 khung
 * 1024 mẫu, bước 480, nhân Hann tuần hoàn; công suất = |rfft|^2; nhân ngân hàng lọc, sàn 1e-10, 10*log10. Ra [1001][64] (khung
 * trước, mel sau). Tính bằng double (rẻ - ba cửa sổ chưa tới nửa giây) rồi ép float32 như bản Python.
 */
object MusicMel {
    const val SAMPLE_RATE = 48_000
    const val N_FFT = 1024
    const val HOP = 480
    const val N_MELS = 64
    const val F_MIN = 50.0
    const val F_MAX = 14_000.0
    const val MAX_SAMPLES = 480_000
    const val FRAMES = 1 + MAX_SAMPLES / HOP // 1001
    private const val MEL_FLOOR = 1e-10
    private const val BINS = N_FFT / 2 + 1

    private fun hzToMel(freq: Double): Double =
        if (freq >= 1000.0) 15.0 + ln(max(freq, 1e-12) / 1000.0) * (27.0 / ln(6.4)) else 3.0 * freq / 200.0

    private fun melToHz(mel: Double): Double =
        if (mel >= 15.0) 1000.0 * exp((ln(6.4) / 27.0) * (mel - 15.0)) else 200.0 * mel / 3.0

    /** numpy.linspace: bước đều, điểm cuối đúng bằng `stop`. */
    private fun linspace(start: Double, stop: Double, count: Int): DoubleArray {
        val step = (stop - start) / (count - 1)
        return DoubleArray(count) { if (it == count - 1) stop else start + it * step }
    }

    /** Dải k..k+len của từng bộ lọc mel khác 0 (ngân hàng lọc thưa: mỗi dải chỉ phủ vài chục bin). */
    private class Filter(val first: Int, val weights: DoubleArray)

    private val FILTERS: Array<Filter> = run {
        val edges = linspace(hzToMel(F_MIN), hzToMel(F_MAX), N_MELS + 2).map { melToHz(it) }.toDoubleArray()
        val bins = linspace(0.0, (SAMPLE_RATE / 2).toDouble(), BINS)
        Array(N_MELS) { m ->
            val norm = 2.0 / (edges[m + 2] - edges[m])
            val weight = DoubleArray(BINS) { k ->
                val down = -(edges[m] - bins[k]) / (edges[m + 1] - edges[m])
                val up = (edges[m + 2] - bins[k]) / (edges[m + 2] - edges[m + 1])
                max(0.0, min(down, up)) * norm
            }
            val first = weight.indexOfFirst { it != 0.0 }.coerceAtLeast(0)
            val last = weight.indexOfLast { it != 0.0 }.coerceAtLeast(first)
            Filter(first, weight.copyOfRange(first, last + 1))
        }
    }

    /** Hann tuần hoàn: np.hanning(1025)[:1024]. */
    private val WINDOW = DoubleArray(N_FFT) { 0.5 - 0.5 * cos(2.0 * PI * it / N_FFT) }
    private val COS = DoubleArray(N_FFT / 2) { cos(2.0 * PI * it / N_FFT) }
    private val SIN = DoubleArray(N_FFT / 2) { -sin(2.0 * PI * it / N_FFT) }
    private val REVERSED = IntArray(N_FFT).also { table ->
        val bits = Integer.numberOfTrailingZeros(N_FFT)
        for (i in 0 until N_FFT) table[i] = Integer.reverse(i) ushr (32 - bits)
    }

    /** FFT cơ số 2 tại chỗ (re, im dài N_FFT). */
    private fun fft(re: DoubleArray, im: DoubleArray) {
        for (i in 0 until N_FFT) {
            val j = REVERSED[i]
            if (j > i) {
                val r = re[i]; re[i] = re[j]; re[j] = r
                val q = im[i]; im[i] = im[j]; im[j] = q
            }
        }
        var half = 1
        while (half < N_FFT) {
            val stride = N_FFT / (half * 2)
            var start = 0
            while (start < N_FFT) {
                for (k in 0 until half) {
                    val wr = COS[k * stride]
                    val wi = SIN[k * stride]
                    val a = start + k
                    val b = a + half
                    val tr = re[b] * wr - im[b] * wi
                    val ti = re[b] * wi + im[b] * wr
                    re[b] = re[a] - tr
                    im[b] = im[a] - ti
                    re[a] += tr
                    im[a] += ti
                }
                start += half * 2
            }
            half *= 2
        }
    }

    /** repeatpad của một cửa sổ (<= MAX_SAMPLES; dài hơn thì cắt) -> đúng MAX_SAMPLES mẫu. */
    private fun padWindow(wave: FloatArray, offset: Int, length: Int): DoubleArray {
        val out = DoubleArray(MAX_SAMPLES)
        if (length >= MAX_SAMPLES) {
            for (i in 0 until MAX_SAMPLES) out[i] = wave[offset + i].toDouble()
            return out
        }
        require(length > 0) { "cửa sổ rỗng" }
        for (i in 0 until (MAX_SAMPLES / length) * length) out[i] = wave[offset + i % length].toDouble()
        return out
    }

    /** Một cửa sổ -> [FRAMES * N_MELS] float32 (khung trước, mel sau) ghi vào `out` từ `outOffset`. */
    fun logMel(wave: FloatArray, offset: Int, length: Int, out: FloatArray, outOffset: Int) {
        val padded = padWindow(wave, offset, length)
        val half = N_FFT / 2
        // đệm phản xạ (mẫu rìa không lặp): vị trí p của dãy 481024 mẫu
        fun sample(p: Int): Double {
            val i = p - half
            return when {
                i < 0 -> padded[-i]
                i >= MAX_SAMPLES -> padded[2 * (MAX_SAMPLES - 1) - i]
                else -> padded[i]
            }
        }
        val re = DoubleArray(N_FFT)
        val im = DoubleArray(N_FFT)
        val power = DoubleArray(BINS)
        for (frame in 0 until FRAMES) {
            val start = frame * HOP
            for (i in 0 until N_FFT) {
                re[i] = sample(start + i) * WINDOW[i]
                im[i] = 0.0
            }
            fft(re, im)
            for (k in 0 until BINS) power[k] = re[k] * re[k] + im[k] * im[k]
            val row = outOffset + frame * N_MELS
            for (m in 0 until N_MELS) {
                val filter = FILTERS[m]
                var sum = 0.0
                for (i in filter.weights.indices) sum += power[filter.first + i] * filter.weights[i]
                out[row + m] = (10.0 * log10(max(MEL_FLOOR, sum))).toFloat()
            }
        }
    }

    fun logMel(wave: FloatArray, offset: Int = 0, length: Int = wave.size): FloatArray =
        FloatArray(FRAMES * N_MELS).also { logMel(wave, offset, length, it, 0) }

    /** Báo lỗi nếu `preprocessor_config.json` của gói không còn là cấu hình mà object này chép cứng (music_mel.check_config). */
    fun checkConfig(json: String) {
        val config = org.json.JSONObject(json)
        val expect = mapOf<String, Any?>("sampling_rate" to SAMPLE_RATE, "n_fft" to N_FFT, "fft_window_size" to N_FFT, "hop_length" to HOP,
            "feature_size" to N_MELS, "frequency_min" to F_MIN, "frequency_max" to F_MAX, "nb_max_samples" to MAX_SAMPLES,
            "padding" to "repeatpad", "truncation" to "rand_trunc", "top_db" to null)
        for ((key, want) in expect) {
            val have = config.opt(key)
            val same = when (want) {
                null -> config.isNull(key)
                is Number -> (have as? Number)?.toDouble() == want.toDouble()
                else -> have == want
            }
            if (!same) throw IllegalArgumentException("preprocessor_config $key=$have, bộ phân tích chép cứng $want")
        }
    }
}
