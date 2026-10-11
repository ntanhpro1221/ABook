package vn.abook.player

import kotlin.math.PI
import kotlin.math.log10
import kotlin.math.pow
import kotlin.math.tan

/**
 * Độ to tích hợp BS.1770-4 (LUFS) theo dòng, cho bản xuất kèm nhạc trên điện thoại - máy tính đo bằng `ebur128` của ffmpeg
 * (`music_export._lufs`). Lọc K (kệ cao + thông cao RLB, hệ số theo công thức của libebur128 ở đúng tần số của luồng), khối 400 ms
 * bước 100 ms, cổng tuyệt đối -70 LUFS, cổng tương đối -10 LU. `dualMono`: một kênh tính như phát ra hai loa (+3,01 dB, như
 * `ebur128=dualmono=true`). Kết quả làm tròn 0,1 như dòng `I:` ffmpeg in ra, để số bù tính từ nó đi cùng bậc với máy tính.
 */
class Lufs(private val rate: Int, private val channels: Int, dualMono: Boolean = false) {
    private val weight = if (dualMono && channels == 1) 2.0 else 1.0
    private val shelf = Array(channels) { Biquad.shelf(rate) }
    private val highPass = Array(channels) { Biquad.highPass(rate) }
    private val step = Math.round(rate * 0.1).toInt() // khung của một khối con 100 ms
    private var inStep = 0
    private var energy = 0.0                            // tổng bình phương có trọng số của khối con đang dồn
    private val recent = DoubleArray(4)                 // 4 khối con gần nhất (khối 400 ms)
    private var filled = 0
    private val blocks = ArrayList<Double>()            // năng lượng trung bình (z) của từng khối 400 ms

    /** `count` mẫu PCM 16-bit xen kẽ kênh. */
    fun feed(pcm: ShortArray, count: Int = pcm.size) {
        require(count % channels == 0) { "khối không trọn khung" }
        var i = 0
        while (i < count) {
            for (c in 0 until channels) {
                val y = highPass[c].next(shelf[c].next(pcm[i + c] / 32768.0))
                energy += weight * y * y
            }
            i += channels
            if (++inStep == step) {
                System.arraycopy(recent, 1, recent, 0, 3)
                recent[3] = energy / step
                energy = 0.0
                inStep = 0
                if (++filled >= 4) blocks.add(recent.average())
            }
        }
    }

    /** Độ to tích hợp (LUFS, 0,1); null khi không có khối nào qua cổng (im, ngắn dưới 400 ms) hay dưới -70 như máy tính coi là không đo được. */
    fun integrated(): Double? {
        val absolute = blocks.filter { loudness(it) > -70.0 }
        if (absolute.isEmpty()) return null
        val relative = loudness(absolute.average()) - 10.0
        val gated = absolute.filter { loudness(it) > relative }
        if (gated.isEmpty()) return null
        val value = Math.round(loudness(gated.average()) * 10) / 10.0
        return if (value > -70.0) value else null
    }

    private fun loudness(z: Double) = -0.691 + 10 * log10(z)

    /** Bộ lọc bậc hai dạng trực tiếp II chuyển vị. */
    private class Biquad(val b0: Double, val b1: Double, val b2: Double, val a1: Double, val a2: Double) {
        private var s1 = 0.0
        private var s2 = 0.0

        fun next(x: Double): Double {
            val y = b0 * x + s1
            s1 = b1 * x - a1 * y + s2
            s2 = b2 * x - a2 * y
            return y
        }

        companion object {
            /** Kệ cao (tầng 1 của lọc K), hằng số libebur128. */
            fun shelf(rate: Int): Biquad {
                val f0 = 1681.974450955533
                val gain = 3.999843853973347
                val q = 0.7071752369554196
                val k = tan(PI * f0 / rate)
                val vh = 10.0.pow(gain / 20)
                val vb = vh.pow(0.4996667741545416)
                val a0 = 1.0 + k / q + k * k
                return Biquad((vh + vb * k / q + k * k) / a0, 2.0 * (k * k - vh) / a0, (vh - vb * k / q + k * k) / a0,
                    2.0 * (k * k - 1.0) / a0, (1.0 - k / q + k * k) / a0)
            }

            /** Thông cao RLB (tầng 2), tử số (1, -2, 1) như libebur128. */
            fun highPass(rate: Int): Biquad {
                val f0 = 38.13547087602444
                val q = 0.5003270373238773
                val k = tan(PI * f0 / rate)
                val a0 = 1.0 + k / q + k * k
                return Biquad(1.0, -2.0, 1.0, 2.0 * (k * k - 1.0) / a0, (1.0 - k / q + k * k) / a0)
            }
        }
    }

    companion object {
        /** Trần số bù gộp một kênh (`music_export.MONO_MAX_DB`). */
        const val MONO_MAX_DB = 4.0

        /**
         * dB bù cho bản gộp một kênh của một bài hai kênh: độ to bài phát hai loa - độ to bản gộp phát hai loa, kẹp <= [MONO_MAX_DB], làm
         * tròn 0,01 (`music_export.mono_offset_db`). Một trong hai không đo được -> 0.
         */
        fun monoOffsetDb(stereo: Double?, folded: Double?): Double =
            if (stereo == null || folded == null) 0.0 else MusicRender.round(minOf(MONO_MAX_DB, stereo - folded), 2)
    }
}
