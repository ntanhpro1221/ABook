package vn.abook.player

import kotlin.math.PI
import kotlin.math.sin
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/**
 * Bs1770 (độ to của bài nhập trên điện thoại) phải ra cùng số với `music_plan.stereo_lufs` (pyloudnorm) của máy tính, để `gainDb` tính
 * từ nó khớp. Số mong đợi do Python tính trên đúng các tín hiệu này (sin, `sin(2 pi f n / rate + pha)`, kênh phải lệch pha).
 */
class Bs1770Test {
    /** Mỗi đoạn: (giây, biên độ, tần số, lệch pha kênh phải). */
    private class Part(val seconds: Double, val amplitude: Double, val frequency: Double, val shift: Double = 0.0)

    private fun measure(rate: Int, vararg parts: Part, mono: Boolean = false): Double? {
        val meter = Bs1770(rate)
        for (part in parts) {
            for (n in 0 until (rate * part.seconds).toInt()) {
                val left = part.amplitude * sin(2 * PI * part.frequency * n / rate)
                val right = if (mono) left else part.amplitude * sin(2 * PI * part.frequency * n / rate + part.shift)
                meter.push(left, right)
            }
        }
        return meter.integrated()
    }

    @Test
    fun a_stereo_sine_measures_like_pyloudnorm() {
        assertEquals(-20.034711196386542, measure(48000, Part(5.0, 0.1, 1000.0))!!, 0.001)
    }

    @Test
    fun a_mono_source_is_played_on_two_speakers() {
        // tone.wav của bộ ví dụ: một kênh 440 Hz, 8 kHz, 1 giây
        assertEquals(-21.501912452926046, measure(8000, Part(1.0, 3000 / 32768.0, 440.0), mono = true)!!, 0.001)
    }

    @Test
    fun quiet_passages_are_gated_out_and_channels_are_added_as_power() {
        val loudness = measure(44100, Part(3.0, 0.2, 440.0, 0.5), Part(2.0, 0.0005, 440.0), Part(3.0, 0.05, 3000.0, 1.0))
        assertEquals(-17.263059072160658, loudness!!, 0.001)
    }

    @Test
    fun low_frequencies_are_weighted_down_by_the_high_pass() {
        assertEquals(-14.079450845711916, measure(48000, Part(4.0, 0.3, 60.0))!!, 0.001)
    }

    @Test
    fun too_short_or_silent_audio_has_no_loudness() {
        assertNull(measure(48000, Part(0.3, 0.1, 1000.0)))
        assertNull(measure(48000, Part(2.0, 0.0, 1000.0)))
    }
}
