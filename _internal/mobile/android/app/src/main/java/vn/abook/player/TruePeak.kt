package vn.abook.player

import kotlin.math.abs
import kotlin.math.log10
import kotlin.math.max

/**
 * Đỉnh thật (dBTP) của PCM 16-bit xen kẽ kênh theo từng ĐOẠN khung - bước đo sau mã hoá AAC của bản xuất (máy tính:
 * `export.true_peak_dbtp`, ebur128 của ffmpeg). Nội suy x4 bằng đúng `truePeakFir` của bộ chặn ([MusicRender.Params.fir]): điểm
 * nội suy pha p giữa khung m và m+1 = sum_j fir[p][j] * x[m - 5 + j] (như `GuardStream.need`), cộng |mẫu| của chính khung m; đỉnh
 * của khung m tính vào đoạn chứa m. Đọc theo dòng (giữ 11 khung quá khứ), không giữ cả chương.
 *
 * [bounds] = khung bắt đầu của từng đoạn, tăng dần, bounds[0] = 0 (một đoạn = cả luồng: `intArrayOf(0)`). Bộ lọc khác ebur128 nên
 * số đo lệch máy tính chút ít (K2_SPEC mục 4) - không bắt khớp ffmpeg.
 */
class TruePeak(params: MusicRender.Params, private val channels: Int, bounds: LongArray = longArrayOf(0)) {
    private val fir = params.fir
    private val starts = bounds.copyOf()
    private val peaks = DoubleArray(starts.size)
    // x[m - 5 .. m + 6] của khung m đang chờ: vòng FIR_TAPS khung, mẫu thật (short / 32768)
    private val ring = DoubleArray(MusicRender.FIR_TAPS * channels)
    private var fed = 0L   // số khung đã vào
    private var segment = 0
    private var low = -1   // byte thấp còn chờ của [write]
    private val frame = ShortArray(channels)
    private var filled = 0 // mẫu của khung dở dang của [write]

    init {
        require(starts.isNotEmpty() && starts[0] == 0L) { "đoạn đầu phải bắt đầu ở khung 0" }
        for (i in 1 until starts.size) require(starts[i] >= starts[i - 1]) { "mốc đoạn phải tăng dần" }
    }

    /** Thêm `count` mẫu (không phải khung) từ [samples]. */
    fun feed(samples: ShortArray, count: Int = samples.size) {
        require(count % channels == 0) { "khối không trọn khung" }
        var i = 0
        while (i < count) {
            push { c -> samples[i + c] / 32768.0 }
            i += channels
        }
    }

    /** Byte PCM 16-bit little-endian, cắt ở chỗ bất kỳ (như ống `write` của máy tính): byte lẻ và khung dở được giữ sang lần sau. */
    fun write(data: ByteArray, offset: Int = 0, length: Int = data.size - offset) {
        for (k in offset until offset + length) {
            val byte = data[k].toInt() and 0xff
            if (low < 0) {
                low = byte
                continue
            }
            frame[filled++] = ((byte shl 8) or low).toShort()
            low = -1
            if (filled == channels) {
                feed(frame)
                filled = 0
            }
        }
    }

    private inline fun push(sample: (Int) -> Double) {
        System.arraycopy(ring, channels, ring, 0, ring.size - channels)
        val last = ring.size - channels
        for (c in 0 until channels) ring[last + c] = sample(c)
        fed++
        settle(fed - 1 - (MusicRender.FIR_TAPS - MusicRender.FIR_LEFT - 1))
    }

    /** Khung m đã đủ x[m + 6] (hay đã hết luồng): đo nó. ring[j] = x[m - 5 + j]. */
    private fun settle(m: Long) {
        if (m < 0) return
        while (segment + 1 < starts.size && m >= starts[segment + 1]) segment++
        var best = peaks[segment]
        for (c in 0 until channels) {
            best = max(best, abs(ring[MusicRender.FIR_LEFT * channels + c]))
            for (p in 0 until MusicRender.FIR_PHASES) {
                val f = fir[p]
                var v = 0.0
                for (j in 0 until MusicRender.FIR_TAPS) v += f[j] * ring[j * channels + c]
                best = max(best, abs(v))
            }
        }
        peaks[segment] = best
    }

    /** Hết luồng: đẩy 6 khung im để đo nốt các khung cuối. Trả đỉnh từng đoạn (dBTP; im hẳn = -inf). Gọi một lần. */
    fun finish(): DoubleArray {
        require(low < 0 && filled == 0) { "luồng hết giữa một khung" }
        val total = fed
        repeat(MusicRender.FIR_TAPS - MusicRender.FIR_LEFT - 1) {
            System.arraycopy(ring, channels, ring, 0, ring.size - channels)
            ring.fill(0.0, ring.size - channels, ring.size)
            val m = total - (MusicRender.FIR_TAPS - MusicRender.FIR_LEFT - 1) + it
            settle(m)
        }
        return DoubleArray(peaks.size) { if (peaks[it] > 0.0) 20 * log10(peaks[it]) else Double.NEGATIVE_INFINITY }
    }

    companion object {
        /** `_Lowered` của máy tính: mẫu hạ `db` dB = clip(rint(s * 10^(-db/20))). Đổi tại chỗ `count` mẫu từ `from`. */
        fun lower(samples: ShortArray, db: Double, count: Int = samples.size, from: Int = 0) {
            val factor = Math.pow(10.0, -db / 20)
            for (i in from until from + count) samples[i] = Math.rint(samples[i] * factor).coerceIn(-32768.0, 32767.0).toInt().toShort()
        }
    }
}
