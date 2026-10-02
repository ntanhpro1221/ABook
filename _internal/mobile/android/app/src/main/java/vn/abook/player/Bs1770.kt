package vn.abook.player

import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.log10
import kotlin.math.pow
import kotlin.math.roundToInt
import kotlin.math.sin
import kotlin.math.sqrt

/**
 * Độ to LUFS tích hợp theo ITU-R BS.1770-4 - cùng phép đo với `music_plan.stereo_lufs` của máy tính (pyloudnorm, bộ lọc K-weighting
 * dạng RBJ, khối 400 ms gối 75%, cổng tuyệt đối -70 và tương đối -10) để `gainDb` của một bài nhập trên điện thoại tính bằng cùng con
 * số với máy tính. Hai kênh: cộng công suất hai kênh; một kênh thì chép ra hai kênh giống nhau (+3,01 dB, như lúc phát ra hai loa).
 *
 * Đo theo dòng: mỗi lần đẩy một mẫu qua hai bộ lọc rồi cộng bình phương vào ô 100 ms; một khối 400 ms là bốn ô liền nhau, nên không
 * phải giữ cả bài trong bộ nhớ (một bản mix dài cả giờ vẫn đo được). Chỉ tính khối đủ 400 ms (pyloudnorm còn tính thêm một khối cụt
 * ở cuối khi độ dài không chia hết 100 ms - lệch dưới 0,01 LU với một bài vài phút).
 */
class Bs1770(private val rate: Int) {
    /** Bộ lọc bậc hai dạng trực tiếp I, hệ số đã chia cho a0 (như `scipy.signal.lfilter`). */
    private class Biquad(b0: Double, b1: Double, b2: Double, a0: Double, a1: Double, a2: Double) {
        private val nb0 = b0 / a0
        private val nb1 = b1 / a0
        private val nb2 = b2 / a0
        private val na1 = a1 / a0
        private val na2 = a2 / a0
        private var x1 = 0.0
        private var x2 = 0.0
        private var y1 = 0.0
        private var y2 = 0.0

        fun apply(x: Double): Double {
            val y = nb0 * x + nb1 * x1 + nb2 * x2 - na1 * y1 - na2 * y2
            x2 = x1
            x1 = x
            y2 = y1
            y1 = y
            return y
        }
    }

    private fun shelf(): Biquad {
        val a = 10.0.pow(4.0 / 40.0)
        val w0 = 2.0 * PI * (1500.0 / rate)
        val alpha = sin(w0) / (2.0 * (1.0 / sqrt(2.0)))
        val c = cos(w0)
        val s = 2.0 * sqrt(a) * alpha
        return Biquad(
            a * ((a + 1) + (a - 1) * c + s), -2 * a * ((a - 1) + (a + 1) * c), a * ((a + 1) + (a - 1) * c - s),
            (a + 1) - (a - 1) * c + s, 2 * ((a - 1) - (a + 1) * c), (a + 1) - (a - 1) * c - s,
        )
    }

    private fun highPass(): Biquad {
        val w0 = 2.0 * PI * (38.0 / rate)
        val alpha = sin(w0) / (2.0 * 0.5)
        val c = cos(w0)
        return Biquad((1 + c) / 2, -(1 + c), (1 + c) / 2, 1 + alpha, -2 * c, 1 - alpha)
    }

    private val filters = Array(2) { arrayOf(shelf(), highPass()) }
    private val cell = (rate * 0.1).roundToInt().coerceAtLeast(1) // mẫu trong một ô 100 ms
    private var filled = 0
    private var left = 0.0
    private var right = 0.0
    private val cells = ArrayList<DoubleArray>() // công suất (tổng bình phương) từng ô, từng kênh

    /** Đẩy một khung hai kênh (mẫu trong [-1, 1]); nguồn một kênh thì truyền cùng một giá trị cho cả hai. */
    fun push(l: Double, r: Double) {
        val a = filters[0][1].apply(filters[0][0].apply(l))
        val b = filters[1][1].apply(filters[1][0].apply(r))
        left += a * a
        right += b * b
        if (++filled == cell) {
            cells.add(doubleArrayOf(left, right))
            filled = 0
            left = 0.0
            right = 0.0
        }
    }

    /** LUFS tích hợp của những gì đã đẩy vào; null khi ngắn hơn 400 ms hay toàn im lặng (dưới cổng tuyệt đối). */
    fun integrated(): Double? {
        val blocks = cells.size - 3
        if (blocks <= 0) return null
        val scale = 1.0 / (4.0 * cell)
        val z = Array(blocks) { j ->
            doubleArrayOf((cells[j][0] + cells[j + 1][0] + cells[j + 2][0] + cells[j + 3][0]) * scale,
                (cells[j][1] + cells[j + 1][1] + cells[j + 2][1] + cells[j + 3][1]) * scale)
        }
        val loudness = DoubleArray(blocks) { j -> -0.691 + 10.0 * log10(z[j][0] + z[j][1]) }
        val loud = (0 until blocks).filter { loudness[it] >= ABSOLUTE_GATE }
        if (loud.isEmpty()) return null
        val relative = -0.691 + 10.0 * log10(loud.sumOf { z[it][0] } / loud.size + loud.sumOf { z[it][1] } / loud.size) - 10.0
        val kept = (0 until blocks).filter { loudness[it] > relative && loudness[it] > ABSOLUTE_GATE }
        if (kept.isEmpty()) return null
        val value = -0.691 + 10.0 * log10(kept.sumOf { z[it][0] } / kept.size + kept.sumOf { z[it][1] } / kept.size)
        return value.takeIf { it.isFinite() }
    }

    private companion object {
        const val ABSOLUTE_GATE = -70.0
    }
}
