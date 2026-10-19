package vn.abook.player.readaloud

import android.content.Context
import vn.abook.player.Bs1770
import vn.abook.player.MusicRender
import vn.abook.player.TruePeak
import kotlin.math.floor
import kotlin.math.min

/**
 * Bù theo clip cho giọng VieNeu và Supertonic - bản Kotlin của `loudness.py` (`lift_db`, `lift_wav`): thoại ngắn ("Ừ.", "Hừ.") ra nhỏ hơn mức giọng 3-10 LU, mà
 * `ExoPlayer.volume` chỉ giảm được, nên câu nhỏ được nâng NGAY TRONG clip lúc làm ra (trước khi ghi WAV vào bộ đệm); mức giọng ([VoiceGain]) vẫn chỉnh lúc phát.
 * Bù = (mức giọng - mức clip - vùng chết), kẹp [0, +8] dB, không quá chỗ còn trống tới -1 dBTP; làm tròn 0,1 dB. Cùng hằng số, cùng số đo với máy tính:
 * tests/fixtures/vieneu/android/lift.json (scripts/vieneu_android_fixtures.py).
 */
object ClipLift {
    val PREFIXES = listOf("vieneu:", "supertonic:")
    /** Dấu trong khoá bộ đệm (`loudness.LIFT_TAG`, xem [tag]): "ld1" = có bù theo clip; "ld2" = thêm trần đỉnh thật từng khúc ([underCeiling]). */
    const val TAG = "ld2"
    const val DEADBAND_DB = 2.0
    const val MAX_DB = 8.0
    const val CEILING_DBTP = -1.0
    const val SAFETY_DB = 0.01
    const val PAD_SECONDS = 0.5
    const val MIN_SECONDS = 0.15
    const val MIN_LUFS = -45.0

    /** Giọng này được bù theo clip: giọng VieNeu / Supertonic đã có mức đo ([voiceId] trần, không kèm bậc tốc độ - cùng một mức cho cả hai bậc). */
    fun lifts(voiceId: String): Boolean = PREFIXES.any { voiceId.startsWith(it) } && VoiceGain.measured(voiceId) != null

    /**
     * Dấu của giọng [voiceId] (mã trần) trong khoá bộ đệm (`loudness.clip_tag`): mọi giọng VieNeu / Supertonic, đã đo mức hay chưa, vì khúc nào của chúng
     * cũng qua [underCeiling] (giọng chưa đo trước đây không mang dấu: một dấu cho cả hai nhóm là đủ để clip cũ của mọi giọng ấy trượt đệm đúng một lần).
     */
    fun tag(voiceId: String): String = if (PREFIXES.any { voiceId.startsWith(it) }) TAG else ""

    private var table: MusicRender.Params? = null

    /** Bảng FIR đo đỉnh thật (asset music_mix.json) cho các giọng; nạp một lần, không nạp được thì null (không bù). */
    @Synchronized
    fun params(context: Context?): MusicRender.Params? = table ?: context?.let { ctx -> runCatching { MusicRender.Params.load(ctx) }.getOrNull() }?.also { table = it }

    /** LUFS (BS.1770, một kênh) của clip đệm lặng [PAD_SECONDS] hai đầu; null: quá ngắn / lặng hẳn. */
    fun clipLufs(samples: FloatArray, rate: Int): Double? {
        if (samples.size < MIN_SECONDS * rate) return null
        val meter = Bs1770(rate)
        val pad = (PAD_SECONDS * rate).toInt()
        repeat(pad) { meter.push(0.0, 0.0) }
        for (s in samples) meter.push(s.toDouble(), 0.0) // một kênh: kênh phải im, không nhân đôi (pyloudnorm một kênh)
        repeat(pad) { meter.push(0.0, 0.0) }
        return meter.integrated()
    }

    /** Đỉnh thật (dBTP) của clip, bằng bảng FIR chung của bản xuất kèm nhạc ([MusicRender.Params]), đo trên mẫu thực chưa lượng tử: mẫu vượt ±1 (Nano,
     *  Turbo thô) được đo đúng, không bị cắt trước khi đo. */
    fun truePeakDbtp(samples: FloatArray, params: MusicRender.Params): Double = TruePeak(params, 1).apply { feed(samples) }.finish()[0]

    /** Đỉnh mà trần [CEILING_DBTP] nhìn: đỉnh thật; `params` null (chưa nạp được bảng FIR) thì đỉnh mẫu (dBFS). Im hẳn / rỗng: -inf. */
    fun peakDb(samples: FloatArray, params: MusicRender.Params?): Double {
        if (params != null) return truePeakDbtp(samples, params)
        val peak = samples.maxOfOrNull { Math.abs(it) }?.toDouble() ?: 0.0
        return if (peak > 0.0) 20 * Math.log10(peak) else Double.NEGATIVE_INFINITY
    }

    /**
     * `loudness.under_ceiling`: một khúc ngay khi engine giọng trên máy trả ra (Nano, Turbo; Supertonic qua [SupertonicText.louder]) - đỉnh ([peakDb]) vượt
     * [CEILING_DBTP] thì hạ cả khúc xuống đúng trần (tại chỗ), không thì để nguyên từng mẫu. Thay cho cắt cứng [-1, 1]: Nano thô tới +0,8 dBFS, Turbo +1,7.
     */
    fun underCeiling(samples: FloatArray, params: MusicRender.Params?): FloatArray {
        val peak = peakDb(samples, params)
        if (peak <= CEILING_DBTP) return samples
        val factor = Math.pow(10.0, (CEILING_DBTP - peak) / 20).toFloat()
        for (i in samples.indices) samples[i] *= factor
        return samples
    }

    /** Bao nhiêu dB nâng [samples] của giọng [voiceId]; 0 = giữ nguyên. `params` null (chưa nạp được bảng FIR): không nâng, vì không đo được đỉnh thật. */
    fun liftDb(voiceId: String, samples: FloatArray, rate: Int, params: MusicRender.Params?): Double {
        if (params == null || !lifts(voiceId)) return 0.0
        val level = clipLufs(samples, rate)
        if (level == null || level < MIN_LUFS) return 0.0
        val wanted = min(MAX_DB, VoiceGain.measured(voiceId)!! - level - DEADBAND_DB)
        if (wanted < 0.05) return 0.0
        val room = CEILING_DBTP - SAFETY_DB - truePeakDbtp(samples, params)
        return maxOf(0.0, floor(min(wanted, room) * 10 + 1e-9) / 10)
    }

    /** [samples] nâng theo [liftDb] (mảng mới); không cần nâng thì chính mảng vào. */
    fun lifted(voiceId: String, samples: FloatArray, rate: Int, params: MusicRender.Params?): FloatArray {
        val gain = liftDb(voiceId, samples, rate, params)
        if (gain <= 0.0) return samples
        val factor = Math.pow(10.0, gain / 20.0)
        return FloatArray(samples.size) { (samples[it] * factor).toFloat() }
    }
}
