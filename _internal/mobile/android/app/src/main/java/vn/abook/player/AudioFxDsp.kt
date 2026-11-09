package vn.abook.player

import kotlin.math.*

/** Playback only: never modifies a recording or its quality evidence. */
data class AudioFxSettings(
    val enabled: Boolean = false,
    val preset: Int = 0,
    val bands: List<Double> = List(5) { 0.0 },
    val bass: Double = 0.0,
    val boost: Double = 0.0,
    val pitch: Double = 0.0,
    val volume: Double = 0.9,
    val speed: Double = 1.0,
    val mono: Boolean = false,
    val balance: Double = 0.0,
    val skipSilence: Boolean = false,
    val silenceDb: Double = -60.0,
    val silenceSeconds: Double = 3.0,
    val keepSeconds: Double = 1.5,
) {
    fun safe() = copy(preset = preset.coerceIn(-1, 4),
        bands = List(5) { bands.getOrNull(it).finite(0.0, -12.0, 12.0) },
        bass = bass.finite(0.0, 0.0, 12.0), boost = boost.finite(0.0, 0.0, 12.0),
        pitch = pitch.finite(0.0, -6.0, 6.0), volume = volume.finite(0.9, 0.0, 1.0),
        speed = speed.finite(1.0, 0.5, 4.0), balance = balance.finite(0.0, -1.0, 1.0),
        silenceDb = silenceDb.finite(-60.0, -80.0, -45.0),
        silenceSeconds = silenceSeconds.finite(3.0, 2.0, 10.0),
        keepSeconds = keepSeconds.finite(1.5, 1.5, 3.0).coerceAtMost(silenceSeconds.finite(3.0, 2.0, 10.0)))
    fun withPreset(index: Int) = copy(preset = index, bands = PRESETS[index].toList(), bass = 0.0)
    companion object {
        val FREQUENCIES = doubleArrayOf(80.0, 250.0, 1000.0, 4000.0, 12000.0)
        val LABELS = listOf("Phẳng", "Rõ lời", "Trầm ấm", "Bổng", "Giảm chói")
        val PRESETS = listOf(doubleArrayOf(0.0, 0.0, 0.0, 0.0, 0.0),
            doubleArrayOf(-4.0, -2.0, 2.0, 3.0, -2.0), doubleArrayOf(4.0, 2.0, 0.0, -1.0, -2.0),
            doubleArrayOf(-2.0, -1.0, 0.0, 2.0, 4.0), doubleArrayOf(0.0, 0.0, 0.0, -3.0, -5.0))
        val BAND_LABELS = listOf("80 Hz", "250 Hz", "1 kHz", "4 kHz", "12 kHz")
    }
}
private fun Double?.finite(fallback: Double, lo: Double, hi: Double) =
    if (this != null && isFinite()) coerceIn(lo, hi) else fallback

/** RBJ peaking filters (Q=1.4), 120 Hz low shelf, linked stereo peak limiter. */
class AudioFxDsp(private val rate: Int, private val channels: Int) {
    class Biquad(val b0: Double, val b1: Double, val b2: Double, val a1: Double, val a2: Double, channels: Int) {
        private val z1 = DoubleArray(channels)
        private val z2 = DoubleArray(channels)
        fun tick(x: Double, channel: Int): Double {
            val y = b0 * x + z1[channel]
            z1[channel] = b1 * x - a1 * y + z2[channel]
            z2[channel] = b2 * x - a2 * y
            return y
        }
        companion object {
            fun make(rate: Int, frequency: Double, db: Double, channels: Int, shelf: Boolean = false): Biquad {
                val w = 2 * PI * min(frequency, rate * 0.45) / rate
                val a = 10.0.pow(db / 40); val c = cos(w); val s = sin(w)
                val alpha = s / (2 * 1.4)
                if (!shelf) {
                    val a0 = 1 + alpha / a
                    return Biquad((1 + alpha * a) / a0, -2*c/a0, (1-alpha*a)/a0, -2*c/a0, (1-alpha/a)/a0, channels)
                }
                val t = s * sqrt(2*a); val a0 = (a+1)+(a-1)*c+t
                return Biquad(a*((a+1)-(a-1)*c+t)/a0, 2*a*((a-1)-(a+1)*c)/a0,
                    a*((a+1)-(a-1)*c-t)/a0, -2*((a-1)+(a+1)*c)/a0, ((a+1)+(a-1)*c-t)/a0, channels)
            }
        }
    }
    private var settings = AudioFxSettings()
    private var filters = emptyList<Biquad>()
    private var gain = 1.0
    private var limiter = 1.0
    private val release = exp(-1.0 / (rate * 0.08))
    fun configure(value: AudioFxSettings) {
        val next = value.safe()
        if (next.enabled != settings.enabled || next.bands != settings.bands || next.bass != settings.bass || filters.isEmpty()) {
            filters = AudioFxSettings.FREQUENCIES.mapIndexed { i, f -> Biquad.make(rate, f, if (next.enabled) next.bands[i] else 0.0, channels) } +
                Biquad.make(rate, 120.0, if (next.enabled) next.bass else 0.0, channels, true)
        }
        settings = next
        gain = 10.0.pow(next.boost / 20)
    }
    /** Caller reuses its PCM frame; no allocations per sample. Instant attack, 80 ms release, -1 dBFS ceiling. */
    fun process(frame: DoubleArray) {
        if (channels >= 2) {
            if (settings.mono) { val mid = (frame[0] + frame[1]) * 0.5; frame[0] = mid; frame[1] = mid }
            frame[0] *= 1.0 - max(0.0, settings.balance)
            frame[1] *= 1.0 + min(0.0, settings.balance)
        }
        var peak = 0.0
        for (ch in 0 until channels) {
            var x = frame[ch]
            if (!x.isFinite()) x = 0.0
            if (settings.enabled) for (filter in filters) x = filter.tick(x, ch)
            frame[ch] = x * gain
            peak = max(peak, abs(frame[ch]))
        }
        val ceiling = 10.0.pow(-1.0/20)
        val target = if (peak > ceiling) ceiling / peak else 1.0
        limiter = min(target, 1 - (1 - limiter) * release)
        for (ch in 0 until channels) frame[ch] = (frame[ch] * limiter).coerceIn(-ceiling, ceiling)
    }
}
