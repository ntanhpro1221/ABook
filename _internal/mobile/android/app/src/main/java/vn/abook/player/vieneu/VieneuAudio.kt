package vn.abook.player.vieneu

import java.io.ByteArrayOutputStream
import java.io.File
import kotlin.math.ceil
import kotlin.math.sqrt

/**
 * The audio side of `vieneu_engine` (vieneu's `core_utils`) on the phone, float32 step for step like numpy so a clip comes out bit-identical:
 * frame caps from the phoneme string, syllable count, edge silence, trim + fade (Nano), the "said more than asked" (babble) check, joining
 * units with minimum pauses, and the 16-bit WAV the clip is stored as. Shared fixture tests/fixtures/vieneu/android/audio.json + text.json.
 */
object VieneuAudio {
    val GAP_SECONDS = mapOf("para" to 0.70, "sentence" to 0.50, "minor" to 0.30)
    private const val ENCODER_PAD_CODE = 455
    private val MARKUP = Regex("<\\|emotion_\\d+\\|>|</?en>")
    private const val IPA_VOWELS = "aeiouyæɐɑɒɔəɘɛɜɤɯɵøœʉʊʌɪɨɚɝᵻᵿ"
    // 10 ** (-45 / 20) and 10 ** (-18 / 20) exactly as Python computes them (numpy then compares in float32)
    private const val EDGE_THRESHOLD = 0.005623413251903491
    private const val BURST_RATIO = 0.12589254117941673

    private fun codePoints(text: String): IntArray = text.codePoints().toArray()

    private fun whitespace(cp: Int) = Character.isWhitespace(cp) || Character.isSpaceChar(cp)

    /** Python `str.split()`: runs of non-whitespace. */
    private fun words(text: String): List<String> {
        val out = ArrayList<String>()
        val current = StringBuilder()
        for (cp in codePoints(text)) {
            if (whitespace(cp)) {
                if (current.isNotEmpty()) out.add(current.toString())
                current.setLength(0)
            } else {
                current.appendCodePoint(cp)
            }
        }
        if (current.isNotEmpty()) out.add(current.toString())
        return out
    }

    /** Syllables of a sea-g2p phoneme string (core_utils.syllable_count). */
    fun phonemeSyllables(phonemes: String): Int {
        var total = 0
        for (tok in words(MARKUP.replace(phonemes, ""))) {
            var groups = 0
            var inVowel = false
            var consonantSeen = true
            val points = codePoints(tok)
            for (cp in points) {
                if (cp < 0x10000 && IPA_VOWELS.indexOf(cp.toChar()) >= 0) {
                    if (!inVowel && consonantSeen) groups++
                    inVowel = true
                    consonantSeen = false
                } else if (cp == 'ː'.code || cp == 'ˈ'.code || cp == 'ˌ'.code || Character.isDigit(cp)) {
                    if ((cp == 'ˈ'.code || cp == 'ˌ'.code) && groups > 0) {
                        inVowel = false
                        consonantSeen = true
                    } else {
                        inVowel = false
                    }
                } else {
                    inVowel = false
                    consonantSeen = true
                }
            }
            if (points.any { Character.isLetter(it) }) total += maxOf(1, groups)
        }
        return total
    }

    private fun cueOnly(phonemes: String): Boolean =
        "<|emotion_" in phonemes && codePoints(MARKUP.replace(phonemes, "")).none { Character.isLetter(it) }

    /** Sensible frame cap of one unit (core_utils.max_expected_frames): 24 + 2 x phoneme characters; <= 4 syllables: 13 + 5 x (syllables - 1). */
    fun maxExpectedFrames(phonemes: String): Int {
        val effective = MARKUP.replace(phonemes, "").let { it.codePointCount(0, it.length) }
        var cap = 24 + ceil(2.0 * effective).toInt()
        if (cueOnly(phonemes)) return minOf(cap, 13)
        if ("<|emotion_" !in phonemes) {
            val syllables = maxOf(1, phonemeSyllables(phonemes))
            if (syllables <= 4 && effective <= 24 * syllables) cap = minOf(cap, 13 + 5 * (syllables - 1))
        }
        return cap
    }

    /** numpy's float32 `add.reduce` over a contiguous run: pairwise summation in blocks of 8 (numpy `pairwise_sum`), starting from 0. */
    private fun pairwiseSum(data: FloatArray, from: Int, n: Int, value: (Float) -> Float): Float {
        if (n < 8) {
            var res = 0f
            for (i in 0 until n) res += value(data[from + i])
            return res
        }
        if (n <= 128) {
            val r = FloatArray(8) { value(data[from + it]) }
            var i = 8
            while (i < n - n % 8) {
                for (j in 0 until 8) r[j] += value(data[from + i + j])
                i += 8
            }
            var res = ((r[0] + r[1]) + (r[2] + r[3])) + ((r[4] + r[5]) + (r[6] + r[7]))
            while (i < n) res += value(data[from + i++])
            return res
        }
        var half = n / 2
        half -= half % 8
        return pairwiseSum(data, from, half, value) + pairwiseSum(data, from + half, n - half, value)
    }

    /** Per-window means of `value(x)` over windows of [win] samples (numpy `.reshape(n, win).mean(1)` in float32). */
    private fun windowMeans(wav: FloatArray, win: Int, value: (Float) -> Float): FloatArray =
        FloatArray(wav.size / win) { pairwiseSum(wav, it * win, win, value) / win.toFloat() }

    /** (leading silence, trailing silence) in samples, by the mean |x| over 10 ms windows (core_utils.edge_silence, -45 dB). */
    fun edgeSilence(wav: FloatArray, rate: Int): IntArray {
        val win = maxOf(1, (0.01 * rate).toInt())
        val env = windowMeans(wav, win) { Math.abs(it) }
        if (env.isEmpty()) return intArrayOf(wav.size, 0)
        val threshold = EDGE_THRESHOLD.toFloat()
        val first = env.indexOfFirst { it > threshold }
        if (first < 0) return intArrayOf(wav.size, 0)
        val last = env.indexOfLast { it > threshold }
        return intArrayOf(first * win, wav.size - (last + 1) * win)
    }

    /** Trim the silence at both ends (keeping 40 ms), then a 15 ms raised-cosine fade at both edges (the Nano output). */
    fun trimAndFade(wav: FloatArray, rate: Int): FloatArray {
        if (wav.isEmpty()) return wav
        val (lead, tail) = edgeSilence(wav, rate).let { it[0] to it[1] }
        val keep = (0.04 * rate).toInt()
        val from = maxOf(0, lead - keep)
        val to = wav.size - maxOf(0, tail - keep)
        val out = if (to > from) wav.copyOfRange(from, to) else FloatArray(0)
        val n = minOf((0.015 * rate).toInt(), out.size / 2)
        if (n > 0) {
            val ramp = FloatArray(n) { i ->
                val x = if (n == 1) 0.0 else if (i == n - 1) Math.PI else i * (Math.PI / (n - 1)) // np.linspace(0, pi, n)
                (0.5 - 0.5 * StrictMath.cos(x)).toFloat()
            }
            for (i in 0 until n) out[i] *= ramp[i]
            for (i in 0 until n) out[out.size - n + i] *= ramp[n - 1 - i]
        }
        return out
    }

    /** Silent samples to insert so the real pause (tail of the previous + inserted + head of the next) reaches [pauseSeconds]. */
    fun pausePadSamples(previous: FloatArray, next: FloatArray, rate: Int, pauseSeconds: Double): Int {
        val (leadPrevious, tailPrevious) = edgeSilence(previous, rate).let { it[0] to it[1] }
        val tail = if (leadPrevious == previous.size) previous.size else tailPrevious
        val lead = edgeSilence(next, rate)[0]
        return maxOf(0, (pauseSeconds * rate).toInt() - tail - lead)
    }

    /** Bursts of speech at least 30 ms long, split by gaps over 60 ms, on the 10 ms RMS envelope (core_utils.count_speech_bursts). */
    fun countSpeechBursts(wav: FloatArray, rate: Int): Int {
        val hop = maxOf(1, (rate * 0.010).toInt())
        val means = windowMeans(wav, hop) { it * it }
        if (means.isEmpty()) return 0
        val env = FloatArray(means.size) { sqrt(means[it]) }
        val peak = env.max().toDouble()
        if (peak <= 1e-6) return 0
        val threshold = (peak * BURST_RATIO).toFloat()
        val bursts = ArrayList<IntArray>()
        var start = -1
        var lastOn = -1
        for (i in env.indices) {
            if (env[i] > threshold) {
                if (start < 0) start = i
                else if (i - lastOn > 6) {
                    bursts.add(intArrayOf(start, lastOn))
                    start = i
                }
                lastOn = i
            }
        }
        if (start >= 0) bursts.add(intArrayOf(start, lastOn))
        return bursts.count { it[1] - it[0] + 1 >= 3 }
    }

    /** (suspect, syllables, bursts, frames): a unit of <= 3 syllables with more bursts than syllables, or <= 2 that hit the frame cap. */
    class Babble(val suspect: Boolean, val syllables: Int, val bursts: Int, val frames: Int) {
        /** core_utils.babble_prefer: is [this] take better than [old]? */
        fun better(old: Babble): Boolean = if (suspect != old.suspect) !suspect else bursts < old.bursts || (bursts == old.bursts && frames < old.frames)
    }

    fun babbleSuspect(wav: FloatArray, rate: Int, phonemes: String, capFrames: Int, frames: Int): Babble {
        if (cueOnly(phonemes)) return Babble(frames >= capFrames - 1, 0, 0, frames)
        val syllables = phonemeSyllables(phonemes)
        if (syllables == 0 || syllables > 3 || "<|emotion_" in phonemes) return Babble(false, syllables, 0, 0)
        val bursts = countSpeechBursts(wav, rate)
        return Babble(bursts > syllables || (syllables <= 2 && frames >= capFrames - 1), syllables, bursts, frames)
    }

    /** Drop the trailing frame the encoder padded (codebook 0 = 455) from stored reference codes `[frames][nVq]`. */
    fun stripEncoderPadFrame(codes: IntArray, nVq: Int): IntArray =
        if (codes.size / nVq > 1 && codes[codes.size - nVq] == ENCODER_PAD_CODE) codes.copyOf(codes.size - nVq) else codes

    /** Join units with minimum pauses (`pauses[i]` between unit i and i + 1): the clip and each unit's [start, end) in samples. */
    fun join(chunks: List<FloatArray>, rate: Int, pauses: List<Double>): Pair<FloatArray, List<IntArray>> {
        val pads = IntArray(chunks.size) { index ->
            if (index == 0) 0 else pausePadSamples(chunks[index - 1], chunks[index], rate, pauses.getOrElse(index - 1) { 0.0 })
        }
        val out = FloatArray(chunks.sumOf { it.size } + pads.sum())
        val spans = ArrayList<IntArray>()
        var at = 0
        for ((index, chunk) in chunks.withIndex()) {
            at += pads[index]
            chunk.copyInto(out, at)
            spans.add(intArrayOf(at, at + chunk.size))
            at += chunk.size
        }
        return out to spans
    }

    /** 16-bit mono WAV of [samples] (clipped to [-1, 1], x 32767, truncated) - the same bytes as `vieneu.wav_bytes`. */
    fun wavBytes(samples: FloatArray, rate: Int): ByteArray {
        val out = ByteArrayOutputStream(44 + samples.size * 2)
        fun put32(v: Int) { for (i in 0 until 4) out.write((v ushr (8 * i)) and 0xFF) }
        fun put16(v: Int) { out.write(v and 0xFF); out.write((v ushr 8) and 0xFF) }
        val data = samples.size * 2
        out.write("RIFF".toByteArray()); put32(36 + data); out.write("WAVEfmt ".toByteArray()); put32(16)
        put16(1); put16(1); put32(rate); put32(rate * 2); put16(2); put16(16)
        out.write("data".toByteArray()); put32(data)
        val pcm = ByteArray(data)
        for (i in samples.indices) {
            val v = (samples[i].coerceIn(-1f, 1f) * 32767f).toInt()
            pcm[2 * i] = (v and 0xFF).toByte()
            pcm[2 * i + 1] = ((v shr 8) and 0xFF).toByte()
        }
        out.write(pcm)
        return out.toByteArray()
    }

    fun writeWav(samples: FloatArray, rate: Int, file: File) = file.writeBytes(wavBytes(samples, rate))
}
