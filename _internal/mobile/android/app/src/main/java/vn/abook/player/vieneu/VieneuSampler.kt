package vn.abook.player.vieneu

import kotlin.math.exp

/** Where the sampler's random draws (uniform in [0,1)) come from: a seeded generator in the app, a recorded stream in the bench. */
fun interface UniformSource {
    fun next(): Double

    companion object {
        fun seeded(seed: Long): UniformSource = java.util.Random(seed).let { random -> UniformSource { random.nextDouble() } }

        fun recorded(values: DoubleArray): UniformSource {
            var at = 0
            return UniformSource { values[at++] }
        }
    }
}

/**
 * The codes of one codebook over the last [window] frames (the repetition penalty only breaks LOCAL loops;
 * `vieneu/_v3_turbo_engine/rep_history.py`). [codes] is the distinct set, as the desktop's sliding-window history iterates it.
 */
class RepetitionWindow(private val window: Int, vocab: Int) {
    private val counts = IntArray(vocab)
    private val ring = IntArray(window.coerceAtLeast(1))
    private var size = 0
    private var head = 0
    private val seenMark = IntArray(vocab)
    private var stamp = 0

    fun add(code: Int) {
        counts[code]++
        if (window <= 0) return
        if (size == window) {
            val old = ring[head]
            counts[old]--
        } else {
            size++
        }
        ring[head] = code
        head = (head + 1) % window
    }

    /** Calls [visit] once per distinct code in the window. */
    fun forEachCode(visit: (Int) -> Unit) {
        stamp++
        if (window <= 0) {
            for (code in counts.indices) if (counts[code] > 0) visit(code)
            return
        }
        for (i in 0 until size) {
            val code = ring[i]
            if (seenMark[code] != stamp) {
                seenMark[code] = stamp
                visit(code)
            }
        }
    }
}

/**
 * One draw of the acoustic codebook sampler, the same maths as `OnnxV3LiteEngine._sample` of the desktop (repetition penalty,
 * temperature, top-k, nucleus), except that the final pick is an inverse-CDF draw from one uniform number so that a recorded
 * stream of uniforms reproduces a desktop run exactly (the bench). Penalty and temperature are float32 like numpy; the rest is float64.
 */
object VieneuSampler {
    /** Modifies [logits] in place (the caller owns a fresh array per draw). */
    fun sample(logits: FloatArray, history: RepetitionWindow?, repetitionPenalty: Float, temperature: Float, topK: Int, topP: Double, u: Double): Int {
        if (history != null && repetitionPenalty != 1f) {
            history.forEachCode { code ->
                val value = logits[code]
                logits[code] = if (value < 0f) value * repetitionPenalty else value / repetitionPenalty
            }
        }
        val k = topK.coerceIn(1, logits.size)
        val index = IntArray(k)
        val value = FloatArray(k)
        var count = 0
        for (v in logits.indices) {
            val x = logits[v] / temperature
            if (count == k && x <= value[k - 1]) continue
            var at = if (count < k) count++ else k - 1
            // insertion after every candidate >= x, so equal logits keep the lower index first (numpy's stable sort of -logits)
            while (at > 0 && value[at - 1] < x) {
                value[at] = value[at - 1]
                index[at] = index[at - 1]
                at--
            }
            value[at] = x
            index[at] = v
        }
        val top = value[0].toDouble()
        val p = DoubleArray(count) { exp(value[it].toDouble() - top) }
        val sum = p.sum()
        var before = 0.0
        var kept = 0.0
        for (i in 0 until count) {
            p[i] /= sum
            val keep = before < topP
            before += p[i]
            if (!keep) p[i] = 0.0
            kept += p[i]
        }
        var cdf = 0.0
        var pick = 0
        for (i in 0 until count - 1) {
            cdf += p[i] / kept
            if (cdf > u) return index[i]
            pick = i + 1
        }
        return index[pick]
    }
}
