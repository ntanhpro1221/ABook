package vn.abook.player

import java.io.File
import java.io.RandomAccessFile
import java.nio.ByteBuffer
import java.nio.ByteOrder
import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.ceil
import kotlin.math.max
import kotlin.math.min
import kotlin.math.sin
import kotlin.math.sqrt

/** Âm thanh mono float đã giải mã ở tần số gốc của file; `read` trả 0 ngoài [0, frames). */
interface PcmSource : AutoCloseable {
    val rate: Int
    val frames: Long

    fun read(from: Long, out: FloatArray, count: Int)
}

/** Bộ giải mã file nhạc -> mono float (không resample); null khi không giải mã được. */
fun interface AudioDecoder {
    fun decode(file: File): PcmSource?
}

/** [PcmSource] trong bộ nhớ (test, bài ngắn). */
class FloatPcm(override val rate: Int, private val samples: FloatArray) : PcmSource {
    override val frames: Long get() = samples.size.toLong()

    override fun read(from: Long, out: FloatArray, count: Int) {
        for (i in 0 until count) {
            val at = from + i
            out[i] = if (at in 0 until samples.size) samples[at.toInt()] else 0f
        }
    }

    override fun close() {}
}

/**
 * Chỗ chứa PCM mono float giải mã dở trong một file tạm: bài dài tới 30 phút ở 48 kHz là 345 MB float - không để trong heap của
 * điện thoại. Ghi tuần tự bằng [append], rồi đọc ngẫu nhiên từng đoạn ([read]) cho ba cửa sổ phân tích. Đóng thì xoá file.
 */
class PcmSpool(private val file: File, override val rate: Int) : PcmSource {
    private val access = RandomAccessFile(file, "rw")
    private var written = 0L
    private val buffer = ByteBuffer.allocate(1 shl 16).order(ByteOrder.LITTLE_ENDIAN)

    override val frames: Long get() = written

    /** Ghi thêm `count` mẫu đầu của `samples`. */
    fun append(samples: FloatArray, count: Int) {
        var done = 0
        while (done < count) {
            val take = min(count - done, buffer.capacity() / 4)
            buffer.clear()
            for (i in 0 until take) buffer.putFloat(samples[done + i])
            access.write(buffer.array(), 0, take * 4)
            done += take
        }
        written += count
    }

    override fun read(from: Long, out: FloatArray, count: Int) {
        java.util.Arrays.fill(out, 0, count, 0f)
        val first = max(from, 0L)
        val last = min(from + count, written)
        if (last <= first) return
        val bytes = ByteArray(((last - first) * 4).toInt())
        access.seek(first * 4)
        access.readFully(bytes)
        val view = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).asFloatBuffer()
        view.get(out, (first - from).toInt(), (last - first).toInt())
    }

    override fun close() {
        runCatching { access.close() }
        file.delete()
    }
}

/**
 * Đổi tần số lấy mẫu về 48 kHz bằng sinc cửa sổ Kaiser nhiều pha (như swresample của ffmpeg mà máy tính dùng để giải mã:
 * 32 tiếp, cắt ở 97% Nyquist của tần số thấp hơn, Kaiser beta 9) - không lấy gần nhất / nội suy tuyến tính. Bảng 1024 pha, nội
 * suy tuyến tính giữa hai pha; mỗi pha chuẩn hoá tổng 1 (độ lợi một chiều đúng 1). Vị trí mẫu ra tính bằng số nguyên
 * (t * rate / 48000) nên không trôi.
 */
object Resampler {
    const val OUT_RATE = MusicMel.SAMPLE_RATE
    private const val PHASES = 1024
    private const val CUTOFF = 0.97
    private const val BETA = 9.0
    private const val HALF_TAPS = 16

    private class Kernel(val half: Int, val table: Array<FloatArray>)

    private val kernels = HashMap<Int, Kernel>()

    /** Bessel I0 bậc 0 (chuỗi). */
    private fun bessel0(x: Double): Double {
        var sum = 1.0
        var term = 1.0
        val quarter = x * x / 4.0
        var k = 1
        while (term > 1e-12 * sum) {
            term *= quarter / (k.toDouble() * k)
            sum += term
            k++
        }
        return sum
    }

    private fun kernel(rate: Int): Kernel = synchronized(kernels) {
        kernels.getOrPut(rate) {
            val ratio = min(1.0, OUT_RATE.toDouble() / rate)
            val half = ceil(HALF_TAPS / ratio).toInt()
            val scale = CUTOFF * ratio
            val norm = bessel0(BETA)
            val table = Array(PHASES + 1) { phase ->
                val fraction = phase.toDouble() / PHASES
                val taps = DoubleArray(2 * half) { k ->
                    val distance = fraction + (half - 1 - k) // x - i với i = floor(x) - half + 1 + k
                    val x = PI * scale * distance
                    val sinc = if (abs(x) < 1e-12) 1.0 else sin(x) / x
                    val u = distance / half
                    val window = if (abs(u) >= 1.0) 0.0 else bessel0(BETA * sqrt(1.0 - u * u)) / norm
                    scale * sinc * window
                }
                val total = taps.sum()
                FloatArray(2 * half) { (taps[it] / total).toFloat() }
            }
            Kernel(half, table)
        }
    }

    /** Số mẫu 48 kHz của một nguồn `frames` mẫu ở `rate` (làm tròn lên như ffmpeg xả nốt). */
    fun outputFrames(frames: Long, rate: Int): Long = (frames * OUT_RATE + rate - 1) / rate

    /** `count` mẫu 48 kHz bắt đầu từ mẫu `start` (đếm theo 48 kHz) của `source`; ngoài bài thì 0. */
    fun window(source: PcmSource, start: Long, count: Int): FloatArray {
        val rate = source.rate
        if (rate == OUT_RATE) return FloatArray(count).also { source.read(start, it, count) }
        val kernel = kernel(rate)
        val half = kernel.half
        val firstInput = Math.floorDiv(start * rate, OUT_RATE.toLong()) - half + 1
        val lastInput = Math.floorDiv((start + count - 1) * rate, OUT_RATE.toLong()) + half
        val span = (lastInput - firstInput + 1).toInt()
        val input = FloatArray(span)
        source.read(firstInput, input, span)
        val out = FloatArray(count)
        for (j in 0 until count) {
            val position = (start + j) * rate
            val whole = Math.floorDiv(position, OUT_RATE.toLong())
            val fraction = (position - whole * OUT_RATE).toDouble() / OUT_RATE * PHASES
            val phase = fraction.toInt()
            val blend = (fraction - phase).toFloat()
            val low = kernel.table[phase]
            val high = kernel.table[phase + 1]
            val base = (whole - half + 1 - firstInput).toInt()
            var sum = 0f
            for (k in 0 until 2 * half) {
                sum += input[base + k] * (low[k] + (high[k] - low[k]) * blend)
            }
            out[j] = sum
        }
        return out
    }
}
